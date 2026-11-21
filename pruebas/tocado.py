"""Tocado: tocar con el teclado de la MicroFreak a través del motor, con estilo.

  python3 -m pruebas.tocado
"""

import json
from pathlib import Path

from goa.config import cargar, normalizar, salidas
from goa.motor import Motor

RAIZ = Path(__file__).resolve().parent.parent
COMPAS = 96


def ok(cond, texto):
    print(("  ok   " if cond else "  FALLA ") + texto)
    return cond


def base(**tocado):
    cfg = normalizar(cargar(RAIZ / "config.ejemplo.toml"))
    for s in cfg["secuencia"]:
        s["activa"] = False
    cfg["entrada"].update(canal_disparo=2, nota_maxima=0)
    cfg["pads"].update(activo=True, suenan=False, disparo=0)
    cfg["tocado"].update(dict(activo=True, salida="FM-1", canal=4), **tocado)
    return normalizar(cfg)


class Sesion:
    """El motor corriendo, con la nota larga de la Circuit en cada compás."""

    def __init__(self, cfg):
        self.salida = []
        self.m = Motor(cfg, lambda sal, tipo, canal, a, b: self.salida.append((self.m.tick, sal, tipo, canal, a, b)))
        self.m.start()

    def pulsos(self, n, toques=()):
        """toques: {pulso relativo: [(tecla, vel, largo en pulsos)]}"""
        apagar = {}
        inicio = self.m.tick + 1
        for k in range(n):
            self.m.reloj()
            t = self.m.tick
            if t % COMPAS == 1:
                self.m.nota_on(1, 41)
            for tecla, vel, largo in dict(toques).get(t - inicio, []):
                self.m.tocado_on(tecla, vel)
                apagar.setdefault(t + largo, []).append(tecla)
            for tecla in apagar.pop(t, []):
                self.m.tocado_off(tecla)

    def notas(self, desde=0):
        return [(t, a, b) for t, sal, tipo, canal, a, b in self.salida
                if sal == "FM-1" and canal == 3 and tipo == "note_on" and t >= desde]

    def colgadas(self):
        on = {}
        for t, sal, tipo, canal, a, b in self.salida:
            if sal != "FM-1" or canal != 3:
                continue
            if tipo == "note_on":
                on[a] = on.get(a, 0) + 1
            elif tipo == "note_off" and on.get(a):
                on[a] -= 1
        return sum(on.values())


def ritmo(compases, tecla=60):
    """Un ritmo con cortas, largas y acentos: en cada compás 1, 1-y, 2-y (larga), 4."""
    toques = {}
    for c in range(compases):
        b = c * COMPAS
        toques[b + 0] = [(tecla, 110, 10)]
        toques[b + 12] = [(tecla, 70, 6)]
        toques[b + 36] = [(tecla, 90, 30)]
        toques[b + 72] = [(tecla, 120, 8)]
    return toques


def en_escala(m, nota):
    t = m.tonalidad
    return (nota - t.tonica) % 12 in t.intervalos


