"""Motor de FX: gestos cuantizados, notas largas con el filtro loco y el riser.

Un sinte propio (por defecto un canal de la MC-101; salida y canal se eligen) que
acompaña de fondo. Todo sale de la armonía (el acorde que suena o la escala), así
que nunca desafina, y todo cae en la rejilla:

- Gestos (zap, burbujas, ácido, glitch, barrido, gate, eco, escalera): cada uno
  dura tiempos enteros y empieza en un tiempo. «Dónde» decide su lugar: al final
  de cada frase de 4 compases, al final de cada compás o en cualquier tiempo. Qué
  gesto va en cada lugar se repite cada `repetir` compases (así se vuelve parte
  del tema en vez de sonar al azar); el «caos» va cambiando algunos en cada vuelta.
  La «locura» (que la energía sube y baja) decide cuántos lugares tienen gesto.
- Fondo: notas largas (la raíz, notas del acorde, quinta u octavas) que se
  renuevan cada tantos compases y cuando cambia el acorde, con el filtro moviéndose
  en ritmo: pluck (golpes euclidianos), pasos (una fila de 16 valores), sample &
  hold, wobble o rampa, en la división que elijas, más la resonancia en un ciclo
  desfasado (polirritmo). El caos mete locuras por tiempo: el doble de rápido,
  saltos de fusas, congelar.
- En una subida: el riser (golpes que se densifican, pitch que sube, filtro que
  baja y se abre). En el drop: la caída.

Las secuencias marcadas con FX también se intervienen (eso lo hace el motor,
ver motor._filtro_secuencias y motor._glitch).

Todo es determinista: misma variante, mismos gestos y el mismo filtro.
"""

import math
import random

from . import armonia

TICKS_POR_PASO = 6
PASOS_POR_COMPAS = 16
TICKS_POR_TIEMPO = 24
BEND_MAX = 8191
BEND_MIN = -8192

GESTOS = ("zap", "burbujas", "acido", "glitch", "barrido", "gate", "eco", "escalera")
# Cuántos tiempos dura cada gesto (todo lo que toca cabe ahí, y termina en un tiempo).
TIEMPOS = {"zap": 2, "burbujas": 1, "acido": 2, "glitch": 2, "barrido": 4, "gate": 2, "eco": 4, "escalera": 1}
# Los que mueven el filtro (mientras suenan, el fondo no lo toca).
CON_FILTRO = ("acido", "barrido", "gate", "eco", "escalera")

# Cuánto aparece cada gesto en cada género (0 = nunca).
PALETAS = {
    "goa": {"zap": 3, "burbujas": 2, "acido": 3, "glitch": 2, "barrido": 2, "gate": 2, "eco": 2, "escalera": 2},
    "psytrance": {"zap": 3, "burbujas": 1, "acido": 2, "glitch": 3, "barrido": 2, "gate": 3, "eco": 1, "escalera": 2},
    "psy_chill": {"zap": 1, "burbujas": 3, "acido": 1, "glitch": 1, "barrido": 2, "gate": 1, "eco": 3, "escalera": 1},
    "chillgressive": {"zap": 2, "burbujas": 2, "acido": 2, "glitch": 2, "barrido": 2, "gate": 2, "eco": 2, "escalera": 2},
    "chillout": {"zap": 1, "burbujas": 3, "acido": 0, "glitch": 0, "barrido": 2, "gate": 0, "eco": 3, "escalera": 1},
    "zenon": {"zap": 1, "burbujas": 2, "acido": 1, "glitch": 2, "barrido": 2, "gate": 1, "eco": 2, "escalera": 0},
    "ambient": {"zap": 0, "burbujas": 1, "acido": 0, "glitch": 0, "barrido": 2, "gate": 0, "eco": 2, "escalera": 0},
}
# Cuánto aparecen los gestos en cada género (multiplica la locura).
DENSIDAD_GENERO = {"goa": 1.0, "psytrance": 0.9, "psy_chill": 0.7, "chillgressive": 0.8, "chillout": 0.5, "zenon": 0.45, "ambient": 0.35}

