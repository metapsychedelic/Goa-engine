"""Levanta la app con una Circuit simulada, sin MIDI real.

  python3 -m pruebas.app [ruta-config]     y abre http://localhost:8080
"""

import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

from goa.config import cargar, salidas
from goa.motor import Motor
from goa.web import Contexto, crear_servidor

RAIZ = Path(__file__).resolve().parent.parent


class PuertosFalsos:
    def __init__(self, salidas):
        self.disponibles = ["Circuit Tracks:Circuit Tracks MIDI 1 20:0", "FM-1:FM-1 MIDI 1 24:0", "Midi Through:Midi Through Port-0 14:0"]
        self.cambiar_salidas(salidas)

    def cambiar_salidas(self, salidas):
        self.salidas = sorted(set(salidas))
        self.abiertos = {k: True for k in self.salidas if any(k.lower() in n.lower() for n in self.disponibles)}

    def panico(self):
        pass


def main():
    ruta = sys.argv[1] if len(sys.argv) > 1 else None
    if ruta is None:
        ruta = str(Path(tempfile.mkdtemp()) / "config.toml")
        shutil.copy(RAIZ / "config.ejemplo.toml", ruta)
    config = cargar(ruta)
    candado = threading.RLock()
    motor = Motor(config, lambda *a: None)
    puertos = PuertosFalsos(salidas(config))
    ctx = Contexto(motor, puertos, candado, ruta, config)
    ctx.entrada = "Circuit Tracks:Circuit Tracks MIDI 1 20:0"
    crear_servidor(ctx, config["app"]["puerto"])
    print("App en http://localhost:%d · config: %s" % (config["app"]["puerto"], ruta))
    with candado:
        motor.start()
        motor.nota_on(motor.canal_disparo, 41)
    while True:  # reloj a 140 BPM
        time.sleep(60 / 140 / 24)
        with candado:
            motor.reloj()


if __name__ == "__main__":
    main()
