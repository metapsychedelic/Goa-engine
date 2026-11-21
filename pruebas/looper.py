"""Looper de la MC-101: cada escena elige su loop (slot 1-16) por Program Change.

  python3 -m pruebas.looper
"""

import json
from pathlib import Path

from goa import forma
from goa.config import cargar, normalizar, salidas
from goa.motor import Motor

RAIZ = Path(__file__).resolve().parent.parent
PULSOS = 96  # por compás


def ok(cond, texto):
    print(("  ok   " if cond else "  FALLA ") + texto)
    return cond


def base(**looper):
    cfg = normalizar(cargar(RAIZ / "config.ejemplo.toml"))
    cfg["entrada"].update(canal_disparo=2, nota_maxima=0)
    cfg["secuencia"] = [dict(s, disparo=0) for s in cfg["secuencia"]]
    cfg["looper"].update(dict(activo=True, salida="MC-101", canal=4), **looper)
    return normalizar(cfg)


class Registro:
    def __init__(self):
        self.motor = None
        self.pcs = []   # (compás, pulso dentro del compás, salida, canal, programa)

    def __call__(self, salida, tipo, canal, a, b):
        if tipo == "program_change" and salida == "MC-101" and canal == 3:
            t = max(self.motor.tick, 0) if self.motor else 0
            self.pcs.append((t // PULSOS, t % PULSOS, a))


def arrancar(cfg):
    r = Registro()
    m = Motor(cfg, r)
    r.motor = m
    m.start()
    m.nota_on(1, 45)
    return m, r


def compases(m, n):
    for _ in range(n * PULSOS):
        m.reloj()


def main():
    todo = True
    print("Looper en modo libre")
    m, r = arrancar(base(clip=3))
    compases(m, 2)
    todo &= ok([p[2] for p in r.pcs] == [2], f"al arrancar pide el loop 3 (PC 2) una sola vez {r.pcs}")
    cfg = json.loads(json.dumps(m.base))
    cfg["looper"]["clip"] = 7
    m.aplicar_config(normalizar(cfg))
    compases(m, 2)
    todo &= ok([p[2] for p in r.pcs] == [2, 6], "cambiarlo desde la app lo pide de inmediato (la MC-101 cuantiza)")
    m.start()
    compases(m, 1)
    todo &= ok([p[2] for p in r.pcs] == [2, 6, 6], "en cada Start lo vuelve a pedir")

    m, r = arrancar(base(clip=0, parar=0))
    compases(m, 2)
    todo &= ok(r.pcs == [], "sin loop y sin slot vacío no manda nada")
    m, r = arrancar(base(clip=0, parar=16))
    compases(m, 2)
    todo &= ok([p[2] for p in r.pcs] == [15], "sin loop y con slot vacío 16: lanza el 16 para callar")
    m, r = arrancar(dict(base(clip=5), looper=dict(base()["looper"], activo=False, clip=5)))
    compases(m, 2)
    todo &= ok(r.pcs == [], "apagado no manda nada")
    todo &= ok("MC-101" in salidas(base(clip=1)), "abre el puerto de la MC-101")

    print("\nEntra con la frase")
    m, r = arrancar(base(clip=3, cada=4))
    compases(m, 5)
    cfg = json.loads(json.dumps(m.base))
    cfg["looper"]["clip"] = 8
    m.aplicar_config(normalizar(cfg))   # en el compás 6 (índice 5)
    compases(m, 4)
    todo &= ok(r.pcs[-1] == (7, 48, 7), f"cada 4: pedido en el compás 6, entra en el 9 (se pide en la mitad del 8) {r.pcs}")
    m, r = arrancar(base(clip=3, cada=1))
    compases(m, 2)
    for _ in range(10):
        m.reloj()   # pulso 10 del compás 3
    cfg = json.loads(json.dumps(m.base)); cfg["looper"]["clip"] = 5
    m.aplicar_config(normalizar(cfg))   # (los cambios de la app entran en el compás siguiente)
    compases(m, 2)
    todo &= ok(r.pcs[-1] == (3, 48, 4), f"cada compás: en la mitad del compás, no justo en el uno {r.pcs}")
    cfg["looper"]["clip"] = 3
    m.aplicar_config(normalizar(cfg))
    cfg["looper"]["clip"] = 5
    m.aplicar_config(normalizar(cfg))
    compases(m, 2)
    todo &= ok(r.pcs[-1] == (3, 48, 4) and len([p for p in r.pcs if p[2] == 4]) == 1, "ir y volver al mismo loop antes de que entre no manda nada")

    print("\nEscenas")
    cfg = base(clip=1, parar=16)
    escena_b = forma.escena_de(dict(cfg, looper=dict(cfg["looper"], clip=9, parar=3)), "B")
    escena_c = forma.escena_de(dict(cfg, looper=dict(cfg["looper"], clip=0)), "C")
    todo &= ok(json.loads(escena_b["datos"])["looper"] == {"activo": True, "clip": 9, "cada": 1},
               "la escena guarda si suena, qué loop y cada cuánto entra (no la salida, el canal, el slot vacío ni el transporte)")
    m, r = arrancar(cfg)
    compases(m, 3)
    m.lanzar_escena(normalizar(forma.mezclar(m.base, escena_b)), 4)   # llega en el compás 3+4 = 7 (índice 6)
    compases(m, 6)
    llegada = m.conductor.transicion.fin if m.conductor.transicion else 6
    pcs_b = [p for p in r.pcs if p[2] == 8]
    todo &= ok(len(pcs_b) == 1 and pcs_b[0][:2] == (6 - 1, 48),
               f"pide el loop 9 en la mitad del compás antes de que llegue la escena (nunca justo en el uno) {pcs_b}")
    todo &= ok(m.base["looper"]["parar"] == 16, "el slot vacío es de la máquina: la escena no lo cambia")
    m.lanzar_escena(normalizar(forma.mezclar(m.base, escena_c)), 1)   # en el próximo compás
    pide = len(r.pcs)
    todo &= ok(r.pcs[-1][2] == 15 and r.pcs[-1][0] == m._compas_actual(), "escena sin loop en el próximo compás: calla de inmediato (slot 16)")
    compases(m, 3)
    todo &= ok(len(r.pcs) == pide, "y no lo repite")
    vieja = {"nombre": "vieja", "energia": 0.5, "datos": json.dumps({k: v for k, v in json.loads(escena_b["datos"]).items() if k != "looper"})}
    m.lanzar_escena(normalizar(forma.mezclar(m.base, vieja)), 1)
    compases(m, 2)
    todo &= ok(len(r.pcs) == pide, "una escena guardada antes del looper no lo toca")
    del llegada

    print("\nModo canción")
    cfg = base(clip=2)
    cfg["escena"] = [forma.escena_de(cfg, "A"), escena_b]
    cfg["parte"] = [dict(nombre="A", compases=8, escena=0), dict(nombre="B", compases=8, escena=1, entrada="golpe")]
    cfg["cancion"]["activa"] = True
    cfg = normalizar(cfg)
    m, r = arrancar(cfg)
    compases(m, 18)
    todo &= ok([(p[0], p[2]) for p in r.pcs][:2] == [(0, 1), (7, 8)],
               f"parte A con el loop 2; el loop 9 de la parte B se pide en el compás antes (8) {[(p[0] + 1, p[2] + 1) for p in r.pcs]}")
    todo &= ok([(p[0], p[2]) for p in r.pcs][2:3] == [(15, 1)], "y al volver a la A, su loop otra vez un compás antes")

    print("\nTodo bien" if todo else "\nHAY FALLAS")
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
