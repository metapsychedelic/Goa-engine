"""App web: la Pi sirve una página para controlar el motor desde el celular."""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__
from .config import ConfigError, guardar, normalizar
from .motor import Motor

log = logging.getLogger("goa")
PAGINA = Path(__file__).parent / "web" / "index.html"
MAX_CUERPO = 64 * 1024


class Contexto:
    """Lo que la app necesita del proceso principal."""

    def __init__(self, motor, puertos, candado, ruta_config, config):
        self.motor = motor
        self.puertos = puertos
        self.candado = candado
        self.ruta_config = ruta_config
        self.config = config
        self.entrada = None  # nombre de la entrada conectada, o None


def _nombre_corto(nombre):
    # "FM-1:FM-1 MIDI 1 24:0" -> "FM-1" (sin los números que cambian al reconectar)
    return nombre.split(":")[0].strip()


def crear_servidor(ctx, puerto):
    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, formato, *args):
            pass

        def _json(self, datos, codigo=200):
            cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                cuerpo = PAGINA.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)
            elif self.path == "/api/estado":
                with ctx.candado:
                    estado = ctx.motor.estado()
                    estado["version"] = __version__
                    estado["entrada"] = ctx.entrada
                    estado["salidas"] = {clave: clave in ctx.puertos.abiertos for clave in ctx.puertos.salidas}
                    estado["disponibles"] = sorted({_nombre_corto(n) for n in ctx.puertos.disponibles
                                                    if "through" not in n.lower()})
                self._json(estado)
            elif self.path == "/api/config":
                with ctx.candado:
                    self._json(ctx.config)
            else:
                self._json({"error": "no existe"}, 404)

        def do_POST(self):
            largo = int(self.headers.get("Content-Length") or 0)
            if largo > MAX_CUERPO:
                self._json({"error": "demasiado grande"}, 413)
                return
            cuerpo = self.rfile.read(largo) if largo else b""
            if self.path == "/api/panico":
                with ctx.candado:
                    ctx.motor.apagar_todo()
                    ctx.puertos.panico()
                self._json({"ok": True})
            elif self.path == "/api/config":
                try:
                    nueva = normalizar(json.loads(cuerpo or b"{}"))
                    Motor(nueva, lambda *a: None)  # valida antes de tocar nada
                except (ConfigError, ValueError, KeyError) as e:
                    self._json({"error": str(e)}, 400)
                    return
                with ctx.candado:
                    ctx.motor.aplicar_config(nueva)
                    ctx.config = nueva
                    ctx.puertos.cambiar_salidas([s["salida"] for s in nueva["secuencia"]])
                    try:
                        guardar(ctx.ruta_config, nueva)
                    except OSError as e:
                        log.warning("No pude guardar la configuración: %s", e)
                        self._json({"ok": True, "aviso": "Aplicado, pero no se pudo guardar en la tarjeta"})
                        return
                self._json({"ok": True})
            else:
                self._json({"error": "no existe"}, 404)

    servidor = ThreadingHTTPServer(("0.0.0.0", puerto), Manejador)
    servidor.daemon_threads = True
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    log.info("App disponible en http://goa.local:%d", puerto)
    return servidor
