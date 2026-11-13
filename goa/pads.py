"""Motor de pads y drones.

Progresiones lentas de estilo Goa, psytrance, chill y ambient. Los acordes se
arman apilando grados de la escala de la tonalidad, y cada cambio elige la
inversión que mueve menos las voces, para que suene ligado y orgánico.
Opcionalmente sostiene un drone grave en la raíz.

Con `pulso` > 0 los acordes no se sostienen: suenan en un ritmo euclidiano
suave (golpes repartidos en las corcheas del compás, el primero en el uno),
que se puede correr con el control Pegado ↔ Desplazado.

Los pads son la guía armónica del motor (ver armonia.py): `momento()` dice qué
acorde suena, cuál viene y cuándo. Con `suenan` en falso callan pero siguen
guiando. Con suspensiones, al cambiar de acorde una voz que se mueve por paso
se queda colgada y resuelve un tiempo después.
"""

import random

from .armonia import Momento
from .escalas import nombre_midi

TICKS_POR_PASO = 6
PASOS_POR_COMPAS = 16

# Grados de la escala (0 = i) por acorde de cada progresión.
PROGRESIONES = {
    "i_bII": [0, 1],                 # frigio: la tensión oscura del psytrance
    "i_bVI_bVII": [0, 5, 6],         # épica, para clímax
    "i_v": [0, 4],                   # con menor armónica suena i–V, sabor oriental
    "drone_modal": [0, 1, 0, 6],     # la raíz queda fija y los acordes se mueven encima
    "i_iv_bII_i": [0, 3, 1, 0],      # ciclo largo para breaks
    "andaluza": [0, 6, 5, 4],        # i–♭VII–♭VI–V, bajada muy Goa
    "i_IV": [0, 3],                  # con dórica, el IV mayor: abierto, psy chill
    "i_IV_i_bVII": [0, 3, 0, 6],     # psy chill con un respiro en ♭VII
    "i_bVI_bVII_v": [0, 5, 6, 4],    # chillgressive: oscura y en movimiento
    "i_bVI_iv_v": [0, 5, 3, 4],      # chillout: suave, para acordes de séptima y novena
    "pedal_I_II": [0, 1],            # con lidia, I y II sobre la misma raíz: galáctico
}

# Pasos de escala apilados desde la raíz del acorde.
ACORDES = {
    "quintas": [0, 4, 7],            # raíz, quinta, octava: oscuro y abierto
    "sus2": [0, 1, 4],
    "menor_add9": [0, 2, 4, 8],
    "triada": [0, 2, 4],
    "cluster": [0, 1, 2, 4],
    "septima": [0, 2, 4, 6],         # m7 / maj7 según el grado
    "novena": [0, 2, 4, 6, 8],       # con 4 voces suena la séptima; con 5, la novena
}

APERTURAS = ("cerrada", "abierta", "amplia")
ATAQUES = ("ligado", "reatacar")
BASES = ("nota", "tonica")
CENTRO = 48  # C3: centro del registro de los pads
TEXTURAS = ("acordes", "nota", "raiz_acorde")


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


def _sin_semitonos(notas, piso=36, techo=96):
    """Evita medio tono o ♭9 entre dos voces cualquiera (p. ej. la séptima mayor bajo
    la raíz de un acorde maj7): la nota de arriba baja hasta quedar bajo la otra
    (queda séptima mayor, que suena abierta); si no cabe, la de abajo sube.
    Medio tono entre voces de un pad suena a batido turbio, más con filtro compartido."""
    notas = sorted(set(notas))
    for _ in range(len(notas) * 3):
        par = next(((a, b) for i, a in enumerate(notas) for b in notas[i + 1:] if (b - a) % 12 == 1), None)
        if par is None:
            break
        a, b = par
        notas.remove(b)
        if a - 11 >= piso and a - 11 not in notas:
            notas.append(a - 11)        # b una séptima mayor bajo a
        elif b + 11 <= techo:
            notas.remove(a)
            notas += [b, b + 11]        # a una séptima mayor sobre b
        notas = sorted(set(notas))
    return notas


def euclides(golpes, lugares):
    """`golpes` repartidos parejo en `lugares`, con el primero en el uno."""
    golpes = max(0, min(golpes, lugares))
    return [i for i in range(lugares) if (i * golpes) % lugares < golpes]


