"""Forma: escenas, transiciones graduales y energía.

Una escena es una foto del carácter musical de todo el motor (géneros, escala,
progresión, estilos, variantes y ajustes de cada motor, qué motores suenan y su
energía). No guarda destinos ni canales: si después cambias de cable, las escenas
siguen sirviendo.

Al lanzar una escena, el motor no salta: pasa a ella en unos compases.
- Lo continuo (densidad, largo de notas, oscuridad, swing, tensión, fuerza…) se
  mueve un poco en cada compás.
- Lo que no se puede mover de a poco (estilo, variante, progresión, escala…)
  cambia en el último compás de la transición, en el borde de la frase.
- Los motores que se prenden entran de a uno; los que se apagan salen de a uno.
- Si cambia la tonalidad, los compases antes del cambio suena un acorde puente
  que es de las dos (ver armonia.puente), y la progresión nueva parte en su i.

La energía (0 a 1, 0,5 = tal como dejaste cada motor) mueve juntas densidad,
fuerza, acentos, notas fantasma, evolución, pulso de los pads, espacio del
diálogo y tensión. Al moverla, el motor llega de a poco: como mucho un 10 % por
compás.
"""

import copy
import json

SECCIONES = ("musica", "pads", "bajo", "dialogo", "llamada", "respuesta")
ENRUTAMIENTO = frozenset(("salida", "canal", "disparo", "escucha", "nombre"))
# Floats que no se pueden mover de a poco: rehacen el patrón entero.
DISCRETOS = frozenset((("secuencia", "pedal"), ("bajo", "movimiento")))
# Enteros que sí se mueven de a poco.
ENTEROS_CONTINUOS = frozenset(("velocidad", "acento", "golpes", "rasgueo"))
TRANSICIONES = (1, 4, 8, 16)
MAX_ESCENAS = 8
PASO_ENERGIA = 0.1  # lo más que se mueve la energía en un compás

# Orden en que entran (y, al revés, salen) los motores en una transición:
# primero la armonía, al final el bajo.
ORDEN_ENTRADA = ("pads", "secuencia", "dialogo", "bajo")
ORDEN_SALIDA = ("secuencia", "dialogo", "bajo", "pads")


# --- Escenas ---

def foto(cfg):
    """El carácter musical de una configuración, sin destinos ni canales."""
    datos = {s: {k: v for k, v in cfg[s].items() if k not in ENRUTAMIENTO} for s in SECCIONES}
    datos["secuencia"] = [{k: v for k, v in s.items() if k not in ENRUTAMIENTO - {"nombre"}} for s in cfg["secuencia"]]
    return datos


def escena_de(cfg, nombre):
    return {"nombre": nombre.strip()[:24] or "Escena", "energia": cfg["forma"]["energia"],
            "datos": json.dumps(foto(cfg), ensure_ascii=False, separators=(",", ":"))}


def mezclar(cfg, escena):
    """La configuración actual con el carácter de la escena (los destinos quedan)."""
    datos = json.loads(escena["datos"]) if isinstance(escena["datos"], str) else escena["datos"]
    nueva = copy.deepcopy(cfg)
    for s in SECCIONES:
        nueva[s].update({k: v for k, v in (datos.get(s) or {}).items() if k not in ENRUTAMIENTO})
    secuencias = datos.get("secuencia") or []
    for i, s in enumerate(secuencias):
        if i < len(nueva["secuencia"]):
            nueva["secuencia"][i].update({k: v for k, v in s.items() if k not in ENRUTAMIENTO})
        else:
            nueva["secuencia"].append(dict(s))  # con los destinos que tenía al guardarla
    for s in nueva["secuencia"][len(secuencias):]:
        s["activa"] = False  # secuencias que la escena no tenía: calladas
    nueva["forma"]["energia"] = escena.get("energia", nueva["forma"]["energia"])
    return nueva


def resumen(escena):
    """Texto corto de una escena para la app: género y qué suena."""
    d = json.loads(escena["datos"]) if isinstance(escena["datos"], str) else escena["datos"]
    suenan = []
    if d.get("pads", {}).get("activo"):
        suenan.append("pads")
    if d.get("bajo", {}).get("activo"):
        suenan.append("bajo")
    suenan += [s.get("nombre", "?") for s in d.get("secuencia", []) if s.get("activa")]
    if d.get("dialogo", {}).get("activo"):
        suenan.append("diálogo")
    genero = {"goa": "Goa", "psy_chill": "Psy chill", "chillgressive": "Chillgressive",
              "chillout": "Chillout", "ambient": "Ambient"}.get(d.get("musica", {}).get("genero"), "")
    return f"{genero} · {', '.join(suenan) or 'silencio'}"


