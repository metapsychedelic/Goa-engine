"""Tocado: un secuenciador aparte que se toca con el teclado de la MicroFreak.

Tú pones el ritmo (cortas, largas, fuertes, suaves) y el motor pone las alturas, siempre
dentro de la escala y del acorde que suena: nunca queda desafinado.

  Una tecla  da lo mismo qué tecla: las notas salen de una secuencia del estilo elegido
             (los mismos estilos de las secuencias, con sus ajustes: figura, frase,
             relación, saltos, raga, escala de color, ♭2, acentos), con la seed. La nota N
             que tocas toma la nota N que suena en esa secuencia: tu ritmo, su melodía. En
             el loop la cuenta sigue de una vuelta a la otra, así la melodía avanza.
  Contorno   la tecla cuenta: tocas más agudo y la nota sube, pero cae siempre en la
             escala, y en los tiempos fuertes en una nota del acorde.

Lo que tocas suena al instante (sin cuantizar: cuantizar sería esperar). Grabar arma la
grabación: empieza en el próximo compás, dura los pasos elegidos (1 a 128 semicorcheas) y
después queda en loop. La cuantización se aplica a lo grabado:
  estricta  inicio y largo a la semicorchea
  suave     a mitad de camino hacia la semicorchea: ordena sin perder tu toque
  swing     a la semicorchea, con las del contratiempo un poco tarde (groove)
  libre     tal cual lo tocaste
El loop guarda el ritmo y la tecla, no la altura: cada vuelta vuelve a elegir las notas con
la armonía de ese momento, así sigue a los pads, y «Otra variante» (seed nueva) le cambia
las notas sin tocar tu ritmo.

Una nota larga que queda chocando con un acorde nuevo se vuelve a atacar, suave, en la
nota del acorde más cercana.
"""

import json
import logging
import math
import random

from . import armonia
from .azar import azar as azar_fijo
from .config import TOCADO_PATRON
from .generador import ESTILOS

log = logging.getLogger("goa.tocado")

PULSOS_POR_COMPAS = 96
PULSOS_POR_PASO = 6
CUANTIZAR = ("estricta", "suave", "swing", "libre")
LATENCIA = 1 # pulsos que se descuentan antes de cuantizar (la tecla llega y uno toca un pelo tarde)
SWING = 2    # pulsos de atraso de las semicorcheas del contratiempo en «swing» (un tercio de paso)
ANTES = 4    # pulsos: una nota tocada justo antes de que empiece la grabación cuenta desde el uno


