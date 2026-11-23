"""Escuchar el bajo sin hardware: corre el motor de verdad (solo bajo) y lo renderiza con
un sinte de bajo psy mono (sierra + cuadrada, filtro resonante de 2 polos con envolvente
por nota, pitch bend y CC 74 del motor), con bombo y hi-hats.

  python3 -m pruebas.escuchar_bajo carpeta/ [compases]

Deja un .mp3 por ejemplo (o .wav si no hay ffmpeg).
"""

import math
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

from goa.config import cargar, normalizar
from goa.motor import Motor
from pruebas.simular import RAIZ

SR = 44100

# nombre, BPM, nota larga, escala, ajustes del bajo, sonido (ver SONIDOS), batería ("4x4" o "halftime")
# Zenonesque: 126-134 BPM, bajo de una nota a contratiempo, corto, semicorcheas con swing y el filtro
# moviéndose lento en frases largas; la nota larga entra justo después del bombo y cae.
# Swampy (swamp / psybass): la contraparte lenta del forest, groove en halftime, notas largas
# que se deslizan y un filtro «squelchy» que se abre en cada nota.
EJEMPLOS = [
    ("01_rolling_de_base", 140, 42, "frigio", dict(estilo="rolling", frase=4), "psy", "4x4"),
    ("02_rolling_remates_de_los_packs", 140, 42, "frigio", dict(estilo="rolling", frase=2, remates_pack=1.0), "psy", "4x4"),
    ("03_trote_332", 138, 42, "frigio", dict(estilo="trote", frase=4), "psy", "4x4"),
    ("04_zenon_offbeat_seco", 132, 41, "frigio", dict(estilo="offbeat", frase=4, remates=False, gate=0.35, swing=0.12,
                                                       movimiento=0.0, filtro=True, filtro_min=30, filtro_max=85,
                                                       filtro_ciclo=16, filtro_forma="ola", filtro_nota=0.3), "zenon", "4x4"),
    ("05_zenon_offbeat_nota_larga", 132, 41, "frigio", dict(estilo="offbeat", frase=4, remates=False, gate=0.35,
                                                             swing=0.12, movimiento=0.0, zenon=1.0, caida=7, filtro=True,
                                                             filtro_min=30, filtro_max=85, filtro_ciclo=16,
                                                             filtro_forma="ola", filtro_nota=0.3), "zenon", "4x4"),
    ("06_zenon_offbeat_ciclo_de_5", 132, 41, "dorico", dict(estilo="offbeat", frase=4, remates=False, gate=0.35,
                                                             swing=0.12, movimiento=0.0, ciclo=5, filtro=True,
                                                             filtro_min=30, filtro_max=85, filtro_ciclo=32,
                                                             filtro_forma="ola", filtro_nota=0.3), "zenon", "4x4"),
    ("07_zenon_trote_con_swing", 132, 41, "frigio", dict(estilo="trote", frase=4, gate=0.45, swing=0.15, zenon=0.6,
                                                          caida=5, filtro=True, filtro_min=30, filtro_max=80,
                                                          filtro_ciclo=16, filtro_forma="ola", filtro_nota=0.3), "zenon", "4x4"),
    ("08_swampy_halftime", 140, 43, "frigio", dict(estilo="dub", frase=4, slide=0.6, swing=0.1, movimiento=0.6,
                                                    filtro=True, filtro_min=20, filtro_max=75, filtro_ciclo=8,
                                                    filtro_forma="ola", filtro_nota=1.0), "swampy", "halftime"),
    ("09_swampy_halftime_que_evoluciona", 140, 43, "frigio", dict(estilo="dub", frase=2, slide=0.5, swing=0.15,
                                                              movimiento=0.7, evolucion=0.6, mutar_cada=2,
                                                              filtro=True, filtro_min=15, filtro_max=80, filtro_ciclo=4,
                                                              filtro_forma="ola", filtro_nota=1.0), "swampy", "halftime"),
]

# corte base (Hz) sin CC, octavas que abre la envolvente, decaimiento (s), resonancia (0-1), FM, sub
SONIDOS = {
    "psy": dict(corte=170, abre=3.6, decae=0.045, res=0.35, fm=0.0, sub=0.35),
    "zenon": dict(corte=140, abre=3.0, decae=0.07, res=0.55, fm=0.25, sub=0.45),
    "swampy": dict(corte=None, abre=2.4, decae=0.12, res=0.85, fm=0.6, sub=0.5, glide=0.07),
}


