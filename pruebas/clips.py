"""Clips de secuencia por la app: guardar con o sin variante, renombrar, guardar encima,
borrar y deshacer el borrado, y que la app sirva sus archivos comprimidos y guardables.

  python3 -m pruebas.clips
"""

import gzip
import re
import shutil
import tempfile
import threading
import urllib.request
from pathlib import Path

from goa.config import cargar, normalizar
from goa.motor import Motor
from goa.web import Contexto, crear_servidor

from .app import PuertosFalsos
from .fabrica import ok
from .proyectos import get, post
from . import proyectos

RAIZ = Path(__file__).resolve().parent.parent
PUERTO = 18437


def cambiar(**secuencia):
    cfg = get("/api/config")
    cfg["secuencia"][0].update(secuencia)
    return post("/api/config", cfg)


def main():
    proyectos.PUERTO = PUERTO
    todo = True
    carpeta = Path(tempfile.mkdtemp())
    ruta = carpeta / "config.toml"
    shutil.copy(RAIZ / "config.ejemplo.toml", ruta)
    config = normalizar(cargar(ruta))
    config["clip"] = []
    ctx = Contexto(Motor(config, lambda *a: None), PuertosFalsos([]), threading.RLock(), str(ruta), config)
    crear_servidor(ctx, PUERTO)

    print("Guardar")
    cambiar(estilo="acido", seed="AAAA", octava=1)
    post("/api/clip/guardar", {"fila": 0, "nombre": "Con seed"})
    cambiar(estilo="psytrance", seed="BBBB", octava=2)
    post("/api/clip/guardar", {"fila": 0, "nombre": "Sin seed", "variante": False})
    clips = get("/api/config")["clip"]
    todo &= ok([c["nombre"] for c in clips] == ["Con seed", "Sin seed"], "dos clips")
    todo &= ok(clips[0]["con_variante"] is True and clips[1]["con_variante"] is False, "uno con variante y otro sin")

    print("\nTocar")
    cambiar(seed="CCCC")
    post("/api/lanzar", {"fila": 0, "clip": 1})
    s = get("/api/config")["secuencia"][0]
    todo &= ok(s["estilo"] == "psytrance" and s["octava"] == 2 and s["seed"] == "CCCC", f"sin variante: trae el estilo y los ajustes, deja la seed ({s['seed']})")
    todo &= ok("con_variante" not in s, "la secuencia no hereda la marca del clip")
    post("/api/lanzar", {"fila": 0, "clip": 0})
    s = get("/api/config")["secuencia"][0]
    todo &= ok(s["estilo"] == "acido" and s["seed"] == "AAAA", "con variante: trae también la seed")

    print("\nRenombrar y guardar encima")
    post("/api/clip/renombrar", {"indice": 0, "nombre": "  Ácido intro  "})
    todo &= ok(get("/api/config")["clip"][0]["nombre"] == "Ácido intro", "renombrado (sin espacios de más)")
    cambiar(octava=-2)
    post("/api/clip/guardar", {"fila": 0, "indice": 0})
    c = get("/api/config")["clip"]
    todo &= ok(len(c) == 2 and c[0]["nombre"] == "Ácido intro" and c[0]["octava"] == -2, "guardar lo que suena encima: mismo nombre, valores nuevos")

    print("\nBorrar y deshacer")
    antes = get("/api/config")["clip"][0]
    post("/api/clip/borrar", {"indice": 0})
    todo &= ok([x["nombre"] for x in get("/api/config")["clip"]] == ["Sin seed"], "borrado")
    post("/api/clip/restaurar", {"indice": 0, "clip": antes})
    todo &= ok(get("/api/config")["clip"] == [antes, c[1]], "deshacer lo vuelve a su lugar, igual que estaba")

    print("\nArchivos de la app")
    base = f"http://localhost:{PUERTO}"
    html = urllib.request.urlopen(base + "/").read().decode()
    rutas = re.findall(r'(?:src|href)="(/app/[^"]+)"', html)
    todo &= ok(len(rutas) == 6 and all("?v=" in r for r in rutas), "el HTML pide cada archivo con su marca ?v=")
    pedido = urllib.request.Request(base + rutas[1], headers={"Accept-Encoding": "gzip"})
    r = urllib.request.urlopen(pedido)
    cuerpo = gzip.decompress(r.read())
    todo &= ok(r.headers["Content-Encoding"] == "gzip" and "immutable" in r.headers["Cache-Control"], "llega comprimido y guardable")
    todo &= ok(cuerpo == (RAIZ / "goa" / "web" / rutas[1][5:].split("?")[0]).read_bytes(), "y descomprimido es el archivo")
    r = urllib.request.urlopen(base + rutas[1].split("?")[0])
    todo &= ok(r.headers["Cache-Control"] == "no-store" and r.headers.get("Content-Encoding") is None, "sin marca ni gzip: tal cual y sin guardar")
    try:
        urllib.request.urlopen(base + "/app/../web.py")
        todo &= ok(False, "no se sale de goa/web")
    except urllib.error.HTTPError as e:
        todo &= ok(e.code == 404, "no se sale de goa/web (404)")

    print("\n" + ("Todo bien" if todo else "HAY FALLAS"))
    shutil.rmtree(carpeta, ignore_errors=True)
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
