"""Llamada y respuesta euclidiana.

Dos voces que conversan con ritmos euclidianos: cada una reparte sus golpes de
la forma más pareja posible en el compás. Todo cae en una rejilla (corcheas o
semicorcheas) y la llamada siempre tiene un golpe en el uno, así nada se
arrastra respecto del bombo.

Formas de conversar:
- entrelazado: la respuesta toca solo en los huecos que deja la llamada,
  esperando `espacio` lugares después de cada nota de la llamada.
- turnos: la llamada toca unos compases, luego responde la otra voz, y alternan.

La llamada la toca el motor (con su nota larga) o la tocas tú en vivo: el motor
escucha dónde tocaste en cada compás y en el siguiente responde en tus huecos.

Las notas salen de un conjunto chico según Luminoso ↔ Oscuro, contadas en la
escala desde la raíz del acorde de los pads (o de la nota larga). Cada voz
repite su orden de notas, y la mutación cambia una nota o gira el patrón
cada cierto número de compases, como las secuencias.

Armonía guiada: sigue la raíz del acorde de los pads, la última nota de cada
voz en el compás cierra en una nota del acorde (salvo ultra oscuro) y, con
anticipar, la última antes de un cambio de acorde lleva al que viene.

Pegado ↔ Desplazado: en 0 todo cae justo en la rejilla. Al subirlo, algunas
notas se corren una semicorchea (nunca el uno de la llamada), y las que caen en
semicorcheas débiles se atrasan un pulso (swing) o se humanizan. Cada voz usa el
valor general o uno propio.
"""

import random

from . import armonia, generador

from .escalas import Tonalidad

TICKS_POR_PASO = 6
PASOS_POR_COMPAS = 16

MODOS = ("motor", "en_vivo")
# Cómo contesta la respuesta: contraste (sus propias notas), eco (las notas de la
# llamada), espejo (la llamada dada vuelta: si sube, baja) o cierra (termina en la raíz).
RESPONDE = ("contraste", "eco", "espejo", "cierra")
FORMAS = ("entrelazado", "turnos")
REJILLAS = {"corcheas": 2, "semicorcheas": 1}  # pasos de semicorchea por lugar

# Notas de cada voz según el color, en grados de la escala desde la raíz del acorde.
# La primera es el ancla (el golpe del uno en la llamada). La respuesta vive más
# arriba: parte de la quinta y llega a la octava.
NOTAS = {
    "luminoso": {"llamada": (0, 2, 4, 6), "respuesta": (4, 6, 7, 9)},   # raíz, ♭3, 5, ♭7
    "claro": {"llamada": (0, 2, 4), "respuesta": (4, 6, 7)},
    "oscuro": {"llamada": (0, 1, 4), "respuesta": (4, 5, 7)},           # ♭2 y ♭6: el color frigio
    "ultra": {"llamada": (0, 1, 0, 1), "respuesta": (5, 4, 8)},         # medio tono contra la raíz
}
LARGO_MAXIMO = 8  # pasos: con largo 100 % una nota sola puede sostenerse hasta medio compás


def color(oscuridad):
    if oscuridad < 0.15:
        return "luminoso"
    if oscuridad < 0.5:
        return "claro"
    if oscuridad < 0.85:
        return "oscuro"
    return "ultra"


def euclides(golpes, lugares, giro=0):
    """`golpes` repartidos lo más parejo posible en `lugares` (lista de booleanos)."""
    if lugares <= 0:
        return []
    golpes = max(0, min(golpes, lugares))
    return [((i + giro) * golpes) % lugares < golpes for i in range(lugares)]


def lugares_abiertos(molde, lugares, paso_lugar, prob=0.5, rng=None):
    """El filtro (molde de 16 pasos: x pasa, ? a veces, - bloquea) en lugares: el
    conjunto de lugares por donde pasa una nota. Los ? se deciden en cada compás."""
    molde = (str(molde or "") + "-" * 16)[:16]
    rng = rng or random.Random(0)
    molde = "".join(("x" if rng.random() < prob else "-") if c == "?" else ("x" if c not in "-" else "-")
                    for c in molde)
    return {i for i in range(lugares) if "x" in molde[i * paso_lugar:(i + 1) * paso_lugar]}


