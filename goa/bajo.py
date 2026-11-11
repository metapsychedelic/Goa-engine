"""Generador de líneas de bajo.

A diferencia de una secuencia (un motivo que se repite sobre una nota base),
el bajo sabe hacia dónde va la armonía (ver armonia.py):

- Toca la raíz del acorde de los pads, y elige raíz, quinta, octava o una nota
  de paso según el estilo y el movimiento.
- Con armonía guiada y "anticipar", la última nota antes de un cambio de acorde
  es una nota de aproximación: un paso de escala junto a la raíz que viene.
- Frases de 2, 4 u 8 compases: los compases se repiten igual y el último cierra
  con un remate, que alterna entre dos variantes para no sonar idéntico cada vuelta.
- En los estilos psy nunca cae en el tiempo (ahí va el bombo).

Todo es determinista: misma variante, mismo bajo.
"""

import random

TICKS_POR_PASO = 6
PASOS_POR_COMPAS = 16

ESTILOS = ("rolling", "psy_chill", "chillgressive", "dub", "sub")

# Golpes de cada estilo en el compás: lugar -> duración en pasos.
GOLPES = {
    "rolling": {l: 1 for l in range(16) if l % 4},                 # bombo, bajo, bajo, bajo
    "psy_chill": {l: 1 for l in range(16) if l % 4 in (2, 3)},     # bombo, silencio, bajo, bajo
    "chillgressive": {l: 1 for l in range(16) if l % 4},           # rolling oscuro, acento que se mueve
    "dub": {0: 5, 7: 2, 10: 4},                                    # en el uno, antes del tres y en el tres
    "sub": {0: 16},                                                # una nota por compás, ligada: casi un drone
}

# Remates del último tiempo de la frase (lugares 13 a 15): grados de escala desde la raíz.
REMATES = {
    "rolling": ({13: 7, 14: 0, 15: 4}, {13: 7, 14: 6, 15: 4}),     # salto de octava · bajada 8-7-5
    "psy_chill": ({14: 7, 15: 4}, {14: 4, 15: 6}),
    "chillgressive": ({13: 0, 14: 7, 15: 6}, {13: 4, 14: 6, 15: 7}),
    "dub": ({14: 4}, {13: 6, 15: 4}),
    "sub": ({}, {}),
}

# Qué nota toca cada golpe cuando hay movimiento: (lugares, grado de escala, probabilidad).
MOVIMIENTOS = {
    "rolling": [(lambda l: l % 4 == 3, 7, 0.5), (lambda l: l % 4 == 2, 4, 0.25)],
    "psy_chill": [(lambda l: l % 4 == 3, 4, 0.5), (lambda l: l % 4 == 3, 1, 0.25)],
    "chillgressive": [(lambda l: l % 4 == 3, 7, 0.4), (lambda l: l % 4 == 1, 4, 0.2)],
    "dub": [(lambda l: l == 7, 7, 0.6), (lambda l: l == 10, 4, 0.6)],
    "sub": [(lambda l: l == 0, 4, 0.0)],
}


