"""Obertura: un preludio orquestal de batalla que crece por capas y desemboca en el drop.

Sale del experimento «clásico + psy» (0.97): oscuro y pesado, nada esperanzador.

- Cuatro capas, cada una en un canal (pensado para una escena de la MC-101 armada con
  sonidos orquestales; ver docs/molde-obertura.md): cuerdas graves (chelos y contrabajos
  marcati al galope), cuernos o metales (acordes en quintas, la llamada y el tema de
  guerra), coro grave (drone «aaah» en la raíz y la quinta) y percusión de guerra
  (taiko, tambor y un golpe de toda la orquesta).
- Crece en cuatro etapas, repartidas en el largo elegido (2 a 8 frases de 8 compases):
  1. coro en drone y golpes de taiko sueltos; 2. entra el galope y una llamada de cuerno
  solitaria; 3. cuernos en quintas, taikos y el tambor de guerra; 4. todo lleno, con el
  tema en octavas. Al final un golpe de toda la orquesta y un tiempo y medio de silencio:
  la parte siguiente (el drop) entra en el uno.
- Carácter: batalla (eólica, i – ♭VI – ♭VII – i), frigia (i – ♭II, más oscura) o
  trágica (i – iv – ♭VI – ♭VII, con tercera menor en los cuernos). Nunca resuelve en un V
  mayor. La tónica es la del tema.
- La seed elige la variante de la progresión, la figura del galope, la llamada de cuerno,
  el tema y el patrón de los taikos. Misma seed, misma obertura.
- La MC-101 no cambia de sonido por Program Change: cambia de escena (Program Change en su
  canal de control) y lo hace en el uno siguiente (como los clips del Looper, con Master
  Step Length en 16). Por eso, si hay escena «orquesta», la obertura usa un compás de
  preparación: manda el cambio en la mitad de ese compás y empieza a sonar en el uno
  siguiente (con «preparar» apagado empieza de una). La vuelta va en el silencio del
  final, después de la mitad del último compás: la escena psy entra justo con el drop.
  Los números de escena se eligen (1-128); 0 = no la cambia.
- El crescendo va en la fuerza de las notas y, si se quiere, por CC 11 (expresión).

Modo chill (0.98): la misma maquinaria para una capa orquestal tranquila. Caracteres etéreo
(dórico, i – ♭VII – IV con novena, melodía alta), lamento (eólico, i – iv – ♭VI – v, melodía
grave sola y el coro al final) y ritual (frigio casi en drone, quintas abiertas, taikos suaves
y tambor fantasma). Cuerdas en colchón cada 2 compases, coro que respira, una melodía en
frases de 4 compases (A cae en la quinta, B en la tónica) por la pista de los cuernos y
percusión suave; sin golpes, y al final se apaga (fuerza y CC 11) con un tiempo de silencio.

«repetir» (los dos modos): no termina; después de la última etapa vuelve a la etapa 2 y
sigue, y en el chill cada vuelta trae otra melodía. Si se apaga a medio camino y había
cambiado de escena, manda la escena de vuelta.

Empieza en el primer compás en que está activa (con el reloj andando) y suena una sola
vez; para repetirla hay que apagarla y volver a prenderla (o volver a lanzar su parte).
"""

import random

TICKS_POR_PASO = 6
PASOS_POR_COMPAS = 16
TICKS_POR_COMPAS = TICKS_POR_PASO * PASOS_POR_COMPAS
NEGRA = 4 * TICKS_POR_PASO
SEMI = TICKS_POR_PASO

MODOS = ("epico", "chill")
CARACTERES_MODO = {"epico": ("batalla", "frigia", "tragica"), "chill": ("etereo", "lamento", "ritual")}
CARACTERES = CARACTERES_MODO["epico"] + CARACTERES_MODO["chill"]
NOMBRES = {"batalla": "Batalla", "frigia": "Frigia", "tragica": "Trágica",
           "etereo": "Etéreo", "lamento": "Lamento", "ritual": "Ritual"}

