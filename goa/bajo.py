"""Generador de líneas de bajo.

A diferencia de una secuencia (un motivo que se repite sobre una nota base),
el bajo sabe hacia dónde va la armonía (ver armonia.py):

- Toca la raíz del acorde de los pads, y elige raíz, quinta, octava o una nota
  de paso según el estilo y el movimiento.
- Con armonía guiada y "anticipar", la última nota antes de un cambio de acorde
  es una nota de aproximación: un paso de escala junto a la raíz que viene.
- Frases de 2, 4 u 8 compases: los compases se repiten igual y el último cierra
  con un remate, que alterna entre dos variantes.
- Evolución: cada "mutar cada" compases puede cambiar un golpe (otra nota,
  silencio, uno nuevo, o correrlo), y los cambios se acumulan. A veces un golpe
  vuelve a como era, para que no se aleje demasiado.
- En los estilos psy nunca cae en el tiempo (ahí va el bombo).
- Monofónico: una nota nueva corta la anterior, salvo el slide, que se pisa
  un instante para que un sinte en legato se deslice.

Todo es determinista: misma variante, mismo bajo y misma evolución.
"""

import math
import random

from .azar import azar
from dataclasses import dataclass, replace

TICKS_POR_PASO = 6
PASOS_POR_COMPAS = 16
TICKS_POR_COMPAS = TICKS_POR_PASO * PASOS_POR_COMPAS

ESTILOS = ("rolling", "fullon", "galope", "offbeat", "saltado", "tresillo", "chillgressive", "sincopado", "trote", "zenon", "dub", "sub")
ALIAS = {"psy_chill": "galope", "deepnotic": "offbeat"}  # nombres que tuvo (0.18) o estilos que se sacaron (0.45)
PSY = {"rolling", "fullon", "galope", "offbeat", "saltado", "tresillo", "chillgressive", "sincopado", "trote", "zenon"}


@dataclass(frozen=True)
class Golpe:
    dur: int            # ticks
    retraso: int = 0    # ticks después del paso (tresillos)
    grado: int = 0      # grado de escala desde la raíz del acorde
    fusa: object = None  # remate en fusas: grado de la segunda fusa (el golpe se parte en dos)
    caida: bool = False  # nota larga zenon: el pitch bend la hace caer mientras suena


def _cada_tiempo(lugares, dur, retrasos=None):
    """Golpes repetidos en los 4 tiempos: `lugares` dentro del tiempo (0 a 3)."""
    return {t * 4 + l: Golpe(dur, (retrasos or {}).get(l, 0)) for t in range(4) for l in lugares}


# Golpes de cada estilo en el compás: lugar (semicorchea) -> Golpe.
BASES = {
    "rolling": _cada_tiempo((1, 2, 3), 6),                 # K B B B
    "fullon": _cada_tiempo((1, 2, 3), 6),                  # K B B B con una celda melódica por tiempo
    "galope": _cada_tiempo((2, 3), 6),                     # K · B B
    "offbeat": _cada_tiempo((2,), 12),                     # K · B ·  (una corchea a contratiempo)
    "saltado": _cada_tiempo((1, 3), 6),                    # K B · B
    "tresillo": _cada_tiempo((1, 2), 8, {1: 2, 2: 4}),     # K y dos de tresillo (ticks 8 y 16 del tiempo)
    "chillgressive": _cada_tiempo((1, 2, 3), 6),           # rolling oscuro, acento que se mueve
    # Sincopado progresivo (Chakra Bass 3, 12, 15): lejos del bombo, notas largas en
    # «y» y «a» del tiempo; cambia de nota con el acorde.
    "sincopado": {2: Golpe(6), 3: Golpe(12), 6: Golpe(12), 10: Golpe(6), 11: Golpe(12), 14: Golpe(12)},
    # Trote 3-3-2 (Progressive 001 y 019, Apex 019): ·B·B··B··B·B··B· — grupos de 3+3+2
    # entre los bombos, nunca en el tiempo.
    "trote": {l: Golpe(6) for l in (1, 3, 6, 9, 11, 14)},
    "zenon": None,  # sale de MASCARAS_ZENON según la variante (ver _base)
    "dub": {0: Golpe(30), 7: Golpe(12), 10: Golpe(24)},    # en el uno, antes del tres y en el tres
    "sub": {0: Golpe(TICKS_POR_COMPAS)},                   # una nota por compás, ligada: casi un drone
}

