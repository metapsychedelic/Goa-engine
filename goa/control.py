"""Korg nanoKONTROL2: cada canal maneja un motor y el transporte, las escenas.

El nanoKONTROL2 tiene que estar en modo CC (al prenderlo, mantener SET + CYCLE) con sus
números de fábrica. Para que los botones se queden prendidos según el estado del motor,
LED Mode = External: el botón de Ajustes › nanoKONTROL2 o `goa-ports --nano-led` (goa/nano.py)
lo escriben en el nano sin el Kontrol Editor de Korg.

Los ocho canales, de izquierda a derecha: Pads, Bajo, Secuencia A, Secuencia B, Diálogo,
FX, Texturas y Looper.

  Fader    cuánto pasa (densidad, voces, filtro)   Perilla  su carácter
           El volumen no se maneja desde acá: queda en cada sinte.
  S        solo (los demás se callan; otra vez y vuelven)
  M        prende o apaga el motor (como en la app: entra y sale sin cortar)
  R        seed nueva (en el looper: el loop siguiente)

  ◀ TRACK ▶  elegir escena          PLAY  lanzarla       STOP  volver a la de antes
  SET        guardar lo que suena como escena nueva
  ◀ MARKER ▶ energía −/+            CYCLE piloto         REW   deshacer
  REC        subida (otra vez: la cancela)

Faders y perillas «recogen» el valor: mientras no pasen por donde está el motor no
cambian nada, así nada salta al tocarlos (también después de cambiar de escena).

Todo pasa por la API de la app (como si fuera otro teléfono): las mismas validaciones,
el mismo deshacer y el guardado en la tarjeta, y el candado del reloj solo el instante
de aplicar. El nanoKONTROL2 manda muchos mensajes seguidos al mover un fader: se junta
lo último de cada control y se aplica cada INTERVALO segundos.
"""

import json
import logging
import queue
import random
import threading
import time
import urllib.error
import urllib.request

from .config import ESQUEMA_SECCIONES, ESQUEMA_SECUENCIA

log = logging.getLogger("goa.control")

INTERVALO = 0.06      # cada cuánto se aplica lo que movieron faders y perillas
RECOGER = 3           # a cuántos pasos (de 0-127) del valor del motor engancha un control
LUCES_CADA = 0.25

FADERS, PERILLAS = range(0, 8), range(16, 24)
SOLO, MUTE, REC = range(32, 40), range(48, 56), range(64, 72)
TRACK_ANT, TRACK_SIG, CYCLE, SET, MARKER_ANT, MARKER_SIG = 58, 59, 46, 60, 61, 62
REW, FF, STOP, PLAY, GRABAR = 43, 44, 42, 41, 45

# Qué maneja cada canal: (sección, fila) del motor, la clave de su encendido, y
# (secciones, clave) del fader y de la perilla. Una sección "cc" no toca la
# configuración: manda ese CC al sinte del motor (el looper no tiene parámetros).
CANALES = [
    {"nombre": "Pads", "motor": ("pads", None), "activo": "activo",
     "fader": (("pads",), "voces"), "perilla": (("pads",), "variacion")},
    {"nombre": "Bajo", "motor": ("bajo", None), "activo": "activo",
     "fader": (("bajo",), "densidad"), "perilla": (("bajo",), "filtro_max")},
    {"nombre": "Secuencia A", "motor": ("secuencia", 0), "activo": "activa",
     "fader": (("secuencia",), "densidad"), "perilla": (("secuencia",), "mutacion")},
    {"nombre": "Secuencia B", "motor": ("secuencia", 1), "activo": "activa",
     "fader": (("secuencia",), "densidad"), "perilla": (("secuencia",), "mutacion")},
    {"nombre": "Diálogo", "motor": ("dialogo", None), "activo": "activo",
     "fader": (("dialogo",), "densidad"), "perilla": (("llamada", "respuesta"), "oscuridad")},
    {"nombre": "FX", "motor": ("fx", None), "activo": "activo",
     "fader": (("fx",), "filtro_reposo"), "perilla": (("fx",), "locura")},
    {"nombre": "Texturas", "motor": ("texturas", None), "activo": "activo",
     "fader": (("texturas",), "densidad"), "perilla": (("texturas",), "profundidad")},
    {"nombre": "Looper", "motor": ("looper", None), "activo": "activo",
     "fader": (("cc",), 74), "perilla": (("cc",), 71)},
]

