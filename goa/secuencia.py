"""Una secuencia del motor: su patrón, su molde y cómo evoluciona.

Separada de motor.py; el motor la toca paso a paso en Motor._tocar_paso.
"""

import math
import random

from . import generador
from .azar import azar as azar_fijo

TICKS_POR_PASO = 6  # 24 pulsos por negra -> 6 por semicorchea
PASOS_POR_COMPAS = 16


def limpiar_molde(molde):
    """El molde es un filtro de notas de 16 pasos: x = pasa, ? = a veces, - = bloquea.
    Vacío = todo bloqueado (al prender el filtro no suena nada hasta abrir pasos).
    Un . de los moldes de antes (libre) pasa."""
    molde = "".join(c if c in "x?-" else "x" for c in str(molde or ""))[:16]
    return molde.ljust(16, "-")


def celda_molde(molde, prob, seed, paso, filtro=True):
    """Si el filtro deja pasar la nota de este paso: "x" pasa, "-" no. Las «a veces»
    se deciden en cada compás. Con el filtro apagado pasa todo."""
    if not filtro:
        return "x"
    celda = molde[paso % 16]
    if celda == "?":
        celda = "x" if azar_fijo(f"{seed}:molde:{paso}") < prob else "-"
    return celda


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
        self.mutacion_ritmo = float(cfg.get("mutacion_ritmo", 0.0))
        self.bloqueada = bool(cfg.get("bloqueada", False))
        self.velocidad = int(cfg.get("velocidad", 100))
        self.acento = int(cfg.get("acento", 120))
        # Afinación
        self.densidad = float(cfg.get("densidad", 1.0))
        self.gate_random = float(cfg.get("gate_random", 0.0))
        self.vel_random = float(cfg.get("vel_random", 0.0))
        self.swing = float(cfg.get("swing", 0.0))
        self.slide = float(cfg.get("slide", 0.0))
        self.acentos = float(cfg.get("acentos", 0.0))
        self.saltos = float(cfg.get("saltos", 0.0))
        self.repeticion = float(cfg.get("repeticion", 0.0))
        self.largas = float(cfg.get("largas", 0.0))
        self.armonia = cfg.get("armonia", "general")  # general, guiada o libre
        self.escala_color = cfg.get("escala_color", "")
        self.filtro = bool(cfg.get("filtro", False))
        self.molde = limpiar_molde(cfg.get("molde", ""))
        self.molde_prob = float(cfg.get("molde_prob", 0.5))
        self.recorrido = cfg.get("recorrido", "adelante")
        self.molde_muta = float(cfg.get("molde_muta", 0.0))
        self.molde_estilo = cfg.get("molde_estilo", "goa")
        self.molde_vivo = self.molde   # el que suena: la mutación del molde lo va cambiando
        self.semitono = float(cfg.get("semitono", 0.0))
        self.fx = bool(cfg.get("fx", False))            # el motor de FX la interviene
        self.cc_filtro = int(cfg.get("cc_filtro", 74))
        # Filtro en las subidas (opcional, sin el motor de FX): se abre de «desde» a «hasta»
        # a lo largo del rise; después del drop vuelve al reposo o se queda donde llegó.
        self.subida_filtro = bool(cfg.get("subida_filtro", False))
        self.subida_desde = max(0, min(127, int(cfg.get("subida_desde", 20))))
        self.subida_hasta = max(0, min(127, int(cfg.get("subida_hasta", 127))))
        self.subida_despues = cfg.get("subida_despues", "vuelve")
        # Dos LFO de filtro (opcionales): cada uno mueve un CC del sinte de la secuencia,
        # sincronizados al compás. Así se pueden mover, por ejemplo, corte y resonancia a la vez.
        self.lfos = [Lfo(cfg, p, self.seed) for p in PREFIJOS_LFO]
        self.lfo = self.lfos[0].activo
        self.lfo_cc = self.lfos[0].cc
        self.filtro_reposo = int(cfg.get("filtro_reposo", 110))
        self.tonalidad = None   # su escala de color (None = la de Música); la arma el motor con la tónica
        self.sonando = {}       # nota -> tick en que se apaga
        self.pendientes = []    # (tick, nota, velocidad, duración) por swing y repeticiones
        self.slide_previo = False
        self.clip = None        # nombre del clip que suena en esta fila, si vino del disparador
        self.reiniciar()

    def reiniciar(self):
        if self.posicion not in generador.POSICIONES:
            raise ValueError(f"Posición desconocida: {self.posicion!r}. Opciones: {', '.join(generador.POSICIONES)}")
        self.patron = generador.generar(self.seed, self.estilo, self.largo, self.pedal)
        self.ritmo_base = [bool(p["suena"]) for p in self.patron]
        self.extra = generador.extras(self.seed, self.largo)

    def evolucionar(self, compas):
        if self.bloqueada or compas <= 0 or compas % self.mutar_cada:
            return
        if self.filtro and self.molde_muta > 0:
            rng = random.Random(f"{self.seed}:molde:{compas}")
            self.molde_vivo = limpiar_molde(generador.mutar_molde(self.molde_vivo, rng, self.molde_muta, self.molde_estilo))
        if self.mutacion <= 0 and self.mutacion_ritmo <= 0:
            return
        self.patron = self._mutado(self.patron, compas)
        guardado = getattr(self, "_director_patron", None)
        if guardado is not None:
            # Mientras suena una variante del director, el patrón propio sigue mutando
            # por debajo: al terminar el período vuelve evolucionado, no al de antes.
            clave, propio = guardado
            self._director_patron = (clave, self._mutado(propio, compas))

    def _mutado(self, patron, compas):
        nuevo = generador.mutar(patron, self.seed, compas, self.mutacion, self.pedal)
        if self.mutacion_ritmo > 0 and len(nuevo) == len(self.ritmo_base):
            nuevo = generador.mutar_ritmo(nuevo, self.seed, compas, self.mutacion_ritmo, self.posicion, self.ritmo_base)
        return nuevo

    def valor_lfo(self, tick):
        """El valor del primer LFO en este pulso (ver Lfo.valor)."""
        return self.lfos[0].valor(tick)