def filtrar(elegidos, abiertos, lugares):
    """Pasa los lugares elegidos por el filtro: los que caen en un lugar cerrado se
    corren al abierto más cercano (así la voz conserva sus notas); si dos van al
    mismo lugar suena una. Sin lugares abiertos, nada."""
    if not abiertos:
        return []
    salida = []
    for l in elegidos:
        if l not in abiertos:
            l = min(abiertos, key=lambda a: (min((a - l) % lugares, (l - a) % lugares), (a - l) % lugares))
        if l not in salida:
            salida.append(l)
    return sorted(salida)


def giros_anclados(golpes, lugares):
    """Giros del patrón que dejan un golpe en el primer lugar (el uno del compás)."""
    return [g for g in range(lugares) if euclides(golpes, lugares, g)[:1] == [True]]


class Voz:
    def __init__(self, cfg, papel, seed):
        self.papel = papel
        self.salida = cfg.get("salida", "FM-1")
        self.canal = int(cfg.get("canal", 4)) - 1
        self.golpes = max(1, int(cfg.get("golpes", 3)))
        self.octava = int(cfg.get("octava", 1))
        self.oscuridad = float(cfg.get("oscuridad", 0.7))
        self.gate = float(cfg.get("gate", 0.5))
        self.velocidad = int(cfg.get("velocidad", 100))
        self.vel_random = float(cfg.get("vel_random", 0.15))
        self.desplazamiento = float(cfg.get("desplazamiento", -1.0))  # menos de 0 = el general
        self.filtro = bool(cfg.get("filtro", False))   # el molde filtra sus notas
        self.molde = str(cfg.get("molde", ""))
        self.molde_prob = float(cfg.get("molde_prob", 0.5))
        self.recorrido = cfg.get("recorrido", "adelante")   # orden de sus notas
        self.molde_muta = float(cfg.get("molde_muta", 0.0))
        self.molde_estilo = cfg.get("molde_estilo", "goa")
        self.molde_vivo = self.molde
        self.variante = int(cfg.get("variante", 0))   # «Otra» la sube, «Volver» la baja
        self.fija = bool(cfg.get("fija", False))      # «Fijar»: la mutación no la toca
        sufijo = f":{self.variante}" if self.variante else ""
        self.rng = random.Random(f"{papel}:{seed}{sufijo}")          # notas y mutaciones
        self.rng_vel = random.Random(f"fuerza:{papel}:{seed}")  # matices de fuerza, aparte
        self.color = color(self.oscuridad)
        self.grados = NOTAS[self.color][papel]
        # El ancla primero; después cada otra nota del color al menos una vez (si caben),
        # para que el color se escuche siempre; el resto, al azar dentro del color.
        otras = list(dict.fromkeys(g for g in self.grados[1:] if g != self.grados[0])) or [self.grados[0]]
        self.rng.shuffle(otras)
        self.orden = ([self.grados[0]] + otras + [self.rng.choice(self.grados) for _ in range(self.golpes)])[:self.golpes]
        self.giro = 0

    def mutar(self, cantidad, lugares, anclada):
        """Cambia una nota o gira el patrón; `cantidad` es la probabilidad de cambiar."""
        if self.fija or self.rng.random() >= cantidad:
            return
        if len(self.orden) > 1 and self.rng.random() < 0.5:
            i = self.rng.randrange(1, len(self.orden))
            self.orden[i] = self.rng.choice(self.grados)
            return
        giros = giros_anclados(self.golpes, lugares) if anclada else list(range(lugares))
        giros = [g for g in giros if g != self.giro]
        if giros:
            self.giro = self.rng.choice(giros)


