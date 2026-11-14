"""App web: la Pi sirve una página para controlar el motor desde el celular."""

import json
import logging
import re
import threading
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__, forma, generos
from .config import (MAX_CLIPS, ConfigError, cargar, clip_de, clip_de_dialogo, guardar, normalizar, salidas,
                     secciones_de_clip)
from .motor import Motor

log = logging.getLogger("goa")
PAGINA = Path(__file__).parent / "web" / "index.html"
MAX_CUERPO = 1024 * 1024  # la configuración trae las escenas


class Contexto:
    """Lo que la app necesita del proceso principal."""

    def __init__(self, motor, puertos, candado, ruta_config, config):
        self.motor = motor
        self.puertos = puertos
        self.candado = candado
        self.ruta_config = ruta_config
        self.config = config
        self.entrada = None  # nombre de la entrada conectada, o None
        self.entradas_disponibles = []  # puertos de entrada que ve la Pi


def _carpeta_proyectos(ctx):
    carpeta = Path(ctx.ruta_config).resolve().parent / "proyectos"
    carpeta.mkdir(exist_ok=True)
    return carpeta


def ruta_proyecto(ctx, nombre):
    """Archivo de un proyecto: el nombre se reduce a letras, números y guiones,
    así nunca puede apuntar fuera de la carpeta de proyectos."""
    limpio = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode().lower()
    limpio = re.sub(r"[^a-z0-9_-]+", "-", limpio).strip("-")[:40]
    if not limpio:
        raise ValueError("Escribe un nombre para el proyecto")
    return _carpeta_proyectos(ctx) / f"{limpio}.toml"


