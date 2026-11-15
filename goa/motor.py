"""Motor: sigue el reloj de la Circuit y la nota larga, y toca las secuencias.

No depende de mido: recibe eventos simples y envía notas a través de
una función `enviar(salida, tipo, canal, nota, velocidad)`, para poder
probarlo sin hardware.
"""

import copy
import logging
import random
import time
from collections import deque

from . import armonia, forma, fx, generador
from .bajo import Bajo
from .dialogo import Dialogo
from .director import Director
from .escalas import Tonalidad, nombre_midi
from .fx import Fx
from .pads import Pads, _cerca, raiz_tension

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
        self.semitono = float(cfg.get("semitono", 0.0))
        self.fx = bool(cfg.get("fx", False))            # el motor de FX la interviene
        self.cc_filtro = int(cfg.get("cc_filtro", 74))
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
        self.config = None
        self.config_aplicada = None
        self.config_en_cola = None  # cambios que entran en el próximo compás
        self.cola_bajo = None  # bajo nuevo que entra en el próximo compás (cambio al vuelo)
        self.cola = {}  # fila -> (cfg, nombre) o None para detener; se aplica en el próximo compás
        self.cola_dialogo = False  # False = nada en cola · None = detener · (secciones, nombre) = lanzar
        self.musica = {}
        self.base = None            # la configuración que pidió la app (sin energía ni transición)
        self.conductor = forma.Conductor()
        self.director = Director()
        self.origen_progresion = 0  # compás donde parte la progresión de los pads
        self.puente = None          # (tonalidad nueva, base de los pads, paso del cambio) durante un acorde puente
        self.version_base = 0       # sube cuando la canción cambia de parte (la app se recarga)
        self.programas = {}         # (salida, canal) -> último Program Change mandado
        # Efectos de subida de la parte de la canción que suena (ver _efectos_parte)
        self.roll_desde, self.roll_compases = None, 0
        self.hueco_desde = None
        self.tension_pc, self.tension_fin, self.resolver_en = None, None, None
        self.saltar_parte_a = None  # parte pedida desde la app (entra en el próximo compás)
        self.fx = None
        # Subida de FX: {"desde": paso, "hasta": paso del drop, "origen": manual, cancion o piloto}
        self.subida = None
        self.subida_pedida = None   # compases de la subida pedida desde la app (0 = cancelar)
        self.cc_secuencias = {}     # (salida, canal, cc) -> (valor mandado, reposo): filtros intervenidos
        self.aplicar_config(config)

    def aplicar_config(self, config):
        """Cambia la configuración en vivo, sin detener el reloj ni cortar nada.

        Con el motor andando, las secuencias cambian al tiempo (una variante o un estilo
        nuevo se escucha de inmediato). Todo lo demás (pads, bajo, diálogo, tónica,
        escala, armonía…) entra en el primer paso del próximo compás, y en ese cambio
        las notas que suenan terminan solas y los pads pasan en ligado."""
        config = copy.deepcopy(config)
        config.setdefault("forma", {"energia": 0.5})
        self.base = config
        tr = self.conductor.transicion
        if tr is not None:
            # Lo que cambias durante una transición va al destino; la transición sigue.
            tr.destino = copy.deepcopy(config)
            tr.umbrales = tr._umbrales()
        if self.corriendo and self.tick >= 0 and self.config is not None:
            efectiva = self.conductor.efectiva(config, self._compas_actual())
            ahora = dict(self.config, secuencia=efectiva.get("secuencia", []))
            self._aplicar(ahora)
            self.config_en_cola = None if efectiva == ahora else efectiva
        else:
            self.config_en_cola = None
            self.conductor.energia = None  # detenido: la energía queda donde la pediste
            self._aplicar(self.conductor.efectiva(config, 0))

    def _compas_actual(self):
        return max(self.tick, 0) // (TICKS_POR_PASO * PASOS_POR_COMPAS)

    def saltar_seccion(self, clave):
        """Piloto: pasa a la sección `clave` en el próximo compás."""
        if clave not in forma.PLAN:
            raise ValueError(f"Sección desconocida: {clave}")
        self.conductor.saltar_a = clave

    def saltar_parte(self, indice):
        """Canción: pasa a la parte `indice` en el próximo compás (para volver a cuadrar con la Circuit)."""
        if not (0 <= indice < len(self.base.get("parte", []))):
            raise ValueError("Esa parte no existe")
        self.saltar_parte_a = indice

    def _config_parte(self, indice):
        """La configuración de la parte `indice`: lo que suena ahora con el carácter de su escena."""
        from .config import normalizar  # aquí para no importar en círculo
        p = self.base["parte"][indice]
        if p["escena"] < 0 or p["escena"] >= len(self.base.get("escena", [])):
            return None  # sin escena: sigue lo que suena
        destino = normalizar(forma.mezclar(self.base, self.base["escena"][p["escena"]]))
        destino["forma"]["escena"] = p["escena"]
        return destino

    def _avanzar_cancion(self, compas):
        """Primer paso de cada compás, en modo canción: lanza cada parte para que llegue
        completa justo en su primer compás (junto con la escena de la Circuit)."""
        c = self.conductor
        if not forma.cancion_activa(self.base):
            c.cancion = None
            self.saltar_parte_a = None
            return
        partes = self.base["parte"]
        if self.saltar_parte_a is not None:
            c.cancion = {"origen": compas - forma.inicio_parte(partes, self.saltar_parte_a), "lanzada": None}
            self.saltar_parte_a = None
        if c.cancion is None:
            c.cancion = {"origen": compas, "lanzada": None}  # la canción parte aquí (en el Start, compás 0)
        ahora = c.parte(self.base, compas)
        if ahora is None:
            return
        inicio_actual = compas - ahora["dentro"]
        objetivo = None
        if ahora["dentro"] == 0 and c.cancion["lanzada"] != compas:
            objetivo = (ahora["i"], compas)  # la parte empieza ya y nadie la lanzó (inicio o salto)
        else:
            fin = inicio_actual + ahora["largo"]  # primer compás de la parte siguiente
            siguiente = c.parte(self.base, fin)
            if siguiente is not None and fin != c.cancion["lanzada"] and (siguiente["i"], siguiente["vuelta"]) != (ahora["i"], ahora["vuelta"]):
                p = partes[siguiente["i"]]
                # Suave: la transición ocupa como mucho la mitad de la parte que suena (que
                # se alcance a escuchar tal como es). Golpe: entra de una en el uno.
                largo_tr = 1 if p["entrada"] == "golpe" else max(1, min(int(self.base["forma"].get("transicion", 8)), ahora["largo"] // 2))
                if compas >= fin - largo_tr + 1:
                    objetivo = (siguiente["i"], fin)
        if objetivo is None:
            return
        indice, llega = objetivo
        c.cancion["lanzada"] = llega
        destino = self._config_parte(indice)
        if destino is None:
            return
        tr = c.transicion
        origen = tr.config(compas) if tr is not None else self.base
        c.lanzar(origen, destino, compas, llega - compas + 1, partes[indice]["escena"], escalonar=False)
        self.base = destino
        self.version_base += 1
        log.info("Canción: %s llega en el compás %d", partes[indice]["nombre"], llega + 1)

    def lanzar_escena(self, destino, compases, indice=None):
        """Pasa a la configuración `destino` (una escena) en `compases` compases, desde el próximo."""
        destino = copy.deepcopy(destino)
        if not (self.corriendo and self.tick >= 0):
            self.conductor.reiniciar()
            self.aplicar_config(destino)
            return
        compas = self._compas_actual()
        tr = self.conductor.transicion
        origen = tr.config(compas) if tr is not None else self.base
        self.conductor.lanzar(origen, destino, compas + 1, compases, indice)
        self.base = destino
        self.config_en_cola = destino
        log.info("Escena %s: transición de %d compases", indice, compases)

    def _aplicar(self, config):
        config = copy.deepcopy(config)  # una copia propia: si quien llama la modifica, no se confunde
        self.config = config
        musica = config.get("musica", {})
        entrada = config.get("entrada", {})
        tonalidad = Tonalidad(musica.get("tonica", "F"), musica.get("escala", "frigio"))
        secuencias = [Secuencia(c) for c in config.get("secuencia", [])]
        for s in secuencias:
            if s.escala_color:
                s.tonalidad = Tonalidad(musica.get("tonica", "F"), s.escala_color)
        desplazamiento = musica.get("desplazamiento", 0.0)
        anterior = self.config_aplicada or {}
        mismo = lambda *secciones: all(anterior.get(k) == config.get(k) for k in secciones)  # noqa: E731
        # La tensión y anticipar solo los leen las secuencias, el bajo y el diálogo en cada paso:
        # moverlos (la energía lo hace) no rehace los pads ni el bajo.
        sin_tension = lambda c: {k: v for k, v in c.get("musica", {}).items() if k not in ("tension", "anticipar")}  # noqa: E731
        musica_igual = sin_tension(anterior) == sin_tension(config)
        self.musica = musica
        self.canal_disparo = int(entrada.get("canal_disparo", 2)) - 1
        if self.pads is not None and mismo("pads", "entrada") and musica_igual:
            pads = self.pads  # nada de los pads cambió: siguen exactamente igual
        else:
            pads = Pads(config.get("pads", {}), tonalidad, desplazamiento)
            pads.continuar_de(self.pads, self.enviar)  # en ligado, sin volver a atacar
        if self.bajo is not None and mismo("bajo", "entrada") and musica_igual:
            bajo = self.cola_bajo or self.bajo
        else:
            bajo = Bajo(config.get("bajo", {}), tonalidad)
        if self.dialogo is not None and mismo("dialogo", "llamada", "respuesta", "entrada") and musica_igual:
            dialogo = self.dialogo
        else:
            dialogo = self._crear_dialogo(config.get("dialogo", {}), config.get("llamada", {}), config.get("respuesta", {}))
            if self.dialogo is not None:
                dialogo.clip = self.dialogo.clip  # recuerda qué clip de diálogo sonaba
                dialogo.continuar_de(self.dialogo)  # sigue la conversación sin callarse ni perder lo mutado
                # Las notas que suenan terminan solas (cada una sabe a qué salida y canal va).
                dialogo.sonando, dialogo.pendientes = self.dialogo.sonando, self.dialogo.pendientes
        fx_cfg = config.get("fx", {})
        if self.fx is not None and mismo("fx", "entrada") and musica_igual:
            nuevo_fx = self.fx
        else:
            nuevo_fx = Fx(fx_cfg, tonalidad)
            nuevo_fx.continuar_de(self.fx, self.enviar)
        self.config_aplicada = config
        self._programas(config)
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
                if (vieja.salida, vieja.canal) == (s.salida, s.canal):
                    # Las notas que suenan terminan solas, sin cortarse.
                    s.sonando, s.pendientes, s.slide_previo = vieja.sonando, vieja.pendientes, vieja.slide_previo
                else:
                    self._callar(vieja)
                if (vieja.seed, vieja.estilo, vieja.largo, vieja.pedal) == (s.seed, s.estilo, s.largo, s.pedal):
                    # Mismo patrón de base: conserva lo que ya mutó. Antes, mover cualquier
                    # control de la app devolvía la secuencia a su patrón original.
                    s.patron = vieja.patron
                    s.ritmo_base = vieja.ritmo_base
                    s._director_patron = getattr(vieja, "_director_patron", None)  # un cambio del director viaja con su patrón
        pads.disparo = self._canal_de(config.get("pads", {}))
        bajo.disparo = self._canal_de(config.get("bajo", {}))
        nuevo_fx.disparo = self._canal_de(fx_cfg)
        self.fx = nuevo_fx
        canales = {s.disparo for s in secuencias} | {pads.disparo, dialogo.disparo, bajo.disparo, nuevo_fx.disparo, self.canal_disparo}
        anteriores = self.disparos
        self.disparos = {c: anteriores.get(c) or Disparo(c) for c in canales}
        for vieja in self.secuencias[len(secuencias):]:
            self._callar(vieja)
        self._soltar_filtros(secuencias)
        self.secuencias = secuencias
        self.pads = pads
        self.dialogo = dialogo
        if self.bajo is not None and bajo is not (self.cola_bajo or self.bajo):
            bajo.continuar_de(self.cola_bajo or self.bajo)
        if bajo is self.bajo:
            self.cola_bajo = None
        elif bajo is self.cola_bajo:
            pass
        elif self.bajo is not None and self.corriendo and self.tick >= 0:
            # Al vuelo: el bajo nuevo entra justo en el próximo compás, sin cortar la frase.
            self.cola_bajo = bajo
        else:
            if self.bajo is not None:
                bajo.heredar_notas(self.bajo, self.enviar)
            self.bajo, self.cola_bajo = bajo, None
        self.seguir_pads = bool(musica.get("seguir_pads", False))
        self.tension = float(musica.get("tension", 0.3))
        self.anticipar = bool(musica.get("anticipar", True))
        self.dialogo.tension, self.dialogo.anticipar = self.tension, self.anticipar
        self.pads.origen = self.origen_progresion
        self.director.aplicar(self)  # los cambios del período siguen en los motores recién armados

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
            "progresion": self.pads.texto_progresion() if self.pads else None,
            "dialogo": self.dialogo.fase if self.dialogo and self.dialogo.activo and self.corriendo else None,
            "filas": [{"clip": s.clip, "activa": s.activa,
                       "cola": (None if i not in self.cola else
                                ("detener" if self.cola[i] is None else self.cola[i][1]))}
                      for i, s in enumerate(self.secuencias)],
            "cambios_en_cola": self.config_en_cola is not None,
            "forma": self._forma_estado(),
            "cancion": self._cancion_estado(),
            "version_base": self.version_base,
            "motores": dict({"pads": bool(self.pads and self.pads.activo), "bajo": bool(self.bajo and self.bajo.activo),
                             "dialogo": bool(self.dialogo and self.dialogo.activo), "fx": bool(self.fx and self.fx.activo)},
                            **{f"sec{i}": s.activa for i, s in enumerate(self.secuencias)}),
            "bajo": {"estilo": self.bajo.estilo, "activo": self.bajo.activo,
                     "cola": self.cola_bajo.estilo if self.cola_bajo is not None else None} if self.bajo else None,
            "subida": self._subida_estado(),
            "fx_gesto": self.fx.ultimo if self.fx and self.corriendo else None,
            "fila_dialogo": {"clip": self.dialogo.clip, "activa": self.dialogo.activo,
                             "cola": (None if self.cola_dialogo is False else
                                      ("detener" if self.cola_dialogo is None else self.cola_dialogo[1]))},
        }

    def _subida_estado(self):
        """La subida de FX en curso (o pedida), para la app."""
        if self.subida_pedida is not None:
            return {"pedida": self.subida_pedida}
        if self.subida is None or not self.corriendo:
            return None
        paso = max(self.tick, 0) // TICKS_POR_PASO
        largo = (self.subida["hasta"] - self.subida["desde"]) // PASOS_POR_COMPAS
        return {"compas": (paso - self.subida["desde"]) // PASOS_POR_COMPAS + 1, "largo": largo,
                "origen": self.subida["origen"]}

    def _cancion_estado(self):
        """Dónde va la canción, para la app (None en modo libre)."""
        if not self.base or not forma.cancion_activa(self.base):
            return None
        partes = self.base["parte"]
        compas = self._compas_actual()
        ahora = self.conductor.parte(self.base, compas) if self.corriendo else None
        if ahora is None:
            return {"parte": None, "total": forma.total_cancion(partes),
                    "pedida": self.saltar_parte_a}
        siguiente = self.conductor.parte(self.base, compas + ahora["largo"] - ahora["dentro"])
        pos = sum(p["compases"] for p in partes[:ahora["i"]]) + ahora["dentro"]
        return {"parte": ahora["i"], "compas": ahora["dentro"] + 1, "largo": ahora["largo"],
                "vuelta": ahora["vuelta"] + 1, "posicion": pos + 1, "total": forma.total_cancion(partes),
                "siguiente": siguiente["i"] if siguiente else None, "pedida": self.saltar_parte_a}

    def _forma_estado(self):
        tr = self.conductor.transicion
        compas = self._compas_actual()
        base = (self.base or {}).get("forma", {})
        sec = self.conductor.seccion(self.base, compas) if self.base and self.corriendo else None
        duracion = base.get("duracion", "normal")
        piloto = None
        if base.get("piloto"):
            piloto = {"plan": [{"clave": k, "nombre": forma.SECCIONES_PILOTO[k]["nombre"],
                                "compases": forma.largo_seccion(k, duracion)} for k in forma.PLAN],
                      "seccion": sec[0] if sec else None, "compas": sec[2] + 1 if sec else None,
                      "largo": sec[3] if sec else None,
                      "siguiente": (forma.PLAN[self.conductor.piloto["i"] + 1] if self.conductor.piloto["i"] + 1 < len(forma.PLAN)
                                    else forma.PLAN[forma.VUELTA]) if sec else None}
        if piloto is not None and sec is not None:
            antes, ahora = forma._motores(self.base), forma._motores(forma.con_piloto(self.base, sec[0], sec[1]))
            piloto["calla"] = [k for k, v in antes.items() if v and not ahora.get(k)]
        return {
            "piloto": piloto,
            "energia": self.conductor.energia if self.conductor.energia is not None else base.get("energia", 0.5),
            "pedida": self.conductor.objetivo(self.base, compas) if self.base else 0.5,
            "escena": base.get("escena", -1),
            "director": self.director.descripcion(self) if self.corriendo else [],
            "transicion": None if tr is None or not self.corriendo else {
                "escena": tr.escena, "compases": tr.compases,
                "faltan": max(0, tr.fin - compas) if compas >= tr.inicio else tr.compases,
                "puente": self.puente is not None},
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

    def _programas(self, config):
        """Program Change: cada motor puede pedir un parche (1-128) a su sinte. Se manda
        solo cuando cambia (una escena o una parte nueva lo cambian en su uno) y otra vez
        en cada Start. Si dos motores van al mismo sinte y canal, manda el que suena."""
        fuentes = [(s, s.get("activa")) for s in config.get("secuencia", [])]
        fuentes += [(config.get("pads", {}), config.get("pads", {}).get("activo")),
                    (config.get("bajo", {}), config.get("bajo", {}).get("activo")),
                    (config.get("fx", {}), config.get("fx", {}).get("activo"))]
        hay_dialogo = config.get("dialogo", {}).get("activo")
        fuentes += [(config.get("llamada", {}), hay_dialogo and config["dialogo"].get("modo") == "motor"),
                    (config.get("respuesta", {}), hay_dialogo)]
        pedidos = {}
        for seccion, suena in sorted(fuentes, key=lambda f: not f[1]):  # primero los que suenan
            programa = int(seccion.get("programa", 0) or 0)
            if programa > 0 and seccion.get("salida"):
                pedidos.setdefault((seccion["salida"], int(seccion.get("canal", 1)) - 1), programa)
        for (salida, canal), programa in pedidos.items():
            if self.programas.get((salida, canal)) != programa:
                self.programas[(salida, canal)] = programa
                self.enviar(salida, "program_change", canal, programa - 1, 0)
                log.info("Program Change %d a %s canal %d", programa, salida, canal + 1)

    def start(self):
        log.info("Start")
        self.programas = {}  # en cada Start se vuelven a mandar (por si cambiaste el parche a mano)
        # Una transición a medias termina de una vez: arranca en la escena pedida.
        self.conductor.reiniciar()
        self.director.reiniciar()
        self.origen_progresion, self.puente = 0, None
        self.config_en_cola = None
        self._aplicar(self.conductor.efectiva(self.base, 0))
        self.apagar_todo()
        self._olvidar_notas()  # la Circuit vuelve a mandar sus notas desde el primer paso
        for s in self.secuencias:
            s.reiniciar()
        self.dialogo.reiniciar()
        if self.cola_bajo is not None:
            self.bajo, self.cola_bajo = self.cola_bajo, None
        self.bajo.reiniciar()
        self.subida, self.subida_pedida = None, None
        self.corriendo = True
        self.tick = -1

    def continuar(self):
        log.info("Continue")
        self.corriendo = True

    def stop(self):
        log.info("Stop")
        self.corriendo = False
        self.apagar_todo()
        self.subida = None
        self._soltar_filtros()
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
        self.fx.tick(self.tick, self.enviar)
        if self.tick % TICKS_POR_PASO == 0:
            self._paso(self.tick // TICKS_POR_PASO)
        elif self.tick % TICKS_POR_PASO == 2:
            # Los pads deciden dos pulsos después del paso: si la nota larga termina
            # justo en el cambio de compás, su note_off ya llegó y no suena un acorde suelto.
            d = self.disparos[self.pads.disparo]
            raiz = None if d.pendiente is None else (d.raiz if d.raiz is not None else d.pendiente)
            paso = self.tick // TICKS_POR_PASO
            if self.puente is not None and raiz is not None:
                self.pads.forzado = self._momento_puente(paso, raiz).raiz % 12
            else:
                self.pads.forzado = self.tension_pc  # acorde de tensión al final de una subida (o None)
            if not self._en_hueco(paso):
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
            self._compas_forma(paso // PASOS_POR_COMPAS)
            self._compas_subida(paso // PASOS_POR_COMPAS)
            if self.cola:
                self._aplicar_cola()  # los clips entran justo en el primer paso del compás
            if self.cola_dialogo is not False:
                self._aplicar_cola_dialogo()
            compas = paso // PASOS_POR_COMPAS
            for s in self.secuencias:
                s.evolucionar(compas)
            if self.cola_bajo is not None:
                self.cola_bajo.heredar_notas(self.bajo, self.enviar)  # la nota que suena termina sola
                self.bajo, self.cola_bajo = self.cola_bajo, None
                log.info("Entra el bajo nuevo (%s)", self.bajo.estilo)
            self.bajo.evolucionar(compas)
        for d in self.disparos.values():
            d.paso(paso, self.tick, self.cambio, self.nota_maxima)
        if self._en_hueco(paso):
            if paso == self.hueco_desde:
                self.apagar_todo()  # el último tiempo antes de la parte que viene: silencio
            return
        self._tocar_paso(paso)
        self._paso_dialogo(paso)
        self._paso_bajo(paso)
        self._paso_fx(paso)
        self._filtro_secuencias(paso)

    # --- FX: subidas, riser, filtros y glitches ---

    def pedir_subida(self, compases):
        """Subida de FX desde la app: empieza en el próximo compás y el drop cae al terminar.
        0 = cancelar (el drop cae en el próximo compás, sin caída)."""
        compases = int(compases)
        if compases not in (0, 4, 8, 16, 32):
            raise ValueError("La subida dura 4, 8, 16 o 32 compases")
        self.subida_pedida = compases

    def _subida_auto(self, compas):
        """La subida que piden la canción (parte con riser) o el piloto (build y break)."""
        parte = self.conductor.parte(self.base, compas)
        if parte is not None:
            if not self.base["parte"][parte["i"]].get("riser"):
                return None
            inicio = compas - parte["dentro"]
            fin = inicio + parte["largo"]
            desde = max(inicio, fin - 32)  # como mucho 32 compases de subida
            if compas < desde:
                return None
            return {"desde": desde * PASOS_POR_COMPAS, "hasta": fin * PASOS_POR_COMPAS, "origen": "cancion"}
        sec = self.conductor.seccion(self.base, compas)
        if sec is not None and sec[0] in ("build", "break"):
            desde = compas - sec[2]
            return {"desde": desde * PASOS_POR_COMPAS, "hasta": (desde + sec[3]) * PASOS_POR_COMPAS, "origen": "piloto"}
        return None

    def _compas_subida(self, compas):
        """Primer paso de cada compás: termina la subida (drop), empieza la pedida o la automática."""
        paso = compas * PASOS_POR_COMPAS
        if self.subida is not None and paso >= self.subida["hasta"]:
            self._drop(paso)
        pedida, self.subida_pedida = self.subida_pedida, None
        if pedida == 0:
            if self.subida is not None:
                self._drop(paso, caida=False)
        elif pedida:
            self.subida = {"desde": paso, "hasta": paso + pedida * PASOS_POR_COMPAS, "origen": "manual"}
            log.info("Subida de %d compases", pedida)
        if self.subida is None or self.subida["origen"] != "manual":
            auto = self._subida_auto(compas)
            if auto is not None and auto["hasta"] > paso and (self.subida is None or auto != self.subida):
                self.subida = auto
            elif auto is None and self.subida is not None and self.subida["origen"] != "manual":
                self._drop(paso, caida=False)  # la parte o la sección cambió antes de terminar

    def _drop(self, paso, caida=True):
        """Fin de la subida: el riser se corta, la caída parte y los filtros vuelven a su lugar."""
        self.subida = None
        raiz = self.disparos[self.fx.disparo].raiz
        momento = self._momento(paso, raiz) if raiz is not None else None
        self.fx.drop(self.tick, raiz, momento, self.enviar, caida)
        self._soltar_filtros()

    def _soltar_filtros(self, secuencias=None):
        """Los filtros intervenidos vuelven a su reposo. Con `secuencias`, solo los que ya no se intervienen."""
        siguen = set()
        if secuencias is not None and self.subida is not None:
            siguen = {(s.salida, s.canal, s.cc_filtro) for s in secuencias if s.fx}
        for clave, (valor, reposo) in list(self.cc_secuencias.items()):
            if clave in siguen:
                continue
            if valor != reposo:
                self.enviar(clave[0], "control_change", clave[1], clave[2], reposo)
            del self.cc_secuencias[clave]

    def _paso_fx(self, paso):
        if not self.fx.activo:
            return
        raiz = self.disparos[self.fx.disparo].raiz
        momento = self._momento(paso, raiz) if raiz is not None else None
        self.fx.paso(paso, self.tick, raiz, momento, self.subida, self.enviar)
        self.fx.tick(self.tick, self.enviar)  # lo que empieza en este paso sale ya, sin un pulso de atraso

    def _filtro_secuencias(self, paso):
        """En la subida, el filtro de cada secuencia con FX baja y se va abriendo hasta el drop."""
        if self.subida is None:
            return
        t = fx.avance(self.subida, paso)
        for s in self.secuencias:
            if not (s.fx and s.activa) or self.disparos[s.disparo].raiz is None:
                continue
            valor = fx.curva_filtro(t, s.filtro_reposo)
            clave = (s.salida, s.canal, s.cc_filtro)
            if self.cc_secuencias.get(clave, (None,))[0] != valor:
                self.cc_secuencias[clave] = (valor, s.filtro_reposo)
                self.enviar(s.salida, "control_change", s.canal, s.cc_filtro, valor)

    def _glitch(self, s, paso):
        """Intervención de FX en una secuencia: (paso del patrón que suena o None, redoble forzado).
        En la segunda mitad de la subida, redobles cada vez más seguidos. Fuera de la subida,
        a veces el último tiempo de la frase se traba en una nota (stutter) o queda en silencio."""
        if not s.fx:
            return None
        locura = max(self.fx.locura, 0.3)
        if self.subida is not None:
            t = fx.avance(self.subida, paso)
            if t >= 0.5 and random.Random(f"{s.seed}:fxr:{paso}").random() < locura * (t - 0.5) * 2.4:
                return None, True
            return None
        compas, lugar = divmod(paso, PASOS_POR_COMPAS)
        if compas % 4 != 3 or lugar < 12:
            return None
        if random.Random(f"{s.seed}:fxg:{self.fx.seed}:{compas}").random() >= self.fx.locura * 0.5:
            return None
        ventana = compas * PASOS_POR_COMPAS + 12
        for k in range(ventana - 1, ventana - 5, -1):
            p = s.patron[k % s.largo]
            if p["suena"] and generador.pasa_posicion(s.posicion, k):
                return k, True  # se traba en la última nota que sonó
        return ventana, False  # no había nota cerca: el tiempo queda en silencio (corte)

    def _en_hueco(self, paso):
        return self.hueco_desde is not None and self.hueco_desde <= paso < self.hueco_desde + 4

    def _efectos_parte(self, compas):
        """Canción: los efectos de subida de la parte que suena (todos opcionales).
        Roll de secuencias y corte de bajo en los últimos compases, acorde de tensión
        en el último compás (la parte siguiente resuelve en la i) y hueco en el último
        tiempo. Los pads que suben y el corte de bajo los aplica el conductor."""
        self.roll_desde, self.roll_compases, self.hueco_desde = None, 0, None
        self.tension_pc = self.tension_fin = None
        if self.resolver_en == compas:
            self.origen_progresion = compas  # después de la tensión, la progresión parte en su i
            self.resolver_en = None
        parte = self.conductor.parte(self.base, compas)
        if parte is None:
            return
        p = self.base["parte"][parte["i"]]
        falta = parte["largo"] - parte["dentro"]  # compases que quedan, contando este
        if p.get("roll"):
            n = forma.compases_corte(parte["largo"])
            if falta <= n:
                self.roll_compases = n
                self.roll_desde = (compas - (n - falta)) * PASOS_POR_COMPAS
        if falta == 1:
            fin = (compas + 1) * PASOS_POR_COMPAS
            if p.get("hueco"):
                self.hueco_desde = fin - 4
            if p.get("tension"):
                self.tension_pc = (self.tonalidad.tonica + raiz_tension(self.tonalidad.intervalos)) % 12
                self.tension_fin = fin
                self.resolver_en = compas + 1

    def _momento_tension(self, paso, raiz):
        """El acorde de tensión, que pide resolver en la i en el uno de la parte siguiente."""
        tension = armonia.de_nota_larga(_cerca(self.tension_pc, raiz), self.tonalidad)
        tonica = armonia.de_nota_larga(_cerca(self.tonalidad.tonica % 12, raiz), self.tonalidad)
        return armonia.Momento(tension.raiz, tension.clases, tonica.raiz, tonica.clases,
                               max(1, self.tension_fin - paso))

    def _compas_forma(self, compas):
        """Primer paso de cada compás: entran los cambios de la app, la energía da un paso
        y avanza la transición entre escenas."""
        self._avanzar_cancion(compas)
        self.conductor.avanzar(self.base, compas)
        self._efectos_parte(compas)
        tr = self.conductor.transicion
        self.puente = None
        if tr is not None:
            if tr.puente(compas):
                d = tr.destino
                self.puente = (Tonalidad(d["musica"]["tonica"], d["musica"]["escala"]), d["pads"].get("base", "nota"),
                               (tr.fin) * PASOS_POR_COMPAS)
            if compas == tr.fin and forma.cambia_armonia(tr.origen, tr.destino):
                self.origen_progresion = compas  # la progresión nueva parte en su i
        efectiva = self.conductor.efectiva(self.base, compas)
        if efectiva != self.config:
            if self.config is not None and forma.cambia_armonia(self.config, efectiva):
                self.origen_progresion = compas  # otra progresión (o tonalidad) parte en su i
            self._aplicar(efectiva)  # los cambios entran justo en el compás
            log.info("Entran los cambios (compás %d)", compas + 1)
        self.pads.origen = self.origen_progresion
        self.config_en_cola = None
        self.conductor.terminar_si_corresponde(compas)
        f = self.base.get("forma", {})
        self.director.compas(self, compas, float(f.get("variacion", 0.0)), max(1, int(f.get("periodo", 16))),
                             self.base.get("pads", {}).get("seed", ""))

    def _momento_puente(self, paso, raiz):
        nueva, base, cambio = self.puente
        raiz_nueva = _cerca(nueva.tonica, raiz) if base == "tonica" else raiz
        return armonia.puente(self.tonalidad, nueva, raiz_nueva, max(1, cambio - paso))

    def _momento(self, paso, raiz):
        """Momento armónico en `paso`: el de los pads, o el acorde sobre la nota larga `raiz`."""
        if self.puente is not None:
            r = self.disparos[self.pads.disparo].raiz if self.pads.activo else None
            r = r if r is not None else raiz
            if r is not None:
                return self._momento_puente(paso, r)
        if self.tension_pc is not None and raiz is not None:
            return self._momento_tension(paso, raiz)
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
            fuente = paso if self.roll_desde is None else forma.roll(paso, self.roll_desde, self.roll_compases)
            forzar = False
            glitch = self._glitch(s, paso)
            if glitch is not None:
                fuente = fuente if glitch[0] is None else glitch[0]
                forzar = glitch[1]
            i = fuente % s.largo
            p = s.patron[i]
            x = s.extra[p.get("fuente", i)]
            if (raiz is None or not s.activa or not generador.pasa_posicion(s.posicion, fuente)
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
            tonalidad = s.tonalidad or self.tonalidad
            nota = tonalidad.nota(raiz, p["grado"] + s.relacion, self.adaptacion) + 12 * octava
            fuerte = generador.es_fuerte(s.posicion, paso)
            if momento is not None:
                azar_arm = random.Random(f"{s.seed}:armonia:{i}").random()
                ultima = momento.cambia_pronto and self._ultima_antes_del_cambio(s, paso, momento.falta)
                nota = armonia.ajustar(nota, momento, self.tonalidad, fuerte, ultima,
                                       self.tension, self.anticipar, azar_arm)
            if s.semitono and not fuerte and random.Random(f"{s.seed}:semitono:{i}").random() < s.semitono:
                # El ♭2: medio tono sobre la raíz que suena, en los pasos débiles (el fuerte queda firme).
                nota = _cerca((raiz + 1) % 12, nota)
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
            elif not slide and (forzar or x["repeticion"] < s.repeticion):
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

    def _callar(self, s):
        for nota in list(s.sonando):
            self.enviar(s.salida, "note_off", s.canal, nota, 0)
        s.sonando.clear()
        s.pendientes = []

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

    def apagar_todo(self, pads=True):
        for s in self.secuencias:
            for nota in list(s.sonando):
                self.enviar(s.salida, "note_off", s.canal, nota, 0)
            s.sonando.clear()
            s.pendientes = []
            s.slide_previo = False
        if pads and self.pads is not None:
            self.pads.apagar(self.enviar)
        if self.dialogo is not None:
            self.dialogo.apagar(self.enviar)
        if self.bajo is not None:
            self.bajo.apagar(self.enviar)
        if self.fx is not None:
            self.fx.apagar(self.enviar)
