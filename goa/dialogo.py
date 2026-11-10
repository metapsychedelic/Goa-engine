"""Llamada y respuesta euclidiana.

Dos voces que conversan con ritmos euclidianos: cada una reparte sus golpes de
la forma más pareja posible en el compás. Todo cae en una rejilla (corcheas o
semicorcheas) y la llamada siempre tiene un golpe en el uno, así nada se
arrastra respecto del bombo.

Formas de conversar:
- entrelazado: la respuesta toca solo en los huecos que deja la llamada,
  esperando `espacio` lugares después de cada nota de la llamada.
- turnos: la llamada toca unos compases, luego responde la otra voz, y alternan.

La llamada la toca el motor (con su nota larga) o la tocas tú en vivo: el motor
escucha dónde tocaste en cada compás y en el siguiente responde en tus huecos.

Las notas salen de un conjunto chico según Luminoso ↔ Oscuro, contadas en la
escala desde la raíz del acorde de los pads (o de la nota larga). Cada voz
repite su orden de notas, y la mutación cambia una nota o gira el patrón
cada cierto número de compases, como las secuencias.
"""

import random

from .escalas import Tonalidad

TICKS_POR_PASO = 6
PASOS_POR_COMPAS = 16

MODOS = ("motor", "en_vivo")
FORMAS = ("entrelazado", "turnos")
REJILLAS = {"corcheas": 2, "semicorcheas": 1}  # pasos de semicorchea por lugar

# Notas de cada voz según el color, en grados de la escala desde la raíz del acorde.
# La primera es el ancla (el golpe del uno en la llamada). La respuesta vive más
# arriba: parte de la quinta y llega a la octava.
NOTAS = {
    "luminoso": {"llamada": (0, 2, 4, 6), "respuesta": (4, 6, 7, 9)},   # raíz, ♭3, 5, ♭7
    "claro": {"llamada": (0, 2, 4), "respuesta": (4, 6, 7)},
    "oscuro": {"llamada": (0, 1, 4), "respuesta": (4, 5, 7)},           # ♭2 y ♭6: el color frigio
    "ultra": {"llamada": (0, 1, 0, 1), "respuesta": (5, 4, 8)},         # medio tono contra la raíz
}
LARGO_MAXIMO = 8  # pasos: con largo 100 % una nota sola puede sostenerse hasta medio compás


def color(oscuridad):
    if oscuridad < 0.15:
        return "luminoso"
    if oscuridad < 0.5:
        return "claro"
    if oscuridad < 0.85:
        return "oscuro"
    return "ultra"


def euclides(golpes, lugares, giro=0):
    """`golpes` repartidos lo más parejo posible en `lugares` (lista de booleanos)."""
    if lugares <= 0:
        return []
    golpes = max(0, min(golpes, lugares))
    return [((i + giro) * golpes) % lugares < golpes for i in range(lugares)]


def giros_anclados(golpes, lugares):
    """Giros del patrón que dejan un golpe en el primer lugar (el uno del compás)."""
    return [g for g in range(lugares) if euclides(golpes, lugares, g)[:1] == [True]]


class Voz:
    def __init__(self, cfg, papel, seed):
        self.papel = papel
        self.salida = cfg.get("salida", "FM-1")
        self.canal = int(cfg.get("canal", 4)) - 1
        self.golpes = max(1, int(cfg.get("golpes", 3)))
        self.octava = int(cfg.get("octava", 1))
        self.oscuridad = float(cfg.get("oscuridad", 0.7))
        self.gate = float(cfg.get("gate", 0.5))
        self.velocidad = int(cfg.get("velocidad", 100))
        self.vel_random = float(cfg.get("vel_random", 0.15))
        self.rng = random.Random(f"{papel}:{seed}")
        self.grados = NOTAS[color(self.oscuridad)][papel]
        # El ancla primero; después cada otra nota del color al menos una vez (si caben),
        # para que el color se escuche siempre; el resto, al azar dentro del color.
        otras = list(dict.fromkeys(g for g in self.grados[1:] if g != self.grados[0])) or [self.grados[0]]
        self.rng.shuffle(otras)
        self.orden = ([self.grados[0]] + otras + [self.rng.choice(self.grados) for _ in range(self.golpes)])[:self.golpes]
        self.giro = 0

    def mutar(self, cantidad, lugares, anclada):
        """Cambia una nota o gira el patrón; `cantidad` es la probabilidad de cambiar."""
        if self.rng.random() >= cantidad:
            return
        if len(self.orden) > 1 and self.rng.random() < 0.5:
            i = self.rng.randrange(1, len(self.orden))
            self.orden[i] = self.rng.choice(self.grados)
            return
        giros = giros_anclados(self.golpes, lugares) if anclada else list(range(lugares))
        giros = [g for g in giros if g != self.giro]
        if giros:
            self.giro = self.rng.choice(giros)


