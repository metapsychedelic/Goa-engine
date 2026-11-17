"""Ragas y ornamentos Goa (alankar), opcionales por secuencia.

Cada raga define su escala (desde la tónica de Música, el Sa) y cómo se adornan
sus notas. Los ornamentos salen de la música indostaní:

- **Kan** (kan-swar): nota de gracia muy breve y suave de una nota vecina, antes de
  la nota principal. Cada raga dice qué notas la llevan y desde dónde (en Todi el
  re ♭2 toma su kan del ga ♭3).
- **Meend**: deslizamiento con pitch bend desde la nota de arriba hasta la que
  suena (el «swoop» G→r de Bhairav). Necesita el rango de pitch bend del sinte.
- **Gamak**: oscilación fuerte entre la nota y su vecina de arriba, en las notas
  que la raga hace temblar (komal re y komal dha en Bhairav).
- **Andolan**: oscilación lenta y poco profunda (pitch bend) en esas mismas notas
  cuando se sostienen.
- **Pakad**: la frase que identifica a la raga; el Goa clásico la usa para cerrar
  la respuesta.

Hijaz es la versión de Medio Oriente (freygish / Ahava Rabbah del Goa israelí):
la segunda aumentada ♭2→3, el trino sobre el ♭2 y la caída ♭6 5 4 3 ♭2 1.
"""

# Sa (1) y Pa (5) son notas fijas (achal): nunca se adornan, el pedal queda limpio y
# los ornamentos caen en las notas que la raga hace cantar.
RAGAS = {
    "bhairav": {
        "nombre": "Bhairav",
        "escala": [0, 1, 4, 5, 7, 8, 11],     # doble armónica: komal re y komal dha
        "oscila": {1, 8},                       # re y dha tiemblan (andolan / gamak)
        "kan": {1: 4, 8: 11, 4: 5},             # nota → de dónde viene su gracia (r con gracia de G)
        "meend": {1: 0, 8: 7, 4: 5},            # nota → desde dónde se desliza
        "pakad": [4, 5, 1, 0],                  # G m r S (la bajada clásica de Bhairav)
    },
    "bhairavi": {
        "nombre": "Bhairavi",
        "escala": [0, 1, 3, 5, 7, 8, 10],     # todo komal: el frigio
        "oscila": {1, 8},
        "kan": {1: 3, 3: 5, 8: 10},
        "meend": {1: 3, 8: 10, 3: 5},
        "pakad": [5, 3, 1, 0],                  # m g r S
    },
    "todi": {
        "nombre": "Todi",
        "escala": [0, 1, 3, 6, 7, 8, 11],     # ♭2 ♭3 ♯4 ♭6 7: serio, mucho pathos
        "oscila": {1, 3, 8},
        "kan": {1: 3, 8: 11, 3: 6},             # el re toma la gracia del ga
        "meend": {1: 3, 8: 7, 3: 1},
        "pakad": [3, 1, 3, 1, 0],               # g r g r S
    },
    "marwa": {
        "nombre": "Marwa",
        "escala": [0, 1, 4, 6, 7, 9, 11],     # ♭2 3 ♯4 6 7: crepuscular, inquieta
        "oscila": {1},
        "kan": {1: 4, 9: 11, 4: 6},
        "meend": {1: 0, 4: 6, 9: 11},
        "pakad": [4, 6, 4, 1, 0],               # G M G r S (el re pesa más que el Sa)
    },
    "hijaz": {
        "nombre": "Hijaz (israelí)",
        "escala": [0, 1, 4, 5, 7, 8, 10],     # frigio dominante / freygish
        "oscila": {1, 8},                       # trino sobre el ♭2 y el ♭6
        "kan": {4: 5, 1: 4, 8: 10},             # el ♭2 con gracia de la 3.ª: la segunda aumentada
        "meend": {1: 0, 4: 5, 8: 7},
        "pakad": [8, 7, 5, 4, 1, 0],            # ♭6 5 4 3 ♭2 1
    },
}
NOMBRES = ("",) + tuple(RAGAS)


def escala(raga):
    return RAGAS[raga]["escala"] if raga in RAGAS else None


def pakad_en_grados(raga):
    """La frase de la raga en grados de su escala (para el generador)."""
    r = RAGAS.get(raga)
    if not r:
        return []
    return [r["escala"].index(st % 12) + 7 * (st // 12) for st in r["pakad"]]


def clase(nota, tonica):
    return (nota - tonica) % 12


def kan(raga, nota, tonica):
    """La nota de gracia (kan) para `nota`, o None si la raga no la adorna."""
    r = RAGAS.get(raga)
    if not r:
        return None
    c = clase(nota, tonica)
    if c not in r["kan"]:
        return None
    fuente = r["kan"][c]
    d = (fuente - c) % 12
    return nota + (d if d <= 6 else d - 12)


def meend(raga, nota, tonica):
    """Cuántos semitonos arriba (+) o abajo (-) parte el deslizamiento hacia `nota`."""
    r = RAGAS.get(raga)
    if not r:
        return None
    c = clase(nota, tonica)
    if c not in r["meend"]:
        return None
    d = (r["meend"][c] - c) % 12
    return d if d <= 6 else d - 12


def oscila(raga, nota, tonica):
    r = RAGAS.get(raga)
    return bool(r) and clase(nota, tonica) in r["oscila"]


def vecina_arriba(raga, nota, tonica):
    """La nota de la raga justo arriba de `nota` (para el gamak)."""
    esc = RAGAS[raga]["escala"]
    for d in range(1, 13):
        if clase(nota + d, tonica) in esc:
            return nota + d
    return nota + 1


def bend(semitonos, rango):
    """Valor de pitch bend (-8192..8191) para correr `semitonos` con el rango del sinte."""
    if rango <= 0:
        return 0
    v = round(semitonos / rango * 8191)
    return max(-8192, min(8191, v))
