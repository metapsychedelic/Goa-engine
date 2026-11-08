"""Punto de entrada: abre los puertos MIDI y conecta la Circuit con el motor."""

import argparse
import logging
import signal
import threading
import time
import tomllib

import mido

from .motor import Motor

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

    def revisar(self):
        disponibles = mido.get_output_names()
        for clave in self.salidas:
            puerto = self.abiertos.get(clave)
            if puerto is not None and puerto.name not in disponibles:
                log.warning("Se desconectó la salida %r", clave)
                puerto.close()
                del self.abiertos[clave]
            if clave not in self.abiertos:
                nombre = buscar_puerto(disponibles, clave)
                if nombre:
                    self.abiertos[clave] = mido.open_output(nombre)
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

    with open(args.config, "rb") as f:
        config = tomllib.load(f)

    puertos = Puertos([s["salida"] for s in config.get("secuencia", [])])
    candado = threading.Lock()

    def enviar(salida, tipo, canal, nota, velocidad):
        if args.debug and tipo == "note_on":
            log.debug("%s canal %d nota %d vel %d", salida, canal + 1, nota, velocidad)
        puertos.enviar(salida, tipo, canal, nota, velocidad)

    motor = Motor(config, enviar)
    log.info("Secuencias: %s", ", ".join(f"{s.nombre} -> {s.salida} canal {s.canal + 1}" for s in motor.secuencias))

    def al_recibir(msg):
        with candado:
            t = msg.type
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

    nombre_entrada = config.get("entrada", {}).get("puerto", "Circuit")
    entrada = None
    terminar = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: terminar.set())
    signal.signal(signal.SIGINT, lambda *_: terminar.set())

    try:
        while not terminar.is_set():
            with candado:
                puertos.revisar()
            disponibles = mido.get_input_names()
            if entrada is not None and entrada.name not in disponibles:
                log.warning("Se desconectó la entrada %r", nombre_entrada)
                entrada.close()
                entrada = None
                with candado:
                    motor.stop()
            if entrada is None:
                nombre = buscar_puerto(disponibles, nombre_entrada)
                if nombre:
                    entrada = mido.open_input(nombre, callback=al_recibir)
                    log.info("Entrada conectada: %s", nombre)
            terminar.wait(2.0)
    finally:
        with candado:
            motor.apagar_todo()
        if entrada is not None:
            entrada.close()
        puertos.cerrar()
        log.info("Motor detenido")


if __name__ == "__main__":
    main()
