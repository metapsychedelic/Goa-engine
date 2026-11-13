"""Prueba el piloto automático de forma (intro, build, clímax, break, drop), sin hardware.

  python3 -m pruebas.piloto            desde la carpeta goa-engine
"""

import copy

from goa import forma
from goa.config import normalizar
from goa.motor import Motor

from .dialogo import base, colgadas, ok


def armar(**forma_extra):
    cfg = normalizar(base())
    cfg["dialogo"].update(activo=True, disparo=2)
    cfg["pads"].update(activo=True, disparo=2, salida="PADS", pulso=3, suspensiones=0.2)
    cfg["bajo"].update(activo=True, disparo=2, salida="BAJO")
    cfg["secuencia"][0].update(activa=True, disparo=2, salida="SEC")
    cfg["forma"].update(dict(variacion=0.0, energia=0.3, piloto=True, duracion="corta"), **forma_extra)
    return cfg


class Prueba:
    def __init__(self, cfg):
        self.ev, self.reg = [], {}
        self.m = Motor(cfg, lambda sal, tipo, canal, nota, vel: self.ev.append((self.m.tick, sal, tipo, canal, nota, vel)))
        self.m.start()
        self.tick = 0

    def correr(self, compases):
        m = self.m
        for _ in range(compases * 96):
            m.reloj()
            p, r = divmod(self.tick, 6)
            if r == 1 and p % 16 == 0:
                m.nota_on(1, 41)
            if r == 3 and p % 16 == 0:
                sec = m.conductor.seccion(m.base, p // 16)
                self.reg[p // 16] = {"sec": sec[0] if sec else None, "bajo": m.bajo.activo, "dialogo": m.dialogo.activo,
                                     "secuencia": m.secuencias[0].activa, "pulso": m.pads.pulso,
                                     "susp": m.pads.suspensiones, "energia": m.conductor.energia}
            self.tick += 1


if __name__ == "__main__":
    todo = True
    cfg = armar()
    pr = Prueba(cfg)
    pr.correr(70)
    reg = pr.reg
    secs = [reg[c]["sec"] for c in sorted(reg)]
    inicio = {}
    for c in sorted(reg):
        s = reg[c]["sec"]
        if s and (c == 0 or reg[c - 1]["sec"] != s):
            inicio.setdefault(s, []).append(c)
    print("Secciones: " + " ".join(f"{s}@{c + 1}" for s in forma.PLAN for c in inicio.get(s, [])))
    largos = {k: forma.largo_seccion(k, "corta") for k in forma.PLAN}
    todo &= ok(inicio["intro"][0] == 0, "con poca energía parte en la intro, en el borde de la frase")
    b, cl, br, dr = inicio["build"][0], inicio["climax"][0], inicio["break"][0], inicio["drop"][0]
    todo &= ok((b, cl, br, dr) == (largos["intro"], largos["intro"] + largos["build"], largos["intro"] + largos["build"] + largos["climax"],
                                     largos["intro"] + largos["build"] + largos["climax"] + largos["break"]),
               f"duración corta: intro {largos['intro']}, build {largos['build']}, clímax {largos['climax']}, break {largos['break']}, drop {largos['drop']}")
    todo &= ok(len(inicio["build"]) == 2 and inicio["build"][1] == dr + largos["drop"], "después del drop vuelve al build")

    print("\nCapas")
    intro = [reg[c] for c in range(0, b)]
    todo &= ok(all(not r["bajo"] and not r["dialogo"] and r["secuencia"] for r in intro), "intro: pads y secuencia, sin bajo ni diálogo")
    build = [reg[c] for c in range(b, cl)]
    mitad = len(build) // 2
    todo &= ok(all(r["bajo"] for r in build) and not build[0]["dialogo"] and build[-1]["dialogo"],
               "build: entra el bajo, y el diálogo a la mitad")
    todo &= ok(all(r["bajo"] and r["dialogo"] and r["secuencia"] for r in (reg[c] for c in range(cl, br))), "clímax: todo")
    rotura = [reg[c] for c in range(br, dr)]
    todo &= ok(all(not r["bajo"] and not r["secuencia"] and r["pulso"] == 0 and r["susp"] >= 0.7 for r in rotura),
               "break: se van el bajo y la secuencia; los pads quedan sostenidos y con suspensiones")
    d = reg[dr]
    todo &= ok(d["bajo"] and d["secuencia"] and d["dialogo"] and d["pulso"] > 0, "drop: todo vuelve junto, en el uno")

    print("\nEnergía")
    e = [reg[c]["energia"] for c in range(b, cl)]
    todo &= ok(all(y >= x for x, y in zip(e, e[1:])) and e[-1] > e[0] + 0.2, f"build: sube de a poco ({e[0]:.2f} → {e[-1]:.2f})")
    todo &= ok(reg[br]["energia"] > reg[br + 1]["energia"] and reg[dr - 1]["energia"] < 0.4,
               f"break: la energía cae en el uno y sigue bajando ({reg[br]['energia']:.2f} → {reg[dr - 1]['energia']:.2f})")
    todo &= ok(reg[dr]["energia"] >= 0.89, f"drop: la energía entra de golpe ({reg[dr - 1]['energia']:.2f} → {reg[dr]['energia']:.2f})")
    todo &= ok(pr.m.base == normalizar(cfg), "tu configuración no cambia")

    print("\nTomar el control")
    pr.m.saltar_seccion("break")
    pr.correr(2)
    ultimo = max(pr.reg)
    todo &= ok(pr.reg[ultimo]["sec"] == "break", "saltar a una sección entra en el próximo compás")
    sin = copy.deepcopy(pr.m.base)
    sin["forma"]["piloto"] = False
    pr.m.aplicar_config(sin)
    pr.correr(2)
    ultimo = max(pr.reg)
    todo &= ok(pr.reg[ultimo]["sec"] is None and pr.reg[ultimo]["bajo"] and pr.reg[ultimo]["secuencia"],
               "al apagar el piloto vuelve todo lo que dejaste prendido")
    pr.m.stop()
    todo &= ok(colgadas(pr.ev) == 0, "ninguna nota colgada en todo el viaje")

    print("\nCon energía arriba")
    pr = Prueba(armar(energia=0.7))
    pr.correr(6)
    todo &= ok(pr.reg[0]["sec"] == "build", "si ya suena con energía, parte en el build")

    print("\nTODO BIEN" if todo else "\nHAY ERRORES")
    raise SystemExit(0 if todo else 1)
