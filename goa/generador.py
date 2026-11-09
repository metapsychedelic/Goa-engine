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
    0: {0: 1.5, 1: 2.5, 2: 2.0, 4: 2.0, 6: 1.2, 7: 1.5},
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


# Células rítmicas de un tiempo (4 semicorcheas) para líneas ácidas, con su peso.
# Sin las células más sincopadas (x..x, .x.x, .xx.): corren la línea respecto al bombo.
CELULAS_ACIDO = {
    "x.xx": 3.0, "xx.x": 3.0, "xxx.": 2.5, ".xxx": 1.5, "x.x.": 2.0, "x...": 1.5, "xx..": 1.5, "xxxx": 0.7,
}

# Final del motivo (el tiempo "C"): más chance de dejar espacio o una nota larga.
CELULAS_FINAL = dict(CELULAS_ACIDO, **{"x...": 3.0, "xx..": 2.0, "....": 1.5})


def _acido(rng, largo, pedal):
    """Línea estilo 303 con estructura musical.

    Un compás se arma como A B A C: un motivo de dos tiempos que se repite
    y cambia su final, como pregunta y respuesta. Los acentos caen sobre todo
    en las semicorcheas débiles, los slides unen notas seguidas y los saltos
    de octava acompañan a los acentos, como en las líneas clásicas de 303.
    """
    celulas = list(CELULAS_ACIDO)
    a = _elegir(rng, CELULAS_ACIDO)
    b = _elegir(rng, CELULAS_ACIDO)
    c = _elegir(rng, {k: v for k, v in CELULAS_FINAL.items() if k != b} or CELULAS_FINAL)
    ritmo = [ch == "x" for ch in a + b + a + c]

    def melodia(n, anterior, primero_raiz):
        grados = []
        for i in range(n):
            if i == 0 and primero_raiz:
                g = 0
            elif rng.random() < pedal * 0.25:
                g = 0
            else:
                g = _elegir(rng, TRANSICIONES_ACIDO.get(anterior, TRANSICIONES_ACIDO[0]))
            grados.append(g)
            anterior = g
        return grados

    motivo = melodia(8, 0, True)
    respuesta = melodia(4, motivo[3], False)
    grados = motivo + motivo[:4] + respuesta

    # Los acentos y slides no quedan fijos: cada paso dice cuánto le calzan
    # (pesos) y la cantidad la regula el usuario. "fuente" hace que la parte
    # repetida del motivo use los mismos valores al azar, así se repiten igual.
    fuente = list(range(8)) + list(range(4)) + list(range(12, 16))
    compas = []
    for i in range(16):
        siguiente = ritmo[(i + 1) % 16]
        cambia = grados[(i + 1) % 16] != grados[i]
        r = rng.random()
        compas.append({
            "suena": ritmo[i], "grado": grados[i], "acento": False, "slide": False,
            "octava": 1 if r < 0.06 else (-1 if r < 0.09 else 0),
            # Algunas notas muy cortas (staccato) para contrastar con las largas.
            "gate_mult": 0.45 if rng.random() < 0.3 else 1.0,
            "fuente": fuente[i],
            "pref_acento": 1.6 if i % 2 == 1 else 0.6,  # mejor en las semicorcheas débiles
            # Slides solo hacia el contratiempo o la última semicorchea del tiempo:
            # nunca hacia el golpe del bombo ni saliendo de él, y nunca hacia un silencio.
            "pref_slide": ((1.5 if cambia else 0.5) if siguiente and i % 4 in (1, 2) else 0.0),
        })
    for i in range(12):  # la repetición del motivo copia también sus saltos de octava y articulación
        if fuente[i] != i:
            compas[i]["octava"] = compas[fuente[i]]["octava"]
            compas[i]["gate_mult"] = compas[fuente[i]]["gate_mult"]
    return [dict(compas[i % 16]) for i in range(largo)]


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
    largo = max(largo, 16)  # el ácido referencia pasos de su compás de 16
    return [{"densidad": rng.random(), "slide": rng.random(), "acento": rng.random(),
             "salto": rng.random(), "direccion": 1 if rng.random() < 0.7 else -1,
             "repeticion": rng.random(), "larga": rng.random()} for _ in range(largo)]


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
