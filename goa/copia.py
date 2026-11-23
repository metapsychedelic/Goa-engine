"""Copias rápidas de la configuración, para el reloj y los cambios en vivo.

copy.deepcopy de una configuración completa copia también las escenas, partes y clips
guardados (cada escena trae una configuración entera): era lo que más tardaba al aplicar
un cambio (≈80 % del tiempo de Motor.aplicar_config) y se hace con el candado tomado.
Esas listas de la biblioteca nunca se modifican dentro del motor ni de forma.py (solo
se leen; la app las cambia con el candado tomado y después le da al motor su copia), así
que se comparten. Las secciones musicales son diccionarios de valores simples (números,
textos, booleanos): basta copiar cada diccionario, sin la maquinaria de deepcopy.
"""

import copy

BIBLIOTECA = frozenset(("escena", "parte", "clip", "clip_dialogo", "clip_bajo", "clip_pads"))
_SIMPLES = (int, float, str, bool, type(None))


def _dict(d):
    for v in d.values():
        if not isinstance(v, _SIMPLES):
            return copy.deepcopy(d)
    return dict(d)


def _valor(v):
    if isinstance(v, dict):
        return _dict(v)
    if isinstance(v, list):
        return [_dict(x) if isinstance(x, dict) else copy.deepcopy(x) for x in v]
    if isinstance(v, _SIMPLES):
        return v
    return copy.deepcopy(v)


def config(cfg):
    """Copia de `cfg` que se puede modificar sin tocar el original (salvo la biblioteca,
    que se comparte y no se modifica)."""
    return {k: (v if k in BIBLIOTECA else _valor(v)) for k, v in cfg.items()}
