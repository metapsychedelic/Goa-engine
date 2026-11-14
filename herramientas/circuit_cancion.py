"""Arma los proyectos de la Circuit Tracks de las plantillas de canción (percusión).

Usa la librería circuit-tracks-tools (github.com/namirsab/circuit-tracks-tools)
para escribir el archivo .ncs con escenas de cadenas de patrones distintas en cada
pista, cosa que su formato de canción no permite (ahí cada escena es un solo
patrón de 2 compases).

Cómo se arma cada proyecto:
- Cada pista tiene 8 patrones de 32 pasos (2 compases). Cada escena elige en cada
  pista un tramo de esos patrones; la escena dura lo que su cadena más larga.
- Synth 1 es la «regla»: sus 8 patrones van vacíos y su cadena marca el largo de
  cada escena (1-8 = 16 compases, 1-4 = 8). Las baterías usan cadenas de 1, 2 o 4
  patrones, que siempre caben justo, así todo cambia en el compás exacto.
- MIDI 1 (canal 3, pads) y MIDI 2 (canal 4, secuencias) llevan la nota larga que
  dispara el motor.
- Los nombres y compases de las partes salen de goa/plantillas.py: la canción del
  motor y la de la Circuit son siempre la misma.
- El crash lleva más reverb (Hall) y un poco de delay solo en sus pasos, para que
  tenga cola sin ensuciar el resto de la pista.

Uso:
  python3 herramientas/circuit_cancion.py template1 salida.ncs
  python3 herramientas/circuit_cancion.py todas carpeta/
(con circuit-tracks-tools instalado: pip install circuit-tracks-tools)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from goa.plantillas import PLANTILLAS  # noqa: E402
from circuit_tracks import ncs_parser as ncs  # noqa: E402
from circuit_tracks.song import parse_song, song_to_ncs  # noqa: E402

PASOS = 32  # 2 compases de semicorcheas
NEGRAS = list(range(0, 32, 4))
CONTRAS = list(range(2, 32, 4))
DOS_Y_CUATRO = [4, 12, 20, 28]

# Muestras del banco FROM GOA TO PSYT (clasificadas analizando el audio).
CRASH, RIDE = 40, 40
RISER, SWELL, ATMOS, ZAP = 63, 41, 60, 62
SUB_BOOM = 49
TOM_1, TOM_2, TOM_GRAVE, TOM_SNARE = 31, 55, 15, 27
PERC_A, PERC_B, CONGA_A, CONGA_B, PERC_4, PERC_5 = 47, 53, 44, 45, 53, 54
BLIP_1, BLIP_2 = 57, 58

# Envíos del crash (en su paso y los siguientes, mientras suena).
CRASH_REVERB, CRASH_DELAY, CRASH_PASOS = 72, 42, 8


def golpes(pasos, vel=110, muestra=None):
    """{paso: {velocity, sample}} para una lista de pasos (o de (paso, vel))."""
    d = {}
    for p in pasos:
        paso, v = p if isinstance(p, tuple) else (p, vel)
        d[str(paso)] = {"velocity": v} | ({"sample": muestra} if muestra is not None else {})
    return d


def redoble(pasos, desde, hasta, muestra=None):
    n = len(pasos)
    return golpes([(p, round(desde + (hasta - desde) * i / max(1, n - 1))) for i, p in enumerate(pasos)], muestra=muestra)


def nota_larga(nota=41):
    """Fa (F2) sostenido, tocado de nuevo en cada compás (una nota dura como mucho 16 pasos)."""
    return {"0": {"note": nota, "velocity": 100, "gate": 16}, "16": {"note": nota, "velocity": 100, "gate": 16}}


def pista(pasos, base_reverb, base_delay):
    """Datos de una pista de batería: sus pasos y, si hay crash, sus envíos de FX."""
    datos = {"steps": pasos}
    crashes = [int(k) for k, v in pasos.items() if v.get("sample") == CRASH]
    if crashes:
        reverb, delay = {}, {}
        for c in crashes:
            for paso in range(c, min(PASOS, c + CRASH_PASOS)):
                reverb[str(paso)] = CRASH_REVERB
                delay[str(paso)] = CRASH_DELAY
            if c + CRASH_PASOS < PASOS:  # vuelve a lo de la pista
                reverb.setdefault(str(c + CRASH_PASOS), base_reverb)
                delay.setdefault(str(c + CRASH_PASOS), base_delay)
        datos["params"] = {"reverb_send": reverb, "delay_send": delay}
    return datos


# =====================================================================
# Template 1 · Psytrance 140 (proyecto 32)
# =====================================================================
def template1():
    BOMBO, CLAP, SNARE_ROLL = 3, 16, 22
    HAT_MEDIO, HAT_CERRADO, HAT_CERRADO_2, HAT_ABIERTO = 36, 32, 33, 39
    K = [
        {},
        golpes(NEGRAS, 118), golpes(NEGRAS, 118), golpes(NEGRAS, 118),
        golpes([0, 4, 8, 12, 16, 20, 24, 30], 118),                  # remate
        golpes(NEGRAS[:4] + list(range(16, 32, 2)), 116),            # corcheas (fin de build)
        {}, {},
    ]
    C = [
        {},
        golpes(DOS_Y_CUATRO, 100), golpes(DOS_Y_CUATRO, 100),
        golpes(DOS_Y_CUATRO, 100) | golpes([(30, 70)]),
        redoble(list(range(0, 16, 4)) + list(range(16, 32, 2)), 50, 85, SNARE_ROLL),
        redoble(list(range(0, 16, 2)) + list(range(16, 32)), 60, 100, SNARE_ROLL),
        redoble(list(range(0, 32)), 75, 115, SNARE_ROLL),
        redoble(list(range(0, 32)), 95, 127, SNARE_ROLL),
    ]
    suaves = [(p, 55) for p in range(1, 32, 2)]
    H = [
        {},
        golpes(CONTRAS, 100, HAT_MEDIO),
        golpes(CONTRAS, 100, HAT_MEDIO) | golpes(suaves, muestra=HAT_CERRADO),
        golpes(CONTRAS, 100, HAT_MEDIO) | golpes(suaves, muestra=HAT_CERRADO) | golpes([(30, 95)], muestra=HAT_ABIERTO),
        golpes([(p, 60) for p in range(0, 32, 2)], muestra=HAT_CERRADO_2),
        golpes([(p, 70 if p % 4 == 2 else 45) for p in range(0, 32)], muestra=HAT_CERRADO_2),
        {},
        golpes(CONTRAS, 90, RIDE) | golpes(suaves, muestra=HAT_CERRADO),
    ]
    perc_a = golpes([(3, 70), (11, 60), (19, 70), (27, 60)], muestra=PERC_A)
    perc_b = golpes([(6, 65), (14, 75), (22, 65), (26, 55), (30, 75)], muestra=PERC_B)
    P = [
        {},
        perc_a | golpes([0], 110, CRASH),
        perc_a, perc_b,
        perc_b | golpes([18], 100, RISER),
        golpes([23], 100, SWELL),
        golpes([0], 90, ATMOS),
        {},
    ]
    cadenas = {
        "Intro": (1, 1, 5, 7), "Intro bombo": ((2, 5), 1, 6, 3), "Build": ((3, 6), (2, 5), (2, 3), (4, 5)),
        "Groove A": ((2, 5), (2, 3), (2, 3), 3), "Groove B": ((2, 5), (3, 4), (3, 4), (3, 4)),
        "Groove C": ((2, 5), (3, 4), 4, 4), "Break": (1, 1, 5, 7), "Rise": (1, (5, 8), 6, (5, 6)),
        "Climax A": ((2, 5), (2, 3), (3, 4), (2, 3)), "Climax B": ((2, 5), (3, 4), 8, (3, 4)),
        "Groove D": ((2, 5), (2, 3), (2, 3), 3), "Break 2": (1, 1, 5, 7), "Rise 2": (1, (5, 8), 6, (5, 6)),
        "Drop": ((2, 5), (2, 3), (3, 4), (2, 3)), "Groove E": ((2, 5), (3, 4), (2, 3), (3, 4)),
        "Outro": ((2, 5), 1, 2, 7),
    }
    sonidos = {"drum1": {"sample": BOMBO, "level": 115}, "drum2": {"sample": CLAP, "level": 95},
               "drum3": {"sample": HAT_MEDIO, "level": 85}, "drum4": {"sample": PERC_A, "level": 80}}
    envios = {"reverb": {"drum2": 25, "drum4": 35}, "delay": {"drum4": 25}}
    return "GOA CANCION 1", K, C, H, P, cadenas, sonidos, envios, 50


# =====================================================================
# Template 2 · Dark minimal 142 (proyecto 33)
# Pocos elementos que entran de a uno, percusión glitch, sub booms; sin drops grandes.
# =====================================================================
def template2():
    BOMBO, SNARE, HAT_CORTO, HAT_OFF, HAT_ABIERTO = 8, 23, 38, 34, 39
    K = [
        {},
        golpes(NEGRAS, 120), golpes(NEGRAS, 120), golpes(NEGRAS, 120),
        golpes(NEGRAS[:-1], 120),                                     # falta el último: un hueco cada 8 compases
        golpes(NEGRAS[:4] + [16, 20], 118),                           # se corta a mitad del 2.º compás
        golpes([0], 115),                                             # un golpe cada 2 compases
        {},
    ]
    C = [
        {},
        golpes([(30, 60)]),                                           # un fantasma cada 2 compases
        golpes([(12, 70), (28, 85)]),                                 # solo el 4.º tiempo
        golpes([(7, 40), (15, 50), (23, 40), (28, 85), (30, 55)]),    # fantasmas
        redoble(list(range(24, 32)), 40, 95),                          # redoble corto al final
        {}, {}, {},
    ]
    H = [
        {},
        golpes([(p, 35 + 10 * (p % 4 == 2)) for p in range(0, 32)], muestra=HAT_CORTO),   # semis casi inaudibles
        golpes(CONTRAS, 85, HAT_OFF),
        golpes(CONTRAS, 85, HAT_OFF) | golpes([(p, 38) for p in range(1, 32, 2)], muestra=HAT_CORTO),
        golpes(CONTRAS, 85, HAT_OFF) | golpes([(p, 70) for p in range(0, 32, 3) if p % 4 != 2], muestra=HAT_CORTO),  # 3 contra 4
        golpes([(14, 70), (30, 80)], muestra=HAT_ABIERTO),
        {}, {},
    ]
    glitch_a = golpes([(11, 70)], muestra=ZAP) | golpes([(27, 80)], muestra=BLIP_1)
    glitch_b = golpes([(3, 75), (19, 75)], muestra=BLIP_2) | golpes([(9, 60), (25, 60)], muestra=CONGA_B)
    P = [
        {},
        glitch_a,
        glitch_b,
        glitch_b | golpes([(30, 70)], muestra=ZAP),
        golpes([0], 105, CRASH) | golpes([(27, 80)], muestra=BLIP_1),   # crash (cada 8 compases)
        golpes([0], 85, ATMOS),
        golpes([0], 105, SUB_BOOM),
        golpes([23], 95, SWELL),                                        # llega al uno siguiente
    ]
    cadenas = {
        "Intro": (1, 1, 2, 6), "Pulso": ((2, 5), 1, 2, 1), "Capa 1": ((2, 5), 2, 3, 2),
        "Capa 2": ((2, 5), 2, 4, 3), "Capa 3": ((2, 5), 3, 4, 4), "Respiro": (1, 1, 2, (7, 8)),
        "Tension": ((2, 5), 4, 5, 3), "Nucleo A": ((2, 5), 3, 4, (5, 8)), "Nucleo B": ((2, 5), 4, 5, (2, 3)),
        "Respiro 2": (7, 5, 6, (7, 8)), "Nucleo C": ((2, 5), (3, 4), 4, (5, 8)), "Fragmento": (6, 2, 5, (3, 4)),
        "Nucleo D": ((2, 5), 4, 4, (2, 3)), "Disolucion": ((2, 5), 1, 3, 6), "Final": (1, 1, 2, 6),
    }
    sonidos = {"drum1": {"sample": BOMBO, "level": 118}, "drum2": {"sample": SNARE, "level": 85},
               "drum3": {"sample": HAT_OFF, "level": 85}, "drum4": {"sample": ZAP, "level": 80}}
    envios = {"reverb": {"drum2": 45, "drum4": 40}, "delay": {"drum2": 20, "drum4": 35}}
    return "DARK MINIMAL", K, C, H, P, cadenas, sonidos, envios, 50


# =====================================================================
# Template 3 · Goa clásico 140 (proyecto 34)
# Bombo tipo 909, snare en vez de clap, toms que rematan, breakdown largo, ride.
# =====================================================================
def template3():
    BOMBO, SNARE, SNARE_ROLL = 0, 21, 22
    HAT_ABIERTO, HAT_CERRADO = 35, 33
    K = [
        {},
        golpes(NEGRAS, 118), golpes(NEGRAS, 118), golpes(NEGRAS, 118),
        golpes(NEGRAS[:-1] + [28, 30], 116),                            # doble al final
        golpes(NEGRAS[:4] + list(range(16, 32, 2)), 115),               # corcheas
        {},
        golpes([0], 118),                                               # un golpe cada 2 compases
    ]
    C = [
        {},
        golpes(DOS_Y_CUATRO, 100),
        golpes(DOS_Y_CUATRO, 100) | golpes([(27, 55)]),                 # flam
        golpes(DOS_Y_CUATRO, 100) | golpes([(30, 70), (31, 85)]),       # entrada en semis
        golpes([(28, 80)]),                                              # solo el 4.º (breakdown)
        redoble(list(range(0, 32, 4)), 45, 70, SNARE_ROLL),
        redoble(list(range(0, 32, 2)), 65, 95, SNARE_ROLL),
        redoble(list(range(0, 32)), 90, 127, SNARE_ROLL),
    ]
    H = [
        {},
        golpes(CONTRAS, 100, HAT_ABIERTO),
        golpes(CONTRAS, 100, HAT_ABIERTO) | golpes([(p, 50) for p in range(1, 32, 2)], muestra=HAT_CERRADO),
        golpes([(p, 75 if p % 4 == 2 else 45) for p in range(0, 32)], muestra=HAT_CERRADO),
        golpes(CONTRAS, 95, RIDE) | golpes([(p, 50) for p in range(1, 32, 2)], muestra=HAT_CERRADO),
        golpes([(30, 95)], muestra=HAT_ABIERTO),
        golpes([(p, 55) for p in range(0, 32, 2)], muestra=HAT_CERRADO),
        {},
    ]
    remate = (golpes([(24, 85)], muestra=TOM_1) | golpes([(26, 85)], muestra=TOM_2)
              | golpes([(28, 95)], muestra=TOM_GRAVE) | golpes([(30, 90)], muestra=TOM_1))
    P = [
        {},
        remate,
        golpes([0], 110, CRASH),
        remate,
        golpes([18], 100, RISER),
        golpes([23], 100, SWELL),
        golpes([0], 90, ATMOS),
        (golpes([(6, 65)], muestra=TOM_2) | golpes([(14, 70)], muestra=TOM_1)
         | golpes([(22, 65)], muestra=TOM_2) | golpes([(30, 75)], muestra=TOM_GRAVE)),
    ]
    cadenas = {
        "Intro": (1, 1, 4, 7), "Intro bombo": ((3, 6), 1, 4, 1), "Groove A": ((2, 5), 2, 2, (1, 2)),
        "Groove B": ((2, 5), (2, 3), 3, (1, 2)), "Toms": ((2, 5), (3, 4), 3, 8), "Breakdown": (1, 5, 7, 7),
        "Rise": (1, (5, 8), 6, (5, 6)), "Climax A": ((2, 5), 2, 5, (3, 4)), "Climax B": ((2, 5), (3, 4), 5, 8),
        "Groove C": ((2, 5), 2, 3, (1, 2)), "Break 2": (8, 1, 7, 7), "Rise 2": (1, (5, 8), 6, (5, 6)),
        "Drop": ((2, 5), 2, 5, (3, 4)), "Groove D": ((2, 5), (2, 3), 2, 8), "Outro": ((2, 5), 1, 4, 7),
    }
    sonidos = {"drum1": {"sample": BOMBO, "level": 118}, "drum2": {"sample": SNARE, "level": 95},
               "drum3": {"sample": HAT_ABIERTO, "level": 85}, "drum4": {"sample": TOM_1, "level": 85}}
    envios = {"reverb": {"drum2": 30, "drum4": 30}, "delay": {"drum4": 20}}
    return "GOA CLASICO", K, C, H, P, cadenas, sonidos, envios, 50


# =====================================================================
# Template 4 · Goa tribal 140 (proyecto 35)
# Congas y toms tejidos, shaker 3+3+2, tambores antes del bombo, ceremonia a medio tiempo.
# =====================================================================
def template4():
    BOMBO, CLAP = 5, 19
    SHAKER, HAT_ABIERTO = 37, 39
    K = [
        {},
        golpes(NEGRAS, 118), golpes(NEGRAS, 118), golpes(NEGRAS, 118),
        golpes(NEGRAS, 118) | golpes([(30, 70)]),                          # fantasma al final
        golpes([0, 4, 8, 12, 16, 20, 24, 26, 28, 30], 116),              # se apura al final
        golpes([0, 16], 118),                                            # medio tiempo
        {},
    ]
    C = [
        {},
        golpes(DOS_Y_CUATRO, 90, TOM_SNARE),
        golpes(DOS_Y_CUATRO, 90, TOM_SNARE) | golpes([(10, 55), (26, 55)], muestra=TOM_SNARE),
        golpes(DOS_Y_CUATRO, 90, TOM_SNARE) | golpes([(12, 80), (28, 85)], muestra=CLAP),
        redoble(list(range(16, 32)), 50, 100, TOM_SNARE),
        redoble(list(range(0, 32)), 70, 120, TOM_SNARE),
        golpes([(2, 85), (6, 70), (7, 60), (10, 85), (18, 85), (22, 70), (23, 60), (26, 90)], muestra=TOM_SNARE),  # llamado
        {},
    ]
    tres_tres_dos = [0, 3, 6, 8, 11, 14]
    H = [
        {},
        golpes([(p, 80 if p % 4 == 2 else 45) for p in range(0, 32)], muestra=SHAKER),
        golpes([(p, 85 if p % 16 in tres_tres_dos else 40) for p in range(0, 32)], muestra=SHAKER),
        golpes(CONTRAS, 90, HAT_ABIERTO) | golpes([(p, 45) for p in range(1, 32, 2)], muestra=SHAKER),
        golpes([(p, 55) for p in range(0, 32, 2)], muestra=SHAKER),
        golpes([(30, 90)], muestra=HAT_ABIERTO),
        {}, {},
    ]
    conga_a = (golpes([(3, 75), (10, 65), (19, 75), (26, 65)], muestra=CONGA_A)
               | golpes([(6, 70), (22, 70)], muestra=CONGA_B) | golpes([(14, 80), (30, 80)], muestra=PERC_A))
    conga_b = golpes([(2, 70), (8, 65), (18, 70), (24, 65)], muestra=PERC_4) | golpes([(5, 60), (13, 70), (21, 60), (29, 75)], muestra=PERC_5)
    toms = (golpes([(6, 70)], muestra=TOM_2) | golpes([(14, 75)], muestra=TOM_1)
            | golpes([(22, 70)], muestra=TOM_2) | golpes([(30, 85)], muestra=TOM_GRAVE))
    P = [
        {},
        conga_a,
        conga_b,
        conga_a | conga_b,
        conga_a | golpes([0], 110, CRASH),
        golpes([(10, 60), (26, 60)], muestra=CONGA_A) | golpes([18], 100, RISER),
        golpes([23], 100, SWELL),
        toms,
    ]
    cadenas = {
        "Llamado": (1, 7, 5, 3), "Tambores": (1, (2, 3), 1, (2, 3)), "Entra el bombo": ((2, 5), 2, 1, 2),
        "Danza A": ((2, 5), (2, 3), 2, (2, 3)), "Danza B": ((2, 5), (3, 4), 3, 4), "Ceremonia": (7, 7, 5, 8),
        "Fuego": (1, (5, 6), 2, (6, 7)), "Trance A": ((2, 5), (2, 3), 3, (5, 6)), "Trance B": ((2, 5), (3, 4), 2, 4),
        "Circulo": (1, 1, 5, 8), "Fuego 2": (1, (5, 6), 2, (6, 7)), "Trance C": ((2, 5), (3, 4), 3, (5, 6)),
        "Danza final": ((2, 5), (2, 3), 1, (2, 3)), "Despedida": ((2, 5), 7, 5, 3),
    }
    sonidos = {"drum1": {"sample": BOMBO, "level": 118}, "drum2": {"sample": TOM_SNARE, "level": 90},
               "drum3": {"sample": SHAKER, "level": 85}, "drum4": {"sample": CONGA_A, "level": 88}}
    envios = {"reverb": {"drum2": 30, "drum4": 35}, "delay": {"drum4": 20}}
    return "GOA TRIBAL", K, C, H, P, cadenas, sonidos, envios, 54


# =====================================================================
# Template 5 · Goa épico 140
# Arcos largos, redobles en dos olas, crash cada 8 compases, valles largos.
# =====================================================================
def template5():
    BOMBO, CLAP, SNARE_ROLL = 2, 18, 22
    HAT_ABIERTO, HAT_CERRADO, HAT_LARGO = 35, 32, 39
    K = [
        {},
        golpes(NEGRAS, 118), golpes(NEGRAS, 118), golpes(NEGRAS, 118),
        golpes(NEGRAS[:-1], 118),                                        # hueco antes del cambio
        golpes(NEGRAS[:4] + list(range(16, 32, 2)), 116),                # corcheas
        golpes(NEGRAS[:4] + list(range(16, 32)), 114),                   # semicorcheas
        golpes([0], 118),
    ]
    C = [
        {},
        golpes(DOS_Y_CUATRO, 100),
        golpes(DOS_Y_CUATRO, 100) | golpes([(28, 95)], muestra=SNARE_ROLL),   # clap + snare en el 4
        golpes(DOS_Y_CUATRO, 100) | golpes([(30, 70), (31, 85)], muestra=SNARE_ROLL),
        redoble(list(range(0, 32, 4)), 40, 60, SNARE_ROLL),
        redoble(list(range(0, 32, 2)), 60, 80, SNARE_ROLL),
        redoble(list(range(0, 32)), 80, 105, SNARE_ROLL),
        redoble(list(range(0, 32)), 105, 127, SNARE_ROLL),
    ]
    H = [
        {},
        golpes(CONTRAS, 100, HAT_ABIERTO),
        golpes(CONTRAS, 100, HAT_ABIERTO) | golpes([(p, 50) for p in range(1, 32, 2)], muestra=HAT_CERRADO),
        golpes([(p, 60) for p in range(0, 32, 2)], muestra=HAT_CERRADO),
        golpes(CONTRAS, 95, HAT_ABIERTO) | golpes([(14, 85), (30, 90)], muestra=HAT_LARGO),
        golpes(CONTRAS, 95, RIDE) | golpes([(p, 50) for p in range(1, 32, 2)], muestra=HAT_CERRADO),
        golpes([(p, 30 + p * 2) for p in range(0, 32)], muestra=HAT_CERRADO),   # crecen
        {},
    ]
    P = [
        {},
        golpes([0], 110, CRASH),
        {},
        {},
        golpes([18], 100, RISER),                                        # crash … riser: un arco de 8 compases
        golpes([23], 100, SWELL),
        golpes([0], 90, ATMOS),
        golpes([(7, 60), (23, 60)], muestra=PERC_A),
    ]
    cadenas = {
        "Amanecer": (1, 1, 4, 7), "Despertar": ((2, 5), 1, 4, 8), "Camino": ((2, 5), 2, 2, 8),
        "Camino 2": ((2, 5), 3, 3, (2, 5)), "Valle": (1, 1, 4, 7), "Ascenso": (1, (5, 8), 7, (5, 6)),
        "Ascenso 2": ((6, 7), (5, 8), 7, (5, 6)), "Cumbre A": ((2, 5), 2, 6, (2, 5)),
        "Cumbre B": ((2, 5), (3, 4), 5, (2, 5)), "Meseta": ((2, 5), 2, 3, 8), "Valle 2": (8, 1, 4, 7),
        "Ascenso 3": ((6, 7), (5, 8), 7, (5, 6)), "Cumbre final": ((2, 5), (3, 4), 6, (2, 5)),
        "Cumbre final 2": ((2, 5), (2, 3), 5, (2, 5)), "Descenso": ((2, 5), 1, 2, 8), "Ocaso": (1, 1, 4, 7),
    }
    sonidos = {"drum1": {"sample": BOMBO, "level": 118}, "drum2": {"sample": CLAP, "level": 95},
               "drum3": {"sample": HAT_ABIERTO, "level": 85}, "drum4": {"sample": PERC_A, "level": 80}}
    envios = {"reverb": {"drum2": 35, "drum4": 35}, "delay": {"drum4": 25}}
    return "GOA EPICO", K, C, H, P, cadenas, sonidos, envios, 50


TEMPLATES = {"template1": template1, "template2": template2, "template3": template3,
             "template4": template4, "template5": template5}


def _rango(x):
    return x if isinstance(x, tuple) else (x, x)


def comprobar(clave):
    """Que todo calce: 8 patrones por pista, partes iguales a la plantilla del motor,
    y cada cadena de batería cabe justo en su escena."""
    nombre, K, C, H, P, cadenas, *_ = TEMPLATES[clave]()
    partes = PLANTILLAS[clave]["partes"]
    assert all(len(x) == 8 for x in (K, C, H, P)), clave
    assert len(partes) <= 16, f"{clave}: la Circuit tiene 16 escenas"
    assert [p[0] for p in partes] == list(cadenas), f"{clave}: las partes no coinciden con la plantilla"
    for parte, compases, *_ in partes:
        assert compases in (8, 16), parte
        for pista_, x in zip(("drum1", "drum2", "drum3", "drum4"), cadenas[parte]):
            a, b = _rango(x)
            assert 1 <= a <= b <= 8, f"{clave} {parte} {pista_}"
            largo = (b - a + 1) * 2
            assert compases % largo == 0, f"{clave} {parte}: {pista_} dura {largo} compases"
    return sum(p[1] for p in partes)


def armar(clave):
    nombre, K, C, H, P, cadenas, sonidos, envios, swing = TEMPLATES[clave]()
    plantilla = PLANTILLAS[clave]
    patrones = {}
    for i in range(8):
        pistas = {}
        for nombre_pista, lista in (("drum1", K), ("drum2", C), ("drum3", H), ("drum4", P)):
            if lista[i]:
                pistas[nombre_pista] = pista(lista[i], envios["reverb"].get(nombre_pista, 0),
                                             envios["delay"].get(nombre_pista, 0))
        if i == 0:  # las escenas usan el patrón 1 de MIDI 1 y MIDI 2
            pistas["midi1"] = {"steps": nota_larga()}
            pistas["midi2"] = {"steps": nota_larga()}
        patrones[f"p{i + 1}"] = {"length": PASOS, "tracks": pistas}
    cancion = {
        "name": nombre, "bpm": plantilla["bpm"], "swing": swing, "scale": {"root": "F", "type": "phrygian"},
        "sounds": sonidos,
        "fx": {"reverb_preset": "hall", "delay_preset": "8th dotted ping pong",
               "reverb_sends": envios["reverb"], "delay_sends": envios["delay"]},
        "patterns": patrones,
    }
    proyecto = ncs.parse_ncs_from_bytes(song_to_ncs(parse_song(cancion)))
    for i, (parte, compases, *_) in enumerate(plantilla["partes"]):
        pistas = {t: (0, 0) for t in range(8)}
        pistas[0] = (0, 7) if compases == 16 else (0, 3)  # Synth 1: la regla del largo
        for t, x in zip((4, 5, 6, 7), cadenas[parte]):
            a, b = _rango(x)
            pistas[t] = (a - 1, b - 1)
        ncs.set_scene(proyecto, i, pistas)
    ncs.set_scene_chain(proyecto, start=0, end=len(plantilla["partes"]) - 1)
    return nombre, ncs.serialize_ncs(proyecto)


def generar(clave, ruta):
    total = comprobar(clave)
    nombre, datos = armar(clave)
    with open(ruta, "wb") as f:
        f.write(datos)
    bpm = PLANTILLAS[clave]["bpm"]
    segundos = round(total * 240 / bpm)
    print(f"{clave} · {nombre}: {len(PLANTILLAS[clave]['partes'])} escenas, {total} compases, "
          f"{segundos // 60}:{segundos % 60:02d} a {bpm} BPM → {ruta}")


if __name__ == "__main__":
    clave = sys.argv[1] if len(sys.argv) > 1 else "template1"
    if clave == "todas":
        carpeta = sys.argv[2] if len(sys.argv) > 2 else "."
        os.makedirs(carpeta, exist_ok=True)
        for k in TEMPLATES:
            generar(k, os.path.join(carpeta, f"goa_{k}.ncs"))
    else:
        generar(clave, sys.argv[2] if len(sys.argv) > 2 else f"goa_{clave}.ncs")