# Remates del final de la frase: lugar -> grado de escala desde la raíz. Dos por estilo,
# que se alternan frase a frase. Con «variación», cada frase cambia algunas de sus
# notas al azar (repetible con la seed). Desde el tiempo donde empieza el remate se
# reemplaza el patrón. En los estilos psy nunca caen en el bombo (lugares 0, 4, 8, 12).
REMATES = {
    # rolling: rebote de octava en los tiempos 3 y 4 · corrida que baja 8-7-5 | 4-2-1
    "rolling": ({9: 0, 10: 7, 11: 0, 13: 7, 14: 4, 15: 7}, {9: 7, 10: 6, 11: 4, 13: 3, 14: 1, 15: 0}),
    "fullon": ({13: 7, 14: 6, 15: 4}, {13: 1, 14: 0, 15: 7}),
    "galope": ({14: 7, 15: 4}, {14: 4, 15: 6}),
    # offbeat: los clásicos (corrida al final); junto al bombo nunca va una nota grave
    "offbeat": ({13: 7, 14: 4, 15: 0}, {14: 7, 15: 6}),
    "saltado": ({13: 7, 15: 4}, {13: 4, 14: 6, 15: 7}),
    "tresillo": ({13: 7, 14: 4}, {13: 4, 14: 6}),
    "chillgressive": ({13: 0, 14: 7, 15: 6}, {13: 4, 14: 6, 15: 7}),
    "sincopado": ({11: 4, 14: 7}, {10: 6, 11: 4, 14: 1}),
    "trote": ({14: 0, 15: 6}, {11: 4, 14: 7, 15: 6}),   # Progressive 001: cierra en la ♭7
    "zenon": ({13: 7, 15: 6}, {11: 1, 14: 0}),          # octava que cae a la ♭7 · ♭2 que vuelve
    "dub": ({14: 4}, {13: 6, 15: 4}),
    "sub": ({}, {}),
}
# Zenonesque / swampy: notas largas, a veces sincopadas (empiezan en la «y» o la «a» y se
# sostienen por encima del bombo). Nunca empiezan en el bombo. (lugar, largo en pasos);
# la variante elige una.
MASCARAS_ZENON = (
    # Dekel & Ilan Or, «Sons of Earth» (140 BPM, medido en el audio): cada tiempo una nota
    # larga que entra después del bombo y dura hasta el siguiente; en el 4 se parte (la de
    # la «a» anticipa el uno). Las del 1 y el 3 hacen un arco de altura (ver `arco`).
    ((1, 3), (6, 2), (9, 3), (13, 1), (15, 1)),
    ((1, 3), (5, 3), (9, 3), (13, 3)),            # larga después de cada bombo
    ((1, 3), (6, 5), (13, 3)),                     # la del medio entra en la «y» y cruza el bombo
    ((2, 2), (5, 3), (10, 5), (15, 1)),
    ((1, 6), (9, 3), (14, 2)),                     # la primera se queda por encima del 2
    ((3, 4), (7, 2), (11, 4), (15, 1)),            # anticipadas: entran en la «a» y cruzan el bombo
    ((1, 2), (3, 3), (9, 2), (11, 4)),
    ((1, 7), (10, 3), (14, 2)),                    # medio compás largo y respuesta sincopada
    ((2, 3), (6, 2), (9, 4), (14, 2)),
)

# Remates sacados de los bajos de la carpeta de MIDIs (Zenhiser Apex, 0.92): siempre en
# la segunda mitad del compás, sobre el rolling (lugar -> grado). Con «remates de los
# packs», en esa proporción de frases el remate es uno de estos en vez del clásico.
REMATES_PACK = (
    {9: 0, 10: 0, 11: 6, 13: 0, 14: 7, 15: 0},   # ♭7 y octava (Apex 001, 006, 009, 045)
    {9: 0, 10: 0, 11: 1, 13: 0, 14: 2, 15: 0},   # ♭2 y ♭3 (Apex 042)
    {9: 0, 10: 0, 11: 0, 13: 0, 14: 2, 15: 1},   # ♭3 que cae al ♭2 (Apex 048)
    {9: 0, 10: 0, 11: 0, 13: 0, 14: 0, 15: 2},   # solo la última sube al ♭3 (Apex 041)
    {9: 1, 10: 1, 11: 1, 13: 1, 14: 1, 15: 1},   # media frase en el ♭2 (Apex 047)
    {9: 2, 10: 2, 11: 2, 13: 2, 14: 2, 15: 2},   # media frase en el ♭3 (Apex 007)
    {9: 0, 10: 0, 11: 0, 13: -1, 14: -1, 15: -1},  # el último tiempo un grado abajo (Apex 050)
)
CON_REMATES_PACK = ("rolling", "fullon", "chillgressive")
# Ciclo de alturas (zenonesque): el ritmo queda fijo y las notas de la raíz rotan por un
# ciclo de 5 o 7 grados; como no calza con el compás (12 notas en el rolling, 6 en el
# trote), cae distinto cada vez y vuelve a empezar recién después de 5 o 7 compases.
# (Uno de 3 no sirve: en el rolling calza justo con el tiempo y todos los compases son iguales.)
CICLOS = {5: (0, 0, 1, 0, 7), 7: (0, 0, 7, 0, 1, 0, 4)}
# Grados que puede tomar una nota variada del remate, según el rango elegido.
GRADOS_REMATE = {"quinta": (0, 1, 2, 3, 4), "octava": (0, 1, 3, 4, 6, 7)}

# «Notas que suben»: caminos de grados para los 4 tiempos del compás, de la raíz hacia
# arriba (como los bajos full-on que no se quedan en la raíz). El control elige cuántos
# tiempos suben, si sube una o dos notas por tiempo y hasta dónde llega el camino.
CAMINOS = ((0, 1, 0, 2), (0, 0, 1, 2), (0, 2, 1, 2), (0, 1, 2, 2), (0, 2, 0, 1),
           (0, 1, 2, 3), (0, 1, 2, 4), (0, 2, 3, 4), (0, 0, 2, 4), (0, 1, 3, 4),
           (0, 2, 4, 7), (0, 3, 4, 6), (0, 2, 4, 6), (0, 4, 6, 7))
