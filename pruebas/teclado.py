"""Teclado de la MicroFreak: con Local Off el motor le devuelve sus perillas.

  python3 -m pruebas.teclado
"""

import threading
from pathlib import Path
from types import SimpleNamespace

from goa.config import cargar, normalizar, salidas
from goa.motor import Motor
from goa.teclado import Teclado
from goa.web import Contexto

RAIZ = Path(__file__).resolve().parent.parent


def ok(cond, texto):
    print(("  ok   " if cond else "  FALLA ") + texto)
    return cond


class Puertos:
    def __init__(self):
        self.enviados = []

    def enviar(self, *m):
        self.enviados.append(m)


def msg(tipo, canal, **datos):
    return SimpleNamespace(type=tipo, channel=canal, **datos)


def main():
    todo = True
    cfg = normalizar(cargar(RAIZ / "config.ejemplo.toml"))
    cfg["teclado"].update(activo=True)
    cfg = normalizar(cfg)
    puertos = Puertos()
    ctx = Contexto(Motor(cfg, lambda *a: None), puertos, threading.RLock(), "/tmp/no-se-usa.toml", cfg)
    t = Teclado(ctx)
    todo &= ok("MicroFreak" in salidas(cfg), "abre la salida a la MicroFreak (para devolverle las perillas)")
    t.recibir(msg("control_change", 9, control=23, value=80))
    todo &= ok(puertos.enviados == [("MicroFreak", "control_change", 2, 23, 80)], "perilla (canal 10) vuelve por USB al canal 3, el del pad")
    t.recibir(msg("pitchwheel", 9, pitch=-2000))
    todo &= ok(puertos.enviados[-1] == ("MicroFreak", "pitchwheel", 2, -2000, 0), "la cinta de pitch bend también")
    n = len(puertos.enviados)
    t.recibir(msg("control_change", 2, control=23, value=80))
    todo &= ok(len(puertos.enviados) == n, "lo que vuelve por el canal 3 no se devuelve otra vez (sin bucle)")
    t.recibir(msg("note_on", 9, note=60, velocity=100))
    todo &= ok(len(puertos.enviados) == n and t.estado()["apretadas"] == 1, "las teclas no van a la MicroFreak: quedan para el motor")
    t.recibir(msg("note_off", 9, note=60, velocity=0))
    todo &= ok(t.estado()["apretadas"] == 0 and t.estado()["ultimo"] == "nota 60 (100)", "suelta la tecla")
    ctx.config["teclado"]["perillas"] = False
    t.recibir(msg("control_change", 9, control=23, value=10))
    todo &= ok(len(puertos.enviados) == n, "con «Devolverle sus perillas» apagado no devuelve nada")
    print("\nTodo bien" if todo else "\nHAY FALLAS")
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
