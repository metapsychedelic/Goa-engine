"""Tocado: un secuenciador aparte que se toca con el teclado de la MicroFreak.

Tú pones el ritmo (cortas, largas, fuertes, suaves) y el motor pone las alturas, siempre
dentro de la escala y del acorde que suena: nunca queda desafinado.

  Una tecla  da lo mismo qué tecla: las notas salen de una secuencia del estilo elegido
             (los mismos estilos de las secuencias: rolling, galope, arpegio, ácido,
             clásico, psytrance…), con la seed. Cada nota que tocas toma la altura del paso
             de esa secuencia en que cae (o la del último paso que suena antes).
  Contorno   la tecla cuenta: tocas más agudo y la nota sube, pero cae siempre en la
             escala, y en los tiempos fuertes en una nota del acorde.

Lo que tocas suena al instante (sin cuantizar: cuantizar sería esperar). Grabar arma la
grabación: empieza en el próximo compás, dura los pasos elegidos (1 a 32 semicorcheas) y
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
import random

from . import armonia
from .generador import ESTILOS

log = logging.getLogger("goa.tocado")

PULSOS_POR_COMPAS = 96
PULSOS_POR_PASO = 6
CUANTIZAR = ("estricta", "suave", "swing", "libre")
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
        clave = (cfg.get("estilo"), cfg.get("seed"), cfg.get("genero"))
        if clave != getattr(self, "_clave_patron", None):
            self._clave_patron = clave
            self.patron = _patron(cfg)
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

    def elegir(self, tecla, velocidad, pulso_en_compas, momento, indice, previa, paso_absoluto=None):
        """La nota para una tecla. pulso_en_compas: 0-95. previa: la nota anterior (o None)."""
        t = self.tonalidad
        fuerte = pulso_en_compas % 24 < 3   # en el tiempo (o apenas después)
        clases = momento.clases if momento is not None else armonia.triada(t, t.tonica)
        raiz = momento.raiz % 12 if momento is not None else t.tonica
        centro = self._registro()
        ancla = _cerca(raiz, centro)
        if self.cfg.get("modo") == "contorno":
            nota = _en_escala(t, tecla + (centro - 60))
            if fuerte:
                nota = armonia.nota_del_acorde(nota, clases)
            return _limitar(nota)
        nota = ancla
        if self.patron:
            # La altura del paso de la secuencia del estilo en que cae la nota (o la del
            # último paso que suena antes): tu ritmo, la melodía del estilo.
            n = len(self.patron)
            i = (paso_absoluto if paso_absoluto is not None else pulso_en_compas // PULSOS_POR_PASO) % n
            for k in range(n):
                p = self.patron[(i - k) % n]
                if p and p.get("suena", True):
                    nota = t.nota(ancla, p["grado"], "escala") + 12 * p.get("octava", 0)
                    break
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
                    nota = self.elegir(tecla, vel, tick % PULSOS_POR_COMPAS, momento, i, previa, tick // PULSOS_POR_PASO)
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
        """Según `cuantizar`: estricta, suave (a mitad de camino), swing o libre. Dos
        notas que caen en el mismo lugar: queda la más fuerte."""
        modo = self.cfg.get("cuantizar", "estricta")
        notas = {}
        for inicio, largo, vel, tecla in self.grabadas:
            q, d = inicio, largo
            if modo != "libre":
                paso = round(inicio / PULSOS_POR_PASO)
                destino = paso * PULSOS_POR_PASO + (SWING if modo == "swing" and paso % 2 == 1 else 0)
                fin = max(destino + PULSOS_POR_PASO, round((inicio + largo) / PULSOS_POR_PASO) * PULSOS_POR_PASO)
                if modo == "suave":
                    q = round((inicio + destino) / 2)
                    d = max(2, round((largo + (fin - destino)) / 2))
                else:
                    q, d = destino, fin - destino
            q %= self.largo
            d = max(1, min(d, self.largo))
            if q not in notas or vel > notas[q][2]:
                notas[q] = (q, d, vel, tecla)
        self.grabadas = sorted(notas.values())

    def _cambio_de_acorde(self, tick, momento, enviar):
        """Una nota que queda chocando con el acorde nuevo se vuelve a atacar, suave,
        en la nota del acorde más cercana."""
        if momento is None or momento.clases == self.clases:
            return
        self.clases = momento.clases
        for nota, (duenio, vel) in list(self.sonando.items()):
            if nota % 12 in momento.clases:
                continue
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


def _patron(cfg):
    """La secuencia del estilo elegido (la misma que generaría una secuencia normal con
    esa seed). En «una tecla» cada nota toma de ahí su altura."""
    from .config import ESQUEMA_SECUENCIA
    from .secuencia import Secuencia
    estilo = cfg.get("estilo") if cfg.get("estilo") in ESTILOS else "rolling"
    base = {k: v[1] for k, v in ESQUEMA_SECUENCIA.items()}
    base.update(estilo=estilo, seed=cfg.get("seed", "TC-0001"), genero=cfg.get("genero", base.get("genero")),
                nombre="Tocado", activa=False, molde="", filtro=False)
    try:
        return list(Secuencia(base).patron)
    except Exception:  # noqa: BLE001  sin patrón, toca la raíz del acorde
        log.exception("Tocado: no pude generar el patrón de %s", estilo)
        return []