class Tocado:
    def __init__(self):
        self.cfg = {}
        self.activo = False
        self.salida, self.canal = None, 0
        self.tonalidad = None
        self.vivas = {}          # tecla -> nota que suena por esa tecla
        self.fuerzas = {}        # tecla -> velocidad con que se apretó
        self.anticipadas = {}    # tecla -> fuerza, tocadas apenas antes de empezar a grabar
        self.sonando = {}        # nota que suena -> (tecla o ("loop", i), velocidad)
        self.estado = "libre"    # libre | armado | grabando | loop | pausa
        self.grabadas = []       # (pulso desde el inicio, largo en pulsos, velocidad, tecla)
        self.abiertas = {}       # tecla -> (pulso de inicio, velocidad) mientras se graba
        self.inicio = None       # tick (al principio de un compás) en que empezó la grabación
        self.largo = 0           # pulsos del loop
        self.vencen = []         # (tick, nota, dueño) de las notas del loop y las apoyaturas
        self.pendientes = []     # (tick, nota, velocidad, dueño): la nota tras una apoyatura
        self.indice = 0          # notas tocadas en la frase (para el mantra y el azar)
        self.ultima = None       # (tick, nota) de la última nota tocada
        self.clases = None       # acorde con el que se eligieron las notas que suenan
        self.patron = []         # la secuencia del estilo (de ahí salen las alturas en «una tecla»)
        self.acento = False      # la última nota elegida cae en un acento del estilo
        self.sec = None          # esa secuencia (con sus ajustes: relación, saltos, raga, acentos…)
        self.texto = ""          # lo grabado tal como está en la configuración (tocado.loop)
        self.cambio_loop = False # grabó o borró: la app tiene que guardarlo (Contexto.sincronizar_tocado)

    # --- Configuración ---

    def configurar(self, cfg, tonalidad, enviar, tick=0):
        destino = (cfg.get("salida"), int(cfg.get("canal", 4)) - 1)
        texto = cfg.get("loop", "") or ""
        if texto != self.texto and not self.cambio_loop:
            self._cargar(texto, tick)   # otra escena, otro proyecto o al prender
        if (self.salida, self.canal) != destino or not cfg.get("activo"):
            self.apagar(enviar)
        self.cfg = dict(cfg)
        self.activo = bool(cfg.get("activo"))
        self.salida, self.canal = destino
        self.tonalidad = tonalidad
        clave = json.dumps({k: cfg.get(k) for k in ("estilo", "seed") + TOCADO_PATRON}, sort_keys=True)
        if clave != getattr(self, "_clave_patron", None) or tonalidad is not getattr(self, "_tonalidad_patron", None):
            self._clave_patron, self._tonalidad_patron = clave, tonalidad
            self.sec = _secuencia(cfg, tonalidad)
            self.patron = list(self.sec.patron) if self.sec is not None else []
        if not self.activo:
            self.estado, self.abiertas = ("pausa" if self.grabadas else "libre"), {}

    # --- Elegir la nota ---

    # --- Guardar lo grabado (en la configuración: escenas, proyecto, tarjeta) ---

    def serializar(self):
        if not self.grabadas:
            return ""
        return json.dumps({"pulsos": self.largo, "notas": [list(g) for g in self.grabadas]}, separators=(",", ":"))

    def _cargar(self, texto, tick):
        self.texto = texto
        try:
            datos = json.loads(texto) if texto else {"pulsos": 0, "notas": []}
            if isinstance(datos, list):   # formato de la 0.64-0.65: [compases, notas]
                datos = {"pulsos": int(datos[0]) * PULSOS_POR_COMPAS, "notas": datos[1]}
            largo, notas = int(datos["pulsos"]), datos["notas"]
            grabadas = sorted((int(a), int(b), int(c), int(d)) for a, b, c, d in notas)
        except (ValueError, TypeError):
            log.warning("Tocado: no entiendo el loop guardado")
            return
        if self.estado in ("grabando", "armado"):
            return  # estás grabando: lo nuevo manda
        self.grabadas, self.largo = grabadas, largo
        if grabadas and self.largo:
            self.estado = "loop" if self.estado != "pausa" else "pausa"
            self.inicio = max(tick, 0) - max(tick, 0) % PULSOS_POR_COMPAS   # desde el uno de este compás
        else:
            self.estado = "libre"

    def _rng(self, *clave):
        return random.Random(f"{self.cfg.get('seed', 'TC')}:{self.cfg.get('estilo')}:" + ":".join(map(str, clave)))

    def _registro(self):
        base = 60
        return base + 12 * int(self.cfg.get("octava", 0))

    def elegir(self, tecla, velocidad, pulso_en_compas, momento, indice, previa=None, paso_absoluto=None):
        """La nota para una tecla. pulso_en_compas: 0-95. previa: la nota anterior (o None)."""
        t = self.tonalidad
        fuerte = pulso_en_compas % 24 < 3   # en el tiempo (o apenas después)
        clases = momento.clases if momento is not None else armonia.triada(t, t.tonica)
        raiz = momento.raiz % 12 if momento is not None else t.tonica
        centro = self._registro()
        ancla = _cerca(raiz, centro)
        self.acento = False
        if self.cfg.get("modo") == "contorno":
            nota = _en_escala(t, tecla + (centro - 60))
            if fuerte:
                nota = armonia.nota_del_acorde(nota, clases)
            return _limitar(nota)
        nota, self.acento = ancla, False
        sec = self.sec
        suenan = [i for i, p in enumerate(self.patron) if p and p.get("suena", True)]
        if suenan:
            # La nota N que tocas toma la nota N que suena en la secuencia del estilo:
            # tu ritmo con la melodía del estilo (su contorno, sus saltos, su raga).
            i = suenan[indice % len(suenan)]
            p = self.patron[i]
            x = sec.extra[p.get("fuente", i)] if sec is not None and sec.extra else {}
            octava = p.get("octava", 0) + (x.get("direccion", 0) if x.get("salto", 1) < (sec.saltos if sec else 0) else 0)
            escala = (sec.tonalidad if sec is not None and sec.tonalidad is not None else t)
            nota = escala.nota(ancla, p["grado"] + (sec.relacion if sec else 0), "escala") + 12 * octava
            if sec is not None and sec.semitono and not fuerte and x.get("semitono", azar_fijo(f"{sec.seed}:semitono:{i}")) < sec.semitono:
                nota = _cerca((raiz + 1) % 12, nota)   # el ♭2 en los pasos débiles
            if "pref_acento" in p:
                self.acento = x.get("acento", 1) < (sec.acentos if sec else 0) * p["pref_acento"]
            else:
                self.acento = bool(p.get("acento")) or x.get("acento", 1) < (sec.acentos if sec else 0)
            if escala is not t:
                return _limitar(armonia.nota_del_acorde(nota, clases) if fuerte else nota)   # raga / color: su escala
        if fuerte:
            nota = armonia.nota_del_acorde(nota, clases)
        return _limitar(_en_escala(t, nota))

    def _apoyatura(self, nota, pulso_en_compas):
        """Raga: en el tiempo, la nota llega desde la de arriba (un pulso antes)."""
        return False  # (la raga queda para los estilos de secuencia con ornamentos)

    # --- Tocar en vivo ---

    def tecla_on(self, tecla, velocidad, tick, momento, enviar, corriendo=True):
        if not self.activo or self.tonalidad is None:
            return
        if tecla in self.vivas:
            self.tecla_off(tecla, tick, enviar)   # la misma tecla otra vez sin soltar (no debería pasar)
        en_compas = max(tick, 0) % PULSOS_POR_COMPAS
        previa = self.ultima[1] if self.ultima is not None else None
        if self.ultima is not None and tick - self.ultima[0] > 2 * 24:
            self.indice, previa = 0, None   # después de una pausa larga empieza otra frase
        nota = self.elegir(tecla, velocidad, en_compas, momento, self.indice, previa, max(tick, 0) // PULSOS_POR_PASO)
        if self.acento and self.sec is not None:
            velocidad = max(velocidad, self.sec.acento)   # acento del estilo
        self.indice += 1
        self.ultima = (tick, nota)
        self.clases = momento.clases if momento is not None else None
        self._sonar(nota, velocidad, tecla, tick, en_compas if corriendo else 1, enviar)
        self.vivas[tecla] = nota
        self.fuerzas[tecla] = velocidad
        if self.estado == "grabando":
            self.abiertas[tecla] = (tick - self.inicio, velocidad)
        elif self.estado == "armado" and PULSOS_POR_COMPAS - en_compas <= ANTES:
            self.anticipadas[tecla] = velocidad   # justo antes del uno: cuenta desde el uno

    def tecla_off(self, tecla, tick, enviar):
        nota = self.vivas.pop(tecla, None)
        if nota is not None and self.sonando.get(nota, (None,))[0] == tecla:
            del self.sonando[nota]
            enviar(self.salida, "note_off", self.canal, nota, 0)
        self.pendientes = [p for p in self.pendientes if p[3] != tecla]
        self.fuerzas.pop(tecla, None)
        abierta = self.abiertas.pop(tecla, None)
        if abierta is not None and self.estado == "grabando":
            inicio, vel = abierta
            self.grabadas.append((inicio, max(1, tick - self.inicio - inicio), vel, tecla))

    def _sonar(self, nota, velocidad, duenio, tick, en_compas, enviar):
        if nota in self.sonando:
            enviar(self.salida, "note_off", self.canal, nota, 0)   # la misma nota: se vuelve a atacar
        self.sonando[nota] = (duenio, velocidad)
        if self._apoyatura(nota, en_compas):
            arriba = _limitar(self.tonalidad.nota(nota, 1, "escala"))
            enviar(self.salida, "note_on", self.canal, arriba, max(1, velocidad - 20))
            self.vencen.append((tick + 2, arriba, None))
            self.pendientes.append((tick + 2, nota, velocidad, duenio))
            return
        enviar(self.salida, "note_on", self.canal, nota, velocidad)

    # --- Grabar y loop ---

    def accion(self, que, tick):
        pasos = max(1, min(32, int(self.cfg.get("pasos", 16))))
        if que == "grabar":
            self.grabadas, self.abiertas, self.estado = [], {}, "armado"
            self.anticipadas = {}
            self.largo = pasos * PULSOS_POR_PASO
        elif que == "parar":
            if self.estado in ("loop", "grabando", "armado"):
                self.estado = "pausa" if self.grabadas else "libre"
        elif que == "seguir":
            if self.grabadas:
                self.estado = "loop"
        elif que == "borrar":
            self.grabadas, self.abiertas, self.estado = [], {}, "libre"
            self.cambio_loop = True
        else:
            raise ValueError(f"Acción desconocida: {que!r}")

    def pulso(self, tick, momento_de, enviar):
        """Cada pulso del reloj. momento_de(paso) -> Momento (o None)."""
        for v in [v for v in self.vencen if v[0] <= tick]:
            self.vencen.remove(v)
            _, nota, duenio = v
            actual = self.sonando.get(nota, (None,))[0]
            if duenio is None and actual is not None:
                continue  # la apoyatura cayó en una nota que ahora suena por otra tecla
            if duenio is not None and actual != duenio:
                continue  # esa nota ya la volvió a tomar otra
            self.sonando.pop(nota, None)
            enviar(self.salida, "note_off", self.canal, nota, 0)
        for p in [p for p in self.pendientes if p[0] <= tick]:
            self.pendientes.remove(p)
            _, nota, vel, duenio = p
            if nota in self.sonando and self.sonando[nota][0] == duenio:
                enviar(self.salida, "note_on", self.canal, nota, vel)
        if tick % PULSOS_POR_COMPAS == 0 and self.estado == "armado":
            self._empezar(tick)
        elif self.estado == "grabando" and tick - self.inicio >= self.largo:
            self._terminar(tick)
        if tick % PULSOS_POR_PASO == 0:
            self._cambio_de_acorde(tick, momento_de(tick // PULSOS_POR_PASO), enviar)
        if self.estado == "loop" and self.activo and self.largo:
            dentro = (tick - self.inicio) % self.largo
            for i, (inicio, largo, vel, tecla) in enumerate(self.grabadas):
                if inicio == dentro:
                    momento = momento_de(tick // PULSOS_POR_PASO)
                    previa = self.ultima[1] if self.ultima is not None else None
                    vuelta = (tick - self.inicio) // self.largo
                    nota = self.elegir(tecla, vel, tick % PULSOS_POR_COMPAS, momento, vuelta * len(self.grabadas) + i,
                                       previa, tick // PULSOS_POR_PASO)
                    if self.acento and self.sec is not None:
                        vel = max(vel, self.sec.acento)
                    self.ultima = (tick, nota)
                    self.clases = momento.clases if momento is not None else None
                    self._sonar(nota, vel, ("loop", i), tick, tick % PULSOS_POR_COMPAS, enviar)
                    self.vencen.append((tick + largo, nota, ("loop", i)))

    def _empezar(self, tick):
        self.estado, self.inicio = "grabando", tick
        # Lo que ya estabas apretando (o tocaste apenas antes) cuenta desde el uno.
        self.abiertas = {tecla: (0, self.fuerzas.get(tecla, 100)) for tecla in self.vivas}
        for tecla, vel in self.anticipadas.items():
            if tecla not in self.vivas:   # una corta tocada apenas antes y ya soltada
                self.grabadas.append((0, PULSOS_POR_PASO, vel, tecla))
        self.anticipadas = {}

    def _terminar(self, tick):
        for tecla, (inicio, vel) in self.abiertas.items():
            self.grabadas.append((inicio, max(1, self.largo - inicio), vel, tecla))
        self.abiertas = {}
        self._cuantizar()
        self.estado = "loop" if self.grabadas else "libre"
        self.inicio = tick
        self.cambio_loop = True
        log.info("Tocado: loop de %d pasos con %d notas (%s)", self.largo // PULSOS_POR_PASO, len(self.grabadas),
                 self.cfg.get("cuantizar", "estricta"))

    def _cuantizar(self):
        """Según `cuantizar`: estricta, suave (a mitad de camino), swing o libre, a la
        rejilla de `grilla` (semicorcheas o corcheas). Antes de redondear descuenta
        LATENCIA (lo que tarda la tecla en llegar y lo que uno toca un pelo tarde), así
        una nota apenas tarde no salta al paso siguiente. En estricta además ninguna nota
        se monta sobre la siguiente. Dos notas en el mismo lugar: queda la más fuerte."""
        modo = self.cfg.get("cuantizar", "estricta")
        rejilla = PULSOS_POR_PASO * (2 if int(self.cfg.get("grilla", 16)) == 8 else 1)
        notas = {}
        for inicio, largo, vel, tecla in self.grabadas:
            q, d = inicio, largo
            if modo != "libre":
                paso = math.floor(max(0, inicio - LATENCIA) / rejilla + 0.5)   # a la mitad, hacia adelante
                destino = paso * rejilla + (SWING * rejilla // PULSOS_POR_PASO if modo == "swing" and paso % 2 == 1 else 0)
                fin = max(destino + rejilla, math.floor((inicio - LATENCIA + largo) / rejilla + 0.5) * rejilla)
                if modo == "suave":
                    q = round((inicio + destino) / 2)
                    d = max(2, round((largo + (fin - destino)) / 2))
                else:
                    q, d = destino, fin - destino
            q %= self.largo
            d = max(1, min(d, self.largo))
            if q not in notas or vel > notas[q][2]:
                notas[q] = (q, d, vel, tecla)
        ordenadas = sorted(notas.values())
        if modo == "estricta" and len(ordenadas) > 1:
            # Cada nota termina, a más tardar, donde empieza la siguiente (también la
            # última contra la primera de la vuelta siguiente).
            cortadas = []
            for k, (q, d, vel, tecla) in enumerate(ordenadas):
                siguiente = ordenadas[(k + 1) % len(ordenadas)][0] + (self.largo if k + 1 == len(ordenadas) else 0)
                cortadas.append((q, max(1, min(d, siguiente - q)), vel, tecla))
            ordenadas = cortadas
        self.grabadas = ordenadas

    def _cambio_de_acorde(self, tick, momento, enviar):
        """Una nota que queda chocando con el acorde nuevo se vuelve a atacar, suave,
        en la nota del acorde más cercana."""
        if momento is None or momento.clases == self.clases:
            return
        self.clases = momento.clases
        for nota, (duenio, vel) in list(self.sonando.items()):
            if nota % 12 in momento.clases or isinstance(duenio, tuple):
                continue  # las del loop no se vuelven a atacar: el ritmo grabado queda exacto
            nueva = armonia.nota_del_acorde(nota, momento.clases)
            enviar(self.salida, "note_off", self.canal, nota, 0)
            del self.sonando[nota]
            if nueva in self.sonando:
                continue
            self.sonando[nueva] = (duenio, vel)
            enviar(self.salida, "note_on", self.canal, nueva, max(1, int(vel * 0.7)))
            if not isinstance(duenio, tuple):
                self.vivas[duenio] = nueva
            self.vencen = [(t, nueva if n == nota and d == duenio else n, d) for t, n, d in self.vencen]

    def reiniciar(self, tick=0):
        """Al Start: el loop vuelve a empezar desde su primer compás."""
        if self.estado == "loop":
            self.inicio = tick
        elif self.estado == "grabando":
            self.estado = "armado"
            self.grabadas, self.abiertas = [], {}

    def apagar(self, enviar):
        for nota in list(self.sonando):
            enviar(self.salida, "note_off", self.canal, nota, 0)
        self.sonando, self.vivas, self.vencen, self.pendientes = {}, {}, [], []

    def estado_app(self, tick):
        e = {"estado": self.estado, "notas": len(self.grabadas), "pasos": self.largo // PULSOS_POR_PASO}
        if self.estado == "grabando" and self.inicio is not None:
            e["paso"] = min(self.largo, tick - self.inicio) // PULSOS_POR_PASO + 1
        if self.estado == "loop" and self.inicio is not None and self.largo:
            e["paso"] = (tick - self.inicio) % self.largo // PULSOS_POR_PASO + 1
        return e


def _cerca(clase, referencia):
    n = referencia - (referencia - clase) % 12
    return n + 12 if referencia - n > 6 else n


def _en_escala(tonalidad, nota):
    """La nota de la escala más cercana (en empate, la de abajo): nunca desafina."""
    for d in (0, -1, 1, -2, 2):
        if (nota + d) % 12 in {(tonalidad.tonica + i) % 12 for i in tonalidad.intervalos}:
            return nota + d
    return nota


def _limitar(nota):
    return max(0, min(127, nota))


def _secuencia(cfg, tonalidad):
    """La secuencia del estilo elegido, con los ajustes de patrón del Tocado (los mismos
    que una secuencia normal). En «una tecla» cada nota toma de ahí su altura."""
    from .config import ESQUEMA_SECUENCIA
    from .escalas import Tonalidad
    from .secuencia import Secuencia
    estilo = cfg.get("estilo") if cfg.get("estilo") in ESTILOS else "rolling"
    base = {k: v[1] for k, v in ESQUEMA_SECUENCIA.items()}
    base.update({k: cfg[k] for k in TOCADO_PATRON if k in cfg})
    base.update(estilo=estilo, seed=cfg.get("seed", "TC-0001"), nombre="Tocado", activa=False, molde="", filtro=False,
                salida=cfg.get("salida", "FM-1"))
    try:
        sec = Secuencia(base)
        color = f"raga:{sec.raga}" if sec.raga else base.get("escala_color", "")
        if color and tonalidad is not None:
            nombres = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
            sec.tonalidad = Tonalidad(nombres[tonalidad.tonica % 12], color)
        return sec
    except Exception:  # noqa: BLE001  sin patrón, toca la raíz del acorde
        log.exception("Tocado: no pude generar el patrón de %s", estilo)
        return None
