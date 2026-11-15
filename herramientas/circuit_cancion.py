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

# Muestras del banco FROM GOA TO PSYT, elegidas midiendo el audio de cada una
# (energía por bandas, fundamental y caída). Regla: en los patrones no va nada con
# energía fuerte bajo 150 Hz salvo el bombo, para no chocar con el bajo del motor.
#   Bombos cortos (fundamental 65-86 Hz, poco sub): 1, 3, 4, 5, 7. Evitar 0, 2, 8-12, 14, 15, 46 (sub largo).
#   Fuera de los patrones: 48-50 y 56-59 (booms y blips sub), 26 (snare con sub), 31 y 47 (graves).
#   60 (atmósfera) es un drone medio de 3 s: no va en loops.
CRASH = 40          # solo en el uno de una parte, nunca como ride
RIDE = 39           # hat abierto largo: hace de ride (el crash no se usa en loops)
RISER, SWELL, ATMOS, ZAP = 63, 41, 60, 62
REVERSA = 61
SUB_BOOM = 49       # no se usa: sub de 4 s
TOM_1, TOM_2, TOM_GRAVE, TOM_SNARE = 53, 54, 55, 27    # toms medios que bajan: 377, 280 y 226 Hz
PERC_A, PERC_B, CONGA_A, CONGA_B, PERC_4, PERC_5 = 45, 53, 44, 54, 53, 54
BLIP_1, BLIP_2 = 62, 24  # acentos agudos (antes eran sub blips)


def bruma(vel=55):
    """En vez de la atmósfera: un swell de platillo suave que llega al uno."""
    return golpes([(23, vel)], muestra=SWELL)

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
    BOMBO, CLAP, SNARE_ROLL = 4, 16, 22
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
        bruma(),
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
    sonidos = {"drum1": {"sample": BOMBO, "level": 105}, "drum2": {"sample": CLAP, "level": 95},
               "drum3": {"sample": HAT_MEDIO, "level": 85}, "drum4": {"sample": PERC_A, "level": 80}}
    envios = {"reverb": {"drum2": 25, "drum4": 35}, "delay": {"drum4": 25}}
    return "GOA CANCION 1", K, C, H, P, cadenas, sonidos, envios, 50


# =====================================================================
# Template 2 · Dark minimal 142 (proyecto 33)
# Pocos elementos que entran de a uno, percusión glitch, sub booms; sin drops grandes.
# =====================================================================
def template2():
    BOMBO, SNARE, HAT_CORTO, HAT_OFF, HAT_ABIERTO = 7, 23, 38, 34, 39
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
    # Solo sonidos agudos: el grave queda para el bombo y el bajo del motor.
    CLAP_CORTO, HAT_6, HAT_7, REVERSA = 24, 42, 43, 61
    glitch_a = golpes([(11, 70)], muestra=ZAP) | golpes([(27, 75)], muestra=HAT_7)
    glitch_b = golpes([(3, 60), (19, 60)], muestra=CLAP_CORTO) | golpes([(9, 65), (25, 65)], muestra=HAT_6)
    P = [
        {},
        glitch_a,
        glitch_b,
        glitch_b | golpes([(30, 70)], muestra=ZAP),
        golpes([0], 105, CRASH) | golpes([(27, 75)], muestra=HAT_7),    # crash (cada 8 compases)
        bruma(),
        golpes([16], 80, REVERSA),                                      # reverso que llega al uno
        golpes([23], 95, SWELL),                                        # llega al uno siguiente
    ]
    cadenas = {
        "Intro": (1, 1, 2, 6), "Pulso": ((2, 5), 1, 2, 1), "Capa 1": ((2, 5), 2, 3, 2),
        "Capa 2": ((2, 5), 2, 4, 3), "Capa 3": ((2, 5), 3, 4, 4), "Respiro": (1, 1, 2, (7, 8)),
        "Tension": ((2, 5), 4, 5, 3), "Nucleo A": ((2, 5), 3, 4, (5, 8)), "Nucleo B": ((2, 5), 4, 5, (2, 3)),
        "Respiro 2": (7, 5, 6, (7, 8)), "Nucleo C": ((2, 5), (3, 4), 4, (5, 8)), "Fragmento": (6, 2, 5, (3, 4)),
        "Nucleo D": ((2, 5), 4, 4, (2, 3)), "Disolucion": ((2, 5), 1, 3, 6), "Eco": ((2, 5), 1, 2, (2, 3)),
        "Final": (1, 1, 2, 6),
    }
    sonidos = {"drum1": {"sample": BOMBO, "level": 105}, "drum2": {"sample": SNARE, "level": 85},
               "drum3": {"sample": HAT_OFF, "level": 85}, "drum4": {"sample": ZAP, "level": 80}}
    envios = {"reverb": {"drum2": 45, "drum4": 40}, "delay": {"drum2": 20, "drum4": 35}}
    return "DARK MINIMAL", K, C, H, P, cadenas, sonidos, envios, 50


