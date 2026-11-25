"""Korg nanoKONTROL2: cada canal maneja un motor y el transporte, las escenas.

El nanoKONTROL2 tiene que estar en modo CC (al prenderlo, mantener SET + CYCLE) con sus
números de fábrica. Para que los botones se queden prendidos según el estado del motor,
LED Mode = External: el botón de Ajustes › nanoKONTROL2 o `goa-ports --nano-led` (goa/nano.py)
lo escriben en el nano sin el Kontrol Editor de Korg.

Cada canal maneja el motor que elijas en Ajustes › nanoKONTROL2 (config [control]
canal1-canal8). De fábrica, de izquierda a derecha: Pads, Bajo, Secuencia A, Secuencia B,
Diálogo, FX, Texturas y Looper. Cada motor trae su fader y su perilla (DEFECTO) y se pueden
cambiar por canal (fader1-8, perilla1-8) entre los de OPCIONES.

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
# Un fader gastado o sucio tiembla solo (manda 82, 85, 83, 87… sin tocarlo): eso cambiaba el
# motor sin parar y la app se recargaba todo el tiempo. Histéresis: mientras lo mueves
# (otro cambio hace menos de QUIETO segundos) y sigue para el mismo lado, va fino (SEGUIR
# pasos); quieto, o dando la vuelta, tiene que moverse VUELTA pasos. El temblor va y viene
# sobre un fader quieto, así que no pasa. 0 y 127 siempre llegan.
SEGUIR = 2
VUELTA = 7
QUIETO = 0.4
LUCES_CADA = 0.25

FADERS, PERILLAS = range(0, 8), range(16, 24)
SOLO, MUTE, REC = range(32, 40), range(48, 56), range(64, 72)
TRACK_ANT, TRACK_SIG, CYCLE, SET, MARKER_ANT, MARKER_SIG = 58, 59, 46, 60, 61, 62
REW, FF, STOP, PLAY, GRABAR = 43, 44, 42, 41, 45

# Qué maneja cada canal: (sección, fila) del motor, la clave de su encendido, y
# (secciones, clave) del fader y de la perilla. Una sección "cc" no toca la
# configuración: manda ese CC al sinte del motor (el looper no tiene parámetros).
# Lo que pueden mover el fader y la perilla de cada tipo de motor: id -> (secciones, clave,
# nombre). ("cc",) es un CC directo al sinte del motor (sin valor guardado: no recoge).
# La app tiene la misma lista (web/js/3-vivo.js, OPCIONES_NANO).
OPCIONES = {
    "secuencia": {"densidad": (("secuencia",), "densidad", "densidad"), "mutacion": (("secuencia",), "mutacion", "mutación"),
                  "gate": (("secuencia",), "gate", "largo de nota (gate)"), "swing": (("secuencia",), "swing", "swing"),
                  "huecos": (("secuencia",), "huecos", "huecos (psytrance)"), "slide": (("secuencia",), "slide", "slide"),
                  "acentos": (("secuencia",), "acentos", "acentos"), "largas": (("secuencia",), "largas", "notas largas"),
                  "repeticion": (("secuencia",), "repeticion", "repetición"),
                  "filtro_reposo": (("secuencia",), "filtro_reposo", "filtro en reposo"),
                  "piano_melancolia": (("secuencia",), "piano_melancolia", "melancolía (piano)"),
                  "piano_psy": (("secuencia",), "piano_psy", "psy (piano)")},
    "pads": {"voces": (("pads",), "voces", "voces del acorde"), "variacion": (("pads",), "variacion", "variación"),
             "rasgueo": (("pads",), "rasgueo", "rasgueo"), "pulso": (("pads",), "pulso", "pulso"),
             "suspensiones": (("pads",), "suspensiones", "suspensiones"), "velocidad": (("pads",), "velocidad", "fuerza")},
    "bajo": {"densidad": (("bajo",), "densidad", "densidad"), "filtro_max": (("bajo",), "filtro_max", "filtro (apertura)"),
             "filtro_min": (("bajo",), "filtro_min", "filtro (cierre)"), "swing": (("bajo",), "swing", "swing"),
             "slide": (("bajo",), "slide", "slide"), "acentos": (("bajo",), "acentos", "acentos"),
             "gate": (("bajo",), "gate", "largo de nota (gate)"), "evolucion": (("bajo",), "evolucion", "evolución")},
    "dialogo": {"densidad": (("dialogo",), "densidad", "densidad"), "oscuridad": (("llamada", "respuesta"), "oscuridad", "oscuridad"),
                "espacio": (("dialogo",), "espacio", "espacio"), "evolucion": (("dialogo",), "evolucion", "evolución")},
    "fx": {"filtro_reposo": (("fx",), "filtro_reposo", "filtro en reposo"), "locura": (("fx",), "locura", "locura"),
           "caos": (("fx",), "caos", "caos"), "repetir": (("fx",), "repetir", "repetir"),
           "movimiento": (("fx",), "movimiento", "movimiento")},
    "texturas": {"densidad": (("texturas",), "densidad", "densidad"), "profundidad": (("texturas",), "profundidad", "profundidad"),
                 "largas": (("texturas",), "largas", "notas largas"), "registro": (("texturas",), "registro", "registro")},
    "looper": {"cc74": (("cc",), 74, "filtro (CC 74)"), "cc71": (("cc",), 71, "resonancia (CC 71)"),
               "nivel": (("looper",), "nivel", "nivel")},
    "obertura": {"densidad_cuerdas": (("obertura",), "densidad_cuerdas", "intensidad (densidad de cuerdas)"),
                 "viva": (("obertura",), "viva", "desarrollo (orquestación viva)"),
                 "humanizar": (("obertura",), "humanizar", "humanizar"), "swing": (("obertura",), "swing", "swing"),
                 "nivel_cuerdas": (("obertura",), "nivel_cuerdas", "nivel de cuerdas"),
                 "nivel_cuernos": (("obertura",), "nivel_cuernos", "nivel de cuernos"),
                 "nivel_coro": (("obertura",), "nivel_coro", "nivel del coro")},
    "tocado": {"densidad": (("tocado",), "densidad", "densidad"), "mutacion": (("tocado",), "mutacion", "mutación"),
               "gate": (("tocado",), "gate", "largo de nota (gate)"), "huecos": (("tocado",), "huecos", "huecos")},
    "circuit": {"cc74": (("cc",), 74, "filtro maestro (CC 74)"), "reverb_s1": (("circuit",), "reverb_s1", "reverb Synth 1"),
                "reverb_s2": (("circuit",), "reverb_s2", "reverb Synth 2"), "delay_s1": (("circuit",), "delay_s1", "delay Synth 1"),
                "delay_s2": (("circuit",), "delay_s2", "delay Synth 2")},
}
DEFECTO = {"secuencia": ("densidad", "mutacion"), "pads": ("voces", "variacion"), "bajo": ("densidad", "filtro_max"),
           "dialogo": ("densidad", "oscuridad"), "fx": ("filtro_reposo", "locura"), "texturas": ("densidad", "profundidad"),
           "looper": ("cc74", "cc71"), "obertura": ("densidad_cuerdas", "viva"), "tocado": ("densidad", "mutacion"),
           "circuit": ("cc74", "reverb_s1")}
NOMBRE_MOTOR = {"pads": "Pads", "bajo": "Bajo", "dialogo": "Diálogo", "fx": "FX", "texturas": "Texturas",
                "looper": "Looper", "obertura": "Obertura", "tocado": "Tocado", "circuit": "Circuit"}
# De fábrica (lo que había antes de poder elegir): las secuencias por su nombre.
FABRICA = ("pads", "bajo", "sec:A", "sec:B", "dialogo", "fx", "texturas", "looper")


def canales(cfg):
    """Los 8 canales según [control]: cada uno un dict (o None si está en «nada» o su motor
    no existe, por ejemplo una secuencia borrada)."""
    c = cfg.get("control", {})
    lista = []
    for n in range(1, 9):
        ref = c.get(f"canal{n}", FABRICA[n - 1])
        tipo, fila, nombre = ref, None, NOMBRE_MOTOR.get(ref)
        if ref.startswith("sec:"):
            tipo = "secuencia"
            nombres = [s.get("nombre") for s in cfg.get("secuencia", [])]
            fila = nombres.index(ref[4:]) if ref[4:] in nombres else None
            nombre = f"Secuencia {ref[4:]}"
            if fila is None:
                lista.append(None)
                continue
        if tipo not in OPCIONES:
            lista.append(None)
            continue
        opciones = OPCIONES[tipo]
        f = c.get(f"fader{n}") or DEFECTO[tipo][0]
        p = c.get(f"perilla{n}") or DEFECTO[tipo][1]
        f = f if f in opciones else DEFECTO[tipo][0]
        p = p if p in opciones else DEFECTO[tipo][1]
        lista.append({"nombre": nombre, "tipo": tipo, "motor": (tipo, fila),
                      "activo": "activa" if tipo == "secuencia" else "activo",
                      "fader": opciones[f][:2], "perilla": opciones[p][:2],
                      "textos": (opciones[f][2], opciones[p][2])})
    return lista


def mapa(cfg):
    """El mapa para mostrar en la app."""
    return [{"canal": i + 1, "motor": c["nombre"] if c else "—", "fader": c["textos"][0] if c else "",
             "perilla": c["textos"][1] if c else ""} for i, c in enumerate(canales(cfg))]


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
        self.lado = {}           # cc -> +1 / -1: para dónde se movió la última vez (contra el temblor)
        self.movido = {}         # cc -> cuándo se aplicó su último cambio
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
                "solo": None if self.solo is None else (self._canal(self.solo[0]) or {}).get("nombre"),
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

    def _canal(self, i):
        return canales(self.ctx.config)[i]

    def _destino(self, cc):
        canal = self._canal(cc - (0 if cc in FADERS else 16))
        if canal is None:
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
            ultimo = self.enganchado.get(cc)
            if ultimo is not None and v not in (0, 127):
                lado = 1 if v > ultimo else -1
                moviendo = time.monotonic() - self.movido.get(cc, 0.0) < QUIETO
                umbral = SEGUIR if moviendo and self.lado.get(cc) in (None, lado) else VUELTA
                if abs(v - ultimo) < umbral:
                    continue  # tiembla en el lugar: no es un movimiento
            if ultimo is not None and v != ultimo:
                self.lado[cc] = 1 if v > ultimo else -1
            self.movido[cc] = time.monotonic()
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
        # La Circuit: su filtro maestro va por el canal de proyecto.
        return {"salida": datos["salida"], "canal": datos.get("canal_control", datos.get("canal")), "cc": numero, "valor": valor}

    # --- Botones ---

    def _encendido(self, i):
        canal = self._canal(i)
        if canal is None:
            return False
        seccion, fila = canal["motor"]
        cfg = self.ctx.config
        if seccion == "secuencia":
            return bool(cfg["secuencia"][fila]["activa"])
        return bool(cfg[seccion]["activo"])

    def _cambio_encendido(self, i, valor):
        canal = self._canal(i)
        if canal is None:
            return None
        seccion, fila = canal["motor"]
        return [seccion, fila, canal["activo"], bool(valor)]

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
            antes = self.solo[1] if self.solo is not None else [self._encendido(j) for j in range(8)]
            for j in range(8):
                cambio = self._cambio_encendido(j, j == i)
                if cambio:
                    cambios.append(cambio)
            self.solo = (i, antes)
        if cambios:
            self._api("/api/ajuste", {"cambios": cambios})

    def _rec(self, i):
        canal = self._canal(i)
        if canal is None:
            return
        seccion, fila = canal["motor"]
        cfg = self.ctx.config
        if seccion == "looper":
            clip = cfg["looper"]["clip"] % 16 + 1
            self._api("/api/ajuste", {"cambios": [["looper", None, "clip", clip]]})
            return
        esquema = ESQUEMA_SECUENCIA if seccion == "secuencia" else ESQUEMA_SECCIONES[seccion]
        if "seed" in esquema:   # la Circuit no tiene seed: R no hace nada
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
        for i in range(8):
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