NOMBRES = {"voces": "voces del acorde", "densidad": "densidad", "variacion": "variación",
           "filtro_max": "filtro (apertura)", "mutacion": "mutación",
           "oscuridad": "oscuridad", "filtro_reposo": "filtro en reposo", "locura": "locura",
           "profundidad": "profundidad", 74: "filtro (CC 74)", 71: "resonancia (CC 71)"}


def mapa():
    """El mapa para mostrar en la app."""
    def texto(destino):
        secciones, clave = destino
        return NOMBRES.get(clave, str(clave))
    return [{"canal": i + 1, "motor": c["nombre"], "fader": texto(c["fader"]), "perilla": texto(c["perilla"])}
            for i, c in enumerate(CANALES)]


def _rango(seccion, clave):
    esquema = ESQUEMA_SECUENCIA if seccion == "secuencia" else ESQUEMA_SECCIONES[seccion]
    tipo, _, minimo, maximo = esquema[clave]
    return tipo, minimo, maximo


def a_valor(seccion, clave, cc):
    tipo, minimo, maximo = _rango(seccion, clave)
    v = minimo + (maximo - minimo) * cc / 127
    return int(round(v)) if tipo is int else round(v, 3)


def a_cc(seccion, clave, valor):
    _, minimo, maximo = _rango(seccion, clave)
    return 0 if maximo == minimo else max(0, min(127, round((valor - minimo) / (maximo - minimo) * 127)))


def nueva_seed():
    return "%04X-%04X" % (random.randrange(65536), random.randrange(65536))