# =====================================================================
# Template 3 · Goa clásico 140 (proyecto 34)
# Bombo tipo 909, snare en vez de clap, toms que rematan, breakdown largo, ride.
# =====================================================================
def template3():
    BOMBO, SNARE, SNARE_ROLL = 3, 21, 22
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
        bruma(),
        (golpes([(6, 65)], muestra=TOM_2) | golpes([(14, 70)], muestra=TOM_1)
         | golpes([(22, 65)], muestra=TOM_2) | golpes([(30, 75)], muestra=TOM_GRAVE)),
    ]
    cadenas = {
        "Intro": (1, 1, 4, 7), "Intro bombo": ((3, 6), 1, 4, 1), "Groove A": ((2, 5), 2, 2, (1, 2)),
        "Groove B": ((2, 5), (2, 3), 3, (1, 2)), "Toms": ((2, 5), (3, 4), 3, 8), "Breakdown": (1, 5, 7, 7),
        "Rise": (1, (5, 8), 6, (5, 6)), "Climax A": ((2, 5), 2, 5, (3, 4)), "Climax B": ((2, 5), (3, 4), 5, 8),
        "Groove C": ((2, 5), 2, 3, (1, 2)), "Break 2": (8, 1, 7, 7), "Rise 2": (1, (5, 8), 6, (5, 6)),
        "Drop": ((2, 5), 2, 5, (3, 4)), "Groove D": ((2, 5), (2, 3), 2, 8),
        "Groove E": ((2, 5), 2, 3, (1, 2)), "Outro": ((2, 5), 1, 4, 7),
    }
    sonidos = {"drum1": {"sample": BOMBO, "level": 105}, "drum2": {"sample": SNARE, "level": 95},
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
        "Trance D": ((2, 5), (3, 4), 2, 4), "Danza C": ((2, 5), (3, 4), 3, 4),
        "Danza final": ((2, 5), (2, 3), 1, (2, 3)), "Despedida": ((2, 5), 7, 5, 3),
    }
    sonidos = {"drum1": {"sample": BOMBO, "level": 105}, "drum2": {"sample": TOM_SNARE, "level": 90},
               "drum3": {"sample": SHAKER, "level": 85}, "drum4": {"sample": CONGA_A, "level": 88}}
    envios = {"reverb": {"drum2": 30, "drum4": 35}, "delay": {"drum4": 20}}
    return "GOA TRIBAL", K, C, H, P, cadenas, sonidos, envios, 54


# =====================================================================
# Template 5 · Goa épico 140
# Arcos largos, redobles en dos olas, crash cada 8 compases, valles largos.
# =====================================================================
def template5():
    BOMBO, CLAP, SNARE_ROLL = 1, 18, 22
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
        bruma(),
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
    sonidos = {"drum1": {"sample": BOMBO, "level": 105}, "drum2": {"sample": CLAP, "level": 95},
               "drum3": {"sample": HAT_ABIERTO, "level": 85}, "drum4": {"sample": PERC_A, "level": 80}}
    envios = {"reverb": {"drum2": 35, "drum4": 35}, "delay": {"drum4": 25}}
    return "GOA EPICO", K, C, H, P, cadenas, sonidos, envios, 50


