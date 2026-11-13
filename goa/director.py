"""Director: variación de mediano y largo plazo.

Cada `periodo` compases (16 o 32, siempre en el borde de una frase) el director
deshace lo que hizo en el período anterior y, según la *variación*, elige uno o
dos cambios nuevos para el período que empieza:

- **Variante hermana:** una secuencia toca su patrón con un 20 % de notas
  cambiadas (misma forma, otras alturas).
- **Vuelve un motivo:** una secuencia retoma un patrón que tocó hace uno o más
  períodos, transformado (corrido, una tercera arriba o en espejo).
- **Una octava arriba:** una secuencia sube una octava.
- **Cambio de roles:** la llamada pasa al sinte de la respuesta y al revés.
- **Pads solo guían:** los pads se callan un período (siguen guiando la armonía).
- **Protagonista:** un motor queda adelante y los otros dejan espacio (tocan
  menos notas).

Una secuencia congelada queda fuera: el director no la toca.

No toca la configuración: cambia los motores que suenan y todo vuelve solo al
terminar el período. Es determinista: la misma configuración da el mismo viaje.
"""

import copy
import random
from collections import deque

from . import generador

TIPOS = ("hermana", "recuerdo", "octava", "roles", "pads_guian", "protagonista")
TRANSFORMACIONES = ("corrido", "tercera", "espejo")


