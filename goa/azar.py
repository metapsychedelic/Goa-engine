"""Azar determinista y barato.

Muchos motores deciden cosas con `random.Random(clave).random()`: el mismo resultado
para la misma clave (misma seed, mismo paso), así todo es repetible. Crear un Random
por paso cuesta (siembra con SHA-512); acá se calcula una vez por clave y se guarda.
"""

import random
from functools import lru_cache


@lru_cache(maxsize=65536)
def azar(clave):
    """Lo mismo que random.Random(clave).random(), guardado."""
    return random.Random(clave).random()
