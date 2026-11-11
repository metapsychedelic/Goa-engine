"""Motor: sigue el reloj de la Circuit y la nota larga, y toca las secuencias.

No depende de mido: recibe eventos simples y envía notas a través de
una función `enviar(salida, tipo, canal, nota, velocidad)`, para poder
probarlo sin hardware.
"""

import logging
import random
import time
from collections import deque

from . import armonia, generador
from .bajo import Bajo
from .dialogo import Dialogo
from .escalas import Tonalidad, nombre_midi
from .pads import Pads, _cerca

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
        self.sonando = {}       # nota -> tick en que se apaga
        self.pendientes = []    # (tick, nota, velocidad, duración) por swing y repeticiones
        self.slide_previo = False
        self.clip = None        # nombre del clip que suena en esta fila, si vino del disparador
        self.reiniciar()

    def reiniciar(self):
        if self.posicion not in generador.POSICIONES:
            raise ValueError(f"Posición desconocida: {self.posicion!r}. Opciones: {', '.join(generador.POSICIONES)}")
        self.patron = generador.generar(self.seed, self.estilo, self.largo, self.pedal)
        self.extra = generador.extras(self.seed, self.largo)

    def evolucionar(self, compas):
        if not self.bloqueada and self.mutacion > 0 and compas > 0 and compas % self.mutar_cada == 0:
            self.patron = generador.mutar(self.patron, self.seed, compas, self.mutacion, self.pedal)


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


