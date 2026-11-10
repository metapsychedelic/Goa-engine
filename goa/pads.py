"""Motor de pads y drones.

Progresiones lentas de estilo Goa y psytrance oscuro. Los acordes se
arman apilando grados de la escala de la tonalidad, y cada cambio
elige la inversión que mueve menos las voces, para que suene ligado
y orgánico. Opcionalmente sostiene un drone grave en la raíz.
"""

import random

from .escalas import nombre_midi

# Grados de la escala (0 = i) por acorde de cada progresión.
PROGRESIONES = {
    "i_bII": [0, 1],                 # frigio: la tensión oscura del psytrance
    "i_bVI_bVII": [0, 5, 6],         # épica, para clímax
    "i_v": [0, 4],                   # con menor armónica suena i–V, sabor oriental
    "drone_modal": [0, 1, 0, 6],     # la raíz queda fija y los acordes se mueven encima
    "i_iv_bII_i": [0, 3, 1, 0],      # ciclo largo para breaks
    "andaluza": [0, 6, 5, 4],        # i–♭VII–♭VI–V, bajada muy Goa
}

# Pasos de escala apilados desde la raíz del acorde.
ACORDES = {
    "quintas": [0, 4, 7],            # raíz, quinta, octava: oscuro y abierto
    "sus2": [0, 1, 4],
    "menor_add9": [0, 2, 4, 8],
    "triada": [0, 2, 4],
    "cluster": [0, 1, 2, 4],
}

APERTURAS = ("cerrada", "abierta", "amplia")
ATAQUES = ("ligado", "reatacar")
BASES = ("nota", "tonica")
CENTRO = 48  # C3: centro del registro de los pads


def _cerca(clase, referencia):
    """Nota con esa clase de altura más cercana a `referencia`."""
    n = referencia + ((clase - referencia) % 12)
    return n - 12 if n - referencia > 6 else n


def _limitar(n):
    while n > 108:
        n -= 12
    while n < 24:
        n += 12
    return n