def transformar(patron, como):
    """Un motivo que vuelve, cambiado: corrido en el tiempo, una tercera arriba o en espejo."""
    nuevo = [dict(p) for p in patron]
    if como == "corrido":
        giro = max(1, len(nuevo) // 4)
        nuevo = nuevo[-giro:] + nuevo[:-giro]
        for i, p in enumerate(nuevo):
            p.pop("fuente", None)  # los matices (densidad, acentos) siguen al lugar, no a la nota
    elif como == "tercera":
        for p in nuevo:
            p["grado"] = p["grado"] + 2
    else:  # espejo: los saltos hacia arriba van hacia abajo
        for p in nuevo:
            p["grado"] = -p["grado"]
    return nuevo


class Director:
    def __init__(self):
        self.reiniciar()

    def reiniciar(self):
        self.efectos = []   # [(tipo, objetivo, extra)]
        self.memoria = {}   # índice de secuencia -> últimos patrones (uno por período)

    # --- Marcas en los motores (para no aplicar dos veces y poder deshacer) ---

    @staticmethod
    def _poner(obj, clave, cambios):
        marcas = obj.__dict__.setdefault("_director", {})
        if clave in marcas:
            return
        marcas[clave] = {k: getattr(obj, k) for k in cambios}
        for k, v in cambios.items():
            setattr(obj, k, v)

    @staticmethod
    def _sacar(obj, clave):
        marcas = obj.__dict__.get("_director", {})
        for k, v in marcas.pop(clave, {}).items():
            setattr(obj, k, v)

    @staticmethod
    def _poner_patron(s, clave, nuevo):
        if getattr(s, "_director_patron", None) is not None:
            return
        s._director_patron = (clave, s.patron)
        s.patron = nuevo

    @staticmethod
    def _sacar_patron(s):
        guardado = getattr(s, "_director_patron", None)
        if guardado is not None:
            s.patron = guardado[1]
            s._director_patron = None

    # --- Aplicar y deshacer ---

    def aplicar(self, motor):
        """Pone los cambios del período en los motores (también en los recién armados)."""
        for tipo, objetivo, extra in self.efectos:
            clave = (tipo, objetivo)
            if tipo in ("hermana", "recuerdo"):
                if objetivo < len(motor.secuencias):
                    self._poner_patron(motor.secuencias[objetivo], clave, extra)
            elif tipo == "octava":
                if objetivo < len(motor.secuencias):
                    s = motor.secuencias[objetivo]
                    self._poner(s, clave, {"octava": s.octava + 1})
            elif tipo == "roles":
                ll, re = motor.dialogo.llamada, motor.dialogo.respuesta
                a, b = (ll.salida, ll.canal, ll.octava), (re.salida, re.canal, re.octava)
                if "_director" in ll.__dict__ and clave in ll._director:
                    continue
                self._poner(ll, clave, dict(zip(("salida", "canal", "octava"), b)))
                self._poner(re, clave, dict(zip(("salida", "canal", "octava"), a)))
            elif tipo == "pads_guian":
                self._poner(motor.pads, clave, {"suenan": False})
            elif tipo == "protagonista":
                for i, s in enumerate(motor.secuencias):
                    if f"sec{i}" != objetivo and not s.bloqueada:
                        self._poner(s, clave, {"densidad": round(s.densidad * 0.6, 3)})
                if objetivo != "dialogo":
                    for v in (motor.dialogo.llamada, motor.dialogo.respuesta):
                        self._poner(v, clave, {"golpes": max(1, v.golpes - 1)})

    def quitar(self, motor):
        for tipo, objetivo, _ in self.efectos:
            clave = (tipo, objetivo)
            for s in motor.secuencias:
                self._sacar(s, clave)
                if tipo in ("hermana", "recuerdo"):
                    self._sacar_patron(s)
            for obj in (motor.pads, motor.dialogo.llamada, motor.dialogo.respuesta):
                self._sacar(obj, clave)
        self.efectos = []

    # --- Cada compás ---

    def compas(self, motor, compas, variacion, periodo, semilla):
        """Al inicio de cada compás. En el borde de un período cambia lo que hace."""
        if compas <= 0 or compas % periodo:
            self.aplicar(motor)
            return
        self.quitar(motor)
        for i, s in enumerate(motor.secuencias):
            self.memoria.setdefault(i, deque(maxlen=4)).append(copy.deepcopy(s.patron))
        if variacion > 0:
            self.efectos = self._elegir(motor, random.Random(f"director:{semilla}:{compas}"), variacion, compas)
        self.aplicar(motor)

    def _elegir(self, motor, rng, variacion, compas):
        secs = [i for i, s in enumerate(motor.secuencias) if s.activa]
        dialogo = motor.dialogo.activo and motor.dialogo.modo == "motor"
        otros = len(secs) + (1 if dialogo else 0) + (1 if motor.bajo.activo else 0)
        posibles = []
        for i in secs:
            s = motor.secuencias[i]
            if s.bloqueada:
                continue  # congelada: el director no la toca
            posibles.append(("hermana", i))
            viejos = [p for p in list(self.memoria.get(i, []))[:-1] if len(p) == len(s.patron) and p != s.patron]
            if viejos:
                posibles.append(("recuerdo", i))
            if s.octava < 2:
                posibles.append(("octava", i))
        if dialogo:
            posibles.append(("roles", None))
        if motor.pads.activo and motor.pads.suenan and otros >= 2:
            posibles.append(("pads_guian", None))
        candidatos = [f"sec{i}" for i in secs] + (["dialogo"] if dialogo else [])
        if len(candidatos) >= 2:
            posibles.append(("protagonista", None))
        cuantos = (1 if rng.random() < variacion else 0) + (1 if rng.random() < variacion - 0.5 else 0)
        efectos = []
        for _ in range(cuantos):
            libres = [p for p in posibles if p[1] is None or all(e[1] != p[1] for e in efectos)]
            libres = [p for p in libres if all(e[0] != p[0] for e in efectos)]
            if not libres:
                break
            tipo, objetivo = rng.choice(libres)
            extra = None
            if tipo == "hermana":
                s = motor.secuencias[objetivo]
                extra = generador.mutar(s.patron, f"{s.seed}~hermana", compas, 0.2, s.pedal)
            elif tipo == "recuerdo":
                s = motor.secuencias[objetivo]
                viejos = [p for p in list(self.memoria[objetivo])[:-1] if len(p) == len(s.patron) and p != s.patron]
                extra = transformar(viejos[0], rng.choice(TRANSFORMACIONES))
            elif tipo == "protagonista":
                objetivo = rng.choice(candidatos)
            efectos.append((tipo, objetivo, extra))
        return efectos

    def descripcion(self, motor):
        textos = []
        nombre = lambda i: motor.secuencias[i].nombre if i < len(motor.secuencias) else "?"  # noqa: E731
        for tipo, objetivo, _ in self.efectos:
            if tipo == "hermana":
                textos.append(f"{nombre(objetivo)}: variante hermana")
            elif tipo == "recuerdo":
                textos.append(f"{nombre(objetivo)}: vuelve un motivo")
            elif tipo == "octava":
                textos.append(f"{nombre(objetivo)}: una octava arriba")
            elif tipo == "roles":
                textos.append("Diálogo: cambian de sinte")
            elif tipo == "pads_guian":
                textos.append("Pads: solo guían")
            elif tipo == "protagonista":
                textos.append("Adelante: " + ("diálogo" if objetivo == "dialogo" else nombre(int(objetivo[3:]))))
        return textos