# Acordes: raíz en semitonos desde la tónica.
RAIZ = {"i": 0, "bII": 1, "bIII": 3, "iv": 5, "IV": 5, "v": 7, "bVI": -4, "bVII": -2}
TERCERA = {"i": 3, "bII": 4, "bIII": 4, "iv": 3, "IV": 4, "v": 3, "bVI": 4, "bVII": 4}
# Dos variantes de progresión por carácter (cada acorde dura 2 compases de la frase de 8).
PLANES = {
    "batalla": (("i", "bVI", "bVII", "i"), ("i", "bVII", "bVI", "bVII")),
    "frigia": (("i", "bII", "i", "bVII"), ("i", "bII", "bVII", "bII")),
    "tragica": (("i", "iv", "bVI", "bVII"), ("i", "bVI", "iv", "bVII")),
    # Chill: dórico con el IV mayor y novena (etéreo), eólico con v menor (lamento),
    # frigio casi en drone con quintas abiertas (ritual).
    "etereo": (("i", "bVII", "IV", "i"), ("i", "bIII", "bVII", "IV")),
    "lamento": (("i", "iv", "bVI", "v"), ("i", "bVI", "iv", "v")),
    "ritual": (("i", "i", "bII", "i"), ("i", "bII", "bVII", "i")),
}
# Escalas de la melodía chill y su registro (semitonos sobre la tónica grave).
ESCALAS_CHILL = {"etereo": (0, 2, 3, 5, 7, 9, 10), "lamento": (0, 2, 3, 5, 7, 8, 10), "ritual": (0, 1, 3, 5, 7, 8, 10)}
REGISTRO_CHILL = {"etereo": 24, "lamento": 12, "ritual": 12}
# Ritmos de la melodía chill por compás ((inicio, largo) en negras): notas largas y aire.
RITMOS_CHILL = (((0, 2), (2, 2)), ((0, 3), (3, 1)), ((0, 4),), ((1, 1), (2, 2)), ((0, 1.5), (1.5, 2.5)), ((0.5, 3.5),))
TAIKOS_RITUAL = ((0, 2.5), (0, 1.5, 2.5), (0, 0.75, 2, 2.5), (0, 1, 2.5, 3.5))
# Galope de batalla (semicorcheas del compás) y su versión llena para la última etapa.
GALOPES = ((0, 3, 6, 8, 11, 14), (0, 3, 6, 10, 12, 14), (0, 2, 3, 6, 8, 10, 11, 14), (0, 3, 4, 8, 11, 12))
LLENOS = ((0, 2, 3, 5, 6, 8, 10, 11, 13, 14), (0, 1, 2, 4, 6, 8, 9, 10, 12, 14), (0, 2, 3, 4, 6, 8, 10, 11, 12, 14))
# Llamadas de cuerno: (inicio en negras, largo en negras, semitonos sobre la tónica).
LLAMADAS = (
    ((0, 1.5, 0), (1.5, 0.5, 7), (2, 2, 12), (4, 1, 10), (5, 3, 7)),
    ((0, 1, 0), (1, 1, 5), (2, 2, 7), (4, 2, 10), (6, 2, 7)),
    ((0, 2, 7), (2, 1, 5), (3, 1, 3), (4, 4, 0)),
    ((0, 1, 0), (1, 1, 0), (2, 1, 7), (3, 1, 10), (4, 4, 12)),
)
# Taikos por etapa: tiempos (en negras) del compás.
TAIKOS = (((0,),), ((0, 2), (0, 1.5, 2)), ((0, 2.5, 3), (0, 1.5, 2, 3), (0, 2, 2.5, 3.5)), ((0, 1, 2, 2.5, 3, 3.5), (0, 0.5, 1, 2, 2.5, 3)))
# Ritmos del tema (por compás: (inicio, largo) en negras); el último compás es una nota larga.
RITMOS_TEMA = (((0, 2), (2, 1), (3, 1)), ((0, 3), (3, 1)), ((0, 1.5), (1.5, 0.5), (2, 2)), ((0, 1), (1, 1), (2, 2)))
ESCALA_TEMA = (0, 2, 3, 5, 7, 8, 10)


