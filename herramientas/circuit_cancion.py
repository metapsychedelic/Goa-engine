"""Arma el proyecto de la Circuit Tracks para una canción del motor (percusión).

Usa la librería circuit-tracks-tools (github.com/namirsab/circuit-tracks-tools)
para escribir el archivo .ncs con escenas de cadenas de patrones distintas en cada
pista, cosa que su formato de canción no permite (ahí cada escena es un solo
patrón de 2 compases).

Cómo se arma:
- Cada pista tiene 8 patrones de 32 pasos (2 compases). Cada escena elige en cada
  pista un tramo de esos patrones; la escena dura lo que su cadena más larga.
- Synth 1 es la «regla»: sus 8 patrones van vacíos y su cadena marca el largo de
  cada escena (0-7 = 16 compases, 0-3 = 8). Las baterías usan cadenas de 1, 2 o 4
  patrones, que siempre caben justo, así todo cambia en el compás exacto.
- La misma estructura (CANCION) sirve para armar las partes del modo canción del
  motor, con los mismos largos.

Uso:  python3 herramientas/circuit_cancion.py salida.ncs
(con circuit-tracks-tools instalado: pip install circuit-tracks-tools)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from goa.plantillas import PLANTILLAS  # noqa: E402
from circuit_tracks import ncs_parser as ncs  # noqa: E402
from circuit_tracks.song import parse_song, song_to_ncs  # noqa: E402


# Muestras del banco FROM GOA TO PSYT (clasificadas escuchando el audio).
BOMBO, CLAP, SNARE_ROLL = 3, 16, 22
HAT_MEDIO, HAT_CERRADO, HAT_CERRADO_2, HAT_ABIERTO, RIDE = 36, 32, 33, 39, 40
PERC_A, PERC_B, PERC_C = 47, 53, 44
CRASH, RISER, SWELL, ATMOS = 40, 63, 41, 60

PASOS = 32  # 2 compases de semicorcheas


def golpes(pasos, vel=110, muestra=None):
    """{paso: {velocity, sample}} para una lista de pasos (o de (paso, vel))."""
    d = {}
    for p in pasos:
        paso, v = p if isinstance(p, tuple) else (p, vel)
        d[str(paso)] = {"velocity": v} | ({"sample": muestra} if muestra is not None else {})
    return d


NEGRAS = list(range(0, 32, 4))
CONTRAS = list(range(2, 32, 4))
DOS_Y_CUATRO = [4, 12, 20, 28]

# --- Drum 1: bombo ---
K = [
    {},                                                       # 1 vacío (intro, breaks)
    golpes(NEGRAS, 118),                                      # 2 4/4
    golpes(NEGRAS, 118),                                      # 3 4/4
    golpes(NEGRAS, 118),                                      # 4 4/4
    golpes([0, 4, 8, 12, 16, 20, 24, 30], 118),               # 5 4/4 con remate (falta el último, entra a contratiempo)
    golpes(NEGRAS[:4] + list(range(16, 32, 2)), 116),         # 6 4/4 y corcheas en el 2.º compás (fin de build)
    {},                                                       # 7 libre
    {},                                                       # 8 libre
]

# --- Drum 2: clap y redobles ---
def redoble(pasos, desde, hasta):
    n = len(pasos)
    return golpes([(p, round(desde + (hasta - desde) * i / max(1, n - 1))) for i, p in enumerate(pasos)], muestra=SNARE_ROLL)


C = [
    {},                                                       # 1 vacío
    golpes(DOS_Y_CUATRO, 100),                                # 2 clap en 2 y 4
    golpes(DOS_Y_CUATRO, 100),                                # 3 clap en 2 y 4
    golpes(DOS_Y_CUATRO, 100) | golpes([(30, 70)]),           # 4 clap + fantasma
    redoble(list(range(0, 16, 4)) + list(range(16, 32, 2)), 50, 85),   # 5 redoble A: negras, corcheas
    redoble(list(range(0, 16, 2)) + list(range(16, 32)), 60, 100),     # 6 redoble B: corcheas, semicorcheas
    redoble(list(range(0, 32)), 75, 115),                    # 7 redoble C: semicorcheas
    redoble(list(range(0, 32)), 95, 127),                    # 8 redoble D: semicorcheas a tope
]

# --- Drum 3: hats ---
semis_suaves = [(p, 55) for p in range(1, 32, 2)]
H = [
    {},                                                                    # 1 vacío
    golpes(CONTRAS, 100, HAT_MEDIO),                                       # 2 contratiempo
    golpes(CONTRAS, 100, HAT_MEDIO) | golpes(semis_suaves, muestra=HAT_CERRADO),   # 3 contra + semis suaves
    golpes(CONTRAS, 100, HAT_MEDIO) | golpes(semis_suaves, muestra=HAT_CERRADO) | golpes([(30, 95)], muestra=HAT_ABIERTO),  # 4 + abierto
    golpes([(p, 60) for p in range(0, 32, 2)], muestra=HAT_CERRADO_2),     # 5 corcheas suaves (intro)
    golpes([(p, 70 if p % 4 == 2 else 45) for p in range(0, 32)], muestra=HAT_CERRADO_2),  # 6 semis con acento (intro 2, rise)
    {},                                                                    # 7 libre
    golpes(CONTRAS, 90, RIDE) | golpes(semis_suaves, muestra=HAT_CERRADO), # 8 ride en contratiempo (clímax B)
]

# --- Drum 4: percusión y FX ---
perc_a = golpes([(3, 70), (11, 60), (19, 70), (27, 60)], muestra=PERC_A)
perc_b = golpes([(6, 65), (14, 75), (22, 65), (26, 55), (30, 75)], muestra=PERC_B)
P = [
    {},                                                       # 1 vacío
    golpes([0], 110, CRASH) | perc_a,                         # 2 crash al entrar + perc A
    perc_a,                                                   # 3 perc A
    perc_b,                                                   # 4 perc B
    perc_b | golpes([18], 100, RISER),                        # 5 perc B + riser que llega al uno siguiente
    golpes([23], 100, SWELL),                                 # 6 swell que llega al uno siguiente
    golpes([0], 90, ATMOS),                                   # 7 atmósfera
    {},                                                       # 8 libre
]

# --- MIDI 1 y MIDI 2: las notas largas que disparan el motor ---
# MIDI 1 sale por el canal 3 (pads) y MIDI 2 por el canal 4 (secuencias), según el
# Setup de la Circuit. La nota se vuelve a tocar en cada compás (en la Circuit una
# nota dura como mucho 16 pasos); el motor tiene medio paso de gracia entre una y
# otra, así que no se corta. Suena en todas las escenas: qué suena en cada parte lo
# decide la canción del motor.
NOTA_LARGA = 41  # F2, la tónica


def nota_larga(nota=NOTA_LARGA):
    return {"0": {"note": nota, "velocity": 100, "gate": 16}, "16": {"note": nota, "velocity": 100, "gate": 16}}


# --- Cadenas de cada parte: {pista: (desde, hasta)} con patrones 1-8 ---
# Los nombres y compases salen de la plantilla del motor (goa/plantillas.py), así la
# canción del motor y la de la Circuit son siempre la misma.
CADENAS = {
    "Intro": {"drum1": (1, 1), "drum2": (1, 1), "drum3": (5, 5), "drum4": (7, 7)},
    "Intro bombo": {"drum1": (2, 5), "drum2": (1, 1), "drum3": (6, 6), "drum4": (3, 3)},
    "Build": {"drum1": (3, 6), "drum2": (2, 5), "drum3": (2, 3), "drum4": (4, 5)},
    "Groove A": {"drum1": (2, 5), "drum2": (2, 3), "drum3": (2, 3), "drum4": (3, 3)},
    "Groove B": {"drum1": (2, 5), "drum2": (3, 4), "drum3": (3, 4), "drum4": (3, 4)},
    "Groove C": {"drum1": (2, 5), "drum2": (3, 4), "drum3": (4, 4), "drum4": (4, 4)},
    "Break": {"drum1": (1, 1), "drum2": (1, 1), "drum3": (5, 5), "drum4": (7, 7)},
    "Rise": {"drum1": (1, 1), "drum2": (5, 8), "drum3": (6, 6), "drum4": (5, 6)},
    "Climax A": {"drum1": (2, 5), "drum2": (2, 3), "drum3": (3, 4), "drum4": (2, 3)},
    "Climax B": {"drum1": (2, 5), "drum2": (3, 4), "drum3": (8, 8), "drum4": (3, 4)},
    "Groove D": {"drum1": (2, 5), "drum2": (2, 3), "drum3": (2, 3), "drum4": (3, 3)},
    "Break 2": {"drum1": (1, 1), "drum2": (1, 1), "drum3": (5, 5), "drum4": (7, 7)},
    "Rise 2": {"drum1": (1, 1), "drum2": (5, 8), "drum3": (6, 6), "drum4": (5, 6)},
    "Drop": {"drum1": (2, 5), "drum2": (2, 3), "drum3": (3, 4), "drum4": (2, 3)},
    "Groove E": {"drum1": (2, 5), "drum2": (3, 4), "drum3": (2, 3), "drum4": (3, 4)},
    "Outro": {"drum1": (2, 5), "drum2": (1, 1), "drum3": (2, 2), "drum4": (7, 7)},
}
PLANTILLA = PLANTILLAS["template1"]
CANCION = [(nombre, compases, CADENAS[nombre]) for nombre, compases, *_ in PLANTILLA["partes"]]
ORDEN_PISTAS = ["synth1", "synth2", "midi1", "midi2", "drum1", "drum2", "drum3", "drum4"]


NOMBRE = "GOA CANCION 1"
BPM = PLANTILLA["bpm"]


def armar():
    patrones = {}
    for i in range(8):
        pistas = {}
        for nombre, lista in (("drum1", K), ("drum2", C), ("drum3", H), ("drum4", P)):
            if lista[i]:
                pistas[nombre] = {"steps": lista[i]}
        if i == 0:  # las escenas usan el patrón 1 de MIDI 1 y MIDI 2
            pistas["midi1"] = {"steps": nota_larga()}
            pistas["midi2"] = {"steps": nota_larga()}
        patrones[f"p{i + 1}"] = {"length": PASOS, "tracks": pistas}
    cancion = {
        "name": NOMBRE, "bpm": BPM, "swing": 50, "scale": {"root": "F", "type": "phrygian"},
        "sounds": {"drum1": {"sample": BOMBO, "level": 115}, "drum2": {"sample": CLAP, "level": 95},
                   "drum3": {"sample": HAT_MEDIO, "level": 85}, "drum4": {"sample": PERC_A, "level": 80}},
        "fx": {"reverb_sends": {"drum2": 25, "drum4": 40}, "delay_sends": {"drum4": 30}},
        "patterns": patrones,
    }
    datos = song_to_ncs(parse_song(cancion))
    proyecto = ncs.parse_ncs_from_bytes(datos)
    for i, (_, compases, cadenas) in enumerate(CANCION):
        regla = (0, 7) if compases == 16 else (0, 3) if compases == 8 else (0, 1)
        pistas = {}
        for t, nombre in enumerate(ORDEN_PISTAS):
            if nombre == "synth1":
                pistas[t] = regla
            elif nombre in cadenas:
                a, b = cadenas[nombre]
                pistas[t] = (a - 1, b - 1)
            else:
                pistas[t] = (0, 0)
        ncs.set_scene(proyecto, i, pistas)
    ncs.set_scene_chain(proyecto, start=0, end=len(CANCION) - 1)
    return ncs.serialize_ncs(proyecto)


def comprobar():
    """Cada cadena de batería cabe justo en su escena (1, 2, 4 u 8 patrones)."""
    for nombre, compases, cadenas in CANCION:
        assert compases in (8, 16), nombre
        for pista, (a, b) in cadenas.items():
            largo = (b - a + 1) * 2
            assert compases % largo == 0, f"{nombre}: {pista} dura {largo} compases"
    total = sum(c for _, c, _ in CANCION)
    return total


if __name__ == "__main__":
    total = comprobar()
    datos = armar()
    with open(sys.argv[1] if len(sys.argv) > 1 else "cancion.ncs", "wb") as f:
        f.write(datos)
    print(f"{NOMBRE}: {len(CANCION)} escenas, {total} compases, {total * 240 / BPM / 60:.2f} min a {BPM} BPM, {len(datos)} bytes")
