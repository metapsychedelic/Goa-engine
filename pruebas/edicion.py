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

    print("\nCopiar y pegar desde la línea de tiempo")
    cfg = get("/api/config"); cfg["cancion"]["activa"] = False
    cfg["parte"] = [{"nombre": n, "compases": 16, "escena": -1, "energia": 0.5, "energia_fin": 0.5, "entrada": "suave"} for n in ("A", "B", "C", "D")]
    post("/api/config", cfg)
    for i, (bajo, octava) in enumerate([(True, 2), (False, -1), (False, 0)]):
        post("/api/editar", {"parte": i})
        c = get("/api/config"); c["bajo"]["activo"] = bajo; c["bajo"]["octava"] = octava if "octava" in c["bajo"] else c["bajo"].get("octava"); c["secuencia"][0]["octava"] = octava
        post("/api/config", c)
        post("/api/editar/listo")
    cfg = get("/api/config")
    esc = lambda c, i: datos(c, c["parte"][i]["escena"])
    antes_sec = esc(cfg, 1)["secuencia"][0]["octava"]
    codigo, r = post("/api/parte/copiar", {"desde": 0, "hacia": [1, 2], "motores": ["bajo"]})
    cfg = get("/api/config")
    todo &= ok(codigo == 200 and esc(cfg, 1)["bajo"]["activo"] and esc(cfg, 2)["bajo"]["activo"], "pegar el bajo de A en B y C")
    todo &= ok(esc(cfg, 1)["secuencia"][0]["octava"] == antes_sec == -1, "solo el bajo: la secuencia de B queda como estaba")
    codigo, r = post("/api/parte/copiar", {"desde": 0, "hacia": 3, "motores": ["sec0"]})
    cfg = get("/api/config")
    todo &= ok(cfg["parte"][3]["escena"] >= 0 and esc(cfg, 3)["secuencia"][0]["octava"] == 2, "pegar en una parte sin escena le crea una")
    post("/api/parte/apagar", {"parte": 0, "motor": "bajo"})
    todo &= ok(not esc(get("/api/config"), 0)["bajo"]["activo"], "«que no suene aquí» apaga el bajo en A")
    cfg = get("/api/config"); cfg["parte"][3]["escena"] = cfg["parte"][1]["escena"]; post("/api/config", cfg)
    codigo, r = post("/api/parte/copiar", {"desde": 2, "hacia": [3], "motores": ["sec0"]})
    todo &= ok(r.get("compartidas") == ["B"], f"avisa si la escena la comparte otra parte {r.get('compartidas')}")
    post("/api/editar", {"parte": 2})
    post("/api/parte/copiar", {"desde": 0, "hacia": [2], "motores": ["sec0"]})
    cfg = get("/api/config")
    todo &= ok(cfg["secuencia"][0]["octava"] == 2 and bool(get("/api/estado")["editando"]), "pegar en la parte que editas: suena al tiro y sigue la edición")
    codigo, r = post("/api/parte/copiar", {"desde": 0, "hacia": [1], "motores": ["nada"]})
    todo &= ok(codigo == 400, "un motor que no existe da error")

    print("\nEditor de secuencia: copiar lo que suena y ver lo que toca")
    post("/api/editar/listo")
    c = get("/api/config"); c["secuencia"][0]["octava"] = 3; post("/api/config", c)
    codigo, r = post("/api/parte/copiar", {"desde": -1, "hacia": [1], "motores": ["sec0"]})
    cfg = get("/api/config")
    todo &= ok(codigo == 200 and esc(cfg, 1)["secuencia"][0]["octava"] == 3, "copiar la secuencia de lo que suena ahora a otra parte")
    p = get("/api/patron?sec=0")
    todo &= ok(p["corriendo"] is False and p["ahora"] is None and p["largo"] >= 7, f"con el motor quieto no marca paso {p}")
    todo &= ok(get("/api/patron?sec=99")["activa"] is False, "una secuencia que no existe no se cae")

    print("\n" + ("Todo bien" if todo else "HAY FALLAS"))
    shutil.rmtree(carpeta, ignore_errors=True)
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