class Control:
    def __init__(self, ctx, puerto_app):
        self.ctx = ctx
        self.url = f"http://127.0.0.1:{puerto_app}"
        self.cola = queue.Queue()
        self.mover = {}          # cc -> último valor sin aplicar (faders y perillas)
        self.enganchado = {}     # cc -> último valor aplicado (control "recogido")
        self.previo = {}         # cc -> valor anterior que mandó el control (para ver si cruzó)
        self.solo = None         # (canal, encendidos de antes) mientras hay un solo
        self.escena = None       # escena elegida con TRACK
        self.anterior = None     # escena que sonaba antes de PLAY (para STOP)
        self.ultimo = None       # último mensaje que llegó (para ver en la app)
        self.luces = {}          # cc -> 0/127 ya mandado
        self.conectado = None    # nombre del puerto abierto
        threading.Thread(target=self._trabajar, name="control", daemon=True).start()

    # --- Entrada (callback de mido: nada pesado acá) ---

    def recibir(self, msg):
        if msg.type == "control_change":
            self.cola.put(msg)

    # --- Estado para la app ---

    def estado(self):
        cfg = self.ctx.config
        escenas = cfg.get("escena", [])
        elegida = self.escena if self.escena is not None and self.escena < len(escenas) else None
        return {"conectado": self.conectado, "ultimo": self.ultimo, "escena": elegida,
                "solo": None if self.solo is None else CANALES[self.solo[0]]["nombre"],
                "sueltos": sorted(c for c in list(FADERS) + list(PERILLAS) if c not in self.enganchado and self._destino(c))}

    # --- El hilo ---

    def _trabajar(self):
        luces = 0.0
        while True:
            try:
                msg = self.cola.get(timeout=INTERVALO)
                self._juntar(msg)
                while True:  # todo lo que ya llegó
                    self._juntar(self.cola.get_nowait())
            except queue.Empty:
                pass
            try:
                self._aplicar_movidos()
                if time.monotonic() - luces > LUCES_CADA:
                    luces = time.monotonic()
                    self._luces()
            except Exception:  # noqa: BLE001  el control no debe caerse por un error
                log.exception("Error en el control")

    def _juntar(self, msg):
        cfg = self.ctx.config["control"]
        if msg.channel != cfg["canal"] - 1:
            return
        self.ultimo = f"CC {msg.control} = {msg.value}"
        cc, v = msg.control, msg.value
        if cc in FADERS or cc in PERILLAS:
            self.mover[cc] = v
            return
        if v == 0:
            return  # los botones mandan 127 al apretar y 0 al soltar: solo cuenta apretar
        try:
            self._boton(cc)
        except Exception as e:  # noqa: BLE001
            log.warning("Control: %s", e)

    # --- Faders y perillas ---

    def _destino(self, cc):
        i = cc - (0 if cc in FADERS else 16)
        canal = CANALES[i]
        seccion, fila = canal["motor"]
        if seccion == "secuencia" and fila >= len(self.ctx.config["secuencia"]):
            return None
        return canal, canal["fader" if cc in FADERS else "perilla"]

    def _actual(self, canal, destino):
        """El valor que tiene ahora el motor, en 0-127 (None: un CC directo, sin valor guardado)."""
        secciones, clave = destino
        if secciones == ("cc",):
            return None
        cfg = self.ctx.config
        seccion = secciones[0]
        datos = cfg["secuencia"][canal["motor"][1]] if seccion == "secuencia" else cfg[seccion]
        return a_cc(seccion, clave, datos[clave])

    def _aplicar_movidos(self):
        if not self.mover:
            return
        movidos, self.mover = self.mover, {}
        cambios, ccs = [], []
        for cc, v in movidos.items():
            hallado = self._destino(cc)
            if hallado is None:
                continue
            canal, destino = hallado
            secciones, clave = destino
            actual = self._actual(canal, destino)
            antes = self.previo.get(cc)
            self.previo[cc] = v
            if actual is not None:
                if cc in self.enganchado and abs(self.enganchado[cc] - actual) > RECOGER:
                    del self.enganchado[cc]  # cambió por otro lado (escena, app): recoger otra vez
                if cc not in self.enganchado:
                    cruzo = antes is not None and (antes - actual) * (v - actual) <= 0
                    if abs(v - actual) > RECOGER and not cruzo:
                        continue
            self.enganchado[cc] = v
            if secciones == ("cc",):
                ccs.append(self._cc_del_motor(canal, clave, v))
                continue
            for seccion in secciones:
                fila = canal["motor"][1] if seccion == "secuencia" else None
                cambios.append([seccion, fila, clave, a_valor(seccion, clave, v)])
        for datos in ccs:
            if datos:
                self._api("/api/cc", datos)
        if cambios:
            self._api("/api/ajuste", {"cambios": cambios, "juntar": True})

    def _cc_del_motor(self, canal, numero, valor):
        seccion, _ = canal["motor"]
        datos = self.ctx.config[seccion]
        return {"salida": datos["salida"], "canal": datos["canal"], "cc": numero, "valor": valor}

    # --- Botones ---

    def _encendido(self, i):
        seccion, fila = CANALES[i]["motor"]
        cfg = self.ctx.config
        if seccion == "secuencia":
            return fila < len(cfg["secuencia"]) and cfg["secuencia"][fila]["activa"]
        return cfg[seccion]["activo"]

    def _cambio_encendido(self, i, valor):
        seccion, fila = CANALES[i]["motor"]
        if seccion == "secuencia" and fila >= len(self.ctx.config["secuencia"]):
            return None
        return [seccion, fila, CANALES[i]["activo"], bool(valor)]

    def _boton(self, cc):
        cfg = self.ctx.config
        if cc in MUTE:
            i = cc - MUTE.start
            cambio = self._cambio_encendido(i, not self._encendido(i))
            if cambio:
                self.solo = None
                self._api("/api/ajuste", {"cambios": [cambio]})
        elif cc in SOLO:
            self._solo(cc - SOLO.start)
        elif cc in REC:
            self._rec(cc - REC.start)
        elif cc in (TRACK_ANT, TRACK_SIG):
            n = len(cfg["escena"])
            if n:
                base = self.escena if self.escena is not None else max(cfg["forma"]["escena"], 0)
                self.escena = (base + (1 if cc == TRACK_SIG else -1)) % n if self.escena is not None else base
        elif cc == PLAY:
            if self.escena is not None and self.escena < len(cfg["escena"]):
                self.anterior = cfg["forma"]["escena"]
                self._api("/api/escena/lanzar", {"indice": self.escena})
        elif cc == STOP:
            if self.anterior is not None and 0 <= self.anterior < len(cfg["escena"]):
                self.escena, self.anterior = self.anterior, cfg["forma"]["escena"]
                self._api("/api/escena/lanzar", {"indice": self.escena})
        elif cc == SET:
            r = self._api("/api/escena/guardar", {"nombre": f"Escena {len(cfg['escena']) + 1}"})
            if r and "indice" in r:
                self.escena = r["indice"]
        elif cc in (MARKER_ANT, MARKER_SIG):
            e = cfg["forma"]["energia"] + (0.1 if cc == MARKER_SIG else -0.1)
            self._api("/api/energia", {"energia": round(max(0.0, min(1.0, e)), 2)})
        elif cc == CYCLE:
            self._api("/api/piloto", {"activo": not cfg["forma"].get("piloto")})
        elif cc == REW:
            self._api("/api/deshacer", {})
        elif cc == GRABAR:
            hay = self._subida_en_curso()
            self._api("/api/subida", {"compases": 0 if hay else cfg["control"]["subida"]})

    def _solo(self, i):
        cambios = []
        if self.solo is not None and self.solo[0] == i:
            # Otra vez el mismo: vuelven los que sonaban.
            for j, estaba in enumerate(self.solo[1]):
                cambio = self._cambio_encendido(j, estaba)
                if cambio:
                    cambios.append(cambio)
            self.solo = None
        else:
            antes = self.solo[1] if self.solo is not None else [self._encendido(j) for j in range(len(CANALES))]
            for j in range(len(CANALES)):
                cambio = self._cambio_encendido(j, j == i)
                if cambio:
                    cambios.append(cambio)
            self.solo = (i, antes)
        if cambios:
            self._api("/api/ajuste", {"cambios": cambios})

    def _rec(self, i):
        seccion, fila = CANALES[i]["motor"]
        cfg = self.ctx.config
        if seccion == "looper":
            clip = cfg["looper"]["clip"] % 16 + 1
            self._api("/api/ajuste", {"cambios": [["looper", None, "clip", clip]]})
            return
        if seccion == "secuencia" and fila >= len(cfg["secuencia"]):
            return
        self._api("/api/ajuste", {"cambios": [[seccion, fila, "seed", nueva_seed()]]})

    def _subida_en_curso(self):
        try:
            with self.ctx.candado:
                s = self.ctx.motor.estado().get("subida")
            return bool(s)
        except Exception:  # noqa: BLE001
            return False

    # --- Luces ---

    def _luces(self):
        cfg = self.ctx.config
        if not (cfg["control"]["activo"] and cfg["control"]["luces"] and self.conectado):
            self.luces = {}
            return
        quiero = {}
        for i in range(len(CANALES)):
            quiero[MUTE.start + i] = 127 if self._encendido(i) else 0
            quiero[SOLO.start + i] = 127 if self.solo is not None and self.solo[0] == i else 0
            quiero[REC.start + i] = 0
        quiero[CYCLE] = 127 if cfg["forma"].get("piloto") else 0
        quiero[GRABAR] = 127 if self._subida_en_curso() else 0
        quiero[PLAY] = 127 if cfg["forma"]["escena"] >= 0 else 0
        quiero[STOP] = 0
        canal = cfg["control"]["canal"] - 1
        puerto = cfg["control"]["puerto"]
        cambios = [(cc, v) for cc, v in quiero.items() if self.luces.get(cc) != v]
        if not cambios:
            return
        with self.ctx.candado:
            for cc, v in cambios:
                self.ctx.puertos.enviar(puerto, "control_change", canal, cc, v)
        self.luces.update(cambios)

    # --- La app ---

    def _api(self, ruta, datos):
        pedido = urllib.request.Request(self.url + ruta, data=json.dumps(datos).encode(),
                                        headers={"Content-Type": "application/json", "X-Goa-Control": "1"}, method="POST")
        try:
            with urllib.request.urlopen(pedido, timeout=5) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            try:
                log.warning("Control %s: %s", ruta, json.loads(e.read()).get("error"))
            except ValueError:
                log.warning("Control %s: error %s", ruta, e.code)
        except OSError as e:
            log.warning("Control %s: %s", ruta, e)
        return None