def _redobles(muestra, niveles=((45, 70), (70, 90), (90, 110), (110, 127))):
    """Los 4 patrones de un redoble que se acelera (negras, corcheas, semicorcheas, semicorcheas)."""
    (a, b), (c, d), (e, f), (g, h) = niveles
    return [redoble(list(range(0, 32, 4)), a, b, muestra), redoble(list(range(0, 32, 2)), c, d, muestra),
            redoble(list(range(0, 32)), e, f, muestra), redoble(list(range(0, 32)), g, h, muestra)]


def _bombos(base, vel):
    """Bombos de 4 por 4: 1 vacío, 2 base, 3 base con fantasmas, 4 con hueco al final,
    y la subida 5-8: un golpe, blancas, negras, negras que pasan a corcheas."""
    return [
        {},
        golpes(base, vel),
        golpes(base, vel) | golpes([(14, 65), (30, 70)]),
        golpes(base[:-1], vel),
        golpes([0], vel),
        golpes([0, 8, 16, 24], vel),
        golpes(NEGRAS, vel),
        golpes(NEGRAS[:4] + list(range(16, 32, 2)), vel - 2),
    ]


# =====================================================================
# Template 6 · Psy chill 104
# =====================================================================
def template6():
    BOMBO, CLAP, SNARE = 1, 17, 25
    HAT_ABIERTO, SHAKER, HAT_CERRADO = 35, 43, 37
    K = _bombos(NEGRAS, 108)
    K[7] = K[7] | golpes([(18, 70)], muestra=RISER)   # la subida termina con un riser suave
    C = [{}, golpes(DOS_Y_CUATRO, 90),
         golpes(DOS_Y_CUATRO, 90) | golpes([(23, 50), (30, 60)], muestra=SNARE),
         golpes([12, 28], 90)] + _redobles(SNARE, ((40, 60), (60, 80), (80, 100), (100, 120)))
    H = [
        {},
        golpes(CONTRAS, 85, HAT_ABIERTO),
        golpes(CONTRAS, 85, HAT_ABIERTO) | golpes([(p, 45) for p in range(1, 32, 2)], muestra=HAT_CERRADO),
        golpes([(p, 55) for p in range(0, 32, 2)], muestra=HAT_CERRADO),
        golpes([(p, 30 + p * 2) for p in range(32)], muestra=HAT_CERRADO),     # crecen
        golpes([(6, 60), (22, 65)], muestra=HAT_ABIERTO),
        golpes([(p, 55 if p % 4 == 2 else 35) for p in range(32)], muestra=SHAKER),
        {},
    ]
    # Pista 4 en los géneros chill: percusión orgánica suave y los FX solo en los cambios.
    # Con la cadena 1-8 (16 compases): crash suave en el uno, 2 compases sin percusión
    # cerca del final y un swell suave que llega a la parte siguiente. 7 = silencio.
    conga_a = golpes([(3, 60), (11, 55), (19, 60), (27, 50)], muestra=CONGA_A)
    conga_b = golpes([(3, 60), (7, 45), (19, 60), (23, 45)], muestra=CONGA_A) | golpes([(14, 50), (30, 55)], muestra=PERC_A)
    P = [
        golpes([0], 75, CRASH) | conga_a,
        conga_a, conga_b, conga_a, conga_b, conga_a,
        {},
        golpes([(3, 50), (19, 50)], muestra=CONGA_A) | golpes([(23, 60)], muestra=SWELL),
    ]
    cadenas = {
        "Intro": (1, 1, 6, 8), "Intro 2": (1, 1, 7, 8), "Entra bombo": (2, 1, 7, 8),
        "Groove A": (2, 2, 2, (2, 5)), "Groove B": (3, 3, 3, (2, 5)), "Groove C": (3, 2, 4, (2, 5)),
        "Break": (5, 4, 7, 8), "Rise": ((5, 8), (5, 8), 5, (6, 7)),
        "Viaje A": (2, 2, 3, (2, 5)), "Viaje B": (3, 3, 4, (2, 5)), "Respiro": (1, 4, 7, 8),
        "Rise 2": ((5, 8), (5, 8), 5, (6, 7)), "Viaje C": (3, 3, 3, (2, 5)), "Viaje D": (2, 3, 2, (2, 5)),
        "Outro": (2, 1, 2, 8), "Final": (1, 1, 6, 8),
    }
    D4 = {'Intro': 7, 'Intro 2': 7, 'Entra bombo': (2, 3), 'Groove A': (1, 8), 'Groove B': (1, 8), 'Groove C': (1, 8), 'Break': 7, 'Rise': 7, 'Viaje A': (1, 8), 'Viaje B': (1, 8), 'Respiro': 7, 'Rise 2': 7, 'Viaje C': (1, 8), 'Viaje D': (1, 8), 'Outro': (2, 3), 'Final': 7}
    cadenas = {n: v[:3] + (D4[n],) for n, v in cadenas.items()}
    sonidos = {"drum1": {"sample": BOMBO, "level": 105}, "drum2": {"sample": CLAP, "level": 90},
               "drum3": {"sample": HAT_ABIERTO, "level": 80}, "drum4": {"sample": CONGA_A, "level": 80}}
    envios = {"reverb": {"drum2": 40, "drum3": 15, "drum4": 40}, "delay": {"drum2": 15, "drum4": 30}}
    return "PSY CHILL", K, C, H, P, cadenas, sonidos, envios, 56