class Motor:
    def __init__(self, config, enviar):
        self.enviar = enviar
        self.secuencias = []
        self.disparos = {}
        self.corriendo = False
        self.tick = -1
        self.relojes = deque(maxlen=48)
        self.pads = None
        self.dialogo = None
        self.bajo = None
        self.cola = {}  # fila -> (cfg, nombre) o None para detener; se aplica en el próximo compás
        self.cola_dialogo = False  # False = nada en cola · None = detener · (secciones, nombre) = lanzar
        self.musica = {}
        self.aplicar_config(config)

    def aplicar_config(self, config):
        """Cambia la configuración en vivo, sin detener el reloj."""
        musica = config.get("musica", {})
        entrada = config.get("entrada", {})
        tonalidad = Tonalidad(musica.get("tonica", "F"), musica.get("escala", "frigio"))
        secuencias = [Secuencia(c) for c in config.get("secuencia", [])]
        desplazamiento = musica.get("desplazamiento", 0.0)
        pads = Pads(config.get("pads", {}), tonalidad, desplazamiento)
        bajo = Bajo(config.get("bajo", {}), tonalidad)
        self.musica = musica
        self.canal_disparo = int(entrada.get("canal_disparo", 2)) - 1
        dialogo = self._crear_dialogo(config.get("dialogo", {}), config.get("llamada", {}), config.get("respuesta", {}))
        self.apagar_todo()
        if self.dialogo is not None:
            dialogo.clip = self.dialogo.clip  # recuerda qué clip de diálogo sonaba
            dialogo.continuar_de(self.dialogo)  # sigue la conversación sin callarse ni perder lo mutado
        self.tonalidad = tonalidad
        self.adaptacion = musica.get("adaptacion", "escala")
        self.cambio = musica.get("cambio_de_nota", "paso")
        self.canal_disparo = int(entrada.get("canal_disparo", 2)) - 1
        self.nota_maxima = int(entrada.get("nota_maxima", 4))
        # Cada secuencia y los pads escuchan su propia pista; 0 = la general.
        for i, (s, c) in enumerate(zip(secuencias, config.get("secuencia", []))):
            s.disparo = self._canal_de(c)
            if i < len(self.secuencias):
                vieja = self.secuencias[i]
                s.clip = vieja.clip  # recuerda qué clip sonaba en esa fila
                if (vieja.seed, vieja.estilo, vieja.largo, vieja.pedal) == (s.seed, s.estilo, s.largo, s.pedal):
                    # Mismo patrón de base: conserva lo que ya mutó. Antes, mover cualquier
                    # control de la app devolvía la secuencia a su patrón original.
                    s.patron = vieja.patron
        pads.disparo = self._canal_de(config.get("pads", {}))
        bajo.disparo = self._canal_de(config.get("bajo", {}))
        canales = {s.disparo for s in secuencias} | {pads.disparo, dialogo.disparo, bajo.disparo, self.canal_disparo}
        anteriores = self.disparos
        self.disparos = {c: anteriores.get(c) or Disparo(c) for c in canales}
        self.secuencias = secuencias
        self.pads = pads
        self.dialogo = dialogo
        self.bajo = bajo
        self.seguir_pads = bool(musica.get("seguir_pads", False))
        self.tension = float(musica.get("tension", 0.3))
        self.anticipar = bool(musica.get("anticipar", True))

    def _modo_armonia(self, propio):
        """Modo efectivo de un motor: el suyo, o el general de Música."""
        return propio if propio in armonia.MODOS else self.musica.get("armonia", "guiada")

    def _canal_de(self, c):
        return int(c["disparo"]) - 1 if c.get("disparo") else self.canal_disparo

    # --- Disparador de clips ---

    def lanzar(self, fila, cfg, nombre):
        """Pone un clip en cola para la fila; entra en el próximo compás."""
        if not 0 <= fila < len(self.secuencias):
            raise ValueError("Fila inexistente")
        Secuencia(cfg)  # valida antes de encolar
        self.cola[fila] = (cfg, nombre)
        if not self.corriendo:
            self._aplicar_cola()

    def detener(self, fila):
        if not 0 <= fila < len(self.secuencias):
            raise ValueError("Fila inexistente")
        self.cola[fila] = None
        if not self.corriendo:
            self._aplicar_cola()

    def lanzar_dialogo(self, dialogo, llamada, respuesta, nombre):
        """Pone un clip de diálogo en cola; entra en el próximo compás con todo su seteo."""
        self._crear_dialogo(dialogo, llamada, respuesta)  # valida antes de encolar
        self.cola_dialogo = ((dialogo, llamada, respuesta), nombre)
        if not self.corriendo:
            self._aplicar_cola_dialogo()

    def detener_dialogo(self):
        self.cola_dialogo = None
        if not self.corriendo:
            self._aplicar_cola_dialogo()

    def _crear_dialogo(self, dialogo, llamada, respuesta):
        m = self.musica
        nuevo = Dialogo(dialogo, llamada, respuesta, m.get("tonica", "F"), m.get("escala", "frigio"),
                        m.get("adaptacion", "escala"), m.get("desplazamiento", 0.0))
        nuevo.disparo = self._canal_de(dialogo)
        nuevo.guiada = self._modo_armonia(dialogo.get("armonia", "general")) == "guiada"
        nuevo.tension = float(m.get("tension", 0.3))
        nuevo.anticipar = bool(m.get("anticipar", True))
        return nuevo

    def _aplicar_cola_dialogo(self):
        pedido, self.cola_dialogo = self.cola_dialogo, False
        if pedido is False:
            return
        self.dialogo.apagar(self.enviar)
        if pedido is None:
            self.dialogo.activo = False
            self.dialogo.reiniciar()
            log.info("Diálogo detenido")
            return
        (dialogo, llamada, respuesta), nombre = pedido
        nuevo = self._crear_dialogo(dialogo, llamada, respuesta)
        if nuevo.disparo not in self.disparos:
            self.disparos[nuevo.disparo] = Disparo(nuevo.disparo)
        nuevo.clip = nombre
        self.dialogo = nuevo
        log.info("Entra el diálogo %s", nombre)

    def _aplicar_cola(self):
        for fila, pedido in self.cola.items():
            if fila >= len(self.secuencias):
                continue
            vieja = self.secuencias[fila]
            for nota in list(vieja.sonando):
                self.enviar(vieja.salida, "note_off", vieja.canal, nota, 0)
            vieja.sonando.clear()
            vieja.pendientes = []
            if pedido is None:
                vieja.activa = False
                continue
            cfg, nombre = pedido
            nueva = Secuencia(cfg)
            nueva.disparo = self._canal_de(cfg)
            if nueva.disparo not in self.disparos:
                self.disparos[nueva.disparo] = Disparo(nueva.disparo)
            nueva.clip = nombre
            self.secuencias[fila] = nueva
            log.info("Fila %d: entra el clip %s", fila + 1, nombre)
        self.cola = {}

    @property
    def canales_disparo(self):
        return set(self.disparos)

    def estado(self):
        bpm = None
        if len(self.relojes) >= 24:
            intervalo = (self.relojes[-1] - self.relojes[0]) / (len(self.relojes) - 1)
            if intervalo > 0:
                bpm = round(60 / (intervalo * 24), 1)
        paso = max(self.tick, 0) // TICKS_POR_PASO
        raices = {c + 1: nombre_midi(d.raiz) for c, d in sorted(self.disparos.items()) if d.raiz is not None}
        return {
            "corriendo": self.corriendo,
            "bpm": bpm if self.corriendo else None,
            "raiz": " · ".join(raices.values()) or None,
            "raices": raices,
            "compas": paso // PASOS_POR_COMPAS + 1 if self.corriendo else None,
            "acorde": self._acorde_estado(paso),
            "dialogo": self.dialogo.fase if self.dialogo and self.dialogo.activo and self.corriendo else None,
            "filas": [{"clip": s.clip, "activa": s.activa,
                       "cola": (None if i not in self.cola else
                                ("detener" if self.cola[i] is None else self.cola[i][1]))}
                      for i, s in enumerate(self.secuencias)],
            "fila_dialogo": {"clip": self.dialogo.clip, "activa": self.dialogo.activo,
                             "cola": (None if self.cola_dialogo is False else
                                      ("detener" if self.cola_dialogo is None else self.cola_dialogo[1]))},
        }

    def _acorde_estado(self, paso):
        if not self.pads or not self.pads.activo:
            return None
        if self.pads.suenan:
            return self.pads.descripcion()
        m = self.pads.momento(paso, self.disparos[self.pads.disparo].raiz)
        return None if m is None else f"{nombre_midi(m.raiz)} (solo guía)"

    def _olvidar_notas(self):
        for d in self.disparos.values():
            d.olvidar()

    # --- Eventos que llegan de la Circuit ---

    def start(self):
        log.info("Start")
        self.apagar_todo()
        self._olvidar_notas()  # la Circuit vuelve a mandar sus notas desde el primer paso
        for s in self.secuencias:
            s.reiniciar()
        self.dialogo.reiniciar()
        self.corriendo = True
        self.tick = -1

    def continuar(self):
        log.info("Continue")
        self.corriendo = True

    def stop(self):
        log.info("Stop")
        self.corriendo = False
        self.apagar_todo()
        self.dialogo.reiniciar()
        self._olvidar_notas()  # al parar, la Circuit no siempre manda el note_off

    def reloj(self):
        self.relojes.append(time.monotonic())
        if not self.corriendo:
            return
        self.tick += 1
        self._apagar_vencidas()
        self.dialogo.tick(self.tick, self.enviar)
        self.pads.tick(self.tick, self.enviar)
        self.bajo.tick(self.tick, self.enviar)
        if self.tick % TICKS_POR_PASO == 0:
            self._paso(self.tick // TICKS_POR_PASO)
        elif self.tick % TICKS_POR_PASO == 2:
            # Los pads deciden dos pulsos después del paso: si la nota larga termina
            # justo en el cambio de compás, su note_off ya llegó y no suena un acorde suelto.
            d = self.disparos[self.pads.disparo]
            raiz = None if d.pendiente is None else (d.raiz if d.raiz is not None else d.pendiente)
            self.pads.actualizar(self.tick // TICKS_POR_PASO, raiz, self.tick, self.enviar)

    def nota_on(self, canal, nota, velocidad=100):
        if canal == self.dialogo.escucha:
            self.dialogo.entrada_on(nota, velocidad, self.tick)
        d = self.disparos.get(canal)
        if d is None:
            return
        estaba_en_silencio = d.raiz is None
        d.on(nota, self.tick)
        log.info("Canal %d: nota disparadora %s", canal + 1, nombre_midi(nota))
        # La nota de la Circuit suele llegar justo después del pulso del paso.
        # Si ese canal estaba en silencio y la nota va tarde por poco, tocamos ese paso igual.
        if self.corriendo and estaba_en_silencio and self.tick >= 0 and self.tick % TICKS_POR_PASO <= 2:
            paso = self.tick // TICKS_POR_PASO
            if self.cambio == "paso" or paso % PASOS_POR_COMPAS == 0:
                d.raiz = nota
                self._tocar_paso(paso, solo_canal=canal)
                if self.dialogo.disparo == canal:
                    self._paso_dialogo(paso)
                if self.bajo.disparo == canal:
                    self._paso_bajo(paso)

    def nota_off(self, canal, nota):
        if canal == self.dialogo.escucha:
            self.dialogo.entrada_off(nota, self.tick)
        d = self.disparos.get(canal)
        if d is not None:
            d.off(nota, self.tick)

    # --- Lógica interna ---

    def _paso(self, paso):
        if paso % PASOS_POR_COMPAS == 0:
            if self.cola:
                self._aplicar_cola()  # los clips entran justo en el primer paso del compás
            if self.cola_dialogo is not False:
                self._aplicar_cola_dialogo()
            compas = paso // PASOS_POR_COMPAS
            for s in self.secuencias:
                s.evolucionar(compas)
        for d in self.disparos.values():
            d.paso(paso, self.tick, self.cambio, self.nota_maxima)
        self._tocar_paso(paso)
        self._paso_dialogo(paso)
        self._paso_bajo(paso)

    def _momento(self, paso, raiz):
        """Momento armónico en `paso`: el de los pads, o el acorde sobre la nota larga `raiz`."""
        if self.pads.activo:
            m = self.pads.momento(paso, self.disparos[self.pads.disparo].raiz)
            if m is not None:
                return m
        return None if raiz is None else armonia.de_nota_larga(raiz, self.tonalidad)

    def _paso_bajo(self, paso):
        """El bajo toca la raíz del acorde (guiada) o la de su nota larga (libre)."""
        raiz = self.disparos[self.bajo.disparo].raiz
        if raiz is None:
            return
        if self._modo_armonia(self.bajo.armonia) == "guiada":
            momento = self._momento(paso, raiz)
            if momento is not None and momento.siguiente is not None:
                raiz = _cerca(momento.raiz % 12, raiz)
            self.bajo.paso(paso, self.tick, raiz, momento, self.anticipar, self.enviar)
        else:
            self.bajo.paso(paso, self.tick, raiz, None, False, self.enviar)

    def _raiz_con_pads(self, raiz):
        if raiz is not None and self.seguir_pads and self.pads.activo and self.pads.raiz_acorde is not None:
            # Toma como base la raíz del acorde que suena, cerca de su nota larga.
            return _cerca(self.pads.raiz_acorde % 12, raiz)
        return raiz

    def _paso_dialogo(self, paso):
        raiz = self.disparos[self.dialogo.disparo].raiz
        acorde = None
        if self.dialogo.guiada:
            momento = self._momento(paso, raiz if self.dialogo.modo == "motor" else self.dialogo.raiz_vivo)
            if momento is not None and self.pads.activo and momento.siguiente is not None:
                if self.dialogo.modo == "motor":
                    raiz = None if raiz is None else _cerca(momento.raiz % 12, raiz)
                else:
                    raiz = momento.raiz
            self.dialogo.paso(paso, self.tick, raiz, self.enviar, momento)
            return
        if self.dialogo.seguir_pads and self.pads.activo:
            # Sigue la progresión de los pads: la raíz del acorde y sus notas.
            raiz_acorde, acorde = self.pads.acorde_en(paso, self.disparos[self.pads.disparo].raiz)
            if raiz_acorde is not None:
                if self.dialogo.modo == "motor":
                    # Sigue esperando su nota larga; con ella, toma la raíz del acorde cerca.
                    raiz = None if raiz is None else _cerca(raiz_acorde % 12, raiz)
                else:
                    raiz = raiz_acorde  # en vivo solo importa la clase: el registro lo pones tú
        else:
            raiz = self._raiz_con_pads(raiz)
        self.dialogo.paso(paso, self.tick, raiz, self.enviar)

    def _tocar_paso(self, paso, solo_canal=None):
        for s in self.secuencias:
            if solo_canal is not None and s.disparo != solo_canal:
                continue
            raiz = self.disparos[s.disparo].raiz
            i = paso % s.largo
            p = s.patron[i]
            x = s.extra[p.get("fuente", i)]
            if (raiz is None or not s.activa or not generador.pasa_posicion(s.posicion, paso)
                    or not p["suena"] or x["densidad"] >= s.densidad):
                s.slide_previo = False
                continue
            guiada = self._modo_armonia(s.armonia) == "guiada"
            momento = self._momento(paso, raiz) if guiada else None
            if momento is not None and momento.siguiente is not None:
                # Guiada con pads: la base es la raíz del acorde, cerca de su nota larga.
                raiz = _cerca(momento.raiz % 12, raiz)
            elif not guiada and self.seguir_pads and self.pads.activo and self.pads.raiz_acorde is not None:
                # Toma como base la raíz del acorde que suena, cerca de su nota larga.
                raiz = _cerca(self.pads.raiz_acorde % 12, raiz)
            octava = s.octava + p.get("octava", 0) + (x["direccion"] if x["salto"] < s.saltos else 0)
            nota = self.tonalidad.nota(raiz, p["grado"] + s.relacion, self.adaptacion) + 12 * octava
            if momento is not None:
                azar_arm = random.Random(f"{s.seed}:armonia:{i}").random()
                ultima = momento.cambia_pronto and self._ultima_antes_del_cambio(s, paso, momento.falta)
                nota = armonia.ajustar(nota, momento, self.tonalidad, generador.es_fuerte(s.posicion, paso), ultima,
                                       self.tension, self.anticipar, azar_arm)
            nota = max(0, min(127, nota))
            if "pref_acento" in p:
                # Ácido 303: la cantidad de acentos y slides la regula el usuario;
                # el patrón solo dice dónde calzan mejor.
                acento = x["acento"] < s.acentos * p["pref_acento"]
                slide = x["slide"] < s.slide * p["pref_slide"]
            else:
                acento = p["acento"] or x["acento"] < s.acentos
                slide = p.get("slide", False) or x["slide"] < s.slide
            azar = random.Random(f"{s.seed}:{paso}")  # determinista: misma seed, mismo resultado
            velocidad = (s.acento if acento else s.velocidad) + round(s.vel_random * 30 * azar.uniform(-1, 1))
            velocidad = max(1, min(127, velocidad))
            gate = s.gate * p.get("gate_mult", 1.0)
            gate = max(0.05, min(1.0, gate * (1 + s.gate_random * azar.uniform(-1, 1))))
            duracion = max(1, round(TICKS_POR_PASO * gate))
            if slide:
                # Slide 303: la nota dura hasta pisar la siguiente; un sinte en modo
                # legato con glide hace el deslizamiento.
                duracion = TICKS_POR_PASO + 2
            elif x.get("larga", 1.0) < s.largas:
                # Nota larga: se sostiene sobre los silencios que la siguen (hasta 4 pasos).
                silencios = 0
                while silencios < 3 and not s.patron[(i + silencios + 1) % s.largo]["suena"]:
                    silencios += 1
                if silencios:
                    duracion = (silencios + 1) * TICKS_POR_PASO - 1
            inicio = self.tick + (round(s.swing * TICKS_POR_PASO) if paso % 2 == 1 else 0)
            if s.slide_previo and nota in s.sonando:
                # Tie: misma nota después de un slide, se prolonga sin volver a tocarla.
                s.sonando[nota] = max(s.sonando[nota], inicio + duracion)
            elif not slide and x["repeticion"] < s.repeticion:
                # Repetición (ratchet): dos golpes de fusa en el mismo paso.
                mitad = TICKS_POR_PASO // 2
                self._programar(s, inicio, nota, velocidad, max(1, mitad - 1))
                self._programar(s, inicio + mitad, nota, max(1, velocidad - 15), max(1, mitad - 1))
            else:
                self._programar(s, inicio, nota, velocidad, duracion)
            s.slide_previo = slide

    @staticmethod
    def _ultima_antes_del_cambio(s, paso, falta):
        """True si ninguna otra nota de la secuencia suena antes del cambio de acorde."""
        for k in range(1, falta):
            q = paso + k
            j = q % s.largo
            pq = s.patron[j]
            if (pq["suena"] and generador.pasa_posicion(s.posicion, q)
                    and s.extra[pq.get("fuente", j)]["densidad"] < s.densidad):
                return False
        return True

    def _programar(self, s, tick, nota, velocidad, duracion):
        if tick <= self.tick:
            self._encender(s, nota, velocidad, self.tick + duracion)
        else:
            s.pendientes.append((tick, nota, velocidad, duracion))

    def _encender(self, s, nota, velocidad, fin):
        if nota in s.sonando:
            self.enviar(s.salida, "note_off", s.canal, nota, 0)
        self.enviar(s.salida, "note_on", s.canal, nota, velocidad)
        s.sonando[nota] = fin

    def _apagar_vencidas(self):
        for s in self.secuencias:
            for nota, fin in list(s.sonando.items()):
                if fin <= self.tick:
                    self.enviar(s.salida, "note_off", s.canal, nota, 0)
                    del s.sonando[nota]
            if s.pendientes:
                listas = [p for p in s.pendientes if p[0] <= self.tick]
                s.pendientes = [p for p in s.pendientes if p[0] > self.tick]
                for _, nota, velocidad, duracion in listas:
                    self._encender(s, nota, velocidad, self.tick + duracion)

    def apagar_todo(self):
        for s in self.secuencias:
            for nota in list(s.sonando):
                self.enviar(s.salida, "note_off", s.canal, nota, 0)
            s.sonando.clear()
            s.pendientes = []
            s.slide_previo = False
        if self.pads is not None:
            self.pads.apagar(self.enviar)
        if self.dialogo is not None:
            self.dialogo.apagar(self.enviar)
        if self.bajo is not None:
            self.bajo.apagar(self.enviar)
