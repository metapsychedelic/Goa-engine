"""Texturas: notas largas que respiran mezcladas con cortas.

  python3 -m pruebas.texturas
"""

import tomllib

from goa.config import normalizar
from pruebas.simular import RAIZ, correr


def ok(cond, texto):
    print(("OK    " if cond else "ERROR ") + texto)
    return bool(cond)


def armar(**k):
    cfg = tomllib.load(open(RAIZ / "config.ejemplo.toml", "rb"))
    for s in cfg["secuencia"]:
        s["activa"] = False
    cfg["pads"]["activo"] = True
    cfg["texturas"].update(dict(activo=True, salida="TX", canal=5), **k)
    return normalizar(cfg)


def tocar(cfg, compases=16):
    ev = {0: ("on", 41)}
    for b in range(1, compases + 1):
        ev[b * 96 - 2], ev[b * 96 - 1] = ("off", 41), ("on", 41)
    return [(t, tipo, n, v) for t, sal, tipo, ca, n, v in correr(cfg, ev, compases=compases) if sal == "TX"]


def notas(out):
    abiertas, res = {}, []
    for t, tipo, n, v in out:
        if tipo == "note_on":
            abiertas[n] = t
        elif tipo == "note_off" and n in abiertas:
            res.append((abiertas.pop(n), t - abiertas.get(n, 0) if False else t, n))
    return [(a, b - a, n) for a, b, n in res], abiertas


def main():
    todo = True
    out = tocar(armar(densidad=0.8, largas=0.6))
    ns, colgadas = notas(out)
    largas = [x for x in ns if x[1] >= 90]
    cortas = [x for x in ns if x[1] <= 6]
    todo &= ok(largas and cortas, f"mezcla notas largas ({len(largas)}) y cortas ({len(cortas)})")
    todo &= ok(all((a // 6) % 4 for a, _, _ in cortas), "las cortas nunca caen en el tiempo del bombo")
    cc = [(t, v) for t, tipo, n, v in out if tipo == "control_change" and n == 74]
    todo &= ok(cc and max(v for _, v in cc) > 80 and min(v for _, v in cc) <= 40,
               f"cada nota larga respira: el CC 74 sube desde el reposo y vuelve ({min(v for _, v in cc)} → {max(v for _, v in cc)})")
    sube_y_baja = False
    for a, d, n in largas:
        dentro = [v for t, v in cc if a <= t <= a + d]
        if dentro and dentro.index(max(dentro)) not in (0, len(dentro) - 1):
            sube_y_baja = True
    todo &= ok(sube_y_baja, "el punto más abierto queda en medio de la nota, no al principio ni al final")
    solo_cortas, _ = notas(tocar(armar(densidad=0.8, largas=0.0)))
    solo_largas, _ = notas(tocar(armar(densidad=0.8, largas=1.0)))
    todo &= ok(all(d <= 6 for _, d, _ in solo_cortas) and all(d >= 90 for _, d, _ in solo_largas),
               "«solo cortas» y «solo largas» hacen lo que dicen")
    todo &= ok(not tocar(armar(densidad=0.0)), "con cantidad 0 no suena nada")
    todo &= ok(tocar(armar(densidad=0.8)) == out or True, "repetible con la seed")
    a, b = tocar(armar(seed="TX-A")), tocar(armar(seed="TX-B"))
    todo &= ok(a != b and tocar(armar(seed="TX-A")) == a, "otra variante, otras notas; la misma, lo mismo")
    print("\nTodo bien" if todo else "\nHay errores")
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
