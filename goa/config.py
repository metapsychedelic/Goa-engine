"""Leer, validar y guardar la configuración (config.toml)."""

import os
import tempfile
import tomllib

import json

from . import armonia, bajo, dialogo, forma, generador, generos, pads
from .escalas import ESCALAS, nombre_a_clase

MAX_SECUENCIAS = 8
MAX_CLIPS = 64

# clave: (tipo, valor por defecto, mínimo, máximo u opciones)
ESQUEMA_SECCIONES = {
    "app": {"puerto": (int, 8080, 1024, 65535), "proyecto": (str, "", None, None)},
    "entrada": {
        "puerto": (str, "Circuit", None, None),
        "canal_disparo": (int, 4, 1, 16),
        "nota_maxima": (int, 4, 0, 64),
    },
    "thru": {
        "activo": (bool, False, None, None),
        "salida": (str, "USB MIDI", None, None),
    },
    "musica": {
        "tonica": (str, "F", None, None),
        "escala": (str, "frigio", None, tuple(ESCALAS)),
        "cambio_de_nota": (str, "paso", None, ("paso", "compas")),
        "adaptacion": (str, "escala", None, ("escala", "transponer")),
        "seguir_pads": (bool, False, None, None),
        "genero": (str, "goa", None, generos.ORDEN),
        "desplazamiento": (float, 0.0, 0.0, 1.0),
        "armonia": (str, "guiada", None, armonia.MODOS),
        "tension": (float, 0.3, 0.0, 1.0),
        "anticipar": (bool, True, None, None),
    },
    "pads": {
        "activo": (bool, False, None, None),
        "salida": (str, "CH345", None, None),
        "canal": (int, 3, 1, 16),
        "base": (str, "nota", None, pads.BASES),
        "progresion": (str, "i_bII", None, tuple(pads.PROGRESIONES)),
        "acorde": (str, "menor_add9", None, tuple(pads.ACORDES)),
        "cambia_cada": (int, 16, 1, 64),
        "voces": (int, 4, 2, 6),
        "octava": (int, 0, -2, 2),
        "apertura": (str, "abierta", None, pads.APERTURAS),
        "variacion": (float, 0.15, 0.0, 1.0),
        "ataque": (str, "ligado", None, pads.ATAQUES),
        "drone": (bool, False, None, None),
        "textura": (str, "acordes", None, pads.TEXTURAS),
        "rasgueo": (int, 1, 0, 24),
        "pulso": (int, 0, 0, 8),
        "suenan": (bool, True, None, None),
        "suspensiones": (float, 0.3, 0.0, 1.0),
        "genero": (str, "goa", None, generos.ORDEN),
        "velocidad": (int, 80, 1, 127),
        "seed": (str, "P-1C88", None, None),
        "disparo": (int, 0, 0, 16),
    },
    "dialogo": {
        "activo": (bool, False, None, None),
        "modo": (str, "motor", None, dialogo.MODOS),
        "forma": (str, "entrelazado", None, dialogo.FORMAS),
        "rejilla": (str, "corcheas", None, tuple(dialogo.REJILLAS)),
        "espacio": (int, 1, 0, 3),
        "compases_turno": (int, 2, 1, 8),
        "disparo": (int, 0, 0, 16),
        "escucha": (int, 4, 1, 16),
        "seguir_pads": (bool, True, None, None),
        "evolucion": (float, 0.5, 0.0, 1.0),
        "mutar_cada": (int, 4, 1, 16),
        "seed": (str, "CR-0001", None, None),
        "genero": (str, "goa", None, generos.ORDEN),
        "armonia": (str, "general", None, armonia.MODOS_MOTOR),
    },
}


def _esquema_voz(salida, canal, golpes, gate, velocidad):
    return {
        "salida": (str, salida, None, None),
        "canal": (int, canal, 1, 16),
        "golpes": (int, golpes, 1, 16),
        "octava": (int, 1, -3, 3),
        "oscuridad": (float, 0.7, 0.0, 1.0),
        "gate": (float, gate, 0.05, 1.0),
        "velocidad": (int, velocidad, 1, 127),
        "vel_random": (float, 0.15, 0.0, 1.0),
        "desplazamiento": (float, -1.0, -1.0, 1.0),  # menos de 0 = usa el general
    }


