"""Prueba el modo canción y el Program Change, sin hardware.

  python3 -m pruebas.cancion        desde la carpeta goa-engine
"""

import copy
import os
import tempfile

from goa import forma
from goa.config import a_toml, cargar, normalizar, salidas
from goa.motor import Motor

from .dialogo import base, ok


def armar(**cancion):
    cfg = normalizar(base())
    cfg["pads"].update(activo=True, disparo=2)
    for s in cfg["secuencia"]:
        s.update(activa=False, disparo=2)

    def escena(nombre, activas, programa=0):
        c = copy.deepcopy(cfg)
        for i, s in enumerate(c["secuencia"]):
            s["activa"] = i in activas
            s["programa"] = programa if i == 0 else 0
        return forma.escena_de(c, nombre)

    cfg["escena"] = [escena("Intro", [0], programa=5), escena("Groove", [1]), escena("Todo", [0, 1], programa=9)]
    cfg["parte"] = [dict(nombre="Intro", compases=8, escena=0, energia=0.2, energia_fin=0.4, entrada="suave"),
                    dict(nombre="Groove", compases=8, escena=1, energia=0.6, energia_fin=0.6, entrada="suave"),
                    dict(nombre="Drop", compases=4, escena=2, energia=0.9, energia_fin=0.9, entrada="golpe")]
    cfg["cancion"].update(activa=True, **cancion)
    return normalizar(cfg)


