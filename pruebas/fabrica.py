"""Restaurar ajustes de fábrica (secuencia y bajo) y Deshacer, por la app de verdad.

  python3 -m pruebas.fabrica
"""

import json
import shutil
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

from goa.config import ESQUEMA_SECCIONES, cargar, fabrica_bajo, normalizar
from goa.motor import Motor
from goa.web import Contexto, crear_servidor

from .app import PuertosFalsos

RAIZ = Path(__file__).resolve().parent.parent
PUERTO = 18431


def ok(cond, texto):
    print(("  ok   " if cond else "  FALLA ") + texto)
    return cond


def post(ruta, datos=None):
    pedido = urllib.request.Request(f"http://127.0.0.1:{PUERTO}{ruta}", data=json.dumps(datos or {}).encode(),
                                    headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(pedido) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def compases(ctx, n):
    with ctx.candado:
        for _ in range(96 * n):
            ctx.motor.reloj()


def main():
    todo = True

    print("Bajo de fábrica (config)")
    cfg = normalizar(cargar(RAIZ / "config.ejemplo.toml"))
    propio = dict(activo=True, salida="MC-101", canal=2, programa=7, disparo=5, genero="psytrance", seed="B-0777", filtro_cc=71)
    cfg["bajo"].update(propio, estilo="sincopado", fusas=0.7, slide=0.8, octava=-1, evolucion=0.9, filtro=True, porta=True)
    b = normalizar(dict(cfg, bajo=fabrica_bajo(cfg["bajo"])))["bajo"]
    todo &= ok(all(b[k] == v for k, v in propio.items()), "conserva salida, canal, programa, nota larga, género, seed y CC del filtro")
    fabrica = {k: v[1] for k, v in ESQUEMA_SECCIONES["bajo"].items()}
    distintos = [k for k in fabrica if k not in propio and b[k] != fabrica[k]]
    todo &= ok(not distintos, f"todo lo demás queda de fábrica {distintos or ''}")

    print("\nPor la app: restaurar y deshacer")
    carpeta = Path(tempfile.mkdtemp())
    ruta = carpeta / "config.toml"
    shutil.copy(RAIZ / "config.ejemplo.toml", ruta)
    config = normalizar(cargar(ruta))
    config["entrada"].update(canal_disparo=2, nota_maxima=0)
    config["secuencia"] = [dict(s, disparo=0) for s in config["secuencia"]]
    config["secuencia"][0].update(activa=True, mutacion=1.0, mutar_cada=1, mutacion_ritmo=0.5, swing=0.2, octava=1)
    config["bajo"].update(disparo=0, activo=True, evolucion=1.0, mutar_cada=1, slide=0.6, estilo="rolling")
    config = normalizar(config)
    candado = threading.RLock()
    motor = Motor(config, lambda *a: None)
    ctx = Contexto(motor, PuertosFalsos([]), candado, str(ruta), config)
    servidor = crear_servidor(ctx, PUERTO)
    with candado:
        motor.start()
        motor.nota_on(1, 45)
    compases(ctx, 12)

    # Secuencia
    antes_cfg = json.loads(json.dumps(ctx.config["secuencia"][0]))
    antes_patron = json.loads(json.dumps(motor.secuencias[0].patron))
    base_patron = Motor(normalizar(dict(config, secuencia=[dict(config["secuencia"][0], mutacion=0.0)])),
                        lambda *a: None).secuencias[0].patron
    todo &= ok(antes_patron != base_patron, "la secuencia mutó antes de restaurar")
    codigo, r = post("/api/secuencia/fabrica", {"fila": 0})
    todo &= ok(codigo == 200 and r.get("deshacer"), "restaura la secuencia y ofrece deshacer")
    todo &= ok(ctx.config["secuencia"][0]["mutacion"] == 0.0 and motor.secuencias[0].patron == base_patron,
               "queda de fábrica y sin lo mutado")
    codigo, r = post("/api/fabrica/deshacer")
    todo &= ok(codigo == 200, "deshacer responde bien")
    todo &= ok(ctx.config["secuencia"][0] == antes_cfg, "la secuencia vuelve a sus ajustes de antes")
    todo &= ok(json.loads(json.dumps(motor.secuencias[0].patron)) == antes_patron, "y al patrón mutado que sonaba")
    todo &= ok(cargar(ruta)["secuencia"][0]["mutacion"] == 1.0, "queda guardado en la tarjeta")
    codigo, r = post("/api/fabrica/deshacer")
    todo &= ok(codigo == 400 and "nada" in r["error"], "un segundo deshacer no hace nada")
    compases(ctx, 2)

    # Bajo
    antes_cfg = json.loads(json.dumps(ctx.config["bajo"]))
    antes_patron = dict(motor.bajo.patron)
    todo &= ok(antes_patron != motor.bajo.base, "el bajo mutó antes de restaurar")
    codigo, r = post("/api/bajo/fabrica")
    todo &= ok(codigo == 200 and r.get("deshacer"), "restaura el bajo y ofrece deshacer")
    compases(ctx, 1)  # el bajo nuevo entra en el próximo compás
    todo &= ok(ctx.config["bajo"]["evolucion"] == 0.0 and ctx.config["bajo"]["activo"], "queda de fábrica y sigue prendido")
    todo &= ok(motor.bajo.patron == motor.bajo.base, "sin lo mutado")
    codigo, r = post("/api/fabrica/deshacer")
    todo &= ok(codigo == 200 and ctx.config["bajo"] == antes_cfg, "deshacer devuelve los ajustes del bajo")
    todo &= ok((motor.cola_bajo or motor.bajo).patron == antes_patron, "y vuelve el patrón mutado que sonaba")
    compases(ctx, 1)

    # Si cambiaste algo después, deshacer no lo pisa
    post("/api/bajo/fabrica")
    nueva = json.loads(json.dumps(ctx.config))
    nueva["bajo"]["slide"] = 0.4
    codigo, _ = post("/api/config", nueva)
    codigo, r = post("/api/fabrica/deshacer")
    todo &= ok(codigo == 400 and ctx.config["bajo"]["slide"] == 0.4, "si tocaste el bajo después, deshacer no pisa tu cambio")
    # Cambios en otra parte no impiden deshacer
    post("/api/secuencia/fabrica", {"fila": 0})
    nueva = json.loads(json.dumps(ctx.config))
    nueva["bajo"]["slide"] = 0.1
    post("/api/config", nueva)
    codigo, _ = post("/api/fabrica/deshacer")
    todo &= ok(codigo == 200 and ctx.config["secuencia"][0]["mutacion"] == 1.0 and ctx.config["bajo"]["slide"] == 0.1,
               "tocar otro motor no impide deshacer ni se pierde")
    codigo, r = post("/api/secuencia/fabrica", {"fila": 99})
    todo &= ok(codigo == 400, "una fila que no existe da error")

    servidor.shutdown() if hasattr(servidor, "shutdown") else None
    print("\nTodo bien" if todo else "\nHAY FALLAS")
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
