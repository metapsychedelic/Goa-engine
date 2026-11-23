"""Deshacer: la historia de cambios de la app, un paso a la vez.

Cada paso guarda la configuración de antes y la de después (las mismas que usó la app:
no se copia nada, así anotar dentro del candado no cuesta). Una configuración que dejó
de ser la activa ya no se modifica, y lo que se cambia en vivo sobre la activa (energía,
piloto, escena elegida, clips) o es de la biblioteca (escenas, partes, clips guardados) o
se cambia reemplazando el objeto (web._cambiar_fila). Por eso la foto sigue fiel.

Deshacer devuelve solo lo que ese paso cambió (una sección o una secuencia), y solo si
sigue como ese paso la dejó: si después la cambió un clip, una escena o la canción,
deshacer pisaría eso, y avisa en vez de hacerlo.
"""

import time

MAX_PASOS = 50
JUNTAR = 1.5   # segundos: mover un deslizador manda varios cambios seguidos; son un solo paso

# Lo que se puede deshacer. Las escenas, partes, clips guardados, la canción y la app
# tienen sus propios botones (y confirmaciones), y no entran.
SECCIONES = ("musica", "armonia_tema", "entrada", "thru", "pads", "bajo", "dialogo", "llamada", "respuesta", "fx", "texturas", "looper", "tocado", "obertura", "forma")
# De la forma, lo que se toca en vivo (el control de energía, el piloto, la escena que suena) no es un paso.
FORMA_EN_VIVO = ("energia", "piloto", "escena", "duracion")

NOMBRES = {"musica": "Música", "armonia_tema": "Armonía del tema", "entrada": "Entrada", "thru": "Thru", "pads": "Pads", "bajo": "Bajo",
           "dialogo": "Llamada y respuesta", "llamada": "Llamada y respuesta", "respuesta": "Llamada y respuesta",
           "fx": "FX", "texturas": "Texturas", "looper": "Looper", "tocado": "Tocado", "obertura": "Obertura", "forma": "Forma"}
ORIGENES = {"fabrica": "ajustes de fábrica", "genero": "género", "limpiar": "limpiar"}


class Conflicto(Exception):
    pass


def anotar(pasos, antes, despues, origen, estado=None):
    """Suma un paso. Cambios seguidos de controles (menos de JUNTAR s) se juntan en uno."""
    ahora = time.monotonic()
    ultimo = pasos[-1] if pasos else None
    if (origen == "config" and ultimo and ultimo["origen"] == "config" and ultimo["despues"] is antes
            and ahora - ultimo["t"] < JUNTAR):
        ultimo["despues"], ultimo["t"] = despues, ahora
        return
    pasos.append({"antes": antes, "despues": despues, "origen": origen, "estado": estado, "t": ahora})
    del pasos[:-MAX_PASOS]


def _forma(f):
    return {k: v for k, v in (f or {}).items() if k not in FORMA_EN_VIVO}


def _partes(cfg):
    """Las piezas que se comparan y se devuelven: cada sección y cada secuencia."""
    piezas = {s: cfg.get(s) for s in SECCIONES}
    piezas["forma"] = _forma(cfg.get("forma"))
    filas = cfg.get("secuencia") or []
    piezas["secuencias"] = len(filas)
    for i, f in enumerate(filas):
        piezas[("secuencia", i)] = f
    return piezas


def cambios(antes, despues):
    a, d = _partes(antes), _partes(despues)
    if a["secuencias"] != d["secuencias"]:
        # Se agregó o se quitó una secuencia: vuelve la lista entera.
        claves = [k for k in a if not isinstance(k, tuple) and k != "secuencias" and a[k] != d.get(k)]
        return claves + ["secuencia"]
    return [k for k in a if k != "secuencias" and a[k] != d.get(k)]


def _valor(cfg, clave):
    if clave == "secuencia":
        return cfg.get("secuencia")
    if isinstance(clave, tuple):
        filas = cfg.get("secuencia") or []
        return filas[clave[1]] if clave[1] < len(filas) else None
    if clave == "forma":
        return _forma(cfg.get("forma"))
    return cfg.get(clave)


def describir(claves, antes, despues, origen):
    nombres = []
    for c in claves:
        if c == "secuencia":
            n = "Secuencias"
        elif isinstance(c, tuple):
            n = f"Secuencia {(despues['secuencia'][c[1]] or {}).get('nombre') or c[1] + 1}"
        else:
            n = NOMBRES.get(c, c)
        if n not in nombres:
            nombres.append(n)
    texto = ", ".join(nombres[:3]) + ("…" if len(nombres) > 3 else "")
    if origen in ORIGENES:
        return f"{texto} ({ORIGENES[origen]})"
    if len(claves) == 1:  # un solo control: cuál
        a, d = _valor(antes, claves[0]), _valor(despues, claves[0])
        if isinstance(a, dict) and isinstance(d, dict):
            distintos = [k for k in d if a.get(k) != d.get(k)]
            if len(distintos) == 1:
                texto += f" · {distintos[0].replace('_', ' ')}"
    return texto


def deshacer(paso, actual):
    """La configuración `actual` con lo que cambió `paso` de vuelta como estaba antes.
    Devuelve (configuración sin normalizar, texto de lo deshecho). Conflicto si eso
    cambió después del paso."""
    antes, despues = paso["antes"], paso["despues"]
    claves = cambios(antes, despues)
    if not claves:
        return dict(actual), "nada (ese paso no cambiaba nada)"
    otras = [c for c in claves if _valor(actual, c) != _valor(despues, c)]
    if otras:
        que = describir(otras, antes, despues, None).split(" · ")[0]
        raise Conflicto(f"No se puede deshacer: {que} cambió después (un clip, una escena o la canción)")
    nueva = dict(actual)
    filas = None
    for c in claves:
        if c == "secuencia":
            filas = list(antes.get("secuencia") or [])
        elif isinstance(c, tuple):
            if filas is None:
                filas = list(actual.get("secuencia") or [])
            filas[c[1]] = antes["secuencia"][c[1]]
        elif c == "forma":
            nueva["forma"] = dict(actual.get("forma") or {}, **_forma(antes.get("forma")))
        else:
            nueva[c] = antes.get(c)
    if filas is not None:
        nueva["secuencia"] = filas
    return nueva, describir(claves, antes, despues, paso["origen"])