# --- Energía ---

def _limitar(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def _escala(x, f):
    """f de -0,5 a 0,5: multiplica tu ajuste, del 40 % (calma) al 160 % (clímax).

    Multiplica, no rellena: una densidad baja sigue siendo baja con la energía
    arriba, y en 0 queda en 0. Tu ajuste siempre manda."""
    return x * (1 + 1.2 * f)


def energizar(cfg, energia):
    """La configuración con la energía aplicada. Con 0,5 queda tal cual."""
    f = _limitar(energia) - 0.5
    if abs(f) < 1e-9:
        return cfg
    c = copy.deepcopy(cfg)
    alto = max(f, 0.0)
    m = c["musica"]
    m["tension"] = round(_limitar(m["tension"] + 0.4 * f), 3)
    for s in c["secuencia"]:
        s["densidad"] = round(_limitar(_escala(s["densidad"], f)), 3)
        s["acentos"] = round(_limitar(s["acentos"] + 0.3 * f), 3)
        s["velocidad"] = int(_limitar(s["velocidad"] + round(20 * f), 1, 127))
        if s["mutacion"] > 0:
            s["mutacion"] = round(_limitar(s["mutacion"] + 0.3 * alto), 3)
    b = c["bajo"]
    b["densidad"] = round(_limitar(_escala(b["densidad"], f)), 3)
    b["fantasmas"] = round(_limitar(_escala(b["fantasmas"], f)), 3)
    b["acentos"] = round(_limitar(b["acentos"] + 0.3 * f), 3)
    b["velocidad"] = int(_limitar(b["velocidad"] + round(16 * f), 1, 127))
    if b["evolucion"] > 0:
        b["evolucion"] = round(_limitar(b["evolucion"] + 0.4 * alto), 3)
    p = c["pads"]
    p["velocidad"] = int(_limitar(p["velocidad"] + round(24 * f), 1, 127))
    p["suspensiones"] = round(_limitar(p["suspensiones"] - 0.6 * f), 3)  # más suspensiones en la calma
    if p["pulso"] > 0:
        p["pulso"] = int(_limitar(round(p["pulso"] * (1 + 1.2 * f)), 1, 8))
    d = c["dialogo"]
    d["espacio"] = int(_limitar(d["espacio"] + round(-4 * f), 0, 3))
    if d["evolucion"] > 0:
        d["evolucion"] = round(_limitar(d["evolucion"] + 0.4 * alto), 3)
    for voz in ("llamada", "respuesta"):
        v = c[voz]
        v["golpes"] = int(_limitar(round(v["golpes"] * (1 + f)), 1, 16))
        v["velocidad"] = int(_limitar(v["velocidad"] + round(20 * f), 1, 127))
    return c


# --- Transiciones ---

def _mezcla(seccion, k, a, b, t):
    if a == b or t >= 1:
        return b
    if isinstance(a, bool) or isinstance(b, bool):
        return a
    if isinstance(a, float) and isinstance(b, (int, float)) and (seccion, k) not in DISCRETOS:
        return round(a + (b - a) * t, 4)
    if isinstance(a, int) and isinstance(b, int) and k in ENTEROS_CONTINUOS:
        return round(a + (b - a) * t)
    return a


ACTIVO = {"pads": "activo", "bajo": "activo", "dialogo": "activo"}


def _motores(cfg):
    """{clave: suena} de cada motor."""
    m = {k: bool(cfg[k][v]) for k, v in ACTIVO.items()}
    m.update({f"sec{i}": bool(s["activa"]) for i, s in enumerate(cfg["secuencia"])})
    return m


def _orden(clave, orden):
    tipo = "secuencia" if clave.startswith("sec") else clave
    return (orden.index(tipo), clave)


def cambia_armonia(a, b):
    """True si la transición cambia la tonalidad o la progresión (la nueva parte en su i)."""
    ma, mb, pa, pb = a["musica"], b["musica"], a["pads"], b["pads"]
    return ((ma["tonica"], ma["escala"]) != (mb["tonica"], mb["escala"])
            or any(pa[k] != pb[k] for k in ("progresion", "cambia_cada", "base")))


def cambia_tono(a, b):
    return (a["musica"]["tonica"], a["musica"]["escala"]) != (b["musica"]["tonica"], b["musica"]["escala"])


class Transicion:
    """Paso gradual de `origen` a `destino` en `compases` compases desde `inicio`.

    En el compás inicio + i el avance es (i + 1) / compases: el último compás
    (inicio + compases - 1) ya es el destino completo."""

    def __init__(self, origen, destino, inicio, compases, escena=None):
        self.origen = copy.deepcopy(origen)
        self.destino = copy.deepcopy(destino)
        self.inicio = inicio
        self.compases = max(1, int(compases))
        self.escena = escena
        self.umbrales = self._umbrales()

    @property
    def fin(self):
        return self.inicio + self.compases - 1

    def _umbrales(self):
        """Avance (0 a 1) en que cada motor que se prende o se apaga lo hace."""
        a, b = _motores(self.origen), _motores(self.destino)
        entran = sorted((k for k in b if b[k] and not a.get(k)), key=lambda k: _orden(k, ORDEN_ENTRADA))
        salen = sorted((k for k in a if a[k] and not b.get(k)), key=lambda k: _orden(k, ORDEN_SALIDA))
        umbrales = {}
        for lista in (entran, salen):
            for j, k in enumerate(lista):
                umbrales[k] = (j + 1) / (len(lista) + 1)
        return umbrales

    def avance(self, compas):
        return max(0.0, min(1.0, (compas - self.inicio + 1) / self.compases))

    def terminada(self, compas):
        return compas >= self.fin

    def puente(self, compas):
        """True en los compases del acorde puente (antes del cambio de tonalidad)."""
        if not cambia_tono(self.origen, self.destino) or self.compases < 2:
            return False
        largo = min(2, self.compases - 1)
        return self.fin - largo <= compas < self.fin

    def config(self, compas):
        t = self.avance(compas)
        if t >= 1:
            return copy.deepcopy(self.destino)
        if compas < self.inicio:
            return copy.deepcopy(self.origen)
        a, b = self.origen, self.destino
        c = copy.deepcopy(b)
        for s in SECCIONES:
            c[s] = {k: _mezcla(s, k, a[s].get(k, v), v, t) for k, v in b[s].items()}
        largo = max(len(a["secuencia"]), len(b["secuencia"]))
        secuencias = []
        for i in range(largo):
            sa = a["secuencia"][i] if i < len(a["secuencia"]) else dict(b["secuencia"][i], activa=False)
            sb = b["secuencia"][i] if i < len(b["secuencia"]) else dict(sa, activa=False)
            secuencias.append({k: _mezcla("secuencia", k, sa.get(k, v), v, t) for k, v in sb.items()})
        c["secuencia"] = secuencias
        # Los motores que se prenden o se apagan lo hacen de a uno.
        for clave, umbral in self.umbrales.items():
            suena = _motores(b)[clave] if t >= umbral else _motores(a).get(clave, False)
            if clave.startswith("sec"):
                c["secuencia"][int(clave[3:])]["activa"] = suena
            else:
                c[clave][ACTIVO[clave]] = suena
        c["forma"] = dict(b["forma"], energia=round(a["forma"]["energia"] + (b["forma"]["energia"] - a["forma"]["energia"]) * t, 4))
        return c


# --- Piloto automático ---

# Cada sección: compases (con duración normal), energía al empezar y al terminar,
# motores que calla y si la energía llega de golpe (el drop entra en el uno).
SECCIONES_PILOTO = {
    "intro": {"nombre": "Intro", "compases": 16, "energia": (0.2, 0.3), "callan": ("bajo", "dialogo")},
    "build": {"nombre": "Build", "compases": 16, "energia": (0.35, 0.75), "callan_mitad": ("dialogo",)},
    "climax": {"nombre": "Clímax", "compases": 32, "energia": (0.85, 0.85)},
    "break": {"nombre": "Break", "compases": 8, "energia": (0.25, 0.15), "callan": ("bajo", "secuencias"), "golpe": True},
    "drop": {"nombre": "Drop", "compases": 32, "energia": (0.9, 0.8), "golpe": True},
}
PLAN = ("intro", "build", "climax", "break", "drop")
VUELTA = 1  # después del drop vuelve al build
DURACIONES = {"corta": 0.5, "normal": 1.0, "larga": 2.0}


def largo_seccion(clave, duracion):
    return max(4, int(SECCIONES_PILOTO[clave]["compases"] * DURACIONES.get(duracion, 1.0)))


def con_piloto(cfg, clave, avance):
    """La configuración con las capas de la sección del piloto (calla motores, prepara el break)."""
    s = SECCIONES_PILOTO[clave]
    c = copy.deepcopy(cfg)
    callan = set(s.get("callan", ()))
    if avance < 0.5:
        callan |= set(s.get("callan_mitad", ()))
    for motor in callan:
        if motor == "secuencias":
            for sec in c["secuencia"]:
                sec["activa"] = False
        else:
            c[motor][ACTIVO[motor]] = False
    if clave == "break" and c["pads"]["activo"]:
        # Break: los pads crecen, sostenidos, con más suspensiones y entrada escalonada.
        p = c["pads"]
        p.update(suenan=True, pulso=0, suspensiones=max(p["suspensiones"], 0.7), rasgueo=max(p["rasgueo"], 6))
    return c


class Conductor:
    """Lleva la transición en curso, el piloto y la energía, y da la configuración que suena."""

    def __init__(self):
        self.transicion = None
        self.energia = None  # energía que suena (llega de a poco a la pedida)
        self.piloto = None   # {"i": índice en PLAN, "inicio": compás} o None
        self.saltar_a = None  # sección pedida desde la app

    def reiniciar(self):
        self.transicion = None
        self.energia = None
        self.piloto = None
        self.saltar_a = None

    def _avanzar_piloto(self, base, compas):
        f = base.get("forma", {})
        if not f.get("piloto"):
            self.piloto = None
            return False
        duracion = f.get("duracion", "normal")
        antes = None if self.piloto is None else self.piloto["i"]
        if self.saltar_a is not None:
            self.piloto = {"i": PLAN.index(self.saltar_a), "inicio": compas}
            self.saltar_a = None
        elif self.piloto is None:
            if compas % 4:
                return False  # arranca en el borde de una frase
            # Si ya suena con energía, parte en el build; si no, en la intro.
            self.piloto = {"i": 1 if f.get("energia", 0.5) >= 0.5 else 0, "inicio": compas}
        else:
            while compas >= self.piloto["inicio"] + largo_seccion(PLAN[self.piloto["i"]], duracion):
                self.piloto["inicio"] += largo_seccion(PLAN[self.piloto["i"]], duracion)
                self.piloto["i"] = self.piloto["i"] + 1 if self.piloto["i"] + 1 < len(PLAN) else VUELTA
        return self.piloto["i"] != antes  # True si empezó una sección

    def seccion(self, base, compas):
        """(clave, avance de 0 a 1, compás dentro de la sección, largo) o None."""
        if self.piloto is None:
            return None
        clave = PLAN[self.piloto["i"]]
        largo = largo_seccion(clave, base.get("forma", {}).get("duracion", "normal"))
        dentro = max(0, compas - self.piloto["inicio"])
        return clave, min(1.0, dentro / max(1, largo - 1)), dentro, largo

    def lanzar(self, origen, destino, inicio, compases, escena=None):
        self.transicion = Transicion(origen, destino, inicio, compases, escena)

    def objetivo(self, base, compas):
        sec = self.seccion(base, compas)
        if sec is not None:
            a, b = SECCIONES_PILOTO[sec[0]]["energia"]
            return round(a + (b - a) * sec[1], 4)
        cfg = self.transicion.config(compas) if self.transicion else base
        return cfg["forma"]["energia"]

    def avanzar(self, base, compas):
        """Al inicio de cada compás: avanza el piloto y la energía da un paso hacia la pedida."""
        nueva_seccion = self._avanzar_piloto(base, compas)
        meta = self.objetivo(base, compas)
        golpe = nueva_seccion and SECCIONES_PILOTO[PLAN[self.piloto["i"]]].get("golpe")
        if self.energia is None or golpe:
            self.energia = meta  # el break y el drop entran de golpe, en el uno
        else:
            self.energia = round(self.energia + max(-PASO_ENERGIA, min(PASO_ENERGIA, meta - self.energia)), 4)

    def terminar_si_corresponde(self, compas):
        if self.transicion is not None and self.transicion.terminada(compas):
            self.transicion = None

    def efectiva(self, base, compas):
        cfg = self.transicion.config(compas) if self.transicion else base
        sec = self.seccion(base, compas)
        if sec is not None:
            cfg = con_piloto(cfg, sec[0], sec[1])
        energia = self.energia if self.energia is not None else cfg["forma"]["energia"]
        return energizar(cfg, energia)