PREFIJOS_LFO = ("lfo", "lfo2")


class Lfo:
    def __init__(self, cfg, prefijo, seed):
        g = lambda k, d: cfg.get(f"{prefijo}{k}", d)  # noqa: E731
        self.prefijo = prefijo
        self.seed = seed
        self.activo = bool(g("", False))
        self.cc = max(0, min(127, int(g("_cc", 74 if prefijo == "lfo" else 71))))
        self.forma = g("_forma", "seno")
        self.compases = max(0.25, min(32.0, float(g("_compases", 4))))
        self.minimo = max(0, min(127, int(g("_min", 30))))
        self.maximo = max(0, min(127, int(g("_max", 100))))
        self.ultimo = None

    def valor(self, tick):
        """El valor del CC en este pulso (24 por negra): seno, triángulo, sube, baja o
        azar (valores al azar que se unen suave, repetibles con la seed)."""
        periodo = self.compases * 96
        f = (tick % periodo) / periodo
        forma = self.forma
        if forma == "triangulo":
            y = 1 - abs(2 * f - 1)
        elif forma == "sube":
            y = f
        elif forma == "baja":
            y = 1 - f
        elif forma == "azar":
            pasos = 8
            k, r = divmod(f * pasos, 1)
            vuelta = int(tick // periodo)
            clave = f"{self.seed}:{self.prefijo}"
            a = azar_fijo(f"{clave}:{vuelta}:{int(k)}")
            b = azar_fijo(f"{clave}:{vuelta + (int(k) + 1) // pasos}:{(int(k) + 1) % pasos}")
            y = a + (b - a) * (0.5 - 0.5 * math.cos(math.pi * r))
        else:  # seno: parte abajo, sube y vuelve
            y = 0.5 - 0.5 * math.cos(2 * math.pi * f)
        return round(self.minimo + (self.maximo - self.minimo) * y)
