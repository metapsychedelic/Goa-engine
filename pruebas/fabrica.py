"""Restaurar ajustes de fábrica (todos los motores) y Deshacer general, por la app de verdad.

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

    print("\nFábrica en todos los motores (config)")
    from goa.config import ESQUEMA_SECCIONES as E, fabrica_motor
    cfg = normalizar(cargar(RAIZ / "config.ejemplo.toml"))
    cfg["pads"].update(salida="MC-101", canal=6, seed="P-9", activo=True, progresion="i_bVI_bII", voces=6, pulso=3)
    cfg["dialogo"].update(seed="CR-77", escucha=9, evolucion=0.9, forma="pregunta" if "pregunta" in E["dialogo"]["forma"][3] else cfg["dialogo"]["forma"])
    cfg["llamada"].update(salida="FM-1", canal=8, golpes=9, oscuridad=0.1)
    cfg["fx"].update(cc_corte=23, locura=1.0, seed="FX-9")
    cfg["texturas"].update(cc=71, densidad=0.9, seed="TX-9")
    for motor, secciones, propios in (("pads", ("pads",), dict(salida="MC-101", canal=6, seed="P-9", activo=True)),
                                       ("dialogo", ("dialogo", "llamada"), dict(seed="CR-77", escucha=9, salida="FM-1", canal=8)),
                                       ("fx", ("fx",), dict(cc_corte=23, seed="FX-9")),
                                       ("texturas", ("texturas",), dict(cc=71, seed="TX-9"))):
        n = normalizar(fabrica_motor(cfg, motor))
        bien = True
        for sec in secciones:
            for k, (_, defecto, _, _) in E[sec].items():
                esperado = propios.get(k, cfg[sec][k]) if k in propios or k in ("salida", "canal", "programa", "disparo", "genero", "activo", "suenan", "escucha", "seed", "cc", "cc_corte", "filtro_cc") else defecto
                bien &= n[sec][k] == esperado
        otras = [s for s in E if s not in secciones and s not in ("respuesta",) and n[s] != cfg[s]]
        todo &= ok(bien and not otras and n["secuencia"] == cfg["secuencia"], f"{motor}: de fábrica, conserva destino y seed, no toca lo demás")

    print("\nPor la app: fábrica y deshacer general")
    carpeta = Path(tempfile.mkdtemp())
    ruta = carpeta / "config.toml"
    shutil.copy(RAIZ / "config.ejemplo.toml", ruta)
    config = normalizar(cargar(ruta))
    config["entrada"].update(canal_disparo=2, nota_maxima=0)
    config["secuencia"] = [dict(s, disparo=0) for s in config["secuencia"]]
    config["secuencia"][0].update(activa=True, mutacion=1.0, mutar_cada=1, mutacion_ritmo=0.5, swing=0.2, octava=1)
    config["bajo"].update(disparo=0, activo=True, evolucion=1.0, mutar_cada=1, slide=0.6, estilo="rolling")
    config["pads"].update(voces=6, variacion=0.7, activo=True)
    config["dialogo"].update(activo=True, evolucion=1.0, mutar_cada=1, espacio=2)
    config["llamada"].update(golpes=6, oscuridad=0.2)
    config["fx"].update(locura=0.9)
    config["texturas"].update(densidad=0.9, largas=0.2)
    config = normalizar(config)
    candado = threading.RLock()
    motor = Motor(config, lambda *a: None)
    ctx = Contexto(motor, PuertosFalsos([]), candado, str(ruta), config)
    servidor = crear_servidor(ctx, PUERTO)
    with candado:
        motor.start()
        motor.nota_on(1, 45)
    compases(ctx, 12)
    todo &= ok(post("/api/deshacer")[0] == 400, "sin cambios no hay nada que deshacer")

    # Fábrica de una secuencia y deshacer (vuelve también lo mutado)
    antes_cfg = json.loads(json.dumps(ctx.config["secuencia"][0]))
    antes_patron = json.loads(json.dumps(motor.secuencias[0].patron))
    base_patron = Motor(normalizar(dict(config, secuencia=[dict(config["secuencia"][0], mutacion=0.0)])),
                        lambda *a: None).secuencias[0].patron
    todo &= ok(antes_patron != base_patron, "la secuencia mutó antes de restaurar")
    codigo, r = post("/api/fabrica", {"motor": "secuencia", "fila": 0})
    todo &= ok(codigo == 200 and ctx.config["secuencia"][0]["mutacion"] == 0.0 and motor.secuencias[0].patron == base_patron,
               "secuencia de fábrica y sin lo mutado")
    codigo, r = post("/api/deshacer")
    todo &= ok(codigo == 200 and ctx.config["secuencia"][0] == antes_cfg, f"deshacer devuelve sus ajustes ({r.get('deshecho')})")
    todo &= ok(json.loads(json.dumps(motor.secuencias[0].patron)) == antes_patron, "y el patrón mutado que sonaba")
    todo &= ok(ctx.esperar_guardado() and cargar(ruta)["secuencia"][0]["mutacion"] == 1.0, "queda guardado en la tarjeta (en otro hilo)")
    codigo, _ = post("/api/secuencia/fabrica", {"fila": 0})
    todo &= ok(codigo == 200 and ctx.config["secuencia"][0]["mutacion"] == 0.0, "la ruta vieja /api/secuencia/fabrica sigue andando")
    post("/api/deshacer")

    # Bajo: fábrica sin aviso especial; deshacer general lo devuelve
    antes_cfg = json.loads(json.dumps(ctx.config["bajo"]))
    antes_patron = dict(motor.bajo.patron)
    todo &= ok(antes_patron != motor.bajo.base, "el bajo mutó antes de restaurar")
    codigo, r = post("/api/fabrica", {"motor": "bajo"})
    compases(ctx, 1)
    todo &= ok(codigo == 200 and ctx.config["bajo"]["evolucion"] == 0.0 and ctx.config["bajo"]["activo"]
               and motor.bajo.patron == motor.bajo.base, "bajo de fábrica, sigue prendido y sin lo mutado")
    codigo, r = post("/api/deshacer")
    todo &= ok(codigo == 200 and ctx.config["bajo"] == antes_cfg and (motor.cola_bajo or motor.bajo).patron == antes_patron,
               "deshacer devuelve el bajo y su patrón mutado")

    # Pads, diálogo, FX y texturas
    for m in ("pads", "dialogo", "fx", "texturas"):
        antes = json.loads(json.dumps(ctx.config))
        codigo, _ = post("/api/fabrica", {"motor": m})
        cambio_real = any(ctx.config[s] != antes[s] for s in ("pads", "dialogo", "llamada", "respuesta", "fx", "texturas"))
        compases(ctx, 1)
        codigo2, r = post("/api/deshacer")
        todo &= ok(cambio_real and codigo == 200 and codigo2 == 200 and all(ctx.config[s] == antes[s] for s in ("pads", "dialogo", "llamada", "respuesta", "fx", "texturas")),
                   f"{m}: fábrica y deshacer ({r.get('deshecho')})")

    # El diálogo de fábrica vuelve a sus frases sin lo mutado
    from goa.dialogo import Voz
    d = motor.dialogo
    todo &= ok(d.llamada.orden != Voz(d.cfg_voces[0], "llamada", d.seed).orden or d.respuesta.orden != Voz(d.cfg_voces[1], "respuesta", d.seed).orden,
               "el diálogo mutó")
    post("/api/fabrica", {"motor": "dialogo"})
    d = motor.dialogo
    todo &= ok(d.llamada.orden == Voz(d.cfg_voces[0], "llamada", d.seed).orden and d.respuesta.orden == Voz(d.cfg_voces[1], "respuesta", d.seed).orden,
               "diálogo de fábrica: frases de su seed, sin lo mutado")
    post("/api/deshacer")
    # Un paso que no cambiaba nada se salta
    post("/api/config", json.loads(json.dumps(ctx.config)))

    # Deshacer general: pasos de controles, uno a la vez
    import time
    base = json.loads(json.dumps(ctx.config))
    def cambio(seccion, clave, valor, fila=None):
        nueva = json.loads(json.dumps(ctx.config))
        (nueva[seccion][fila] if fila is not None else nueva[seccion])[clave] = valor
        return post("/api/config", nueva)
    cambio("bajo", "slide", 0.1)
    cambio("bajo", "slide", 0.2)        # el mismo deslizador, seguido: un solo paso
    time.sleep(1.6)
    cambio("pads", "voces", 5)
    time.sleep(1.6)
    cambio("secuencia", "octava", -1, fila=1)
    codigo, r = post("/api/deshacer")
    todo &= ok(codigo == 200 and ctx.config["secuencia"][1]["octava"] == base["secuencia"][1]["octava"] and ctx.config["pads"]["voces"] == 5,
               f"deshace solo el último paso ({r['deshecho']})")
    codigo, r = post("/api/deshacer")
    todo &= ok(ctx.config["pads"]["voces"] == base["pads"]["voces"] and ctx.config["bajo"]["slide"] == 0.2, f"luego el anterior ({r['deshecho']})")
    codigo, r = post("/api/deshacer")
    todo &= ok(ctx.config["bajo"]["slide"] == base["bajo"]["slide"], f"el deslizador movido seguido vuelve de una vez ({r['deshecho']})")
    with candado:
        ctx.motor.aplicar_config(ctx.config)
    # La energía y el piloto no son pasos ni se pierden al deshacer
    time.sleep(1.6)
    cambio("bajo", "acentos", 0.9)
    post("/api/energia", {"energia": 0.83})
    codigo, r = post("/api/deshacer")
    todo &= ok(ctx.config["bajo"]["acentos"] == base["bajo"]["acentos"] and ctx.config["forma"]["energia"] == 0.83,
               "deshacer no mueve la energía")
    # Un clip lanzado después en esa fila: no lo pisa
    time.sleep(1.6)
    cambio("secuencia", "swing", 0.4, fila=0)
    post("/api/clip/guardar", {"fila": 0, "nombre": "c"})
    nueva = json.loads(json.dumps(ctx.config)); nueva["clip"][-1]["swing"] = 0.1
    with candado:
        ctx.config = normalizar(dict(ctx.config, clip=nueva["clip"]))
    post("/api/lanzar", {"fila": 0, "clip": len(ctx.config["clip"]) - 1})
    codigo, r = post("/api/deshacer")
    todo &= ok(codigo == 400 and "cambió después" in r["error"] and ctx.config["secuencia"][0]["swing"] == 0.1,
               "si un clip cambió esa secuencia después, no la pisa y avisa")
    # Abrir un proyecto limpia la historia
    time.sleep(1.6)
    cambio("bajo", "acentos", 0.5)
    post("/api/proyecto/guardar", {"nombre": "p1"})
    post("/api/proyecto/abrir", {"nombre": "p1"})
    todo &= ok(post("/api/deshacer")[0] == 400, "abrir un proyecto empieza la historia de cero")
    estado = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PUERTO}/api/estado").read())
    todo &= ok(estado.get("deshacer") == 0, "el estado dice cuántos pasos se pueden deshacer")
    codigo, r = post("/api/fabrica", {"motor": "secuencia", "fila": 99})
    todo &= ok(codigo == 400, "una fila que no existe da error")
    codigo, r = post("/api/fabrica", {"motor": "nada"})
    todo &= ok(codigo == 400, "un motor que no existe da error")

    servidor.shutdown() if hasattr(servidor, "shutdown") else None
    print("\nTodo bien" if todo else "\nHAY FALLAS")
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
