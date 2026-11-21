"""Punto de entrada: abre los puertos MIDI, conecta la Circuit con el motor y sirve la app."""

import argparse
import os
import re
import logging
import signal
import threading

import mido

from .config import ConfigError, cargar, salidas
from .control import Control
from .teclado import Teclado
from .motor import Motor
from .web import Contexto, crear_servidor

log = logging.getLogger("goa")


def es_propio(nombre):
    """Puertos que crea el propio motor (cada salida abierta con rtmidi aparece como
    «RtMidiOut Client») o el sistema (Midi Through). Escuchar uno de esos es escucharse
    a sí mismo: lo que el motor manda vuelve a entrar y se realimenta sin fin (así se
    colgó la Pi en la 0.65 con el teclado apuntando a «RtMidiOut Client #1»)."""
    n = nombre.lower()
    return "rtmidi" in n or "midi through" in n


def sin_propios(nombres):
    return [n for n in nombres if not es_propio(n)]


def buscar_puerto(nombres, parte):
    """El puerto cuyo nombre contiene `parte`. Con dos aparatos iguales (dos dongles
    CH345, por ejemplo) «CH345 #2» elige el segundo, en el orden en que los ve el sistema."""
    m = re.fullmatch(r"(.*?)\s*#(\d+)", parte.strip())
    cual = int(m.group(2)) if m else 1
    parte = (m.group(1) if m else parte).lower()
    if es_propio(parte):
        return None
    hallados = [n for n in sin_propios(nombres) if parte in n.lower()]
    return hallados[cual - 1] if 0 < cual <= len(hallados) else None


class Puertos:
    """Salidas MIDI buscadas por parte del nombre, con reconexión."""

    def __init__(self, salidas):
        self.salidas = sorted(set(salidas))
        self.abiertos = {}
        self.avisados = set()
        self.disponibles = []

    def cambiar_salidas(self, salidas):
        nuevas = sorted(set(salidas))
        for clave in list(self.abiertos):
            if clave not in nuevas:
                self.abiertos.pop(clave).close()
        self.salidas = nuevas
        self.revisar()

    def revisar(self):
        self.disponibles = sin_propios(mido.get_output_names())
        for clave in self.salidas:
            puerto = self.abiertos.get(clave)
            if puerto is not None and puerto.name not in self.disponibles:
                log.warning("Se desconectó la salida %r", clave)
                puerto.close()
                del self.abiertos[clave]
            if clave not in self.abiertos:
                nombre = buscar_puerto(self.disponibles, clave)
                if nombre:
                    try:
                        self.abiertos[clave] = mido.open_output(nombre)
                    except OSError as e:
                        log.warning("No pude abrir %s: %s", nombre, e)
                        continue
                    self.avisados.discard(clave)
                    log.info("Salida %r conectada: %s", clave, nombre)
                elif clave not in self.avisados:
                    self.avisados.add(clave)
                    log.warning("No encuentro la salida %r. Revisa el cable o corre goa-ports.", clave)

    def enviar(self, clave, tipo, canal, nota, velocidad):
        puerto = self.abiertos.get(clave)
        if puerto is None:
            return
        try:
            if tipo == "program_change":
                puerto.send(mido.Message("program_change", channel=canal, program=nota))
            elif tipo == "control_change":
                puerto.send(mido.Message("control_change", channel=canal, control=nota, value=velocidad))
            elif tipo == "pitchwheel":
                puerto.send(mido.Message("pitchwheel", channel=canal, pitch=nota))
            else:
                puerto.send(mido.Message(tipo, channel=canal, note=nota, velocity=velocidad))
        except (OSError, ValueError) as e:
            log.warning("Error enviando a %r: %s", clave, e)

    def reenviar(self, clave, msg):
        puerto = self.abiertos.get(clave)
        if puerto is None:
            return
        try:
            puerto.send(msg)
        except (OSError, ValueError) as e:
            log.warning("Error reenviando a %r: %s", clave, e)

    def panico(self):
        """All Notes Off en los 16 canales de cada salida abierta."""
        for puerto in self.abiertos.values():
            for canal in range(16):
                try:
                    puerto.send(mido.Message("control_change", channel=canal, control=123, value=0))
                except (OSError, ValueError):
                    pass

    def cerrar(self):
        for p in self.abiertos.values():
            p.close()


