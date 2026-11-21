"""Guardar y abrir proyectos por la app de verdad: guardar varias veces, autoguardado,
aviso de cambios sin guardar, no pisar otro proyecto sin querer.

  python3 -m pruebas.proyectos
"""

import json
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from goa.config import cargar, normalizar
from goa.motor import Motor
from goa.web import Contexto, crear_servidor

from .app import PuertosFalsos
from .fabrica import ok

RAIZ = Path(__file__).resolve().parent.parent
PUERTO = 18432


def post(ruta, datos=None):
    pedido = urllib.request.Request(f"http://127.0.0.1:{PUERTO}{ruta}", data=json.dumps(datos or {}).encode(),
                                    headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(pedido) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def get(ruta):
    return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PUERTO}{ruta}").read())


def cambiar(**secuencia):
    cfg = get("/api/config")
    cfg["secuencia"][0].update(secuencia)
    return post("/api/config", cfg)


def main():
    todo = True
    carpeta = Path(tempfile.mkdtemp())
    ruta = carpeta / "config.toml"
    shutil.copy(RAIZ / "config.ejemplo.toml", ruta)
    config = normalizar(cargar(ruta))
    candado = threading.RLock()
    ctx = Contexto(Motor(config, lambda *a: None), PuertosFalsos([]), candado, str(ruta), config)
    crear_servidor(ctx, PUERTO)
    archivo = lambda n: carpeta / "proyectos" / f"{n}.toml"

    print("Guardar")
    todo &= ok(post("/api/proyecto/guardar", {"nombre": "Mi Tema", "nuevo": True})[0] == 200, "guardar uno nuevo")
    cambiar(octava=2)
    ctx.esperar_guardado()
    todo &= ok(post("/api/proyecto/guardar", {"nombre": "Mi Tema"})[0] == 200, "guardar otra vez el mismo (antes fallaba)")
    todo &= ok(cargar(archivo("mi-tema"))["secuencia"][0]["octava"] == 2, "el archivo tiene el cambio")
    todo &= ok((carpeta / "proyectos" / "mi-tema.toml.respaldo").exists(), "la versión anterior queda de respaldo")
    todo &= ok(get("/api/estado")["proyecto_al_dia"], "la app ve que está guardado")

    print("\nAutoguardado")
    cambiar(octava=-1)
    ctx.esperar_guardado()
    todo &= ok(cargar(archivo("mi-tema"))["secuencia"][0]["octava"] == -1, "un cambio queda solo en el proyecto")
    todo &= ok(get("/api/estado")["proyecto_al_dia"], "y la app lo ve guardado")
    cfg = get("/api/config"); cfg["app"]["autoguardar"] = False; post("/api/config", cfg)
    ctx.esperar_guardado()
    cambiar(octava=1)
    ctx.esperar_guardado()
    todo &= ok(cargar(archivo("mi-tema"))["secuencia"][0]["octava"] == -1, "sin autoguardado, el proyecto no cambia solo")
    todo &= ok(not get("/api/estado")["proyecto_al_dia"], "y la app avisa: cambios sin guardar")
    post("/api/proyecto/guardar", {"nombre": "Mi Tema"})
    todo &= ok(cargar(archivo("mi-tema"))["secuencia"][0]["octava"] == 1 and get("/api/estado")["proyecto_al_dia"],
               "«Guardar» lo deja al día")

    print("\nGuardar como")
    codigo, r = post("/api/proyecto/guardar", {"nombre": "Otro", "nuevo": True})
    todo &= ok(codigo == 200, "guardar como uno nuevo")
    codigo, r = post("/api/proyecto/guardar", {"nombre": "Mi Tema", "nuevo": True})
    todo &= ok(codigo == 409 and r.get("existe"), "no pisa otro proyecto sin preguntar")
    todo &= ok(post("/api/proyecto/guardar", {"nombre": "Mi Tema", "nuevo": True, "sobrescribir": True})[0] == 200,
               "con permiso, lo reemplaza")
    nombres = [p["nombre"] for p in get("/api/proyectos")["proyectos"]]
    (carpeta / "proyectos" / ".config-abc.toml").write_text("")   # un temporal que quedó de un corte de luz
    todo &= ok(sorted(nombres) == ["Mi Tema", "Otro"] and len(get("/api/proyectos")["proyectos"]) == 2,
               f"la lista no muestra temporales ni respaldos ({nombres})")

    print("\nAbrir")
    cfg = get("/api/config"); cfg["app"]["autoguardar"] = True; cfg["secuencia"][0]["octava"] = 3
    post("/api/config", cfg)
    post("/api/proyecto/abrir", {"nombre": "otro"})   # enseguida, con el autoguardado en camino
    todo &= ok(get("/api/config")["app"]["proyecto"] == "Otro" and get("/api/estado")["proyecto_al_dia"], "abrir deja al día")
    ctx.esperar_guardado()
    todo &= ok(cargar(archivo("mi-tema"))["secuencia"][0]["octava"] == 3 and cargar(archivo("otro"))["secuencia"][0]["octava"] != 3,
               "el último cambio queda en su proyecto, y no en el que abriste")
    contexto2 = Contexto(Motor(ctx.config, lambda *a: None), PuertosFalsos([]), candado, str(ruta), ctx.config)
    todo &= ok(contexto2.proyecto_al_dia, "al arrancar, sabe si lo de la tarjeta es el proyecto")

    print("\n" + ("Todo bien" if todo else "HAY FALLAS"))
    shutil.rmtree(carpeta, ignore_errors=True)
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
