"""Motor de FX: zaps, burbujas, ácido, glitch, risers y caídas.

Un sinte propio (por defecto un canal de la MC-101) toca gestos cortos hechos de
notas, pitch bend y el CC del filtro. Las notas salen de la armonía (el acorde
que suena o la escala), así que las locuras nunca desafinan.

- Fuera de las subidas, los gestos aparecen de vez en cuando, más al final de
  cada frase de 4 compases. La "locura" (que la energía sube y baja) decide
  cuántos.
- En una subida, la voz de FX hace el riser: golpes que se van densificando
  (negras, corcheas, semicorcheas, fusas), el pitch subiendo hasta el drop y el
  filtro que primero baja y después se abre de a poco.
- En el drop: la caída (una nota que se desploma con el pitch y el filtro).

Las secuencias marcadas con FX también se intervienen (eso lo hace el motor,
ver motor._filtro_secuencias y motor._glitch): en la subida su filtro baja y
se abre igual que el del riser, y suman redobles cada vez más seguidos; fuera
de las subidas, a veces el último tiempo de la frase se traba (stutter).

Todo es determinista: misma variante, mismos gestos en los mismos lugares.
"""

import random

from . import armonia

TICKS_POR_PASO = 6
PASOS_POR_COMPAS = 16
BEND_MAX = 8191
BEND_MIN = -8192

GESTOS = ("zap", "burbujas", "acido", "glitch")

# Cuánto aparece cada gesto en cada género (0 = nunca).
PALETAS = {
    "goa": {"zap": 3, "burbujas": 2, "acido": 3, "glitch": 2},
    "psy_chill": {"zap": 1, "burbujas": 3, "acido": 1, "glitch": 1},
    "chillgressive": {"zap": 2, "burbujas": 2, "acido": 2, "glitch": 2},
    "chillout": {"zap": 1, "burbujas": 3, "acido": 0, "glitch": 0},
    "ambient": {"zap": 0, "burbujas": 1, "acido": 0, "glitch": 0},
}
# Cuánto aparecen los gestos en cada género (multiplica la locura).
DENSIDAD_GENERO = {"goa": 1.0, "psy_chill": 0.7, "chillgressive": 0.8, "chillout": 0.5, "ambient": 0.35}

_ORDEN = {"off": 0, "bend": 1, "cc": 1, "on": 2}


def curva_filtro(t, reposo):
    """Valor del filtro en el avance `t` (0 a 1) de una subida: en el primer cuarto
    baja suave desde donde estaba hasta casi cerrado; después se abre de a poco,
    cada vez más rápido, hasta quedar abierto justo en el drop."""
    reposo = max(0, min(127, int(reposo)))
    cerrado = max(8, round(reposo * 0.2))
    t = max(0.0, min(1.0, t))
    if t < 0.25:
        x = t / 0.25
        return round(reposo + (cerrado - reposo) * (x * x * (3 - 2 * x)))  # baja en curva suave
    x = (t - 0.25) / 0.75
    return round(cerrado + (127 - cerrado) * x ** 1.6)


def avance(subida, paso):
    largo = max(1, subida["hasta"] - subida["desde"])
    return max(0.0, min(1.0, (paso - subida["desde"]) / largo))


def _f(x):
    return max(0.0, min(1.0, float(x)))