# =====================================================================
# Template 7 · Chillgressive 120
# =====================================================================
def template7():
    BOMBO, CLAP, SNARE_ROLL = 7, 19, 22
    HAT_CERRADO, HAT_ABIERTO, HAT_FINO = 34, 39, 42
    PERC, REVERSA, SUB_BLIP = 45, 61, 24
    K = _bombos(NEGRAS, 112)
    K[7] = K[7] | golpes([(18, 70)], muestra=RISER)   # la subida termina con un riser suave
    C = [{}, golpes(DOS_Y_CUATRO, 95),
         golpes(DOS_Y_CUATRO, 95) | golpes([(30, 55)]),
         golpes([12, 28], 95)] + _redobles(SNARE_ROLL)
    H = [
        {},
        golpes(CONTRAS, 90, HAT_ABIERTO),
        golpes([(p, 80 if p % 4 == 2 else 45) for p in range(32)], muestra=HAT_CERRADO),   # rolling
        golpes(CONTRAS, 85, HAT_ABIERTO) | golpes([(p, 45) for p in range(32) if p % 4 != 2], muestra=HAT_FINO),
        golpes([(p, 30 + p * 2) for p in range(32)], muestra=HAT_CERRADO),
        golpes([(p, 55) for p in range(0, 32, 2)], muestra=HAT_FINO),
        golpes([(14, 70), (30, 80)], muestra=HAT_ABIERTO),
        {},
    ]
    # Pista 4 en los géneros chill: percusión orgánica suave y los FX solo en los cambios.
    # Con la cadena 1-8 (16 compases): crash suave en el uno, 2 compases sin percusión
    # cerca del final y un swell suave que llega a la parte siguiente. 7 = silencio.
    perc_a = golpes([(3, 60), (6, 65), (19, 60), (22, 65)], muestra=PERC)
    perc_b = golpes([(3, 60), (6, 65), (11, 55), (19, 60), (22, 65), (27, 55)], muestra=PERC)
    P = [
        golpes([0], 80, CRASH) | perc_a,
        perc_a, perc_b, perc_a, perc_b, perc_a,
        {},
        golpes([(3, 55), (19, 55)], muestra=PERC) | golpes([(23, 65)], muestra=SWELL),
    ]
    cadenas = {
        "Intro": (1, 1, 6, 8), "Intro 2": (1, 1, 7, 8), "Pulso": (2, 1, 6, 8),
        "Groove A": (2, 2, 2, (2, 5)), "Groove B": (2, 3, 4, (2, 5)), "Groove C": (3, 2, 3, (2, 5)),
        "Break": (1, 4, 7, 8), "Rise": ((5, 8), (5, 8), 5, (6, 7)),
        "Drive A": (3, 2, 4, (2, 5)), "Drive B": (3, 3, 3, (2, 5)), "Drive C": (2, 3, 4, (2, 5)),
        "Break 2": (1, 4, 7, 8), "Rise 2": ((5, 8), (5, 8), 5, (6, 7)), "Drive D": (3, 3, 4, (2, 5)),
        "Outro": (2, 1, 6, 8), "Final": (1, 1, 7, 8),
    }
    D4 = {'Intro': 7, 'Intro 2': 7, 'Pulso': (2, 3), 'Groove A': (1, 8), 'Groove B': (1, 8), 'Groove C': (1, 8), 'Break': 7, 'Rise': 7, 'Drive A': (1, 8), 'Drive B': (1, 8), 'Drive C': (1, 8), 'Break 2': 7, 'Rise 2': 7, 'Drive D': (1, 8), 'Outro': (2, 3), 'Final': 7}
    cadenas = {n: v[:3] + (D4[n],) for n, v in cadenas.items()}
    sonidos = {"drum1": {"sample": BOMBO, "level": 105}, "drum2": {"sample": CLAP, "level": 92},
               "drum3": {"sample": HAT_CERRADO, "level": 82}, "drum4": {"sample": PERC, "level": 80}}
    envios = {"reverb": {"drum2": 35, "drum4": 35}, "delay": {"drum3": 10, "drum4": 30}}
    return "CHILLGRESSIVE", K, C, H, P, cadenas, sonidos, envios, 50