class Dialogo:
    def __init__(self, cfg, cfg_llamada, cfg_respuesta, tonica, escala, adaptacion):
        self.activo = bool(cfg.get("activo", False))
        self.modo = cfg.get("modo", "motor")
        self.forma = cfg.get("forma", "entrelazado")
        self.rejilla = cfg.get("rejilla", "corcheas")
        self.espacio = max(0, int(cfg.get("espacio", 1)))
        self.compases_turno = max(1, int(cfg.get("compases_turno", 2)))
        self.escucha = int(cfg.get("escucha", 4)) - 1
        self.seguir_pads = bool(cfg.get("seguir_pads", True))
        self.evolucion = float(cfg.get("evolucion", 0.5))
        self.mutar_cada = max(1, int(cfg.get("mutar_cada", 4)))
        self.seed = str(cfg.get("seed", "CR-0001"))
        for nombre, valor, opciones in (("modo", self.modo, MODOS), ("forma", self.forma, FORMAS),
                                        ("rejilla", self.rejilla, tuple(REJILLAS))):
            if valor not in opciones:
                raise ValueError(f"{nombre} debe ser una de: {', '.join(opciones)}")
        self.cfg_voces = (cfg_llamada, cfg_respuesta)
        self.tonalidad = Tonalidad(tonica, escala)
        self.adaptacion = adaptacion
        self.disparo = None  # lo resuelve el motor
        self.clip = None     # nombre del clip de diálogo que suena, si vino del disparador
        self.sonando = {}    # (salida, canal, nota) -> tick en que se apaga
        self.reiniciar()

    @property
    def paso_lugar(self):
        return REJILLAS[self.rejilla]

    @property
    def lugares(self):
        return PASOS_POR_COMPAS // self.paso_lugar

    def reiniciar(self):
        self.llamada = Voz(self.cfg_voces[0], "llamada", self.seed)
        self.respuesta = Voz(self.cfg_voces[1], "respuesta", self.seed)
        self.inicio = None      # compás donde empezó la conversación
        self.ultimo_paso = None
        self.plan = []          # (paso, voz, grado, dur, vel)
        self.fase = None
        self.raiz_vivo = None
        self.tocado = set()     # en vivo: lugares donde tocaste en este compás
        self.notas_vivo = []

    # --- Patrones de un compás ---

    def huecos(self, ocupados):
        """Lugares libres para la respuesta: fuera de los ocupados y esperando
        `espacio` lugares después de cada uno."""
        n = self.lugares
        return [i for i in range(n)
                if i not in ocupados and not any(1 <= (i - j) % n <= self.espacio for j in ocupados)]

    def lugares_llamada(self):
        patron = euclides(self.llamada.golpes, self.lugares, self.llamada.giro)
        return [i for i, x in enumerate(patron) if x]

    def lugares_respuesta(self, ocupados):
        if not ocupados:  # turno propio: su euclidiano en todo el compás
            patron = euclides(self.respuesta.golpes, self.lugares, self.respuesta.giro)
            return [i for i, x in enumerate(patron) if x]
        libres = self.huecos(ocupados)
        patron = euclides(min(self.respuesta.golpes, len(libres)), len(libres), self.respuesta.giro)
        return [h for h, x in zip(libres, patron) if x]

    def _compas(self, compas, paso, tocado=None):
        """Plan de un compás. En vivo, `tocado` son los lugares donde tocaste el compás anterior."""
        if self.modo == "en_vivo":
            golpes_l = []
            golpes_r = self.lugares_respuesta(set(tocado)) if tocado else []
            self.fase = "respuesta" if golpes_r else "escuchando"
        elif self.forma == "turnos":
            responde = (compas // self.compases_turno) % 2 == 1
            golpes_l = [] if responde else self.lugares_llamada()
            golpes_r = self.lugares_respuesta(set()) if responde else []
            self.fase = "respuesta" if responde else "llamada"
        else:
            golpes_l = self.lugares_llamada()
            golpes_r = self.lugares_respuesta(set(golpes_l))
            self.fase = "conversando"
        eventos = sorted([(i, self.llamada, self.llamada.orden[k % len(self.llamada.orden)])
                          for k, i in enumerate(golpes_l)]
                         + [(i, self.respuesta, self.respuesta.orden[k % len(self.respuesta.orden)])
                            for k, i in enumerate(golpes_r)], key=lambda e: e[0])
        # Cada nota dura según su largo, pero termina antes de que entre la siguiente
        # (de cualquier voz, también el uno del compás que viene): no se pisan.
        inicios = [i * self.paso_lugar for i, _, _ in eventos] + [PASOS_POR_COMPAS]
        self.plan = []
        for k, (i, voz, grado) in enumerate(eventos):
            inicio = i * self.paso_lugar
            hasta = inicios[k + 1] - inicio
            pasos = min(hasta * 0.9, max(0.5, voz.gate * min(hasta, LARGO_MAXIMO)))
            dur = max(1, round(pasos * TICKS_POR_PASO))
            vel = voz.velocidad + (8 if i == 0 else 0) + round(voz.vel_random * 20 * voz.rng.uniform(-1, 1))
            self.plan.append((paso + inicio, voz, grado, dur, max(1, min(127, vel))))

    def _mutar(self, compas):
        if self.evolucion > 0 and compas > 0 and compas % self.mutar_cada == 0:
            self.llamada.mutar(self.evolucion, self.lugares, anclada=True)
            self.respuesta.mutar(self.evolucion, self.lugares, anclada=False)

    # --- En vivo ---

    def entrada_on(self, nota, velocidad, tick):
        if not self.activo or self.modo != "en_vivo":
            return
        # Se cuantiza al lugar más cercano de la rejilla; al final del compás cuenta como el uno.
        largo_lugar = self.paso_lugar * TICKS_POR_PASO
        lugar = round((tick % (PASOS_POR_COMPAS * TICKS_POR_PASO)) / largo_lugar)
        self.tocado.add(lugar % self.lugares)
        self.notas_vivo.append(nota)

    def entrada_off(self, nota, tick):
        pass

    # --- Llamado por el motor en cada paso ---

    def paso(self, paso, tick, raiz, enviar, acorde=None):
        if not self.activo or paso == self.ultimo_paso:
            return
        if self.modo == "en_vivo":
            self.ultimo_paso = paso
            self._paso_vivo(paso, raiz, enviar)
            return
        if raiz is None:
            # Sin marcar el paso: si la nota larga llega un pulso tarde, el motor vuelve
            # a llamar en este mismo paso y la conversación igual empieza en el uno.
            if self.inicio is not None:
                self.apagar(enviar)
                self.reiniciar()
            return
        self.ultimo_paso = paso
        if self.inicio is None:
            if paso % PASOS_POR_COMPAS != 0:
                return  # la conversación empieza en un compás de la Circuit
            self.inicio = paso // PASOS_POR_COMPAS
        if paso % PASOS_POR_COMPAS == 0:
            compas = paso // PASOS_POR_COMPAS - self.inicio
            self._mutar(compas)
            self._compas(compas, paso)
        self._tocar(paso, raiz, enviar)

    def _paso_vivo(self, paso, raiz, enviar):
        if paso % PASOS_POR_COMPAS == 0:
            tocado, self.tocado = self.tocado, set()
            if tocado:
                # La respuesta queda en el registro de lo que tocaste.
                clase = (raiz if raiz is not None else self.tonalidad.tonica) % 12
                grave = min(self.notas_vivo) if self.notas_vivo else 48
                self.raiz_vivo = grave - ((grave - clase) % 12) - 12 * self.respuesta.octava
            self.notas_vivo = []
            self._mutar(paso // PASOS_POR_COMPAS)
            self._compas(paso // PASOS_POR_COMPAS, paso, sorted(tocado))
        self._tocar(paso, self.raiz_vivo, enviar)

    def _tocar(self, paso, raiz, enviar):
        if raiz is None:
            return
        for evento in [e for e in self.plan if e[0] == paso]:
            _, voz, grado, dur, vel = evento
            # Grados contados en la escala desde la raíz (la del acorde de los pads si
            # los sigue): nunca sale de la escala.
            nota = max(0, min(127, self.tonalidad.nota(raiz, grado, "escala") + 12 * voz.octava))
            clave = (voz.salida, voz.canal, nota)
            if clave in self.sonando:
                enviar(voz.salida, "note_off", voz.canal, nota, 0)
            enviar(voz.salida, "note_on", voz.canal, nota, vel)
            self.sonando[clave] = paso * TICKS_POR_PASO + dur
        self.plan = [e for e in self.plan if e[0] > paso]

    def tick(self, tick, enviar):
        for clave, fin in list(self.sonando.items()):
            if fin <= tick:
                salida, canal, nota = clave
                enviar(salida, "note_off", canal, nota, 0)
                del self.sonando[clave]

    def apagar(self, enviar):
        for salida, canal, nota in self.sonando:
            enviar(salida, "note_off", canal, nota, 0)
        self.sonando = {}