class Pads:
    def __init__(self, cfg, tonalidad):
        self.activo = bool(cfg.get("activo", False))
        self.salida = cfg.get("salida", "CH345")
        self.canal = int(cfg.get("canal", 3)) - 1
        self.base = cfg.get("base", "nota")
        self.progresion = PROGRESIONES[cfg.get("progresion", "i_bII")]
        self.acorde = ACORDES[cfg.get("acorde", "menor_add9")]
        self.cambia_cada = max(1, int(cfg.get("cambia_cada", 16)))
        self.voces = max(2, min(6, int(cfg.get("voces", 4))))
        self.octava = int(cfg.get("octava", 0))
        self.apertura = cfg.get("apertura", "abierta")
        self.variacion = float(cfg.get("variacion", 0.15))
        self.ataque = cfg.get("ataque", "ligado")
        self.drone = bool(cfg.get("drone", False))
        self.rasgueo = max(0, min(6, int(cfg.get("rasgueo", 1))))
        self.velocidad = int(cfg.get("velocidad", 80))
        self.seed = str(cfg.get("seed", "pads"))
        for nombre, valor, opciones in (("apertura", self.apertura, APERTURAS),
                                        ("ataque", self.ataque, ATAQUES), ("base", self.base, BASES)):
            if valor not in opciones:
                raise ValueError(f"{nombre} debe ser una de: {', '.join(opciones)}")
        self.tonalidad = tonalidad
        self.sonando = set()        # notas del acorde que están sonando
        self.nota_drone = None
        self.pendientes = []        # (tick, nota) por el rasgueo
        self.clave = None           # (cambio, base) del acorde actual
        self.raiz_acorde = None

    # --- Armado de acordes ---

    def _grado(self, cambio):
        """Grado del acorde para el cambio número `cambio`, con variación determinista."""
        grado = self.progresion[cambio % len(self.progresion)]
        if self.variacion > 0 and cambio > 0:
            rng = random.Random(f"pads:{self.seed}:{cambio}")
            if rng.random() < self.variacion:
                # Sustituto por terceras (relativo): comparte dos notas con el original.
                grado += rng.choice((2, -2, 5))
        return grado

    def _base(self, raiz):
        if raiz is None:  # sin nota larga, los pads se callan
            return None
        centro = CENTRO + 12 * self.octava
        if self.base == "nota":
            return _cerca(raiz % 12, centro)
        return _cerca(self.tonalidad.tonica, centro)

    def _voicing(self, raiz_acorde):
        pasos = list(self.acorde)
        while len(pasos) < self.voces:  # dobla raíz y quinta una octava arriba
            pasos.append(pasos[len(pasos) - len(self.acorde)] + 7)
        notas = sorted(self.tonalidad.nota(raiz_acorde, p, "escala") for p in pasos[:self.voces])
        if self.apertura in ("abierta", "amplia"):
            notas = [n + 12 if i % 2 == 1 else n for i, n in enumerate(notas)]
        if self.apertura == "amplia" and len(notas) > 3:
            notas[3] += 12
        notas = sorted(_limitar(n) for n in notas)
        return self._mover_minimo(notas)

    def _mover_minimo(self, notas):
        """Elige la inversión que menos mueve las voces respecto al acorde que suena."""
        if not self.sonando:
            return notas
        anterior = sorted(self.sonando)
        candidatas = []
        actual = list(notas)
        for _ in range(len(notas)):
            for desplazamiento in (-12, 0, 12):
                cand = sorted(_limitar(n + desplazamiento) for n in actual)
                candidatas.append(cand)
            actual = sorted(actual[1:] + [actual[0] + 12])  # siguiente inversión
        registro = CENTRO + 12 * self.octava
        # Solo inversiones cuya voz grave queda cerca del registro: si no, el acorde
        # se iría subiendo (o bajando) de a poco con cada cambio.
        en_registro = [c for c in candidatas if abs(c[0] - registro) <= 9] or candidatas

        def costo(cand):
            k = min(len(cand), len(anterior))
            return sum(abs(a - b) for a, b in zip(cand[:k], anterior[:k])) + abs(cand[0] - registro) * 0.5

        return min(en_registro, key=costo)

    def acorde_en(self, paso, raiz):
        """Raíz y clases de altura del acorde que suena (o sonará) en `paso`.

        Sin efectos: sirve para que otros módulos sigan la progresión justo en el
        paso del cambio, sin esperar a que los pads lo toquen."""
        base = self._base(raiz) if self.activo else None
        if base is None:
            return None, None
        cambio = (paso // 16) // self.cambia_cada
        raiz_acorde = self.tonalidad.nota(base, self._grado(cambio), "escala")
        clases = {self.tonalidad.nota(raiz_acorde, p, "escala") % 12 for p in self.acorde}
        return raiz_acorde, clases

    # --- Tiempo ---

    def actualizar(self, paso, raiz, tick, enviar):
        """Llamado en cada paso de semicorchea con la raíz de la nota larga."""
        if not self.activo:
            return
        base = self._base(raiz)
        if base is None:
            self.apagar(enviar)
            return
        cambio = (paso // 16) // self.cambia_cada
        clave = (cambio, base)
        if clave == self.clave:
            return
        self.clave = clave
        raiz_acorde = self.tonalidad.nota(base, self._grado(cambio), "escala")
        self.raiz_acorde = raiz_acorde
        nuevas = sorted(set(self._voicing(raiz_acorde)))  # sin notas repetidas al doblar voces

        if self.drone:
            drone = _limitar(base - 12)
            # Que ninguna voz del acorde caiga justo en la nota del drone.
            nuevas = sorted(set(n + 12 if n == drone else n for n in nuevas))
            if drone != self.nota_drone:
                if self.nota_drone is not None:
                    enviar(self.salida, "note_off", self.canal, self.nota_drone, 0)
                enviar(self.salida, "note_on", self.canal, drone, self.velocidad)
                self.nota_drone = drone

        if self.ataque == "reatacar":
            quitar, poner = set(self.sonando), list(nuevas)
            self.pendientes = []
        else:
            quitar = self.sonando - set(nuevas)
            poner = [n for n in nuevas if n not in self.sonando]
            self.pendientes = [(t, n) for t, n in self.pendientes if n in nuevas]
        for n in quitar:
            enviar(self.salida, "note_off", self.canal, n, 0)
        for i, n in enumerate(sorted(poner)):
            self.pendientes.append((tick + i * self.rasgueo, n))
        self.sonando = set(nuevas)
        self.tick(tick, enviar)

    def tick(self, tick, enviar):
        listas = [p for p in self.pendientes if p[0] <= tick]
        if not listas:
            return
        self.pendientes = [p for p in self.pendientes if p[0] > tick]
        for _, n in listas:
            enviar(self.salida, "note_on", self.canal, n, self.velocidad)

    def apagar(self, enviar):
        for n in self.sonando:
            enviar(self.salida, "note_off", self.canal, n, 0)
        if self.nota_drone is not None:
            enviar(self.salida, "note_off", self.canal, self.nota_drone, 0)
        self.sonando = set()
        self.nota_drone = None
        self.pendientes = []
        self.clave = None
        self.raiz_acorde = None

    def descripcion(self):
        if not self.sonando:
            return None
        return " · ".join(nombre_midi(n) for n in sorted(self.sonando))
