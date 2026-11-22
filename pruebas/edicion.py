"""Modo edición de escenas, por la app de verdad: entrar, que cada cambio quede en la
escena, descartar, listo, y que lanzar otra escena termine la edición.

  python3 -m pruebas.edicion
"""

import json
import shutil
import tempfile
import threading
from pathlib import Path

from goa.config import cargar, normalizar
from goa.motor import Motor
from goa.web import Contexto, crear_servidor

from .app import PuertosFalsos
from .fabrica import ok
from .proyectos import get, post
from . import proyectos

RAIZ = Path(__file__).resolve().parent.parent
PUERTO = 18433


def datos(cfg, i):
    return json.loads(cfg["escena"][i]["datos"])


def cambiar(**secuencia):
    cfg = get("/api/config")
    cfg["secuencia"][0].update(secuencia)
    return post("/api/config", cfg)


def main():
    proyectos.PUERTO = PUERTO   # post/get de pruebas.proyectos apuntan a este servidor
    todo = True
    carpeta = Path(tempfile.mkdtemp())
    ruta = carpeta / "config.toml"
    shutil.copy(RAIZ / "config.ejemplo.toml", ruta)
    config = normalizar(cargar(ruta))
    ctx = Contexto(Motor(config, lambda *a: None), PuertosFalsos([]), threading.RLock(), str(ruta), config)
    crear_servidor(ctx, PUERTO)

    print("Preparar dos escenas")
    cambiar(octava=0)
    post("/api/escena/guardar", {"nombre": "Intro"})
    cambiar(octava=1)
    post("/api/escena/guardar", {"nombre": "Drop"})
    todo &= ok(len(get("/api/config")["escena"]) == 2, "dos escenas")

    print("\nEditar")
    codigo, r = post("/api/editar", {"escena": 0})
    todo &= ok(codigo == 200 and bool(r.get("original")), "entrar a editar la Intro (devuelve cómo estaba)")
    cfg = get("/api/config")
    todo &= ok(cfg["secuencia"][0]["octava"] == 0, "suena la Intro")
    e = get("/api/estado")["editando"]
    todo &= ok(bool(e) and e["escena"] == 0 and e["nombre"] == "Intro" and not e["cambios"], f"la app sabe que edita la Intro, sin cambios {e}")
    cambiar(octava=-1)
    cfg = get("/api/config")
    todo &= ok(datos(cfg, 0)["secuencia"][0]["octava"] == -1, "un cambio queda solo en la escena, sin «Guardar»")
    todo &= ok(datos(cfg, 1)["secuencia"][0]["octava"] == 1, "la otra escena no se toca")
    todo &= ok(get("/api/estado")["editando"]["cambios"], "y la app ve que hay cambios")

    print("\nDescartar")
    post("/api/editar/descartar")
    cfg = get("/api/config")
    todo &= ok(datos(cfg, 0)["secuencia"][0]["octava"] == 0 and cfg["secuencia"][0]["octava"] == 0,
               "la escena vuelve a como estaba, y suena así")
    todo &= ok(get("/api/estado")["editando"] is None, "y sale de la edición")
    cambiar(octava=2)
    todo &= ok(datos(get("/api/config"), 0)["secuencia"][0]["octava"] == 0, "fuera de la edición, mover algo no toca la escena")

    print("\nListo")
    post("/api/editar", {"escena": 1})
    cambiar(octava=-2)
    post("/api/editar/listo")
    cambiar(octava=0)
    cfg = get("/api/config")
    todo &= ok(datos(cfg, 1)["secuencia"][0]["octava"] == -2, "«Listo» deja lo editado, y lo de después ya no entra")

    print("\nLanzar otra escena termina la edición")
    post("/api/editar", {"escena": 1})
    post("/api/escena/lanzar", {"indice": 0, "compases": 1})
    todo &= ok(get("/api/estado")["editando"] is None, "lanzar la Intro sale de editar el Drop")
    todo &= ok(datos(get("/api/config"), 1)["secuencia"][0]["octava"] == -2, "y el Drop no se pisa con la Intro")

    print("\nPartes")
    cfg = get("/api/config")
    cfg["parte"] = [{"nombre": "A", "compases": 16, "escena": -1, "energia": 0.5, "energia_fin": 0.5, "entrada": "suave"}]
    post("/api/config", cfg)
    codigo, _ = post("/api/editar", {"parte": 0})
    cfg = get("/api/config")
    todo &= ok(codigo == 200 and cfg["parte"][0]["escena"] == 2 and get("/api/estado")["editando"]["escena"] == 2,
               "editar una parte sin escena le crea una y la edita")
    post("/api/editar/listo")
    cfg = get("/api/config"); cfg["cancion"]["activa"] = True; post("/api/config", cfg)
    codigo, r = post("/api/editar", {"escena": 0})
    todo &= ok(codigo == 400 and "canción" in r.get("error", ""), "con el modo canción prendido no se edita")

    print("\n" + ("Todo bien" if todo else "HAY FALLAS"))
    shutil.rmtree(carpeta, ignore_errors=True)
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