def listar_proyectos(ctx):
    proyectos = []
    for ruta in sorted(_carpeta_proyectos(ctx).glob("*.toml"), key=lambda r: r.stat().st_mtime, reverse=True):
        try:
            nombre = cargar(ruta)["app"]["proyecto"] or ruta.stem
        except (ConfigError, OSError, ValueError):
            continue
        proyectos.append({"nombre": nombre, "archivo": ruta.stem})
    return proyectos


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
                    estado["entradas"] = sorted({_nombre_corto(n) for n in ctx.entradas_disponibles
                                                 if "through" not in n.lower()})
                self._json(estado)
            elif self.path == "/api/config":
                with ctx.candado:
                    self._json(ctx.config)
            elif self.path == "/api/proyectos":
                self._json({"proyectos": listar_proyectos(ctx)})
            else:
                self._json({"error": "no existe"}, 404)

        def do_POST(self):
            largo = int(self.headers.get("Content-Length") or 0)
            if largo > MAX_CUERPO:
                self._json({"error": "demasiado grande"}, 413)
                return
            try:
                datos = json.loads(self.rfile.read(largo) or b"{}") if largo else {}
            except ValueError:
                self._json({"error": "JSON inválido"}, 400)
                return
            rutas = {
                "/api/panico": self._panico,
                "/api/config": self._config,
                "/api/genero": self._genero,
                "/api/clip/guardar": self._clip_guardar,
                "/api/clip/borrar": self._clip_borrar,
                "/api/lanzar": self._lanzar,
                "/api/detener": self._detener,
                "/api/dialogo/clip/guardar": self._dialogo_clip_guardar,
                "/api/dialogo/clip/borrar": self._dialogo_clip_borrar,
                "/api/dialogo/lanzar": self._dialogo_lanzar,
                "/api/dialogo/detener": self._dialogo_detener,
                "/api/escena/guardar": self._escena_guardar,
                "/api/escena/lanzar": self._escena_lanzar,
                "/api/escena/borrar": self._escena_borrar,
                "/api/energia": self._energia,
                "/api/piloto": self._piloto,
                "/api/proyecto/guardar": self._proyecto_guardar,
                "/api/proyecto/abrir": self._proyecto_abrir,
                "/api/proyecto/borrar": self._proyecto_borrar,
            }
            accion = rutas.get(self.path)
            if accion is None:
                self._json({"error": "no existe"}, 404)
                return
            try:
                accion(datos)
            except FileNotFoundError:
                self._json({"error": "No existe ese proyecto"}, 404)
            except (ConfigError, ValueError, KeyError, IndexError, TypeError, OSError) as e:
                self._json({"error": str(e)}, 400)

        # --- Acciones ---

        def _panico(self, datos):
            with ctx.candado:
                ctx.motor.apagar_todo()
                ctx.puertos.panico()
            self._json({"ok": True})

        def _aplicar(self, nueva):
            """Aplica y guarda una configuración ya normalizada. Llamar con el candado tomado."""
            ctx.motor.aplicar_config(nueva)
            ctx.config = nueva
            ctx.puertos.cambiar_salidas(salidas(nueva))
            return self._guardar_activa()

        def _guardar_activa(self):
            try:
                guardar(ctx.ruta_config, ctx.config)
                return None
            except OSError as e:
                log.warning("No pude guardar la configuración: %s", e)
                return "Aplicado, pero no se pudo guardar en la tarjeta"

        def _responder(self, aviso=None, **extra):
            self._json(dict({"ok": True, "aviso": aviso} if aviso else {"ok": True}, **extra))

        def _config(self, datos):
            if isinstance(datos, dict):
                with ctx.candado:
                    # Las escenas solo cambian con sus botones: una configuración vieja no las borra.
                    datos = dict(datos, escena=ctx.config["escena"])
            nueva = normalizar(datos)
            Motor(nueva, lambda *a: None)  # valida antes de tocar nada
            with ctx.candado:
                aviso = self._aplicar(nueva)
            self._responder(aviso)

        def _genero(self, datos):
            """Aplica un perfil de género: a todo, o a un motor (parte = pads, dialogo o secuencia + indice)."""
            genero = str(datos.get("genero", ""))
            with ctx.candado:
                nueva = normalizar(generos.aplicar(ctx.config, genero, datos.get("parte"), datos.get("indice")))
                Motor(nueva, lambda *a: None)  # valida antes de tocar nada
                aviso = self._aplicar(nueva)
            self._responder(aviso, genero=genero)

        def _clip_guardar(self, datos):
            with ctx.candado:
                fila = int(datos["fila"])
                secuencia = ctx.config["secuencia"][fila]
                if len(ctx.config["clip"]) >= MAX_CLIPS:
                    raise ValueError(f"Máximo {MAX_CLIPS} clips")
                ctx.config["clip"].append(clip_de(secuencia, str(datos.get("nombre", ""))))
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _clip_borrar(self, datos):
            with ctx.candado:
                del ctx.config["clip"][int(datos["indice"])]
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _lanzar(self, datos):
            with ctx.candado:
                fila = int(datos["fila"])
                clip = ctx.config["clip"][int(datos["clip"])]
                fila_cfg = ctx.config["secuencia"][fila]
                nueva = dict(fila_cfg, **{k: v for k, v in clip.items() if k != "nombre"}, activa=True)
                ctx.motor.lanzar(fila, nueva, clip["nombre"])
                ctx.config["secuencia"][fila] = nueva
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _detener(self, datos):
            with ctx.candado:
                fila = int(datos["fila"])
                ctx.motor.detener(fila)
                ctx.config["secuencia"][fila]["activa"] = False
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _dialogo_clip_guardar(self, datos):
            with ctx.candado:
                if len(ctx.config["clip_dialogo"]) >= MAX_CLIPS:
                    raise ValueError(f"Máximo {MAX_CLIPS} clips de diálogo")
                ctx.config["clip_dialogo"].append(clip_de_dialogo(ctx.config, str(datos.get("nombre", ""))))
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _dialogo_clip_borrar(self, datos):
            with ctx.candado:
                del ctx.config["clip_dialogo"][int(datos["indice"])]
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _dialogo_lanzar(self, datos):
            with ctx.candado:
                clip = ctx.config["clip_dialogo"][int(datos["clip"])]
                dialogo, llamada, respuesta = secciones_de_clip(clip)
                ctx.motor.lanzar_dialogo(dialogo, llamada, respuesta, clip["nombre"])
                ctx.config.update(dialogo=dialogo, llamada=llamada, respuesta=respuesta)
                ctx.puertos.cambiar_salidas(salidas(ctx.config))
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _dialogo_detener(self, datos):
            with ctx.candado:
                ctx.motor.detener_dialogo()
                ctx.config["dialogo"]["activo"] = False
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _escena_guardar(self, datos):
            """Guarda cómo suena todo ahora como escena (nueva, o encima de `indice`)."""
            with ctx.candado:
                escenas = ctx.config["escena"]
                escena = forma.escena_de(ctx.config, str(datos.get("nombre", "")))
                indice = datos.get("indice")
                if indice is None:
                    if len(escenas) >= forma.MAX_ESCENAS:
                        raise ValueError(f"Máximo {forma.MAX_ESCENAS} escenas")
                    escenas.append(escena)
                    indice = len(escenas) - 1
                else:
                    indice = int(indice)
                    escena["nombre"] = str(datos.get("nombre") or escenas[indice]["nombre"])[:24]
                    escenas[indice] = escena
                ctx.config["forma"]["escena"] = indice
                ctx.motor.base["forma"]["escena"] = indice
                aviso = self._guardar_activa()
            self._responder(aviso, indice=indice)

        def _escena_lanzar(self, datos):
            """Pasa a una escena en los compases de transición (desde el próximo compás)."""
            with ctx.candado:
                indice = int(datos["indice"])
                escena = ctx.config["escena"][indice]
                nueva = normalizar(forma.mezclar(ctx.config, escena))
                nueva["forma"]["escena"] = indice
                compases = int(datos.get("compases") or nueva["forma"]["transicion"])
                Motor(nueva, lambda *a: None)  # valida antes de tocar nada
                ctx.motor.lanzar_escena(nueva, compases, indice)
                ctx.config = nueva
                ctx.puertos.cambiar_salidas(salidas(nueva))
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _escena_borrar(self, datos):
            with ctx.candado:
                indice = int(datos["indice"])
                del ctx.config["escena"][indice]
                actual = ctx.config["forma"]["escena"]
                ctx.config["forma"]["escena"] = -1 if actual == indice else actual - (1 if actual > indice else 0)
                ctx.motor.base["forma"]["escena"] = ctx.config["forma"]["escena"]
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _energia(self, datos):
            """Solo la energía (el control grande de Tocar): llega de a poco, sin mandar toda la configuración."""
            with ctx.candado:
                ctx.config["forma"]["energia"] = max(0.0, min(1.0, float(datos["energia"])))
                ctx.config["forma"]["piloto"] = False  # tomas el control: el piloto se apaga
                ctx.motor.aplicar_config(ctx.config)
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _piloto(self, datos):
            """Prende o apaga el piloto, cambia su duración o salta a una sección (en el próximo compás)."""
            with ctx.candado:
                f = ctx.config["forma"]
                if "activo" in datos:
                    f["piloto"] = bool(datos["activo"])
                if "duracion" in datos:
                    if datos["duracion"] not in forma.DURACIONES:
                        raise ValueError("Duración desconocida")
                    f["duracion"] = datos["duracion"]
                if datos.get("seccion"):
                    f["piloto"] = True
                    ctx.motor.saltar_seccion(str(datos["seccion"]))
                ctx.motor.aplicar_config(ctx.config)
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _proyecto_guardar(self, datos):
            nombre = str(datos.get("nombre", "")).strip()[:40]
            with ctx.candado:
                ctx.config["app"]["proyecto"] = nombre
                guardar(ruta_proyecto(ctx, nombre), ctx.config)
                aviso = self._guardar_activa()
            self._responder(aviso, proyecto=nombre)

        def _proyecto_abrir(self, datos):
            nombre = str(datos.get("nombre", "")).strip()
            nueva = cargar(ruta_proyecto(ctx, nombre))
            nueva["app"]["puerto"] = ctx.config["app"]["puerto"]  # el puerto de la app no cambia
            Motor(nueva, lambda *a: None)
            with ctx.candado:
                aviso = self._aplicar(nueva)
            self._responder(aviso, proyecto=nueva["app"]["proyecto"])

        def _proyecto_borrar(self, datos):
            ruta = ruta_proyecto(ctx, str(datos.get("nombre", "")))
            ruta.unlink()
            self._responder()

    servidor = ThreadingHTTPServer(("0.0.0.0", puerto), Manejador)
    servidor.daemon_threads = True
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    log.info("App disponible en http://goa.local:%d", puerto)
    return servidor
