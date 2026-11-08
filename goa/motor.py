"""Motor: sigue el reloj de la Circuit y la nota larga, y toca las secuencias.

No depende de mido: recibe eventos simples y envía notas a través de
una función `enviar(salida, tipo, canal, nota, velocidad)`, para poder
probarlo sin hardware.
"""

import logging

from . import generador
from .escalas import Tonalidad, nombre_midi

TICKS_POR_PASO = 6  # 24 pulsos por negra -> 6 por semicorchea
PASOS_POR_COMPAS = 16

log = logging.getLogger("goa")


class Secuencia:
    def __init__(self, cfg):
        self.nombre = cfg.get("nombre", "?")
        self.activa = cfg.get("activa", True)
        self.salida = cfg["salida"]
        self.canal = int(cfg.get("canal", 1)) - 1
        self.estilo = cfg.get("estilo", "rolling")
        self.posicion = cfg.get("posicion", "offbeat")
        self.relacion = generador.RELACIONES[cfg.get("relacion", "unisono")]
        self.octava = int(cfg.get("octava", 0))
        self.largo = int(cfg.get("largo", 16))
        self.gate = float(cfg.get("gate", 0.55))
        self.pedal = float(cfg.get("pedal", 0.5))
        self.seed = str(cfg.get("seed", "goa"))
        self.mutacion = float(cfg.get("mutacion", 0.0))
        self.mutar_cada = max(1, int(cfg.get("mutar_cada", 8)))
        self.bloqueada = bool(cfg.get("bloqueada", False))
        self.velocidad = int(cfg.get("velocidad", 100))
        self.acento = int(cfg.get("acento", 120))
        self.sonando = {}  # nota -> tick en que se apaga
        self.reiniciar()

    def reiniciar(self):
        if self.posicion not in generador.POSICIONES:
            raise ValueError(f"Posición desconocida: {self.posicion!r}. Opciones: {', '.join(generador.POSICIONES)}")
        self.patron = generador.generar(self.seed, self.estilo, self.largo, self.pedal)

    def evolucionar(self, compas):
        if not self.bloqueada and self.mutacion > 0 and compas > 0 and compas % self.mutar_cada == 0:
            self.patron = generador.mutar(self.patron, self.seed, compas, self.mutacion, self.pedal)


class Motor:
    def __init__(self, config, enviar):
        musica = config.get("musica", {})
        entrada = config.get("entrada", {})
        self.tonalidad = Tonalidad(musica.get("tonica", "F"), musica.get("escala", "frigio"))
        self.adaptacion = musica.get("adaptacion", "escala")
        self.cambio = musica.get("cambio_de_nota", "paso")
        self.canal_disparo = int(entrada.get("canal_disparo", 4)) - 1
        self.secuencias = [Secuencia(c) for c in config.get("secuencia", [])]
        self.enviar = enviar
        self.corriendo = False
        self.tick = -1
        self.sostenidas = []
        self.raiz = None
        self.raiz_pendiente = None
        self.soltada_en = -1

    # --- Eventos que llegan de la Circuit ---

    def start(self):
        log.info("Start")
        self.apagar_todo()
        for s in self.secuencias:
            s.reiniciar()
        self.corriendo = True
        self.tick = -1

    def continuar(self):
        log.info("Continue")
        self.corriendo = True

    def stop(self):
        log.info("Stop")
        self.corriendo = False
        self.apagar_todo()

    def reloj(self):
        if not self.corriendo:
            return
        self.tick += 1
        self._apagar_vencidas()
        if self.tick % TICKS_POR_PASO == 0:
            self._paso(self.tick // TICKS_POR_PASO)

    def nota_on(self, canal, nota):
        if canal != self.canal_disparo:
            return
        if nota in self.sostenidas:
            self.sostenidas.remove(nota)
        self.sostenidas.append(nota)
        self.raiz_pendiente = nota
        log.info("Nota disparadora %s", nombre_midi(nota))
        # La nota de la Circuit suele llegar justo después del pulso del paso.
        # Si estábamos en silencio y va tarde por poco, tocamos ese paso igual.
        if self.corriendo and self.raiz is None and self.tick >= 0 and self.tick % TICKS_POR_PASO <= 2:
            paso = self.tick // TICKS_POR_PASO
            if self.cambio == "paso" or paso % PASOS_POR_COMPAS == 0:
                self.raiz = nota
                self._tocar_paso(paso)

    def nota_off(self, canal, nota):
        if canal != self.canal_disparo:
            return
        if nota in self.sostenidas:
            self.sostenidas.remove(nota)
        self.raiz_pendiente = self.sostenidas[-1] if self.sostenidas else None
        if self.raiz_pendiente is None:
            self.soltada_en = self.tick

    # --- Lógica interna ---

    def _paso(self, paso):
        if paso % PASOS_POR_COMPAS == 0:
            compas = paso // PASOS_POR_COMPAS
            for s in self.secuencias:
                s.evolucionar(compas)
        if self.raiz_pendiente is None:
            # Un paso de gracia: al pasar de una nota a otra en la Circuit
            # puede haber un instante sin nota, y eso no debe cortar el patrón.
            if self.tick - self.soltada_en >= TICKS_POR_PASO:
                self.raiz = None
        elif self.cambio == "paso" or paso % PASOS_POR_COMPAS == 0 or self.raiz is None:
            self.raiz = self.raiz_pendiente
        self._tocar_paso(paso)

    def _tocar_paso(self, paso):
        if self.raiz is None:
            return
        for s in self.secuencias:
            if not s.activa or not generador.pasa_posicion(s.posicion, paso):
                continue
            p = s.patron[paso % s.largo]
            if not p["suena"]:
                continue
            nota = self.tonalidad.nota(self.raiz, p["grado"] + s.relacion, self.adaptacion) + 12 * s.octava
            nota = max(0, min(127, nota))
            if nota in s.sonando:
                self.enviar(s.salida, "note_off", s.canal, nota, 0)
            velocidad = s.acento if p["acento"] else s.velocidad
            self.enviar(s.salida, "note_on", s.canal, nota, velocidad)
            s.sonando[nota] = self.tick + max(1, round(TICKS_POR_PASO * s.gate))

    def _apagar_vencidas(self):
        for s in self.secuencias:
            for nota, fin in list(s.sonando.items()):
                if fin <= self.tick:
                    self.enviar(s.salida, "note_off", s.canal, nota, 0)
                    del s.sonando[nota]

    def apagar_todo(self):
        for s in self.secuencias:
            for nota in list(s.sonando):
                self.enviar(s.salida, "note_off", s.canal, nota, 0)
            s.sonando.clear()
