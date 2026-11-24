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

Modo cine (0.99): sintes al estilo de Vangelis, con melodías propias. Brass de ataque lento
con acordes de color (novena, séptima mayor, sus2), lead con pitch bend (entra un semitono
abajo y sube; en el neón cae un tono al final de la frase; siempre vuelve al centro), pulso
de octavas (títulos) o arpegio (neón, cosmos) en la pista 3 y timbal, caja con reverb y gong.

Forma (los tres modos): crece, golpe, ola (falso final a la mitad) o respiro: la etapa de
cada octavo del largo. Tema del track: la llamada, el tema y la melodía siguen las primeras
alturas de la 1.ª secuencia activa (tomadas al empezar).

Empieza en el primer compás en que está activa (con el reloj andando) y suena una sola
vez; para repetirla hay que apagarla y volver a prenderla (o volver a lanzar su parte).
"""

import math
import random

TICKS_POR_PASO = 6
PASOS_POR_COMPAS = 16
TICKS_POR_COMPAS = TICKS_POR_PASO * PASOS_POR_COMPAS
NEGRA = 4 * TICKS_POR_PASO
SEMI = TICKS_POR_PASO

MODOS = ("epico", "chill", "cine")
# Formas: la etapa (0 a 3) de cada octavo del largo.
FORMAS = {
    "crece": (0, 0, 1, 1, 2, 2, 3, 3),     # crece de a poco hasta el final
    "golpe": (3, 1, 1, 2, 2, 3, 3, 3),     # entra con todo, baja y vuelve a crecer
    "ola": (0, 1, 2, 3, 0, 1, 3, 3),       # crece, falso final a la mitad, y vuelve más fuerte
    "respiro": (0, 1, 1, 2, 0, 2, 3, 3),   # crece, se vacía (solo coro) y remata
}
CARACTERES_MODO = {"epico": ("batalla", "frigia", "tragica"), "chill": ("etereo", "lamento", "ritual"),
                   "cine": ("neon", "titulos", "cosmos")}
CARACTERES = CARACTERES_MODO["epico"] + CARACTERES_MODO["chill"] + CARACTERES_MODO["cine"]
NOMBRES = {"batalla": "Batalla", "frigia": "Frigia", "tragica": "Trágica",
           "etereo": "Etéreo", "lamento": "Lamento", "ritual": "Ritual",
           "neon": "Neón", "titulos": "Títulos", "cosmos": "Cosmos"}

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
# Cine (al estilo de los sintes de Vangelis, melodías propias): acordes con color (novena,
# séptima mayor, sus2), lead con bends y pulso o arpegio en la pista 3.
PLANES_CINE = {
    "neon": (("i", "bVI", "bIII", "bVII"), ("i", "bVII", "bVI", "iv")),
    "titulos": (("i", "bVI", "bVII", "i"), ("i", "bIII", "bVII", "bVI")),
    "cosmos": (("i", "bIII", "bVII", "IV"), ("i", "bVI", "bVII", "IV")),
}
COLOR_CINE = {"i": (0, 3, 7, 14), "bII": (0, 4, 7, 11), "bIII": (0, 4, 7, 14), "iv": (0, 3, 7, 10),
              "IV": (0, 4, 7, 14), "v": (0, 3, 7, 10), "bVI": (0, 4, 7, 11), "bVII": (0, 2, 7, 12)}
ESCALAS_CINE = {"neon": (0, 2, 3, 5, 7, 8, 10), "titulos": (0, 2, 3, 5, 7, 8, 10), "cosmos": (0, 2, 3, 5, 7, 9, 10)}
RITMOS_CINE = (((0, 4),), ((0, 3), (3, 1)), ((0, 1.5), (1.5, 2.5)), ((0, 2), (2, 2)), ((0.5, 3.5),), ((0, 2.5), (2.5, 1.5)))
ARPEGIOS = ((0, 1, 2, 3, 2, 1, 2, 3), (0, 2, 1, 3, 0, 2, 1, 3), (0, 1, 2, 3, 3, 2, 1, 0), (3, 2, 1, 0, 1, 2, 3, 2))
PULSOS = ((0, 12) * 8, (0, 0, 12, 0) * 4, (0, 12, 0, 0) * 4)
CAPAS = ("cuerdas", "cuernos", "coro", "percusion")
# Qué capa usa cada sorteo (para la seed propia de cada instrumento).
CAPA_DE_CLAVE = {"galope": "cuerdas", "llamada": "cuernos", "tema": "cuernos", "melodia": "cuernos", "bend": "cuernos",
                 "arpegio": "coro", "pulso": "coro", "taiko": "percusion", "tambor": "percusion",
                 "ritual": "percusion", "fantasma": "percusion", "fantasmas": "percusion", "densidad": "cuernos"}
# Secciones de la forma larga: A (la progresión de la seed), B (la otra progresión del
# carácter), C (la de A un tono arriba: el clímax). En loop, cada vuelta es una sección.
PATRONES_SECCION = ("AABA", "ABAB", "AABC", "ABAC", "ABCA")
TRANSPORTE_SECCION = {"A": 0, "B": 0, "C": 2}
FONDO = {"epico": "coro", "chill": "cuerdas", "cine": "cuerdas"}   # la capa que la orquestación viva casi nunca saca
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
        self.forma = cfg.get("forma", "crece") if cfg.get("forma", "crece") in FORMAS else "crece"
        self.tema_track = bool(cfg.get("tema_track", False))   # el tema sale de la 1.ª secuencia
        self.bend_rango = max(0, min(24, int(cfg.get("bend_rango", 2))))   # semitonos del bend del lead (cine)
        self.motivo = None        # semitonos sobre la tónica, tomados del patrón al empezar
        self.repetir = bool(cfg.get("repetir", False))   # en loop: después de la intro vuelve a la etapa 2, sin final
        # Forma larga (0.100)
        self.largo_parte = bool(cfg.get("largo_parte", False))   # en canción: el arco dura lo que su parte
        self.secciones = bool(cfg.get("secciones", True))       # más de 32 compases (o en loop): secciones A/B/C
        self.viva = _f(cfg.get("viva", 0.0))                     # orquestación viva: capas que entran y salen
        # Respiración por CC (relativo en la MC-101: 64 = sin cambio)
        self.respira_cc = max(0, min(119, int(cfg.get("respira_cc", 0))))
        self.respira_compases = max(2, min(64, int(cfg.get("respira_compases", 16))))
        self.respira_rango = _f(cfg.get("respira_rango", 0.4))
        # Por instrumento
        self.seeds = {k: str(cfg.get(f"seed_{k}", "") or "").strip() for k in CAPAS}
        self.niveles = {k: max(0.0, min(1.5, float(cfg.get(f"nivel_{k}", 1.0)))) for k in CAPAS}
        self.octavas = {k: max(-2, min(2, int(cfg.get(f"octava_{k}", 0)))) for k in CAPAS if k != "percusion"}
        self.densidades = {k: _f(cfg.get(f"densidad_{k}", 0.5)) for k in CAPAS}
        self.legatos = {k: max(0.2, min(1.5, float(cfg.get(f"legato_{k}", 1.0)))) for k in CAPAS}
        # Acordes del colchón o brass (chill y cine)
        self.voces = max(0, min(5, int(cfg.get("voces", 0))))   # 0 = las del carácter
        self.abierto = bool(cfg.get("abierto", False))
        self.inversion = max(0, min(2, int(cfg.get("inversion", 0))))
        self.pedal = bool(cfg.get("pedal", False))
        # Feel
        self.swing = max(0.0, min(0.5, float(cfg.get("swing", 0.0))))
        self.humanizar = _f(cfg.get("humanizar", 0.0))
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
        self._corte = None        # chill y cine: tick absoluto en que todo debe estar callado
        self._largo = None        # con largo_parte: el de la parte (si no, 8 × frases)
        self._seccion = "A"
        self._transp = 0
        self._mudas = frozenset()
        self._t0 = 0              # tick del compás que se está agendando
        self._escena_enviada = None
        self._bend_usado = False

    # --- Forma ---

    @property
    def largo(self):
        return self._largo or 8 * self.frases

    def _rng(self, *clave):
        seed = self.seeds.get(CAPA_DE_CLAVE.get(str(clave[0]) if clave else ""), "") or self.seed
        return random.Random(":".join(["obertura", seed, *map(str, clave)]))

    def plan(self, seccion="A"):
        """Los acordes de la frase de 8 compases (uno cada 2). La sección B usa la otra
        progresión del carácter."""
        variantes = PLANES_CINE[self.caracter] if self.modo == "cine" else PLANES[self.caracter]
        i = int(self._rng("plan").random() * len(variantes))
        if seccion == "B":
            i = (i + 1) % len(variantes)
        cuatro = variantes[i]
        return [a for a in cuatro for _ in (0, 1)]

    def tonica_grave(self):
        """La tónica del tema en el registro grave (de E1 a D#2... con cuernos y coro arriba)."""
        pc = self.tonalidad.tonica
        return 40 + (pc - 4) % 12   # E2 a D#3

    def etapa(self, c):
        """0 a 3: en qué etapa está el compás c, según la forma (8 tramos iguales)."""
        return FORMAS[self.forma][min(7, c * 8 // self.largo)]

    def inicio_tramo(self, c):
        """El primer compás del tramo (compases seguidos en la misma etapa) en que está c."""
        e = self.etapa(c)
        while c > 0 and self.etapa(c - 1) == e:
            c -= 1
        return c

    def fin_tramo(self, c):
        e = self.etapa(c)
        while c < self.largo and self.etapa(c) == e:
            c += 1
        return c

    def falso_final(self, c):
        """Forma «ola»: el compás antes de que todo caiga (de la etapa 3 a la 0 o 1)."""
        return c + 1 < self.largo and self.etapa(c + 1) <= self.etapa(c) - 2

    def crece(self, c):
        """0-1: cuánto empuja el compás c (fuerza de las notas, CC 11)."""
        if self.forma == "crece":
            return (c + 1) / self.largo
        return min(1.0, (self.etapa(c) + 1) / 4 * (0.8 + 0.2 * (c + 1) / self.largo))

    # --- Estado ---

    def continuar_de(self, viejo, enviar):
        if viejo is None:
            return
        if viejo.salida == self.salida and viejo.canales == self.canales:
            self.inicio, self.terminada = viejo.inicio, viejo.terminada
            if self.tema_track == viejo.tema_track:
                self.motivo = viejo.motivo
            self._bend_usado = viejo._bend_usado
            self._escena_enviada = viejo._escena_enviada
            self._prep = getattr(viejo, "_prep", 0)
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

    def paso(self, paso, tick, enviar, patron=None, parte=None):
        """Agenda un compás en su uno. `parte` (en canción): {"dentro", "largo", "vuelta"} de
        la parte que suena; con largo_parte la obertura sigue esa parte."""
        if not self.activo:
            return
        compas, lugar = divmod(paso, PASOS_POR_COMPAS)
        if lugar:
            return
        if self.largo_parte and parte is not None:
            self._paso_parte(compas, tick, enviar, patron, parte)
            return
        if self.terminada:
            return
        self._largo = None
        if self.inicio is None:
            self.inicio = compas
            self.motivo = self.motivo_de(patron) if self.tema_track else None
            if self.escena:
                if self.preparar:
                    # En la mitad de este compás: la MC-101 cambia de escena en el uno siguiente.
                    self.inicio = compas + 1
                    self.pendientes.append((tick + TICKS_POR_COMPAS // 2, "program_change", self.canal_control,
                                            self.escena - 1, 0))
                else:
                    enviar(self.salida, "program_change", self.canal_control, self.escena - 1, 0)
                self._escena_enviada = self.escena
        c = compas - self.inicio
        if c < 0:
            return  # compás de preparación
        ciclo = 0
        if c >= self.largo:
            if not self.repetir:
                self.terminada = True
                self._soltar_respiracion(enviar)
                return
            # En loop: vuelve a la etapa 2 (sin la intro de coro solo), cada vuelta distinta.
            i1 = self._inicio_etapa(1)
            vuelta = self.largo - i1
            ciclo = 1 + (c - self.largo) // vuelta
            c = i1 + (c - self.largo) % vuelta
        self._agendar(c, tick, ciclo, compas)
        self.tick(tick, enviar)

    def _paso_parte(self, compas, tick, enviar, patron, parte):
        """Largo de la parte: el compás de la obertura es el de la parte (cada parte es un arco)."""
        dentro, largo = int(parte["dentro"]), int(parte["largo"])
        cambia = self.escena and self.escena != self._escena_enviada
        prep = 1 if cambia and self.preparar and largo > 1 else 0
        if dentro == 0 or self.inicio is None:
            self.terminada = False
            self.motivo = self.motivo_de(patron) if self.tema_track else None
            if cambia:
                if prep and dentro == 0:
                    self.pendientes.append((tick + TICKS_POR_COMPAS // 2, "program_change", self.canal_control, self.escena - 1, 0))
                else:
                    prep = 0
                    enviar(self.salida, "program_change", self.canal_control, self.escena - 1, 0)
                self._escena_enviada = self.escena
            self._prep = prep
        prep = getattr(self, "_prep", 0)
        self._largo = max(1, largo - prep)
        c = dentro - prep
        self.inicio = compas - c
        if c < 0 or c >= self._largo:
            return
        self._agendar(c, tick, int(parte.get("vuelta", 0) or 0), compas, en_parte=True)
        self.tick(tick, enviar)

    def _agendar(self, c, tick, ciclo, compas, en_parte=False):
        """Prepara el compás (sección, transporte, capas que callan) y lo agenda."""
        self._t0 = tick
        self._seccion = self.seccion(c, 0 if en_parte else ciclo)
        self._transp = TRANSPORTE_SECCION[self._seccion]
        self._mudas = self._mudas_de(c, ciclo)
        if self.modo == "chill":
            self._compas_chill(c, tick, ciclo)
        elif self.modo == "cine":
            self._compas_cine(c, tick, ciclo)
        else:
            self._corte = None
            self._compas(c, tick)
        self._fantasmas(c, tick)
        self._respirar(compas, tick)

    # --- Forma larga ---

    def seccion(self, c, ciclo=0):
        """La sección (A, B o C) del compás c; en loop, la de la vuelta."""
        if not self.secciones:
            return "A"
        patron = PATRONES_SECCION[int(self._rng("secciones").random() * len(PATRONES_SECCION))]
        if ciclo:
            return patron[ciclo % len(patron)]
        if self.largo <= 32:
            return "A"
        n = max(2, self.largo // 16)
        letras = (patron * n)[:n]
        if n >= 3:
            letras = letras[:-1] + "A"   # termina en casa
        return letras[min(n - 1, c // 16)]

    def _mudas_de(self, c, ciclo):
        """Orquestación viva: las capas que callan en este tramo de 16 compases."""
        if not self.viva or self.etapa(c) == 0:
            return frozenset()
        ventana = c // 16 + 1000 * ciclo
        if ventana == 0 or (not self.repetir and c >= self.largo - 8):
            return frozenset()   # el comienzo y el cierre van completos
        rng = self._rng("viva", ventana)
        fondo = FONDO[self.modo]
        fuera = {k for k in CAPAS if rng.random() < self.viva * (0.2 if k == fondo else 0.6)}
        activas = [k for k in CAPAS if self.canales[k] >= 0]
        if len([k for k in activas if k not in fuera]) < 2:
            fuera -= {fondo, "cuernos"}
        return frozenset(fuera)

    def _fantasmas(self, c, t0):
        """Densidad alta de la percusión: golpes suaves de tambor en las corcheas a contratiempo."""
        d = self.densidades["percusion"]
        if d <= 0.5 or self.etapa(c) == 0 or (c == self.largo - 1 and not self.repetir):
            return
        rng = self._rng("fantasmas", c, self._t0)
        for pos in (12, 36, 60, 84):
            if rng.random() < (d - 0.5) * 2:
                self._nota("percusion", t0 + pos, SEMI, self.nota_tambor, self.velocidad * (0.2 + 0.15 * self.crece(c)))

    # --- Respiración ---

    def _respirar(self, compas, t0):
        if not self.respira_cc:
            return
        for k, capa in enumerate(("cuerdas", "cuernos", "coro")):
            canal = self.canales[capa]
            if canal < 0:
                continue
            for b in range(4):
                fase = 2 * math.pi * ((compas + b / 4) / self.respira_compases + k / 3)
                val = 64 + self.respira_rango * 63 * math.sin(fase)
                self.pendientes.append((t0 + b * NEGRA, "control_change", canal, self.respira_cc, max(0, min(127, round(val)))))

    def _soltar_respiracion(self, enviar):
        if not self.respira_cc:
            return
        for capa in ("cuerdas", "cuernos", "coro"):
            if self.canales[capa] >= 0:
                enviar(self.salida, "control_change", self.canales[capa], self.respira_cc, 64)

    def _nota(self, capa, inicio, largo, nota, vel):
        canal = self.canales[capa]
        if canal < 0 or capa in self._mudas:
            return
        pos = (inicio - self._t0) % TICKS_POR_COMPAS
        if capa == "percusion":
            d = self.densidades["percusion"]
            if d < 0.5 and pos % NEGRA and nota != self.nota_golpe and \
                    random.Random(f"{self.seed}:dp:{inicio}:{nota}").random() < (0.5 - d) * 2:
                return
        else:
            nota += 12 * self.octavas[capa] + self._transp
        if not 0 <= nota <= 127:
            return
        if self.swing:
            if pos % NEGRA == 12:
                inicio += round(self.swing * 8)
            elif pos % 12 == 6:
                inicio += round(self.swing * 4)
        if self.humanizar:
            h = random.Random(f"{self.seed}:h:{inicio}:{nota}:{canal}")
            inicio += h.randint(0, round(2 * self.humanizar))
            vel += h.uniform(-1, 1) * 15 * self.humanizar
        vel = max(1, min(127, round(vel * self.niveles[capa])))
        largo = largo * self.legatos[capa]
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
        crece = self.crece(c)
        tope = self.velocidad
        v = lambda x: tope * x  # noqa: E731
        ton = self.tonica_grave()
        plan = self.plan(self._seccion)
        nombre = plan[c % 8]
        raiz = ton + RAIZ[nombre]
        final = c == self.largo - 1 and not self.repetir
        falso = self.falso_final(c)
        hasta = 2 * NEGRA if final or falso else TICKS_POR_COMPAS   # el último compás corta en el golpe (tiempo 3)
        if self.expresion:
            for canal in set(self.canales.values()) - {-1, self.canales["percusion"]}:
                self.pendientes.append((t0, "control_change", canal, 11, round(45 + 82 * crece)))
        # Coro: drone de raíz y quinta, cada 4 compases (o lo que quede).
        if c % 4 == 0:
            largo = min(4, self.largo - c) * TICKS_POR_COMPAS - (TICKS_POR_COMPAS - 2 * NEGRA if c + 4 >= self.largo and not self.repetir else 0) - 2
            for n in self._coro_notas((ton + 12, ton + 19), ton):
                self._nota("coro", t0, largo, n, v(0.45 + 0.5 * crece))
        # Cuerdas graves al galope desde la etapa 2 (o el 2.º compás si la obertura es corta).
        if etapa >= 1 or (self.largo <= 8 and c >= 2):
            d = self.densidades["cuerdas"]
            figuras = LLENOS if etapa == 3 or (d > 0.66 and etapa >= 1) else GALOPES
            figura = figuras[int(self._rng("galope", etapa).random() * len(figuras))]
            if d < 0.34:
                figura = [k for k in figura if k in (0, 6, 8, 14)] or [0]
            grave = raiz - 12 if raiz - 12 >= 28 else raiz
            for k in figura:
                if k * SEMI >= hasta:
                    break
                fuerte = k in (0, 6, 8, 14)
                self._nota("cuerdas", t0 + k * SEMI, SEMI - 1, grave, v((0.55 + 0.4 * crece) * (1 if fuerte else 0.7)))
                if etapa >= 2:
                    self._nota("cuerdas", t0 + k * SEMI, SEMI - 1, grave + 12, v((0.45 + 0.4 * crece) * (1 if fuerte else 0.6)))
        # Cuernos: la llamada en la etapa 2 (al empezar la etapa y a la mitad); acordes en quintas desde la 3.
        if etapa == 1 and (c - self.inicio_tramo(c)) % 4 == 0:
            llamada = LLAMADAS[int(self._rng("llamada").random() * len(LLAMADAS))]
            for j, (ini, dur, s) in enumerate(llamada):
                if self.motivo:
                    s = self.motivo[j % len(self.motivo)]
                self._nota("cuernos", t0 + round(ini * NEGRA), dur * NEGRA * 0.95, ton + 12 + s, v(0.75))
        if etapa >= 2 and c % 2 == 0 and not (final or falso):
            sumas = (0, 7, 12) + ((TERCERA[nombre],) if self.caracter == "tragica" else ())
            dura = 2 * TICKS_POR_COMPAS - 4 if not self.falso_final(c + 1) else TICKS_POR_COMPAS + 2 * NEGRA - 4
            for s in sumas:
                self._nota("cuernos", t0, dura, raiz + 12 + s, v(0.6 + 0.35 * crece))
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
        if c == self.inicio_tramo(c) and etapa > 0:
            self._nota("percusion", t0, SEMI, self.nota_golpe, v(0.5 + 0.45 * crece))
        if final or falso:
            golpe = t0 + 2 * NEGRA
            self._nota("percusion", golpe, SEMI, self.nota_golpe, tope)
            self._nota("percusion", golpe, SEMI, self.nota_taiko, tope)
            for capa, notas in (("cuerdas", (raiz - 12, raiz)), ("cuernos", (ton + 12, ton + 19, ton + 24)), ("coro", (ton + 12, ton + 19))):
                for n in notas:
                    self._nota(capa, golpe, SEMI * 2, n, tope)
            if final and self.escena_vuelta:
                # En el silencio, pasada la mitad del compás: la escena psy entra en el uno del drop.
                self.pendientes.append((golpe + SEMI * 2 + 1, "program_change", self.canal_control, self.escena_vuelta - 1, 0))

    def _inicio_etapa(self, etapa):
        """El primer compás que llega a esa etapa (0 si nunca llega)."""
        return next((c for c in range(self.largo) if self.etapa(c) >= etapa), 0)

    def _tema(self, c, t0, ton, v):
        """El tema de guerra en octavas en la segunda mitad de la última etapa (4 compases
        que se repiten): una línea por la escala menor que vuelve a la tónica (a la ♭2 en
        la frigia antes de volver)."""
        ini = self.inicio_tramo(c)
        mitad = ini + max(0, (self.fin_tramo(c) - ini) // 2)
        if c < mitad or c == self.largo - 1 or self.falso_final(c):
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
                if self.motivo:
                    semis = self.motivo[(i + j) % len(self.motivo)]
            for o in (24, 36):
                self._nota("cuernos", t0 + round(ini * NEGRA), dur * NEGRA * 0.95, ton + semis + o, v(0.9))


    # --- Chill ---

    def _compas_chill(self, c, t0, ciclo):
        """Chill: colchón de cuerdas, coro que respira, una melodía larga en la pista de los
        cuernos (flauta, chelo o piano en la escena chill) y percusión suave. Crece por las
        mismas cuatro etapas pero sin golpes; al final se apaga (CC 11 y fuerza) y deja un
        tiempo de silencio antes de la parte siguiente."""
        etapa = self.etapa(c)
        crece = self.crece(c)
        final = c == self.largo - 1 and not self.repetir
        hasta = 3 * NEGRA if final else TICKS_POR_COMPAS
        self._corte = None if self.repetir else t0 + (self.largo - 1 - c) * TICKS_POR_COMPAS + 3 * NEGRA
        v = lambda x: self.velocidad * x  # noqa: E731
        ton = self.tonica_grave()
        car = self.caracter
        nombre = self.plan(self._seccion)[c % 8]
        r = RAIZ[nombre]
        i1 = self._inicio_etapa(1)
        if self.expresion:
            nivel = lambda k: 40 + 70 * min(1.0, self.crece(k) * 4 / 3)  # noqa: E731
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
        cada = self._cada_acorde()
        if c % cada == 0:
            raiz = ton + 12 + r
            if raiz > ton + 18:
                raiz -= 12
            acorde = [raiz, raiz + 7] if car == "ritual" else [raiz, raiz + TERCERA[nombre], raiz + 7]
            if car == "etereo":
                acorde.append(raiz + 14)
            notas = self._voicing(acorde, ton) + ([raiz - 12] if etapa >= 2 else [])
            for n in notas:
                self._nota("cuerdas", t0, cada * TICKS_POR_COMPAS - 3, n, v(0.3 + 0.35 * crece))
        # Coro: raíz y quinta (y la octava en el etéreo lleno), desde el comienzo salvo en el
        # lamento, que lo deja para la etapa 3.
        if c % 2 == 0 and (car != "lamento" or etapa >= 2):
            notas = self._coro_notas([ton + 12, ton + 19] + ([ton + 24] if car == "etereo" and etapa >= 2 else []), ton)
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
            if c == self.inicio_tramo(c) and etapa == 3:
                golpes.append((0, self.nota_golpe, 0.45))
        for b, nota, f in golpes:
            if b * NEGRA < hasta:
                self._nota("percusion", t0 + round(b * NEGRA), SEMI, nota, v(f))
        if final and self.escena_vuelta:
            self.pendientes.append((t0 + hasta + 1, "program_change", self.canal_control, self.escena_vuelta - 1, 0))

    # --- Cine ---

    def _compas_cine(self, c, t0, ciclo):
        """Cine (al estilo de Vangelis): pista 1 un brass de sinte que se abre lento con
        acordes de color, pista 2 un lead con bends (entra deslizándose y cae al final de
        la frase), pista 3 el arpegio o el pulso, pista 4 timbal, caja con mucha reverb y
        gong. Neón: lento y lluvioso, arpegio en corcheas. Títulos: pulso de octavas en
        semicorcheas y fanfarria. Cosmos: campanas, lead en octavas y redobles de timbal."""
        etapa = self.etapa(c)
        crece = self.crece(c)
        final = c == self.largo - 1 and not self.repetir
        hasta = 3 * NEGRA if final else TICKS_POR_COMPAS
        self._corte = None if self.repetir else t0 + (self.largo - 1 - c) * TICKS_POR_COMPAS + 3 * NEGRA
        v = lambda x: self.velocidad * x  # noqa: E731
        ton = self.tonica_grave()
        car = self.caracter
        nombre = self.plan(self._seccion)[c % 8]
        r = RAIZ[nombre]
        color = COLOR_CINE[nombre]
        i1 = self._inicio_etapa(1)
        if self.expresion:
            cola = not self.repetir and c >= self.largo - 2 and car != "titulos"
            for b in range(4 if cola else 1):
                if cola:
                    val = (40 + 70 * min(1.0, self.crece(self.largo - 3) * 4 / 3)) * (1 - ((c - (self.largo - 2)) * 4 + b + 1) / 9)
                else:
                    val = 40 + 70 * min(1.0, crece * 4 / 3)
                for canal in set(self.canales.values()) - {-1, self.canales["percusion"]}:
                    self.pendientes.append((t0 + b * NEGRA, "control_change", canal, 11, max(0, min(127, round(val)))))
        raiz = ton + 12 + r
        if raiz > ton + 18:
            raiz -= 12
        # Pista 1: el brass, un acorde cada 2 compases (la octava grave desde la etapa 3).
        cada = self._cada_acorde()
        if c % cada == 0:
            notas = self._voicing([raiz + x for x in color], ton) + ([raiz - 12] if etapa >= 2 else [])
            for n in notas:
                self._nota("cuerdas", t0, cada * TICKS_POR_COMPAS - 3, n, v((0.45 if car == "titulos" else 0.35) + 0.4 * crece))
        # Pista 3: arpegio (neón, cosmos) o pulso (títulos).
        rng = self._rng("arpegio", etapa, ciclo)
        if car == "titulos":
            grave = ton + r if ton + r >= 36 else ton + r + 12
            figura = PULSOS[int(self._rng("pulso", ciclo).random() * len(PULSOS))]
            for k in range(0, 16, 1 if etapa >= 1 and self.densidades["coro"] >= 0.34 else 2):
                if k * SEMI < hasta:
                    self._nota("coro", t0 + k * SEMI, SEMI - 1, grave + figura[k],
                               v((0.45 + 0.4 * crece) * (1 if k % 4 == 0 else 0.7)))
        elif etapa >= 1:
            figura = ARPEGIOS[int(rng.random() * len(ARPEGIOS))]
            alto = 24 if car == "cosmos" else 12
            paso = 2 if car == "neon" or etapa == 3 else 4   # corcheas o negras (en semicorcheas)
            if self.densidades["coro"] < 0.34:
                paso = 4
            elif self.densidades["coro"] > 0.66:
                paso = max(1, paso // 2)
            for j, k in enumerate(range(0, 16, paso)):
                if k * SEMI < hasta:
                    self._nota("coro", t0 + k * SEMI, paso * SEMI - 1, raiz + alto + color[figura[j % 8]],
                               v((0.3 if car == "neon" else 0.35) + 0.3 * crece))
        # Pista 2: el lead en frases de 4 compases (títulos: fanfarria desde la etapa 3).
        if etapa >= (2 if car == "titulos" else 1):
            frase, k = divmod(c - (self._inicio_etapa(2) if car == "titulos" else i1), 4)
            notas = self._melodia(t0, k, frase % 2, (ciclo, frase), ton + 24, v(0.6 + 0.3 * crece),
                                  escala=ESCALAS_CINE[car], ritmos_de=RITMOS_TEMA if car == "titulos" else RITMOS_CINE, tocar=False)
            octava = etapa == 3 and car != "neon"
            for j, (ini, dur, nota, fuerza) in enumerate(notas):
                if ini >= t0 + hasta:
                    continue
                self._nota("cuernos", ini, dur, nota, fuerza)
                if octava:
                    self._nota("cuernos", ini, dur, nota + 12, fuerza * 0.85)
                self._bends(ini, dur, entra=(car != "titulos" or j == 0) and self._rng("bend", c, j, ciclo).random() < 0.6,
                            cae=k == 3 and car == "neon")
        # Pista 4: timbal, caja con reverb y gong.
        golpes = []
        if c == self.inicio_tramo(c) and etapa > 0:
            golpes.append((0, self.nota_golpe, 0.4 + 0.4 * crece))
        if car == "neon":
            if etapa >= 2:
                golpes.append((2, self.nota_tambor, 0.4 + 0.3 * crece))
            if etapa == 3 and c % 2 == 0:
                golpes.append((0, self.nota_taiko, 0.5 + 0.3 * crece))
        elif car == "titulos":
            if etapa >= 1:
                golpes += [(0, self.nota_taiko, 0.55 + 0.35 * crece), (2.5, self.nota_taiko, 0.45 + 0.3 * crece)]
            if etapa >= 2:
                golpes.append((2, self.nota_tambor, 0.55 + 0.35 * crece))
            if final:
                golpes.append((0, self.nota_golpe, 1.0))
        else:
            if etapa >= 2:
                golpes.append((0, self.nota_taiko, 0.5 + 0.3 * crece))
            sube = c + 1 < self.largo and self.etapa(c + 1) > etapa
            if sube:   # redoble de timbal hacia la etapa siguiente
                golpes += [(2 + k / 4, self.nota_taiko, 0.3 + 0.08 * k) for k in range(8)]
        for b, nota, f in golpes:
            if b * NEGRA < hasta:
                self._nota("percusion", t0 + round(b * NEGRA), SEMI, nota, v(min(1.0, f)))
        if final and self.escena_vuelta:
            self.pendientes.append((t0 + hasta + 1, "program_change", self.canal_control, self.escena_vuelta - 1, 0))

    def _bends(self, ini, dur, entra, cae):
        """Pitch bend del lead: entra un semitono abajo y sube en una corchea; al final de
        la frase (neón) cae un tono en el último tiempo. Siempre vuelve al centro."""
        canal = self.canales["cuernos"]
        if canal < 0 or not self.bend_rango:
            return
        semi = 8191 / self.bend_rango
        fin = ini + max(1, round(dur))
        if self._corte is not None:
            fin = min(fin, self._corte)
        if entra and ini + 12 < fin:
            for k in range(5):
                self.pendientes.append((ini + k * 3, "pitchwheel", canal, round(-semi * (1 - k / 4)), 0))
        if cae and dur >= 2 * NEGRA:
            desde = fin - NEGRA
            for k in range(1, 7):
                self.pendientes.append((desde + k * NEGRA // 6, "pitchwheel", canal,
                                        round(-min(2, self.bend_rango) * semi * k / 6), 0))
        self.pendientes.append((fin, "pitchwheel", canal, 0, 0))

    def _melodia(self, t0, k, cual, clave, base, vel, escala=None, ritmos_de=RITMOS_CHILL, tocar=True):
        """El compás k (0-3) de la frase A (cual 0, cae en la quinta) o B (1, cae en la tónica).
        Con el tema del track, las notas siguen el motivo de la secuencia (menos la última,
        que cierra la frase). Devuelve las notas (inicio, largo, nota, fuerza)."""
        escala = escala or ESCALAS_CHILL[self.caracter]
        rng = self._rng("melodia", self.caracter, cual, *clave) if clave[0] else self._rng("melodia", self.caracter, cual, clave[1] // 2)
        ritmos = [ritmos_de[int(rng.random() * len(ritmos_de))] for _ in range(3)] + [((0, 4),)]
        g = rng.choice((0, 2, 4))
        grados = []
        for _ in range(sum(len(x) for x in ritmos)):
            g = max(0, min(9, g + rng.choice((-2, -1, -1, 0, 1, 1, 2))))
            grados.append(g)
        fin = 4 if cual == 0 else (7 if grados[-2] >= 4 else 0)
        grados[-1] = fin
        i = sum(len(x) for x in ritmos[:k])
        notas = []
        for j, (ini, dur) in enumerate(ritmos[k]):
            gg = grados[i + j]
            semis = escala[gg % len(escala)] + 12 * (gg // len(escala))
            if self.motivo and i + j < len(grados) - 1:
                semis = self.motivo[(i + j) % len(self.motivo)]
            notas.append((t0 + round(ini * NEGRA), dur * NEGRA - 3, base + semis, vel * (1 if j == 0 else 0.85)))
        notas = self._densificar(notas, t0, base, escala, (cual, *clave, k))
        if tocar:
            for n in notas:
                self._nota("cuernos", *n)
        return notas

    # --- Por instrumento ---

    def _densificar(self, notas, t0, base, escala, clave):
        """Densidad de la melodía: baja = a veces una sola nota larga en el compás; alta =
        las notas largas se parten en dos (la segunda a un paso de escala)."""
        d = self.densidades["cuernos"]
        if d == 0.5 or not notas:
            return notas
        rng = self._rng("densidad", *clave)
        if d < 0.5:
            if rng.random() < (0.5 - d) * 2:
                ini, dur, nota, f = notas[0]
                return [(ini, max(dur, t0 + TICKS_POR_COMPAS - 3 - ini), nota, f)]
            return notas
        sal = []
        for ini, dur, nota, f in notas:
            if dur >= 2 * NEGRA - 3 and rng.random() < (d - 0.5) * 2:
                mitad = (dur + 3) // 2
                sal.append((ini, mitad - 3, nota, f))
                sal.append((ini + mitad, dur - mitad, self._vecina(nota, base, escala, rng.choice((-1, 1, 1))), f * 0.9))
            else:
                sal.append((ini, dur, nota, f))
        return sal

    @staticmethod
    def _vecina(nota, base, escala, paso):
        octava, r = divmod(nota - base, 12)
        if r not in escala:
            return nota
        o2, j = divmod(escala.index(r) + paso, len(escala))
        return base + 12 * (octava + o2) + escala[j]

    def _cada_acorde(self):
        """Cada cuántos compases ataca el colchón: 2 (como siempre) o 1 con densidad alta."""
        return 1 if self.densidades["cuerdas"] > 0.66 else 2

    def _voicing(self, acorde, ton):
        """Acordes: voces (2-5), inversión, abierto y pedal de tónica. Densidad baja del
        colchón: solo raíz y quinta."""
        tonos = sorted(acorde)
        if self.densidades["cuerdas"] < 0.34 and not self.voces:
            tonos = [tonos[0]] + [x for x in tonos if (x - tonos[0]) % 12 == 7][:1]
        if self.voces:
            base = list(tonos)
            k = 0
            while len(tonos) < self.voces:
                tonos.append(base[k % len(base)] + 12 * (1 + k // len(base)))
                k += 1
            tonos = sorted(tonos)[:self.voces]
        for _ in range(self.inversion):
            tonos = sorted(tonos[1:] + [tonos[0] + 12])
        if self.abierto and len(tonos) >= 3:
            tonos = sorted(tonos[::2] + [x + 12 for x in tonos[1::2]])
        if self.pedal:
            tonos = [ton] + tonos
        return tonos

    def _coro_notas(self, notas, ton):
        """Densidad del coro: baja = solo la raíz; alta = suma la octava de arriba."""
        d = self.densidades["coro"]
        notas = list(notas)
        if d < 0.34:
            return notas[:1]
        if d > 0.66 and ton + 24 not in notas:
            notas.append(ton + 24)
        return notas

    # --- Tema del track ---

    def motivo_de(self, patron):
        """Las primeras 3 a 6 alturas distintas que suenan en el patrón de una secuencia,
        en semitonos sobre la tónica, plegadas para que ningún salto pase de una sexta."""
        iv = self.tonalidad.intervalos
        sal, previa = [], None
        for p in patron or ():
            if not p.get("suena"):
                continue
            g = int(p.get("grado", 0)) + 7 * int(p.get("octava", 0))
            x = iv[g % len(iv)] + 12 * (g // len(iv))
            if previa is None:
                sal.append(x % 12)
            else:
                salto = x - previa
                while salto > 9:
                    salto -= 12
                while salto < -9:
                    salto += 12
                if salto:
                    sal.append(sal[-1] + salto)
            previa = x
            if len(sal) == 6:
                break
        if len({x % 12 for x in sal}) < 3:
            return None   # un pedal o casi: no hay tema que tomar
        if min(sal) < -2:
            sal = [x + 12 for x in sal]
        elif max(sal) > 19:
            sal = [x - 12 for x in sal]
        return sal

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
            elif tipo == "pitchwheel":
                self._bend_usado = a != 0
            enviar(self.salida, tipo, canal, a, b)

    def apagar(self, enviar):
        for canal, nota in list(self.sonando):
            enviar(self.salida, "note_off", canal, nota, 0)
        self._soltar_respiracion(enviar)
        if self._bend_usado and self.canales["cuernos"] >= 0:
            enviar(self.salida, "pitchwheel", self.canales["cuernos"], 0, 0)
            self._bend_usado = False
        self.sonando = {}
        self.pendientes = [p for p in self.pendientes if p[1] == "program_change"]