def cargar_seguro(ruta):
    """La configuración del usuario; si está dañada (un corte de luz, una tarjeta con
    problemas), la última buena (`.respaldo`), y si tampoco, la de ejemplo. Así el
    motor arranca igual y no queda reiniciándose cada 2 segundos."""
    try:
        if os.path.getsize(ruta) == 0:
            raise ValueError("el archivo quedó vacío")
        return cargar(ruta)
    except (ConfigError, OSError, ValueError) as e:
        log.error("No pude leer %s: %s", ruta, e)
    for otra in (ruta + ".respaldo", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.ejemplo.toml")):
        try:
            if os.path.exists(otra) and os.path.getsize(otra) == 0:
                raise ValueError("el archivo está vacío")
            config = cargar(otra)
        except (ConfigError, OSError, ValueError) as e:
            log.error("Tampoco pude leer %s: %s", otra, e)
            continue
        log.warning("Arranco con %s. Tu configuración dañada queda como %s.dañada", otra, ruta)
        try:
            if os.path.exists(ruta):
                os.replace(ruta, ruta + ".dañada")
        except OSError:
            pass
        return config
    raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description="Motor generativo Goa")
    parser.add_argument("--config", required=True, help="ruta al archivo config.toml")
    parser.add_argument("--debug", action="store_true", help="registra cada nota")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    config = cargar_seguro(args.config)

    puertos = Puertos(salidas(config))
    candado = threading.RLock()

    def enviar(salida, tipo, canal, nota, velocidad):
        if args.debug and tipo == "note_on":
            log.debug("%s canal %d nota %d vel %d", salida, canal + 1, nota, velocidad)
        puertos.enviar(salida, tipo, canal, nota, velocidad)

    motor = Motor(config, enviar)
    log.info("Secuencias: %s", ", ".join(f"{s.nombre} -> {s.salida} canal {s.canal + 1}" for s in motor.secuencias))

    ctx = Contexto(motor, puertos, candado, args.config, config)
    servidor = None
    try:
        servidor = crear_servidor(ctx, config["app"]["puerto"])
    except OSError as e:
        log.error("No pude abrir la app web: %s", e)

    errores = set()
    control = Control(ctx, config["app"]["puerto"])
    ctx.control = control
    teclado = Teclado(ctx)
    ctx.teclado = teclado

    def al_recibir(msg):
        try:
            procesar(msg)
        except Exception as e:  # noqa: BLE001
            # Un error en un paso no debe dejar el motor sordo: se anota (una vez por
            # tipo de error) y el siguiente pulso sigue normal.
            clave = f"{type(e).__name__}: {e}"
            if clave not in errores:
                errores.add(clave)
                log.exception("Error procesando %s (el motor sigue)", msg.type)

    def procesar(msg):
        with candado:
            t = msg.type
            thru = ctx.config["thru"]
            if thru["activo"] and t != "sysex" and getattr(msg, "channel", None) not in motor.canales_disparo:
                # Pasa todo lo de la Circuit (reloj, notas, CC) a la cadena MIDI,
                # menos los canales de las notas largas: esas notas son solo para la Pi.
                puertos.reenviar(thru["salida"], msg)
            if t == "clock":
                motor.reloj()
            elif t == "note_on" and msg.velocity > 0:
                motor.nota_on(msg.channel, msg.note, msg.velocity)
            elif t == "note_off" or t == "note_on":
                motor.nota_off(msg.channel, msg.note)
            elif t == "start":
                motor.start()
            elif t == "stop":
                motor.stop()
            elif t == "continue":
                motor.continuar()

    def revisar_entrada(abierta, disponibles, nombre_entrada, seccion, receptor, que):
        """Una entrada aparte de la de la Circuit (el nanoKONTROL2, el teclado de la
        MicroFreak), abierta mientras su sección esté activa, con reconexión."""
        with candado:
            c = ctx.config[seccion]
            quiero = c["puerto"] if c["activo"] else None
        if quiero and nombre_entrada.lower() in quiero.lower():
            quiero = None  # el mismo puerto que la Circuit: no se abre dos veces
        if abierta is not None and (quiero is None or abierta.name not in disponibles
                                    or quiero.lower() not in abierta.name.lower()):
            log.info("%s desconectado: %s", que, abierta.name)
            abierta.close()
            abierta = None
            receptor.conectado = None
        if abierta is None and quiero:
            nombre = buscar_puerto(disponibles, quiero)
            if nombre:
                try:
                    abierta = mido.open_input(nombre, callback=receptor.recibir)
                except OSError as e:
                    log.warning("No pude abrir %s: %s", nombre, e)
                else:
                    receptor.conectado = nombre
                    log.info("%s conectado: %s", que, nombre)
        return abierta

    entrada = None
    entrada_control = None
    entrada_teclado = None
    terminar = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: terminar.set())
    signal.signal(signal.SIGINT, lambda *_: terminar.set())

    try:
        while not terminar.is_set():
            with candado:
                puertos.revisar()
                nombre_entrada = ctx.config["entrada"]["puerto"]
                ctx.sincronizar_tocado()   # lo grabado en el Tocado queda guardado aunque la app esté cerrada
            disponibles = sin_propios(mido.get_input_names())
            with candado:
                ctx.entradas_disponibles = disponibles
            if entrada is not None and (entrada.name not in disponibles
                                        or nombre_entrada.lower() not in entrada.name.lower()):
                log.warning("Se desconectó la entrada %s", entrada.name)
                entrada.close()
                entrada = None
                with candado:
                    ctx.entrada = None
                    motor.stop()
                    puertos.panico()  # por si quedó una nota reenviada sin su note_off
            if entrada is None:
                nombre = buscar_puerto(disponibles, nombre_entrada)
                if nombre:
                    try:
                        entrada = mido.open_input(nombre, callback=al_recibir)
                    except OSError as e:
                        log.warning("No pude abrir %s: %s", nombre, e)
                    else:
                        with candado:
                            ctx.entrada = nombre
                        log.info("Entrada conectada: %s", nombre)
            entrada_control = revisar_entrada(entrada_control, disponibles, nombre_entrada, "control", control, "Controlador")
            entrada_teclado = revisar_entrada(entrada_teclado, disponibles, nombre_entrada, "teclado", teclado, "Teclado")
            terminar.wait(2.0)
    finally:
        with candado:
            motor.apagar_todo()
        ctx.guardar_ya()  # lo último que cambiaste queda en la tarjeta
        if servidor is not None:
            servidor.shutdown()
        if entrada is not None:
            entrada.close()
        for abierta in (entrada_control, entrada_teclado):
            if abierta is not None:
                abierta.close()
        puertos.cerrar()
        log.info("Motor detenido")


if __name__ == "__main__":
    main()
