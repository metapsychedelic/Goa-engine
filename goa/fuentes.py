"""Fuentes de la app guardadas en la Pi, para que el diseño se vea igual sin internet.

La primera vez que la Pi tiene internet baja las letras de Google Fonts (solo el
alfabeto latino, unos 150 KB en total) a goa/web/fuentes/. Después la app las sirve
desde la Pi y el teléfono las guarda en su caché. Sin internet no pasa nada: la app
usa la letra del sistema hasta que se puedan bajar.
"""

import logging
import re
import threading
import urllib.request
from pathlib import Path

log = logging.getLogger("goa")
CARPETA = Path(__file__).parent / "web" / "fuentes"
# archivo -> (familia en Google Fonts, peso)
FUENTES = {
    "plex-sans-400.woff2": ("IBM Plex Sans", 400),
    "plex-sans-500.woff2": ("IBM Plex Sans", 500),
    "plex-sans-600.woff2": ("IBM Plex Sans", 600),
    "plex-sans-700.woff2": ("IBM Plex Sans", 700),
    "plex-mono-500.woff2": ("IBM Plex Mono", 500),
    "plex-mono-700.woff2": ("IBM Plex Mono", 700),
    "megrim-400.woff2": ("Megrim", 400),
}
NOMBRE = re.compile(r"^[a-z0-9-]+\.woff2$")
# Google entrega woff2 solo a navegadores que lo entienden.
_AGENTE = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
           "Chrome/120.0 Safari/537.36")


def _bajar(url, tiempo=15):
    pedido = urllib.request.Request(url, headers={"User-Agent": _AGENTE})
    with urllib.request.urlopen(pedido, timeout=tiempo) as r:
        return r.read()


def url_latina(css, peso):
    """De la hoja de Google Fonts, la URL del archivo latino del peso pedido."""
    for comentario, bloque in re.findall(r"/\*\s*([\w-]+)\s*\*/\s*@font-face\s*\{([^}]*)\}", css):
        if comentario != "latin":
            continue
        p = re.search(r"font-weight:\s*(\d+)", bloque)
        u = re.search(r"url\((https://[^)]+\.woff2)\)", bloque)
        if p and u and int(p.group(1)) == peso:
            return u.group(1)
    return None


def faltan(carpeta=CARPETA):
    return [n for n in FUENTES if not (carpeta / n).is_file()]


def asegurar(carpeta=CARPETA, bajar=_bajar):
    """Baja las fuentes que falten. Devuelve cuántas bajó; si no hay internet, 0."""
    pendientes = faltan(carpeta)
    if not pendientes:
        return 0
    carpeta.mkdir(parents=True, exist_ok=True)
    bajadas = 0
    hojas = {}
    for nombre in pendientes:
        familia, peso = FUENTES[nombre]
        try:
            if familia not in hojas:
                pesos = ";".join(str(p) for f, p in sorted(FUENTES.values()) if f == familia)
                hojas[familia] = bajar("https://fonts.googleapis.com/css2?family="
                                       + familia.replace(" ", "+") + ":wght@" + pesos + "&display=swap").decode()
            url = url_latina(hojas[familia], peso)
            if not url:
                log.info("Fuentes: no encontré %s %s en Google Fonts", familia, peso)
                continue
            datos = bajar(url)
            if not datos.startswith(b"wOF2"):
                continue
            temporal = carpeta / (nombre + ".tmp")
            temporal.write_bytes(datos)
            temporal.replace(carpeta / nombre)
            bajadas += 1
        except Exception as e:  # sin internet o Google no responde: se intenta en el próximo arranque
            log.info("Fuentes: no se pudieron bajar ahora (%s); la app usa la letra del sistema", e)
            break
    if bajadas:
        log.info("Fuentes: %d guardadas en la Pi", bajadas)
    return bajadas


def asegurar_en_segundo_plano():
    if faltan():
        threading.Thread(target=asegurar, daemon=True, name="fuentes").start()


def leer(nombre, carpeta=CARPETA):
    """Bytes de una fuente guardada, o None (nombre raro o no bajada aún)."""
    if not NOMBRE.match(nombre) or nombre not in FUENTES:
        return None
    ruta = carpeta / nombre
    return ruta.read_bytes() if ruta.is_file() else None
