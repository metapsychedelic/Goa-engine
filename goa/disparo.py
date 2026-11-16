"""La nota larga de cada canal de la Circuit: qué raíz manda y cuándo se soltó."""

import logging

from .escalas import nombre_midi
from .secuencia import PASOS_POR_COMPAS, TICKS_POR_PASO

log = logging.getLogger("goa")


class Disparo:
    """Estado de la nota larga de un canal de la Circuit."""

    def __init__(self, canal):
        self.canal = canal
        self.olvidar()

    def olvidar(self):
        self.sostenidas = []
        self.vistas = {}  # nota -> tick de su último note_on
        self.raiz = None
        self.pendiente = None
        self.soltada_en = -1

    def on(self, nota, tick):
        if nota in self.sostenidas:
            self.sostenidas.remove(nota)
        self.sostenidas.append(nota)
        self.vistas[nota] = tick
        self.pendiente = nota

    def off(self, nota, tick):
        if nota in self.sostenidas:
            self.sostenidas.remove(nota)
        self.vistas.pop(nota, None)
        self.pendiente = self.sostenidas[-1] if self.sostenidas else None
        if self.pendiente is None:
            self.soltada_en = tick

    def paso(self, paso, tick, cambio, nota_maxima):
        if nota_maxima > 0:
            # Vigilancia: la Circuit repite sus notas en cada vuelta del patrón.
            # Una nota que no se repite en tantos compases perdió su note_off.
            limite = nota_maxima * PASOS_POR_COMPAS * TICKS_POR_PASO
            for nota in list(self.sostenidas):
                if tick - self.vistas.get(nota, tick) > limite:
                    log.info("Canal %d: nota %s sin repetirse, la doy por soltada", self.canal + 1, nombre_midi(nota))
                    self.off(nota, tick)
                    self.soltada_en = tick - TICKS_POR_PASO  # sin paso de gracia
        if self.pendiente is None:
            # Medio paso de gracia: al pasar de una nota a otra en la Circuit
            # puede haber un instante sin nota, y eso no debe cortar el patrón.
            if tick - self.soltada_en >= TICKS_POR_PASO // 2:
                self.raiz = None
        elif cambio == "paso" or paso % PASOS_POR_COMPAS == 0 or self.raiz is None:
            self.raiz = self.pendiente