# =====================================================================
# Template 8 · Chillout 92 (beat quebrado)
# =====================================================================
def template8():
    BOMBO, SNARE = 6, 25
    SHAKER, HAT_ABIERTO = 37, 35
    QUEBRADO = [0, 7, 10, 16, 26]
    K = [
        {},
        golpes(QUEBRADO, 110),
        golpes(QUEBRADO, 110) | golpes([(23, 60), (30, 55)]),
        golpes(QUEBRADO[:-1], 110),
        golpes([0], 110),
        golpes([0, 16], 110),
        golpes([0, 10, 16, 26], 110),
        golpes([0, 10] + list(range(16, 32, 2)), 106) | golpes([(18, 65)], muestra=RISER),
    ]
    C = [{}, golpes(DOS_Y_CUATRO, 95),
         golpes(DOS_Y_CUATRO, 95) | golpes([(14, 40), (27, 45), (30, 40)]),
         golpes([28], 95)] + _redobles(SNARE, ((35, 55), (50, 70), (65, 85), (80, 100)))
    H = [
        {},
        golpes([(p, 60 if p % 2 == 0 else 38) for p in range(32)], muestra=SHAKER),
        golpes([(p, 55) for p in range(0, 32, 2)], muestra=SHAKER),
        golpes([(p, 60 if p % 2 == 0 else 38) for p in range(32) if p not in (14, 30)], muestra=SHAKER)
        | golpes([(14, 65), (30, 70)], muestra=HAT_ABIERTO),
        golpes([(p, 25 + p * 2) for p in range(32)], muestra=SHAKER),
        golpes([(6, 55), (22, 60)], muestra=HAT_ABIERTO),
        golpes([(p, 50) for p in range(2, 32, 4)], muestra=HAT_ABIERTO),
        {},
    ]
    # Pista 4 en los géneros chill: percusión orgánica suave y los FX solo en los cambios.
    # Con la cadena 1-8 (16 compases): crash suave en el uno, 2 compases sin percusión
    # cerca del final y un swell suave que llega a la parte siguiente. 7 = silencio.
    conga_a = golpes([(3, 55), (11, 50), (19, 55), (27, 50)], muestra=CONGA_A)
    conga_b = golpes([(3, 55), (14, 45), (19, 55)], muestra=CONGA_A) | golpes([(11, 50), (27, 50)], muestra=PERC_A)
    P = [
        golpes([0], 70, CRASH) | conga_a,
        conga_a, conga_b, conga_a, conga_b, conga_a,
        {},
        golpes([(3, 45), (19, 45)], muestra=CONGA_A) | golpes([(23, 55)], muestra=SWELL),
    ]
    cadenas = {
        "Intro": (1, 1, 6, 8), "Intro 2": (1, 4, 6, 8), "Llega el beat": (2, 4, 2, 8),
        "Tema A": (2, 2, 2, (2, 5)), "Tema B": (3, 3, 4, (2, 5)), "Tema C": (2, 3, 7, (2, 5)),
        "Pausa": (1, 1, 6, 8), "Vuelta": ((5, 8), (5, 8), 5, (6, 7)),
        "Tema D": ((2, 3), 3, 4, (2, 5)), "Tema E": (3, 3, 7, (2, 5)), "Tema F": (2, 2, 4, (2, 5)),
        "Pausa 2": (1, 4, 6, 8), "Vuelta 2": ((5, 8), (5, 8), 5, (6, 7)), "Tema G": ((2, 3), 3, 4, (2, 5)),
        "Final": (2, 4, 6, 8), "Cierre": (1, 1, 6, 8),
    }
    D4 = {'Intro': 7, 'Intro 2': 7, 'Llega el beat': (2, 3), 'Tema A': (1, 8), 'Tema B': (1, 8), 'Tema C': (1, 8), 'Pausa': 7, 'Vuelta': 7, 'Tema D': (1, 8), 'Tema E': (1, 8), 'Tema F': (1, 8), 'Pausa 2': 7, 'Vuelta 2': 7, 'Tema G': (1, 8), 'Final': (2, 3), 'Cierre': 7}
    cadenas = {n: v[:3] + (D4[n],) for n, v in cadenas.items()}
    sonidos = {"drum1": {"sample": BOMBO, "level": 105}, "drum2": {"sample": SNARE, "level": 88},
               "drum3": {"sample": SHAKER, "level": 75}, "drum4": {"sample": CONGA_A, "level": 78}}
    envios = {"reverb": {"drum2": 45, "drum3": 20, "drum4": 45}, "delay": {"drum2": 20, "drum4": 35}}
    return "CHILLOUT", K, C, H, P, cadenas, sonidos, envios, 58


