"""App web: la Pi sirve una página para controlar el motor desde el celular."""

import copy
import gzip
import hashlib
import json
import logging
import os
import random
import re
import threading
import time
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__, actualizar, copia, forma, fuentes, generador, generos, historia, plantillas
from .config import (MAX_CLIPS, MAX_PARTES, MOTORES_FABRICA, ConfigError, a_toml, cargar, LISTA_CLIPS, clip_aplicado, clip_de, clip_de_dialogo, clip_de_motor, dialogo_con_clip, con_clip_de_motor, fabrica_motor, fabrica_secuencia, guardar, normalizar, salidas,
                     secciones_de_clip)
from .motor import Motor

log = logging.getLogger("goa")
PAGINA = Path(__file__).parent / "web" / "index.html"


def _marca(ruta):
    """Cambia cada vez que cambia el archivo (para que el navegador pida el nuevo)."""
    try:
        return format(ruta.stat().st_mtime_ns // 1000, "x")
    except OSError:
        return "0"


_GZIP = {}


def _comprimido(cuerpo):
    clave = hashlib.sha1(cuerpo).digest()
    if clave not in _GZIP:
        if len(_GZIP) > 32:
            _GZIP.clear()
        _GZIP[clave] = gzip.compress(cuerpo, 6)
    return _GZIP[clave]
MAX_CUERPO = 1024 * 1024  # la configuración trae las escenas


INICIO = time.time()   # cuándo arrancó este proceso: la app nota así que el motor se reinició
_CAMBIANDO = threading.Lock()   # una sola actualización a la vez


GUARDAR_JUNTA = 0.3  # segundos que espera el guardado para juntar cambios seguidos


def hilo_secundario():
    """El hilo que llama esto (la app, el guardado) deja la prioridad de tiempo real del
    servicio y baja un poco: así nunca le quita la CPU al hilo del reloj MIDI."""
    try:
        os.sched_setscheduler(0, os.SCHED_OTHER, os.sched_param(0))   # 0 = este hilo (Linux)
        os.setpriority(os.PRIO_PROCESS, 0, 5)
    except (AttributeError, OSError, PermissionError):
        pass


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
        self.version_base = 0  # la última parte de la canción que la app ya conoce
        self.historia = []     # pasos que se pueden deshacer (ver goa/historia.py)
        self.control = None    # el nanoKONTROL2 (goa/control.py), si está prendido
        self.teclado = None    # el teclado de la MicroFreak (goa/teclado.py)
        self.version_externa = 0  # sube cuando el control cambia algo: la app se recarga
        # Guardar en la tarjeta va en un hilo aparte, fuera del candado: escribir el
        # archivo tardaba más que aplicar el cambio y el reloj tenía que esperarlo.
        self.error_guardado = None
        self._pedido = threading.Event()
        self._guardado = threading.Condition()
        self._escritos = 0     # cuántas veces terminó de escribir (para esperar_guardado)
        self._pedidos = 0
        # ¿El archivo del proyecto abierto tiene lo mismo que suena? (la app avisa si no)
        self.proyecto_al_dia = _proyecto_igual(self, config)
        # Escena en edición: {"escena": índice, "original": la escena como estaba al entrar}.
        # Mientras dura, cada cambio queda en esa escena (ver sincronizar_edicion).
        self.editando = None
        threading.Thread(target=self._guardador, name="guardar-config", daemon=True).start()

    def sincronizar_tocado(self):
        """Lo que grabaste en el Tocado pasa a la configuración (tocado.loop): así queda en
        la tarjeta, en el proyecto y en las escenas que guardes. Llamar con el candado."""
        t = self.motor.tocado
        if not t.cambio_loop:
            return False
        t.cambio_loop = False
        texto = t.serializar()
        t.texto = texto
        if self.config["tocado"].get("loop", "") == texto:
            return False
        self.config = dict(self.config, tocado=dict(self.config["tocado"], loop=texto))
        self.motor.base["tocado"] = dict(self.motor.base["tocado"], loop=texto)
        self.version_externa += 1
        self.pedir_guardado()
        return True

    def pedir_guardado(self):
        """Pide guardar la configuración activa. No espera: devuelve el último error (o None)."""
        with self._guardado:
            self._pedidos += 1
        self.proyecto_al_dia = False   # (lo vuelve a poner el autoguardado o «Guardar»)
        self._pedido.set()
        return self.error_guardado

    def _guardador(self):
        hilo_secundario()
        while True:
            self._pedido.wait()
            time.sleep(GUARDAR_JUNTA)  # cambios seguidos (un deslizador) se guardan una vez
            self._pedido.clear()
            with self._guardado:
                hasta = self._pedidos
            self._escribir()
            with self._guardado:
                self._escritos = max(self._escritos, hasta)
                self._guardado.notify_all()

    def _escribir(self):
        for _ in range(3):
            try:
                # Sin el candado: ctx.config se reemplaza en cada cambio (no se modifica
                # adentro), y lo poco que se toca en el lugar (energía, piloto, listas de la
                # biblioteca) pide otro guardado después, así que el archivo queda al día.
                cfg = self.config
                texto = a_toml(cfg)   # una vez: va a la configuración y al proyecto
                guardar(self.ruta_config, cfg, texto)
                self._autoguardar(cfg, texto)
                if self.error_guardado:
                    log.info("Configuración guardada otra vez")
                self.error_guardado = None
                return
            except RuntimeError:
                continue  # cambió justo mientras la leía: otra vuelta
            except OSError as e:
                log.warning("No pude guardar la configuración: %s", e)
                self.error_guardado = "Aplicado, pero no se pudo guardar en la tarjeta"
                return

    def sincronizar_edicion(self):
        """Modo edición: lo que suena se copia en la escena que estás editando (con el
        candado, en cada cambio). Así no hay que acordarse de «Guardar lo que suena»."""
        ed = self.editando
        if ed is None:
            return
        escenas = self.config["escena"]
        i = ed["escena"]
        if i >= len(escenas) or self.config["cancion"]["activa"]:
            self.editando = None
            return
        nueva = forma.escena_de(self.config, escenas[i]["nombre"], escenas[i])
        if nueva["datos"] == escenas[i]["datos"] and nueva["energia"] == escenas[i]["energia"] and nueva["armonia_propia"] == escenas[i]["armonia_propia"]:
            return
        lista = list(escenas)
        lista[i] = nueva
        self.config = dict(self.config, escena=lista)
        self.motor.base["escena"] = copy.deepcopy(lista)

    def estado_edicion(self):
        ed = self.editando
        if ed is None or ed["escena"] >= len(self.config["escena"]):
            return None
        e = self.config["escena"][ed["escena"]]
        return {"escena": ed["escena"], "nombre": e["nombre"],
                "cambios": e["datos"] != ed["original"]["datos"] or e["energia"] != ed["original"]["energia"]}

    def _autoguardar(self, cfg, texto=None):
        """Con un proyecto abierto y el autoguardado prendido, el cambio queda también en
        el archivo del proyecto (escritura atómica, la versión anterior como .respaldo)."""
        app = cfg.get("app", {})
        if not (app.get("proyecto") and app.get("autoguardar", True)):
            return
        try:
            ruta = ruta_proyecto(self, app["proyecto"])
        except ValueError:
            return
        guardar(ruta, cfg, texto)
        if cfg is self.config:   # (si cambió mientras escribía, ya hay otro guardado pedido)
            self.proyecto_al_dia = True

    def esperar_guardado(self, espera=5.0):
        """Espera a que lo pedido hasta ahora quede en la tarjeta. True si alcanzó."""
        with self._guardado:
            meta = self._pedidos
            return self._guardado.wait_for(lambda: self._escritos >= meta, espera)

    def guardar_ya(self):
        """Guarda ahora mismo, esperando (antes de actualizar o de apagar el motor)."""
        self._escribir()
        return self.error_guardado

    def sincronizar(self):
        """Modo canción: si el motor pasó a otra parte, lo que muestra la app (y se guarda)
        pasa a ser la escena de esa parte. Llamar con el candado tomado. True si cambió."""
        if self.motor.version_base == self.version_base:
            return False
        self.version_base = self.motor.version_base
        nueva = copy.deepcopy(self.motor.base)
        # Las escenas y la canción las edita la app: se quedan como están acá.
        nueva["escena"], nueva["parte"], nueva["cancion"] = self.config["escena"], self.config["parte"], self.config["cancion"]
        self.config = nueva
        return True


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


def _proyecto_igual(ctx, config):
    """Al arrancar: ¿lo que quedó en la tarjeta es igual al archivo del proyecto?"""
    nombre = config.get("app", {}).get("proyecto")
    if not nombre:
        return True
    try:
        return a_toml(cargar(ruta_proyecto(ctx, nombre))) == a_toml(config)
    except (ConfigError, OSError, ValueError):
        return False


def listar_proyectos(ctx):
    proyectos = []
    archivos = [r for r in _carpeta_proyectos(ctx).glob("*.toml") if not r.name.startswith(".")]   # sin temporales
    for ruta in sorted(archivos, key=lambda r: r.stat().st_mtime, reverse=True):
        try:
            cfg = cargar(ruta)
            nombre = cfg["app"]["proyecto"] or ruta.stem
        except (ConfigError, OSError, ValueError):
            continue
        proyectos.append({"nombre": nombre, "archivo": ruta.stem, "partes": len(cfg.get("parte", [])),
                          "compases": sum(p.get("compases", 0) for p in cfg.get("parte", []))})
    return proyectos


def _nombre_corto(nombre):
    # "FM-1:FM-1 MIDI 1 24:0" -> "FM-1" (sin los números que cambian al reconectar)
    return nombre.split(":")[0].strip()


def _nombres_cortos(nombres):
    """Nombres cortos para la app. Con dos aparatos iguales (dos dongles CH345) quedan
    «CH345 #1» y «CH345 #2», que es como el motor elige cada uno."""
    cortos = [_nombre_corto(n) for n in nombres if "through" not in n.lower() and "rtmidi" not in n.lower()]
    vistos, salida = {}, []
    for c in cortos:
        vistos[c] = vistos.get(c, 0) + 1
        salida.append(f"{c} #{vistos[c]}" if cortos.count(c) > 1 else c)
    return sorted(set(salida))


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

        def _estatico(self, cuerpo, tipo, guardable):
            """Manda un archivo de la app comprimido (si el navegador acepta gzip). guardable: con
            ?v= en la dirección el navegador lo guarda; la marca cambia cuando cambia el archivo."""
            if "gzip" in (self.headers.get("Accept-Encoding") or ""):
                cuerpo = _comprimido(cuerpo)
                comprimido = True
            else:
                comprimido = False
            self.send_response(200)
            self.send_header("Content-Type", tipo)
            self.send_header("Cache-Control", "public, max-age=31536000, immutable" if guardable else "no-store")
            if comprimido:
                self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):
            hilo_secundario()
            if self.path in ("/", "/index.html"):
                # Cada archivo de la app va con ?v=<su fecha>: el teléfono lo guarda hasta que cambie.
                html = PAGINA.read_text(encoding="utf-8")
                html = re.sub(r'(href|src)="/app/([^"?]+)"', lambda m: f'{m[1]}="/app/{m[2]}?v={_marca(PAGINA.parent / m[2])}"', html)
                self._estatico(html.encode(), "text/html; charset=utf-8", False)
            elif self.path.startswith("/app/"):
                # Los archivos de la app (estilo.css y js/*.js), solo de goa/web y sin salir de ahí.
                ruta = (PAGINA.parent / self.path[len("/app/"):].split("?")[0]).resolve()
                tipos = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8"}
                if PAGINA.parent.resolve() not in ruta.parents or ruta.suffix not in tipos or not ruta.is_file():
                    self.send_error(404)
                    return
                self._estatico(ruta.read_bytes(), tipos[ruta.suffix], "?v=" in self.path)
            elif self.path.startswith("/fuentes/"):
                datos = fuentes.leer(self.path[len("/fuentes/"):])
                if datos is None:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "font/woff2")
                self.send_header("Cache-Control", "public, max-age=31536000, immutable")
                self.send_header("Content-Length", str(len(datos)))
                self.end_headers()
                self.wfile.write(datos)
            elif self.path == "/api/estado":
                with ctx.candado:
                    if ctx.sincronizar():
                        self._guardar_activa()
                    ctx.sincronizar_tocado()
                    estado = ctx.motor.estado()
                    estado["version"] = __version__
                    estado["inicio"] = INICIO
                    estado["deshacer"] = len(ctx.historia)
                    estado["proyecto_al_dia"] = ctx.proyecto_al_dia
                    estado["editando"] = ctx.estado_edicion()
                    estado["version_externa"] = ctx.version_externa
                    if ctx.control is not None:
                        estado["control"] = ctx.control.estado()
                    if ctx.teclado is not None:
                        estado["teclado"] = ctx.teclado.estado()
                    estado["tocado"] = ctx.motor.tocado.estado_app(max(ctx.motor.tick, 0))
                    estado["entrada"] = ctx.entrada
                    estado["salidas"] = {clave: clave in ctx.puertos.abiertos for clave in ctx.puertos.salidas}
                    estado["disponibles"] = _nombres_cortos(ctx.puertos.disponibles)
                    estado["entradas"] = _nombres_cortos(ctx.entradas_disponibles)
                self._json(estado)
            elif self.path == "/api/config":
                with ctx.candado:
                    ctx.sincronizar()
                    self._json(dict(ctx.config, version_base=ctx.version_base, version_externa=ctx.version_externa))
            elif self.path.startswith("/api/patron"):
                # Lo que toca una secuencia ahora (la franja de arriba del editor).
                try:
                    fila = int(self.path.rpartition("sec=")[2])
                except ValueError:
                    fila = -1
                with ctx.candado:
                    m = ctx.motor
                    s = m.secuencias[fila] if 0 <= fila < len(m.secuencias) else None
                    huella = list(getattr(s, "huella", None) or []) if s is not None else []
                    datos = {"corriendo": bool(m.corriendo), "activa": bool(s is not None and s.activa),
                             "largo": s.largo if s is not None else 16, "pasos": huella,
                             "raiz": bool(s is not None and s.disparo in m.disparos and m.disparos[s.disparo].raiz is not None),
                             "ahora": getattr(s, "huella_paso", None) if s is not None and m.corriendo else None}
                self._json(datos)
            elif self.path.startswith("/api/clips/fabrica"):
                # Clips de fábrica (uno por género) de secuencia, bajo o pads.
                motor = self.path.rpartition("motor=")[2] or "secuencia"
                try:
                    self._json({"clips": generos.clips_fabrica(motor)})
                except ValueError:
                    self.send_error(404)
            elif self.path.startswith("/api/molde/azar"):
                # Un molde al azar (🎲): lo arma el motor, la app no repite los pesos.
                estilo = self.path.rpartition("estilo=")[2] or "goa"
                if estilo not in generador.ESTILOS_MOLDE:
                    estilo = "goa"
                self._json({"molde": generador.molde_al_azar(random.Random(), estilo), "estilo": estilo})
            elif self.path == "/api/plantillas":
                self._json({"plantillas": plantillas.lista()})
            elif self.path.startswith("/api/actualizacion"):
                try:
                    datos = actualizar.estado(buscar="buscar=1" in self.path)
                except actualizar.ErrorActualizacion as e:
                    datos = dict(actualizar.estado(buscar=False), error=str(e))
                self._json(dict(datos, servicio=actualizar.con_servicio()))
            elif self.path == "/api/proyectos":
                self._json({"proyectos": listar_proyectos(ctx)})
            else:
                self._json({"error": "no existe"}, 404)

        def do_POST(self):
            hilo_secundario()
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
                "/api/fabrica": self._fabrica,
                "/api/limpiar": self._limpiar,
                "/api/escena/restaurar": self._escena_restaurar,
                "/api/secuencia/fabrica": lambda d: self._fabrica(dict(d, motor="secuencia")),
                "/api/deshacer": self._deshacer,
                "/api/ajuste": self._ajuste,
                "/api/tocado": self._tocado,
                "/api/cc": self._cc,
                "/api/clip/guardar": self._clip_guardar,
                "/api/clip/borrar": self._clip_borrar,
                "/api/escena/armonia": self._escena_armonia,
                "/api/clip/renombrar": self._clip_renombrar,
                "/api/clip/restaurar": self._clip_restaurar,
                "/api/motor/clip/guardar": self._mclip_guardar,
                "/api/motor/clip/lanzar": self._mclip_lanzar,
                "/api/motor/clip/parar": self._mclip_parar,
                "/api/motor/clip/borrar": self._mclip_borrar,
                "/api/motor/clip/renombrar": self._mclip_renombrar,
                "/api/motor/clip/restaurar": self._mclip_restaurar,
                "/api/lanzar": self._lanzar,
                "/api/detener": self._detener,
                "/api/dialogo/clip/guardar": self._dialogo_clip_guardar,
                "/api/dialogo/clip/borrar": self._dialogo_clip_borrar,
                "/api/dialogo/lanzar": self._dialogo_lanzar,
                "/api/dialogo/detener": self._dialogo_detener,
                "/api/escena/guardar": self._escena_guardar,
                "/api/escena/lanzar": self._escena_lanzar,
                "/api/escena/borrar": self._escena_borrar,
                "/api/editar": self._editar,
                "/api/editar/listo": self._editar_listo,
                "/api/editar/descartar": self._editar_descartar,
                "/api/editar/original": self._editar_original,
                "/api/energia": self._energia,
                "/api/piloto": self._piloto,
                "/api/subida": self._subida,
                "/api/cancion": self._cancion,
                "/api/cancion/plantilla": self._cancion_plantilla,
                "/api/cancion/actualizar": self._cancion_actualizar,
                "/api/parte/nueva": self._parte_nueva,
                "/api/parte/guardar": self._parte_guardar,
                "/api/parte/escuchar": self._parte_escuchar,
                "/api/parte/copiar": self._parte_copiar,
                "/api/parte/apagar": self._parte_apagar,
                "/api/proyecto/guardar": self._proyecto_guardar,
                "/api/proyecto/abrir": self._proyecto_abrir,
                "/api/proyecto/borrar": self._proyecto_borrar,
                "/api/actualizar": self._actualizar,
                "/api/actualizar/anterior": self._actualizar_anterior,
            }
            accion = rutas.get(self.path)
            if accion is None:
                self._json({"error": "no existe"}, 404)
                return
            with ctx.candado:
                ctx.sincronizar()
            try:
                accion(datos)
                if self.headers.get("X-Goa-Control") and self.path != "/api/cc":
                    with ctx.candado:
                        ctx.version_externa += 1   # lo cambió el nanoKONTROL2: la app se recarga
            except FileNotFoundError:
                self._json({"error": "No existe ese proyecto"}, 404)
            except (ConfigError, ValueError, KeyError, IndexError, TypeError, OSError) as e:
                self._json({"error": str(e)}, 400)

        # --- Acciones ---

        def _actualizar(self, datos):
            self._cambiar_version(lambda: actualizar.actualizar(ctx.ruta_config))

        def _actualizar_anterior(self, datos):
            self._cambiar_version(lambda: actualizar.anterior(ctx.ruta_config))

        def _cambiar_version(self, cambio):
            """Actualiza (o vuelve atrás) y reinicia el motor. Sin systemd que lo vuelva a
            levantar (corriendo a mano), no lo apaga: avisa que hay que reiniciarlo."""
            if not _CAMBIANDO.acquire(blocking=False):
                raise ValueError("Ya se está actualizando")
            try:
                aviso = ctx.guardar_ya()   # que la config quede en la tarjeta antes
                if aviso:
                    raise ValueError("No se pudo guardar la configuración: no actualizo")
                res = cambio()
            except actualizar.ErrorActualizacion as e:
                _CAMBIANDO.release()
                raise ValueError(str(e)) from None
            except Exception:
                _CAMBIANDO.release()
                raise
            reinicia = res.get("cambio", True) and actualizar.con_servicio()
            self._json(dict(res, ok=True, reinicia=reinicia))
            if reinicia:
                log.info("Versión %s instalada desde la app: reinicio el motor", res["version"])
                actualizar.reiniciar()
            else:
                _CAMBIANDO.release()

        def _panico(self, datos):
            with ctx.candado:
                ctx.motor.apagar_todo()
                ctx.puertos.panico()
            self._json({"ok": True})

        def _aplicar(self, nueva, origen=None, estado=None):
            """Aplica y guarda una configuración ya normalizada. Llamar con el candado tomado.
            Con `origen`, el cambio queda en la historia y se puede deshacer."""
            previa = ctx.config
            ctx.motor.aplicar_config(nueva)
            ctx.config = nueva
            if origen:
                historia.anotar(ctx.historia, previa, nueva, origen, estado)
            ctx.puertos.cambiar_salidas(salidas(nueva))
            return self._guardar_activa()

        def _guardar_activa(self):
            ctx.sincronizar_edicion()
            return ctx.pedir_guardado()   # se escribe en otro hilo, sin el candado

        def _responder(self, aviso=None, **extra):
            self._json(dict({"ok": True, "aviso": aviso} if aviso else {"ok": True}, **extra))

        def _config(self, datos):
            if isinstance(datos, dict):
                with ctx.candado:
                    vista = datos.get("version_base")
                    if vista is not None and int(vista) != ctx.version_base:
                        # La canción pasó a otra parte mientras tocabas: lo que mandó la app es
                        # de la parte anterior y la desharía. La app se recarga y lo vuelves a hacer.
                        raise ValueError("La canción pasó a otra parte: vuelve a hacer el cambio")
                    vista = datos.get("version_externa")
                    if vista is not None and int(vista) != ctx.version_externa:
                        # Lo que mandó la app es de antes de que movieras el nanoKONTROL2: lo desharía.
                        raise ValueError("Cambió desde el nanoKONTROL2: vuelve a hacer el cambio")
                    # Las escenas solo cambian con sus botones: una configuración vieja no las borra.
                    datos = dict(datos, escena=ctx.config["escena"])
            nueva = normalizar(datos)
            Motor(nueva, lambda *a: None)  # valida antes de tocar nada
            with ctx.candado:
                aviso = self._aplicar(nueva, "config")
            self._responder(aviso)

        def _genero(self, datos):
            """Aplica un perfil de género: a todo, o a un motor (parte = pads, dialogo o secuencia + indice)."""
            genero = str(datos.get("genero", ""))
            with ctx.candado:
                nueva = generos.aplicar(ctx.config, genero, datos.get("parte"), datos.get("indice"))
                if datos.get("base"):   # desde la pestaña Armonía: también es la armonía del tema
                    nueva["armonia_tema"] = dict(nueva["musica"])
                nueva = normalizar(nueva)
                Motor(nueva, lambda *a: None)  # valida antes de tocar nada
                aviso = self._aplicar(nueva, "genero")
            self._responder(aviso, genero=genero)

        def _fabrica(self, datos):
            """Restaurar ajustes de fábrica de un motor (pads, bajo, una secuencia, diálogo, FX
            o texturas). Lo pesado (copiar, normalizar, validar) va fuera del candado."""
            motor = str(datos.get("motor", ""))
            fila = int(datos.get("fila", 0))
            for _ in range(3):
                with ctx.candado:
                    actual = ctx.config
                nueva = normalizar(fabrica_motor(actual, motor, fila))
                if not historia.cambios(actual, nueva):
                    # Ya estaba de fábrica: solo vuelve el patrón a su base, sin sumar un paso.
                    with ctx.candado:
                        ctx.motor.reiniciar_motor(motor, fila)
                    self._responder(None, igual=True)
                    return
                Motor(nueva, lambda *a: None)  # valida antes de tocar nada
                with ctx.candado:
                    if ctx.config is not actual:
                        continue  # algo cambió mientras tanto: vuelvo a armarla
                    # Una foto de lo que ya mutó, para que Deshacer lo devuelva tal cual sonaba.
                    if motor == "secuencia":
                        estado = {"secuencia": (fila, ctx.motor.estado_secuencia(fila))}
                    elif motor == "bajo":
                        estado = {"bajo": ctx.motor.estado_bajo()}
                    else:
                        estado = None
                    aviso = self._aplicar(nueva, "fabrica", estado)
                    ctx.motor.reiniciar_motor(motor, fila)   # también deshace lo que ya había mutado
                self._responder(aviso)
                return
            raise ValueError("La configuración cambió mientras restauraba: vuelve a intentarlo")

        def _ajuste(self, datos):
            """Cambia unos pocos valores sueltos ({cambios: [[sección, fila o null, clave, valor]]}),
            sin mandar toda la configuración: es lo que usa el nanoKONTROL2. Armar y normalizar
            va fuera del candado; adentro solo se aplica. Faders y perillas (`juntar`) se
            juntan en un solo paso de deshacer, como un deslizador de la app."""
            cambios = datos["cambios"]
            for _ in range(3):
                with ctx.candado:
                    actual = ctx.config
                nueva = copia.config(actual)
                for seccion, fila, clave, valor in cambios:
                    if seccion not in historia.SECCIONES and seccion != "secuencia":
                        raise ValueError(f"No se puede cambiar {seccion!r} así")
                    destino = nueva[seccion][int(fila)] if seccion == "secuencia" else nueva[seccion]
                    if clave not in destino:
                        raise ValueError(f"{seccion} no tiene {clave!r}")
                    destino[clave] = valor
                nueva = normalizar(nueva)
                with ctx.candado:
                    if ctx.config is not actual:
                        continue
                    aviso = self._aplicar(nueva, "config" if datos.get("juntar") else "ajuste")
                self._responder(aviso)
                return
            raise ValueError("La configuración cambió mientras ajustaba: vuelve a intentarlo")

        def _tocado(self, datos):
            """Grabar, parar, seguir o borrar el loop de lo que tocas en la MicroFreak."""
            with ctx.candado:
                ctx.motor.tocado.accion(str(datos.get("accion")), max(ctx.motor.tick, 0), datos.get("pasos"))
                ctx.sincronizar_tocado()
                estado = ctx.motor.tocado.estado_app(max(ctx.motor.tick, 0))
            self._responder(tocado=estado)

        def _cc(self, datos):
            """Un CC directo al sinte de un motor (volumen, filtro), sin tocar la configuración."""
            with ctx.candado:
                ctx.puertos.enviar(str(datos["salida"]), "control_change", int(datos["canal"]) - 1,
                                   max(0, min(127, int(datos["cc"]))), max(0, min(127, int(datos["valor"]))))
            self._responder()

        def _deshacer(self, datos):
            """Deshace el último paso (un cambio de controles, un género o un «fábrica»).
            Lo pesado va fuera del candado: adentro solo se toma el paso y se aplica."""
            while True:
                with ctx.candado:
                    if ctx.sincronizar():
                        self._guardar_activa()
                    if not ctx.historia:
                        raise ValueError("No hay nada que deshacer")
                    paso = ctx.historia.pop()
                    actual = ctx.config
                if historia.cambios(paso["antes"], paso["despues"]):
                    break  # un paso que no cambiaba nada (la app mandó lo mismo) se salta
            try:
                nueva, que = historia.deshacer(paso, actual)
                nueva = normalizar(nueva)
                Motor(nueva, lambda *a: None)  # valida antes de tocar nada
            except historia.Conflicto as e:
                raise ValueError(str(e)) from None
            with ctx.candado:
                if ctx.config is not actual:
                    ctx.historia.append(paso)  # cambió algo justo ahora: el paso sigue ahí
                    raise ValueError("Cambió algo mientras deshacía: vuelve a tocar Deshacer")
                aviso = self._aplicar(nueva)
                estado = paso.get("estado") or {}
                if "secuencia" in estado:
                    ctx.motor.volver_estado_secuencia(*estado["secuencia"])
                if "bajo" in estado:
                    ctx.motor.volver_estado_bajo(estado["bajo"])
                quedan = len(ctx.historia)
            self._responder(aviso, deshecho=que, quedan=quedan)

        def _cambiar_fila(self, fila, nueva):
            """Cambia una secuencia sin tocar la configuración de antes (la historia la recuerda
            tal como estaba: así sabe si un clip cambió la fila después de un paso)."""
            filas = list(ctx.config["secuencia"])
            filas[fila] = nueva
            ctx.config = dict(ctx.config, secuencia=filas)

        def _clip_guardar(self, datos):
            """{fila, nombre, variante=true, indice?}: con indice guarda lo que suena encima de ese clip."""
            with ctx.candado:
                fila = int(datos["fila"])
                secuencia = ctx.config["secuencia"][fila]
                clips = ctx.config["clip"]
                if datos.get("indice") is not None:
                    i = int(datos["indice"])
                    nombre = str(datos.get("nombre") or clips[i]["nombre"])
                    clips[i] = clip_de(secuencia, nombre, datos.get("variante", clips[i].get("con_variante", True)))
                else:
                    if len(clips) >= MAX_CLIPS:
                        raise ValueError(f"Máximo {MAX_CLIPS} clips")
                    clips.append(clip_de(secuencia, str(datos.get("nombre", "")), datos.get("variante", True)))
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _escena_armonia(self, datos):
            """{escena, propia}: la escena (parte) sigue la armonía del tema o tiene la suya. Si es la
            que suena y pasa a seguir el tema, suena la del tema desde el próximo compás."""
            with ctx.candado:
                i = int(datos["escena"])
                lista = [dict(e) for e in ctx.config["escena"]]
                lista[i]["armonia_propia"] = bool(datos.get("propia"))
                ctx.config["escena"] = lista
                ctx.motor.base["escena"] = copy.deepcopy(lista)
                if ctx.editando is not None and ctx.editando["escena"] == i:
                    ctx.editando["original"] = dict(ctx.editando["original"], armonia_propia=lista[i]["armonia_propia"])
                if not lista[i]["armonia_propia"] and ctx.config["forma"]["escena"] == i and ctx.config["musica"] != ctx.config["armonia_tema"]:
                    nueva = copia.config(ctx.config)
                    nueva["musica"] = dict(ctx.config["armonia_tema"])
                    aviso = self._aplicar(normalizar(nueva))
                else:
                    aviso = self._guardar_activa()
            self._responder(aviso)

        def _clip_borrar(self, datos):
            with ctx.candado:
                del ctx.config["clip"][int(datos["indice"])]
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _clip_renombrar(self, datos):
            with ctx.candado:
                clip = ctx.config["clip"][int(datos["indice"])]
                clip["nombre"] = str(datos.get("nombre", "")).strip()[:40] or clip["nombre"]
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _clip_restaurar(self, datos):
            """Deshacer un borrado: vuelve a poner el clip en su lugar."""
            with ctx.candado:
                clips = ctx.config["clip"]
                if len(clips) >= MAX_CLIPS:
                    raise ValueError(f"Máximo {MAX_CLIPS} clips")
                clip = normalizar(dict(ctx.config, clip=[datos["clip"]]))["clip"][0]
                clips.insert(max(0, min(len(clips), int(datos.get("indice", len(clips))))), clip)
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _lanzar(self, datos):
            with ctx.candado:
                fila = int(datos["fila"])
                if datos.get("fabrica"):
                    clip = generos.clip_fabrica("secuencia", str(datos["fabrica"]))
                else:
                    clip = ctx.config["clip"][int(datos["clip"])]
                fila_cfg = ctx.config["secuencia"][fila]
                nueva = clip_aplicado(fila_cfg, clip)
                ctx.motor.lanzar(fila, nueva, clip["nombre"])
                self._cambiar_fila(fila, nueva)
                aviso = self._guardar_activa()
            self._responder(aviso)

        # --- Clips del bajo, los pads y el diálogo: igual que los de una secuencia ---
        # Tocar uno entra en el próximo compás, prende el motor, el motor recuerda su nombre y no
        # queda en la historia (como /api/lanzar). Salida, canal y nota larga se quedan.
        LISTAS = dict(LISTA_CLIPS, dialogo="clip_dialogo")

        def _mlista(self, datos):
            motor = str(datos.get("motor", ""))
            if motor not in self.LISTAS:
                raise ValueError(f"Motor sin clips: {motor!r}")
            return motor, ctx.config[self.LISTAS[motor]]

        def _mclip_nuevo(self, motor, nombre, variante):
            if motor == "dialogo":
                return clip_de_dialogo(ctx.config, nombre, variante)
            return clip_de_motor(ctx.config, motor, nombre, variante)

        def _mclip_guardar(self, datos):
            """{motor, nombre, variante=true, indice?}: con indice guarda lo que suena encima."""
            with ctx.candado:
                motor, clips = self._mlista(datos)
                if datos.get("indice") is not None:
                    i = int(datos["indice"])
                    clips[i] = self._mclip_nuevo(motor, str(datos.get("nombre") or clips[i]["nombre"]),
                                                 datos.get("variante", clips[i].get("con_variante", True)))
                else:
                    if len(clips) >= MAX_CLIPS:
                        raise ValueError(f"Máximo {MAX_CLIPS} clips")
                    clips.append(self._mclip_nuevo(motor, str(datos.get("nombre", "")), datos.get("variante", True)))
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _mclip_lanzar(self, datos):
            """{motor, clip: i} o {motor, fabrica: género}."""
            with ctx.candado:
                motor, clips = self._mlista(datos)
                clip = generos.clip_fabrica(motor, str(datos["fabrica"])) if datos.get("fabrica") else clips[int(datos["clip"])]
                if motor == "dialogo":
                    dialogo, llamada, respuesta = dialogo_con_clip(ctx.config, clip)
                    ctx.motor.lanzar_dialogo(dialogo, llamada, respuesta, clip["nombre"])
                    ctx.config = dict(ctx.config, dialogo=dialogo, llamada=llamada, respuesta=respuesta)
                    ctx.puertos.cambiar_salidas(salidas(ctx.config))
                    aviso = self._guardar_activa()
                else:
                    nueva = copia.config(ctx.config)
                    nueva[motor] = dict(con_clip_de_motor(nueva[motor], clip), activo=True)
                    nueva = normalizar(nueva)
                    Motor(nueva, lambda *a: None)  # valida antes de tocar nada
                    aviso = self._aplicar(nueva)
                    ctx.motor.clip_motor[motor] = clip["nombre"]
            self._responder(aviso)

        def _mclip_parar(self, datos):
            """Calla el motor en el próximo compás (como «Parar» en una fila de secuencias)."""
            with ctx.candado:
                motor, _ = self._mlista(datos)
                if motor == "dialogo":
                    ctx.motor.detener_dialogo()
                    ctx.config = dict(ctx.config, dialogo=dict(ctx.config["dialogo"], activo=False))
                    aviso = self._guardar_activa()
                else:
                    nueva = copia.config(ctx.config)
                    nueva[motor] = dict(nueva[motor], activo=False)
                    aviso = self._aplicar(normalizar(nueva))
                    ctx.motor.clip_motor[motor] = None
            self._responder(aviso)

        def _mclip_borrar(self, datos):
            with ctx.candado:
                _, clips = self._mlista(datos)
                del clips[int(datos["indice"])]
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _mclip_renombrar(self, datos):
            with ctx.candado:
                _, clips = self._mlista(datos)
                clip = clips[int(datos["indice"])]
                clip["nombre"] = str(datos.get("nombre", "")).strip()[:40] or clip["nombre"]
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _mclip_restaurar(self, datos):
            with ctx.candado:
                motor, clips = self._mlista(datos)
                if len(clips) >= MAX_CLIPS:
                    raise ValueError(f"Máximo {MAX_CLIPS} clips")
                lista = self.LISTAS[motor]
                clip = normalizar(dict(ctx.config, **{lista: [datos["clip"]]}))[lista][0]
                clips.insert(max(0, min(len(clips), int(datos.get("indice", len(clips))))), clip)
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _detener(self, datos):
            with ctx.candado:
                fila = int(datos["fila"])
                ctx.motor.detener(fila)
                self._cambiar_fila(fila, dict(ctx.config["secuencia"][fila], activa=False))
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
            self._mclip_lanzar(dict(datos, motor="dialogo"))

        def _dialogo_detener(self, datos):
            with ctx.candado:
                ctx.motor.detener_dialogo()
                ctx.config = dict(ctx.config, dialogo=dict(ctx.config["dialogo"], activo=False))
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
                    escena = forma.escena_de(ctx.config, str(datos.get("nombre") or escenas[indice]["nombre"]), escenas[indice])
                    escenas[indice] = escena
                ctx.config["forma"]["escena"] = indice
                ctx.motor.base["forma"]["escena"] = indice
                ctx.motor.base["escena"] = copy.deepcopy(escenas)  # la canción usa la escena recién guardada
                aviso = self._guardar_activa()
            self._responder(aviso, indice=indice)

        def _escena_lanzar(self, datos):
            """Pasa a una escena en los compases de transición (desde el próximo compás)."""
            # Armar y validar va fuera del candado (el reloj no espera); adentro solo se lanza.
            indice = int(datos["indice"])
            for _ in range(3):
                with ctx.candado:
                    actual = ctx.config
                nueva = normalizar(forma.mezclar(actual, actual["escena"][indice]))
                nueva["forma"]["escena"] = indice
                compases = int(datos.get("compases") or nueva["forma"]["transicion"])
                Motor(nueva, lambda *a: None)  # valida antes de tocar nada
                if datos.get("editar"):
                    nueva["forma"]["piloto"] = False   # editando, el piloto no mueve nada por su cuenta
                with ctx.candado:
                    if ctx.config is not actual:
                        continue
                    if ctx.editando is not None and (datos.get("editar") or ctx.editando["escena"] != indice):
                        ctx.editando = None   # lanzar otra escena termina la edición (ya quedó guardada)
                    ctx.motor.lanzar_escena(nueva, compases, indice)
                    ctx.config = nueva
                    ctx.puertos.cambiar_salidas(salidas(nueva))
                    if datos.get("editar"):
                        ctx.editando = {"escena": indice, "original": copy.deepcopy(nueva["escena"][indice])}
                        ctx.historia.clear()   # deshacer no vuelve a antes de entrar (para eso, «Descartar»)
                    aviso = self._guardar_activa()
                self._responder(aviso, **({"original": ctx.editando["original"]["datos"]} if datos.get("editar") else {}))
                return
            raise ValueError("La configuración cambió mientras lanzaba la escena: vuelve a intentarlo")

        def _editar(self, datos):
            """Entra a editar una escena (o la de una parte): suena, y lo que muevas queda en ella."""
            with ctx.candado:
                if ctx.config["cancion"]["activa"]:
                    raise ValueError("Apaga el modo canción para editar: en él, lo que suena lo decide la canción")
                if datos.get("parte") is not None:
                    p = ctx.config["parte"][int(datos["parte"])]
                    if p["escena"] < 0:   # parte sin escena: se la crea con lo que suena ahora
                        if len(ctx.config["escena"]) >= forma.MAX_ESCENAS:
                            raise ValueError(f"Ya hay {forma.MAX_ESCENAS} escenas: elige una que ya exista para esta parte")
                        ctx.config["escena"].append(forma.escena_de(ctx.config, p["nombre"]))
                        p["escena"] = len(ctx.config["escena"]) - 1
                        ctx.motor.base["escena"] = copy.deepcopy(ctx.config["escena"])
                        ctx.motor.base["parte"] = copy.deepcopy(ctx.config["parte"])
                    indice = p["escena"]
                else:
                    indice = int(datos["escena"])
                if not 0 <= indice < len(ctx.config["escena"]):
                    raise ValueError("Esa escena no existe")
            self._escena_lanzar({"indice": indice, "compases": 1, "editar": True})

        def _editar_listo(self, datos):
            with ctx.candado:
                ctx.editando = None
            self._responder()

        def _editar_original(self, datos):
            with ctx.candado:
                ed = ctx.editando
                self._json({"ok": True, "original": ed["original"]["datos"] if ed else None})

        def _editar_descartar(self, datos):
            """Vuelve la escena a como estaba al entrar a editar, y la hace sonar así."""
            with ctx.candado:
                ed = ctx.editando
                if ed is None:
                    raise ValueError("No estás editando ninguna escena")
                i = ed["escena"]
                lista = list(ctx.config["escena"])
                lista[i] = ed["original"]
                ctx.editando = None
                ctx.config = dict(ctx.config, escena=lista)
                ctx.motor.base["escena"] = copy.deepcopy(lista)
            self._escena_lanzar({"indice": i, "compases": 1})

        def _escena_restaurar(self, datos):
            """Deshacer de «Borrar escena»: vuelven la lista de escenas y las partes como estaban."""
            with ctx.candado:
                prueba = normalizar(dict(ctx.config, escena=list(datos["escena"]), parte=list(datos["parte"])))
                ctx.editando = None
                ctx.config["escena"], ctx.config["parte"] = prueba["escena"], prueba["parte"]
                ctx.motor.base["parte"] = copy.deepcopy(ctx.config["parte"])
                ctx.motor.base["escena"] = copy.deepcopy(ctx.config["escena"])
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _limpiar(self, datos):
            """Limpiar lo que suena (o la parte que editas): todos los motores y las secuencias
            vuelven a sus valores de fábrica y quedan callados. Quedan sus salidas y canales.
            Se puede deshacer."""
            with ctx.candado:
                actual = ctx.config
            nueva = dict(actual)
            for motor in MOTORES_FABRICA:
                nueva = fabrica_motor(nueva, motor)
            for seccion in ("pads", "bajo", "dialogo", "fx", "texturas", "looper", "tocado"):
                nueva[seccion] = dict(nueva[seccion], activo=False)
            nueva["secuencia"] = [dict(fabrica_secuencia(s), activa=False) for s in actual["secuencia"]]
            nueva = normalizar(nueva)
            Motor(nueva, lambda *a: None)  # valida antes de tocar nada
            with ctx.candado:
                aviso = self._aplicar(nueva, "limpiar")
                for fila in range(len(nueva["secuencia"])):
                    ctx.motor.reiniciar_secuencia(fila)
                ctx.motor.reiniciar_bajo()
                ctx.motor.reiniciar_dialogo()
            self._responder(aviso)

        def _escena_borrar(self, datos):
            with ctx.candado:
                indice = int(datos["indice"])
                ed = ctx.editando
                if ed is not None:
                    if ed["escena"] == indice:
                        ctx.editando = None
                    elif ed["escena"] > indice:
                        ed["escena"] -= 1
                del ctx.config["escena"][indice]
                for p in ctx.config["parte"]:  # las partes de la canción siguen apuntando bien
                    p["escena"] = -1 if p["escena"] == indice else p["escena"] - (1 if p["escena"] > indice else 0)
                ctx.motor.base["parte"] = copy.deepcopy(ctx.config["parte"])
                ctx.motor.base["escena"] = copy.deepcopy(ctx.config["escena"])
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

        # --- Modo canción ---

        def _cancion(self, datos):
            """Prende o apaga el modo canción, cambia qué pasa al final o salta a una parte."""
            with ctx.candado:
                c = ctx.config["cancion"]
                if "activa" in datos:
                    c["activa"] = bool(datos["activa"])
                    if c["activa"]:
                        ctx.config["forma"]["piloto"] = False  # la canción manda sobre el piloto
                if "al_final" in datos:
                    if datos["al_final"] not in ("repetir", "quedarse"):
                        raise ValueError("Opción desconocida")
                    c["al_final"] = datos["al_final"]
                if "nombre" in datos:
                    c["nombre"] = str(datos["nombre"]).strip()[:40] or c["nombre"]
                if "loop" in datos:
                    # [desde, hasta] (partes, desde 0) o null para quitarlo. Vale desde el próximo Play.
                    if datos["loop"] is None:
                        c["loop_desde"] = c["loop_hasta"] = -1
                    else:
                        d, h = (int(x) for x in datos["loop"])
                        if not 0 <= d <= h < len(ctx.config["parte"]):
                            raise ValueError("Ese loop no calza con las partes")
                        c["loop_desde"], c["loop_hasta"] = d, h
                ctx.motor.aplicar_config(ctx.config)
                if datos.get("saltar") is not None:
                    ctx.motor.saltar_parte(int(datos["saltar"]))
                if datos.get("quedarse"):
                    ctx.motor.quedarse_parte(int(datos["quedarse"]))
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _cancion_plantilla(self, datos):
            """Reemplaza las partes de la canción por las de una plantilla (sin escenas: las eliges tú)."""
            clave = str(datos.get("clave", ""))
            if clave != "blanco" and clave not in plantillas.PLANTILLAS:
                raise ValueError("Esa plantilla no existe")
            with ctx.candado:
                if clave == "blanco":
                    ctx.config["parte"] = [{"nombre": "Parte 1", "compases": 16, "escena": -1, "energia": 0.5, "energia_fin": 0.5, "entrada": "suave"}]
                    ctx.config["cancion"]["nombre"] = "Tema nuevo"
                else:
                    ctx.config["parte"] = plantillas.partes_de(clave)
                    ctx.config["cancion"]["nombre"] = plantillas.PLANTILLAS[clave]["nombre"]
                if datos.get("nuevo"):
                    # Tema nuevo: sin las escenas del tema anterior y con el modo canción prendido.
                    ctx.editando = None
                    ctx.config["escena"] = []
                    ctx.config["forma"]["escena"] = -1
                    ctx.config["cancion"]["activa"] = True
                    ctx.config["forma"]["piloto"] = False
                ctx.config = normalizar(ctx.config)
                ctx.motor.aplicar_config(ctx.config)
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _cancion_actualizar(self, datos):
            """Pone al día los largos de la canción armada con su plantilla, sin perder escenas ni ajustes."""
            clave = str(datos.get("clave") or plantillas.clave_de(ctx.config["cancion"].get("nombre")) or "")
            if clave not in plantillas.PLANTILLAS:
                raise ValueError("No sé de qué plantilla es esta canción")
            with ctx.candado:
                partes, cambios = plantillas.actualizar(ctx.config["parte"], clave)
                if len(partes) > MAX_PARTES:
                    raise ValueError(f"Quedarían más de {MAX_PARTES} partes")
                ctx.config["parte"] = partes
                ctx.config["cancion"]["nombre"] = plantillas.PLANTILLAS[clave]["nombre"]
                ctx.config = normalizar(ctx.config)
                ctx.motor.aplicar_config(ctx.config)
                aviso = self._guardar_activa()
            self._responder(aviso, cambios=cambios)

        def _parte_nueva(self, datos):
            """Agrega una parte a la canción con lo que suena ahora como su escena."""
            with ctx.candado:
                if len(ctx.config["parte"]) >= MAX_PARTES:
                    raise ValueError(f"Máximo {MAX_PARTES} partes")
                escenas = ctx.config["escena"]
                if len(escenas) >= forma.MAX_ESCENAS:
                    raise ValueError(f"Ya hay {forma.MAX_ESCENAS} escenas: borra una o usa una que ya exista")
                nombre = str(datos.get("nombre") or f"Parte {len(ctx.config['parte']) + 1}").strip()[:24]
                escenas.append(forma.escena_de(ctx.config, nombre))
                energia = ctx.config["forma"]["energia"]
                ctx.config["parte"].append({"nombre": nombre, "compases": max(1, min(256, int(datos.get("compases") or 16))),
                                            "escena": len(escenas) - 1, "energia": energia, "energia_fin": energia,
                                            "entrada": "suave"})
                ctx.config = normalizar(ctx.config)
                ctx.motor.aplicar_config(ctx.config)
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _parte_guardar(self, datos):
            """Guarda lo que suena ahora en la escena de la parte (si no tiene, le crea una)."""
            with ctx.candado:
                p = ctx.config["parte"][int(datos["indice"])]
                escena = forma.escena_de(ctx.config, p["nombre"])
                if p["escena"] < 0:
                    if len(ctx.config["escena"]) >= forma.MAX_ESCENAS:
                        raise ValueError(f"Ya hay {forma.MAX_ESCENAS} escenas: elige una que ya exista para esta parte")
                    ctx.config["escena"].append(escena)
                    p["escena"] = len(ctx.config["escena"]) - 1
                else:
                    ctx.config["escena"][p["escena"]] = forma.escena_de(ctx.config, p["nombre"], ctx.config["escena"][p["escena"]])
                ctx.motor.aplicar_config(ctx.config)
                aviso = self._guardar_activa()
            self._responder(aviso)

        def _escena_de_parte(self, j):
            """La escena de la parte j (si no tiene, se le crea con lo que suena)."""
            p = ctx.config["parte"][j]
            if p["escena"] < 0:
                if len(ctx.config["escena"]) >= forma.MAX_ESCENAS:
                    raise ValueError(f"Ya hay {forma.MAX_ESCENAS} escenas: elige una que ya exista para {p['nombre']}")
                ctx.config["escena"].append(forma.escena_de(ctx.config, p["nombre"]))
                p["escena"] = len(ctx.config["escena"]) - 1
            return p["escena"]

        def _cambiar_escenas(self, cambiadas):
            """Escenas cambiadas desde la línea de tiempo: quedan en la config, y si una es la
            que suena (o la que editas) se vuelve a lanzar, para oír el cambio."""
            ctx.config = dict(ctx.config, escena=list(ctx.config["escena"]))
            ctx.motor.base["escena"] = copy.deepcopy(ctx.config["escena"])
            ctx.motor.base["parte"] = copy.deepcopy(ctx.config["parte"])
            suena = ctx.editando["escena"] if ctx.editando else ctx.config["forma"]["escena"]
            return suena if suena in cambiadas and not ctx.config["cancion"]["activa"] else None

        @staticmethod
        def _seccion(datos, motor):
            """Las secciones de una escena que son de un motor («sec2» = la 3.ª secuencia)."""
            if motor.startswith("sec"):
                return [("secuencia", int(motor[3:]))]
            if motor == "dialogo":
                return [("dialogo", None), ("llamada", None), ("respuesta", None)]
            if motor not in forma.SECCIONES:
                raise ValueError(f"Motor desconocido: {motor}")
            return [(motor, None)]

        def _parte_copiar(self, datos):
            """Copia motores de una parte a otras (solo esos: lo demás de la parte de destino
            queda). Si la parte de destino comparte su escena con otras, cambian todas."""
            desde = int(datos["desde"])
            hacia = [int(j) for j in (datos["hacia"] if isinstance(datos["hacia"], list) else [datos["hacia"]])]
            motores = list(datos["motores"])
            with ctx.candado:
                ctx.config = dict(ctx.config, escena=list(ctx.config["escena"]))   # (la historia guarda la lista de antes)
                partes = ctx.config["parte"]
                if desde < 0:
                    origen = None   # «lo que suena ahora»: lo que está tocando, sin parte
                    fuente = forma.foto(ctx.config)
                else:
                    origen = partes[desde]["escena"]
                    if origen < 0:
                        raise ValueError(f"{partes[desde]['nombre']} todavía no tiene escena: edítala primero")
                    fuente = json.loads(ctx.config["escena"][origen]["datos"])
                cambiadas, compartidas = set(), set()
                for j in hacia:
                    if j == desde:
                        continue
                    idx = self._escena_de_parte(j)
                    if idx == origen:
                        continue   # la misma escena: ya tiene lo mismo
                    destino = json.loads(ctx.config["escena"][idx]["datos"])
                    for motor in motores:
                        for sec, n in self._seccion(fuente, motor):
                            if n is None:
                                if sec in fuente:
                                    destino[sec] = copy.deepcopy(fuente[sec])
                            else:
                                lista = destino.setdefault("secuencia", [])
                                if n < len(fuente.get("secuencia", [])):
                                    while len(lista) <= n:
                                        lista.append(dict(fuente["secuencia"][len(lista)], activa=False))
                                    lista[n] = copy.deepcopy(fuente["secuencia"][n])
                    ctx.config["escena"][idx] = dict(ctx.config["escena"][idx], datos=json.dumps(destino, ensure_ascii=False, separators=(",", ":")))
                    cambiadas.add(idx)
                    compartidas |= {p["nombre"] for k, p in enumerate(partes) if p["escena"] == idx and k not in hacia}
                relanzar = self._cambiar_escenas(cambiadas)
                if relanzar is None:
                    aviso = self._guardar_activa()
            if relanzar is not None:
                self._escena_lanzar({"indice": relanzar, "compases": 1})
                return
            self._responder(aviso, compartidas=sorted(compartidas))

        def _parte_apagar(self, datos):
            """«Que no suene aquí»: el motor queda apagado en la escena de esa parte."""
            j, motor = int(datos["parte"]), str(datos["motor"])
            with ctx.candado:
                ctx.config = dict(ctx.config, escena=list(ctx.config["escena"]))
                idx = ctx.config["parte"][j]["escena"]
                if idx < 0:
                    raise ValueError("Esa parte todavía no tiene escena")
                d = json.loads(ctx.config["escena"][idx]["datos"])
                for sec, n in self._seccion(d, motor):
                    if n is None and sec in d and sec in ("pads", "bajo", "dialogo", "fx", "texturas", "looper", "tocado"):
                        d[sec]["activo"] = False
                    elif n is not None and n < len(d.get("secuencia", [])):
                        d["secuencia"][n]["activa"] = False
                ctx.config["escena"][idx] = dict(ctx.config["escena"][idx], datos=json.dumps(d, ensure_ascii=False, separators=(",", ":")))
                relanzar = self._cambiar_escenas({idx})
                if relanzar is None:
                    aviso = self._guardar_activa()
            if relanzar is not None:
                self._escena_lanzar({"indice": relanzar, "compases": 1})
                return
            self._responder(aviso)

        def _parte_escuchar(self, datos):
            """Modo libre: suena la escena de la parte (para armarla). Modo canción: salta a ella."""
            indice = int(datos["indice"])
            with ctx.candado:
                p = ctx.config["parte"][indice]
                if ctx.config["cancion"]["activa"]:
                    ctx.motor.saltar_parte(indice)
                    self._responder()
                    return
                if p["escena"] < 0:
                    raise ValueError("Esta parte no tiene escena todavía")
            self._escena_lanzar({"indice": p["escena"], "compases": 1})

        def _subida(self, datos):
            """Subida de FX: riser, filtros y stutter durante `compases`, desde el próximo compás (0 = cancelar)."""
            with ctx.candado:
                if datos.get("final"):
                    ctx.motor.pedir_subida_final(int(datos.get("compases", 0)))
                else:
                    ctx.motor.pedir_subida(int(datos.get("compases", 0)))
            self._responder()

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
            ruta = ruta_proyecto(ctx, nombre)   # valida el nombre antes de tocar nada
            if datos.get("nuevo") and ruta.exists() and not datos.get("sobrescribir"):
                self._json({"error": "Ya hay un proyecto con ese nombre", "existe": True}, 409)
                return
            if nombre != ctx.config["app"].get("proyecto"):
                ctx.guardar_ya()   # «Guardar como»: el proyecto de antes se queda con su último cambio
            with ctx.candado:
                ctx.sincronizar_tocado()   # lo último grabado en el Tocado también
                ctx.config = dict(ctx.config, app=dict(ctx.config["app"], proyecto=nombre))
                activa = ctx.config
                aviso = self._guardar_activa()
            guardar(ruta, activa)   # escribir el archivo, sin el candado
            with ctx.candado:
                if ctx.config is activa:
                    ctx.proyecto_al_dia = True
            # Comprobar que quedó bien: si no se puede leer, que la app lo diga.
            if cargar(ruta)["app"]["proyecto"] != nombre:
                raise OSError("El proyecto no quedó bien guardado, prueba otra vez")
            self._responder(aviso, proyecto=nombre)

        def _proyecto_abrir(self, datos):
            nombre = str(datos.get("nombre", "")).strip()
            nueva = cargar(ruta_proyecto(ctx, nombre))
            with ctx.candado:
                ctx.sincronizar_tocado()
            ctx.guardar_ya()   # el último cambio (y lo grabado) queda en el proyecto que cierras
            nueva["app"]["puerto"] = ctx.config["app"]["puerto"]  # el puerto de la app no cambia
            Motor(nueva, lambda *a: None)
            with ctx.candado:
                aviso = self._aplicar(nueva)
                ctx.historia.clear()  # otro proyecto: lo de antes no se deshace sobre este
                ctx.proyecto_al_dia = True
            self._responder(aviso, proyecto=nueva["app"]["proyecto"])

        def _proyecto_borrar(self, datos):
            ruta = ruta_proyecto(ctx, str(datos.get("nombre", "")))
            ruta.unlink()
            self._responder()

    fuentes.asegurar_en_segundo_plano()
    servidor = ThreadingHTTPServer(("0.0.0.0", puerto), Manejador)
    servidor.daemon_threads = True
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    log.info("App disponible en http://goa.local:%d", puerto)
    return servidor