DONDE = ("frase", "compas", "tiempo")
FONDO_NOTAS = ("raiz", "acorde", "quinta", "octavas")
FILTRO_MODOS = ("pluck", "pasos", "sh", "wobble", "rampa", "quieto")
# Divisiones del filtro, en pulsos (24 por negra).
DIVISIONES = {"32": 3, "16": 6, "8t": 8, "8": 12, "4": 24, "2": 48, "1c": 96, "2c": 192}

_ORDEN = {"off": 0, "bend": 1, "cc": 1, "cc2": 1, "on": 2}


def euclides(golpes, pasos=16, rotar=0):
    """Ritmo euclidiano: `golpes` repartidos lo más parejo posible en `pasos`."""
    golpes = max(0, min(pasos, golpes))
    return [((i + rotar) * golpes) % pasos < golpes for i in range(pasos)]


def curva_filtro(t, reposo, tope=127):
    """Valor del filtro en el avance `t` (0 a 1) de una subida: en el primer cuarto
    baja suave desde donde estaba hasta casi cerrado; después se abre de a poco,
    cada vez más rápido, hasta llegar a `tope` justo en el drop."""
    reposo = max(0, min(127, int(reposo)))
    cerrado = max(8, round(reposo * 0.2))
    t = max(0.0, min(1.0, t))
    if t < 0.25:
        x = t / 0.25
        return round(reposo + (cerrado - reposo) * (x * x * (3 - 2 * x)))  # baja en curva suave
    x = (t - 0.25) / 0.75
    return round(cerrado + (max(0, min(127, int(tope))) - cerrado) * x ** 1.6)


def avance(subida, paso):
    largo = max(1, subida["hasta"] - subida["desde"])
    return max(0.0, min(1.0, (paso - subida["desde"]) / largo))


def _f(x):
    return max(0.0, min(1.0, float(x)))


# Los 4 golpes de batería de la Circuit Tracks (canal 10): Drum 1, 2, 3 y 4.
KIT_CIRCUIT = (60, 62, 64, 65)


