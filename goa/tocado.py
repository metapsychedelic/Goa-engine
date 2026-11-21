"""Tocado: un secuenciador aparte que se toca con el teclado de la MicroFreak.

Tú pones el ritmo (cortas, largas, fuertes, suaves) y el motor pone las alturas, siempre
dentro de la escala y del acorde que suena: nunca queda desafinado.

  Una tecla  da lo mismo qué tecla: el estilo elige cada nota.
  Contorno   la tecla cuenta: tocas más agudo y la nota sube, pero cae siempre en la
             escala, y en los tiempos fuertes en una nota del acorde.

Estilos: goa (anclas en el tiempo y la línea corre entre ellas), ácido (raíz, octava
en los acentos, terceras y séptimas), mantra (un motivo de tres notas que se repite y
sigue la armonía), raga (líneas por grados con apoyatura desde arriba en los tiempos
fuertes) y bajo (raíz en el tiempo, octava y quinta en el contratiempo).

Lo que tocas suena al instante (sin cuantizar: cuantizar sería esperar). Grabar arma la
grabación: empieza en el próximo compás, dura los compases elegidos (8 a 32) y después
queda en loop, cuantizado a semicorcheas. El loop guarda el ritmo y la tecla, no la
altura: cada vuelta vuelve a elegir las notas con la armonía de ese momento, así sigue
a los pads, y «Otra variación» (seed nueva) le cambia las notas sin tocar tu ritmo.

Una nota larga que queda chocando con un acorde nuevo se vuelve a atacar, suave, en la
nota del acorde más cercana.
"""

import logging
import random

from . import armonia

log = logging.getLogger("goa.tocado")

PULSOS_POR_COMPAS = 96
PULSOS_POR_PASO = 6
ESTILOS = ("goa", "acido", "mantra", "raga", "bajo")