SIN_SUBE = ("dub", "sub")

# Celdas melódicas del full-on: grados de los 3 golpes de cada tiempo (el ♭2 en frigio es muy Goa).
CELDAS = [(0, 0, 7), (0, 0, 1), (0, 7, 0), (0, 0, 4), (0, 1, 0), (0, 4, 7), (0, 0, 0), (7, 0, 0)]

# Movimiento: (dónde, grado, probabilidad) para cada estilo.
MOVIMIENTOS = {
    "rolling": [(lambda l: l % 4 == 3, 7, 0.5), (lambda l: l % 4 == 2, 4, 0.25)],
    "fullon": [(lambda l: l % 4 == 3, 7, 0.3)],
    "galope": [(lambda l: l % 4 == 3, 4, 0.5), (lambda l: l % 4 == 3, 1, 0.25)],
    "offbeat": [(lambda l: l % 8 == 6, 7, 0.5), (lambda l: l % 8 == 2, 4, 0.3)],
    "saltado": [(lambda l: l % 4 == 3, 7, 0.5), (lambda l: l % 4 == 1, 4, 0.2)],
    "tresillo": [(lambda l: l % 4 == 2, 7, 0.5)],
    "chillgressive": [(lambda l: l % 4 == 3, 7, 0.4), (lambda l: l % 4 == 1, 4, 0.2)],
    "sincopado": [(lambda l: l in (6, 14), 4, 0.4), (lambda l: l == 11, 7, 0.3)],
    "trote": [(lambda l: l in (6, 14), 4, 0.3), (lambda l: l == 11, 7, 0.3)],
    "zenon": [(lambda l: l >= 10, 1, 0.25), (lambda l: 5 <= l < 10, 7, 0.25)],
    "dub": [(lambda l: l == 7, 7, 0.6), (lambda l: l == 10, 4, 0.6)],
    "sub": [],
}

GRADOS_MUTACION = (0, 4, 7, 1, -1, 3)



