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

    print("\nVivo: quedarse más y subida al final de la parte")
    m, v, _ = correr(armar(), 30, en_compas={3: lambda m: m.quedarse_parte(4)})
    todo &= ok([x["parte"] for x in v][:24] == [0] * 12 + [1] * 8 + [2] * 4 and v[12]["activas"] == [False, True],
               "«Quedarse 4 más» en la intro: dura 12 y el resto entra corrido, cada parte completa")
    m, v, _ = correr(armar(), 30, en_compas={3: lambda m: m.quedarse_parte(4), 5: lambda m: m.quedarse_parte(4)})
    todo &= ok([x["parte"] for x in v][:17] == [0] * 16 + [1], "apretarlo dos veces suma")
    m, v, _ = correr(armar(), 30, en_compas={7: lambda m: m.quedarse_parte(8)})
    todo &= ok([x["parte"] for x in v][:17] == [0] * 16 + [1] and v[8]["activas"] == [True, False] and v[15]["activas"] == [True, False]
               and v[16]["activas"] == [False, True],
               "en el último compás, cuando el Groove ya entraba: la intro vuelve y el Groove espera")
    vistos = []
    m, v, _ = correr(armar(), 14, en_compas={4: lambda m: m.quedarse_parte(4), 6: lambda m: vistos.append(m.estado()["cancion"]),
                                             13: lambda m: vistos.append(m.estado()["cancion"])})
    todo &= ok(vistos[0]["largo"] == 12 and vistos[0]["extra"] == 4 and vistos[0]["total"] == 24 and vistos[0]["siguiente"] == 1
               and vistos[1]["parte"] == 1 and vistos[1]["extra"] == 0 and vistos[1]["total"] == 20,
               f"la app ve la parte alargada y el total mientras dura; después vuelve a lo de siempre")
    subidas = []
    m, v, _ = correr(armar(), 20, en_compas={k: (lambda m: subidas.append((m._compas_actual(), m.subida and dict(m.subida))))
                                           for k in range(9, 17)} | {9: lambda m: (m.pedir_subida_final(4), subidas.append(m.estado()["subida"]))})
    empieza = next((c for c, s in subidas[1:] if isinstance(c, int) and s), None)
    todo &= ok(subidas[0] == {"pedida": 4, "final": True}, f"la app ve la subida pedida para el final {subidas[0]}")
    todo &= ok(empieza == 12 and m.subida is None, f"«últimos 4» en el Groove (compases 8-15): parte en el 12 y cae en el drop ({empieza})")

    print("\nScatter de la MC-101 al final de la parte")
    from goa.motor import Motor as _Motor

    def scatter(ajuste, compases=18, en_compas=None):
        cfg = armar()
        cfg["parte"][1].update(scatter=True, **ajuste)
        cfg = normalizar(cfg)
        ev, ref = [], {}
        m = _Motor(cfg, lambda sal, tipo, canal, n, v: "m" in ref and tipo in ("note_on", "note_off") and (sal, canal) == ("MC-101", 15)
                   and ev.append((max(ref["m"].tick, 0), tipo, n)))
        ref["m"] = m
        m.start()
        for tick in range(compases * 96):
            if en_compas and tick % 96 == 50 and tick // 96 in en_compas:
                en_compas[tick // 96](m)
            m.reloj()
            if tick == 1:
                m.nota_on(1, 41)
        return m, ev
    m, ev = scatter({})
    # El Groove dura los compases 8-15: termina en el paso 256 (tick 1536).
    todo &= ok(ev == [(192 * 6, "note_on", 60), (224 * 6, "note_off", 60), (224 * 6, "note_on", 67),
                      (252 * 6, "note_off", 67), (252 * 6, "note_on", 75), (256 * 6, "note_off", 75)],
               "suave 4 compases antes (pad 1 = nota 60), intenso en los 2 últimos (pad 8), extremo en el último tiempo (pad 16) y suelta en el uno, por el canal 16")
    m, ev = scatter({"scatter_compases": 2, "scatter_intenso": 0})
    todo &= ok(ev == [(252 * 6, "note_on", 75), (256 * 6, "note_off", 75)], f"un pad en 0 no suena: solo el extremo {ev}")
    m, ev = scatter({}, compases=15, en_compas={14: lambda m: m.stop()})
    todo &= ok(ev[-1][1] == "note_off" and len([e for e in ev if e[1] == "note_on"]) == len([e for e in ev if e[1] == "note_off"]),
               "con Stop se suelta el pad que estaba apretado")
    m, ev = scatter({}, compases=18, en_compas={13: lambda m: m.saltar_parte(0)})
    todo &= ok(ev[-1] == (14 * 96, "note_off", 60), f"si saltas a otra parte, se suelta en el uno de esa parte {ev[-2:]}")
    m, ev = scatter({}, compases=22, en_compas={12: lambda m: m.quedarse_parte(4)})
    todo &= ok(ev[:3] == [(192 * 6, "note_on", 60), (201 * 6, "note_off", 60), (256 * 6, "note_on", 60)] and ev[-1] == (320 * 6, "note_off", 75),
               f"con «quedarse» a mitad del Scatter: se suelta en el paso siguiente y vuelve 4 compases antes del nuevo final {ev}")
    todo &= ok("MC-101" in salidas(normalizar(dict(armar(), parte=[dict(armar()["parte"][0], scatter=True)]))), "abre la salida del Scatter")

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

    print("\nPads en la subida (opcional)")
    def pulsos(cfg, compases):
        m = Motor(cfg, lambda *a: None)
        m.start()
        vistos = []
        for tick in range(compases * 96):
            m.reloj()
            if tick % 96 == 1:
                m.nota_on(1, 41)
            if tick % 96 == 5:
                p = m.config["pads"]
                vistos.append((p["pulso"], p["velocidad"], p["voces"]))
        return vistos
    sube = armar()
    sube["parte"][1]["pads_suben"] = True        # Groove (8 compases) con los pads subiendo
    v_sube = pulsos(normalizar(sube), 18)
    v_igual = pulsos(armar(), 18)
    todo &= ok([x[0] for x in v_sube[8:16]] == [2, 2, 4, 4, 6, 6, 8, 8],
               f"el pulso acelera a lo largo de la parte: 2, 4, 6, 8 ({[x[0] for x in v_sube[8:16]]})")
    todo &= ok(v_sube[15][1] > v_sube[8][1] and v_sube[15][2] == v_sube[8][2] + 1,
               "suben de fuerza y suman una voz al final")
    todo &= ok(v_sube[16] == v_igual[16] and v_sube[:8] == v_igual[:8],
               "antes y después de la parte, los pads suenan como en su escena")
    todo &= ok(all(x[0] == v_igual[0][0] for x in v_igual[:16]), "con la casilla apagada, no cambia nada")

    print("\nApoyo a la subida (roll, corte de bajo, tensión, hueco)")
    def subida(flags, escala="frigio"):
        cfg = armar()
        cfg["musica"].update(tonica="F", escala=escala)
        cfg["bajo"].update(activo=True, disparo=2, salida="BAJO", canal=9, armonia="guiada")
        cfg["pads"].update(salida="PADS", canal=8)
        for sec in cfg["secuencia"]:
            sec.update(activa=True, armonia="guiada", salida="SEC", posicion="todos", densidad=1.0)
        for p in cfg["parte"]:
            p["escena"] = -1  # todas siguen lo que suena
        cfg["parte"][1].update(**flags)
        ev = []
        m = Motor(normalizar(cfg), lambda sal, tipo, canal, n, v: ev.append((m.tick, sal, tipo, n, v)))
        m.start()
        for tick in range(96 * 20):
            m.reloj()
            if tick % 96 == 1:
                m.nota_on(1, 41)
        def notas(c, salida, desde=0, hasta=96):
            return [e[3] for e in ev if e[1] == salida and e[2] == "note_on" and e[4] > 0
                    and (c - 1) * 96 + desde <= e[0] < (c - 1) * 96 + hasta]
        return notas
    nada, todo_ = subida({}), subida({"roll": True, "corte_bajo": True, "tension": True, "hueco": True})
    todo &= ok([len(nada(c, "BAJO")) > 0 for c in (15, 16)] == [True, True]
               and [len(todo_(c, "BAJO")) for c in (14, 15, 16)][1:] == [0, 0] and len(todo_(14, "BAJO")) > 0
               and len(todo_(17, "BAJO")) > 0, "corte de bajo: se calla en los 2 últimos compases y vuelve en la parte siguiente")
    todo &= ok(not todo_(16, "SEC", 72) and not todo_(16, "BAJO", 72) and len(nada(16, "SEC", 72)) > 0,
               "hueco: el último tiempo de la parte, el motor en silencio")
    pads_t, pads_i = {n % 12 for n in todo_(16, "PADS")}, {n % 12 for n in todo_(17, "PADS")}
    todo &= ok(6 in pads_t and 5 not in pads_t and 5 in pads_i,
               f"tensión: el último compás va a ♭II (Solb) y la parte siguiente resuelve en Fa ({sorted(pads_t)} → {sorted(pads_i)})")
    sec_t = {n % 12 for n in todo_(16, "SEC", 0, 72)}
    todo &= ok(6 in sec_t or 1 in sec_t, f"las secuencias guiadas siguen el acorde de tensión ({sorted(sec_t)})")
    sec_roll = todo_(16, "SEC", 48, 72)
    todo &= ok(len(sec_roll) >= 4 * len({n for n in sec_roll}) or len(set(sec_roll)) <= 2,
               f"roll: al final cada semicorchea repite la misma nota ({sec_roll})")
    todo &= ok(nada(13, "SEC") == todo_(13, "SEC") and nada(9, "BAJO") == todo_(9, "BAJO"),
               "antes del final de la parte, todo suena igual")
    from goa.escalas import ESCALAS
    from goa.pads import raiz_tension
    todo &= ok((raiz_tension(ESCALAS["frigio"]), raiz_tension(ESCALAS["menor_armonica"]), raiz_tension(ESCALAS["menor"])) == (1, 7, 10),
               "el acorde de tensión: ♭II en frigio, V en menor armónica, ♭VII en menor")

    print("\nActualizar una canción armada con su plantilla")
    from goa import plantillas as pl
    vieja = pl.partes_de("template1")
    for p in vieja:
        if p["nombre"] in ("Rise", "Rise 2"):
            p["compases"] = 16      # como quedaron en la v0.35
        if p["nombre"] == "Break":
            p["compases"] = 8
    vieja[3].update(escena=2, energia=0.9, pads_suben=True, tension=True)
    vieja = [p for p in vieja if p["nombre"] != "Outro"] + [dict(vieja[0], nombre="Mía")]
    nuevas, cambios = pl.actualizar(vieja, "template1")
    por = {p["nombre"]: p for p in nuevas}
    todo &= ok([p["nombre"] for p in nuevas][:16] == [x[0] for x in pl.PLANTILLAS["template1"]["partes"]]
               and por["Rise"]["compases"] == 8 and por["Break"]["compases"] == 16
               and por[vieja[3]["nombre"]]["escena"] == 2 and por[vieja[3]["nombre"]]["energia"] == 0.9
               and por[vieja[3]["nombre"]]["pads_suben"] and por["Outro"]["escena"] == -1
               and nuevas[-1]["nombre"] == "Mía" and len(cambios) == 5,
               f"los largos pasan a los de la plantilla, lo tuyo se queda, entra la parte que faltaba ({cambios})")
    todo &= ok(pl.clave_de("Template 6 · Psy chill · slot 41") == "template6" and pl.clave_de("Mi canción") is None,
               "reconoce la plantilla por el nombre de la canción")

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

    dos["secuencia"][1].update(activa=False)
    m, v, pcs = correr(normalizar(dos), 2)
    todo &= ok(not [p for p in pcs if p[1] == "FM-1" and p[2] in (3, 7)], f"un motor apagado no manda su parche ({pcs})")

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
    todo &= ok(len(t["parte"]) == 16 and forma.total_cancion(t["parte"]) == 240 and all(p["escena"] == -1 for p in t["parte"]),
               "Template 1: 16 partes (las 16 escenas de la Circuit), sin escenas")
    from goa import plantillas as _pl
    subidas = ("Rise", "Rise 2", "Fuego", "Fuego 2", "Vuelta", "Vuelta 2", "Ascenso", "Ascenso 2", "Ascenso 3")
    todo &= ok(all(len(_pl.partes_de(k)) == 16
                   and all(p["compases"] == (8 if p["nombre"] in subidas else 16) for p in _pl.partes_de(k))
                   for k in ("template1", "template2", "template3", "template4", "template6", "template7", "template8", "template9")),
               "templates 1-4 y 6-9: 16 escenas; las subidas de 8 compases (un solo redoble), el resto de 16")
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