class Fx:
    def __init__(self, cfg, tonalidad):
        self.activo = bool(cfg.get("activo", False))
        self.salida = cfg.get("salida", "")
        self.canal = int(cfg.get("canal", 1)) - 1
        self.genero = cfg.get("genero", "goa")
        if self.genero not in PALETAS:
            raise ValueError(f"Género de FX desconocido: {self.genero!r}")
        self.locura = _f(cfg.get("locura", 0.4))
        self.caos = _f(cfg.get("caos", 0.2))
        self.donde = cfg.get("donde", "frase") if cfg.get("donde", "frase") in DONDE else "frase"
        self.repetir = max(1, int(cfg.get("repetir", 8)))
        self.seed = str(cfg.get("seed", "FX-0001"))
        self.octava = int(cfg.get("octava", 1))
        self.velocidad = int(cfg.get("velocidad", 100))
        self.gestos = tuple(g for g in GESTOS if cfg.get(g, True))
        self.riser = bool(cfg.get("riser", True))
        self.caida = bool(cfg.get("caida", True))
        self.kit = bool(cfg.get("kit_circuit", False))
        self.cc_corte = int(cfg.get("cc_corte", 74))
        self.reposo = int(cfg.get("filtro_reposo", 100))
        # Fondo: notas largas y el filtro en ritmo.
        self.fondo = bool(cfg.get("fondo", False))
        self.fondo_notas = cfg.get("fondo_notas", "raiz")
        self.fondo_largo = max(1, int(cfg.get("fondo_largo", 2)))
        self.fondo_octava = int(cfg.get("fondo_octava", 0))
        self.fondo_fuerza = int(cfg.get("fondo_fuerza", 90))
        self.filtro_modo = cfg.get("filtro_modo", "pluck")
        self.division = DIVISIONES.get(str(cfg.get("filtro_division", "16")), 6)
        self.golpes = int(cfg.get("filtro_golpes", 5))
        self.rotar = int(cfg.get("filtro_rotar", 0))
        self.caida_pluck = max(1, int(cfg.get("filtro_caida", 9)))
        self.filtro_min = int(cfg.get("filtro_min", 25))
        self.filtro_max = int(cfg.get("filtro_max", 115))
        self.movimiento = _f(cfg.get("movimiento", 1.0))
        self.resonancia = bool(cfg.get("resonancia", False))
        self.cc_resonancia = int(cfg.get("cc_resonancia", 71))
        self.reso_min = int(cfg.get("reso_min", 20))
        self.reso_max = int(cfg.get("reso_max", 90))
        self.reso_ciclo = max(1, int(cfg.get("reso_ciclo", 6)))
        self.ritmo = euclides(self.golpes, 16, self.rotar)
        self.tonalidad = tonalidad
        self.disparo = None
        self.eventos = []          # (tick, tipo, a, b): on (nota, vel), off (nota), bend (valor), cc / cc2 (valor)
        self.sonando = set()
        self.ocupado_hasta = -1    # tick hasta el que suena un gesto
        self.filtro_hasta = -1     # tick hasta el que un gesto (o la caída) maneja el filtro
        self.largas = ()           # notas largas del fondo que suenan
        self.bend = 0
        self.corte = None          # último valor del filtro mandado (None = no lo tocamos)
        self.reso = None
        self.ultimo = None         # último gesto (para la app)

    def _salida(self, enviar):
        """Con «baterías de la Circuit», las notas van a sus 4 golpes según la altura y no
        sale ni filtro ni pitch. Se envuelve una sola vez (los métodos se llaman entre sí)."""
        if not self.kit or getattr(enviar, "kit", False):
            return enviar

        def al_kit(salida, tipo, canal, a, b):
            if tipo in ("note_on", "note_off"):
                enviar(salida, tipo, canal, KIT_CIRCUIT[(int(a) % 12) * 4 // 12], b)
            elif tipo not in ("control_change", "pitchwheel"):
                enviar(salida, tipo, canal, a, b)
        al_kit.kit = True
        return al_kit

    # --- Estado ---

    def continuar_de(self, viejo, enviar):
        """Al cambiar la configuración en vivo: el gesto que suena termina solo."""
        crudo, enviar = enviar, self._salida(enviar)
        if viejo is None:
            return
        if (viejo.salida, viejo.canal, viejo.kit) == (self.salida, self.canal, self.kit):
            self.eventos, self.sonando = viejo.eventos, viejo.sonando
            self.ocupado_hasta, self.bend, self.corte = viejo.ocupado_hasta, viejo.bend, viejo.corte
            self.filtro_hasta, self.largas, self.reso = viejo.filtro_hasta, viejo.largas, viejo.reso
            self.ultimo = viejo.ultimo
            if not self.activo:
                self.apagar(enviar)
            elif not self.fondo:
                self._soltar_largas(enviar)
            if viejo.resonancia and not self.resonancia and self.reso is not None:
                enviar(self.salida, "control_change", self.canal, viejo.cc_resonancia, viejo.reso_min)
                self.reso = None
        else:
            viejo.apagar(crudo)   # el viejo se envuelve solo (con o sin baterías)

    def apagar(self, enviar):
        enviar = self._salida(enviar)
        for nota in sorted(self.sonando):
            enviar(self.salida, "note_off", self.canal, nota, 0)
        self.sonando = set()
        self.largas = ()
        self.eventos = []
        self.ocupado_hasta = self.filtro_hasta = -1
        self._reposar(enviar)

    def _soltar_largas(self, enviar):
        for nota in self.largas:
            if nota in self.sonando:
                enviar(self.salida, "note_off", self.canal, nota, 0)
                self.sonando.discard(nota)
        self.largas = ()

    def _reposar(self, enviar):
        """Deja el pitch al centro y el filtro (y la resonancia) donde los tenías."""
        if self.bend != 0:
            self.bend = 0
            enviar(self.salida, "pitchwheel", self.canal, 0, 0)
        if self.corte is not None and self.corte != self.reposo:
            enviar(self.salida, "control_change", self.canal, self.cc_corte, self.reposo)
        self.corte = None
        if self.reso is not None and self.reso != self.reso_min:
            enviar(self.salida, "control_change", self.canal, self.cc_resonancia, self.reso_min)
        self.reso = None

    # --- Reloj ---

    def tick(self, tick, enviar):
        enviar = self._salida(enviar)
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
            if a in self.sonando and not (b == "gesto" and a in self.largas):
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
        elif tipo == "cc2":
            a = max(0, min(127, int(a)))
            if a != self.reso:
                self.reso = a
                enviar(self.salida, "control_change", self.canal, self.cc_resonancia, a)

    def _programar(self, t0, eventos, filtro=False):
        # Los "off" de un gesto no apagan una nota larga del fondo que justo es la misma.
        self.eventos += [(t0 + dt, tipo, a, "gesto" if tipo == "off" else b) for dt, tipo, a, b in eventos]
        fin = t0 + max(dt for dt, *_ in eventos)
        self.ocupado_hasta = max(self.ocupado_hasta, fin)
        if filtro or any(tipo == "cc" for _, tipo, *_ in eventos):
            self.filtro_hasta = max(self.filtro_hasta, fin)

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
        enviar = self._salida(enviar)
        if not self.activo:
            return
        if raiz is None:
            self._soltar_largas(enviar)
            return
        if self.fondo:
            self._fondo(paso, tick, raiz, momento, subida, enviar)
        if subida is not None and self.riser:
            self._riser(paso, tick, raiz, momento, subida)
            return
        if paso % 4 == 0:
            self._gesto(paso, tick, raiz, momento)

    def _gesto(self, paso, tick, raiz, momento):
        """Los gestos empiezan en un tiempo y terminan justo antes de otro. Qué gesto va en
        cada lugar se repite cada `repetir` compases; el caos cambia algunos por vuelta."""
        if tick < self.ocupado_hasta or not self.gestos:
            return
        tiempo = paso // 4
        largo_lugar = {"frase": 16, "compas": 4, "tiempo": 1}[self.donde]
        lugar, dentro = divmod(tiempo, largo_lugar)
        ciclo = max(largo_lugar, self.repetir * 4) // largo_lugar   # lugares por vuelta
        vuelta, cual = divmod(lugar, ciclo)
        cambia = self._azar("caos", vuelta, cual).random() < self.caos
        azar = self._azar("lugar", cual, vuelta if cambia else 0)
        prob = self.locura * DENSIDAD_GENERO.get(self.genero, 1.0) * {"frase": 1.6, "compas": 0.9, "tiempo": 0.3}[self.donde]
        if azar.random() >= prob:
            return
        paleta = PALETAS[self.genero]
        opciones = [(g, paleta[g]) for g in self.gestos if paleta.get(g)
                    and (self.donde != "tiempo" or TIEMPOS[g] <= 2)]
        if not opciones:
            return
        total = sum(p for _, p in opciones)
        x = azar.random() * total
        for gesto, peso in opciones:
            x -= peso
            if x < 0:
                break
        # Al final de la frase o del compás: termina justo en el uno siguiente.
        empieza = largo_lugar - min(TIEMPOS[gesto], largo_lugar) if largo_lugar > 1 else 0
        if dentro != empieza:
            return
        eventos = getattr(self, "_" + gesto)(raiz, momento, azar)
        self.ultimo = gesto
        self._programar(tick, eventos, gesto in CON_FILTRO)

    # --- Fondo: notas largas y el filtro en ritmo ---

    def _notas_largas(self, raiz, momento, compas):
        base = raiz + 12 * (self.fondo_octava + 1)
        nota = _cerca(momento.raiz % 12, base) if momento is not None else self._acorde(base, None)
        vuelta = compas // self.fondo_largo
        if self.fondo_notas == "acorde" and momento is not None:
            tonos = sorted({_cerca(c, nota + 6) for c in momento.clases})
            return (tonos[vuelta % len(tonos)],)
        if self.fondo_notas == "quinta":
            return (nota, self.tonalidad.nota(nota, 4, "escala"))
        if self.fondo_notas == "octavas":
            return (nota + 12 * (vuelta % 2),)
        return (nota,)

    def _fondo(self, paso, tick, raiz, momento, subida, enviar):
        compas = paso // PASOS_POR_COMPAS
        if paso % 4 == 0:   # las notas largas solo cambian en un tiempo
            quiere = tuple(max(0, min(127, n)) for n in self._notas_largas(raiz, momento, compas))
            renovar = paso % (PASOS_POR_COMPAS * self.fondo_largo) == 0
            perdida = any(n not in self.sonando for n in self.largas)
            if renovar or perdida or set(quiere) != set(self.largas):
                for n in self.largas:
                    if n in self.sonando:
                        enviar(self.salida, "note_off", self.canal, n, 0)
                        self.sonando.discard(n)
                for n in quiere:
                    self._mandar("on", n, self.fondo_fuerza, enviar)
                self.largas = quiere
        if self.filtro_modo == "quieto" or tick < self.filtro_hasta or (subida is not None and self.riser):
            return
        for dt in range(TICKS_POR_PASO):
            t = tick + dt
            pos = self._filtro(t)
            if pos is not None:
                centro = (self.filtro_min + self.filtro_max) / 2
                medio = (self.filtro_max - self.filtro_min) / 2 * self.movimiento
                self.eventos.append((t, "cc", round(centro - medio + 2 * medio * pos), 0))
            if self.resonancia:
                fase = (t / (TICKS_POR_PASO * self.reso_ciclo)) % 1.0
                tri = 1 - abs(2 * fase - 1)
                self.eventos.append((t, "cc2", round(self.reso_min + (self.reso_max - self.reso_min) * tri), 0))

    def _filtro(self, t):
        """Dónde va el filtro (0 = abajo, 1 = arriba) en el pulso `t`."""
        modo, d = self.filtro_modo, self.division
        tiempo = t // TICKS_POR_TIEMPO
        vuelta = tiempo // max(4, self.repetir * 4)
        if self.caos > 0:
            loco = self._azar("filtro", vuelta, tiempo % max(4, self.repetir * 4))
            if loco.random() < self.caos * 0.3:
                locura = loco.choice(("doble", "saltos", "congelar"))
                if locura == "doble":
                    d = max(3, d // 2)
                elif locura == "saltos":
                    return self._azar("saltos", t // 3).random()
                else:
                    t = tiempo * TICKS_POR_TIEMPO   # congelado en lo que valía al empezar el tiempo
        if modo == "pluck":
            paso = t // TICKS_POR_PASO
            for atras in range(16):
                if self.ritmo[(paso - atras) % 16]:
                    pasado = t - (paso - atras) * TICKS_POR_PASO
                    return max(0.0, 1 - pasado / self.caida_pluck) ** 2
            return 0.0
        if modo == "pasos":
            k = t // d
            ciclo = max(4, self.repetir * 4) * TICKS_POR_TIEMPO
            gen = t // ciclo if self._azar("pasos", t // ciclo).random() < self.caos else 0
            return self._azar("valor", k % 16, gen).random()
        if modo == "sh":
            return self._azar("sh", t // d).random()
        if modo == "wobble":
            return 0.5 - 0.5 * math.cos(2 * math.pi * (t % d) / d)
        if modo == "rampa":
            return (t % d) / d
        return None

    # --- Gestos (eventos con pulsos relativos, siempre en la rejilla de fusas) ---

    def _zap(self, raiz, momento, azar):
        """Láser: una nota aguda con el pitch que cae en picada (a veces sube) en un tiempo, y su eco en el siguiente."""
        nota = self._acorde(self._registro(raiz) + 12, momento)
        baja = azar.random() < 0.75
        desde, hasta = (BEND_MAX, BEND_MIN) if baja else (BEND_MIN, BEND_MAX)
        ev = []
        for inicio, n, v in ((0, nota, self._vel()), (24, max(0, nota - 12), self._vel(0.6))):
            if inicio and azar.random() >= 0.5:
                continue
            ev += [(inicio, "bend", desde, 0), (inicio, "on", n, v)]
            for k in range(1, 11):
                ev.append((inicio + 2 * k, "bend", round(desde + (hasta - desde) * (k / 10) ** 0.6), 0))
            ev += [(inicio + 21, "off", n, 0), (inicio + 23, "bend", 0, 0)]
        return ev

    def _burbujas(self, raiz, momento, azar):
        """En un tiempo: 3 fusas que caminan por la escala, o 3 fusas y una semicorchea más larga."""
        nota = self._acorde(self._registro(raiz) + 12, momento)
        cuantas = 3 if azar.random() < 0.5 else 4
        ev = []
        for k in range(cuantas):
            larga = cuantas == 4 and k == 3
            if larga:
                nota = self._acorde(nota, momento)
            t = 3 * k if k < 3 else 12
            ev += [(t, "on", nota, self._vel(0.75 if k else 0.9)), (t + (10 if larga else 2), "off", nota, 0)]
            nota = self.tonalidad.nota(nota, azar.choice((1, 2, 1, -1, 3)), "escala")
        return ev

    def _acido(self, raiz, momento, azar):
        """Dos tiempos de 303: semicorcheas con slides, ♭2 y octava, y el filtro chillando en cada nota."""
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
            ev.append((47, "off", anterior, 0))
        ev.append((47, "cc", self.reposo, 0))
        return ev

    def _glitch(self, raiz, momento, azar):
        """Dos tiempos trabados: semicorcheas y redobles de fusas que saltan entre notas del
        acorde (octava, quinta), sin pitch bend: siempre afinado y en la rejilla."""
        nota = self._acorde(self._registro(raiz), momento)
        saltos = [nota, nota, min(127, nota + 12), self._acorde(nota + 7, momento), max(0, nota - 12)]
        ev = []
        for k in range(8):
            if azar.random() >= 0.65:
                continue
            t = k * TICKS_POR_PASO
            n = azar.choice(saltos)
            if azar.random() < 0.5:
                ev += [(t, "on", n, self._vel(0.9)), (t + 2, "off", n, 0),
                       (t + 3, "on", n, self._vel(0.75)), (t + 5, "off", n, 0)]
            else:
                ev += [(t, "on", n, self._vel(0.9)), (t + 4, "off", n, 0)]
        if not ev:
            ev = [(0, "on", nota, self._vel(0.9)), (4, "off", nota, 0)]
        return ev

    def _barrido(self, raiz, momento, azar):
        """Un compás: una nota larga con el filtro que se abre de cerrado a todo (o se cierra)."""
        nota = self._acorde(self._registro(raiz), momento)
        abre = azar.random() < 0.7
        ev = [(0, "on", nota, self._vel(0.85))]
        for k in range(33):
            x = k / 32
            x = x ** 1.7 if abre else 1 - x ** 0.6
            ev.append((3 * k if k < 32 else 95, "cc", round(12 + 115 * x), 0))
        ev.append((94, "off", nota, 0))
        return ev

    def _gate(self, raiz, momento, azar):
        """Dos tiempos: una nota que el filtro corta en semicorcheas (o fusas) con un ritmo euclidiano."""
        nota = self._acorde(self._registro(raiz), momento)
        rejilla = 3 if azar.random() < 0.35 else 6
        golpes = euclides(azar.choice((3, 5, 5, 7)), 8, azar.randrange(8))
        ev = [(0, "on", nota, self._vel(0.85))]
        for k in range(48 // rejilla):
            abierto = golpes[k % 8]
            ev.append((k * rejilla, "cc", 118 if abierto else 18, 0))
        ev += [(46, "off", nota, 0), (47, "cc", self.reposo, 0)]
        return ev

    def _eco(self, raiz, momento, azar):
        """Un compás: una nota y sus ecos cada corchea con puntillo, cada vez más suaves y más oscuros."""
        nota = self._acorde(self._registro(raiz) + 12 * azar.choice((0, 1)), momento)
        ev = []
        for k in range(5):
            t = 18 * k
            ev += [(t, "cc", round(120 - 18 * k), 0), (t, "on", nota, self._vel(0.95 * 0.72 ** k)), (t + 4, "off", nota, 0)]
        ev.append((95, "cc", self.reposo, 0))
        return ev

    def _escalera(self, raiz, momento, azar):
        """Un tiempo de fusas que suben por el acorde mientras el filtro se abre."""
        nota = self._acorde(self._registro(raiz), momento)
        clases = momento.clases if momento is not None else None
        ev = []
        for k in range(8):
            ev += [(3 * k, "cc", 40 + 11 * k, 0), (3 * k, "on", nota, self._vel(0.6 + 0.05 * k)), (3 * k + 2, "off", nota, 0)]
            siguiente = nota + 1
            while clases is not None and siguiente % 12 not in clases and siguiente < nota + 12:
                siguiente += 1
            nota = min(127, siguiente if clases is not None else self.tonalidad.nota(nota, 2, "escala"))
        ev.append((23, "cc", self.reposo, 0))
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
        enviar = self._salida(enviar)
        for nota in sorted(self.sonando):
            enviar(self.salida, "note_off", self.canal, nota, 0)
        self.sonando = set()
        self.largas = ()   # las notas largas del fondo vuelven en el próximo tiempo
        self.eventos = []
        self.ocupado_hasta = self.filtro_hasta = -1
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
