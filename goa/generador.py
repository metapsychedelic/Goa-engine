"""Generación de patrones Goa.

Combina tres técnicas probadas:
- Ritmo: plantillas de estilo y el algoritmo euclidiano (Toussaint).
- Notas: cadena de Markov sobre grados de la escala, con pesos que
  imitan las líneas Goa (la raíz como pedal, saltos a ♭2, 5, ♭7, octava).
- Evolución al estilo Turing Machine: cada cierto número de compases,
  cada paso tiene una probabilidad de cambiar de nota.

Todo sale de un random.Random con la seed, así la misma seed da
siempre el mismo patrón y la misma evolución.
"""

import random

# Grados de la escala relativos a la raíz: 0 raíz, 1 segunda (♭2 en frigio),
# 2 tercera, 3 cuarta, 4 quinta, 6 séptima, 7 octava, -1 séptima abajo.
TRANSICIONES = {
    0: {0: 3.0, 1: 3.0, 4: 2.0, 6: 1.5, 7: 1.5, 2: 1.0, -1: 1.0},
    1: {0: 6.0, 1: 1.0, 2: 1.0, -1: 1.0},
    2: {0: 3.0, 1: 2.0, 3: 1.0, 4: 2.0},
    3: {4: 3.0, 2: 2.0, 0: 2.0},
    4: {0: 4.0, 3: 1.0, 6: 1.0, 7: 1.0, 4: 1.0},
    6: {7: 3.0, 4: 2.0, 0: 3.0},
    7: {0: 4.0, 6: 2.0, 4: 2.0, 7: 1.0},
    -1: {0: 6.0, 1: 1.0},
}

# Melodía de estilo 303: movimientos cortos, mucho ♭2 y ♭3, saltos a quinta, séptima y octava.
TRANSICIONES_ACIDO = {
    0: {0: 3.0, 1: 2.0, 2: 2.0, 4: 1.5, 6: 1.0, 7: 1.0},
    1: {0: 4.0, 2: 1.0, 1: 1.0},
    2: {0: 2.0, 1: 1.5, 3: 1.0, 4: 1.5},
    3: {2: 2.0, 4: 2.0, 0: 1.0},
    4: {0: 2.0, 3: 1.0, 6: 1.5, 7: 1.0, 4: 1.0},
    6: {7: 2.0, 4: 1.5, 0: 2.0},
    7: {6: 2.0, 0: 3.0, 4: 1.0},
}

ESTILOS = ("rolling", "galope", "arpegio3", "acido")
POSICIONES = ("onbeat", "offbeat", "todos", "desplazado")
RELACIONES = {"unisono": 0, "tercera": 2, "quinta": 4, "octava": 7}


def euclidiano(golpes, pasos, rotacion=0):
    """Reparte `golpes` lo más parejo posible en `pasos`."""
    if pasos <= 0:
        return []
    golpes = max(0, min(golpes, pasos))
    patron = [((i * golpes) % pasos) < golpes for i in range(pasos)]
    rotacion %= pasos
    return patron[-rotacion:] + patron[:-rotacion] if rotacion else patron


def _elegir(rng, pesos):
    total = sum(pesos.values())
    r = rng.random() * total
    acumulado = 0.0
    for estado, peso in pesos.items():
        acumulado += peso
        if r < acumulado:
            return estado
    return next(iter(pesos))


def _siguiente_grado(rng, anterior, pedal):
    if rng.random() < pedal:
        return 0
    return _elegir(rng, TRANSICIONES.get(anterior, TRANSICIONES[0]))


def _acido(rng, largo, pedal):
    """Línea de estilo 303: notas, silencios, acentos, slides y saltos de octava por paso."""
    golpes = euclidiano(rng.choice((9, 10, 11, 12)), 16, rotacion=rng.randrange(16))
    patron = []
    anterior = 0
    for i in range(largo):
        suena = golpes[i % 16] or rng.random() < 0.15
        if i == 0:
            grado = 0
        elif rng.random() < pedal * 0.4:
            grado = 0
        else:
            grado = _elegir(rng, TRANSICIONES_ACIDO.get(anterior, TRANSICIONES_ACIDO[0]))
        r = rng.random()
        octava = 1 if r < 0.12 else (-1 if r < 0.18 else 0)
        patron.append({"suena": suena, "grado": grado, "acento": rng.random() < 0.3,
                       "slide": rng.random() < 0.25, "octava": octava})
        if suena:
            anterior = grado
    return patron


def _ritmo(estilo, largo, rng):
    """Lista de (suena, acento) por paso, antes del filtro de posición."""
    pasos = []
    for i in range(largo):
        if estilo == "rolling":
            pasos.append((True, i % 4 == 1))
        elif estilo == "galope":
            pasos.append((i % 4 != 1, i % 4 == 0))
        elif estilo == "arpegio3":
            pasos.append((True, i % 3 == 0))
        else:
            raise ValueError(f"Estilo desconocido: {estilo!r}. Opciones: {', '.join(ESTILOS)}")
    return pasos


def pasa_posicion(posicion, i):
    """Filtro de posición rítmica. `i` es el paso global, para quedar en la grilla del compás."""
    if posicion == "onbeat":
        return i % 4 == 0
    if posicion == "offbeat":
        return i % 4 != 0
    if posicion == "desplazado":
        return i % 2 == 1
    if posicion == "todos":
        return True
    raise ValueError(f"Posición desconocida: {posicion!r}. Opciones: {', '.join(POSICIONES)}")


def generar(seed, estilo="rolling", largo=16, pedal=0.5):
    """Devuelve una lista de pasos: dict(suena, grado, acento).

    La posición rítmica (onbeat, offbeat...) no se aplica aquí sino al tocar,
    con el paso global, para que un patrón de 13 pasos siga en la grilla.
    """
    rng = random.Random(f"patron:{seed}")
    if estilo == "acido":
        return _acido(rng, largo, pedal)
    ritmo = _ritmo(estilo, largo, rng)
    arpegio = [0, 2, 4] if rng.random() < 0.5 else [0, 4, 7]
    patron = []
    anterior = 0
    for i, (suena, acento) in enumerate(ritmo):
        if estilo == "arpegio3":
            grado = arpegio[i % 3]
        elif i == 0:
            grado = 0
        else:
            grado = _siguiente_grado(rng, anterior, pedal)
        if suena:
            anterior = grado
        patron.append({"suena": suena, "grado": grado, "acento": acento, "slide": False, "octava": 0})
    return patron


def extras(seed, largo):
    """Valores al azar fijos por paso, uno por cada control de afinación.

    Como cada paso tiene su número fijo, subir la densidad (o los slides,
    o los saltos) agrega notas sin cambiar las que ya estaban: ideal para
    subir la intensidad de a poco en un rise.
    """
    rng = random.Random(f"extras:{seed}")
    return [{"densidad": rng.random(), "slide": rng.random(), "acento": rng.random(),
             "salto": rng.random(), "direccion": 1 if rng.random() < 0.7 else -1,
             "repeticion": rng.random()} for _ in range(largo)]


def mutar(patron, seed, compas, probabilidad, pedal=0.5):
    """Evolución tipo Turing Machine, determinista para cada seed y compás."""
    if probabilidad <= 0:
        return patron
    rng = random.Random(f"mutacion:{seed}:{compas}")
    nuevo = [dict(p) for p in patron]
    for i, paso in enumerate(nuevo):
        if paso["suena"] and rng.random() < probabilidad:
            anterior = nuevo[i - 1]["grado"] if i > 0 else 0
            paso["grado"] = _siguiente_grado(rng, anterior, pedal)
    return nuevo