class Bajo:
    def __init__(self, cfg, tonalidad):
        self.activo = bool(cfg.get("activo", False))
        self.salida = cfg.get("salida", "")
        self.canal = int(cfg.get("canal", 4)) - 1
        self.estilo = cfg.get("estilo", "rolling")
        if self.estilo not in ESTILOS:
            raise ValueError(f"Estilo de bajo desconocido: {self.estilo!r}. Opciones: {', '.join(ESTILOS)}")
        self.octava = int(cfg.get("octava", 0))
        self.gate = max(0.05, min(1.0, float(cfg.get("gate", 0.6))))
        self.velocidad = int(cfg.get("velocidad", 100))
        self.vel_random = float(cfg.get("vel_random", 0.1))
        self.movimiento = max(0.0, min(1.0, float(cfg.get("movimiento", 0.3))))
        self.remates = bool(cfg.get("remates", True))
        self.frase = max(1, int(cfg.get("frase", 4)))
        self.armonia = cfg.get("armonia", "general")
        self.seed = str(cfg.get("seed", "B-0001"))
        self.tonalidad = tonalidad
        self.disparo = None
        self.sonando = {}   # nota -> tick en que se apaga

    # --- Qué toca ---

    def golpes(self, compas):
        """{lugar: (duración en pasos, grado de escala desde la raíz)} de un compás."""
        golpes = {}
        for lugar, dur in GOLPES[self.estilo].items():
            grado = 0
            for donde, g, prob in MOVIMIENTOS[self.estilo]:
                # Determinista por lugar: el mismo compás suena igual cada vuelta.
                azar = random.Random(f"bajo:{self.seed}:{lugar}:{g}").random()
                if donde(lugar) and azar < prob * self.movimiento * 2:
                    grado = g
                    break
            golpes[lugar] = (dur, grado)
        if self.remates and self.frase > 1 and compas % self.frase == self.frase - 1:
            remate = REMATES[self.estilo][(compas // self.frase) % 2]
            if remate:
                golpes = {l: v for l, v in golpes.items() if l < 12 or GOLPES[self.estilo][l] > 4}
                for lugar, grado in remate.items():
                    golpes[lugar] = (1 if self.estilo != "dub" else 2, grado)
        return golpes

    def _velocidad(self, compas, lugar):
        vel = self.velocidad
        if self.estilo == "chillgressive" and lugar % 4 == compas % 3 + 1:
            vel += 15  # acento que se mueve por la frase
        elif lugar % 4 == 1 or self.estilo in ("dub", "sub") and lugar == 0:
            vel += 6
        azar = random.Random(f"bajo:{self.seed}:vel:{lugar}").uniform(-1, 1)
        return max(1, min(127, vel + round(self.vel_random * 25 * azar)))

    def _nota(self, raiz, grado, momento, ultima, anticipar):
        nota = self.tonalidad.nota(raiz, grado, "escala") + 12 * self.octava
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
        dur, grado = golpes[lugar]
        falta = momento.falta if momento is not None and momento.falta is not None else None
        hasta = min(dur, falta) if falta else dur  # una nota larga no cruza el cambio de acorde
        ultima = falta is not None and not any(lugar < l < lugar + falta for l in golpes)
        nota = self._nota(raiz, grado, momento, ultima, anticipar)
        if self.estilo == "sub":
            fin = tick + hasta * TICKS_POR_PASO + 1  # sigue sonando cuando llega la próxima: se liga
        elif hasta == 1:
            fin = tick + max(1, round(TICKS_POR_PASO * self.gate))
        else:
            fin = tick + hasta * TICKS_POR_PASO - 1
        if self.estilo == "sub" and nota in self.sonando:
            self.sonando[nota] = fin  # ligada: el drone sigue sin volver a atacar
            return
        if nota in self.sonando:
            enviar(self.salida, "note_off", self.canal, nota, 0)
        for vieja in [n for n in self.sonando if n != nota and self.estilo in ("sub", "dub")]:
            enviar(self.salida, "note_off", self.canal, vieja, 0)  # monofónico: nunca dos notas juntas
            del self.sonando[vieja]
        enviar(self.salida, "note_on", self.canal, nota, self._velocidad(compas, lugar))
        self.sonando[nota] = fin

    def tick(self, tick, enviar):
        for nota, fin in list(self.sonando.items()):
            if fin <= tick:
                enviar(self.salida, "note_off", self.canal, nota, 0)
                del self.sonando[nota]

    def apagar(self, enviar):
        for nota in self.sonando:
            enviar(self.salida, "note_off", self.canal, nota, 0)
        self.sonando = {}


def _cerca(clase, referencia):
    """La nota de esa clase más cercana a la referencia."""
    n = referencia - (referencia - clase) % 12
    return n + 12 if referencia - n > 6 else n