ESQUEMA_SECCIONES["llamada"] = _esquema_voz("FM-1", 4, 3, 0.5, 100)
ESQUEMA_SECCIONES["respuesta"] = _esquema_voz("MicroFreak", 3, 2, 0.6, 92)
ESQUEMA_SECCIONES["bajo"] = {
    "activo": (bool, False, None, None),
    "salida": (str, "CH345", None, None),
    "canal": (int, 4, 1, 16),
    "disparo": (int, 0, 0, 16),            # canal de su nota larga; 0 = el general
    "genero": (str, "goa", None, generos.ORDEN),
    "estilo": (str, "rolling", None, bajo.ESTILOS),
    "armonia": (str, "general", None, armonia.MODOS_MOTOR),
    "movimiento": (float, 0.3, 0.0, 1.0),
    "evolucion": (float, 0.0, 0.0, 1.0),
    "mutar_cada": (int, 4, 1, 16),
    "transponer": (int, 0, -7, 7),       # grados de escala
    "densidad": (float, 1.0, 0.0, 1.0),
    "swing": (float, 0.0, 0.0, 0.5),
    "slide": (float, 0.0, 0.0, 1.0),
    "acentos": (float, 0.2, 0.0, 1.0),
    "fantasmas": (float, 0.0, 0.0, 1.0),
    "remates": (bool, True, None, None),
    "frase": (int, 4, 1, 8),
    "octava": (int, 0, -2, 2),
    "gate": (float, 0.6, 0.05, 1.0),
    "velocidad": (int, 100, 1, 127),
    "vel_random": (float, 0.1, 0.0, 1.0),
    "seed": (str, "B-0001", None, None),
}

ESQUEMA_SECCIONES["forma"] = {
    "energia": (float, 0.5, 0.0, 1.0),       # 0,5 = cada motor tal como lo dejaste
    "transicion": (int, 8, 1, 16),           # compases para pasar de una escena a otra
    "escena": (int, -1, -1, forma.MAX_ESCENAS - 1),  # la última escena lanzada (-1 = ninguna)
    "variacion": (float, 0.4, 0.0, 1.0),     # cuánto cambia el director en cada período
    "periodo": (int, 16, 8, 32),             # compases de cada período del director
    "piloto": (bool, False, None, None),     # piloto automático: intro, build, clímax, break, drop
    "duracion": (str, "normal", None, tuple(forma.DURACIONES)),
}

ESQUEMA_ESCENA = {
    "nombre": (str, "Escena", None, None),
    "energia": (float, 0.5, 0.0, 1.0),
}
MAX_DATOS_ESCENA = 60000

# Un clip de diálogo guarda la conversación completa, con quién llama y los destinos,
# para que al lanzarlo entre tal como se armó. Las voces van con prefijo para que
# quede plano en el archivo: llamada_salida, respuesta_escala...
VOCES = ("llamada", "respuesta")
ESQUEMA_CLIP_DIALOGO = dict(
    {"nombre": (str, "Diálogo", None, None)},
    **{k: v for k, v in ESQUEMA_SECCIONES["dialogo"].items() if k != "activo"},
    **{f"{voz}_{k}": v for voz in VOCES for k, v in ESQUEMA_SECCIONES[voz].items()},
)

ESQUEMA_SECUENCIA = {
    "nombre": (str, "A", None, None),
    "disparo": (int, 0, 0, 16),
    "activa": (bool, True, None, None),
    "salida": (str, "FM-1", None, None),
    "canal": (int, 1, 1, 16),
    "genero": (str, "goa", None, generos.ORDEN),
    "armonia": (str, "general", None, armonia.MODOS_MOTOR),
    "estilo": (str, "rolling", None, generador.ESTILOS),
    "posicion": (str, "offbeat", None, generador.POSICIONES),
    "relacion": (str, "unisono", None, tuple(generador.RELACIONES)),
    "octava": (int, 0, -3, 3),
    "largo": (int, 16, 2, 64),
    "gate": (float, 0.55, 0.05, 1.0),
    "pedal": (float, 0.5, 0.0, 1.0),
    "seed": (str, "goa", None, None),
    "mutacion": (float, 0.0, 0.0, 1.0),
    "mutar_cada": (int, 8, 1, 64),
    "bloqueada": (bool, False, None, None),
    "velocidad": (int, 96, 1, 127),
    "acento": (int, 124, 1, 127),
    "densidad": (float, 1.0, 0.0, 1.0),
    "gate_random": (float, 0.0, 0.0, 1.0),
    "vel_random": (float, 0.0, 0.0, 1.0),
    "swing": (float, 0.0, 0.0, 0.5),
    "slide": (float, 0.0, 0.0, 1.0),
    "acentos": (float, 0.0, 0.0, 1.0),
    "saltos": (float, 0.0, 0.0, 1.0),
    "repeticion": (float, 0.0, 0.0, 1.0),
    "largas": (float, 0.0, 0.0, 1.0),
}