class Tocado:
    def __init__(self):
        self.cfg = {}
        self.activo = False
        self.salida, self.canal = None, 0
        self.tonalidad = None
        self.vivas = {}          # tecla -> nota que suena por esa tecla
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

    # --- Configuración ---

    def configurar(self, cfg, tonalidad, enviar):
        destino = (cfg.get("salida"), int(cfg.get("canal", 4)) - 1)
        if (self.salida, self.canal) != destino or not cfg.get("activo"):
            self.apagar(enviar)
        self.cfg = dict(cfg)
        self.activo = bool(cfg.get("activo"))
        self.salida, self.canal = destino
        self.tonalidad = tonalidad
        if not self.activo:
            self.estado, self.abiertas = ("pausa" if self.grabadas else "libre"), {}

    # --- Elegir la nota ---

    def _rng(self, *clave):
        return random.Random(f"{self.cfg.get('seed', 'TC')}:{self.cfg.get('estilo')}:" + ":".join(map(str, clave)))

    def _registro(self):
        base = 36 if self.cfg.get("estilo") == "bajo" else 60
        return base + 12 * int(self.cfg.get("octava", 0))

    def elegir(self, tecla, velocidad, pulso_en_compas, momento, indice, previa):
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
        r = self._rng(indice, pulso_en_compas // PULSOS_POR_PASO)
        estilo = self.cfg.get("estilo", "goa")
        if estilo == "goa":
            if fuerte or previa is None:
                nota = ancla if r.random() < 0.6 else t.nota(ancla, 4, "escala")
            else:
                paso = r.choice((1, 1, 2, -1, -1, -2))
                nota = t.nota(previa, paso, "escala")
                if not ancla - 3 <= nota <= ancla + 14:
                    nota = t.nota(previa, -paso, "escala")
        elif estilo == "acido":
            if velocidad >= 100:
                nota = ancla + 12
            else:
                nota = t.nota(ancla, r.choice((0, 0, 0, 2, 6, -1, 4)), "escala")
        elif estilo == "mantra":
            motivo = self._rng("motivo").choice(((0, 2, 1), (0, -1, 2), (0, 4, 2), (0, 1, -1), (4, 2, 0)))
            nota = t.nota(ancla, motivo[indice % 3], "escala")
        elif estilo == "raga":
            if previa is None or fuerte:
                nota = t.nota(ancla, r.choice((0, 0, 4, 2)), "escala")
            else:
                nota = t.nota(previa, r.choice((1, -1, -1, 2, -2)), "escala")
                if not ancla - 5 <= nota <= ancla + 12:
                    nota = t.nota(ancla, 2, "escala")
        else:  # bajo
            if fuerte or previa is None:
                nota = ancla
            else:
                nota = r.choice((ancla, ancla + 12, ancla + 12, t.nota(ancla, 4, "escala")))
        if fuerte:
            nota = armonia.nota_del_acorde(nota, clases)
        return _limitar(_en_escala(t, nota))

    def _apoyatura(self, nota, pulso_en_compas):
        """Raga: en el tiempo, la nota llega desde la de arriba (un pulso antes)."""
        return self.cfg.get("estilo") == "raga" and self.cfg.get("modo") != "contorno" and pulso_en_compas % 24 < 3

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
        nota = self.elegir(tecla, velocidad, en_compas, momento, self.indice, previa)
        self.indice += 1
        self.ultima = (tick, nota)
        self.clases = momento.clases if momento is not None else None
        self._sonar(nota, velocidad, tecla, tick, en_compas if corriendo else 1, enviar)
        self.vivas[tecla] = nota
        if self.estado == "grabando":
            self.abiertas[tecla] = (tick - self.inicio, velocidad)

    def tecla_off(self, tecla, tick, enviar):
        nota = self.vivas.pop(tecla, None)
        if nota is not None and self.sonando.get(nota, (None,))[0] == tecla:
            del self.sonando[nota]
            enviar(self.salida, "note_off", self.canal, nota, 0)
        self.pendientes = [p for p in self.pendientes if p[3] != tecla]
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
        compases = max(8, min(32, int(self.cfg.get("compases", 8))))
        if que == "grabar":
            self.grabadas, self.abiertas, self.estado = [], {}, "armado"
            self.largo = compases * PULSOS_POR_COMPAS
        elif que == "parar":
            if self.estado in ("loop", "grabando", "armado"):
                self.estado = "pausa" if self.grabadas else "libre"
        elif que == "seguir":
            if self.grabadas:
                self.estado = "loop"
        elif que == "borrar":
            self.grabadas, self.abiertas, self.estado = [], {}, "libre"
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
        if tick % PULSOS_POR_COMPAS == 0:
            self._compas(tick, enviar)
        if tick % PULSOS_POR_PASO == 0:
            self._cambio_de_acorde(tick, momento_de(tick // PULSOS_POR_PASO), enviar)
        if self.estado == "loop" and self.activo and self.largo:
            dentro = (tick - self.inicio) % self.largo
            for i, (inicio, largo, vel, tecla) in enumerate(self.grabadas):
                if inicio == dentro:
                    momento = momento_de(tick // PULSOS_POR_PASO)
                    previa = self.ultima[1] if self.ultima is not None else None
                    nota = self.elegir(tecla, vel, tick % PULSOS_POR_COMPAS, momento, i, previa)
                    self.ultima = (tick, nota)
                    self.clases = momento.clases if momento is not None else None
                    self._sonar(nota, vel, ("loop", i), tick, tick % PULSOS_POR_COMPAS, enviar)
                    self.vencen.append((tick + largo, nota, ("loop", i)))

    def _compas(self, tick, enviar):
        if self.estado == "armado":
            self.estado, self.inicio = "grabando", tick
            # Lo que ya estabas apretando al empezar cuenta desde el uno.
            self.abiertas = {tecla: (0, 100) for tecla in self.vivas}
        elif self.estado == "grabando" and tick - self.inicio >= self.largo:
            for tecla, (inicio, vel) in self.abiertas.items():
                self.grabadas.append((inicio, max(1, self.largo - inicio), vel, tecla))
            self.abiertas = {}
            self._cuantizar()
            self.estado = "loop" if self.grabadas else "libre"
            self.inicio = tick
            log.info("Tocado: loop de %d compases con %d notas", self.largo // PULSOS_POR_COMPAS, len(self.grabadas))

    def _cuantizar(self):
        """A semicorcheas: el inicio al paso más cercano; el largo, al menos un paso."""
        vistas, notas = set(), []
        for inicio, largo, vel, tecla in sorted(self.grabadas):
            q = round(inicio / PULSOS_POR_PASO) * PULSOS_POR_PASO % self.largo
            d = max(PULSOS_POR_PASO, round(largo / PULSOS_POR_PASO) * PULSOS_POR_PASO)
            if q in vistas:
                continue  # dos notas en el mismo paso: queda la primera
            vistas.add(q)
            notas.append((q, d, vel, tecla))
        self.grabadas = sorted(notas)

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
        e = {"estado": self.estado, "notas": len(self.grabadas), "compases": self.largo // PULSOS_POR_COMPAS}
        if self.estado == "grabando" and self.inicio is not None:
            e["compas"] = (tick - self.inicio) // PULSOS_POR_COMPAS + 1
        if self.estado == "loop" and self.inicio is not None and self.largo:
            e["compas"] = (tick - self.inicio) % self.largo // PULSOS_POR_COMPAS + 1
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
