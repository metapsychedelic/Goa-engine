"""Huella sonora: que un cambio en la app no cambie lo que suena.

Corre el motor en escenarios fijos (el ejemplo completo, el modo canción con una
plantilla y cada estilo de secuencia y sus figuras), graba cada mensaje MIDI que
sale (tick, salida, tipo, canal, nota o CC, valor) y lo compara con la huella
guardada. Si cambia una sola nota, falla y dice dónde.

  python3 -m pruebas.huella_sonora            comparar
  python3 -m pruebas.huella_sonora --grabar   guardar la huella actual (solo cuando
                                              el cambio de sonido es a propósito)
"""

import copy
import gzip
import json
import random
import sys
import tomllib
from pathlib import Path

from goa import generos, plantillas
from goa.config import normalizar
from goa.motor import Motor

RAIZ = Path(__file__).resolve().parent.parent
HUELLA = Path(__file__).parent / "datos" / "huella_sonora.json.gz"


def ejemplo(todo=False):
    with open(RAIZ / "config.ejemplo.toml", "rb") as f:
        cfg = normalizar(tomllib.load(f))
    if todo:   # todos los motores sonando a la vez
        for motor in ("pads", "bajo", "dialogo", "fx", "texturas"):
            if motor in cfg and "activo" in cfg[motor]:
                cfg[motor]["activo"] = True
        for s in cfg["secuencia"]:
            s["activa"] = True
    return cfg


def correr(cfg, compases):
    random.seed(1234)  # por si algún motor usa el azar del sistema
    eventos = []
    ref = {}
    m = Motor(cfg, lambda sal, tipo, canal, n, v: eventos.append([ref["m"].tick if "m" in ref else -1, sal, tipo, canal, n, v]))
    ref["m"] = m
    m.start()
    for tick in range(compases * 96):
        m.reloj()
        if tick % 96 == 1:   # como la Circuit: cada motor con su nota larga (si se soltó)
            for c in sorted(m.disparos):
                if m.disparos[c].raiz is None:
                    m.nota_on(c, 41)
    m.stop()
    return eventos


def escenarios():
    e = {}
    e["ejemplo"] = (ejemplo(), 32)
    e["todos_los_motores"] = (normalizar(ejemplo(True)), 32)
    can = ejemplo(True)
    can["parte"] = plantillas.partes_de("template1")
    can["cancion"]["activa"] = True
    e["cancion_template1"] = (normalizar(can), 96)
    for estilo in ("rolling", "galope", "arpegio3", "acido", "psy_chill", "euclidiano", "largas", "ambient", "clasico", "psytrance"):
        figuras = {"clasico": ("auto", "pedal", "ciclo", "acordes"),
                   "psytrance": ("auto", "riff", "rafaga", "octavas", "arpegio", "pulsos", "espacio", "mantra",
                                 "tresillo", "descenso", "puntillo", "melodia")}.get(estilo, (None,))
        for figura in figuras:
            c = ejemplo()
            for i, s in enumerate(c["secuencia"]):
                s["activa"] = i == 0
            c["secuencia"][0].update(estilo=estilo, seed="huella", mutacion=0.3, mutar_cada=2)
            if estilo in generos.POSICION_NECESARIA:   # como lo pone la app al elegir el estilo
                c["secuencia"][0]["posicion"] = generos.POSICION_NECESARIA[estilo]
            if figura:
                c["secuencia"][0]["figura"] = figura
            e[f"sec_{estilo}{'_' + figura if figura else ''}"] = (normalizar(c), 8)
    for g in generos.ORDEN:
        e[f"genero_{g}"] = (normalizar(generos.aplicar(ejemplo(True), g)), 16)
    return e


def main():
    grabar = "--grabar" in sys.argv
    actual = {nombre: correr(cfg, compases) for nombre, (cfg, compases) in escenarios().items()}
    if grabar:
        HUELLA.write_bytes(gzip.compress(json.dumps(actual).encode()))
        print(f"Huella guardada: {len(actual)} escenarios, {sum(len(v) for v in actual.values())} mensajes MIDI")
        return
    guardada = json.loads(gzip.decompress(HUELLA.read_bytes()))
    todo = True
    for nombre in sorted(set(guardada) | set(actual)):
        a, g = actual.get(nombre), guardada.get(nombre)
        if a == g:
            print(f"OK    {nombre} ({len(a)} mensajes)")
            continue
        todo = False
        if a is None or g is None:
            print(f"ERROR {nombre}: {'falta en la huella' if g is None else 'ya no existe'}")
            continue
        i = next((k for k, (x, y) in enumerate(zip(a, g)) if x != y), min(len(a), len(g)))
        print(f"ERROR {nombre}: cambia en el mensaje {i} de {len(g)} (ahora {len(a)})")
        print(f"        antes: {g[i] if i < len(g) else '—'}")
        print(f"        ahora: {a[i] if i < len(a) else '—'}")
    print("\nEl sonido no cambió" if todo else "\nEL SONIDO CAMBIÓ")
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