def _f(x):
    return max(0.0, min(1.0, float(x)))


class Obertura:
    def __init__(self, cfg, tonalidad):
        self.activo = bool(cfg.get("activo", False))
        self.salida = cfg.get("salida", "MC-101")
        self.canales = {capa: int(cfg.get(f"canal_{capa}", n)) - 1
                        for capa, n in (("cuerdas", 1), ("cuernos", 2), ("coro", 3), ("percusion", 4))}  # -1 = capa apagada
        self.nota_taiko = int(cfg.get("nota_taiko", 36))
        self.nota_tambor = int(cfg.get("nota_tambor", 38))
        self.nota_golpe = int(cfg.get("nota_golpe", 49))
        self.modo = cfg.get("modo", "epico") if cfg.get("modo", "epico") in MODOS else "epico"
        propios = CARACTERES_MODO[self.modo]
        self.caracter = cfg.get("caracter") if cfg.get("caracter") in propios else propios[0]
        self.repetir = bool(cfg.get("repetir", False))   # en loop: después de la intro vuelve a la etapa 2, sin final
        self.frases = max(1, min(8, int(cfg.get("frases", 4))))
        self.velocidad = max(1, min(127, int(cfg.get("velocidad", 115))))
        self.expresion = bool(cfg.get("expresion", True))
        self.escena = max(0, min(128, int(cfg.get("escena", 0))))           # 1-128; 0 = no cambia
        self.escena_vuelta = max(0, min(128, int(cfg.get("escena_vuelta", 0))))
        self.canal_control = max(1, min(16, int(cfg.get("canal_control", 16)))) - 1
        self.preparar = bool(cfg.get("preparar", True))   # con escena: un compás para que la MC cambie
        self.seed = str(cfg.get("seed", "OB-0001"))
        self.tonalidad = tonalidad
        self.disparo = None
        self.inicio = None        # compás en que empezó
        self.terminada = False
        self.pendientes = []      # (tick, tipo, canal, a, b)
        self.sonando = {}         # (canal, nota) -> tick en que termina
        self._corte = None        # chill: tick absoluto en que todo debe estar callado

    # --- Forma ---

    @property
    def largo(self):
        return 8 * self.frases

    def _rng(self, *clave):
        return random.Random(":".join(["obertura", self.seed, *map(str, clave)]))

    def plan(self):
        """Los acordes de la frase de 8 compases (uno cada 2)."""
        variantes = PLANES[self.caracter]
        cuatro = variantes[int(self._rng("plan").random() * len(variantes))]
        return [a for a in cuatro for _ in (0, 1)]

    def tonica_grave(self):
        """La tónica del tema en el registro grave (de E1 a D#2... con cuernos y coro arriba)."""
        pc = self.tonalidad.tonica
        return 40 + (pc - 4) % 12   # E2 a D#3

    def etapa(self, c):
        """0 a 3: en qué etapa del crecimiento está el compás c."""
        return min(3, c * 4 // self.largo)

    # --- Estado ---

    def continuar_de(self, viejo, enviar):
        if viejo is None:
            return
        if viejo.salida == self.salida and viejo.canales == self.canales:
            self.inicio, self.terminada = viejo.inicio, viejo.terminada
            self.pendientes, self.sonando = viejo.pendientes, viejo.sonando
            viejo.pendientes, viejo.sonando = [], {}
        else:
            viejo.apagar(enviar)
        if not self.activo:
            # Apagada a medio camino: si había cambiado de escena, vuelve a la escena psy.
            if viejo.activo and viejo.inicio is not None and not viejo.terminada and viejo.escena and viejo.escena_vuelta:
                enviar(viejo.salida, "program_change", viejo.canal_control, viejo.escena_vuelta - 1, 0)
                self.pendientes = [p for p in self.pendientes if p[1] != "program_change"]
            # Apagada: lo que suena termina y la próxima vez empieza de nuevo.
            self.inicio, self.terminada = None, False
            self.pendientes = [p for p in self.pendientes if p[1] == "note_off"]

    def reiniciar(self):
        self.inicio, self.terminada = None, False

    # --- Tiempo ---

    def paso(self, paso, tick, enviar):
        if not self.activo or self.terminada:
            return
        compas, lugar = divmod(paso, PASOS_POR_COMPAS)
        if lugar:
            return
        if self.inicio is None:
            self.inicio = compas
            if self.escena:
                if self.preparar:
                    # En la mitad de este compás: la MC-101 cambia de escena en el uno siguiente.
                    self.inicio = compas + 1
                    self.pendientes.append((tick + TICKS_POR_COMPAS // 2, "program_change", self.canal_control,
                                            self.escena - 1, 0))
                else:
                    enviar(self.salida, "program_change", self.canal_control, self.escena - 1, 0)
        c = compas - self.inicio
        if c < 0:
            return  # compás de preparación
        ciclo = 0
        if c >= self.largo:
            if not self.repetir:
                self.terminada = True
                return
            # En loop: vuelve a la etapa 2 (sin la intro de coro solo), cada vuelta distinta.
            i1 = self._inicio_etapa(1)
            vuelta = self.largo - i1
            ciclo = 1 + (c - self.largo) // vuelta
            c = i1 + (c - self.largo) % vuelta
        if self.modo == "chill":
            self._compas_chill(c, tick, ciclo)
        else:
            self._corte = None
            self._compas(c, tick)
        self.tick(tick, enviar)

    def _nota(self, capa, inicio, largo, nota, vel):
        canal = self.canales[capa]
        if canal < 0 or not 0 <= nota <= 127:
            return
        vel = max(1, min(127, round(vel)))
        fin = inicio + max(1, round(largo))
        if self._corte is not None:
            if inicio >= self._corte:
                return
            fin = min(fin, self._corte)
        self.pendientes.append((inicio, "note_on", canal, nota, vel))
        self.pendientes.append((fin, "note_off", canal, nota, 0))

    def _compas(self, c, t0):
        """Agenda las notas del compás c (0 = el primero) desde el tick t0."""
        etapa = self.etapa(c)
        crece = (c + 1) / self.largo
        tope = self.velocidad
        v = lambda x: tope * x  # noqa: E731
        ton = self.tonica_grave()
        plan = self.plan()
        nombre = plan[c % 8]
        raiz = ton + RAIZ[nombre]
        final = c == self.largo - 1 and not self.repetir
        hasta = 2 * NEGRA if final else TICKS_POR_COMPAS   # el último compás corta en el golpe (tiempo 3)
        if self.expresion:
            for canal in set(self.canales.values()) - {-1, self.canales["percusion"]}:
                self.pendientes.append((t0, "control_change", canal, 11, round(45 + 82 * crece)))
        # Coro: drone de raíz y quinta, cada 4 compases (o lo que quede).
        if c % 4 == 0:
            largo = min(4, self.largo - c) * TICKS_POR_COMPAS - (TICKS_POR_COMPAS - 2 * NEGRA if c + 4 >= self.largo and not self.repetir else 0) - 2
            for n in (ton + 12, ton + 19):
                self._nota("coro", t0, largo, n, v(0.45 + 0.5 * crece))
        # Cuerdas graves al galope desde la etapa 2 (o el 2.º compás si la obertura es corta).
        if etapa >= 1 or (self.largo <= 8 and c >= 2):
            figuras = LLENOS if etapa == 3 else GALOPES
            figura = figuras[int(self._rng("galope", etapa).random() * len(figuras))]
            grave = raiz - 12 if raiz - 12 >= 28 else raiz
            for k in figura:
                if k * SEMI >= hasta:
                    break
                fuerte = k in (0, 6, 8, 14)
                self._nota("cuerdas", t0 + k * SEMI, SEMI - 1, grave, v((0.55 + 0.4 * crece) * (1 if fuerte else 0.7)))
                if etapa >= 2:
                    self._nota("cuerdas", t0 + k * SEMI, SEMI - 1, grave + 12, v((0.45 + 0.4 * crece) * (1 if fuerte else 0.6)))
        # Cuernos: la llamada en la etapa 2 (al empezar la etapa y a la mitad); acordes en quintas desde la 3.
        if etapa == 1 and (c - self._inicio_etapa(1)) % 4 == 0:
            llamada = LLAMADAS[int(self._rng("llamada").random() * len(LLAMADAS))]
            for ini, dur, s in llamada:
                self._nota("cuernos", t0 + round(ini * NEGRA), dur * NEGRA * 0.95, ton + 12 + s, v(0.75))
        if etapa >= 2 and c % 2 == 0 and not final:
            sumas = (0, 7, 12) + ((TERCERA[nombre],) if self.caracter == "tragica" else ())
            for s in sumas:
                self._nota("cuernos", t0, 2 * TICKS_POR_COMPAS - 4, raiz + 12 + s, v(0.6 + 0.35 * crece))
        if etapa == 3:
            self._tema(c, t0, ton, v)
        # Percusión: taikos por etapa, tambor de guerra desde la 3 (lleno en la 4).
        taikos = TAIKOS[etapa]
        patron = taikos[int(self._rng("taiko", etapa).random() * len(taikos))]
        if etapa > 0 or c % 2 == 0:
            for b in patron:
                if b * NEGRA < hasta:
                    self._nota("percusion", t0 + round(b * NEGRA), SEMI, self.nota_taiko, v(0.55 + 0.4 * crece))
        if etapa >= 2:
            pasos = range(16) if etapa == 3 else GALOPES[int(self._rng("tambor").random() * len(GALOPES))]
            for k in pasos:
                if k * SEMI < hasta:
                    self._nota("percusion", t0 + k * SEMI, SEMI - 1, self.nota_tambor, v((0.35 + 0.5 * crece) * (1 if k % 4 == 0 else 0.6)))
        # Golpe en el 1 de cada etapa y el golpe final (tiempo 3 del último compás), con todos.
        if c == self._inicio_etapa(etapa) and etapa > 0:
            self._nota("percusion", t0, SEMI, self.nota_golpe, v(0.5 + 0.45 * crece))
        if final:
            golpe = t0 + 2 * NEGRA
            self._nota("percusion", golpe, SEMI, self.nota_golpe, tope)
            self._nota("percusion", golpe, SEMI, self.nota_taiko, tope)
            for capa, notas in (("cuerdas", (raiz - 12, raiz)), ("cuernos", (ton + 12, ton + 19, ton + 24)), ("coro", (ton + 12, ton + 19))):
                for n in notas:
                    self._nota(capa, golpe, SEMI * 2, n, tope)
            if self.escena_vuelta:
                # En el silencio, pasada la mitad del compás: la escena psy entra en el uno del drop.
                self.pendientes.append((golpe + SEMI * 2 + 1, "program_change", self.canal_control, self.escena_vuelta - 1, 0))

    def _inicio_etapa(self, etapa):
        return next(c for c in range(self.largo) if self.etapa(c) == etapa) if etapa <= self.etapa(self.largo - 1) else 0

    def _tema(self, c, t0, ton, v):
        """El tema de guerra en octavas en la segunda mitad de la última etapa (4 compases
        que se repiten): una línea por la escala menor que vuelve a la tónica (a la ♭2 en
        la frigia antes de volver)."""
        mitad = self._inicio_etapa(3) + max(0, (self.largo - self._inicio_etapa(3)) // 2)
        if c < mitad or c == self.largo - 1:
            return
        k = (c - mitad) % 4
        rng = self._rng("tema")
        grados, g = [], rng.choice((0, 4))
        for _ in range(12):
            g = max(0, min(7, g + rng.choice((-2, -1, -1, 1, 1, 2))))
            grados.append(g)
        ritmos = [RITMOS_TEMA[int(rng.random() * len(RITMOS_TEMA))] for _ in range(3)] + [((0, 3.5),)]
        i = sum(len(r) for r in ritmos[:k])
        for j, (ini, dur) in enumerate(ritmos[k]):
            if k == 3:
                g = 1 if self.caracter == "frigia" else 0
                semis = 1 if g == 1 else 0
            else:
                gg = grados[(i + j) % len(grados)]
                semis = ESCALA_TEMA[gg % 7] + 12 * (gg // 7)
            for o in (24, 36):
                self._nota("cuernos", t0 + round(ini * NEGRA), dur * NEGRA * 0.95, ton + semis + o, v(0.9))


    # --- Chill ---

    def _compas_chill(self, c, t0, ciclo):
        """Chill: colchón de cuerdas, coro que respira, una melodía larga en la pista de los
        cuernos (flauta, chelo o piano en la escena chill) y percusión suave. Crece por las
        mismas cuatro etapas pero sin golpes; al final se apaga (CC 11 y fuerza) y deja un
        tiempo de silencio antes de la parte siguiente."""
        etapa = self.etapa(c)
        crece = (c + 1) / self.largo
        final = c == self.largo - 1 and not self.repetir
        hasta = 3 * NEGRA if final else TICKS_POR_COMPAS
        self._corte = None if self.repetir else t0 + (self.largo - 1 - c) * TICKS_POR_COMPAS + 3 * NEGRA
        v = lambda x: self.velocidad * x  # noqa: E731
        ton = self.tonica_grave()
        car = self.caracter
        nombre = self.plan()[c % 8]
        r = RAIZ[nombre]
        i1 = self._inicio_etapa(1)
        if self.expresion:
            nivel = lambda k: 40 + 70 * min(1.0, (k + 1) / self.largo * 4 / 3)  # noqa: E731
            cola = not self.repetir and c >= self.largo - 2
            for b in range(4 if cola else 1):
                if cola:
                    paso_fade = (c - (self.largo - 2)) * 4 + b
                    val = nivel(self.largo - 3) * (1 - (paso_fade + 1) / 9)
                else:
                    val = nivel(c)
                for canal in set(self.canales.values()) - {-1, self.canales["percusion"]}:
                    self.pendientes.append((t0 + b * NEGRA, "control_change", canal, 11, max(0, min(127, round(val)))))
        dos = 2 * TICKS_POR_COMPAS - 3
        # Cuerdas: el acorde cada 2 compases (quintas abiertas en el ritual, novena en el etéreo).
        if c % 2 == 0:
            raiz = ton + 12 + r
            if raiz > ton + 18:
                raiz -= 12
            notas = [raiz, raiz + 7] if car == "ritual" else [raiz, raiz + TERCERA[nombre], raiz + 7]
            if car == "etereo":
                notas.append(raiz + 14)
            if etapa >= 2:
                notas.append(raiz - 12)
            for n in notas:
                self._nota("cuerdas", t0, dos, n, v(0.3 + 0.35 * crece))
        # Coro: raíz y quinta (y la octava en el etéreo lleno), desde el comienzo salvo en el
        # lamento, que lo deja para la etapa 3.
        if c % 2 == 0 and (car != "lamento" or etapa >= 2):
            notas = [ton + 12, ton + 19] + ([ton + 24] if car == "etereo" and etapa >= 2 else [])
            for n in notas:
                self._nota("coro", t0, dos, n, v(0.3 + 0.4 * crece))
        # Melodía en frases de 4 compases desde la etapa 2: A termina en la quinta, B en la tónica.
        if etapa >= 1:
            frase, k = divmod(c - i1, 4)
            self._melodia(t0, k, frase % 2, (ciclo, frase), ton + REGISTRO_CHILL[car], v(0.5 + 0.35 * crece))
        # Percusión suave.
        golpes = []
        if car == "ritual":
            if etapa == 0:
                golpes = [(0, self.nota_taiko, 0.3)] if c % 2 == 0 else []
            else:
                patron = TAIKOS_RITUAL[int(self._rng("ritual", etapa, ciclo).random() * len(TAIKOS_RITUAL))]
                golpes = [(b, self.nota_taiko, 0.4 + 0.35 * crece) for b in patron]
                if etapa >= 2:
                    fantasma = (0.5, 1.5, 2.5, 3.5) if self._rng("fantasma").random() < 0.5 else (0.75, 1.75, 2.75, 3.75)
                    golpes += [(b, self.nota_tambor, 0.25 + 0.2 * crece) for b in fantasma]
        elif car == "etereo":
            if etapa >= 1 and (c - i1) % 8 == 0:
                golpes.append((0, self.nota_golpe, 0.4))
            if etapa >= 2 and c % 2 == 0:
                golpes.append((0, self.nota_taiko, 0.35 + 0.2 * crece))
        else:
            if etapa == 3 and c % 2 == 0:
                golpes.append((0, self.nota_taiko, 0.4 + 0.2 * crece))
            if c == self._inicio_etapa(3) and etapa == 3:
                golpes.append((0, self.nota_golpe, 0.45))
        for b, nota, f in golpes:
            if b * NEGRA < hasta:
                self._nota("percusion", t0 + round(b * NEGRA), SEMI, nota, v(f))
        if final and self.escena_vuelta:
            self.pendientes.append((t0 + hasta + 1, "program_change", self.canal_control, self.escena_vuelta - 1, 0))

    def _melodia(self, t0, k, cual, clave, base, vel):
        """El compás k (0-3) de la frase A (cual 0, cae en la quinta) o B (1, cae en la tónica)."""
        escala = ESCALAS_CHILL[self.caracter]
        rng = self._rng("melodia", self.caracter, cual, *clave) if clave[0] else self._rng("melodia", self.caracter, cual, clave[1] // 2)
        ritmos = [RITMOS_CHILL[int(rng.random() * len(RITMOS_CHILL))] for _ in range(3)] + [((0, 4),)]
        g = rng.choice((0, 2, 4))
        grados = []
        for _ in range(sum(len(x) for x in ritmos)):
            g = max(0, min(9, g + rng.choice((-2, -1, -1, 0, 1, 1, 2))))
            grados.append(g)
        fin = 4 if cual == 0 else (7 if grados[-2] >= 4 else 0)
        grados[-1] = fin
        i = sum(len(x) for x in ritmos[:k])
        for j, (ini, dur) in enumerate(ritmos[k]):
            gg = grados[i + j]
            semis = escala[gg % 7] + 12 * (gg // 7)
            self._nota("cuernos", t0 + round(ini * NEGRA), dur * NEGRA - 3, base + semis, vel * (1 if j == 0 else 0.85))

    def tick(self, tick, enviar):
        if not self.pendientes:
            return
        listos = sorted((p for p in self.pendientes if p[0] <= tick), key=lambda p: (p[0], p[1] != "note_off"))
        if not listos:
            return
        self.pendientes = [p for p in self.pendientes if p[0] > tick]
        for _, tipo, canal, a, b in listos:
            if tipo == "note_on":
                if (canal, a) in self.sonando:
                    enviar(self.salida, "note_off", canal, a, 0)
                self.sonando[(canal, a)] = True
            elif tipo == "note_off":
                if (canal, a) not in self.sonando:
                    continue
                del self.sonando[(canal, a)]
            enviar(self.salida, tipo, canal, a, b)

    def apagar(self, enviar):
        for canal, nota in list(self.sonando):
            enviar(self.salida, "note_off", canal, nota, 0)
        self.sonando = {}
        self.pendientes = [p for p in self.pendientes if p[1] == "program_change"]
