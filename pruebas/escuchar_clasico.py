"""Escuchar el estilo «Goa clásico» sin hardware: corre el motor de verdad y renderiza
bombo, hi-hats, el bajo del motor y la secuencia con un lead Goa (dos sierras, filtro
que se cierra, delay ping-pong de 3/16).

  python3 -m pruebas.escuchar_clasico carpeta/ [compases]

Deja un .mp3 por ejemplo (o .wav si no hay ffmpeg).
"""

import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt

from goa.config import cargar
from goa.motor import Motor
from pruebas.simular import RAIZ

SR = 44100
BPM = 145

# nombre, tónica (nota larga), escala, ajustes de la secuencia, progresión de los pads (o None)
EJEMPLOS = [
    ("01_pedal_frase2", 44, "frigio", dict(figura="pedal", frase=2, remate=0.5, seed="PEDAL-1"), None),
    ("02_pedal_frase4_remate", 44, "frigio", dict(figura="pedal", frase=4, remate=0.8, seed="B7"), None),
    ("03_ciclo3_octavas", 44, "frigio", dict(figura="ciclo", ciclo=3, registro=3, frase=2, remate=0.6, seed="OCT-3",
                                             octava=1), None),
    ("04_ciclo6_polimetrico", 46, "frigio_dominante", dict(figura="ciclo", ciclo=6, registro=2, frase=4, remate=0.5,
                                                            seed="D9", octava=1), None),
    ("05_acordes_progresion", 45, "frigio", dict(figura="acordes", frase=4, remate=0.7, seed="E2", octava=1),
     "i_bVI_bVII_v"),
    ("06_auto_mutando", 41, "frigio", dict(figura="auto", frase=4, remate=0.6, seed="GOA-1995", mutacion=0.25,
                                           mutar_cada=4), None),
    ("07_pedal_respuestas_distintas", 44, "frigio", dict(figura="pedal", frase=4, remate=0.8, seed="B7", variar=1.0),
     None),
    ("08_ciclo_respuestas_y_mutacion", 44, "frigio", dict(figura="ciclo", ciclo=6, registro=2, frase=4, remate=0.6,
                                                          seed="MUTA-1", octava=1, variar=0.7, mutacion=0.4,
                                                          mutar_cada=8), None),
]


def eventos(nota_larga, escala, ajustes, progresion, compases):
    cfg = cargar(RAIZ / "config.ejemplo.toml")
    cfg["entrada"].update(canal_disparo=2, nota_maxima=0)
    tonica = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][nota_larga % 12]
    cfg["musica"].update(tonica=tonica, escala=escala, armonia="guiada" if progresion else "libre", seguir_pads=bool(progresion))
    s = cfg["secuencia"][0]
    s.update(disparo=0, estilo="clasico", posicion="todos", salida="LEAD", gate=0.6, velocidad=100, acento=118,
             octava=0, filtro=False, mutacion=0.0, densidad=1.0, slide=0.0, acentos=0.0, saltos=0.0, largas=0.0,
             semitono=0.0, swing=0.0, repeticion=0.0)
    s.update(ajustes)
    for otra in cfg["secuencia"][1:]:
        otra["activa"] = False
    cfg["bajo"].update(activo=True, salida="BAJO", disparo=0, estilo="rolling", octava=-1)
    if progresion:
        cfg["pads"].update(activo=True, suenan=False, salida="PADS", disparo=0, progresion=progresion,
                           cambia_cada=2, azar=False, variacion=0.0)
    out = []
    m = Motor(cfg, lambda sal, tipo, canal, nota, vel: out.append((sal, m.tick, tipo, nota, vel)))
    m.start()
    m.nota_on(1, nota_larga)
    for _ in range(compases * 96):
        m.reloj()
    m.stop()
    return out


def notas(evs, salida):
    tick = 60 / BPM / 24
    abiertas, res, ultima = {}, [], None
    for sal, t, tipo, nota, vel in evs:
        if sal != salida:
            continue
        t = max(t, 0) * tick
        if tipo == "note_on":
            # Empieza con otra sonando: ligado (un sinte en legato desliza desde la anterior).
            abiertas[nota] = (t, vel, ultima if abiertas else None)
            ultima = nota
        elif tipo == "note_off" and nota in abiertas:
            ini, v, desde = abiertas.pop(nota)
            res.append((ini, t, nota, v, desde))
    return sorted(res)


def curva_bend(evs, salida, n, rango):
    """Pitch bend de una salida como semitonos por muestra (escalones de un pulso)."""
    tick = 60 / BPM / 24
    curva = np.zeros(n)
    for sal, t, tipo, valor, _ in evs:
        if sal == salida and tipo == "pitchwheel":
            a = int(max(t, 0) * tick * SR)
            if a < n:
                curva[a:] = valor / 8191 * rango
    return curva


def _sierra(freq, n, fase=0.0):
    f = (fase + np.cumsum(np.full(n, freq / SR))) % 1.0
    return 2 * f - 1


def _sierra_var(freqs, fase=0.0):
    f = (fase + np.cumsum(freqs / SR)) % 1.0
    return 2 * f - 1