class Bajo:
    def __init__(self, cfg, tonalidad):
        self.activo = bool(cfg.get("activo", False))
        self.salida = cfg.get("salida", "")
        self.canal = int(cfg.get("canal", 4)) - 1
        self.estilo = ALIAS.get(cfg.get("estilo", "rolling"), cfg.get("estilo", "rolling"))
        if self.estilo not in ESTILOS:
            raise ValueError(f"Estilo de bajo desconocido: {self.estilo!r}. Opciones: {', '.join(ESTILOS)}")
        self.octava = int(cfg.get("octava", 0))
        self.transponer = int(cfg.get("transponer", 0))
        self.gate = max(0.05, min(1.0, float(cfg.get("gate", 0.6))))
        self.velocidad = int(cfg.get("velocidad", 100))
        self.vel_random = float(cfg.get("vel_random", 0.1))
        self.movimiento = _fraccion(cfg.get("movimiento", 0.3))
        self.sube = _fraccion(cfg.get("sube", 0.0))
        self.evolucion = _fraccion(cfg.get("evolucion", 0.0))
        self.mutar_cada = max(1, int(cfg.get("mutar_cada", 4)))
        self.densidad = _fraccion(cfg.get("densidad", 1.0))
        self.swing = max(0.0, min(0.5, float(cfg.get("swing", 0.0))))
        self.slide = _fraccion(cfg.get("slide", 0.0))
        self.acentos = _fraccion(cfg.get("acentos", 0.2))
        self.fantasmas = _fraccion(cfg.get("fantasmas", 0.0))
        self.remates = bool(cfg.get("remates", True))
        self.remate_var = _fraccion(cfg.get("remate_var", 0.3))       # notas del remate que cambian
        self.remate_rango = cfg.get("remate_rango", "octava")
        if self.remate_rango not in GRADOS_REMATE:
            self.remate_rango = "octava"
        self.remate_marca = _fraccion(cfg.get("remate_marca", 1.0))
        # Remate en fusas (Apex 027, Ghosthack Riff 7): en esa proporción de frases, las
        # últimas notas del compás que cierra se parten en dos fusas (un redoble corto
        # antes del uno). Con más de 60 % también el final del tiempo 3.
        self.fusas = _fraccion(cfg.get("fusas", 0.0))
        self.remates_pack = _fraccion(cfg.get("remates_pack", 0.0))  # frases con un remate de los packs
        # Nota larga zenonesque: en esa proporción de frases, el compás antes del que cierra
        # cambia su segunda mitad por una sola nota larga que entra justo después del
        # bombo (no en el contratiempo como un bajo con glide) y cae de altura con el
        # pitch bend (`caida` semitonos; `bend_rango` = el rango de bend del sinte).
        self.zenon = _fraccion(cfg.get("zenon", 0.0))
        self.caida = max(0, min(24, int(cfg.get("caida", 0))))
        self.bend_rango = max(1, min(24, int(cfg.get("bend_rango", 12))))
        self.bends = []          # (tick, valor) pendientes
        self.bend_movido = False
        # Arco de altura (medido en «Sons of Earth»): en esa proporción de las notas largas
        # (más de 2 pasos: allá las de 3 pasos arquean y las de 2 quedan rectas) el pitch
        # bend sube `arco_alto` semitonos y vuelve mientras suena.
        self.arco = _fraccion(cfg.get("arco", 0.0))
        self.arco_alto = max(1, min(24, int(cfg.get("arco_alto", 12))))
        ciclo = int(cfg.get("ciclo", 0) or 0)
        self.ciclo = ciclo if ciclo in CICLOS else 0
        # Filtro automático por CC (opcional): se abre de a poco y vuelve a cerrarse.
        self.filtro = bool(cfg.get("filtro", False))
        self.filtro_cc = max(0, min(127, int(cfg.get("filtro_cc", 74))))
        self.filtro_min = max(0, min(127, int(cfg.get("filtro_min", 25))))
        self.filtro_max = max(0, min(127, int(cfg.get("filtro_max", 100))))
        self.filtro_ciclo = max(1, int(cfg.get("filtro_ciclo", 32)))
        self.filtro_forma = cfg.get("filtro_forma", "sube")
        self.filtro_nota = _fraccion(cfg.get("filtro_nota", 0.5))  # golpe de filtro en el ataque de cada nota
        self.filtro_ancla = 0
        self.filtro_ultimo = None
        self.cc_pendientes = []  # (tick, valor o None = volver al filtro de base)
        # Portamento por CC (opcional): el motor prende el glide del sinte (CC 65) y su tiempo (CC 5).
        self.porta = bool(cfg.get("porta", False))
        self.porta_tiempo = max(0, min(127, int(cfg.get("porta_tiempo", 30))))
        self.porta_enviado = None
        self.remate_largas = _fraccion(cfg.get("remate_largas", 0.0))  # frases con una nota larga
        self.remate_largo = max(0.3, min(1.0, float(cfg.get("remate_largo", 0.75))))  # cuánto del hueco ocupa   # 0 = como el resto, 1 = acentuado y sin slide
        self.frase = max(1, int(cfg.get("frase", 4)))
        self.armonia = cfg.get("armonia", "general")
        self.seed = str(cfg.get("seed", "B-0001"))
        self.tonalidad = tonalidad
        self.disparo = None
        self.base = self._base()
        self.sonando = {}     # nota -> tick en que se apaga
        self.pendientes = []  # (tick, nota, velocidad, fin)
        self.reiniciar()

    # --- Patrón y evolución ---

    def _azar(self, *clave):
        return azar(":".join(["bajo", self.seed, *map(str, clave)]))

    def _base(self):
        """Compás base del estilo con el movimiento aplicado (fijo para una variante)."""
        base = dict(BASES[self.estilo] or self._mascara_zenon())
        if self.estilo == "fullon":
            celdas = [CELDAS[int(self._azar("celda", t) * len(CELDAS))] for t in range(4)]
            base = {l: replace(g, grado=celdas[l // 4][l % 4 - 1]) for l, g in base.items()}
        for lugar, golpe in base.items():
            for donde, grado, prob in MOVIMIENTOS[self.estilo]:
                if golpe.grado == 0 and donde(lugar) and self._azar(lugar, grado) < prob * self.movimiento * 2:
                    base[lugar] = replace(golpe, grado=grado)
                    break
        return base

    def _mascara_zenon(self):
        mascara = MASCARAS_ZENON[int(self._azar("zenon-mascara") * len(MASCARAS_ZENON))]
        return {l: Golpe(largo * TICKS_POR_PASO) for l, largo in mascara}

    def reiniciar(self):
        self.patron = dict(self.base)
        self.mutado_hasta = -1  # último compás en que se aplicó la evolución

    def continuar_de(self, viejo):
        """Al cambiar la configuración en vivo: si el patrón base es el mismo, sigue con lo mutado."""
        if viejo.base == self.base and viejo.seed == self.seed:
            self.patron = dict(viejo.patron)
            self.mutado_hasta = viejo.mutado_hasta
        self.filtro_ancla = viejo.filtro_ancla  # el filtro sigue abriéndose donde iba
        self.porta_enviado = viejo.porta_enviado  # el portamento solo se manda si cambió
        if self.filtro_cc == viejo.filtro_cc:
            self.filtro_ultimo = viejo.filtro_ultimo

    def evolucionar(self, compas):
        """Llamado al inicio de cada compás: cada `mutar_cada` compases puede cambiar un golpe."""
        if compas <= self.mutado_hasta:
            return
        self.mutado_hasta = compas
        if not self.evolucion or compas == 0 or compas % self.mutar_cada:
            return
        rng = random.Random(f"bajo:{self.seed}:mutar:{compas}")
        if rng.random() >= self.evolucion:
            return
        libres = [l for l in range(PASOS_POR_COMPAS)
                  if l not in self.patron and not (self.estilo in PSY and l % 4 == 0)]
        distintos = [l for l in self.patron if self.patron[l] != self.base.get(l)] + \
                    [l for l in self.base if l not in self.patron]
        operaciones = ["nota", "nota", "mover", "silencio", "agregar"] + (["volver"] if distintos else [])
        op = rng.choice(operaciones)
        lugares = sorted(self.patron)
        if not lugares or self.estilo == "sub":
            op = "nota" if lugares else "volver"
        # En dub y sub, la nota del uno es el ancla: puede cambiar de altura, pero no se mueve ni se calla.
        movibles = [l for l in lugares if not (l == 0 and self.estilo in ("dub", "sub"))]
        if op == "nota":
            l = rng.choice(lugares)
            opciones = [g for g in GRADOS_MUTACION if g != self.patron[l].grado]
            self.patron[l] = replace(self.patron[l], grado=rng.choice(opciones))
        elif op == "silencio" and len(lugares) > max(1, len(self.base) // 2) and movibles:
            del self.patron[rng.choice(movibles[1:] or movibles)]
        elif op == "agregar" and libres and len(lugares) < len(self.base) + 3:
            dur = 12 if self.estilo == "dub" else 6
            self.patron[rng.choice(libres)] = Golpe(dur, 0, rng.choice((0, 7, 4)))
        elif op == "mover" and movibles:
            l = rng.choice(movibles)
            destinos = [d for d in (l - 1, l + 1) if d in libres]
            if destinos:
                self.patron[rng.choice(destinos)] = replace(self.patron.pop(l), retraso=0)
        elif op == "volver" and distintos:
            l = rng.choice(distintos)
            if l in self.base:
                self.patron[l] = self.base[l]
            else:
                del self.patron[l]

    def golpes(self, compas):
        """Golpes de un compás: el patrón (con lo mutado), la densidad, las notas fantasma y el remate."""
        golpes = {l: g for i, (l, g) in enumerate(sorted(self.patron.items()))
                  if i == 0 or self._azar("densidad", l) < self.densidad}
        if self.ciclo and self.estilo not in SIN_SUBE:
            golpes = self._ciclar(golpes, compas)
        if self.sube and self.estilo not in SIN_SUBE:
            golpes = self._subir(golpes, compas)
        if self.fantasmas:
            for l in range(PASOS_POR_COMPAS):
                if (l not in golpes and not (self.estilo in PSY and l % 4 == 0) and self.estilo not in ("sub", "dub")
                        and self._azar("fantasma", l) < self.fantasmas * 0.6):
                    golpes[l] = Golpe(4, 0, 0)
        if self.zenon_en(compas):
            golpes = {l: g for l, g in golpes.items() if l < 9}
            golpes[9] = Golpe(7 * TICKS_POR_PASO, 0, 0, None, True)
        remate = self.remate(compas)
        if remate:
            desde = min(remate) // 4 * 4
            golpes = {l: g for l, g in golpes.items() if l < desde or g.dur > 4 * TICKS_POR_PASO}
            for lugar, grado in remate.items():
                molde = (BASES[self.estilo] or self.base).get(lugar, Golpe(12 if self.estilo == "dub" else 6))
                golpes[lugar] = replace(molde, grado=grado)
        return self._fusas(golpes, compas)

    def zenon_en(self, compas):
        """Si este compás lleva la nota larga zenon: el anterior al que cierra la frase
        (con frase de 1, el tercero de cada 4), en esa proporción de frases."""
        if not self.zenon or self.estilo in ("sub", "dub"):
            return False
        largo = self.frase if self.frase > 1 else 4
        if compas % largo != largo - 2:
            return False
        return random.Random(f"bajo:{self.seed}:zenon:{compas // largo}").random() < self.zenon

    def _ciclar(self, golpes, compas):
        """Ciclo de alturas: la n-ésima nota del patrón (contando desde el primer compás)
        toma el grado n del ciclo. Solo cambian las notas en la raíz: lo que el
        movimiento o la evolución ya movieron se queda."""
        ciclo = CICLOS[self.ciclo]
        orden = sorted(self.patron)
        golpes = dict(golpes)
        for l, g in golpes.items():
            if g.grado == 0 and l in orden:
                n = compas * len(orden) + orden.index(l)
                golpes[l] = replace(g, grado=ciclo[n % len(ciclo)])
        return golpes

    def _fusas(self, golpes, compas):
        """Remate en fusas: en el compás que cierra la frase (o cada 4, sin frase), las
        notas del último tiempo (y con más de 60 %, la última del tiempo 3) se parten en
        dos fusas. La segunda repite la nota, salta a la octava o cae en la ♭7."""
        if not self.fusas or self.estilo in ("sub", "dub"):
            return golpes
        largo = self.frase if self.frase > 1 else 4
        if compas % largo != largo - 1:
            return golpes
        rng = random.Random(f"bajo:{self.seed}:fusas:{compas // largo}")
        if rng.random() >= self.fusas:
            return golpes
        lugares = [l for l in golpes if l >= 13 and not golpes[l].retraso]
        if self.fusas > 0.6:
            lugares += [l for l in golpes if l in (10, 11) and not golpes[l].retraso][-1:]
        golpes = dict(golpes)
        for l in lugares:
            golpes[l] = replace(golpes[l], fusa=rng.choice((golpes[l].grado, golpes[l].grado + 7, golpes[l].grado - 1)))
        return golpes

    def remate(self, compas):
        """El remate de este compás (lugar -> grado), o {} si no toca remate."""
        return self._remate(compas)[0]

    def _remate(self, compas):
        """(remate, largas): se alternan los dos remates del estilo; con variación, en
        cada frase cambian las alturas de algunas notas. Con «notas largas», en esa
        proporción de frases una nota (nunca la última) se alarga hacia la siguiente
        sin pisarla; a lo más una por remate. Nunca se quitan ni se agregan notas."""
        if not (self.remates and self.frase > 1 and compas % self.frase == self.frase - 1):
            return {}, set()
        frase = compas // self.frase
        if (self.remates_pack and self.estilo in CON_REMATES_PACK
                and random.Random(f"bajo:{self.seed}:pack:{frase}").random() < self.remates_pack):
            elegido = random.Random(f"bajo:{self.seed}:pack-cual:{frase}").choice(REMATES_PACK)
            return dict(elegido), set()
        remate = dict(REMATES[self.estilo][frase % 2])
        if not remate:
            return remate, set()
        rng = random.Random(f"bajo:{self.seed}:remate:{frase}")
        grados = GRADOS_REMATE[self.remate_rango]
        for lugar in sorted(remate):
            if rng.random() < self.remate_var:
                remate[lugar] = rng.choice([g for g in grados if g != remate[lugar]])
        if self.estilo == "offbeat":
            # Una nota grave pegada al bombo (justo antes o después) suena como un segundo
            # bombo: esas suben una octava.
            remate = {l: g + 7 if l % 4 in (1, 3) and g < 3 else g for l, g in remate.items()}
        largas = set()
        azar_larga = random.Random(f"bajo:{self.seed}:larga:{frase}")
        if len(remate) > 2 and azar_larga.random() < self.remate_largas:
            largas.add(azar_larga.choice(sorted(remate)[:-1]))
        return remate, largas

    def valor_filtro(self, compas, tiempo=0):
        """Valor del CC del filtro: sube de filtro_min a filtro_max en filtro_ciclo
        compases desde el ancla («sube»: y vuelve a cerrarse; «ola»: sube y baja)."""
        total = self.filtro_ciclo * 4
        k = ((compas - self.filtro_ancla) * 4 + tiempo) % total
        f = k / max(1, total - 1)
        if self.filtro_forma == "ola":
            f = 1 - abs(2 * f - 1)
        return round(self.filtro_min + (self.filtro_max - self.filtro_min) * f)

    def reiniciar_filtro(self, compas):
        """Vuelve a cerrar el filtro y empieza a abrirlo desde este compás (un quiebre)."""
        self.filtro_ancla = compas

    def _ligada(self, nota, inicio):
        """Si esta nota llega con otra todavía sonando (un slide): no se vuelve a atacar."""
        return any(fin > inicio for fin in self.sonando.values())

    def _enviar_cc(self, tick, enviar):
        listas = [c for c in self.cc_pendientes if c[0] <= tick]
        if not listas:
            return
        self.cc_pendientes = [c for c in self.cc_pendientes if c[0] > tick]
        for _, valor in sorted(listas, key=lambda c: c[0]):
            enviar(self.salida, "control_change", self.canal, self.filtro_cc,
                   self.filtro_ultimo if valor is None and self.filtro_ultimo is not None else (valor or 0))

    def _mover_filtro(self, compas, tiempo, enviar):
        valor = self.valor_filtro(compas, tiempo)
        if valor != self.filtro_ultimo:
            enviar(self.salida, "control_change", self.canal, self.filtro_cc, valor)
            self.filtro_ultimo = valor

    def _subir(self, golpes, compas):
        """«Notas que suben»: la última nota de algunos tiempos (y con el control alto,
        también la penúltima) sigue un camino que sube desde la raíz. Hay dos caminos,
        uno para los compases pares y otro para los impares: la línea va variando."""
        piso, tope = (1, 2) if self.sube < 0.35 else (3, 4) if self.sube < 0.7 else (6, 7)
        caminos = [c for c in CAMINOS if piso <= max(c) <= tope]
        k = int(self._azar("camino") * len(caminos))
        if compas % 2:  # los impares, otro camino: la línea va variando
            k = (k + 1 + int(self._azar("camino", 1) * (len(caminos) - 1))) % len(caminos)
        camino = caminos[k]
        cuantos = max(1, round(self.sube * 3))   # tiempos que suben: 1, 2 o los 3
        tiempos = sorted((t for t in range(1, 4) if camino[t]), key=lambda t: self._azar("sube", t))[:cuantos]
        golpes = dict(golpes)
        for tiempo in tiempos:
            propios = sorted(l for l in golpes if l // 4 == tiempo and golpes[l].grado == 0)
            for l in propios[-2 if self.sube > 0.55 else -1:]:
                golpes[l] = replace(golpes[l], grado=camino[tiempo])
        return golpes

    # --- Qué toca ---

    def _velocidad(self, compas, lugar, golpe):
        if golpe.dur == 4 and lugar not in self.patron:
            return max(1, round(self.velocidad * 0.45))  # nota fantasma
        vel = self.velocidad
        if self.estilo == "chillgressive" and lugar % 4 == compas % 3 + 1:
            vel += 15  # acento que se mueve por la frase
        elif self._azar("acento", lugar) < self.acentos:
            vel += 18
        elif self.estilo in ("dub", "sub") and lugar == 0:
            vel += 6
        azar = random.Random(f"bajo:{self.seed}:vel:{lugar}").uniform(-1, 1)
        return max(1, min(127, vel + round(self.vel_random * 25 * azar)))

    def _nota(self, raiz, grado, momento, ultima, anticipar):
        nota = self.tonalidad.nota(raiz, grado + self.transponer, "escala") + 12 * self.octava
        if ultima and anticipar and momento is not None and momento.cambia_pronto and momento.siguiente is not None:
            # Aproximación: un paso de escala junto a la raíz que viene, desde donde viene la línea.
            meta = _cerca(momento.siguiente % 12, nota)
            if meta != nota:
                nota = self.tonalidad.nota(meta, -1 if meta > nota else 1, "escala")
        return max(0, min(127, nota))

    # --- Tiempo ---

    def paso(self, paso, tick, raiz, momento, anticipar, enviar):
        """Llamado en cada paso. `raiz`: raíz del acorde (o la nota larga), ya en su registro."""
        if not self.activo or raiz is None:
            return
        compas, lugar = divmod(paso, PASOS_POR_COMPAS)
        estado_porta = (self.porta, self.porta_tiempo)
        if self.porta_enviado != estado_porta and (self.porta or self.porta_enviado is not None):
            enviar(self.salida, "control_change", self.canal, 65, 127 if self.porta else 0)
            if self.porta:
                enviar(self.salida, "control_change", self.canal, 5, self.porta_tiempo)
            self.porta_enviado = estado_porta
        if self.filtro and lugar % 4 == 0:
            self._mover_filtro(compas, lugar // 4, enviar)
        golpes = self.golpes(compas)
        if lugar not in golpes:
            return
        golpe = golpes[lugar]
        falta = momento.falta if momento is not None and momento.falta is not None else None
        ultima = falta is not None and not any(lugar < l < lugar + falta for l in golpes)
        nota = self._nota(raiz, golpe.grado, momento, ultima, anticipar)
        retraso = golpe.retraso
        if self.swing and lugar % 2 == 1 and not retraso:
            retraso = round(self.swing * TICKS_POR_PASO)
        inicio = tick + retraso
        dur = golpe.dur
        if falta:
            dur = min(dur, falta * TICKS_POR_PASO - retraso)  # una nota no cruza el cambio de acorde
        siguiente = next((l for l in sorted(golpes) if l > lugar), None)
        remate, largas = self._remate(compas)
        en_remate = lugar in remate and self.estilo not in ("sub", "dub") and self.remate_marca >= 0.3
        anterior = max((l for l in golpes if l < lugar), default=None)
        desliza = False
        if lugar in largas and siguiente is not None:
            # Nota larga del remate: ocupa parte del hueco hasta la siguiente y termina
            # antes de que empiece (nunca se pisan).
            hueco = (siguiente - lugar) * TICKS_POR_PASO + golpes[siguiente].retraso - retraso
            fin = inicio + max(1, min(hueco - 1, math.ceil(hueco * self.remate_largo)))
        elif en_remate:
            # Remate marcado: sin slide y con su largo normal (no más corto que el resto,
            # para que no suene a corte); lo marca el acento y que cada nota se ataca.
            fin = inicio + max(1, round(dur * self.gate)) if dur <= 2 * TICKS_POR_PASO else inicio + dur - 1
        elif self.estilo == "sub":
            fin = inicio + dur + 1  # sigue sonando cuando llega la próxima: se liga
        elif (siguiente is not None and self.estilo not in ("dub",) and self._azar("slide", lugar) < self.slide
              and not ultima):
            # Slide: dura hasta pisar la siguiente; un sinte en legato con glide se desliza.
            fin = tick + (siguiente - lugar) * TICKS_POR_PASO + golpes[siguiente].retraso + 2
            desliza = True
        elif dur <= 2 * TICKS_POR_PASO:
            fin = inicio + max(1, round(dur * self.gate))
        else:
            fin = inicio + dur - 1
        if siguiente is not None and self.estilo != "sub" and not desliza:
            # Ninguna nota (salvo un slide) dura más allá del comienzo de la siguiente:
            # con swing, tresillos o golpes largos podían pisarse un instante.
            r_sig = golpes[siguiente].retraso or (round(self.swing * TICKS_POR_PASO) if self.swing and siguiente % 2 else 0)
            fin = max(inicio + 1, min(fin, tick + (siguiente - lugar) * TICKS_POR_PASO + r_sig))
        vel = self._velocidad(compas, lugar, golpe)
        if en_remate and not (self.estilo == "offbeat" and lugar % 4 in (1, 3)):
            # Acento suave y parejo: no se suma a los acentos al azar (antes llegaba a 127).
            vel = min(127, min(vel, self.velocidad) + round(6 * self.remate_marca))
        if self.filtro and self.filtro_nota and not self._ligada(nota, inicio):
            # Envolvente de filtro por nota: el filtro se abre en el ataque y vuelve a su
            # lugar al rato (las notas ligadas de un slide no lo vuelven a abrir).
            base = self.filtro_ultimo if self.filtro_ultimo is not None else self.valor_filtro(compas, lugar // 4)
            pico = min(127, base + round((127 - base) * self.filtro_nota * (0.6 + 0.4 * vel / 127)))
            self.cc_pendientes += [(inicio, pico), (inicio + max(2, round(min(fin - inicio, TICKS_POR_PASO) * 0.7)), None)]
            if not retraso:
                self._enviar_cc(tick, enviar)
        if golpe.fusa is not None:
            # Remate en fusas: dos notas de medio paso, la segunda un poco más suave.
            mitad = TICKS_POR_PASO // 2
            fin = min(fin, inicio + mitad - 1)
            segunda = self._nota(raiz, golpe.fusa, momento, False, False)
            self.pendientes.append((inicio + mitad, segunda, max(1, vel - 12), inicio + 2 * mitad - 1))
        if (self.arco and not golpe.caida and fin - inicio > 2 * TICKS_POR_PASO + 2
                and self._azar("arco", compas % max(1, self.frase), lugar) < self.arco):
            # Arco: sube y vuelve (seno), sin pasar del rango de bend del sinte.
            tope = min(8191, round(8192 * self.arco_alto / self.bend_rango))
            largo = fin - inicio
            for t in range(2, largo, 2):
                self.bends.append((inicio + t, round(tope * math.sin(math.pi * t / largo) ** 1.5)))
            self.bends.append((fin, 0))
        if golpe.caida and self.caida:
            # La caída: el bend baja con una curva (rápido al principio) mientras suena y
            # vuelve al centro cuando termina, antes de la nota siguiente.
            tope = -min(8192, round(8192 * self.caida / self.bend_rango))
            largo = max(2, fin - inicio)
            for t in range(2, largo, 2):
                self.bends.append((inicio + t, round(tope * (1 - (1 - t / largo) ** 2))))
            self.bends.append((fin, 0))
        if retraso:
            self.pendientes.append((inicio, nota, vel, fin))
        else:
            self._encender(nota, vel, inicio, fin, enviar, atacar=en_remate and anterior not in largas)

    def _encender(self, nota, vel, inicio, fin, enviar, atacar=False):
        if not atacar and nota in self.sonando and (self.estilo == "sub" or self.sonando[nota] <= inicio + 3):
            # Misma nota ligada (sub o después de un slide): se prolonga sin volver a atacar.
            self.sonando[nota] = max(self.sonando[nota], fin)
            return
        for vieja, termina in list(self.sonando.items()):
            # Monofónico: corta las demás, salvo la cola de un slide (se pisa un instante).
            if vieja == nota or termina > inicio + 3 or atacar or self.estilo in ("sub", "dub"):
                enviar(self.salida, "note_off", self.canal, vieja, 0)
                del self.sonando[vieja]
        enviar(self.salida, "note_on", self.canal, nota, vel)
        self.sonando[nota] = fin

    def heredar_notas(self, viejo, enviar):
        """Al reemplazar el bajo: la nota que suena termina sola (o se liga, en sub)."""
        if (viejo.salida, viejo.canal) == (self.salida, self.canal):
            self.sonando, self.pendientes = dict(viejo.sonando), list(viejo.pendientes)
            viejo.sonando, viejo.pendientes = {}, []
            self.bends, self.bend_movido = list(viejo.bends), viejo.bend_movido  # la caída termina y vuelve al centro
            viejo.bends, viejo.bend_movido = [], False
        else:
            viejo.apagar(enviar)

    def tick(self, tick, enviar):
        if self.cc_pendientes:
            self._enviar_cc(tick, enviar)
        for nota, fin in list(self.sonando.items()):
            if fin <= tick:
                enviar(self.salida, "note_off", self.canal, nota, 0)
                del self.sonando[nota]
        if self.bends:
            self._mover_bends(tick, enviar)
        if self.pendientes:
            listas = [p for p in self.pendientes if p[0] <= tick]
            self.pendientes = [p for p in self.pendientes if p[0] > tick]
            for inicio, nota, vel, fin in listas:
                self._encender(nota, vel, inicio, fin, enviar)

    def _mover_bends(self, tick, enviar):
        listos = [b for b in self.bends if b[0] <= tick]
        if not listos:
            return
        self.bends = [b for b in self.bends if b[0] > tick]
        valor = listos[-1][1]
        enviar(self.salida, "pitchwheel", self.canal, valor, 0)
        self.bend_movido = valor != 0

    def apagar(self, enviar):
        for nota in self.sonando:
            enviar(self.salida, "note_off", self.canal, nota, 0)
        self.sonando = {}
        self.pendientes = []
        self.bends = []
        if self.bend_movido:
            enviar(self.salida, "pitchwheel", self.canal, 0, 0)
            self.bend_movido = False


def _fraccion(x):
    return max(0.0, min(1.0, float(x)))


def _cerca(clase, referencia):
    """La nota de esa clase más cercana a la referencia."""
    n = referencia - (referencia - clase) % 12
    return n + 12 if referencia - n > 6 else n
