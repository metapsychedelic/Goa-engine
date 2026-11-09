"""Leer, validar y guardar la configuración (config.toml)."""

import json
import os
import tempfile
import tomllib

from . import generador
from .escalas import ESCALAS, nombre_a_clase

MAX_SECUENCIAS = 8

# clave: (tipo, valor por defecto, mínimo, máximo u opciones)
ESQUEMA_SECCIONES = {
    "app": {"puerto": (int, 8080, 1024, 65535)},
    "entrada": {
        "puerto": (str, "Circuit", None, None),
        "canal_disparo": (int, 4, 1, 16),
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
    },
}

ESQUEMA_SECUENCIA = {
    "nombre": (str, "A", None, None),
    "activa": (bool, True, None, None),
    "salida": (str, "FM-1", None, None),
    "canal": (int, 1, 1, 16),
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
}


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
    return limpia


def salidas(cfg):
    """Todos los puertos de salida que usa la configuración."""
    claves = [s["salida"] for s in cfg["secuencia"]]
    if cfg["thru"]["activo"]:
        claves.append(cfg["thru"]["salida"])
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
    return "\n".join(lineas)


def guardar(ruta, cfg):
    """Escritura atómica: nunca deja el archivo a medias."""
    carpeta = os.path.dirname(os.path.abspath(ruta))
    fd, temporal = tempfile.mkstemp(dir=carpeta, prefix=".config-", suffix=".toml")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(a_toml(cfg))
    os.replace(temporal, ruta)
