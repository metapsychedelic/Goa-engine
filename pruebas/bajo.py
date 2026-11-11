"""Prueba el generador de líneas de bajo, sin hardware.

  python3 -m pruebas.bajo            desde la carpeta goa-engine
"""

import tomllib

from goa import bajo, generos
from goa.config import a_toml, normalizar
from goa.escalas import Tonalidad

from .dialogo import base, colgadas, correr, ok

NOTA_LARGA = 41  # F2, la que manda correr() en cada compás
PSY = ("rolling", "psy_chill", "chillgressive")


def armar(genero="goa", modo="guiada", cambia_cada=2, pads=True, **extra):
    cfg = normalizar(generos.aplicar(base(), genero))
    cfg["musica"]["armonia"] = modo
    cfg["dialogo"]["activo"] = False
    cfg["pads"].update(activo=pads, disparo=2, suenan=False, cambia_cada=cambia_cada, variacion=0.0)
    cfg["bajo"].update(dict(activo=True, disparo=2, salida="BAJO", canal=4), **extra)
    return cfg


def notas_de(salida):
    return [(t, n) for t, s, ti, c, n, _ in salida if s == "BAJO" and ti == "note_on"]


def max_juntas(salida):
    sonando, maximo = set(), 0
    for t, s, ti, c, n, _ in salida:
        if s == "BAJO":
            (sonando.add if ti == "note_on" else sonando.discard)(n)
            maximo = max(maximo, len(sonando))
    return maximo


def compas(notas, c):
    return [(t % 96, n) for t, n in notas if t // 96 == c]


if __name__ == "__main__":
    todo = True

    print("Estilos por género")
    for genero in generos.ORDEN:
        cfg = armar(genero)
        salida, motor = correr(cfg, compases=16)
        notas = notas_de(salida)
        escala = Tonalidad(cfg["musica"]["tonica"], cfg["musica"]["escala"])
        en_escala = all((n - escala.tonica) % 12 in escala.intervalos for _, n in notas)
        sin_bombo = cfg["bajo"]["estilo"] not in PSY or all(t % 24 >= 6 for t, _ in notas)
        todo &= ok(notas and en_escala and colgadas(salida) == 0 and max_juntas(salida) == 1 and sin_bombo,
                   f"{generos.GENEROS[genero]['nombre']:<14} {cfg['bajo']['estilo']:<13} {len(notas):>3} notas · "
                   "en la escala, monofónico, sin colgadas" + (", nunca en el tiempo del bombo" if cfg["bajo"]["estilo"] in PSY else ""))
        todo &= ok(correr(cfg, compases=16)[0] == salida, "  misma variante, mismo bajo")

    print("\nArmonía guiada")
    for genero in ("goa", "psy_chill", "chillout"):
        cfg = armar(genero, remates=False)
        salida, motor = correr(cfg, compases=16)
        notas = notas_de(salida)
        primeras = [min(compas(notas, c)) for c in range(16) if compas(notas, c)]
        momentos = [motor.pads.momento(c * 16 + 15, NOTA_LARGA) for c in range(16)]
        raices = all(n % 12 == motor.pads.momento(c * 16, NOTA_LARGA).raiz % 12
                     for c, (_, n) in enumerate(primeras))
        todo &= ok(raices, f"{genero}: cada compás empieza en la raíz del acorde que suena")
        malas = 0
        for c in range(1, 16, 2):  # acordes cada 2 compases: cambian después de los compases 2, 4, 6…
            ult = max(compas(notas, c))
            sig = momentos[c].siguiente % 12
            t_paso, n = ult
            if motor.pads.momento(c * 16 + t_paso // 6, NOTA_LARGA).cambia_pronto:
                vecinas = {motor.tonalidad.nota(n, d, "escala") % 12 for d in (-1, 0, 1)}
                malas += sig not in vecinas
        todo &= ok(malas == 0, f"{genero}: la última nota antes de cada cambio lleva a la raíz que viene")

    cfg = armar("goa", modo="libre", remates=False)
    notas = notas_de(correr(cfg, compases=8)[0])
    todo &= ok({n % 12 for _, n in notas} == {NOTA_LARGA % 12}, "libre: toca la raíz de su nota larga, sin mirar el acorde")
    cfg = armar("goa", pads=False, remates=False)
    notas = notas_de(correr(cfg, compases=8)[0])
    todo &= ok({n % 12 for _, n in notas} == {NOTA_LARGA % 12}, "sin pads: sigue la nota larga")

    print("\nFrases y remates")
    cfg = armar("goa", cambia_cada=8, movimiento=0.6)
    notas = notas_de(correr(cfg, compases=8)[0])
    todo &= ok(compas(notas, 0) == compas(notas, 1) == compas(notas, 2), "los compases de la frase se repiten igual")
    todo &= ok(compas(notas, 3) != compas(notas, 0), "el último compás de la frase cierra con un remate")
    todo &= ok([n for _, n in compas(notas, 3)] != [n for _, n in compas(notas, 7)], "los remates alternan entre dos variantes")
    sin = armar("goa", cambia_cada=8, movimiento=0.6, remates=False)
    notas = notas_de(correr(sin, compases=8)[0])
    todo &= ok(all(compas(notas, c) == compas(notas, 0) for c in range(8)), "sin remates, todos los compases iguales")

    print("\nMovimiento")
    quieto = notas_de(correr(armar("goa", cambia_cada=8, movimiento=0.0, remates=False), compases=4)[0])
    mueve = notas_de(correr(armar("goa", cambia_cada=8, movimiento=1.0, remates=False), compases=4)[0])
    todo &= ok(len({n for _, n in quieto}) == 1 and len({n for _, n in mueve}) > 1,
               "movimiento 0: solo la raíz · movimiento 1: salta a la octava y la quinta")

    print("\nAmbient (sub)")
    salida, _ = correr(armar("ambient", cambia_cada=4), compases=16)
    notas = notas_de(salida)
    todo &= ok(len(notas) == 4 and colgadas(salida) == 0, "una nota por acorde, ligada entre compases (4 acordes, 4 notas)")

    print("\nConfiguración")
    cfg = armar("chillout")
    todo &= ok(cfg["bajo"]["estilo"] == "dub" and cfg["bajo"]["genero"] == "chillout", "el género para todo también pone el bajo")
    solo = generos.aplicar(armar("goa"), "ambient", parte="bajo")
    todo &= ok(solo["bajo"]["estilo"] == "sub" and solo["pads"]["genero"] == "goa", "el género del bajo no toca a los demás")
    cfg = normalizar(cfg)
    todo &= ok(normalizar(tomllib.loads(a_toml(cfg))) == cfg, "se guarda y se lee igual")
    todo &= ok(set(bajo.ESTILOS) == {generos.BAJO[g]["estilo"] for g in generos.ORDEN}, "cada estilo tiene su género")

    print("\nTodo bien" if todo else "\nHay errores")
    raise SystemExit(0 if todo else 1)
