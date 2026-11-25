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

from . import armonia, copia, forma, fx, generador, raga
from .azar import azar as azar_fijo
from .bajo import Bajo
from .dialogo import Dialogo, Voz
from .director import Director
from .disparo import Disparo
from .escalas import Tonalidad, nombre_midi
from .fx import Fx
from .motor_forma import FormaMotor
from .pads import Pads, _cerca
from .secuencia import PASOS_POR_COMPAS, TICKS_POR_PASO, Secuencia, celda_molde
from .obertura import Obertura
from .texturas import Texturas
from .tocado import Tocado

MITAD_COMPAS = 48   # pulso en que se pide el loop de la MC-101 (ver Motor._looper)

log = logging.getLogger("goa")


GRADOS_PAR = (6, 4, 2, 7, 1)  # ♭7, 5.ª, ♭3, octava, ♭2 (grados de escala desde la raíz)


class Motor(FormaMotor):
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
        self.clip_motor = {"bajo": None, "pads": None}  # qué clip se tocó en el bajo y en los pads (como `Secuencia.clip`)
        self.musica = {}
        self.base = None            # la configuración que pidió la app (sin energía ni transición)
        self.conductor = forma.Conductor()
        self.director = Director()
        self.origen_progresion = 0  # compás donde parte la progresión de los pads
        self.puente = None          # (tonalidad nueva, base de los pads, paso del cambio) durante un acorde puente
        self.version_base = 0       # sube cuando la canción cambia de parte (la app se recarga)
        self.programas = {}         # (salida, canal) -> último Program Change mandado
        self.looper_enviado = None  # (salida, canal, clip o -parar) del último Program Change del looper
        self.looper_pendiente = None  # (clave, programa o None, volumen o None, compás en que entra)
        self.looper_mudo = None       # (salida, canal) si el motor bajó el volumen de la pista
        # Efectos de subida de la parte de la canción que suena (ver _efectos_parte)
        self.roll_desde, self.roll_compases = None, 0
        self.hueco_desde = None
        self.tension_pc, self.tension_fin, self.resolver_en = None, None, None
        self.saltar_parte_a = None  # parte pedida desde la app (entra en el próximo compás)
        self.fx = None
        self.texturas = None
        self.obertura = None
        self.tocado = Tocado()      # lo que tocas con el teclado de la MicroFreak (goa/tocado.py)
        # Subida de FX: {"desde": paso, "hasta": paso del drop, "origen": manual, cancion o piloto}
        self.subida = None
        self.subida_pedida = None   # compases de la subida pedida desde la app (0 = cancelar)
        self.subida_final = None    # subida pedida para los últimos N compases de la parte
        self.relanzar_parte = False  # «quedarse» cuando la parte siguiente ya entraba
        self.scatter_nota = None     # (salida, canal, nota) del pad de Scatter apretado
        self.circuit_envios = {}     # cc -> {"valor", "obj", "desde", "p0", "largo"}: envíos de la Circuit
        self.circuit_filtro = None   # (salida, canal, valor) del filtro maestro de la Circuit si se movió
        self.cc_secuencias = {}     # (salida, canal, cc) -> (valor mandado, reposo): filtros intervenidos
        self.aplicar_config(config)

    def aplicar_config(self, config):
        """Cambia la configuración en vivo, sin detener el reloj ni cortar nada.

        Con el motor andando, las secuencias cambian al tiempo (una variante o un estilo
        nuevo se escucha de inmediato). Todo lo demás (pads, bajo, diálogo, tónica,
        escala, armonía…) entra en el primer paso del próximo compás, y en ese cambio
        las notas que suenan terminan solas y los pads pasan en ligado."""
        config = copia.config(config)
        config.setdefault("forma", {"energia": 0.5})
        self.base = config
        tr = self.conductor.transicion
        if tr is not None:
            # Lo que cambias durante una transición va al destino; la transición sigue.
            tr.destino = copia.config(config)
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

    def reiniciar_secuencia(self, fila):
        """La secuencia `fila` vuelve a su patrón de base: deshace lo que mutó (notas, ritmo,
        molde) aunque su configuración no haya cambiado."""
        if 0 <= fila < len(self.secuencias):
            s = self.secuencias[fila]
            s.reiniciar()
            s.molde_vivo = s.molde
            s._director_patron = None

    def reiniciar_motor(self, motor, fila=0):
        """Después de «Restaurar ajustes de fábrica»: el motor vuelve a su patrón de base
        aunque su firma no haya cambiado (si no, seguiría con lo que ya había mutado)."""
        if motor == "secuencia":
            self.reiniciar_secuencia(fila)
        elif motor == "bajo":
            self.reiniciar_bajo()
        elif motor == "dialogo":
            self.reiniciar_dialogo()

    def reiniciar_dialogo(self):
        """Las frases de la llamada y la respuesta vuelven a las de su seed (sin lo mutado),
        sin cortar la conversación."""
        d = self.dialogo
        if d is None:
            return
        for voz, cfg in zip((d.llamada, d.respuesta), d.cfg_voces):
            limpia = Voz(cfg, voz.papel, d.seed)
            voz.orden, voz.rng, voz.molde_vivo = limpia.orden, limpia.rng, voz.molde

    def reiniciar_bajo(self):
        """El bajo vuelve a su patrón de base (deshace lo que mutó). Si hay un bajo nuevo
        esperando el próximo compás, es ese el que vuelve a la base."""
        bajo = self.cola_bajo or self.bajo
        if bajo is not None:
            bajo.reiniciar()

    # --- Lo que ya mutó, para poder deshacer «Restaurar ajustes de fábrica» ---

    def estado_secuencia(self, fila):
        """Una foto del patrón vivo de la secuencia `fila` (con lo que ya mutó)."""
        if not 0 <= fila < len(self.secuencias):
            return None
        s = self.secuencias[fila]
        return copy.deepcopy({"firma": s.firma(), "patron": s.patron, "ritmo_base": s.ritmo_base,
                              "molde_vivo": s.molde_vivo, "director": getattr(s, "_director_patron", None)})

    def volver_estado_secuencia(self, fila, estado):
        """Devuelve la foto de estado_secuencia, si el patrón de base es el mismo."""
        if not estado or not 0 <= fila < len(self.secuencias):
            return
        s = self.secuencias[fila]
        if s.firma() != estado["firma"]:
            return
        foto = copy.deepcopy(estado)
        s.patron, s.ritmo_base, s._director_patron = foto["patron"], foto["ritmo_base"], foto["director"]
        if len(foto["molde_vivo"]) == len(s.molde_vivo):
            s.molde_vivo = foto["molde_vivo"]

    def estado_bajo(self):
        bajo = self.cola_bajo or self.bajo
        if bajo is None:
            return None
        return {"base": dict(bajo.base), "seed": bajo.seed, "patron": dict(bajo.patron), "mutado_hasta": bajo.mutado_hasta}

    def volver_estado_bajo(self, estado):
        bajo = self.cola_bajo or self.bajo
        if not estado or bajo is None or bajo.base != estado["base"] or bajo.seed != estado["seed"]:
            return
        bajo.patron = dict(estado["patron"])
        bajo.mutado_hasta = estado["mutado_hasta"]

    def _aplicar(self, config):
        config = copia.config(config)  # una copia propia: si quien llama la modifica, no se confunde
        self.config = config
        musica = config.get("musica", {})
        entrada = config.get("entrada", {})
        tonalidad = Tonalidad(musica.get("tonica", "F"), musica.get("escala", "frigio"))
        secuencias = [Secuencia(c) for c in config.get("secuencia", [])]
        for s in secuencias:
            color = f"raga:{s.raga}" if s.raga else s.escala_color  # la raga manda sobre la escala de color
            if color:
                s.tonalidad = Tonalidad(musica.get("tonica", "F"), color)
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
        tx_cfg = config.get("texturas", {})
        if self.texturas is not None and mismo("texturas", "entrada") and musica_igual:
            nuevas_texturas = self.texturas
        else:
            nuevas_texturas = Texturas(tx_cfg, tonalidad)
            nuevas_texturas.continuar_de(self.texturas, self.enviar)
        ob_cfg = config.get("obertura", {})
        if self.obertura is not None and mismo("obertura") and musica_igual:
            nueva_obertura = self.obertura
        else:
            nueva_obertura = Obertura(ob_cfg, tonalidad)
            nueva_obertura.continuar_de(self.obertura, self.enviar)
        self.obertura = nueva_obertura
        self.config_aplicada = config
        self._programas(config)
        self._looper(config)
        self.tonalidad = tonalidad
        tocado = config.get("tocado", {})
        self.tocado.configurar(tocado, tonalidad, self.enviar, self.tick,
                               guiada=self._modo_armonia(tocado.get("armonia", "general")) == "guiada")
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
                    for nuevo, viejo in zip(s.lfos, vieja.lfos):
                        if nuevo.cc == viejo.cc:
                            nuevo.ultimo = viejo.ultimo
                if (vieja.salida, vieja.canal) == (s.salida, s.canal):
                    # Las notas que suenan terminan solas, sin cortarse.
                    s.sonando, s.pendientes, s.slide_previo = vieja.sonando, vieja.pendientes, vieja.slide_previo
                    s.bends, s.bend_movido = vieja.bends, vieja.bend_movido
                    if not s.raga:
                        self._soltar_bend(s)  # sacaron la raga: el pitch bend vuelve al centro
                else:
                    self._callar(vieja)
                if vieja.firma() == s.firma():
                    # Mismo patrón de base: conserva lo que ya mutó. Antes, mover cualquier
                    # control de la app devolvía la secuencia a su patrón original.
                    s.patron = vieja.patron
                    s.ritmo_base = vieja.ritmo_base
                if vieja.molde == s.molde and s.molde_muta > 0:
                    s.molde_vivo = vieja.molde_vivo  # el molde mutado sigue su camino
                    s._director_patron = getattr(vieja, "_director_patron", None)  # un cambio del director viaja con su patrón
        pads.disparo = self._canal_de(config.get("pads", {}))
        bajo.disparo = self._canal_de(config.get("bajo", {}))
        nuevo_fx.disparo = self._canal_de(fx_cfg)
        self.fx = nuevo_fx
        nuevas_texturas.disparo = self._canal_de(tx_cfg)
        self.texturas = nuevas_texturas
        canales = {s.disparo for s in secuencias} | {pads.disparo, dialogo.disparo, bajo.disparo, nuevo_fx.disparo,
                                                     nuevas_texturas.disparo, self.canal_disparo}
        anteriores = self.disparos
        self.disparos = {c: anteriores.get(c) or Disparo(c) for c in canales}
        for vieja in self.secuencias[len(secuencias):]:
            self._callar(vieja)
        self._soltar_filtros(secuencias)
        self.secuencias = secuencias
        if self.pads is not None:
            viejos = {l.prefijo: l.ultimo for l in self.pads.lfos}
            for l in pads.lfos:
                l.ultimo = viejos.get(l.prefijo)
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
                             "dialogo": bool(self.dialogo and self.dialogo.activo), "fx": bool(self.fx and self.fx.activo),
                             "texturas": bool(self.texturas and self.texturas.activo),
                             "obertura": bool(self.obertura and self.obertura.activo)},
                            **{f"sec{i}": s.activa for i, s in enumerate(self.secuencias)}),
            "bajo": {"estilo": self.bajo.estilo, "activo": self.bajo.activo,
                     "cola": self.cola_bajo.estilo if self.cola_bajo is not None else None} if self.bajo else None,
            "subida": self._subida_estado(),
            "fx_gesto": self.fx.ultimo if self.fx and self.corriendo else None,
            "clips_motor": dict(self.clip_motor),
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

    def _programas(self, config):
        """Program Change: cada motor puede pedir un parche (1-128) a su sinte. Se manda
        solo cuando cambia (una escena o una parte nueva lo cambian en su uno) y otra vez
        en cada Start. Solo los motores que suenan: uno apagado no le cambia el parche a
        su sinte (puede estar tocándolo otro, o tú a mano). Si dos van al mismo sinte y
        canal, manda el que suena; al prenderse un motor, manda el suyo."""
        fuentes = [(s, s.get("activa")) for s in config.get("secuencia", [])]
        fuentes += [(config.get("pads", {}), config.get("pads", {}).get("activo")),
                    (config.get("bajo", {}), config.get("bajo", {}).get("activo")),
                    # En las baterías de la Circuit el FX no pide parche (el canal 10 no lo usa).
                    (config.get("fx", {}), config.get("fx", {}).get("activo") and not config.get("fx", {}).get("kit_circuit")),
                    (config.get("tocado", {}), config.get("tocado", {}).get("activo"))]
        hay_dialogo = config.get("dialogo", {}).get("activo")
        fuentes += [(config.get("llamada", {}), hay_dialogo and config["dialogo"].get("modo") == "motor"),
                    (config.get("respuesta", {}), hay_dialogo)]
        pedidos = {}
        for seccion, suena in fuentes:
            if not suena:
                continue
            programa = int(seccion.get("programa", 0) or 0)
            if programa > 0 and seccion.get("salida"):
                pedidos.setdefault((seccion["salida"], int(seccion.get("canal", 1)) - 1), programa)
        for clave in [c for c in self.programas if c not in pedidos]:
            del self.programas[clave]   # nadie lo pide: al prenderse otra vez, lo vuelve a mandar
        for (salida, canal), programa in pedidos.items():
            if self.programas.get((salida, canal)) != programa:
                self.programas[(salida, canal)] = programa
                self.enviar(salida, "program_change", canal, programa - 1, 0)
                log.info("Program Change %d a %s canal %d", programa, salida, canal + 1)

    def _looper(self, config=None, ya=False):
        """Looper de la MC-101: Program Change 0-15 = slot 1-16 en el canal de la pista.
        Se manda solo cuando cambia, y en la mitad del compás antes de donde debe entrar:
        la MC-101 lo cambia en el uno siguiente (con Master Step Length en 16 pasos). En
        la mitad, y no justo en el uno, porque un pelo de atraso hacía que a veces lo
        tomara un compás antes y el loop entraba descuadrado.
        Callar (el interruptor apagado, o «Callado»): con un slot vacío elegido, lo lanza;
        si no, baja el volumen de la pista (CC 7) justo en el uno, y lo devuelve a `nivel`
        en el uno en que vuelve a sonar. Solo calla lo que el motor hizo sonar.
        Dónde entra: con una escena o parte en camino, en el compás en que llega; si no,
        en el próximo múltiplo de `cada` compases desde el Start (loops de 2, 4 u 8
        compases entran siempre con la frase)."""
        if not self.corriendo:
            return  # detenido no pide nada: al Start pide el de la escena que suena
        tr = self.conductor.transicion
        lp, objetivo = None, None
        compas = self._compas_actual()
        if tr is not None and self.tick >= 0 and compas >= tr.fin - 1:
            config, objetivo = tr.destino, tr.fin
        elif self.tick >= 0:
            lp = self._looper_parte_siguiente(compas)
            if lp is not None:
                objetivo = compas + 1
        if lp is None:
            lp = (config if config is not None else self.config or {}).get("looper") or {}
        if not lp.get("salida"):
            self.looper_pendiente = None
            return
        if objetivo is not None:
            # Una escena o parte que llega a mitad de frase: el loop espera el uno de la
            # frase (un loop de 4 compases que parte en el compás 2 queda corrido siempre).
            cada = max(1, int(lp.get("cada", 1)))
            objetivo = -(-objetivo // cada) * cada
        canal = int(lp.get("canal", 4)) - 1
        clip, parar = int(lp.get("clip", 0)), int(lp.get("parar", 0))
        pc = nivel = None
        if lp.get("activo") and clip > 0:
            clave = (lp["salida"], canal, clip)
            if clave != self.looper_enviado:
                pc = clip - 1
            if self.looper_mudo == (lp["salida"], canal):
                nivel = int(lp.get("nivel", 100))   # vuelve a sonar
        else:
            sono = self.looper_enviado is not None and self.looper_enviado[2] > 0
            if not sono and not (lp.get("activo") and parar > 0 and self.looper_enviado is None):
                self.looper_pendiente = None   # nada que callar (o ya callado)
                return
            if parar > 0:
                clave = (lp["salida"], canal, -parar)
                pc = parar - 1   # callar = lanzar el slot vacío
            elif self.looper_mudo != (lp["salida"], canal):
                clave, nivel = self.looper_enviado, 0   # callar = volumen de la pista a 0
            else:
                clave = self.looper_enviado
        if pc is None and nivel is None:
            self.looper_pendiente = None   # (volviste a lo que ya suena)
            return
        if objetivo is None:
            cada = max(1, int(lp.get("cada", 1)))
            objetivo = (compas // cada + 1) * cada
        nuevo = (clave, pc, nivel, objetivo)
        pendiente = self.looper_pendiente
        if pendiente is not None and pendiente[:3] == nuevo[:3] and pendiente[3] <= objetivo:
            return   # ya pedido para antes
        self.looper_pendiente = nuevo
        self._looper_pulso(forzar=ya or self.tick < 0)

    def _looper_pulso(self, forzar=False):
        """Manda lo pedido cuando toca (llamado en cada pulso si hay algo pendiente): el
        Program Change en la mitad del compás anterior, el volumen justo en el uno."""
        clave, pc, nivel, objetivo = self.looper_pendiente
        compas, dentro = divmod(max(self.tick, 0), TICKS_POR_PASO * PASOS_POR_COMPAS)
        if pc is not None and (forzar or compas >= objetivo or (compas == objetivo - 1 and dentro >= MITAD_COMPAS)):
            self.looper_enviado = clave
            self.enviar(clave[0], "program_change", clave[1], pc, 0)
            log.info("Looper: %s (canal %d)", f"loop {pc + 1}" if clave[2] > 0 else "callado", clave[1] + 1)
            pc = None
        if nivel is not None and (forzar or compas >= objetivo):
            self.enviar(clave[0], "control_change", clave[1], 7, nivel)
            self.looper_mudo = (clave[0], clave[1]) if nivel == 0 else None
            log.info("Looper: %s (canal %d)", "callado (volumen 0)" if nivel == 0 else f"vuelve (volumen {nivel})", clave[1] + 1)
            nivel = None
        self.looper_pendiente = None if pc is None and nivel is None else (clave, pc, nivel, objetivo)

    def start(self):
        log.info("Start")
        self.programas = {}  # en cada Start se vuelven a mandar (por si cambiaste el parche a mano)
        self.looper_enviado = None
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
        self.obertura.reiniciar()
        self.subida, self.subida_pedida, self.subida_final = None, None, None
        self.circuit_envios = {}   # en cada Start los envíos se vuelven a mandar (por si los moviste a mano)
        self.corriendo = True
        self.looper_pendiente = None
        self._looper(self.config, ya=True)   # antes del primer pulso: la MC-101 arranca con él
        self.tick = -1
        self.tocado.reiniciar(0)

    def continuar(self):
        log.info("Continue")
        self.corriendo = True

    def stop(self):
        log.info("Stop")
        self.corriendo = False
        self._soltar_scatter()
        self._soltar_filtro_circuit()
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
        if self.looper_pendiente is not None:
            self._looper_pulso()
        self._apagar_vencidas()
        self.dialogo.tick(self.tick, self.enviar)
        if self.tick % 3 == 0:
            self._lfo_secuencias()
        self.pads.tick(self.tick, self.enviar)
        self.bajo.tick(self.tick, self.enviar)
        self.fx.tick(self.tick, self.enviar)
        self.texturas.tick(self.tick, self.enviar)
        self.obertura.tick(self.tick, self.enviar)
        self._espacio_bombo()
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
            self._momentos = {}
            if not self._en_hueco(paso):
                self.pads.actualizar(self.tick // TICKS_POR_PASO, raiz, self.tick, self.enviar)
        self.tocado.pulso(self.tick, self._momento_tocado, self.enviar)

    def _espacio_bombo(self):
        """Espacio para el bombo (los temas de Dekel): poco antes de cada tiempo se cortan
        las notas del bajo y de las secuencias que seguirían sonando encima del bombo, como
        un sidechain hecho con las notas. Lo que entra en el tiempo o después no se toca;
        el bajo sub (un drone) tampoco."""
        espacio = float((self.base or {}).get("forma", {}).get("espacio_bombo", 0.0))
        if espacio <= 0:
            return
        antes = max(1, round(espacio * TICKS_POR_PASO))
        tiempo = 4 * TICKS_POR_PASO
        if (self.tick + antes) % tiempo:
            return
        b = self.bajo
        if b.activo and b.estilo != "sub":
            for nota in [n for n, fin in b.sonando.items() if fin > self.tick]:
                self.enviar(b.salida, "note_off", b.canal, nota, 0)
                del b.sonando[nota]
            if b.bends:
                b.bends = []  # la caída o el arco de la nota cortada no siguen
                if b.bend_movido:
                    self.enviar(b.salida, "pitchwheel", b.canal, 0, 0)
                    b.bend_movido = False
        for s in self.secuencias:
            for nota in [n for n, fin in s.sonando.items() if fin > self.tick]:
                self.enviar(s.salida, "note_off", s.canal, nota, 0)
                del s.sonando[nota]

    # --- Tocado: el teclado de la MicroFreak ---

    def _momento_tocado(self, paso):
        """El acorde que suena para lo que tocas: el de los pads, o el de la nota larga."""
        raiz = self.disparos[self.pads.disparo].raiz if self.pads is not None else None
        if raiz is None and self.canal_disparo in self.disparos:
            raiz = self.disparos[self.canal_disparo].raiz
        return self._momento(paso, raiz)

    def tocado_on(self, tecla, velocidad):
        tick = max(self.tick, 0)
        self.tocado.tecla_on(tecla, velocidad, tick, self._momento_tocado(tick // TICKS_POR_PASO), self.enviar,
                             self.corriendo)

    def tocado_off(self, tecla):
        self.tocado.tecla_off(tecla, max(self.tick, 0), self.enviar)

    def _lfo_secuencias(self):
        """Los LFO de filtro de cada secuencia (hasta dos): un CC cada media semicorchea,
        solo cuando cambia. Mientras el motor de FX interviene ese filtro, espera."""
        for s in self.secuencias:
            if not s.activa:
                continue
            for lfo in s.lfos:
                if not lfo.activo or (s.salida, s.canal, lfo.cc) in self.cc_secuencias:
                    continue
                valor = lfo.valor(self.tick)
                if valor != lfo.ultimo:
                    self.enviar(s.salida, "control_change", s.canal, lfo.cc, valor)
                    lfo.ultimo = valor
        p = self.pads
        if p is not None and p.activo and p.suenan:
            for lfo in p.lfos:
                if lfo.activo:
                    valor = lfo.valor(self.tick)
                    if valor != lfo.ultimo:
                        self.enviar(p.salida, "control_change", p.canal, lfo.cc, valor)
                        lfo.ultimo = valor
        t = self.tocado
        if t.activo and t.salida:
            for lfo in t.lfos:
                if not lfo.activo or (t.salida, t.canal, lfo.cc) in self.cc_secuencias:
                    continue
                valor = lfo.valor(self.tick)
                if valor != lfo.ultimo:
                    self.enviar(t.salida, "control_change", t.canal, lfo.cc, valor)
                    lfo.ultimo = valor

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
        self._momentos = {}
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
        self._paso_scatter(paso)
        self._paso_circuit(paso)
        if self._en_hueco(paso):
            if paso == self.hueco_desde:
                self.apagar_todo()  # el último tiempo antes de la parte que viene: silencio
            return
        self._tocar_paso(paso)
        self._paso_dialogo(paso)
        self._paso_bajo(paso)
        self._paso_fx(paso)
        self._paso_texturas(paso)
        ob = self.obertura
        if ob.activo and paso % PASOS_POR_COMPAS == 0:
            parte = self.conductor.parte(self.base, paso // PASOS_POR_COMPAS) if ob.largo_parte else None
            if parte is not None and ob.enlazar:
                parte = dict(parte, sigue=self._obertura_sigue(paso // PASOS_POR_COMPAS, parte))
            ob.paso(paso, self.tick, self.enviar,
                    next((s.patron for s in self.secuencias if s.activa), self.secuencias[0].patron if self.secuencias else None),
                    parte)
        self._filtro_secuencias(paso)

    # --- FX: subidas, riser, filtros y glitches ---

    def _momento(self, paso, raiz):
        """Momento armónico en `paso`: el de los pads, o el acorde sobre la nota larga `raiz`.
        Se calcula una vez por paso y raíz (lo piden el bajo, cada secuencia y el diálogo)."""
        cache = self.__dict__.setdefault("_momentos", {})   # se vacía en cada paso y al moverse los pads
        clave = (paso, raiz)
        if clave not in cache:
            cache[clave] = self._calcular_momento(paso, raiz)
        return cache[clave]

    def _calcular_momento(self, paso, raiz):
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
        self._tocar_paso_secuencias(paso, solo_canal)
        for s in self.secuencias:
            if solo_canal is None or s.disparo == solo_canal:
                _anotar_huella(s, paso)

    def _tocar_paso_secuencias(self, paso, solo_canal=None):
        tocadas = []   # las secuencias ya tocadas en este paso (la primera activa es la referencia)
        for s in self.secuencias:
            if solo_canal is not None and s.disparo != solo_canal:
                continue
            referencia = next((r for r in tocadas if r.activa), None)
            tocadas.append(s)
            s.toco_previo = s.toco if s.toco is not None and s.toco[0] == paso - 1 else None
            s.toco = None
            if s.separar and referencia is not None and referencia.toco is not None:
                # La referencia atacó una nota que choca con una larga nuestra: la cortamos.
                otra = referencia.toco[1]
                for n in [n for n, fin in s.sonando.items() if fin > self.tick]:
                    if choca(n, otra):
                        self.enviar(s.salida, "note_off", s.canal, n, 0)
                        del s.sonando[n]
            raiz = self.disparos[s.disparo].raiz
            fuente = paso if self.roll_desde is None else forma.roll(paso, self.roll_desde, self.roll_compases)
            forzar = False
            glitch = self._glitch(s, paso)
            if glitch is not None:
                fuente = fuente if glitch[0] is None else glitch[0]
                forzar = glitch[1]
            i = _indice(s, fuente)
            p = s.patron[i]
            x = s.extra[p.get("fuente", i)]
            if s.respuesta_par and (paso // 16) % 2 == 1 and paso % 16 >= 12 and p["suena"]:
                # Respuesta en el compás par: el último tiempo del 2.º compás de cada par toma
                # otras notas (♭7, 5.ª, ♭3, octava, ♭2), distintas cada par y repetibles.
                vuelta = (paso // 32) % 4
                if azar_fijo(f"{s.seed}:par:{vuelta}:{paso % 16}") < s.respuesta_par:
                    grados = GRADOS_PAR
                    p = dict(p, grado=grados[int(azar_fijo(f"{s.seed}:par-g:{vuelta}:{paso % 16}") * len(grados))])
            # Filtro (molde, opcional): la seed arma las notas y el filtro decide cuáles pasan.
            celda = celda_molde(s.molde_vivo, s.molde_prob, s.seed, paso, s.filtro)
            if (raiz is None or not s.activa or celda == "-" or not generador.pasa_posicion(s.posicion, fuente)
                    or not p["suena"] or x["densidad"] >= s.densidad):
                s.slide_previo = False
                continue
            if self._respira(s, paso, i):
                continue  # deslices: la nota anterior se sostiene sobre esta raíz
            if s.complementar > 0 and referencia is not None and referencia.toco is not None:
                # Complementar (opcional): calla donde la voz de referencia ataca. Primero
                # cede en sus acentos (hasta 50 %) y después en el resto (100 % = hocket).
                azar_c = azar_fijo(f"{s.seed}:complementar:{i}")
                umbral = min(1.0, 2 * s.complementar) if referencia.toco[2] else max(0.0, 2 * s.complementar - 1)
                if azar_c < umbral:
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
            ornado = self._en_rejilla(s, paso, p)
            if ornado is not None:
                # Ornamento en la rejilla: este paso de pedal toma la nota del adorno (kan,
                # trino del gamak o aproximación de los deslices). Mismo ritmo, nunca fusas.
                p = dict(p, grado=ornado[0], octava=ornado[1])
            octava = s.octava + p.get("octava", 0) + (x["direccion"] if x["salto"] < s.saltos else 0)
            tonalidad = s.tonalidad or self.tonalidad
            nota = tonalidad.nota(raiz, p["grado"] + s.relacion, self.adaptacion) + 12 * octava
            fuerte = generador.es_fuerte(s.posicion, paso)
            if momento is not None:
                azar_arm = azar_fijo(f"{s.seed}:armonia:{i}")
                ultima = momento.cambia_pronto and self._ultima_antes_del_cambio(s, paso, momento.falta)
                nota = armonia.ajustar(nota, momento, self.tonalidad, fuerte, ultima,
                                       self.tension, self.anticipar, azar_arm)
            if s.semitono and not fuerte and azar_fijo(f"{s.seed}:semitono:{i}") < s.semitono:
                # El ♭2: medio tono sobre la raíz que suena, en los pasos débiles (el fuerte queda firme).
                nota = _cerca((raiz + 1) % 12, nota)
            if p.get("semi"):
                # Figura piano con psy: la ♭2 frigia del acorde que suena (sobre su raíz).
                nota = _cerca((raiz + 1) % 12, nota)
            while nota > s.techo and nota - 12 >= 0:
                nota -= 12  # techo: lo que pasa de la nota más alta baja de octava (misma nota, más grave)
            nota = max(0, min(127, nota))
            if s.separar and referencia is not None:
                # Separar (opcional): si choca con lo que suena en la referencia (segunda,
                # séptima, tritono o la misma nota), va a la nota consonante de la escala más cercana.
                nota = _separar(tonalidad, nota, self._suenan(referencia), s.techo,
                                momento.clases if momento is not None else None)
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
            if "vel_mult" in p:
                velocidad = round(velocidad * p["vel_mult"])   # figura piano: ecos y melancolía más suaves
            velocidad = max(1, min(127, velocidad))
            # Para las voces que la complementan o se separan: el ataque y si es fuerte
            # (acento o tiempo del compás).
            s.toco = (paso, nota, acento or paso % 4 == 0, _desfase(s, paso, p))
            gate = s.gate * p.get("gate_mult", 1.0)
            gate = max(0.05, min(1.0, gate * (1 + s.gate_random * azar.uniform(-1, 1))))
            duracion = max(1, round(TICKS_POR_PASO * gate))
            if p.get("sostener") and not slide:
                # Nota sostenida del patrón (pulsos del psytrance): dura varios pasos.
                duracion = max(1, round(p["sostener"] * TICKS_POR_PASO) - 1)
            elif slide:
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
            ornamento = None
            if s.raga and s.ornamentos > 0 and not slide:
                ornamento = self._ornamento_raga(s, nota, i, duracion)
            if ornamento is None and s.deslices > 0 and not slide:
                # Deslices (opcional): notas que respiran y notas llenas que se tocan con la
                # siguiente sin pisarla. Cada paso tiene su número fijo: se suman de a poco.
                siguiente = _indice(s, paso + 1)
                if self._respira(s, paso + 1, siguiente):
                    duracion = 2 * TICKS_POR_PASO       # se sostiene sobre la raíz que sigue
                elif azar_fijo(f"{s.seed}:liga:{i}") < s.deslices * 0.3:
                    duracion = TICKS_POR_PASO           # llena, termina justo cuando entra la siguiente
            # Desfase dentro del paso: swing en los pasos impares y retraso del patrón
            # (pulsos tarde dentro del paso: así caben los tresillos).
            desfase = _desfase(s, paso, p)
            if s.separar and referencia is not None:
                # Separar también en el ritmo: a 1-3 ticks de un ataque de la referencia sería un flam.
                if referencia.toco is not None and referencia.toco[0] == paso:
                    desfase = referencia.toco[3]   # ataca en este paso: va con ella (derecha o corrida)
                elif desfase >= TICKS_POR_PASO - 3:
                    sig = referencia.patron[_indice(referencia, paso + 1)]
                    if sig["suena"] and TICKS_POR_PASO + _desfase(referencia, paso + 1, sig) - desfase <= 3:
                        desfase = 0   # quedaría pegada al golpe que la referencia da en el paso siguiente
                previo = referencia.toco_previo
                if previo is not None and 0 < TICKS_POR_PASO - previo[3] + desfase <= 3:
                    # La referencia atacó tarde en el paso anterior, pegada a esta nota: flam. Calla.
                    s.slide_previo = False
                    s.toco = None
                    continue
                s.toco = s.toco[:3] + (desfase,)
            inicio = self.tick + desfase
            if ornamento is not None and not (s.slide_previo and nota in s.sonando):
                self._tocar_ornamento(s, ornamento, inicio, nota, velocidad, duracion)
                s.slide_previo = False
                continue
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
            if s.doble and not (s.slide_previo and nota in s.sonando and slide):
                # Voz doble (Apex 004): una segunda voz paralela por grados de la escala,
                # un poco más suave; respeta el techo bajándola una octava.
                segunda = _por_grados(s.tonalidad or self.tonalidad, nota, VOZ_DOBLE[s.doble])
                while segunda > min(s.techo, 127) and segunda - 12 > nota:
                    segunda -= 12
                if segunda != nota and segunda <= 127:   # arriba de todo, la voz doble no cabe
                    self._programar(s, inicio, segunda, max(1, velocidad - 12), duracion)
            s.slide_previo = slide

    def _suenan(self, r):
        """Notas de la secuencia `r` que suenan en este paso (las que siguen y las que atacó)."""
        notas = {n for n, fin in r.sonando.items() if fin > self.tick}
        notas |= {n for t, n, _, _ in r.pendientes if t < self.tick + TICKS_POR_PASO}
        if r.toco is not None:
            notas.add(r.toco[1])
        return notas

    def _ornamento_raga(self, s, nota, i, duracion):
        """Ornamentos de pitch bend de la raga sobre la nota del paso (no agregan notas,
        así nada sale de la rejilla): meend si la raga desliza hacia esta nota y el
        bend alcanza; andolan si es una nota que tiembla y se sostiene."""
        if not s.bend_rango:
            return None
        tonica = (s.tonalidad or self.tonalidad).tonica
        d = raga.meend(s.raga, nota, tonica)
        if d and abs(d) <= s.bend_rango and duracion >= 3 and azar_fijo(f"{s.seed}:meend:{i}") < s.ornamentos * 0.45:
            return ("meend", d)
        if (raga.oscila(s.raga, nota, tonica) and duracion >= 2 * TICKS_POR_PASO - 1
                and azar_fijo(f"{s.seed}:andolan:{i}") < s.ornamentos):
            return ("andolan", None)
        return None

    def _tocar_ornamento(self, s, ornamento, inicio, nota, velocidad, duracion):
        tipo, dato = ornamento
        if tipo == "meend":      # parte desde la otra nota con el pitch bend y llega deslizándose
            pasos = max(2, min(duracion - 1, 5))
            self._bend(s, inicio, raga.bend(dato, s.bend_rango))
            for k in range(1, pasos + 1):
                self._bend(s, inicio + k, raga.bend(dato * (1 - k / pasos) ** 1.5, s.bend_rango))
        elif tipo == "andolan":  # vaivén lento y poco profundo (un cuarto de tono)
            for k in range(2, duracion, 2):
                self._bend(s, inicio + k, raga.bend(0.25 * (1 if (k // 2) % 2 else -1) * min(1, k / 6), s.bend_rango))
            self._bend(s, inicio + duracion, 0)
        self._programar(s, inicio, nota, velocidad, duracion)

    def _en_rejilla(self, s, paso, p):
        """Ornamento en la rejilla de semicorcheas: si este paso es una nota fija (Sa o
        Pa, nunca el uno del compás) y al lado hay una nota que la raga adorna, este paso
        toma la nota del adorno. Devuelve (grado, octava) o None.
        - kan: el paso antes de la nota adornada toma su nota de gracia (r con gracia de G).
        - gamak: los dos pasos después de una nota que tiembla hacen el trino (vecina, nota).
        - deslices sin raga: el paso antes de un adorno se le acerca por grado (aproximación)."""
        fija = lambda q: q["suena"] and q["grado"] % 7 in (0, 4)  # noqa: E731  (Sa o Pa: notas fijas)
        if (not fija(p) or paso % PASOS_POR_COMPAS == 0
                or not (s.raga and s.ornamentos > 0 or s.deslices > 0)):
            return None
        vecino = lambda k: s.patron[_indice(s, paso + k)]  # noqa: E731
        sig, ant, ant2 = vecino(1), vecino(-1), vecino(-2)
        j = _indice(s, paso)
        if s.raga and s.ornamentos > 0:
            r = raga.RAGAS[s.raga]
            esc = r["escala"]
            adornada = lambda q: q["suena"] and not fija(q) and esc[q["grado"] % 7] in r["oscila"]  # noqa: E731
            if adornada(ant):
                if azar_fijo(f"{s.seed}:gamak:{j}") < s.ornamentos * 0.6:
                    return (ant["grado"] + 1, ant.get("octava", 0))      # trino: la vecina de arriba
            if (adornada(ant2) and fija(ant)
                    and azar_fijo(f"{s.seed}:gamak:{j - 1}") < s.ornamentos * 0.6
                    and azar_fijo(f"{s.seed}:gamak2:{j}") < s.ornamentos * 0.5):
                return (ant2["grado"], ant2.get("octava", 0))            # …y vuelve a la nota
            if sig["suena"] and not fija(sig):
                clase = esc[sig["grado"] % 7]
                if clase in r["kan"] and azar_fijo(f"{s.seed}:kan:{j}") < s.ornamentos * 0.7:
                    fuente = esc.index(r["kan"][clase]) if r["kan"][clase] in esc else None
                    if fuente is not None:
                        d = (fuente - sig["grado"] % 7 + 3) % 7 - 3      # el camino corto en la escala
                        return (sig["grado"] + d, sig.get("octava", 0))
        if s.deslices > 0 and sig["suena"] and not fija(sig) and azar_fijo(f"{s.seed}:aprox:{j}") < s.deslices * 0.4:
            arriba = azar_fijo(f"{s.seed}:aprox_dir:{j}") < 0.6
            return (sig["grado"] + (1 if arriba else -1), sig.get("octava", 0))
        return None

    def _bend(self, s, tick, valor):
        if tick <= self.tick:
            self.enviar(s.salida, "pitchwheel", s.canal, valor, 0)
            s.bend_movido = valor != 0
        else:
            s.bends.append((tick, valor))

    @staticmethod
    def _respira(s, paso, i):
        """Deslices: esta raíz (en un paso débil) no se ataca; la nota anterior se
        sostiene sobre ella. Menos ametralladora, más canto."""
        if s.deslices <= 0 or paso % PASOS_POR_COMPAS == 0 or generador.es_fuerte(s.posicion, paso):
            return False
        p = s.patron[i]
        anterior = s.patron[_indice(s, paso - 1)]
        return (p["suena"] and p["grado"] == 0 and anterior["suena"]
                and azar_fijo(f"{s.seed}:respira:{i}") < s.deslices * 0.35)

    @staticmethod
    def _ultima_antes_del_cambio(s, paso, falta):
        """True si ninguna otra nota de la secuencia suena antes del cambio de acorde."""
        for k in range(1, falta):
            q = paso + k
            j = _indice(s, q)
            pq = s.patron[j]
            if (pq["suena"] and generador.pasa_posicion(s.posicion, q)
                    and s.extra[pq.get("fuente", j)]["densidad"] < s.densidad):
                return False
        return True

    def _programar(self, s, tick, nota, velocidad, duracion):
        if not 0 <= nota <= 127:
            return   # fuera del MIDI (una octava o voz paralela arriba de todo): no se toca
        if tick <= self.tick:
            self._encender(s, nota, velocidad, self.tick + duracion)
        else:
            s.pendientes.append((tick, nota, velocidad, duracion))

    def _encender(self, s, nota, velocidad, fin):
        if not 0 <= nota <= 127:
            return
        if nota in s.sonando:
            self.enviar(s.salida, "note_off", s.canal, nota, 0)
        self.enviar(s.salida, "note_on", s.canal, nota, velocidad)
        s.sonando[nota] = fin

    def _callar(self, s):
        for nota in list(s.sonando):
            self.enviar(s.salida, "note_off", s.canal, nota, 0)
        s.sonando.clear()
        s.pendientes = []
        self._soltar_bend(s)

    def _soltar_bend(self, s):
        """El pitch bend vuelve al centro (si una raga lo había movido)."""
        s.bends = []
        if s.bend_movido:
            self.enviar(s.salida, "pitchwheel", s.canal, 0, 0)
            s.bend_movido = False

    def _apagar_vencidas(self):
        for s in self.secuencias:
            for nota, fin in list(s.sonando.items()):
                if fin <= self.tick:
                    self.enviar(s.salida, "note_off", s.canal, nota, 0)
                    del s.sonando[nota]
            if s.bends:
                for _, valor in sorted(b for b in s.bends if b[0] <= self.tick):
                    self.enviar(s.salida, "pitchwheel", s.canal, valor, 0)
                    s.bend_movido = valor != 0
                s.bends = [b for b in s.bends if b[0] > self.tick]
            if s.pendientes:
                listas = [p for p in s.pendientes if p[0] <= self.tick]
                s.pendientes = [p for p in s.pendientes if p[0] > self.tick]
                for _, nota, velocidad, duracion in listas:
                    self._encender(s, nota, velocidad, self.tick + duracion)

    def _obertura_sigue(self, compas, parte):
        """¿La parte siguiente también tiene la obertura enlazada? (una vez por parte)"""
        clave = (compas - parte["dentro"], parte["i"])
        if getattr(self, "_ob_sigue", (None, False))[0] != clave:
            sigue = False
            prox = self.conductor.parte(self.base, compas - parte["dentro"] + parte["largo"])
            if prox is not None:
                cfg = self._config_parte(prox["i"]) or self.config or {}
                o = cfg.get("obertura", {})
                sigue = bool(o.get("activo") and o.get("largo_parte") and o.get("enlazar"))
            self._ob_sigue = (clave, sigue)
        return self._ob_sigue[1]

    def apagar_todo(self, pads=True):
        for s in self.secuencias:
            for nota in list(s.sonando):
                self.enviar(s.salida, "note_off", s.canal, nota, 0)
            s.sonando.clear()
            s.pendientes = []
            s.slide_previo = False
            self._soltar_bend(s)
        if pads and self.pads is not None:
            self.pads.apagar(self.enviar)
        if self.dialogo is not None:
            self.dialogo.apagar(self.enviar)
        if self.bajo is not None:
            self.bajo.apagar(self.enviar)
        if self.fx is not None:
            self.fx.apagar(self.enviar)
        if self.texturas is not None:
            self.texturas.apagar(self.enviar)
        if self.obertura is not None:
            self.obertura.apagar(self.enviar)
        if self.tocado is not None:
            self.tocado.apagar(self.enviar)


VOZ_DOBLE = {"tercera": 2, "cuarta": 3, "quinta": 4, "sexta": 5, "octava": 7}


def _desfase(s, paso, p):
    """Ticks tarde dentro del paso: swing (pasos impares) más el retraso del patrón."""
    return (round(s.swing * TICKS_POR_PASO) if paso % 2 == 1 else 0) + p.get("retraso", 0)


def _anotar_huella(s, paso):
    """Lo que la secuencia tocó de verdad en cada paso de su patrón (para verlo en la app):
    [nota, fuerte] o None si calló. Se sobreescribe en cada vuelta, así se ve lo que mutó."""
    largo = max(1, s.largo)
    huella = getattr(s, "huella", None)
    if huella is None or len(huella) != largo:
        huella = s.huella = [None] * largo
    i = _indice(s, paso) % largo
    t = s.toco
    huella[i] = [t[1], bool(t[2])] if t is not None and t[0] == paso and s.activa else None
    s.huella_paso = i


def _indice(s, paso):
    """Índice del patrón de `s` en `paso`, con su corrimiento (el patrón entra N pasos tarde)."""
    return generador.recorrer(s.recorrido, paso - s.corrimiento, s.largo, s.seed)


CHOCAN = {1, 2, 6, 10, 11}   # segundas, tritono y séptimas (y la misma nota exacta)


def choca(n, o):
    """Choque cercano: la misma nota, o segunda, séptima o tritono a menos de una octava.
    A más distancia (la ♭9 del frigio: raíz abajo, ♭2 arriba) es la tensión del estilo."""
    return n == o or (abs(n - o) < 12 and abs(n - o) % 12 in CHOCAN)


def _separar(tonalidad, nota, otras, techo=127, acorde=None):
    """La nota de la escala más cercana a `nota` (hasta una quinta) que no choca de cerca
    con ninguna de `otras`; ante un empate, la de abajo. Sin choques, `nota` tal cual.
    Con armonía guiada (`acorde` = clases del acorde que suena), si `nota` era del acorde
    busca primero entre las notas del acorde: así no se pierde la armonía en los tiempos."""
    if not otras:
        return nota
    chocan = lambda n: any(choca(n, o) for o in otras)  # noqa: E731
    if not chocan(nota):
        return nota
    del_acorde = bool(acorde) and nota % 12 in acorde
    posibles = set(tonalidad.notas) | ({n for n in range(128) if n % 12 in acorde} if del_acorde else set())
    candidatas = [n for n in posibles if abs(n - nota) <= 7 and n <= techo and not chocan(n)]
    if not candidatas:
        return nota
    return min(candidatas, key=lambda n: (del_acorde and n % 12 not in acorde, abs(n - nota), n))


def _por_grados(tonalidad, nota, grados):
    """La nota de la escala `grados` pasos arriba de `nota` (la octava: 12 semitonos)."""
    if grados == 7:
        return nota + 12
    arriba = [n for n in tonalidad.notas if n > nota]
    return arriba[grados - 1] if len(arriba) >= grados else nota + 12


def _vecina(tonalidad, nota, arriba=True):
    """La nota de la escala justo arriba (o abajo) de `nota`, para un mordente."""
    if arriba:
        return next((n for n in tonalidad.notas if n > nota), None)
    return next((n for n in reversed(tonalidad.notas) if n < nota), None)