class Fx:
    def __init__(self, cfg, tonalidad):
        self.activo = bool(cfg.get("activo", False))
        self.salida = cfg.get("salida", "")
        self.canal = int(cfg.get("canal", 1)) - 1
        self.genero = cfg.get("genero", "goa")
        if self.genero not in PALETAS:
            raise ValueError(f"Género de FX desconocido: {self.genero!r}")
        self.locura = _f(cfg.get("locura", 0.4))
        self.seed = str(cfg.get("seed", "FX-0001"))
        self.octava = int(cfg.get("octava", 1))
        self.velocidad = int(cfg.get("velocidad", 100))
        self.gestos = tuple(g for g in GESTOS if cfg.get(g, True))
        self.riser = bool(cfg.get("riser", True))
        self.caida = bool(cfg.get("caida", True))
        self.cc_corte = int(cfg.get("cc_corte", 74))
        self.reposo = int(cfg.get("filtro_reposo", 100))
        self.tonalidad = tonalidad
        self.disparo = None
        self.eventos = []          # (tick, tipo, a, b): on (nota, vel), off (nota), bend (valor), cc (valor)
        self.sonando = set()
        self.ocupado_hasta = -1    # tick hasta el que suena un gesto
        self.bend = 0
        self.corte = None          # último valor del filtro mandado (None = no lo tocamos)
        self.ultimo = None         # último gesto (para la app)

    # --- Estado ---

    def continuar_de(self, viejo, enviar):
        """Al cambiar la configuración en vivo: el gesto que suena termina solo."""
        if viejo is None:
            return
        if (viejo.salida, viejo.canal) == (self.salida, self.canal):
            self.eventos, self.sonando = viejo.eventos, viejo.sonando
            self.ocupado_hasta, self.bend, self.corte = viejo.ocupado_hasta, viejo.bend, viejo.corte
            self.ultimo = viejo.ultimo
            if not self.activo:
                self.apagar(enviar)
        else:
            viejo.apagar(enviar)

    def apagar(self, enviar):
        for nota in sorted(self.sonando):
            enviar(self.salida, "note_off", self.canal, nota, 0)
        self.sonando = set()
        self.eventos = []
        self.ocupado_hasta = -1
        self._reposar(enviar)

    def _reposar(self, enviar):
        """Deja el pitch al centro y el filtro donde lo tenías."""
        if self.bend != 0:
            self.bend = 0
            enviar(self.salida, "pitchwheel", self.canal, 0, 0)
        if self.corte is not None and self.corte != self.reposo:
            enviar(self.salida, "control_change", self.canal, self.cc_corte, self.reposo)
        self.corte = None

    # --- Reloj ---

    def tick(self, tick, enviar):
        if not self.eventos:
            return
        listos = sorted((e for e in self.eventos if e[0] <= tick), key=lambda e: (e[0], _ORDEN[e[1]]))
        if not listos:
            return
        self.eventos = [e for e in self.eventos if e[0] > tick]
        for _, tipo, a, b in listos:
            self._mandar(tipo, a, b, enviar)

    def _mandar(self, tipo, a, b, enviar):
        if tipo == "on":
            if a in self.sonando:
                enviar(self.salida, "note_off", self.canal, a, 0)
            enviar(self.salida, "note_on", self.canal, a, max(1, min(127, int(b))))
            self.sonando.add(a)
        elif tipo == "off":
            if a in self.sonando:
                enviar(self.salida, "note_off", self.canal, a, 0)
                self.sonando.discard(a)
        elif tipo == "bend":
            a = max(BEND_MIN, min(BEND_MAX, int(a)))
            if a != self.bend:
                self.bend = a
                enviar(self.salida, "pitchwheel", self.canal, a, 0)
        elif tipo == "cc":
            a = max(0, min(127, int(a)))
            if a != self.corte:
                self.corte = a
                enviar(self.salida, "control_change", self.canal, self.cc_corte, a)

    def _programar(self, t0, eventos):
        self.eventos += [(t0 + dt, tipo, a, b) for dt, tipo, a, b in eventos]
        fin = t0 + max(dt for dt, *_ in eventos)
        self.ocupado_hasta = max(self.ocupado_hasta, fin)

    # --- Notas ---

    def _registro(self, raiz):
        return raiz + 12 * (self.octava + 1)

    def _acorde(self, nota, momento):
        nota = max(0, min(127, nota))
        if momento is not None:
            return max(0, min(127, armonia.nota_del_acorde(nota, momento.clases)))
        return self.tonalidad.nota(nota, 0, "escala")

    def _azar(self, *clave):
        return random.Random(":".join(["fx", self.seed, *map(str, clave)]))

    def _vel(self, factor=1.0):
        return max(1, min(127, round(self.velocidad * factor)))

    # --- Cada paso ---

    def paso(self, paso, tick, raiz, momento, subida, enviar):
        """Llamado en cada paso con la nota larga (`raiz`), el acorde y la subida en curso."""
        if not self.activo or raiz is None:
            return
        if subida is not None and self.riser:
            self._riser(paso, tick, raiz, momento, subida)
            return
        if tick < self.ocupado_hasta or paso % 2 or not self.gestos:
            return
        compas, lugar = divmod(paso, PASOS_POR_COMPAS)
        azar = self._azar(paso)
        prob = self.locura * 0.08 * DENSIDAD_GENERO.get(self.genero, 1.0)
        if compas % 4 == 3:
            prob *= 3  # al final de la frase, más locuras
        if lugar == 0 and compas % 4 == 0:
            prob = 0  # el uno de la frase queda limpio
        if azar.random() >= prob:
            return
        paleta = PALETAS[self.genero]
        opciones = [(g, paleta[g]) for g in self.gestos if paleta.get(g)]
        if not opciones:
            return
        total = sum(p for _, p in opciones)
        x = azar.random() * total
        for gesto, peso in opciones:
            x -= peso
            if x < 0:
                break
        eventos = getattr(self, "_" + gesto)(raiz, momento, azar)
        self.ultimo = gesto
        self._programar(tick, eventos)

    # --- Gestos (eventos con ticks relativos) ---

    def _zap(self, raiz, momento, azar):
        """Láser: una nota aguda con el pitch que cae en picada (a veces sube), y a veces su eco."""
        nota = self._acorde(self._registro(raiz) + 12, momento)
        baja = azar.random() < 0.75
        desde, hasta = (BEND_MAX, BEND_MIN) if baja else (BEND_MIN, BEND_MAX)
        ev = [(0, "bend", desde, 0), (0, "on", nota, self._vel())]
        pasos = 12
        for k in range(1, pasos + 1):
            ev.append((2 * k, "bend", round(desde + (hasta - desde) * (k / pasos) ** 0.6), 0))
        ev += [(22, "off", nota, 0), (24, "bend", 0, 0)]
        if azar.random() < 0.4:  # eco una octava abajo, más suave
            eco = max(0, nota - 12)
            ev.append((36, "bend", desde, 0))
            ev.append((36, "on", eco, self._vel(0.6)))
            for k in range(1, pasos + 1):
                ev.append((36 + 2 * k, "bend", round(desde + (hasta - desde) * (k / pasos) ** 0.6), 0))
            ev += [(58, "off", eco, 0), (60, "bend", 0, 0)]
        return ev

    def _burbujas(self, raiz, momento, azar):
        """3 notas cortas y rápidas (o 3 cortas y una larga) que caminan por la escala."""
        nota = self._acorde(self._registro(raiz) + 12, momento)
        cuantas = 3 if azar.random() < 0.5 else 4
        ev = []
        for k in range(cuantas):
            larga = cuantas == 4 and k == 3
            if larga:
                nota = self._acorde(nota, momento)
            ev += [(4 * k, "on", nota, self._vel(0.75 if k else 0.9)),
                   (4 * k + (14 if larga else 2), "off", nota, 0)]
            nota = self.tonalidad.nota(nota, azar.choice((1, 2, 1, -1, 3)), "escala")
        return ev

    def _acido(self, raiz, momento, azar):
        """Un pedacito de 303: semicorcheas con slides, ♭2 y octava, y el filtro chillando en cada nota."""
        base = self._acorde(self._registro(raiz) - 12, momento)
        grados = (0, 0, 7, 1, 0, 4, 7, 0)
        ev = [(0, "cc", 30, 0)]
        anterior = None
        for k in range(8):
            if k and azar.random() < 0.2:
                continue  # un silencio
            nota = max(0, min(127, self.tonalidad.nota(base, azar.choice(grados), "escala")))
            t = k * TICKS_POR_PASO
            acento = azar.random() < 0.35
            slide = k < 7 and azar.random() < 0.3
            if anterior is not None and anterior != nota:
                ev.append((t, "off", anterior, 0))
            ev.append((t, "on", nota, self._vel(1.0 if acento else 0.8)))
            ev.append((t, "cc", 100 + (25 if acento else 0), 0))
            ev.append((t + 3, "cc", 40, 0))
            if slide:
                anterior = nota  # se pisa con la siguiente: un sinte en legato se desliza
            else:
                ev.append((t + 3, "off", nota, 0))
                anterior = None
        if anterior is not None:
            ev.append((48, "off", anterior, 0))
        ev.append((48, "cc", self.reposo, 0))
        return ev

    def _glitch(self, raiz, momento, azar):
        """Dos tiempos trabados: ráfagas de fusas con saltos de pitch, siempre en la rejilla."""
        nota = self._acorde(self._registro(raiz), momento)
        saltos = (0, 0, 2048, -2048, 4096, -4096, BEND_MAX)
        ev = []
        for k in range(8):
            if azar.random() >= 0.65:
                continue
            t = k * TICKS_POR_PASO
            n = min(127, nota + 12) if azar.random() < 0.3 else nota
            ev.append((t, "bend", azar.choice(saltos), 0))
            if azar.random() < 0.5:
                ev += [(t, "on", n, self._vel(0.9)), (t + 2, "off", n, 0),
                       (t + 3, "on", n, self._vel(0.75)), (t + 5, "off", n, 0)]
            else:
                ev += [(t, "on", n, self._vel(0.9)), (t + 4, "off", n, 0)]
        if not ev:
            ev = [(0, "on", nota, self._vel(0.9)), (4, "off", nota, 0)]
        ev.append((48, "bend", 0, 0))
        return ev

    # --- Subida y drop ---

    def _riser(self, paso, tick, raiz, momento, subida):
        """Golpes que se van densificando, pitch que sube y filtro que baja y se abre."""
        t = avance(subida, paso)
        if tick < self.ocupado_hasta:
            return  # termina el gesto que sonaba
        i = paso - subida["desde"]
        cada = 4 if t < 0.25 else 2 if t < 0.5 else 1
        ev = [(0, "bend", round(BEND_MAX * t ** 1.5), 0), (0, "cc", curva_filtro(t, self.reposo), 0)]
        if i % cada == 0:
            nota = self._registro(raiz)
            if momento is not None:
                nota = _cerca(momento.raiz % 12, nota)
            vel = self._vel(0.45 + 0.6 * t)
            if t >= 0.75:  # el último cuarto, fusas
                ev += [(0, "on", nota, vel), (2, "off", nota, 0), (3, "on", nota, vel), (5, "off", nota, 0)]
            else:
                ev += [(0, "on", nota, vel), (3, "off", nota, 0)]
        self.ultimo = "riser"
        self.eventos += [(tick + dt, tipo, a, b) for dt, tipo, a, b in ev]

    def drop(self, tick, raiz, momento, enviar, caida=True):
        """Termina la subida: el riser se corta y, si está la caída, una nota se desploma."""
        for nota in sorted(self.sonando):
            enviar(self.salida, "note_off", self.canal, nota, 0)
        self.sonando = set()
        self.eventos = []
        self.ocupado_hasta = -1
        if not (self.activo and self.caida and caida and raiz is not None):
            self._reposar(enviar)
            return
        nota = self._acorde(self._registro(raiz) + 12, momento)
        largo = 2 * PASOS_POR_COMPAS * TICKS_POR_PASO  # dos compases
        ev = [(0, "bend", BEND_MAX, 0), (0, "cc", 127, 0), (0, "on", nota, self._vel())]
        for k in range(1, 33):
            x = k / 32
            ev.append((k * 6, "bend", round(BEND_MAX + (BEND_MIN - BEND_MAX) * x ** 0.8), 0))
            ev.append((k * 6, "cc", round(127 - (127 - self.reposo * 0.4) * x), 0))
        ev += [(largo - 2, "off", nota, 0), (largo, "bend", 0, 0), (largo, "cc", self.reposo, 0)]
        self.ultimo = "caida"
        self._programar(tick, ev)
        self.tick(tick, enviar)  # la caída parte justo en el uno


def _cerca(clase, referencia):
    n = referencia - (referencia - clase) % 12
    return n + 12 if referencia - n > 6 else n