def lead(lista, n, bend=None):
    """Dos sierras desafinadas por canal; el filtro se cierra en cada nota (mezcla
    entre una versión brillante y una oscura) y la fuerza abre más."""
    izq, der = np.zeros(n), np.zeros(n)
    claro, oscuro = butter(2, 5200, fs=SR, output="sos"), butter(2, 650, fs=SR, output="sos")
    for ini, fin, nota, vel, desde in lista:
        a = int(ini * SR)
        largo = max(int((fin - ini) * SR), 200)
        cola = int(0.03 * SR)
        k = min(n - a, largo + cola)
        if k <= 0:
            continue
        f = 440 * 2 ** ((nota - 69) / 12)
        t = np.arange(k) / SR
        amp = np.where(np.arange(k) < largo, 1.0, np.exp(-(np.arange(k) - largo) / (0.01 * SR)))
        amp *= np.minimum(1, np.arange(k) / 40)
        env = np.exp(-t / (0.05 + 0.08 * vel / 127)) * (0.5 + 0.5 * vel / 127)
        curva = np.ones(k)
        if desde is not None and desde != nota:   # glide de 60 ms desde la nota anterior
            g = min(k, int(0.06 * SR))
            curva[:g] = 2 ** ((desde - nota) / 12 * (1 - np.linspace(0, 1, g)))
            env *= 0.5
        if bend is not None:
            curva = curva * 2 ** (bend[a:a + k] / 12)
        for canal, des in ((izq, -0.08), (der, 0.08)):
            osc = 0.5 * _sierra_var(f * 2 ** (des / 12) * curva) + 0.5 * _sierra_var(f * 2 ** (-des / 24) * curva, 0.3)
            y = sosfilt(oscuro, osc) * (1 - env) + sosfilt(claro, osc) * env
            canal[a:a + k] += y * amp * (vel / 127) * 0.32
    # Delay ping-pong de 3/16 con realimentación y algo oscuro.
    retardo = int(60 / BPM / 4 * 3 * SR)
    oscurecer = butter(1, 2500, fs=SR, output="sos")
    wl, wr = np.zeros(n), np.zeros(n)
    eco_l, eco_r = sosfilt(oscurecer, der) * 0.4, sosfilt(oscurecer, izq) * 0.4
    for rep in range(4):
        d = retardo * (rep + 1)
        if d >= n:
            break
        g = 0.55 ** rep
        (wl if rep % 2 == 0 else wr)[d:] += (eco_l if rep % 2 == 0 else eco_r)[:n - d] * g
    return izq + wl, der + wr


def bajo(lista, n):
    out = np.zeros(n)
    lp = butter(2, 380, fs=SR, output="sos")
    for ini, fin, nota, vel, _ in lista:
        a = int(ini * SR)
        k = min(n - a, int((fin - ini) * SR) + 80)
        if k <= 0:
            continue
        f = 440 * 2 ** ((nota - 69) / 12)
        t = np.arange(k) / SR
        osc = sosfilt(lp, _sierra(f, k) * (0.7 + 0.6 * np.exp(-t / 0.03)))
        env = np.minimum(1, np.arange(k) / 30) * np.minimum(1, (k - np.arange(k)) / 80)
        out[a:a + k] += osc * env * (vel / 127) * 0.9
    return out


def bateria(n):
    out, duck = np.zeros(n), np.ones(n)
    negra = 60 / BPM
    t = np.arange(int(0.25 * SR)) / SR
    cuerpo = np.sin(2 * np.pi * np.cumsum(48 + 230 * np.exp(-t * 30)) / SR) * np.exp(-t * 9)
    clic = np.random.default_rng(2).uniform(-1, 1, len(t)) * np.exp(-t * 500) * 0.5
    bombo = np.tanh((cuerpo + clic) * 2.2)
    th = np.arange(int(0.09 * SR)) / SR
    ruido = np.random.default_rng(1).uniform(-1, 1, len(th))
    hp = butter(2, 7000, btype="high", fs=SR, output="sos")
    abierto = sosfilt(hp, ruido) * np.exp(-th * 30)
    cerrado = sosfilt(hp, ruido)[: int(0.03 * SR)] * np.exp(-th[: int(0.03 * SR)] * 120)
    caida = np.concatenate([np.linspace(0.25, 1, int(0.12 * SR)), np.ones(1)])
    k = 0
    while k * negra * SR < n:
        a = int(k * negra * SR)
        out[a:a + len(bombo)] += bombo[: n - a]
        duck[a:a + len(caida)] = np.minimum(duck[a:a + len(caida)], caida[: n - a])
        for j, golpe, g in ((2, abierto, 0.32), (1, cerrado, 0.12), (3, cerrado, 0.15)):
            h = int((k + j / 4) * negra * SR)
            if h < n:
                out[h:h + len(golpe)] += golpe[: n - h] * g
        k += 1
    return out, duck


def render(nombre, nota_larga, escala, ajustes, progresion, compases, carpeta):
    evs = eventos(nota_larga, escala, ajustes, progresion, compases)
    dur = compases * 4 * 60 / BPM + 1.0
    n = int(dur * SR)
    tambores, duck = bateria(n)
    li, ld = lead(notas(evs, "LEAD"), n, curva_bend(evs, "LEAD", n, ajustes.get("bend_rango", 2)))
    b = bajo(notas(evs, "BAJO"), n) * duck
    li, ld = li * (0.55 + 0.45 * duck), ld * (0.55 + 0.45 * duck)
    mezcla = np.stack([tambores * 0.75 + b * 0.75 + li * 3.0, tambores * 0.75 + b * 0.75 + ld * 3.0], axis=1)
    mezcla = np.tanh(mezcla * 1.1) * 0.85
    wav = carpeta / f"{nombre}.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mezcla * 32767).astype(np.int16).tobytes())
    if shutil.which("ffmpeg"):
        mp3 = wav.with_suffix(".mp3")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "192k", str(mp3)], check=True)
        wav.unlink()
        return mp3
    return wav


def main():
    carpeta = Path(sys.argv[1] if len(sys.argv) > 1 else "ejemplos_clasico")
    compases = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    carpeta.mkdir(parents=True, exist_ok=True)
    for ej in EJEMPLOS:
        print(render(*ej[:5], compases, carpeta))


if __name__ == "__main__":
    main()