def eventos(bpm, nota_larga, escala, ajustes, compases):
    cfg = cargar(RAIZ / "config.ejemplo.toml")
    cfg["entrada"].update(canal_disparo=2, nota_maxima=0)
    cfg["forma"]["variacion"] = 0.0
    tonica = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][nota_larga % 12]
    cfg["musica"].update(tonica=tonica, escala=escala, armonia="libre", seguir_pads=False)
    for s in cfg["secuencia"]:
        s["activa"] = False
    cfg["pads"]["activo"] = False
    cfg["bajo"].update(activo=True, salida="BAJO", disparo=0, octava=-1, gate=0.7, slide=0.0, movimiento=0.25)
    cfg["bajo"].update(ajustes)
    out = []
    m = Motor(normalizar(cfg), lambda sal, tipo, canal, nota, vel: out.append((sal, m.tick, tipo, nota, vel)))
    m.start()
    m.nota_on(1, nota_larga)
    for _ in range(compases * 96):
        m.reloj()
    m.stop()
    return [e for e in out if e[0] == "BAJO"]


def sinte_bajo(evs, n, bpm, sonido):
    """Mono: frecuencia, amplitud, corte y fuerza por muestra; después un filtro resonante."""
    tick = 60 / bpm / 24
    s = SONIDOS[sonido]
    freq = np.zeros(n)
    amp = np.zeros(n)
    env = np.zeros(n)
    bend = np.zeros(n)
    cc = np.full(n, -1.0)
    abiertas = {}
    notas = []
    for _, t, tipo, a, b in evs:
        k = int(max(t, 0) * tick * SR)
        if tipo == "note_on":
            abiertas[a] = (k, b)
        elif tipo == "note_off" and a in abiertas:
            k0, v = abiertas.pop(a)
            notas.append((k0, k, a, v))
        elif tipo == "pitchwheel" and k < n:
            bend[k:] = a / 8192 * 12   # bend_rango del ejemplo = 12 (el de fábrica)
        elif tipo == "control_change" and a == 74 and k < n:
            cc[k:] = b
    for k0, k1, nota, v in sorted(notas):
        k1 = min(max(k1, k0 + 200), n)
        if k0 >= n:
            continue
        largo = k1 - k0
        freq[k0:k1] = 440 * 2 ** ((nota - 69) / 12)
        t = np.arange(largo) / SR
        a = np.minimum(1, np.arange(largo) / 25) * np.minimum(1, (largo - np.arange(largo)) / 60)
        amp[k0:k1] = a * (0.55 + 0.45 * v / 127)
        env[k0:k1] = np.exp(-t / s["decae"]) * (0.6 + 0.4 * v / 127)
    # Mantener la frecuencia entre notas (para que no salte la fase).
    idx = np.where(freq > 0, np.arange(n), 0)
    np.maximum.accumulate(idx, out=idx)
    freq = np.where(freq > 0, freq, freq[idx])
    freq[freq == 0] = 55.0
    if s.get("glide"):
        # Portamento: la frecuencia se desliza (filtro de un polo sobre el logaritmo).
        a = math.exp(-1 / (s["glide"] * SR))
        lf = np.log2(freq).tolist()
        y = lf[0]
        for i in range(n):
            y = a * y + (1 - a) * lf[i]
            lf[i] = y
        freq = 2 ** np.array(lf)
    f = freq * 2 ** (bend / 12)
    fase = np.cumsum(f / SR)
    sierra = 2 * (fase % 1.0) - 1
    cuadrada = np.sign(np.sin(2 * np.pi * fase))
    sub = np.sin(np.pi * fase)  # una octava abajo
    if s["fm"]:
        mod = np.sin(2 * np.pi * fase * 2.0) * s["fm"] * (0.3 + 2.5 * env)
        osc = 0.6 * np.sin(2 * np.pi * fase + mod * 3) + 0.4 * sierra
    else:
        osc = 0.7 * sierra + 0.3 * cuadrada
    # Corte: base (o el CC 74 del motor) abierto por la envolvente de cada nota.
    if s["corte"] is None:
        base = np.where(cc >= 0, 60 * 2 ** (cc / 127 * 6.5), 200)
    else:
        base = np.full(n, float(s["corte"]))
    corte = np.minimum(base * 2 ** (s["abre"] * env), 9000)
    y = _svf(osc, corte, s["res"])
    return np.tanh(1.6 * (y * amp + s["sub"] * sub * amp * 0.6))


