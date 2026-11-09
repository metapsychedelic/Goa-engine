"""Punto de entrada: abre los puertos MIDI, conecta la Circuit con el motor y sirve la app."""

import argparse
import logging
import signal
import threading

import mido

from .config import ConfigError, cargar, salidas
from .motor import Motor
from .web import Contexto, crear_servidor

log = logging.getLogger("goa")


def buscar_puerto(nombres, parte):
    parte = parte.lower()
    for n in nombres:
        if parte in n.lower():
            return n
    return None


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
        self.disponibles = mido.get_output_names()
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


def main():
    parser = argparse.ArgumentParser(description="Motor generativo Goa")
    parser.add_argument("--config", required=True, help="ruta al archivo config.toml")
    parser.add_argument("--debug", action="store_true", help="registra cada nota")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    try:
        config = cargar(args.config)
    except (ConfigError, OSError, ValueError) as e:
        log.error("No pude leer %s: %s", args.config, e)
        raise SystemExit(1)

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

    def al_recibir(msg):
        with candado:
            t = msg.type
            thru = ctx.config["thru"]
            if thru["activo"] and t != "sysex":
                # Pasa todo lo de la Circuit (reloj, notas, CC) a la cadena MIDI.
                puertos.reenviar(thru["salida"], msg)
            if t == "clock":
                motor.reloj()
            elif t == "note_on" and msg.velocity > 0:
                motor.nota_on(msg.channel, msg.note)
            elif t == "note_off" or t == "note_on":
                motor.nota_off(msg.channel, msg.note)
            elif t == "start":
                motor.start()
            elif t == "stop":
                motor.stop()
            elif t == "continue":
                motor.continuar()

    entrada = None
    terminar = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: terminar.set())
    signal.signal(signal.SIGINT, lambda *_: terminar.set())

    try:
        while not terminar.is_set():
            with candado:
                puertos.revisar()
                nombre_entrada = ctx.config["entrada"]["puerto"]
            disponibles = mido.get_input_names()
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
            terminar.wait(2.0)
    finally:
        with candado:
            motor.apagar_todo()
        if servidor is not None:
            servidor.shutdown()
        if entrada is not None:
            entrada.close()
        puertos.cerrar()
        log.info("Motor detenido")


if __name__ == "__main__":
    main()
