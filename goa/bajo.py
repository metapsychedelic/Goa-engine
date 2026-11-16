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

ESTILOS = ("rolling", "fullon", "galope", "offbeat", "saltado", "tresillo", "chillgressive", "dub", "sub")
ALIAS = {"psy_chill": "galope"}  # nombre que tuvo en la v0.18.0
PSY = {"rolling", "fullon", "galope", "offbeat", "saltado", "tresillo", "chillgressive"}


@dataclass(frozen=True)
class Golpe:
    dur: int            # ticks
    retraso: int = 0    # ticks después del paso (tresillos)
    grado: int = 0      # grado de escala desde la raíz del acorde


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
    "offbeat": ({13: 7, 14: 4, 15: 0}, {14: 7, 15: 6}),
    "saltado": ({13: 7, 15: 4}, {13: 4, 14: 6, 15: 7}),
    "tresillo": ({13: 7, 14: 4}, {13: 4, 14: 6}),
    "chillgressive": ({13: 0, 14: 7, 15: 6}, {13: 4, 14: 6, 15: 7}),
    "dub": ({14: 4}, {13: 6, 15: 4}),
    "sub": ({}, {}),
}
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
        base = dict(BASES[self.estilo])
        if self.estilo == "fullon":
            celdas = [CELDAS[int(self._azar("celda", t) * len(CELDAS))] for t in range(4)]
            base = {l: replace(g, grado=celdas[l // 4][l % 4 - 1]) for l, g in base.items()}
        for lugar, golpe in base.items():
            for donde, grado, prob in MOVIMIENTOS[self.estilo]:
                if golpe.grado == 0 and donde(lugar) and self._azar(lugar, grado) < prob * self.movimiento * 2:
                    base[lugar] = replace(golpe, grado=grado)
                    break
        return base

    def reiniciar(self):
        self.patron = dict(self.base)
        self.mutado_hasta = -1  # último compás en que se aplicó la evolución

    def continuar_de(self, viejo):
        """Al cambiar la configuración en vivo: si el patrón base es el mismo, sigue con lo mutado."""
        if viejo.base == self.base and viejo.seed == self.seed:
            self.patron = dict(viejo.patron)
            self.mutado_hasta = viejo.mutado_hasta

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
        if self.sube and self.estilo not in SIN_SUBE:
            golpes = self._subir(golpes, compas)
        if self.fantasmas:
            for l in range(PASOS_POR_COMPAS):
                if (l not in golpes and not (self.estilo in PSY and l % 4 == 0) and self.estilo not in ("sub", "dub")
                        and self._azar("fantasma", l) < self.fantasmas * 0.6):
                    golpes[l] = Golpe(4, 0, 0)
        remate = self.remate(compas)
        if remate:
            desde = min(remate) // 4 * 4
            golpes = {l: g for l, g in golpes.items() if l < desde or g.dur > 4 * TICKS_POR_PASO}
            for lugar, grado in remate.items():
                molde = BASES[self.estilo].get(lugar, Golpe(12 if self.estilo == "dub" else 6))
                golpes[lugar] = replace(molde, grado=grado)
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
        remate = dict(REMATES[self.estilo][frase % 2])
        if not remate:
            return remate, set()
        rng = random.Random(f"bajo:{self.seed}:remate:{frase}")
        grados = GRADOS_REMATE[self.remate_rango]
        for lugar in sorted(remate):
            if rng.random() < self.remate_var:
                remate[lugar] = rng.choice([g for g in grados if g != remate[lugar]])
        largas = set()
        azar_larga = random.Random(f"bajo:{self.seed}:larga:{frase}")
        if len(remate) > 2 and azar_larga.random() < self.remate_largas:
            largas.add(azar_larga.choice(sorted(remate)[:-1]))
        return remate, largas

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
        elif dur <= 2 * TICKS_POR_PASO:
            fin = inicio + max(1, round(dur * self.gate))
        else:
            fin = inicio + dur - 1
        vel = self._velocidad(compas, lugar, golpe)
        if en_remate:
            vel = min(127, vel + round(12 * self.remate_marca))
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
        else:
            viejo.apagar(enviar)

    def tick(self, tick, enviar):
        for nota, fin in list(self.sonando.items()):
            if fin <= tick:
                enviar(self.salida, "note_off", self.canal, nota, 0)
                del self.sonando[nota]
        if self.pendientes:
            listas = [p for p in self.pendientes if p[0] <= tick]
            self.pendientes = [p for p in self.pendientes if p[0] > tick]
            for inicio, nota, vel, fin in listas:
                self._encender(nota, vel, inicio, fin, enviar)

    def apagar(self, enviar):
        for nota in self.sonando:
            enviar(self.salida, "note_off", self.canal, nota, 0)
        self.sonando = {}
        self.pendientes = []


def _fraccion(x):
    return max(0.0, min(1.0, float(x)))


def _cerca(clase, referencia):
    """La nota de esa clase más cercana a la referencia."""
    n = referencia - (referencia - clase) % 12
    return n + 12 if referencia - n > 6 else n
