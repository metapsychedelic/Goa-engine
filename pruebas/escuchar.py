"""Renderiza una secuencia con un beat de psytrance para escucharla sin hardware.

  python3 -m pruebas.escuchar salida.wav [estilo] [seed ...]

Bombo en negras, hi-hat abierto en los contratiempos y la secuencia con un
sinte simple tipo 303 (diente de sierra, filtro resonante, glide en los slides).
"""

import sys
import wave

import numpy as np

from goa.config import cargar
from goa.motor import Motor
from pruebas.simular import RAIZ

SR = 44100
BPM = 140
TICK = 60 / BPM / 24


def eventos(estilo, seed, compases, extra=None):
    cfg = cargar(RAIZ / "config.ejemplo.toml")
    cfg["entrada"]["canal_disparo"] = 2
    s = cfg["secuencia"][0]
    s.update(disparo=0, estilo=estilo, posicion="todos", seed=seed, salida="SEQ", gate=0.5, acento=127, velocidad=90,
             acentos=0.3, slide=0.3)
    s.update(extra or {})
    cfg["secuencia"][1]["activa"] = False
    out = []
    m = Motor(cfg, lambda sal, tipo, canal, nota, vel: out.append((m.tick, tipo, nota, vel)))
    m.start()
    m.nota_on(1, 41)  # F2 como nota larga
    for _ in range(compases * 96):
        m.reloj()
    m.stop()
    return out


def notas(evs):
    """Pares (inicio, fin, nota, velocidad, desliza) en segundos."""
    abiertas, res = {}, []
    for tick, tipo, nota, vel in evs:
        t = max(tick, 0) * TICK
        if tipo == "note_on":
            desliza = any(abiertas.values())  # empieza con otra nota sonando: slide
            abiertas[nota] = (t, vel, desliza)
        elif nota in abiertas:
            ini, v, d = abiertas.pop(nota)
            res.append((ini, t, nota, v, d))
    return sorted(res)


def sinte_303(lista, dur):
    n = int(dur * SR)
    freq = np.zeros(n)
    gate = np.zeros(n)
    acc = np.zeros(n)
    env_ini = np.full(n, -1.0)
    actual = 110.0
    for ini, fin, nota, vel, desliza in lista:
        a, b = int(ini * SR), min(n, int(fin * SR))
        objetivo = 440 * 2 ** ((nota - 69) / 12)
        largo = b - a
        if desliza and largo > 0:
            g = min(largo, int(0.06 * SR))
            freq[a:a + g] = np.geomspace(actual, objetivo, g)
            freq[a + g:b] = objetivo
        else:
            freq[a:b] = objetivo
            env_ini[a] = 1.0
        gate[a:b] = 1.0
        acc[a:b] = 1.0 if vel >= 110 else 0.0
        actual = objetivo
    # mantener la frecuencia en los silencios para que el oscilador no salte
    for i in range(1, n):
        if freq[i] == 0:
            freq[i] = freq[i - 1] or 110.0
    fase = np.cumsum(freq / SR) % 1.0
    osc = 2 * fase - 1
    # envolvente de filtro: decae desde cada nota no ligada
    env = np.zeros(n)
    nivel = 0.0
    caida = np.exp(-1 / (0.18 * SR))
    for i in range(n):
        if env_ini[i] > 0:
            nivel = 1.0
        nivel *= caida
        env[i] = nivel
    corte = 180 + 2200 * env * (0.6 + 0.8 * acc)
    # filtro de estado variable con resonancia (2 polos, dos veces = 4 polos)
    y = osc
    for _ in range(2):
        lp = bp = 0.0
        sal = np.zeros(n)
        q = 0.25
        for i in range(n):
            f = 2 * np.sin(np.pi * min(corte[i], 8000) / SR)
            hp = y[i] - lp - q * bp
            bp += f * hp
            lp += f * bp
            sal[i] = lp
        y = sal
    amp_env = np.convolve(gate, np.ones(80) / 80, mode="same")
    return y * amp_env * (0.6 + 0.4 * acc) * 0.5


def beat(dur):
    n = int(dur * SR)
    out = np.zeros(n)
    negra = 60 / BPM
    t = np.arange(int(0.25 * SR)) / SR
    bombo = np.sin(2 * np.pi * (45 + 120 * np.exp(-t * 35)) * t) * np.exp(-t * 9)
    th = np.arange(int(0.06 * SR)) / SR
    hat = np.random.default_rng(1).uniform(-1, 1, len(th)) * np.exp(-th * 60)
    hat = np.diff(hat, prepend=0)
    k = 0
    while k * negra < dur:
        a = int(k * negra * SR)
        out[a:a + len(bombo)] += bombo[: n - a] * 0.9
        h = int((k + 0.5) * negra * SR)
        if h < n:
            out[h:h + len(hat)] += hat[: n - h] * 0.25
        k += 1
    return out


def main():
    salida = sys.argv[1] if len(sys.argv) > 1 else "acido.wav"
    estilo = sys.argv[2] if len(sys.argv) > 2 else "acido"
    seeds = sys.argv[3:] or ["7A3F-0291", "ACID-1", "B-5512"]
    compases = 4
    dur = compases * 4 * 60 / BPM
    partes = []
    for seed in seeds:
        acid = sinte_303(notas(eventos(estilo, seed, compases)), dur)
        partes.append(beat(dur) + acid)
    audio = np.concatenate(partes)
    audio = np.tanh(audio * 1.2) * 0.8
    with wave.open(salida, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((audio * 32767).astype(np.int16).tobytes())
    print(f"{salida}: {len(seeds)} seeds × {compases} compases a {BPM} BPM")


if __name__ == "__main__":
    main()