def main():
    todo = True
    print("Una tecla: cada estilo, siempre en la escala y en el acorde en el tiempo")
    for estilo in ("goa", "acido", "mantra", "raga", "bajo"):
        s = Sesion(base(estilo=estilo, modo="una_tecla"))
        s.pulsos(COMPAS)  # un compás para que suenen los pads
        desde = s.m.tick
        s.pulsos(4 * COMPAS, ritmo(4))
        notas = s.notas(desde)
        fuera = [n for _, n, _ in notas if not en_escala(s.m, n)]
        distintas = len({n for _, n, _ in notas})
        todo &= ok(notas and not fuera and distintas > 1 and s.colgadas() == 0,
                   f"{estilo}: {len(notas)} notas, {distintas} alturas distintas, ninguna fuera de la escala, sin colgadas")
    s = Sesion(base(estilo="goa"))
    s.pulsos(COMPAS + 5)
    antes = len(s.notas())
    s.m.tocado_on(60, 100)
    todo &= ok(len(s.notas()) == antes + 1, "suena al instante, en el mismo pulso (sin cuantizar ni esperar)")
    s.m.tocado_off(60)

    print("\nContorno")
    s = Sesion(base(modo="contorno", estilo="goa"))
    s.pulsos(COMPAS)
    desde = s.m.tick
    toques = {i * 12 + 6: [(tecla, 90, 6)] for i, tecla in enumerate(range(55, 79, 3))}
    s.pulsos(COMPAS, toques)
    alturas = [n for _, n, _ in s.notas(desde)]
    todo &= ok(alturas == sorted(alturas) and len(set(alturas)) >= 5 and all(en_escala(s.m, n) for n in alturas),
               f"teclas que suben: las notas suben y caen en la escala {alturas}")

    print("\nGrabar y loop")
    s = Sesion(base(estilo="goa", compases=8))
    s.pulsos(COMPAS // 2)  # a mitad del compás 1 (pulso 47)
    s.m.tocado.accion("grabar", s.m.tick)
    s.pulsos(COMPAS // 2)  # hasta el último pulso del compás
    todo &= ok(s.m.tocado.estado == "armado", "Grabar espera el próximo compás")
    s.pulsos(8 * COMPAS, ritmo(8))  # desde el uno del compás 2
    todo &= ok(s.m.tocado.grabadas == [] or s.m.tocado.estado == "grabando", "y graba desde el uno")
    s.pulsos(1)
    todo &= ok(s.m.tocado.estado == "loop" and len(s.m.tocado.grabadas) == 32, f"después de 8 compases queda en loop ({len(s.m.tocado.grabadas)} notas)")
    desde = s.m.tick
    s.pulsos(8 * COMPAS)
    lugares = sorted({(t - desde) % COMPAS for t, _, _ in s.notas(desde)})
    todo &= ok(lugares == [0, 12, 36, 72], f"el loop repite tu ritmo, cuantizado: pulsos {lugares}")
    todo &= ok(s.colgadas() == len(s.m.tocado.sonando), "sin notas colgadas (solo las que están sonando)")
    primera = [n for _, n, _ in s.notas(desde)]
    cfg = json.loads(json.dumps(s.m.base))
    cfg["tocado"]["seed"] = "OTRA"
    s.m.aplicar_config(normalizar(cfg))
    desde2 = s.m.tick
    s.pulsos(8 * COMPAS)
    segunda = s.notas(desde2)
    todo &= ok(sorted({(t - desde2) % COMPAS for t, _, _ in segunda}) == lugares and [n for _, n, _ in segunda] != primera,
               "otra variante: mismas posiciones, otras notas")
    s.m.tocado.accion("parar", s.m.tick)
    antes = len(s.notas())
    s.pulsos(2 * COMPAS)
    todo &= ok(len(s.notas()) == antes and s.m.tocado.estado == "pausa", "Parar: el loop calla")
    s.m.tocado.accion("seguir", s.m.tick)
    s.pulsos(COMPAS)
    todo &= ok(len(s.notas()) > antes, "Seguir: vuelve")
    s.m.stop()
    todo &= ok(s.colgadas() == 0, "al parar el reloj no queda nada colgado")

    print("\nCambio de acorde con una nota larga")
    s = Sesion(base(estilo="bajo"))
    s.pulsos(COMPAS)
    s.m.tocado_on(60, 100)
    reataques = 0
    for _ in range(16):
        clases = s.m._momento_tocado(max(s.m.tick, 0) // 6)
        s.pulsos(COMPAS)
        sonando = list(s.m.tocado.sonando)
        m = s.m._momento_tocado(max(s.m.tick, 0) // 6)
        if m is not None and sonando and all(n % 12 in m.clases for n in sonando):
            reataques += 1
        del clases
    s.m.tocado_off(60)
    todo &= ok(reataques == 16, "una larga sostenida siempre queda en el acorde que suena (se vuelve a atacar si choca)")
    todo &= ok(s.colgadas() == 0, "y al soltarla no queda colgada")

    print("\nSalida")
    todo &= ok("FM-1" in salidas(base()), "abre la salida elegida")
    print("\nTodo bien" if todo else "\nHAY FALLAS")
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
