"""Batería de la Circuit Tracks en los rises y fills (módulo «Rises y fills», etapa 2).

Genera los golpes de una transición como un dict {paso relativo: [Golpe, ...]}, igual al
prototipo audible que aprobó el usuario. Cada golpe dice qué Drum toca (1-4), con qué
fuerza, si cae a mitad del paso (fusas: `medio`), el pitch del Drum (CC, 64 = normal) y el
sample que hay que cargar antes (o None). El motor (motor_forma._paso_bateria) los manda.

Circuit Tracks (programmer's reference v3), canal 10: notas 60/62/64/65 = Drum 1-4;
patch select CC 8/18/44/50 (el valor es el número de sample: probado), pitch CC 14/34/46/55.
"""

import random
from dataclasses import dataclass

NOTAS = {1: 60, 2: 62, 3: 64, 4: 65}
CC_SAMPLE = {1: 8, 2: 18, 3: 44, 4: 50}
CC_PITCH = {1: 14, 2: 34, 3: 46, 4: 55}

TIPOS_RISE = ("redoble", "riser", "toms", "reversa", "glitch", "bombo")
TIPOS_FILL = ("redoble", "toms", "glitch", "claps", "bombo")

# Samples del banco FROM GOA TO PSYT (goa/muestras_circuit.py) que usa cada tipo en la voz de FX
# cuando su sample está en «automático».
RISER, REVERSA, ZAP, BLIP = 63, 61, 62, 24
TOMS = (53, 54, 55)          # agudo, medio, grave


@dataclass
class Golpe:
    drum: int
    vel: int
    medio: bool = False        # cae a mitad del paso (fusas)
    pitch: int = None          # valor del CC de pitch del Drum antes de tocar (None = no lo toca)
    sample: int = None         # sample a cargar antes de tocar (None = el que tenga)


def _intervalo(s, intensidad):
    """Cada cuántos pasos golpea el redoble según el avance s (0-1): negras, corcheas,
    semicorcheas y fusas al final si la intensidad es alta."""
    c = 0.6 + intensidad * 1.4
    x = s ** (1 / c) if s > 0 else 0.0
    return 4 if x < 0.3 else 2 if x < 0.55 else 1 if x < 0.85 else (0.5 if intensidad > 0.5 else 1)


def fuerza(t, s, factor=1.0):
    """Velocity con el avance s (0-1): de `bateria_vel_desde` a `bateria_vel_hasta`."""
    d, h = int(t.get("bateria_vel_desde", 70)), int(t.get("bateria_vel_hasta", 127))
    return max(1, min(127, round((d + (h - d) * max(0.0, min(1.0, s))) * factor)))


def elegir_tipo(tipo, tipos, seed, vez, variar):
    rng = random.Random(f"bateria:{seed}:{vez if variar else 0}")
    elegido = rng.choice(tipos)
    return (tipo if tipo in tipos else elegido), rng