def _svf(x, corte, res):
    """Filtro de estado variable (pasa bajos), corte por muestra."""
    g = np.tan(np.pi * np.minimum(corte, SR * 0.45) / SR)
    k = 2 - 2 * res * 0.97
    a1 = 1 / (1 + g * (g + k))
    ic1 = ic2 = 0.0
    out = np.empty_like(x)
    xs, gs, a1s = x.tolist(), g.tolist(), a1.tolist()
    for i in range(len(xs)):
        gi = gs[i]
        v1 = a1s[i] * (ic1 + gi * (xs[i] - ic2))
        v2 = ic2 + gi * v1
        ic1 = 2 * v1 - ic1
        ic2 = 2 * v2 - ic2
        out[i] = v2
    return out


def bateria(n, bpm, forma="4x4"):
    out, duck = np.zeros(n), np.ones(n)
    negra = 60 / bpm
    t = np.arange(int(0.25 * SR)) / SR
    cuerpo = np.sin(2 * np.pi * np.cumsum(46 + 230 * np.exp(-t * 32)) / SR) * np.exp(-t * 10)
    clic = np.random.default_rng(2).uniform(-1, 1, len(t)) * np.exp(-t * 600) * 0.5
    bombo = np.tanh((cuerpo + clic) * 2.4)
    th = np.arange(int(0.06 * SR)) / SR
    ruido = np.random.default_rng(1).uniform(-1, 1, len(th))
    hat = np.diff(ruido, prepend=0) * np.exp(-th * 60)
    caida = np.concatenate([np.linspace(0.0, 1, int(0.1 * SR)), np.ones(1)])
    tp = np.arange(int(0.2 * SR)) / SR
    caja = (np.random.default_rng(4).uniform(-1, 1, len(tp)) * np.exp(-tp * 25) * 0.6
            + np.sin(2 * np.pi * 190 * tp) * np.exp(-tp * 30) * 0.5)
    k = 0
    while k * negra * SR < n:
        a = int(k * negra * SR)
        if forma == "4x4" or k % 4 == 0:
            out[a:a + len(bombo)] += bombo[: n - a]
            duck[a:a + len(caida)] = np.minimum(duck[a:a + len(caida)], caida[: n - a])
        if forma == "halftime" and k % 4 == 2:   # halftime: bombo en el 1, caja en el 3
            out[a:a + len(caja)] += caja[: n - a] * 0.7
        h = int((k + 0.5) * negra * SR)
        if h < n:
            out[h:h + len(hat)] += hat[: n - h] * 0.25
        k += 1
    return out, duck


def render(ejemplo, carpeta, compases):
    nombre, bpm, nota_larga, escala, ajustes, sonido, forma = ejemplo
    evs = eventos(bpm, nota_larga, escala, ajustes, compases)
    n = int((compases * 4 * 60 / bpm + 0.5) * SR)
    b = sinte_bajo(evs, n, bpm, sonido)
    bat, duck = bateria(n, bpm, forma)
    mezcla = b * duck * 0.55 + bat * 0.5
    mezcla /= max(1e-9, np.max(np.abs(mezcla))) / 0.9
    wav = Path(carpeta) / f"{nombre}.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mezcla * 32767).astype("<i2").tobytes())
    if shutil.which("ffmpeg"):
        mp3 = wav.with_suffix(".mp3")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-b:a", "192k", str(mp3)], check=True)
        wav.unlink()
        return mp3
    return wav


def main():
    carpeta = Path(sys.argv[1] if len(sys.argv) > 1 else "bajos")
    compases = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    carpeta.mkdir(parents=True, exist_ok=True)
    for ej in EJEMPLOS:
        print(render(ej, carpeta, compases))


if __name__ == "__main__":
    main()
