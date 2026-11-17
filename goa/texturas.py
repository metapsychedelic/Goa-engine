"""Texturas: notas largas que respiran mezcladas con notas cortas, para un canal propio
de la MC-101 (o cualquier sinte polifónico).

- Notas largas de 1, 2 o 4 compases, sacadas del acorde que suena. Cada una mueve un
  CC (el corte del filtro, la resonancia u otro) mientras dura: sube despacio y vuelve,
  como si la nota respirara.
- Notas cortas salpicadas entre medio (nunca en el tiempo del bombo), una octava más
  arriba y más suaves, sin modulación.
- Sigue la armonía: si el acorde cambia y la nota larga ya no le pertenece, termina.
- En las subidas las largas aparecen más y respiran más hondo.

Todo es repetible con la seed.
"""

import math
import random

from . import armonia

TICKS_POR_PASO = 6
PASOS_POR_COMPAS = 16
TICKS_POR_COMPAS = TICKS_POR_PASO * PASOS_POR_COMPAS


def _f(x):
    return max(0.0, min(1.0, float(x)))


class Texturas:
    def __init__(self, cfg, tonalidad):
        self.activo = bool(cfg.get("activo", False))
        self.salida = cfg.get("salida", "")
        self.canal = int(cfg.get("canal", 2)) - 1
        self.densidad = _f(cfg.get("densidad", 0.5))
        self.largas = _f(cfg.get("largas", 0.6))            # 0 = solo cortas, 1 = solo largas
        self.largo = int(cfg.get("largo", 2))               # largo típico de las largas (1, 2 o 4 compases)
        self.octava = int(cfg.get("octava", 0))
        self.velocidad = int(cfg.get("velocidad", 90))
        self.cc = max(0, min(127, int(cfg.get("cc", 74))))
        self.reposo = max(0, min(127, int(cfg.get("reposo", 40))))
        self.profundidad = _f(cfg.get("profundidad", 0.6))  # cuánto se abre en cada nota larga
        self.seed = str(cfg.get("seed", "TX-0001"))
        self.tonalidad = tonalidad
        self.disparo = None
        self.larga = None          # (nota, inicio, fin, hondo) de la nota larga que suena
        self.cortas = {}           # nota -> tick en que termina
        self.valor_cc = None       # último CC mandado (None = no lo tocamos todavía)

    # --- Estado ---

    def continuar_de(self, viejo, enviar):
        """Al cambiar la configuración en vivo: lo que suena sigue y termina solo."""
        if viejo is None:
            return
        if (viejo.salida, viejo.canal) == (self.salida, self.canal):
            self.larga, self.cortas, self.valor_cc = viejo.larga, viejo.cortas, viejo.valor_cc
            if not self.activo:
                self.apagar(enviar)
        else:
            viejo.apagar(enviar)

    def apagar(self, enviar):
        if self.larga is not None:
            enviar(self.salida, "note_off", self.canal, self.larga[0], 0)
        for nota in sorted(self.cortas):
            enviar(self.salida, "note_off", self.canal, nota, 0)
        self.larga, self.cortas = None, {}
        if self.valor_cc is not None and self.valor_cc != self.reposo:
            enviar(self.salida, "control_change", self.canal, self.cc, self.reposo)
        self.valor_cc = None

    # --- Reloj ---

    def tick(self, tick, enviar):
        for nota, fin in list(self.cortas.items()):
            if tick >= fin:
                enviar(self.salida, "note_off", self.canal, nota, 0)
                del self.cortas[nota]
        if self.larga is not None:
            nota, inicio, fin, hondo = self.larga
            if tick >= fin:
                enviar(self.salida, "note_off", self.canal, nota, 0)
                self.larga = None
                self._cc(self.reposo, enviar)
            elif tick % 3 == 0:
                # La nota respira: el CC sube despacio hasta la mitad y vuelve al reposo.
                x = (tick - inicio) / max(1, fin - inicio)
                self._cc(round(self.reposo + (127 - self.reposo) * hondo * math.sin(math.pi * x) ** 1.5), enviar)

    def _cc(self, valor, enviar):
        valor = max(0, min(127, valor))
        if valor != self.valor_cc:
            enviar(self.salida, "control_change", self.canal, self.cc, valor)
            self.valor_cc = valor

    # --- Notas ---

    def _azar(self, *clave):
        return random.Random(":".join(["tx", self.seed, *map(str, clave)]))

    def _nota(self, raiz, momento, rng, arriba=0, larga=False):
        base = raiz + 12 * (self.octava + 1 + arriba)
        if momento is not None and momento.clases:
            clases = sorted(momento.clases)
            if larga and momento.clases_siguiente:
                # Una larga prefiere una nota que también esté en el acorde que viene:
                # así sigue sonando cuando la armonía cambia.
                comunes = sorted(momento.clases & momento.clases_siguiente)
                clases = comunes or clases
            clase = rng.choice(clases)
            return max(0, min(127, armonia.nota_del_acorde(base + (clase - base) % 12, momento.clases)))
        return max(0, min(127, self.tonalidad.nota(base, rng.choice((0, 2, 4)), "escala")))

    def _vel(self, factor):
        return max(1, min(127, round(self.velocidad * factor)))

    # --- Cada paso ---

    def paso(self, paso, tick, raiz, momento, subida, enviar):
        """Llamado en cada paso con la nota larga (`raiz`), el acorde y la subida en curso."""
        if not self.activo or raiz is None:
            return
        compas, lugar = divmod(paso, PASOS_POR_COMPAS)
        en_subida = subida is not None
        # Si el acorde cambió y la nota larga ya no le pertenece, termina (sin cortar feo:
        # al soltarla el sinte hace su release).
        if self.larga is not None and momento is not None and momento.clases and self.larga[0] % 12 not in momento.clases:
            enviar(self.salida, "note_off", self.canal, self.larga[0], 0)
            self.larga = None
        rng = self._azar(paso)
        if self.larga is None and lugar in (0, 8):
            prob = self.densidad * self.largas * (1.3 if lugar == 0 else 0.5) * (1.5 if en_subida else 1.0)
            if rng.random() < prob:
                largos = [1, 2, 4]
                pesos = [3 if l == self.largo else 1 for l in largos]
                compases = rng.choices(largos, weights=pesos)[0]
                if en_subida:
                    compases = max(compases, 2)
                nota = self._nota(raiz, momento, rng, larga=True)
                fin = tick + compases * TICKS_POR_COMPAS - 2
                hondo = min(1.0, self.profundidad * (rng.uniform(0.7, 1.0)) * (1.3 if en_subida else 1.0))
                enviar(self.salida, "note_on", self.canal, nota, self._vel(rng.uniform(0.85, 1.0)))
                self.larga = (nota, tick, fin, hondo)
                return
        if lugar % 4 and rng.random() < self.densidad * (1 - self.largas) * 0.3:
            nota = self._nota(raiz, momento, rng, arriba=1)
            if self.larga is not None and nota == self.larga[0]:
                return
            if nota in self.cortas:
                enviar(self.salida, "note_off", self.canal, nota, 0)
            enviar(self.salida, "note_on", self.canal, nota, self._vel(rng.uniform(0.5, 0.75)))
            self.cortas[nota] = tick + rng.choice((2, 3, 4))