# =====================================================================
# Template 9 · Ambient 76 (sin bombo fijo)
# =====================================================================
def template9():
    BOOM, SUB_DROP, LATIDO = 51, 61, 13   # sin subs: swell medio, reverso y un bombo suave
    PERC_SUAVE, TOM_A, TOM_B, SNARE_CUERPO = 54, 53, 55, 25
    SHAKER, HAT_ABIERTO = 43, 35
    REVERSA, BLIP = 61, 45
    K = [
        {},
        golpes([0], 70, LATIDO),
        golpes([(0, 70), (16, 55)], muestra=LATIDO),
        golpes([0], 60, BOOM) | golpes([(22, 45)], muestra=BOOM),
        golpes([(0, 80), (3, 55), (16, 80), (19, 55)], muestra=LATIDO),        # latido
        golpes([(0, 60), (3, 40)], muestra=LATIDO),
        golpes([0], 55, LATIDO),
        {},
    ]
    C = [
        {},
        golpes([(8, 60)], muestra=TOM_GRAVE),
        golpes([(6, 50), (13, 40), (22, 55)], muestra=PERC_SUAVE),
        golpes([(12, 55)], muestra=TOM_A) | golpes([(28, 50)], muestra=TOM_B),
        golpes([(24, 45)], muestra=SNARE_CUERPO),
        golpes([(10, 45), (26, 45)], muestra=PERC_B),
        {},
        {},
    ]
    H = [
        {},
        golpes([(p, 40 if p % 4 == 0 else 28) for p in range(0, 32, 2)], muestra=SHAKER),
        golpes([(p, 25 + (p % 4 == 0) * 10) for p in range(32)], muestra=SHAKER),
        golpes([(14, 40), (30, 45)], muestra=HAT_ABIERTO),
        golpes([(p, 35) for p in range(0, 32, 2)], muestra=SHAKER) | golpes([(30, 40)], muestra=HAT_ABIERTO),
        {},
        {},
        {},
    ]
    # Pista 4: casi nada. Percusión muy suave y un swell que llega a la parte siguiente
    # solo con la cadena 1-8 (una vez cada 16 compases). 2 = silencio.
    P = [
        golpes([(6, 40), (19, 35)], muestra=BLIP),
        {},
        golpes([(11, 35)], muestra=PERC_B),
        {},
        golpes([(6, 35), (22, 35)], muestra=BLIP),
        {},
        {},
        golpes([(23, 45)], muestra=SWELL),
    ]
    cadenas = {
        "Niebla": (1, 1, 1, (3, 6)), "Niebla 2": (7, 1, 1, (3, 6)), "Marea": (2, 2, 1, (3, 6)),
        "Marea 2": (2, 2, 2, (5, 8)), "Luz": (2, 3, 2, (5, 8)), "Luz 2": (3, 3, 2, (3, 6)),
        "Pulso suave": (5, 3, 3, (3, 6)), "Pulso 2": (5, (3, 4), 4, (5, 8)),
        "Profundo": ((6, 7), 4, 4, (2, 5)), "Profundo 2": ((6, 7), (4, 5), 4, (2, 5)),
        "Claro": (5, (3, 4), 5, (5, 8)), "Claro 2": (2, 3, 5, (3, 6)), "Calma": (7, 2, 1, (3, 6)),
        "Eco": (2, 6, 2, (5, 8)), "Disolucion": (2, 2, 1, (3, 6)), "Silencio": (1, 1, 1, (3, 4)),
    }
    D4 = {'Niebla': 2, 'Niebla 2': 2, 'Marea': (1, 4), 'Marea 2': (1, 8), 'Luz': (1, 8), 'Luz 2': (1, 4), 'Pulso suave': (1, 8), 'Pulso 2': (1, 4), 'Profundo': (1, 8), 'Profundo 2': (1, 8), 'Claro': (1, 8), 'Claro 2': (1, 4), 'Calma': (1, 8), 'Eco': (1, 4), 'Disolucion': (1, 8), 'Silencio': 2}
    cadenas = {n: v[:3] + (D4[n],) for n, v in cadenas.items()}
    sonidos = {"drum1": {"sample": LATIDO, "level": 95}, "drum2": {"sample": PERC_SUAVE, "level": 80},
               "drum3": {"sample": SHAKER, "level": 65}, "drum4": {"sample": SWELL, "level": 80}}
    envios = {"reverb": {"drum1": 25, "drum2": 60, "drum3": 40, "drum4": 65}, "delay": {"drum2": 40, "drum3": 20, "drum4": 40}}
    return "AMBIENT", K, C, H, P, cadenas, sonidos, envios, 50


TEMPLATES = {"template1": template1, "template2": template2, "template3": template3,
             "template4": template4, "template5": template5, "template6": template6,
             "template7": template7, "template8": template8, "template9": template9}


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
        "name": nombre, "bpm": plantilla["bpm"], "swing": swing, "scale": {"root": "F", "type": plantilla.get("escala_circuit", "phrygian")},
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