class Pads:
    def __init__(self, cfg, tonalidad, desplazamiento=0.0):
        self.cfg = dict(cfg)
        self.desplazamiento_cfg = desplazamiento
        self.transicion = False  # el próximo cambio de acorde viene de un cambio de configuración
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
        self.rasgueo = max(0, min(24, int(cfg.get("rasgueo", 1))))
        self.pulso = max(0, min(8, int(cfg.get("pulso", 0))))
        self.desplazamiento = max(0.0, min(1.0, float(desplazamiento)))
        self.suenan = bool(cfg.get("suenan", True))
        self.textura = cfg.get("textura", "acordes")  # acordes, nota (sola) o raiz_acorde
        if self.textura not in TEXTURAS:
            raise ValueError(f"Textura desconocida: {self.textura!r}. Opciones: {', '.join(TEXTURAS)}")
        self.suspensiones = max(0.0, min(1.0, float(cfg.get("suspensiones", 0.0))))
        self.velocidad = int(cfg.get("velocidad", 80))
        self.seed = str(cfg.get("seed", "pads"))
        for nombre, valor, opciones in (("apertura", self.apertura, APERTURAS),
                                        ("ataque", self.ataque, ATAQUES), ("base", self.base, BASES)):
            if valor not in opciones:
                raise ValueError(f"{nombre} debe ser una de: {', '.join(opciones)}")
        self.tonalidad = tonalidad
        self.sonando = set()        # notas del acorde que están sonando
        self.nota_drone = None
        self.pendientes = []        # (tick, nota) por el rasgueo o el pulso
        self.apagados = []          # (tick, nota): fin de cada golpe del pulso
        self.programados = set()    # pasos del pulso ya programados
        self.acorde_pulso = []      # notas del acorde que toca el pulso
        self.resoluciones = []      # (tick, colgada, destino) de las suspensiones
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

    @property
    def voces_acorde(self):
        """Voces para el acorde: el drone y la raíz grave ocupan una voz cada uno
        (la MicroFreak toca 4 en total)."""
        ocupadas = (1 if self.drone else 0) + (1 if self.textura == "raiz_acorde" else 0)
        return max(2, self.voces - ocupadas)

    def _voicing(self, raiz_acorde):
        base = getattr(self, "base_actual", raiz_acorde)
        # Con drone, la raíz va sobre él (dos notas graves a un tono suenan turbias).
        piso = _limitar(base - 12) + 1 if self.drone else 28
        anterior = getattr(self, "raiz_grave", None)
        if self.textura == "nota":
            # Nota sola: la raíz de cada acorde, grave, moviéndose lo menos posible (como un bajo).
            n = _cerca(raiz_acorde % 12, anterior if anterior is not None else base - 12)
            while n < piso:
                n += 12
            while n > 47 and n - 12 >= piso:
                n -= 12
            self.raiz_grave = n
            return [n]
        notas = self._voicing_acorde(raiz_acorde)
        if self.textura == "raiz_acorde":
            raiz = _cerca(raiz_acorde % 12, anterior if anterior is not None else base - 12)
            while raiz >= min(notas) and raiz - 12 >= piso:
                raiz -= 12
            while raiz < piso:
                raiz += 12
            self.raiz_grave = raiz
            notas = sorted({raiz} | set(notas))
        return notas

    def _voicing_acorde(self, raiz_acorde):
        voces = self.voces_acorde
        pasos = list(self.acorde)
        while len(pasos) < voces:  # dobla raíz y quinta una octava arriba
            pasos.append(pasos[len(pasos) - len(self.acorde)] + 7)
        notas = [self.tonalidad.nota(raiz_acorde, p, "escala") for p in pasos[:voces]]
        # La segunda o novena de la escala a veces es ♭9 (en frigio, o sobre el v en
        # menor): medio tono contra la raíz, áspero en un pad. Se cambia por la raíz.
        notas = sorted({n - 1 if (n - raiz_acorde) % 12 == 1 else n for n in notas})
        if self.apertura in ("abierta", "amplia"):
            notas = [n + 12 if i % 2 == 1 else n for i, n in enumerate(notas)]
        if self.apertura == "amplia" and len(notas) > 3:
            notas[3] += 12
        notas = sorted(_limitar(n) for n in notas)
        return _sin_semitonos(self._mover_minimo(notas))

    def _mover_minimo(self, notas):
        """Elige la inversión que menos mueve las voces respecto al acorde que suena."""
        referencia = self.sonando or set(self.acorde_pulso)  # con pulso, entre golpes no suena nada
        referencia = set(referencia) - {getattr(self, "raiz_grave", None)}  # la raíz grave no cuenta para las voces
        if not referencia:
            return notas
        anterior = sorted(referencia)
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

    def _clases(self, raiz_acorde):
        """Notas del acorde para guiar a los otros motores (sin la novena ni dobles)."""
        return frozenset(self.tonalidad.nota(raiz_acorde, p, "escala") % 12 for p in self.acorde if p < 7)

    def momento(self, paso, raiz):
        """Momento armónico en `paso`: acorde actual, el que viene y cuántos pasos faltan."""
        base = self._base(raiz) if self.activo else None
        if base is None:
            return None
        largo = self.cambia_cada * PASOS_POR_COMPAS
        cambio = paso // largo
        actual = self.tonalidad.nota(base, self._grado(cambio), "escala")
        siguiente = self.tonalidad.nota(base, self._grado(cambio + 1), "escala")
        return Momento(actual, self._clases(actual), siguiente, self._clases(siguiente), (cambio + 1) * largo - paso)

    # --- Tiempo ---

    def actualizar(self, paso, raiz, tick, enviar):
        """Llamado en cada paso de semicorchea con la raíz de la nota larga."""
        if not self.activo:
            return
        base = self._base(raiz)
        if base is None or not self.suenan:  # en silencio igual guían: momento() no depende de esto
            self.apagar(enviar)
            return
        # Con pulso, los pads miran un paso adelante: así el golpe del uno del compás
        # que viene sale a tiempo, ya con su acorde (este llamado llega 2 pulsos tarde).
        cambio = ((paso + (1 if self.pulso else 0)) // 16) // self.cambia_cada
        clave = (cambio, base)
        if clave != self.clave:
            self._cambiar_acorde(clave, cambio, base, tick, enviar)
        if self.pulso:
            self._programar_pulso(paso, tick)
            self.tick(tick, enviar)

    def continuar_de(self, viejo, enviar):
        """Al cambiar la configuración en vivo: sigue sonando sin volver a atacar el acorde.

        Si nada de los pads cambió, sigue igual. Si cambió algo, al próximo paso pasa al
        acorde nuevo en ligado: las notas comunes siguen sonando y solo cambian las otras.
        Si cambió el destino, el canal o el pulso, apaga lo de antes y empieza de cero."""
        if viejo is None:
            return
        mismo_lugar = (viejo.salida, viejo.canal) == (self.salida, self.canal)
        if not mismo_lugar or not self.activo or not self.suenan or bool(viejo.pulso) != bool(self.pulso):
            viejo.apagar(enviar)
            return
        for k in ("sonando", "nota_drone", "raiz_acorde", "pendientes", "apagados", "resoluciones",
                  "programados", "acorde_pulso", "clave", "raiz_grave", "base_actual"):
            if not hasattr(viejo, k):
                continue
            setattr(self, k, getattr(viejo, k))
        igual = (viejo.cfg == self.cfg and viejo.desplazamiento_cfg == self.desplazamiento_cfg
                 and (viejo.tonalidad.tonica, tuple(viejo.tonalidad.intervalos))
                 == (self.tonalidad.tonica, tuple(self.tonalidad.intervalos)))
        if igual:
            return
        if not self.drone and self.nota_drone is not None:
            enviar(self.salida, "note_off", self.canal, self.nota_drone, 0)
            self.nota_drone = None
        self.clave = None  # recalcula el acorde en el próximo paso, en ligado
        self.transicion = True

    def _cambiar_acorde(self, clave, cambio, base, tick, enviar):
        self._resolver(tick, enviar, todas=True)  # una suspensión anterior resuelve antes del cambio
        self.clave = clave
        raiz_acorde = self.tonalidad.nota(base, self._grado(cambio), "escala")
        self.raiz_acorde = raiz_acorde
        self.base_actual = base
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

        if self.pulso:
            self.acorde_pulso = nuevas  # los golpes del pulso tocan este acorde
            self.pendientes = [p for p in self.pendientes if p[1] in nuevas]
            return

        transicion, self.transicion = self.transicion, False
        if self.ataque == "reatacar" and not transicion:
            quitar, poner = set(self.sonando), list(nuevas)
            self.pendientes = []
        else:
            quitar = self.sonando - set(nuevas)
            poner = [n for n in nuevas if n not in self.sonando]
            self.pendientes = [(t, n) for t, n in self.pendientes if n in nuevas]
        colgada = None if transicion else self._suspension(cambio, quitar, poner)
        for n in quitar:
            if colgada is None or n != colgada[0]:
                enviar(self.salida, "note_off", self.canal, n, 0)
        poner = [n for n in poner if colgada is None or n != colgada[1]]
        for i, n in enumerate(sorted(poner)):
            self.pendientes.append((tick + i * self.rasgueo, n))
        self.sonando = set(nuevas)
        if colgada is not None:
            vieja, destino = colgada
            self.sonando.discard(destino)
            self.sonando.add(vieja)
            # Resuelve un tiempo después (dos si los acordes duran 8 compases o más).
            self.resoluciones.append((tick + (48 if self.cambia_cada >= 8 else 24), vieja, destino))
        self.tick(tick, enviar)

    def _suspension(self, cambio, quitar, poner):
        """(nota que se queda, nota a la que resuelve) o None.

        Solo una voz que se mueve por paso (1 o 2 semitonos), en ataque ligado."""
        if not self.suspensiones or self.ataque != "ligado" or not quitar or not poner:
            return None
        if random.Random(f"suspension:{self.seed}:{cambio}").random() >= self.suspensiones:
            return None
        pares = [(abs(q - p), q, p) for q in quitar for p in poner if 1 <= abs(q - p) <= 2 and q not in poner]
        if not pares:
            return None
        _, q, p = min(pares)
        return q, p

    def _resolver(self, tick, enviar, todas=False):
        listas = [r for r in self.resoluciones if todas or r[0] <= tick]
        if not listas:
            return
        self.resoluciones = [r for r in self.resoluciones if r not in listas]
        for _, vieja, destino in listas:
            if vieja in self.sonando:
                enviar(self.salida, "note_off", self.canal, vieja, 0)
                self.sonando.discard(vieja)
            if destino not in self.sonando:
                enviar(self.salida, "note_on", self.canal, destino, self.velocidad)
                self.sonando.add(destino)

    # --- Pulso euclidiano ---

    def golpes_del_compas(self, compas):
        """{paso del compás: retraso en pulsos} de los golpes del pulso.

        Los golpes caen en corcheas, el primero en el uno. Con desplazamiento,
        algunos (nunca el del uno) se corren una semicorchea, y las semicorcheas
        débiles se atrasan un pulso (swing) o se humanizan."""
        rng = random.Random(f"pulso:{self.seed}:{compas}")
        d = self.desplazamiento
        pasos = [i * 2 for i in euclides(self.pulso, 8)]
        golpes = {}
        for k, p in enumerate(pasos):
            siguiente = pasos[k + 1] if k + 1 < len(pasos) else PASOS_POR_COMPAS
            if k > 0 and rng.random() < d and p + 1 < siguiente:
                p += 1
            retraso = (1 if p % 2 == 1 and d >= 0.5 else 0) + (1 if rng.random() < d * 0.3 else 0)
            golpes[p] = retraso
        return golpes

    def _programar_pulso(self, paso, tick):
        """Programa el golpe de este paso (si llegó a tiempo) y el del siguiente."""
        self.programados = {p for p in self.programados if p >= paso}
        for p in (paso, paso + 1):
            if p in self.programados or not self.acorde_pulso:
                continue
            golpes = self.golpes_del_compas(p // PASOS_POR_COMPAS)
            lugar = p % PASOS_POR_COMPAS
            if lugar not in golpes:
                continue
            self.programados.add(p)
            orden = sorted(golpes)
            sigue = next((g for g in orden if g > lugar), PASOS_POR_COMPAS)
            inicio = max(tick, p * TICKS_POR_PASO + golpes[lugar])
            # Dura hasta antes del golpe siguiente (como mucho una negra), sin pisarlo.
            dur = min((sigue - lugar) * TICKS_POR_PASO * 0.85, 4 * TICKS_POR_PASO)
            dur = max(2, round(min(dur, (sigue - lugar) * TICKS_POR_PASO - golpes[lugar] - 1)))
            for i, n in enumerate(self.acorde_pulso):
                desfase = i * min(self.rasgueo, 2)  # rasgueo corto: un golpe no es un arpegio
                self.pendientes.append((inicio + desfase, n))
                self.apagados.append((inicio + dur, n))

    # --- Tiempo ---

    def tick(self, tick, enviar):
        if self.resoluciones:
            self._resolver(tick, enviar)
        if self.apagados:
            fin = [p for p in self.apagados if p[0] <= tick]
            self.apagados = [p for p in self.apagados if p[0] > tick]
            for _, n in fin:  # primero los que terminan: un golpe nunca pisa al siguiente
                if n in self.sonando:
                    enviar(self.salida, "note_off", self.canal, n, 0)
                    self.sonando.discard(n)
        listas = [p for p in self.pendientes if p[0] <= tick]
        if not listas:
            return
        self.pendientes = [p for p in self.pendientes if p[0] > tick]
        for _, n in listas:
            if self.pulso:
                if n in self.sonando:
                    enviar(self.salida, "note_off", self.canal, n, 0)
                self.sonando.add(n)
            enviar(self.salida, "note_on", self.canal, n, self.velocidad)

    def apagar(self, enviar):
        for n in self.sonando:
            enviar(self.salida, "note_off", self.canal, n, 0)
        if self.nota_drone is not None:
            enviar(self.salida, "note_off", self.canal, self.nota_drone, 0)
        self.sonando = set()
        self.nota_drone = None
        self.pendientes = []
        self.apagados = []
        self.resoluciones = []
        self.programados = set()
        self.acorde_pulso = []
        self.clave = None
        self.raiz_acorde = None

    def descripcion(self):
        notas = self.sonando or set(self.acorde_pulso)
        if not notas:
            return None
        return " · ".join(nombre_midi(n) for n in sorted(notas))