def correr(cfg, compases, en_compas=None):
    """Corre el motor y anota, al empezar cada compás, qué secuencias suenan, la
    energía, la parte y los Program Change que salieron."""
    pcs, ref = [], {}
    m = Motor(cfg, lambda sal, tipo, canal, n, v: tipo == "program_change" and "m" in ref
              and pcs.append((max(ref["m"].tick, 0) // 96, sal, n + 1)))
    ref["m"] = m
    m.start()
    vistos = []
    for tick in range(compases * 96):
        if en_compas and tick % 96 == 50 and tick // 96 in en_compas:
            en_compas[tick // 96](m)
        m.reloj()
        if tick % 96 == 1:
            m.nota_on(1, 41)
        if tick % 96 == 5:
            e = m.estado()["cancion"]
            vistos.append({"activas": [s.activa for s in m.secuencias], "energia": m.conductor.energia,
                           "parte": e["parte"] if e else None, "compas": e["compas"] if e else None})
    return m, vistos, pcs


if __name__ == "__main__":
    todo = True

    print("Modo libre (como siempre)")
    libre = armar()
    libre["cancion"]["activa"] = False
    m, v, _ = correr(libre, 24)
    todo &= ok(m.version_base == 0 and all(x["parte"] is None for x in v),
               "con el modo canción apagado nada cambia solo")
    todo &= ok(len({tuple(x["activas"]) for x in v}) == 1, "y suena siempre lo mismo")

    print("\nCanción")
    m, v, pcs = correr(armar(), 44)
    partes = [x["parte"] for x in v]
    todo &= ok(partes[:20] == [0] * 8 + [1] * 8 + [2] * 4 and partes[20] == 0,
               "las partes duran sus compases (8, 8, 4) y la canción vuelve a empezar")
    todo &= ok(v[0]["activas"] == [True, False] and v[7]["activas"] == [True, False] and v[8]["activas"] == [False, True]
               and v[16]["activas"] == [True, True],
               "las secuencias de cada parte entran y salen justo en su primer compás")
    todo &= ok(v[0]["energia"] == 0.2 and abs(v[7]["energia"] - 0.4) < 0.01, "la energía sigue la curva de la parte (20 → 40)")
    todo &= ok(v[16]["energia"] == 0.9, "una parte de golpe llega con su energía en el uno")
    todo &= ok(v[20]["activas"] == [True, False], "en la segunda vuelta vuelve la intro")
    todo &= ok(m.version_base >= 5, "cada parte avisa a la app que cambió lo que suena")

    m, v, _ = correr(armar(al_final="quedarse"), 30)
    todo &= ok([x["parte"] for x in v][20:] == [2] * 10 and v[29]["activas"] == [True, True],
               "«se queda en la última»: al terminar sigue en el drop")

    m, v, _ = correr(armar(), 30, en_compas={3: lambda m: m.saltar_parte(2)})
    todo &= ok(v[4]["parte"] == 2 and v[4]["activas"] == [True, True] and v[8]["parte"] == 0,
               "«Saltar aquí» pasa a esa parte en el próximo compás y la canción sigue desde ahí")

    def reiniciar(m):
        m.stop()
        m.start()
    m, v, _ = correr(armar(), 30, en_compas={11: reiniciar})
    todo &= ok(v[12]["parte"] == 0 and v[12]["compas"] == 1, "Stop y Play en la Circuit: la canción parte de nuevo")

    sin_escena = armar()
    sin_escena["parte"][1]["escena"] = -1
    m, v, _ = correr(normalizar(sin_escena), 18)
    todo &= ok(v[9]["activas"] == [True, False], "una parte sin escena sigue con lo que sonaba")

    corta = armar()
    corta["forma"]["transicion"] = 16
    m, v, _ = correr(corta, 20)
    todo &= ok(v[3]["activas"] == [True, False] and v[8]["activas"] == [False, True],
               "aunque la transición sea larga, cada parte se escucha tal como es")

    print("\nProgram Change")
    m, v, pcs = correr(armar(), 22)
    todo &= ok(pcs[:1] == [(0, "FM-1", 5)], f"al dar Play pide el parche de la intro ({pcs[:1]})")
    cambios = [p for p in pcs if p[0] > 0]
    todo &= ok(cambios == [(16, "FM-1", 9), (20, "FM-1", 5)],
               f"solo lo vuelve a mandar cuando una parte lo cambia, en su uno: el drop y de nuevo la intro ({cambios})")
    m, v, pcs = correr(armar(), 4, en_compas={2: reiniciar})
    todo &= ok(len([p for p in pcs if p[2] == 5]) == 2, "en cada Start lo vuelve a mandar")
    dos = armar()
    dos["cancion"]["activa"] = False
    dos["secuencia"][0].update(activa=False, programa=3, salida="FM-1", canal=1)
    dos["secuencia"][1].update(activa=True, programa=7, salida="FM-1", canal=1)
    m, v, pcs = correr(normalizar(dos), 2)
    todo &= ok(pcs == [(0, "FM-1", 7)], f"si dos motores van al mismo sinte y canal, manda el que suena ({pcs})")

    print("\nPuertos y archivo")
    cfg = armar()
    cfg["bajo"].update(activo=True, salida="SoloBajo")
    todo &= ok("SoloBajo" in salidas(cfg), "abre el puerto del bajo aunque ningún otro motor lo use")
    cfg["pads"]["activo"] = False
    datos = forma.json.loads(cfg["escena"][0]["datos"])
    datos["pads"]["activo"] = True
    cfg["escena"][0]["datos"] = forma.json.dumps(datos)
    cfg["pads"]["salida"] = "PadsAparte"
    todo &= ok("PadsAparte" in salidas(cfg), "en modo canción abre de entrada los puertos de lo que suena en alguna parte")
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "c.toml")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(a_toml(armar()))
        leida = cargar(ruta)
    todo &= ok(leida["parte"] == armar()["parte"] and leida["cancion"]["activa"],
               "la canción se guarda y se vuelve a abrir igual")

    print("\nPlantillas")
    from goa import plantillas
    t = normalizar(dict(armar(), parte=plantillas.partes_de("template1")))
    todo &= ok(len(t["parte"]) == 16 and forma.total_cancion(t["parte"]) == 232 and all(p["escena"] == -1 for p in t["parte"]),
               "Template 1: 16 partes (las 16 escenas de la Circuit), 232 compases, sin escenas")
    todo &= ok(all(p["compases"] in (8, 16) for p in t["parte"]),
               "cada parte dura 8 o 16 compases, como sus escenas en la Circuit")
    buenas = all(len(x["partes"]) <= 16 and all(c in (8, 16) for _, c, *_ in x["partes"])
                 and len({n for n, *_ in x["partes"]}) == len(x["partes"]) for x in plantillas.PLANTILLAS.values())
    todo &= ok(buenas and len(plantillas.PLANTILLAS) >= 5,
               f"las {len(plantillas.PLANTILLAS)} plantillas caben en la Circuit (hasta 16 escenas de 8 o 16 compases, nombres únicos)")
    m, v, _ = correr(t, 40)
    todo &= ok([x["parte"] for x in v][:34] == [0] * 16 + [1] * 16 + [2] * 2, "la plantilla avanza parte por parte")

    print("\nTODO BIEN" if todo else "\nHAY ERRORES")
    raise SystemExit(0 if todo else 1)