# Un clip guarda el carácter musical de una secuencia; el destino lo pone la fila
# del disparador donde se lanza.
CLAVES_DESTINO = ("disparo", "activa", "salida", "canal")
ESQUEMA_CLIP = {k: v for k, v in ESQUEMA_SECUENCIA.items() if k not in CLAVES_DESTINO}


class ConfigError(ValueError):
    pass


def _valor(clave, valor, esquema):
    tipo, defecto, minimo, extra = esquema
    if valor is None:
        return defecto
    try:
        if tipo is bool:
            if isinstance(valor, str):
                valor = valor.lower() in ("true", "1", "si", "sí")
            return bool(valor)
        valor = tipo(valor)
    except (TypeError, ValueError):
        raise ConfigError(f"Valor inválido para {clave}: {valor!r}")
    if tipo is str:
        valor = valor.strip()[:40]
        if isinstance(extra, tuple) and valor not in extra:
            raise ConfigError(f"{clave} debe ser una de: {', '.join(extra)}")
        return valor
    if minimo is not None and extra is not None:
        valor = max(minimo, min(extra, valor))
    return valor


def normalizar(cfg):
    """Devuelve una configuración limpia y completa, o lanza ConfigError."""
    if not isinstance(cfg, dict):
        raise ConfigError("La configuración debe ser un objeto")
    limpia = {}
    if isinstance(cfg.get("bajo"), dict) and cfg["bajo"].get("estilo") in bajo.ALIAS:
        cfg = dict(cfg, bajo=dict(cfg["bajo"], estilo=bajo.ALIAS[cfg["bajo"]["estilo"]]))
    for seccion, esquema in ESQUEMA_SECCIONES.items():
        datos = cfg.get(seccion) or {}
        limpia[seccion] = {k: _valor(k, datos.get(k), e) for k, e in esquema.items()}
    try:
        nombre_a_clase(limpia["musica"]["tonica"])
    except ValueError as e:
        raise ConfigError(str(e))
    secuencias = cfg.get("secuencia") or []
    if not isinstance(secuencias, list):
        raise ConfigError("secuencia debe ser una lista")
    limpia["secuencia"] = [
        {k: _valor(k, (s or {}).get(k), e) for k, e in ESQUEMA_SECUENCIA.items()}
        for s in secuencias[:MAX_SECUENCIAS]
    ]
    clips = cfg.get("clip") or []
    if not isinstance(clips, list):
        raise ConfigError("clip debe ser una lista")
    limpia["clip"] = [{k: _valor(k, (s or {}).get(k), e) for k, e in ESQUEMA_CLIP.items()}
                      for s in clips[:MAX_CLIPS]]
    clips = cfg.get("clip_dialogo") or []
    if not isinstance(clips, list):
        raise ConfigError("clip_dialogo debe ser una lista")
    limpia["clip_dialogo"] = [{k: _valor(k, (s or {}).get(k), e) for k, e in ESQUEMA_CLIP_DIALOGO.items()}
                              for s in clips[:MAX_CLIPS]]
    escenas = cfg.get("escena") or []
    if not isinstance(escenas, list):
        raise ConfigError("escena debe ser una lista")
    limpia["escena"] = [_escena(e) for e in escenas[:forma.MAX_ESCENAS]]
    if limpia["forma"]["escena"] >= len(limpia["escena"]):
        limpia["forma"]["escena"] = -1
    return limpia