class Dialogo:
    def __init__(self, cfg, cfg_llamada, cfg_respuesta, tonica, escala, adaptacion, desplazamiento=0.0):
        self.activo = bool(cfg.get("activo", False))
        self.desplazamiento = max(0.0, min(1.0, float(desplazamiento)))
        self.guiada = False   # armonía guiada: el motor lo decide (ver motor._crear_dialogo)
        self.tension = 0.3
        self.anticipar = True
        self.modo = cfg.get("modo", "motor")
        self.forma = cfg.get("forma", "entrelazado")
        self.rejilla = cfg.get("rejilla", "corcheas")
        self.espacio = max(0, int(cfg.get("espacio", 1)))
        self.compases_turno = max(1, int(cfg.get("compases_turno", 2)))
        self.escucha = int(cfg.get("escucha", 4)) - 1
        self.seguir_pads = bool(cfg.get("seguir_pads", True))
        self.evolucion = float(cfg.get("evolucion", 0.5))
        self.mutar_cada = max(1, int(cfg.get("mutar_cada", 4)))
        self.seed = str(cfg.get("seed", "CR-0001"))
        self.responde = cfg.get("responde", "contraste")
        if self.responde not in RESPONDE:
            raise ValueError(f"responde debe ser una de: {', '.join(RESPONDE)}")
        for nombre, valor, opciones in (("modo", self.modo, MODOS), ("forma", self.forma, FORMAS),
                                        ("rejilla", self.rejilla, tuple(REJILLAS))):
            if valor not in opciones:
                raise ValueError(f"{nombre} debe ser una de: {', '.join(opciones)}")
        self.cfg_voces = (cfg_llamada, cfg_respuesta)
        self.tonalidad = Tonalidad(tonica, escala)
        self.adaptacion = adaptacion
        self.disparo = None  # lo resuelve el motor
        self.clip = None     # nombre del clip de diálogo que suena, si vino del disparador
        self.sonando = {}    # (salida, canal, nota) -> tick en que se apaga
        self.pendientes = []  # (tick, voz, nota, dur, vel): notas atrasadas por el desplazamiento
        self.reiniciar()

    @property
    def paso_lugar(self):
        return REJILLAS[self.rejilla]

    @property
    def lugares(self):
        return PASOS_POR_COMPAS // self.paso_lugar

    def reiniciar(self):
        self.llamada = Voz(self.cfg_voces[0], "llamada", self.seed)
        self.respuesta = Voz(self.cfg_voces[1], "respuesta", self.seed)
        # La seed y cada variante («Otra») también cambian el ritmo: otro giro (la
        # llamada, siempre en el uno). Con un azar aparte, para no tocar las notas.
        anclados = giros_anclados(self.llamada.golpes, self.lugares) or [0]
        self.llamada.giro = random.Random(f"giro:llamada:{self.seed}:{self.llamada.variante}").choice(anclados)
        self.respuesta.giro = random.Random(f"giro:respuesta:{self.seed}:{self.respuesta.variante}").randrange(self.lugares)
        self.inicio = None      # compás donde empezó la conversación
        self.ultimo_paso = None
        self.plan = []          # (paso, voz, grado, dur, vel, retraso en pulsos)
        self.pendientes = []
        self.fase = None
        self.compas_actual = 0
        self.raiz_vivo = None
        self.tocado = set()     # en vivo: lugares donde tocaste en este compás
        self.notas_vivo = []

    def continuar_de(self, viejo):
        """Retoma la conversación de `viejo` al cambiar ajustes en vivo: conserva el
        compás de inicio y lo mutado, y rehace el compás en curso con lo nuevo."""
        if (viejo.modo, viejo.seed) != (self.modo, self.seed):
            return
        for nueva, vieja in ((self.llamada, viejo.llamada), (self.respuesta, viejo.respuesta)):
            nueva.rng.setstate(vieja.rng.getstate())
            if nueva.variante != vieja.variante:
                continue  # «Otra» o «Volver»: entra la frase nueva, no la mutada de antes
            if nueva.molde == vieja.molde and nueva.molde_muta > 0:
                nueva.molde_vivo = vieja.molde_vivo
            if (nueva.golpes, nueva.grados) == (vieja.golpes, vieja.grados):
                nueva.orden = list(vieja.orden)
            if viejo.rejilla == self.rejilla:
                nueva.giro = vieja.giro % self.lugares
        if (self.llamada.variante == viejo.llamada.variante and not self.llamada.filtro
                and not euclides(self.llamada.golpes, self.lugares, self.llamada.giro)[:1] == [True]):
            self.llamada.giro = 0  # la llamada siempre en el uno
        self.inicio, self.ultimo_paso = viejo.inicio, viejo.ultimo_paso
        self.tocado, self.notas_vivo, self.raiz_vivo = viejo.tocado, viejo.notas_vivo, viejo.raiz_vivo
        if self.activo and viejo.ultimo_paso is not None and (self.inicio is not None or self.modo == "en_vivo"):
            paso = viejo.ultimo_paso
            inicio_compas = paso - paso % PASOS_POR_COMPAS
            compas = inicio_compas // PASOS_POR_COMPAS - (self.inicio or 0)
            if self.modo == "en_vivo":
                # La respuesta en curso sigue tal cual, ya con los ajustes nuevos de la voz.
                self.plan = [(p, self.respuesta, g, d, v, r) for p, _, g, d, v, r in viejo.plan]
            else:
                self._compas(compas, inicio_compas)
                self.plan = [e for e in self.plan if e[0] > paso]

    # --- Patrones de un compás ---

    def huecos(self, ocupados):
        """Lugares libres para la respuesta: fuera de los ocupados y esperando
        `espacio` lugares después de cada uno."""
        n = self.lugares
        return [i for i in range(n)
                if i not in ocupados and not any(1 <= (i - j) % n <= self.espacio for j in ocupados)]

    def _abiertos(self, voz):
        """Lugares por donde pasa la voz con su filtro, o None si el filtro está apagado."""
        if not voz.filtro:
            return None
        rng = random.Random(f"{self.seed}:{voz.papel}:molde:{self.compas_actual}")
        return lugares_abiertos(voz.molde_vivo, self.lugares, self.paso_lugar, voz.molde_prob, rng)

    def notas_de(self, voz, cantidad):
        """Las notas del motivo de la voz para este compás, en su orden (adelante, atrás,
        péndulo o al azar). Adelante es el de siempre."""
        n = len(voz.orden)
        if voz.recorrido == "adelante":
            return [voz.orden[k % n] for k in range(cantidad)]
        base = self.compas_actual * cantidad
        return [voz.orden[generador.recorrer(voz.recorrido, base + k, n, f"{self.seed}:{voz.papel}")]
                for k in range(cantidad)]

    def lugares_llamada(self):
        voz = self.llamada
        patron = euclides(voz.golpes, self.lugares, voz.giro)
        elegidos = [i for i, x in enumerate(patron) if x]
        abiertos = self._abiertos(voz)
        return elegidos if abiertos is None else filtrar(elegidos, abiertos, self.lugares)

    def lugares_respuesta(self, ocupados):
        voz = self.respuesta
        if not ocupados:  # turno propio: su euclidiano en todo el compás
            patron = euclides(voz.golpes, self.lugares, voz.giro)
            elegidos = [i for i, x in enumerate(patron) if x]
            libres = set(range(self.lugares))
        else:
            libres = self.huecos(ocupados)
            patron = euclides(min(voz.golpes, len(libres)), len(libres), voz.giro)
            elegidos = [h for h, x in zip(libres, patron) if x]
            libres = set(libres)
        abiertos = self._abiertos(voz)
        return elegidos if abiertos is None else filtrar(elegidos, abiertos & libres, self.lugares)

    def grados_respuesta(self, cantidad):
        """Las notas de la respuesta según cómo contesta."""
        propias = self.notas_de(self.respuesta, cantidad)
        if self.responde == "eco":
            return self.notas_de(self.llamada, cantidad)
        if self.responde == "espejo":
            # La llamada dada vuelta en la octava de arriba: si la llamada sube, la respuesta baja.
            return [7 - g for g in self.notas_de(self.llamada, cantidad)]
        if self.responde == "cierra" and propias:
            propias[-1] = 7  # termina en la raíz (una octava arriba, donde vive la respuesta)
        return propias

    def _compas(self, compas, paso, tocado=None):
        """Plan de un compás. En vivo, `tocado` son los lugares donde tocaste el compás anterior."""
        self.compas_actual = compas
        if self.modo == "en_vivo":
            golpes_l = []
            golpes_r = self.lugares_respuesta(set(tocado)) if tocado else []
            self.fase = "respuesta" if golpes_r else "escuchando"
        elif self.forma == "turnos":
            responde = (compas // self.compases_turno) % 2 == 1
            golpes_l = [] if responde else self.lugares_llamada()
            golpes_r = self.lugares_respuesta(set()) if responde else []
            self.fase = "respuesta" if responde else "llamada"
        else:
            golpes_l = self.lugares_llamada()
            golpes_r = self.lugares_respuesta(set(golpes_l))
            self.fase = "conversando"
        grados_l = self.notas_de(self.llamada, len(golpes_l))
        grados_r = self.grados_respuesta(len(golpes_r))
        eventos = sorted([(i, self.llamada, grados_l[k]) for k, i in enumerate(golpes_l)]
                         + [(i, self.respuesta, grados_r[k]) for k, i in enumerate(golpes_r)], key=lambda e: e[0])
        inicios, retrasos = self._desplazar(compas, eventos)
        # Cada nota dura según su largo, pero termina antes de que entre la siguiente
        # (de cualquier voz, también el uno del compás que viene): no se pisan.
        inicios.append(PASOS_POR_COMPAS)
        self.plan = []
        for k, (i, voz, grado) in enumerate(eventos):
            inicio, retraso = inicios[k], retrasos[k]
            hasta = inicios[k + 1] - inicio
            pasos = min(hasta * 0.9, max(0.5, voz.gate * min(hasta, LARGO_MAXIMO)))
            dur = round(pasos * TICKS_POR_PASO)
            dur = max(1, min(dur, hasta * TICKS_POR_PASO - retraso - 1))
            vel = voz.velocidad + (8 if i == 0 else 0) + round(voz.vel_random * 20 * voz.rng_vel.uniform(-1, 1))
            self.plan.append((paso + inicio, voz, grado, dur, max(1, min(127, vel)), retraso))

    def desplazamiento_de(self, voz):
        return voz.desplazamiento if voz.desplazamiento >= 0 else self.desplazamiento

    def _desplazar(self, compas, eventos):
        """Pasos de inicio y retrasos (en pulsos) de cada evento, según Pegado ↔ Desplazado.

        Determinista por variante y compás. El uno de la llamada nunca se mueve, y una
        nota corrida nunca llega a la siguiente."""
        rng = random.Random(f"desplazar:{self.seed}:{compas}")
        base = [i * self.paso_lugar for i, _, _ in eventos]
        inicios, retrasos = [], []
        for k, (i, voz, _) in enumerate(eventos):
            d = self.desplazamiento_de(voz)
            inicio = base[k]
            siguiente = base[k + 1] if k + 1 < len(base) else PASOS_POR_COMPAS
            correr = rng.random() < d
            if correr and not (voz is self.llamada and i == 0) and inicio + 1 < siguiente:
                inicio += 1
            retraso = (1 if inicio % 2 == 1 and d >= 0.5 else 0) + (1 if rng.random() < d * 0.3 else 0)
            inicios.append(inicio)
            retrasos.append(retraso if d > 0 else 0)
        return inicios, retrasos

    def _mutar(self, compas):
        if compas <= 0 or compas % self.mutar_cada:
            return
        if self.evolucion > 0:
            self.llamada.mutar(self.evolucion, self.lugares, anclada=True)
            self.respuesta.mutar(self.evolucion, self.lugares, anclada=False)
        for voz in (self.llamada, self.respuesta):
            if voz.filtro and voz.molde_muta > 0 and not voz.fija:
                rng = random.Random(f"{self.seed}:{voz.papel}:molde_muta:{compas}")
                voz.molde_vivo = generador.mutar_molde(voz.molde_vivo, rng, voz.molde_muta, voz.molde_estilo)

    # --- En vivo ---

    def entrada_on(self, nota, velocidad, tick):
        if not self.activo or self.modo != "en_vivo":
            return
        # Se cuantiza al lugar más cercano de la rejilla; al final del compás cuenta como el uno.
        largo_lugar = self.paso_lugar * TICKS_POR_PASO
        lugar = round((tick % (PASOS_POR_COMPAS * TICKS_POR_PASO)) / largo_lugar)
        self.tocado.add(lugar % self.lugares)
        self.notas_vivo.append(nota)

    def entrada_off(self, nota, tick):
        pass

    # --- Llamado por el motor en cada paso ---

    def paso(self, paso, tick, raiz, enviar, momento=None):
        if not self.activo or paso == self.ultimo_paso:
            return
        if self.modo == "en_vivo":
            self.ultimo_paso = paso
            self._paso_vivo(paso, raiz, enviar, momento)
            return
        if raiz is None:
            # Sin marcar el paso: si la nota larga llega un pulso tarde, el motor vuelve
            # a llamar en este mismo paso y la conversación igual empieza en el uno.
            if self.inicio is not None:
                self.apagar(enviar)
                self.reiniciar()
            return
        self.ultimo_paso = paso
        if self.inicio is None:
            if paso % PASOS_POR_COMPAS != 0:
                return  # la conversación empieza en un compás de la Circuit
            self.inicio = paso // PASOS_POR_COMPAS
        if paso % PASOS_POR_COMPAS == 0:
            compas = paso // PASOS_POR_COMPAS - self.inicio
            self._mutar(compas)
            self._compas(compas, paso)
        self._tocar(paso, raiz, enviar, momento)

    def _paso_vivo(self, paso, raiz, enviar, momento=None):
        if paso % PASOS_POR_COMPAS == 0:
            tocado, self.tocado = self.tocado, set()
            if tocado:
                # La respuesta queda en el registro de lo que tocaste.
                clase = (raiz if raiz is not None else self.tonalidad.tonica) % 12
                grave = min(self.notas_vivo) if self.notas_vivo else 48
                self.raiz_vivo = grave - ((grave - clase) % 12) - 12 * self.respuesta.octava
            self.notas_vivo = []
            self._mutar(paso // PASOS_POR_COMPAS)
            self._compas(paso // PASOS_POR_COMPAS, paso, sorted(tocado))
        self._tocar(paso, self.raiz_vivo, enviar, momento)

    def _tocar(self, paso, raiz, enviar, momento=None):
        if raiz is None:
            return
        for evento in [e for e in self.plan if e[0] == paso]:
            _, voz, grado, dur, vel, retraso = evento
            # Grados contados en la escala desde la raíz (la del acorde de los pads si
            # los sigue): nunca sale de la escala.
            nota = self.tonalidad.nota(raiz, grado, "escala") + 12 * voz.octava
            if self.guiada and momento is not None:
                despues = [e for e in self.plan if e[0] > paso]
                # Las notas salen del color (Luminoso ↔ Oscuro), que ya es la tensión del
                # diálogo: no se tocan. Solo la última nota de cada voz en el compás cierra
                # su motivo en el acorde, salvo en ultra oscuro, que queda colgado a propósito.
                cierra = not any(e[1] is voz for e in despues) and voz.color != "ultra"
                ultima = momento.cambia_pronto and not any(e[0] < paso + momento.falta for e in despues)
                nota = armonia.ajustar(nota, momento, self.tonalidad, cierra, ultima, 1.0, self.anticipar, 0.0)
            nota = max(0, min(127, nota))
            inicio = paso * TICKS_POR_PASO + retraso
            if retraso:
                self.pendientes.append((inicio, voz, nota, dur, vel))
            else:
                self._encender(voz, nota, vel, inicio + dur, enviar)
        self.plan = [e for e in self.plan if e[0] > paso]

    def _encender(self, voz, nota, vel, fin, enviar):
        clave = (voz.salida, voz.canal, nota)
        if clave in self.sonando:
            enviar(voz.salida, "note_off", voz.canal, nota, 0)
        enviar(voz.salida, "note_on", voz.canal, nota, vel)
        self.sonando[clave] = fin

    def tick(self, tick, enviar):
        for clave, fin in list(self.sonando.items()):
            if fin <= tick:
                salida, canal, nota = clave
                enviar(salida, "note_off", canal, nota, 0)
                del self.sonando[clave]
        if self.pendientes:
            listas = [p for p in self.pendientes if p[0] <= tick]
            self.pendientes = [p for p in self.pendientes if p[0] > tick]
            for inicio, voz, nota, dur, vel in listas:
                self._encender(voz, nota, vel, inicio + dur, enviar)

    def apagar(self, enviar):
        for salida, canal, nota in self.sonando:
            enviar(salida, "note_off", canal, nota, 0)
        self.sonando = {}
        self.pendientes = []