def rise(t, total, vez=0):
    """Golpes del rise de batería de la transición `t` (dict de ESQUEMA_RISE) en `total` pasos."""
    tipo, rng = elegir_tipo(t.get("bateria"), TIPOS_RISE, t.get("bateria_seed", ""), vez, t.get("bateria_variar", True))
    inten, pitch = float(t.get("bateria_intensidad", 0.6)), float(t.get("bateria_pitch", 0.5))
    hasta = total - int(t.get("bateria_silencio", 2))
    golpe, fx = int(t.get("golpe_drum", 2)), int(t.get("fx_drum", 4))
    s_golpe = int(t.get("golpe_sample", 22))
    s_fx = int(t.get("fx_sample", -2))
    sube = rng.random() < 0.5
    acento = rng.choice((3, 4, 6))
    ev = {}

    def poner(pos, g):
        k = int(pos)
        if 0 <= k < hasta:
            g.medio = pos - k >= 0.5
            ev.setdefault(k, []).append(g)

    muestra_golpe = s_golpe if s_golpe >= 0 else None
    if tipo in ("redoble", "riser", "reversa", "toms"):
        pos, j = 0.0, 0
        while pos < hasta:
            s = pos / total
            vel = fuerza(t, s, 1 if j % acento == 0 else 0.85)
            if tipo == "toms":
                orden = TOMS if not sube else TOMS[::-1]
                muestra = orden[j % 3] if s_fx != -1 else None
                poner(pos, Golpe(fx, vel, sample=muestra, pitch=None if muestra else (54, 64, 74)[j % 3]))
            else:
                poner(pos, Golpe(golpe, vel, pitch=round(64 + pitch * s * 40), sample=muestra_golpe if j == 0 else None))
            pos += _intervalo(s, inten)
            j += 1
    if tipo == "riser":
        poner(max(0, total - 32), Golpe(fx, fuerza(t, 0.85), sample=RISER if s_fx == -2 else (s_fx if s_fx >= 0 else None)))
    if tipo == "reversa":
        poner(max(0, total - 16), Golpe(fx, fuerza(t, 0.95), sample=REVERSA if s_fx == -2 else (s_fx if s_fx >= 0 else None)))
    if tipo == "glitch":
        grupos = (3, 3, 2)
        compases = max(1, total // 16)
        for b in range(compases):
            s = b / compases
            largo = 1 if s < 0.5 else 0.5 if s < 0.8 else 0.25
            pos, g = b * 16, 0
            while pos < (b + 1) * 16:
                k = 0.0
                n = grupos[g % 3] * (1 if largo >= 1 else largo * 2)
                while k < n:
                    zap = k == 0
                    muestra = (ZAP if zap else BLIP) if s_fx == -2 else (s_fx if s_fx >= 0 else None)
                    poner(pos + k, Golpe(fx, fuerza(t, s), sample=muestra,
                                         pitch=None if s_fx != -1 else round(64 + pitch * s * 30)))
                    k += max(0.5, largo)
                pos += grupos[g % 3] * (2 if largo >= 1 else 1)
                g += 1
    if tipo == "bombo":
        for i in range(hasta):
            s = i / total
            iv = 4 if s < 0.5 else 2 if s < 0.75 else 1
            if i % iv == 0 and i % 4 != 0:
                poner(i, Golpe(1, fuerza(t, 0.4 + 0.6 * s)))
            if i % 8 == 4:
                poner(i, Golpe(golpe, fuerza(t, s), pitch=round(64 + pitch * s * 20),
                               sample=muestra_golpe if i == 4 else None))
    return tipo, ev


def fill(t, vez=0):
    """Golpes del fill de batería de `t` (ESQUEMA_FILL) en sus últimos `bateria_largo` pasos."""
    tipo, rng = elegir_tipo(t.get("bateria"), TIPOS_FILL, t.get("bateria_seed", ""), vez, t.get("bateria_variar", True))
    largo = int(t.get("bateria_largo", 8))
    golpe, fx = int(t.get("golpe_drum", 2)), int(t.get("fx_drum", 4))
    s_golpe, s_fx = int(t.get("golpe_sample", 22)), int(t.get("fx_sample", -2))
    muestra_golpe = s_golpe if s_golpe >= 0 else None
    ev = {}

    def poner(pos, g):
        k = int(pos)
        if 0 <= k < largo:
            g.medio = pos - k >= 0.5
            ev.setdefault(k, []).append(g)

    if tipo == "redoble":
        i, primero = 0, True
        while i < largo:
            poner(i, Golpe(golpe, fuerza(t, i / max(1, largo - 1)), pitch=round(64 + 12 * i / largo),
                           sample=muestra_golpe if primero else None))
            primero = False
            i += 1 if i >= largo - 4 else 2
    elif tipo == "toms":
        paso = 2 if largo >= 8 else 1
        pasos = list(range(0, largo, paso))
        for j, i in enumerate(pasos):
            n = min(2, j * 3 // max(1, len(pasos)))
            muestra = TOMS[n] if s_fx != -1 else None
            poner(i, Golpe(fx, fuerza(t, j / max(1, len(pasos) - 1)), sample=muestra, pitch=None if muestra else (74, 64, 54)[n]))
    elif tipo == "glitch":
        pos = 0.0
        while pos < largo:
            zap = rng.random() < 0.5
            muestra = (ZAP if zap else BLIP) if s_fx == -2 else (s_fx if s_fx >= 0 else None)
            poner(pos, Golpe(fx, fuerza(t, pos / largo), sample=muestra, pitch=round(64 + rng.random() * 24)))
            pos += 1 if rng.random() < 0.5 else 0.5
    elif tipo == "claps":
        for i in range(max(0, largo - 4), largo):
            poner(i, Golpe(golpe, fuerza(t, (i - largo + 4) / 3), sample=muestra_golpe if i == largo - 4 else None))
    elif tipo == "bombo":
        for i in ((largo - 6) if largo >= 8 else None, largo - 2, largo - 1):
            if i is not None:
                poner(i, Golpe(1, fuerza(t, 1.0)))
    return tipo, ev