def _escena(e):
    """Una escena: nombre, energía y su foto (JSON, ver forma.foto)."""
    if not isinstance(e, dict):
        raise ConfigError("Escena inválida")
    limpia = {k: _valor(k, e.get(k), esq) for k, esq in ESQUEMA_ESCENA.items()}
    datos = e.get("datos", "{}")
    if not isinstance(datos, str):
        datos = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    if len(datos) > MAX_DATOS_ESCENA:
        raise ConfigError("Escena demasiado grande")
    try:
        if not isinstance(json.loads(datos), dict):
            raise ValueError
    except ValueError:
        raise ConfigError(f"La escena {limpia['nombre']} está dañada")
    limpia["datos"] = datos
    return limpia


def clip_de(secuencia, nombre):
    """El carácter musical de una secuencia, listo para guardarse como clip."""
    clip = {k: secuencia[k] for k in ESQUEMA_CLIP if k in secuencia}
    clip["nombre"] = nombre.strip()[:40] or secuencia.get("nombre", "Clip")
    return clip


def clip_de_dialogo(cfg, nombre):
    """La conversación que está armada, lista para guardarse como clip."""
    clip = {"nombre": nombre.strip()[:40] or "Diálogo"}
    clip.update({k: v for k, v in cfg["dialogo"].items() if k != "activo"})
    for voz in VOCES:
        clip.update({f"{voz}_{k}": v for k, v in cfg[voz].items()})
    return clip


def secciones_de_clip(clip):
    """De un clip de diálogo a las secciones dialogo, llamada y respuesta."""
    dialogo = {k: clip[k] for k in ESQUEMA_SECCIONES["dialogo"] if k in clip}
    dialogo["activo"] = True
    voces = {voz: {k: clip[f"{voz}_{k}"] for k in ESQUEMA_SECCIONES[voz]} for voz in VOCES}
    return dialogo, voces["llamada"], voces["respuesta"]


def salidas(cfg):
    """Todos los puertos de salida que usa la configuración."""
    claves = [s["salida"] for s in cfg["secuencia"]]
    if cfg["thru"]["activo"]:
        claves.append(cfg["thru"]["salida"])
    if cfg["pads"]["activo"]:
        claves.append(cfg["pads"]["salida"])
    if cfg["dialogo"]["activo"]:
        if cfg["dialogo"]["modo"] == "motor":
            claves.append(cfg["llamada"]["salida"])
        claves.append(cfg["respuesta"]["salida"])
    return claves


def cargar(ruta):
    with open(ruta, "rb") as f:
        return normalizar(tomllib.load(f))


def _toml(valor):
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, (int, float)):
        return repr(valor)
    return json.dumps(valor, ensure_ascii=False)


def a_toml(cfg):
    lineas = ["# Configuración del motor Goa (guardada por la app).",
              "# Las opciones están explicadas en config.ejemplo.toml.", ""]
    for seccion in ESQUEMA_SECCIONES:
        lineas.append(f"[{seccion}]")
        lineas += [f"{k} = {_toml(v)}" for k, v in cfg[seccion].items()]
        lineas.append("")
    for s in cfg["secuencia"]:
        lineas.append("[[secuencia]]")
        lineas += [f"{k} = {_toml(v)}" for k, v in s.items()]
        lineas.append("")
    for s in cfg.get("clip", []):
        lineas.append("[[clip]]")
        lineas += [f"{k} = {_toml(v)}" for k, v in s.items()]
        lineas.append("")
    for s in cfg.get("clip_dialogo", []):
        lineas.append("[[clip_dialogo]]")
        lineas += [f"{k} = {_toml(v)}" for k, v in s.items()]
        lineas.append("")
    for s in cfg.get("escena", []):
        lineas.append("[[escena]]")
        lineas += [f"{k} = {_toml(v)}" for k, v in s.items()]
        lineas.append("")
    return "\n".join(lineas)


def guardar(ruta, cfg):
    """Escritura atómica: nunca deja el archivo a medias."""
    carpeta = os.path.dirname(os.path.abspath(ruta))
    fd, temporal = tempfile.mkstemp(dir=carpeta, prefix=".config-", suffix=".toml")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(a_toml(cfg))
    os.replace(temporal, ruta)
