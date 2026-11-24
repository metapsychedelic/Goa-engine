"""nanoKONTROL2: faders, perillas, botones y transporte, contra la app de verdad.

  python3 -m pruebas.control
"""

import json
import shutil
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from goa import control as ctl
from goa.config import cargar, normalizar
from goa.control import Control
from goa.motor import Motor
from goa.web import Contexto, crear_servidor

from .app import PuertosFalsos

RAIZ = Path(__file__).resolve().parent.parent
PUERTO = 18471


def ok(cond, texto):
    print(("  ok   " if cond else "  FALLA ") + texto)
    return cond


class Puertos(PuertosFalsos):
    def __init__(self, salidas):
        self.enviados = []
        super().__init__(salidas)
        self.disponibles = self.disponibles + ["nanoKONTROL2:nanoKONTROL2 MIDI 1 32:0", "MC-101:MC-101 MIDI 1 36:0"]
        self.cambiar_salidas(salidas)

    def enviar(self, clave, tipo, canal, a, b):
        self.enviados.append((clave, tipo, canal, a, b))


def main():
    todo = True
    carpeta = Path(tempfile.mkdtemp())
    ruta = carpeta / "config.toml"
    shutil.copy(RAIZ / "config.ejemplo.toml", ruta)
    config = normalizar(cargar(ruta))
    config["control"].update(activo=True)
    config["looper"].update(activo=True, clip=3)
    config["bajo"].update(activo=True, densidad=1.0)
    config["pads"].update(activo=True)
    config["secuencia"][0].update(activa=True)
    config = normalizar(config)
    candado = threading.RLock()
    motor = Motor(config, lambda *a: None)
    puertos = Puertos(["nanoKONTROL2", "MC-101"])
    ctx = Contexto(motor, puertos, candado, str(ruta), config)
    crear_servidor(ctx, PUERTO)
    c = Control(ctx, PUERTO)
    ctx.control = c
    c.conectado = "nanoKONTROL2:nanoKONTROL2 MIDI 1 32:0"
    with candado:
        motor.start()

    def cc(n, v, espera=0.25):
        c.recibir(SimpleNamespace(type="control_change", channel=0, control=n, value=v))
        time.sleep(espera)

    def boton(n):
        cc(n, 127, 0.02)
        cc(n, 0)

    print("Faders y perillas (recogen el valor)")
    version = ctx.version_externa
    cc(1, 20)  # fader 2 = densidad del bajo; el bajo está en 1.0 (127)
    todo &= ok(ctx.config["bajo"]["densidad"] == 1.0, "lejos del valor del motor no cambia nada")
    todo &= ok(1 in c.estado()["sueltos"], "y la app lo muestra como suelto")
    for v in (110, 120, 126):
        cc(1, v, 0.1)
    cc(1, 64, 0.3)
    todo &= ok(abs(ctx.config["bajo"]["densidad"] - 0.504) < 0.01, f"al pasar por el valor engancha y sigue ({ctx.config['bajo']['densidad']})")
    todo &= ok(ctx.version_externa > version, "la app sabe que cambió (se recarga)")
    pasos = len(ctx.historia)
    for v in range(64, 30, -4):
        cc(1, v, 0.02)
    time.sleep(0.3)
    todo &= ok(len(ctx.historia) == pasos, "mover el fader seguido es un solo paso de deshacer")
    version, pasos = ctx.version_externa, len(ctx.historia)
    densidad = ctx.config["bajo"]["densidad"]
    for v in (34, 32, 35, 33, 30, 35, 33, 32, 35, 30, 34, 31, 35):   # fader sucio: tiembla sin tocarlo (como el del usuario)
        cc(1, v, 0.03)
    time.sleep(0.3)
    todo &= ok(ctx.version_externa == version and ctx.config["bajo"]["densidad"] == densidad,
               f"un fader que tiembla solo no cambia nada (la app no se recarga)")
    for v in range(36, 52, 1):
        cc(1, v, 0.02)
    time.sleep(0.3)
    todo &= ok(abs(ctx.config["bajo"]["densidad"] - 51 / 127) < 0.01, f"moverlo de verdad sí, fino y hasta donde lo dejas ({ctx.config['bajo']['densidad']})")
    cc(1, 0, 0.3)
    todo &= ok(ctx.config["bajo"]["densidad"] == 0.0, "y llega al extremo aunque sea un paso chico")
    cc(16 + 7, 90)  # perilla del looper: resonancia CC 71 a la MC-101
    todo &= ok(("MC-101", "control_change", 3, 71, 90) in puertos.enviados, "perilla del looper: CC 71 a la MC-101, canal 4")
    cc(7, 40)
    todo &= ok(("MC-101", "control_change", 3, 74, 40) in puertos.enviados, "fader del looper: filtro CC 74")
    todo &= ok(not any(e[3] == 7 for e in puertos.enviados if e[1] == "control_change"), "nunca manda volumen (CC 7)")
    actual = ctl.a_cc("pads", "variacion", ctx.config["pads"]["variacion"])
    cc(16, actual)
    cc(16, 127)
    todo &= ok(ctx.config["pads"]["variacion"] == 1.0, "perilla de pads: variación")

    print("\nBotones de cada canal")
    boton(48 + 1)  # M del bajo
    todo &= ok(ctx.config["bajo"]["activo"] is False, "M apaga el bajo")
    boton(48 + 1)
    todo &= ok(ctx.config["bajo"]["activo"] is True, "M otra vez lo prende")
    boton(32 + 0)  # S de pads
    todo &= ok(ctx.config["pads"]["activo"] and not ctx.config["bajo"]["activo"] and not ctx.config["secuencia"][0]["activa"]
               and not ctx.config["looper"]["activo"], "S deja solo los pads")
    boton(32 + 0)
    todo &= ok(ctx.config["bajo"]["activo"] and ctx.config["secuencia"][0]["activa"] and ctx.config["looper"]["activo"],
               "S otra vez: vuelven los que sonaban")
    seed = ctx.config["secuencia"][0]["seed"]
    boton(64 + 2)
    todo &= ok(ctx.config["secuencia"][0]["seed"] != seed, "R de la secuencia A: seed nueva")
    boton(64 + 7)
    todo &= ok(ctx.config["looper"]["clip"] == 4, "R del looper: el loop siguiente")

    print("\nTransporte y escenas")
    boton(ctl.SET)
    todo &= ok(len(ctx.config["escena"]) == 1 and c.escena == 0, "SET guarda lo que suena como escena nueva")
    boton(64 + 7)  # looper al 5
    boton(ctl.SET)
    todo &= ok(len(ctx.config["escena"]) == 2, "otra escena")
    boton(ctl.TRACK_ANT)
    todo &= ok(c.estado()["escena"] == 0, "◀ TRACK elige la escena 1")
    boton(ctl.PLAY)
    todo &= ok(ctx.config["forma"]["escena"] == 0 and ctx.config["looper"]["clip"] == 4, "PLAY la lanza")
    boton(ctl.STOP)
    todo &= ok(ctx.config["forma"]["escena"] == 1, "STOP vuelve a la de antes")
    e = ctx.config["forma"]["energia"]
    boton(ctl.MARKER_SIG)
    todo &= ok(abs(ctx.config["forma"]["energia"] - min(1.0, e + 0.1)) < 1e-6, "▶ MARKER sube la energía")
    boton(ctl.CYCLE)
    todo &= ok(ctx.config["forma"]["piloto"] is True, "CYCLE prende el piloto")
    boton(ctl.CYCLE)
    boton(64 + 7)
    clip = ctx.config["looper"]["clip"]
    boton(ctl.REW)
    todo &= ok(ctx.config["looper"]["clip"] == clip - 1, "REW deshace")
    boton(ctl.GRABAR)
    todo &= ok(motor.subida_pedida == ctx.config["control"]["subida"] or motor.subida is not None, "REC pide la subida")
    boton(ctl.GRABAR)
    todo &= ok(motor.subida_pedida in (None, 0) and motor.subida is None, "REC otra vez la cancela")

    print("\nSi el valor cambia por otro lado (escena, app), los controles recogen otra vez")
    import urllib.request
    def ajuste_app(valor):
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PUERTO}/api/ajuste",
            data=json.dumps({"cambios": [["bajo", None, "densidad", valor]]}).encode(),
            headers={"Content-Type": "application/json"}, method="POST"))
    ajuste_app(0.9)
    cc(1, 5)
    todo &= ok(ctx.config["bajo"]["densidad"] == 0.9, "un fader lejos del valor nuevo no salta")
    for v in (100, 110, 116):
        cc(1, v, 0.1)
    todo &= ok(abs(ctx.config["bajo"]["densidad"] - 116 / 127) < 0.01, "al llegar al valor nuevo engancha")

    print("\nLuces")
    time.sleep(0.4)
    luces = {(e[3]): e[4] for e in puertos.enviados if e[0] == "nanoKONTROL2"}
    todo &= ok(luces.get(48 + 1) == 127 and luces.get(48 + 0) == 127, "M prendido en los motores que suenan")
    todo &= ok(luces.get(ctl.PLAY) == 127, "PLAY prendido con una escena sonando")
    cfg = json.loads(json.dumps(ctx.config))
    cfg["control"]["canal"] = 2
    urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PUERTO}/api/config", data=json.dumps(cfg).encode(),
                                                  headers={"Content-Type": "application/json"}, method="POST"))
    antes = json.loads(json.dumps(ctx.config["bajo"]))
    boton(48 + 1)
    todo &= ok(ctx.config["bajo"] == antes, "otro canal MIDI: no hace caso")

    print("\nTodo bien" if todo else "\nHAY FALLAS")
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
