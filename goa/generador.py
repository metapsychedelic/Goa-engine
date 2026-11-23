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
from functools import lru_cache

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

ESTILOS = ("rolling", "galope", "arpegio3", "acido", "psy_chill", "euclidiano", "largas", "ambient", "clasico",
           "psytrance")

# Estilos que muestra cada género (el primero es el que pone al elegir el género).
ESTILOS_POR_GENERO = {
    "goa": ("rolling", "galope", "arpegio3", "acido", "clasico", "psytrance"),
    "psytrance": ("psytrance", "rolling", "galope", "acido"),
    "psy_chill": ("psy_chill", "galope", "arpegio3"),
    "chillgressive": ("rolling", "euclidiano", "acido"),
    "chillout": ("largas", "euclidiano", "arpegio3"),
    "zenon": ("clasico", "psytrance", "euclidiano"),
    "ambient": ("ambient", "largas", "arpegio3"),
}

# Notas para los estilos lentos: casi siempre raíz y quinta, algo de octava y color.
PESOS_LARGAS = {0: 4.0, 4: 3.0, 7: 1.5, 2: 1.0, 6: 0.7}
PESOS_AMBIENT = {0: 3.0, 4: 2.5, 7: 2.0, 1: 1.0, 2: 1.0, 6: 1.0}
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


# --- Goa clásico -------------------------------------------------------------------------
# Sacado de secuencias Goa de los 90 (análisis de MIDIs de referencia, 0.53): grilla
# de semicorcheas sin swing, la raíz manda (40-85 % de las notas) saltando entre dos
# octavas, adornos breves que vuelven (♭2 sobre todo, ♭7, 4.ª, 5.ª), frases de 2 o 4
# compases (A B o A B A C) donde la variación cae en la segunda mitad del último compás.
# Tres figuras:
#   pedal   · rodante: las 16 semicorcheas, raíz en dos octavas y adornos que se repiten.
#   ciclo   · motivo de 3, 5, 6 o 7 notas en varias octavas que corre sobre los 16
#             pasos (el acento se va corriendo) y vuelve a empezar con la frase.
#   acordes · arpegio por tiempo (raíz, octava, tercera o segunda arriba) que sigue el
#             acorde que suena (pads o armonía guiada).

FIGURAS = ("pedal", "ciclo", "acordes")
# Psytrance (análisis del pack Zenhiser Analog Psytrance, 0.54): ver _psy_*.
FIGURAS_PSY = ("riff", "rafaga", "octavas", "arpegio", "pulsos", "espacio", "mantra", "tresillo", "descenso",
               "puntillo", "melodia")
FIGURAS_CON_AUTO = ("auto",) + FIGURAS + FIGURAS_PSY
FRASEADOS = ("clasico", "psytrance")   # estilos cuyo patrón dura una frase de 2 o 4 compases
CICLOS = (0, 3, 5, 6, 7)  # 0 = lo elige la seed

# Octavas de la raíz por tiempo (1 = arriba): las alternancias de las referencias.
CELDAS_OCTAVA = {"1001": 3, "0101": 2, "1010": 2, "0110": 1.5, "1011": 1, "0010": 1, "1000": 1}
# Adornos sobre la raíz: ♭2 (1), ♭7 abajo (-1), 4.ª (3), 5.ª (4), 3.ª (2).
ADORNOS = {1: 4.0, -1: 2.5, 3: 2.0, 4: 2.0, 2: 1.0}
# Notas del motivo del ciclo (grados desde la raíz, pueden pasar la octava).
NOTAS_CICLO = {7: 3.0, 4: 2.5, 11: 2.0, 8: 2.0, 6: 1.5, 14: 1.5, 9: 1.0, 1: 1.0, 2: 1.0, 13: 1.0}
CORRIDAS_ACORDE = ([7, 9, 11, 14], [11, 9, 8, 7], [14, 11, 9, 7], [7, 8, 9, 11], [9, 7, 9, 11], [11, 14, 11, 9])
CELDAS_ACORDE = {"x.xx": 4.0, "xx.x": 1.5, "xxx.": 1.5, "x.x.": 1.0, "xxxx": 1.0}


def figura_de(seed, figura="auto", familia="clasico"):
    """Qué figura toca: la elegida o, en «auto», la que elige la seed."""
    if familia == "psytrance":
        if figura in FIGURAS_PSY:
            return figura
        return _elegir(random.Random(f"psy:figura:{seed}"),
                       {"riff": 4.0, "rafaga": 1.5, "octavas": 1.5, "arpegio": 2.0, "pulsos": 1.0,
                        "espacio": 1.5, "mantra": 1.0, "tresillo": 1.5, "descenso": 1.5,
                        "puntillo": 2.5, "melodia": 1.5})
    if figura in FIGURAS:
        return figura
    r = random.Random(f"clasico:figura:{seed}").random()
    return "pedal" if r < 0.4 else "ciclo" if r < 0.75 else "acordes"


def _forma_frase(frase):
    """Qué compás es cada uno de la frase: A, B (respuesta) o C (remate fuerte)."""
    return ["A", "B"] if frase <= 2 else ["A", "B", "A", "C"]


def _paso(grado, octava=0, suena=True, acento=False, fuente=None):
    p = {"suena": suena, "grado": grado, "acento": acento, "slide": False, "octava": octava}
    if fuente is not None:
        p["fuente"] = fuente
    return p


def _corrida(rng, desde_paso, final):
    """Corrida del remate: escalera que baja o con la raíz intercalada (como en las
    referencias), siempre terminando cerca de la raíz para volver al uno."""
    n = 16 - desde_paso
    tope = rng.choice([4, 4, 6, 7]) if final else rng.choice([3, 4])
    if rng.random() < 0.5:   # escalera: grados seguidos que bajan
        grados = [max(0, tope - k) for k in range(n)]
    else:                    # intercalada: nota, raíz, nota más abajo, raíz…
        grados, g = [], tope
        for k in range(n):
            grados.append(g if k % 2 == 0 else 0)
            if k % 2 == 1:
                g = max(1, g - 1)
    return grados


def _clasico_pedal(rng, frase, remate, pedal, rr=None):
    rr = rr or rng  # azar de la respuesta (otra vuelta = otra respuesta, mismo compás A)
    celdas = [_elegir(rng, CELDAS_OCTAVA) for _ in range(4)]
    octavas = [int(c) for celda in celdas for c in celda]
    raiz = 0.55 + 0.35 * pedal                       # parte de raíz (pedal 0.5 → 72 %)
    adornos = max(1, round(16 * (1 - raiz)))
    color = [_elegir(rng, ADORNOS)]                   # uno o dos adornos que se repiten en el compás
    if rng.random() < 0.6:
        color.append(_elegir(rng, {k: v for k, v in ADORNOS.items() if k != color[0]}))
    pesos_lugar = {i: (0.4 if i % 4 == 0 else 1.6 if i % 4 in (2, 3) else 1.0) for i in range(1, 16)}
    lugares = set()
    while len(lugares) < adornos:
        lugares.add(_elegir(rng, {k: v for k, v in pesos_lugar.items() if k not in lugares}))
    silencio = rng.choice([i for i in range(1, 16) if i not in lugares and i % 4]) if rng.random() < 0.5 else None

    def compas(lugares_adorno, colores, octs):
        c = []
        for i in range(16):
            if i == silencio:
                c.append(_paso(0, suena=False, fuente=i))
            elif i in lugares_adorno:
                c.append(_paso(lugares_adorno[i], 0, fuente=i))
            else:
                c.append(_paso(0, octs[i], acento=(i == 0), fuente=i))
        return c

    base = {i: color[k % len(color)] for k, i in enumerate(sorted(lugares))}
    a = compas(base, color, octavas)
    resultado = []
    for tipo in _forma_frase(frase):
        if tipo == "A" or remate <= 0:
            resultado += [dict(p) for p in a]
            continue
        # Respuesta: la primera mitad igual (a veces con otro color), la segunda mitad nueva.
        nuevo = dict(base)
        otros = [g for g in ADORNOS if g not in color] or list(ADORNOS)
        if rr.random() < remate * 0.6:
            g = rr.choice(otros)
            for i in [i for i in nuevo if i < 8][:2]:
                nuevo[i] = g
        mitad = {i: g for i, g in nuevo.items() if i < 8}
        extra = round(adornos * (0.5 + remate)) + (1 if tipo == "C" else 0)
        sube = rr.random() < 0.35
        libres = [i for i in range(8, 16) if i != silencio]
        elegidos = sorted(rr.sample(libres, min(len(libres), max(1, extra))))
        for k, i in enumerate(elegidos):
            mitad[i] = (1 + k) if sube else _elegir(rr, {g: ADORNOS[g] for g in otros + color})
        c = compas(mitad, color, octavas)
        if (tipo == "C" or remate >= 0.75) and rr.random() < 0.4 + 0.6 * remate:
            desde = 12 if remate < 0.9 else 10
            for k, g in enumerate(_corrida(rr, desde, tipo == "C")):
                c[desde + k] = _paso(g, 0 if g else 1, fuente=desde + k)
        for p in c[8:]:
            p.pop("fuente", None)  # la respuesta tiene sus propios matices
        resultado += c
    return resultado


def _clasico_ciclo(rng, frase, remate, ciclo, registro, rr=None):
    rr = rr or rng
    largo_ciclo = ciclo if ciclo in CICLOS[1:] else rng.choice([3, 3, 5, 6, 6, 7])
    tope = 7 * max(1, registro)
    if largo_ciclo == 3 and rng.random() < 0.4:
        motivo = [0, 7, 14 if tope >= 14 else 4]       # octavas puras (G#3 G#4 G#5)
    else:
        motivo = [0]
        posibles = {g: p for g, p in NOTAS_CICLO.items() if g <= tope}
        while len(motivo) < largo_ciclo:
            g = _elegir(rng, {k: v for k, v in posibles.items() if k != motivo[-1]})
            motivo.append(g)
    # Variantes de la respuesta: una nota sube medio paso de escala (♭2) y, en la
    # segunda mitad, las notas altas bajan a su vecina (como la ♭7 de las referencias).
    i_sube = rr.randrange(1, largo_ciclo)
    resultado = []
    for b, tipo in enumerate(_forma_frase(frase)):
        for i in range(16):
            k = (b * 16 + i) % largo_ciclo
            g = motivo[k]
            if tipo != "A" and remate > 0:
                fuerza = remate * (1.3 if tipo == "C" else 1.0)
                if i < 8 and k == i_sube and fuerza >= 0.25 and g + 1 <= tope:
                    g += 1
                elif i >= 8 and g > 0 and rr.random() < fuerza:
                    g -= 1
            resultado.append(_paso(g, acento=(k == 0), fuente=k))
    return resultado


def _clasico_acordes(rng, frase, remate, rr=None):
    otra = rr is not None
    rr = rr or rng
    celda = _elegir(rng, CELDAS_ACORDE)
    sonantes = [i for i, ch in enumerate(celda) if ch == "x"]
    # Arriba alterna tercera y segunda sobre la octava (A3 C4 / A3 B3), o tercera y quinta.
    altos = rng.choice([(9, 8), (9, 8), (9, 11), (8, 9)])
    baja = rng.random() < 0.25          # algunos arpegios bajan en vez de subir
    resultado = []
    for tipo in _forma_frase(frase):
        for t in range(4):
            notas = [0, altos[t % 2]] if len(sonantes) == 2 else [0, 7, altos[t % 2], 11][:len(sonantes)]
            if baja:
                notas = [notas[0]] + sorted(notas[1:], reverse=True)
            ultimo = t == 3 and tipo != "A" and rr.random() < min(1.0, remate * 1.6)
            if ultimo:
                corrida = rr.choice(CORRIDAS_ACORDE) if otra else ([11, 9, 8, 7] if tipo == "C" else [7, 9, 11, 14])
            for i in range(4):
                paso = t * 4 + i
                if ultimo:   # remate: el último tiempo corre hacia arriba o abajo
                    g = corrida[i]
                    resultado.append(_paso(g))
                elif i in sonantes:
                    g = notas[sonantes.index(i)]
                    resultado.append(_paso(g, acento=(i == 0 and t == 0), fuente=paso))
                else:
                    resultado.append(_paso(0, suena=False, fuente=paso))
    return resultado


def clasico(seed, figura="auto", frase=2, remate=0.5, ciclo=0, registro=2, pedal=0.5, vuelta=0, raga="",
            familia="clasico", huecos=0.5):
    """Patrón «Goa clásico» de `frase` compases (16 pasos cada uno).

    `vuelta` > 0 da otra respuesta para la misma frase: el compás A y la figura
    quedan iguales, cambian los compases B y C (ver `con_respuesta`).
    `raga`: la respuesta cierra con la frase típica (pakad) de esa raga."""
    frase = 4 if frase >= 4 else 2
    rng = random.Random(f"clasico:{seed}")
    rr = random.Random(f"clasico:{seed}:respuesta:{vuelta}") if vuelta else None
    figura = figura_de(seed, figura, familia)
    if familia == "psytrance":
        rng = random.Random(f"psy:{seed}")
        rr = random.Random(f"psy:{seed}:respuesta:{vuelta}") if vuelta else None
        patron = PSY[figura](rng, frase, remate, huecos, rr or rng)
    elif figura == "ciclo":
        patron = _clasico_ciclo(rng, frase, remate, ciclo, registro, rr)
    elif figura == "acordes":
        patron = _clasico_acordes(rng, frase, remate, rr)
    else:
        patron = _clasico_pedal(rng, frase, remate, pedal, rr)
    if raga and remate > 0:
        _cerrar_con_pakad(patron, frase, raga)
    return patron


def _cerrar_con_pakad(patron, frase, raga):
    """El último compás de la frase termina con la frase típica de la raga (G m r S
    en Bhairav…), cayendo en la raíz justo antes de volver al uno. Va una octava
    sobre la raíz, como un canto sobre el pedal."""
    from . import raga as ragas
    grados = ragas.pakad_en_grados(raga)
    inicio = frase * 16 - len(grados)
    for k, g in enumerate(grados):
        patron[inicio + k] = _paso(g + 7)


def con_respuesta(patron, otra, frase):
    """El patrón que suena con los compases de respuesta (B, C) de `otra`; los A
    quedan como estaban (con lo que hayan mutado)."""
    frase = 4 if frase >= 4 else 2
    if len(patron) != len(otra) or len(patron) != frase * 16:
        return patron
    nuevo = [dict(p) for p in patron]
    for b, tipo in enumerate(_forma_frase(frase)):
        if tipo != "A":
            nuevo[b * 16:(b + 1) * 16] = [dict(p) for p in otra[b * 16:(b + 1) * 16]]
    return nuevo


def mutar_clasico(patron, seed, compas, probabilidad, audibles=None):
    """Mutación del Goa clásico: cambia una nota del vocabulario de la figura (o su
    vecina de escala) y el cambio se aplica a todas sus repeticiones (mismo «fuente»),
    así el ciclo sigue siendo ciclo y la frase sigue siendo A B. La raíz no cambia."""
    if probabilidad <= 0 or not patron:
        return patron
    rng = random.Random(f"mutacion:clasico:{seed}:{compas}")
    nuevo = [dict(p) for p in patron]
    vocabulario = sorted({p["grado"] for p in nuevo if p["suena"]})
    veces = 1 + (1 if rng.random() < probabilidad else 0) + (1 if rng.random() < probabilidad - 0.5 else 0)
    for _ in range(veces):
        # La raíz no muta: es el pedal que sostiene la figura.
        candidatos = [i for i, p in enumerate(nuevo)
                      if p["suena"] and p["grado"] != 0 and i % 16 and (not audibles or i in audibles)]
        if not candidatos:
            break
        i = rng.choice(candidatos)
        actual = nuevo[i]["grado"]
        opciones = [g for g in vocabulario + [actual + 1, actual - 1] if g != actual and g >= -1]
        g = rng.choice(opciones or [0])
        clave = nuevo[i].get("fuente")
        for j, p in enumerate(nuevo):
            if j == i or (clave is not None and p.get("fuente") == clave and p["grado"] == actual and j % 16):
                p["grado"] = g
    return nuevo


# --- Psytrance ----------------------------------------------------------------------------
# Del pack Zenhiser Analog Psytrance (25 loops a 140 BPM): el riff deja huecos fijos
# (sobre todo los pasos 5 y 9, donde cae el bombo); 60-90 % de raíz saltando de
# octava; el color (♭7 sobre todo, luego ♭3, ♭2, 4.ª) cae en los pasos de cierre de
# cada medio compás (8, 11, 15, 16); notas muy cortas con alguna larga de acento;
# frases A/B donde el B cambia de uno a tres pasos.

# Máscaras de riff del pack, de la más llena a la más vacía (el control «huecos» elige).
MASCARAS_PSY = ("xxx.xxxx.xx.x.xx", "x.x..xxxxxx.xxxx", "x.x..xxx.xxx.xxx", "x.x..xxx.xx.xxxx",
                "xxxxx.x..xxxx.x.", "xxx.x.xxx.x.xxx.", "x.x..xxx.xx..xxx", ".xx..xxx.xx..xxx",
                "x..xx.xx.xx..xxx", "x.x..xxx.xx.x.x.", "xxxx.x.x..x...xx", "x...x.x.x...x.x.")
# Color sobre la raíz alta: ♭7 (abajo), ♭3, ♭2, 4.ª, 5.ª, ♭6 (grados de la escala).
COLOR_PSY = {-1: 4.0, 2: 3.0, 1: 2.0, 3: 2.0, 4: 0.7, 5: 0.7}
CIERRES_PSY = (7, 10, 14, 15, 13, 6)          # dónde cae el color, en orden de preferencia
CELDAS_ARPEGIO_PSY = ("xxxxx.x.", "xx.xx.x.", "xxx.xxx.", "x.xxx.x.", "xx.x.xx.", "x.x.x.x.")


def _corto(grado, octava, fuente=None, largo=False):
    p = _paso(grado, octava, fuente=fuente)
    p["gate_mult"] = 1.8 if largo else 0.55   # staccato; las notas antes de un hueco se alargan
    return p


def _mascara_psy(rng, huecos, opciones=MASCARAS_PSY):
    i = round(huecos * (len(opciones) - 1)) + rng.choice((-2, -1, 0, 0, 1, 2))
    return opciones[max(0, min(len(opciones) - 1, i))]


def _psy_riff(rng, frase, remate, huecos, rr):
    mascara = _mascara_psy(rng, huecos)
    sonantes = [i for i, c in enumerate(mascara) if c == "x"]
    abajo = {sonantes[0]} if rng.random() < 0.75 else set()
    abajo |= {i for i in sonantes[1:] if rng.random() < 0.12}
    cierres = [i for i in CIERRES_PSY if i in sonantes]
    n_color = min(len(cierres), 1 + (rng.random() < 0.6) + (rng.random() < 0.25))
    color = {i: _elegir(rng, COLOR_PSY) for i in cierres[:n_color]}
    largos = {i for i in sonantes if (i + 1) % 16 not in sonantes and rng.random() < 0.5}  # acento antes de un hueco

    def compas(colores):
        c = []
        for i in range(16):
            if i not in sonantes:
                c.append(_paso(0, suena=False, fuente=i))
                continue
            if i in colores:
                c.append(_corto(colores[i], 1, i, largo=i in largos))
            else:
                c.append(_corto(0, 0 if i in abajo else 1, i, largo=i in largos))
        return c

    a = compas(color)
    resultado = []
    for tipo in _forma_frase(frase):
        if tipo == "A" or remate <= 0:
            resultado += [dict(p) for p in a]
            continue
        nuevo = dict(color)
        cambios = 1 + round(remate * (2 if tipo == "C" else 1))
        candidatos = [i for i in cierres if i >= 6] or cierres
        for i in rr.sample(candidatos, min(len(candidatos), cambios)):
            nuevo[i] = _elegir(rr, {g: p for g, p in COLOR_PSY.items() if g != color.get(i)})
        c = compas(nuevo)
        for p in c[6:]:
            p.pop("fuente", None)
        resultado += c
    return resultado


def _psy_rafaga(rng, frase, remate, huecos, rr):
    """Ráfaga transpuesta: un bloque de notas iguales a mitad de compás que cambia de
    altura cada compás (4.ª → raíz → ♭7 → raíz), como una progresión hecha con el riff."""
    largo_bloque = 5 if huecos < 0.5 else 4
    desde = 5
    progresion = rng.choice(([3, 0, -1, 0], [-1, 0, 3, 0], [2, 0, -1, 1], [4, 3, 0, -1], [3, -1, 0, 1]))
    cola = rng.choice(([2, 1], [1, 2], [2, -1], [-1, 1]))
    resultado = []
    for b in range(frase):
        bloque = progresion[b % 4] if frase == 4 else progresion[(b * 2) % 4]
        if remate > 0 and b == frase - 1 and rr is not rng and rr.random() < remate:
            bloque = _elegir(rr, {g: p for g, p in COLOR_PSY.items() if g != bloque})
        for i in range(16):
            if i in (1, 3, 4) or i == desde + largo_bloque + 1:
                resultado.append(_paso(0, suena=False))
            elif desde <= i < desde + largo_bloque:
                resultado.append(_corto(bloque, 1))
            elif i == desde + largo_bloque:
                resultado.append(_corto(cola[b % 2], 1, largo=True))
            else:
                resultado.append(_corto(0, 0 if i == 0 else 1))
    return resultado


def _psy_octavas(rng, frase, remate, huecos, rr):
    """Rolling de octavas: raíz alta y baja alternadas (semicorcheas, o corcheas con
    más huecos); el color del paso 15 cambia cada compás."""
    corcheas = huecos >= 0.6
    colores = rng.choice(([-1, 1, -1, 2], [-1, 2, -1, 1], [1, -1, 2, -1], [-1, -1, 1, 2]))
    segundo = rng.random() < 0.35            # a veces también un color en el paso 7
    resultado = []
    for b in range(frase):
        c = colores[b % 4] if frase == 4 else colores[(b * 2) % 4]
        if remate > 0 and b == frase - 1 and rr is not rng and rr.random() < remate:
            c = _elegir(rr, {g: p for g, p in COLOR_PSY.items() if g != c})
        for i in range(16):
            if corcheas and i % 2:
                resultado.append(_paso(0, suena=False))
                continue
            alto = (i // 2) % 2 == 0 if corcheas else i % 2 == 0
            if i == 14:
                resultado.append(_corto(c, 1))
            elif segundo and i == 6:
                resultado.append(_corto(-1, 1))
            else:
                p = _paso(0, 1 if alto else 0)
                p["gate_mult"] = 1.0 if corcheas else 0.9
                resultado.append(p)
    return resultado


def _psy_arpegio(rng, frase, remate, huecos, rr):
    """Arpegio con huecos: una célula de 8 pasos (dos por compás) con la raíz alta y
    color de acorde (♭3, 5.ª, ♭7, 4.ª) en sus notas interiores."""
    celda = _mascara_psy(rng, huecos, CELDAS_ARPEGIO_PSY)
    sonantes = [i for i, c in enumerate(celda) if c == "x"]
    acorde = {2: 3.0, 4: 2.5, -1: 2.5, 3: 1.5, 1: 0.8}
    # Color en algunas notas interiores (al menos una, a lo más la mitad): la raíz manda.
    interiores = sonantes[1:]
    cuantas = max(1, min(len(sonantes) // 2, sum(rng.random() < 0.55 for _ in interiores)))
    notas = {i: _elegir(rng, acorde) for i in sorted(rng.sample(interiores, min(cuantas, len(interiores))))}
    abajo = sonantes[-1] if rng.random() < 0.4 else None    # la última de la célula, raíz baja
    resultado = []
    for tipo in _forma_frase(frase):
        mitad2 = dict(notas)
        if tipo != "A" and remate > 0 and notas:
            i = rr.choice(list(notas))
            mitad2[i] = _elegir(rr, {g: p for g, p in acorde.items() if g != notas[i]})
            if tipo == "C" and rr.random() < remate:
                mitad2[sonantes[-1]] = rr.choice((1, -1, 2))
        for m, tabla in enumerate((notas, mitad2)):
            for i in range(8):
                if i not in sonantes:
                    resultado.append(_paso(0, suena=False, fuente=i))
                elif i in tabla:
                    resultado.append(_corto(tabla[i], 1, i if m == 0 else None))
                else:
                    resultado.append(_corto(0, 0 if i == abajo else 1, i if m == 0 else None))
    return resultado


def _psy_pulsos(rng, frase, remate, huecos, rr):
    """Pulsos: negras de raíz en octavas que se sostienen; el último tiempo cambia de
    nota cada compás (♭2, ♭3, ♭7, ♭6). Para bajo, stabs o un lead que respira."""
    octavas = rng.choice(([1, 0, 1, 1], [0, 1, 1, 0], [1, 0, 1, 0]))
    ultimos = rng.choice(([1, 2, 1, 2], [0, 1, -1, -2], [1, 2, -1, 5], [2, 1, 2, 4]))
    resultado = []
    for b in range(frase):
        u = ultimos[b % 4] if frase == 4 else ultimos[(b * 2 + 1) % 4]
        for i in range(16):
            if i % 4:
                resultado.append(_paso(0, suena=False))
                continue
            t = i // 4
            g, o = (u, 1) if t == 3 else (0, octavas[t])
            p = _paso(g, o, acento=(t == 0))
            p["sostener"] = 4 if huecos < 0.5 else 2   # negras sostenidas (o corcheas con aire)
            resultado.append(p)
    return resultado


# --- Psytrance místico (LD Magic, LD Mystic, LD Protest, SY Supernova) ---------------------

def _nota(grado, octava=0, sostener=None, retraso=0, acento=False, fuente=None, gate_mult=None):
    p = _paso(grado, octava, acento=acento, fuente=fuente)
    if sostener:
        p["sostener"] = sostener
    if retraso:
        p["retraso"] = retraso
    if gate_mult:
        p["gate_mult"] = gate_mult
    return p


def _silencios(n=16):
    return [_paso(0, suena=False) for _ in range(n)]


def _psy_espacio(rng, frase, remate, huecos, rr):
    """Espacio: por medio compás, raíz baja y octava largas (un tiempo y medio) y una
    nota corta (5.ª, ♭7 o 4.ª) en el contratiempo. Solo tres notas: lo místico es el aire."""
    largo = rng.choice((1.5, 1.5, 2.5))
    tercera = _elegir(rng, {4: 4.0, 6: 1.5, 3: 1.5})       # la nota corta (sobre la raíz baja)
    lugar = rng.choice((6, 6, 7))
    resultado = []
    for tipo in _forma_frase(frase):
        c = _silencios()
        for m in (0, 8):
            c[m] = _nota(0, 0, largo, fuente=m, acento=m == 0)
            quita_octava = m == 8 and (tipo != "A" or huecos > 0.6)   # el compás B respira más
            if not quita_octava:
                c[m + 4] = _nota(0, 1, largo, fuente=m + 4)
            if not (huecos > 0.85 and m == 0):
                g = tercera
                if tipo == "C" and m == 8 and rr.random() < remate:
                    g = _elegir(rr, {k: v for k, v in {4: 1, 6: 1, 3: 1, 1: 1}.items() if k != tercera})
                c[m + lugar - (0 if m + lugar < 16 else 1)] = _nota(g, 0, gate_mult=0.9, fuente=m + lugar)
        resultado += c
    return resultado


def _psy_mantra(rng, frase, remate, huecos, rr):
    """Mantra: un drone de raíz de tres tiempos y, al final de la frase, un canto lento en
    negras (1 ♭2 3 ♭2 en Hijaz) que entra con una ♭7 de anacrusa."""
    cantos = ([0, 1, 2, 1], [0, 1, 0, -1], [2, 1, 0, 1], [0, 1, 2, 3], [-1, 0, 1, 0])
    canto = rng.choice(cantos)
    resultado = []
    for b in range(frase):
        c = _silencios()
        ultimo = b == frase - 1
        if ultimo:
            melodia = canto
            if remate > 0 and rr is not rng and rr.random() < remate:
                melodia = rr.choice([x for x in cantos if x != canto])
            for t, g in enumerate(melodia):
                c[t * 4] = _nota(g, 1, 4 if huecos < 0.6 else 3, acento=t == 0)
        elif b % 2 == 0 or huecos < 0.4:
            c[0] = _nota(0, 0, 12 if huecos < 0.7 else 8, acento=True, fuente=0)
            if b == frase - 2:
                c[12] = _nota(-1, 1, 4)                      # anacrusa: la ♭7 antes del canto
        resultado += c
    return resultado


def _psy_tresillo(rng, frase, remate, huecos, rr):
    """Tresillos sobre el 4/4: tresillos de corchea (raíz, ♭2, 4.ª / raíz, ♭2, ♭7) en los
    primeros tiempos y tresillos de negra al final del compás. Un pulso = 1/24 de negra:
    el tresillo de corchea cae en los pulsos 0, 8 y 16 (paso 0, paso 1 + 2, paso 2 + 4)."""
    t1 = rng.choice(([0, 1, 3], [0, 1, 2], [0, 2, 3]))
    t2 = rng.choice(([0, 1, -1], [0, -1, -2], [0, 1, 0]))
    fin = rng.choice(([0, 0], [0, -1], [1, 0]))
    resultado = []
    for tipo in _forma_frase(frase):
        a, d, f = list(t1), list(t2), list(fin)
        if tipo != "A" and remate > 0:
            if rr.random() < remate:
                a[2] = a[2] + rr.choice((1, 2))             # el tresillo sube (E3, C#3 en la referencia)
            if tipo == "C" and rr.random() < remate:
                d = [x + 2 for x in d]
                f = [rr.choice((1, -1)), 0]
        c = _silencios()
        for k, g in enumerate(a):
            c[k] = _nota(g, 0, retraso=2 * k, gate_mult=1.2, acento=k == 0, fuente=k if tipo == "A" else None)
        if huecos < 0.75:
            for k, g in enumerate(d):
                c[4 + k] = _nota(g, 0, retraso=2 * k, gate_mult=1.2, fuente=4 + k if tipo == "A" else None)
        c[8] = _nota(0, 0, gate_mult=1.4)
        # tresillo de negra: pulsos 64 y 80 del compás (paso 10 + 4, paso 13 + 2)
        c[10] = _nota(f[0], 0, 1.1, retraso=4)
        if huecos < 0.5 or tipo != "A":
            c[13] = _nota(f[1], 0, 1.1, retraso=2)
        resultado += c
    return resultado


def _psy_descenso(rng, frase, remate, huecos, rr):
    """Descenso: la raíz en cada tiempo y, entre medio, una línea que baja por la escala
    (♭7 ♭6 5 4); acento en el tiempo 3."""
    lineas = ([-1, -2, -3, -4], [1, -1, -2, -3], [-1, -3, -2, -4], [-2, -1, -3, -4])
    linea = rng.choice(lineas)
    corcheas = huecos < 0.6
    resultado = []
    for tipo in _forma_frase(frase):
        ln = list(linea)
        if tipo == "C" and remate > 0 and rr.random() < remate:
            ln = rr.choice([x for x in lineas if x != linea])
        elif tipo == "B" and remate > 0 and rr.random() < remate * 0.6:
            ln[-1] = ln[-1] - 1
        c = _silencios()
        for t in range(4):
            c[t * 4] = _nota(0, 1, gate_mult=1.6, acento=t == 2, fuente=t * 4)
            if corcheas or t % 2 == 1:
                c[t * 4 + 2] = _nota(ln[t], 1, gate_mult=1.6, fuente=t * 4 + 2 if tipo == "A" else None)
        resultado += c
    return resultado


# --- De la carpeta completa de MIDIs (413 loops, 0.54) ---------------------------------------

# Puntillo: agrupar de a 3 semicorcheas (el acento cruza el 4/4 sin salir de la rejilla).
# Máscaras de Ghosthack (Riff 3, Riff 5), Apex (010, 011, 041) y Progressive (019),
# de la más llena a la más vacía.
MASCARAS_PUNTILLO = ("x..x..x..x..x.xx", "x..x..x.x..x..x.", "x..x..x..x..x.x.", "..x..x..x.xx..xx",
                     "x..x..x..x...x.x", "x.x..x..x.x..x..", "x....x..x..x..x.", "x..x..x.........")


def _psy_puntillo(rng, frase, remate, huecos, rr):
    """Puntillo: notas cada 3 semicorcheas (3-3-2, 3-3-3-3-2-2…). Raíz con alguna octava
    y el color en las últimas notas del compás, que cambian en la respuesta."""
    mascara = _mascara_psy(rng, huecos, MASCARAS_PUNTILLO)
    sonantes = [i for i, c in enumerate(mascara) if c == "x"]
    arriba = {i for i in sonantes[1:] if rng.random() < 0.3}
    colores_a = {i: _elegir(rng, COLOR_PSY) for i in sonantes[-(1 + (rng.random() < 0.5)):] if i != sonantes[0]}
    resultado = []
    for tipo in _forma_frase(frase):
        colores = dict(colores_a)
        if tipo != "A" and remate > 0:
            for i in list(colores) or sonantes[-1:]:
                if rr.random() < remate:
                    colores[i] = _elegir(rr, {g: p for g, p in COLOR_PSY.items() if g != colores_a.get(i)})
            if tipo == "C" and rr.random() < remate and len(sonantes) > 3:
                colores[sonantes[-3]] = _elegir(rr, COLOR_PSY)
        for i in range(16):
            if i not in sonantes:
                resultado.append(_paso(0, suena=False, fuente=i))
            elif i in colores:
                resultado.append(_nota(colores[i], 1, gate_mult=1.6, fuente=i if tipo == "A" else None))
            else:
                resultado.append(_nota(0, 1 if i in arriba else 0, gate_mult=1.6, acento=i == sonantes[0], fuente=i))
    return resultado


# Melodía con progresión: líneas por grados (drop leads de Impact, Chakra 13/14/18,
# Progressive 004). Suben por grados en el compás A, bajan desde el ♭6 en el B y
# resuelven en la raíz al cerrar la frase. Con armonía guiada caen en el acorde.
RITMOS_MELODIA = ("x.x.x.x.x.x.x.x.", "x...x...x...x...", "x.x.x...x.x.x...", "x.x.x.x.x...x...",
                  "x..x..x.x..x..x.")
CONTORNOS_A = ([0, 0, 2, 2, 1, 1, 0, 0], [0, 1, 2, 3, 2, 1, 0, 0], [0, 2, 4, 2, 3, 1, 0, 0], [0, 0, 1, 1, 2, 2, 4, 4],
               [4, 3, 2, 1, 2, 3, 4, 2])
CONTORNOS_B = ([5, 5, 4, 4, 3, 3, 0, 0], [5, 4, 3, 2, 1, 0, -1, 0], [6, 5, 4, 3, 4, 2, 1, 0], [4, 5, 4, 3, 2, 1, 0, 0],
               [2, 3, 4, 5, 4, 3, 1, 0])


def _psy_melodia(rng, frase, remate, huecos, rr):
    ritmo = _mascara_psy(rng, huecos, RITMOS_MELODIA)
    sonantes = [i for i, c in enumerate(ritmo) if c == "x"]
    a, bajada = rng.choice(CONTORNOS_A), rng.choice(CONTORNOS_B)
    largo = 1.8 if len(sonantes) <= 6 else 1.4

    def compas(contorno, fuente):
        c = _silencios()
        for k, i in enumerate(sonantes):
            # el contorno se reparte en las notas del ritmo: la primera y la última siempre caen
            g = contorno[round(k * (len(contorno) - 1) / max(1, len(sonantes) - 1))]
            c[i] = _nota(g, 1, gate_mult=largo, acento=k == 0, fuente=i if fuente else None)
        return c

    resultado = []
    for b, tipo in enumerate(_forma_frase(frase)):
        if tipo == "A":
            resultado += compas(a, True)
        else:
            contorno = list(bajada)
            if remate > 0 and rr.random() < remate:
                contorno = rr.choice([x for x in CONTORNOS_B if x != bajada])
            if tipo == "C" or b == frase - 1:
                contorno[-1] = 0          # la frase resuelve en la raíz
            resultado += compas(contorno, False)
    return resultado


PSY = {"riff": _psy_riff, "rafaga": _psy_rafaga, "octavas": _psy_octavas,
       "arpegio": _psy_arpegio, "pulsos": _psy_pulsos, "espacio": _psy_espacio, "mantra": _psy_mantra,
       "tresillo": _psy_tresillo, "descenso": _psy_descenso, "puntillo": _psy_puntillo, "melodia": _psy_melodia}


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
        elif estilo == "psy_chill":                 # bombo, silencio, bajo, bajo
            pasos.append((i % 4 in (2, 3), i % 4 == 2))
        elif estilo in ("euclidiano", "largas", "ambient"):
            pasos.append(None)
        else:
            raise ValueError(f"Estilo desconocido: {estilo!r}. Opciones: {', '.join(ESTILOS)}")
    if pasos and pasos[0] is None:
        # Euclidiano: 7 de 16 en cualquier lugar; largas: 3 de 16 desde el uno;
        # ambient: 1 de cada 8, para notas muy largas (con largo primo se desfasa).
        proporcion, rotar = {"euclidiano": (7 / 16, True), "largas": (3 / 16, False), "ambient": (1 / 8, False)}[estilo]
        golpes = max(1, round(largo * proporcion))
        patron = euclidiano(golpes, largo, rng.randrange(largo) if rotar else 0)
        primero = patron.index(True)
        pasos = [(suena, i == primero) for i, suena in enumerate(patron)]
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


# Lugar fuerte de cada tiempo según la posición: ahí la armonía guiada pone una nota
# del acorde. Entre bombos no suena el tiempo, así que el fuerte es el contratiempo.
FUERTE = {"onbeat": 0, "todos": 0, "offbeat": 2, "desplazado": 1}


def es_fuerte(posicion, i):
    return i % 4 == FUERTE[posicion]


RECORRIDOS = ("adelante", "atras", "pendulo", "azar")

# Pesos para armar o mutar un molde (filtro: x pasa, ? a veces, - bloquea), por lugar
# del tiempo: (tiempo, contratiempo, semicorchea débil). Goa: rolling lleno, casi todo
# pasa. Psy: deja los tiempos al bombo y al bajo y vive en contratiempos y síncopas.
PESOS_MOLDE = {
    "goa": ((("x", 7), ("?", 2), ("-", 1)), (("x", 5), ("?", 3), ("-", 2)), (("x", 4), ("?", 3), ("-", 3))),
    "psy": ((("-", 6), ("x", 2), ("?", 1)), (("x", 7), ("?", 2), ("-", 1)), (("x", 2), ("?", 3), ("-", 5))),
}
ESTILOS_MOLDE = tuple(PESOS_MOLDE)


def _pesos_paso(estilo, i):
    tiempo, contra, debil = PESOS_MOLDE.get(estilo, PESOS_MOLDE["goa"])
    return tiempo if i % 4 == 0 else contra if i % 4 == 2 else debil


def _elegir_peso(rng, pesos):
    r = rng.random() * sum(p for _, p in pesos)
    for c, p in pesos:
        r -= p
        if r < 0:
            return c
    return pesos[-1][0]


def molde_al_azar(rng, estilo="goa"):
    """Un molde de 16 pasos al azar pero con sentido; siempre con al menos un «x»."""
    m = [_elegir_peso(rng, _pesos_paso(estilo, i)) for i in range(16)]
    if "x" not in m:
        m[rng.choice([2, 6, 10, 14] if estilo == "psy" else [0, 4, 8, 12])] = "x"
    return "".join(m)


def mutar_molde(molde, rng, cantidad, estilo="goa"):
    """Cambia uno o dos pasos del molde con probabilidad `cantidad`, sin tocar los del
    bombo. Se llama siempre sobre el molde original (no sobre el ya mutado): el filtro
    se aleja a lo más uno o dos pasos de lo que pintaste y vuelve, así no pierde el
    tiempo. Nunca deja el molde sin ningún «x» si tenía alguno."""
    if cantidad <= 0 or rng.random() >= cantidad:
        return molde
    m = list((molde or "").ljust(16, "-")[:16])
    for _ in range(2 if cantidad >= 0.66 else 1):
        # Los pasos del bombo (1, 2, 3, 4) no mutan: son el ancla que mantiene la
        # secuencia pegada al tiempo.
        i = rng.choice([k for k in range(16) if k % 4])
        opciones = [(c, p) for c, p in _pesos_paso(estilo, i) if c != m[i]]
        m[i] = _elegir_peso(rng, opciones)
    if "x" not in m and "x" in (molde or ""):
        m[molde.index("x")] = "x"
    return "".join(m)


def recorrer(recorrido, k, largo, seed):
    """Qué elemento (paso del patrón o nota del motivo) toca en la vuelta `k`.

    adelante: 0, 1, 2…; atrás: al revés; péndulo: va y vuelve sin repetir los
    extremos; azar: cada vuelta completa en otro orden (sin repetir dentro de la vuelta).
    """
    if largo <= 1:
        return 0
    if recorrido == "atras":
        return largo - 1 - k % largo
    if recorrido == "pendulo":
        n = 2 * largo - 2
        j = k % n
        return j if j < largo else n - j
    if recorrido == "azar":
        vuelta, j = divmod(k, largo)
        return _orden_azar(str(seed), vuelta, largo)[j]
    return k % largo


@lru_cache(maxsize=4096)
def _orden_azar(seed, vuelta, largo):
    orden = list(range(largo))
    random.Random(f"{seed}:orden:{vuelta}").shuffle(orden)
    return tuple(orden)


def generar(seed, estilo="rolling", largo=16, pedal=0.5, clasico_opciones=None):
    """Devuelve una lista de pasos: dict(suena, grado, acento).

    La posición rítmica (onbeat, offbeat...) no se aplica aquí sino al tocar,
    con el paso global, para que un patrón de 13 pasos siga en la grilla.
    «clasico» ignora `largo`: dura su frase (32 o 64 pasos).
    """
    if estilo in FRASEADOS:
        opciones = dict(clasico_opciones or {})
        opciones["familia"] = estilo
        return clasico(seed, pedal=pedal, **opciones)
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
        elif estilo in ("largas", "ambient"):
            grado = 0 if i == 0 else _elegir(rng, PESOS_AMBIENT if estilo == "ambient" else PESOS_LARGAS)
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


def mutar_ritmo(patron, seed, compas, probabilidad, posicion, ritmo_base):
    """Mutación de ritmo: mueve una nota a un lugar vecino, agrega o quita una, o
    devuelve un lugar a como estaba. Determinista por seed y compás.

    Respeta dónde caen las notas (offbeat no pasa al bombo) y no se aleja demasiado
    de la cantidad de notas original: entre la mitad y una vez y media."""
    if probabilidad <= 0 or not patron:
        return patron
    rng = random.Random(f"ritmo:{seed}:{compas}")
    veces = (1 if rng.random() < probabilidad else 0) + (1 if rng.random() < probabilidad - 0.5 else 0)
    if not veces:
        return patron
    largo = len(patron)
    # Con largo múltiplo de 4 cada paso cae siempre en el mismo lugar del compás;
    # con 13, 11 o 7 va girando, así que cualquier paso suena en algún momento.
    valido = (lambda i: pasa_posicion(posicion, i)) if largo % 4 == 0 else (lambda i: True)
    nuevo = [dict(p) for p in patron]
    originales = max(1, sum(1 for i, b in enumerate(ritmo_base) if b and valido(i)))
    for _ in range(veces):
        notas = [i for i, p in enumerate(nuevo) if p["suena"] and valido(i)]
        vacios = [i for i, p in enumerate(nuevo) if not p["suena"] and valido(i)]
        distintos = [i for i in range(largo) if bool(nuevo[i]["suena"]) != bool(ritmo_base[i]) and valido(i)]
        vecinos = lambda i: [j % largo for j in (i - 1, i + 1, i - 2, i + 2)]  # noqa: E731
        ops = []
        if any(not nuevo[j]["suena"] and valido(j) for i in notas for j in vecinos(i)):
            ops += ["mover"] * 3
        if vacios and len(notas) < originales * 1.5:
            ops += ["agregar"] * 2
        if len(notas) > max(1, originales * 0.5):
            ops += ["quitar"] * 2
        if distintos:
            ops += ["volver"]
        if not ops:
            break
        op = rng.choice(ops)
        silencio = lambda p: dict(p, suena=False, acento=False, slide=False)  # noqa: E731
        if op == "mover":
            origenes = [i for i in notas if any(not nuevo[j]["suena"] and valido(j) for j in vecinos(i))]
            i = rng.choice(origenes)
            j = rng.choice([j for j in vecinos(i) if not nuevo[j]["suena"] and valido(j)])
            nota = dict(nuevo[i])
            nota.pop("fuente", None)  # la densidad sigue al lugar nuevo
            nuevo[j], nuevo[i] = nota, silencio(nuevo[i])
        elif op == "agregar":
            cerca = [j for j in vacios if any(nuevo[k]["suena"] for k in vecinos(j))] or vacios
            j = rng.choice(cerca)
            modelo = next((nuevo[k] for k in vecinos(j) if nuevo[k]["suena"]), None)
            nota = dict(modelo or nuevo[j], suena=True, acento=False, slide=False)
            nota["grado"] = modelo["grado"] if modelo and rng.random() < 0.5 else 0
            nota.pop("fuente", None)
            nuevo[j] = nota
        elif op == "quitar":
            i = rng.choice(notas)
            nuevo[i] = silencio(nuevo[i])
        else:  # volver: un lugar vuelve al ritmo original
            i = rng.choice(distintos)
            if ritmo_base[i]:
                nuevo[i] = dict(nuevo[i], suena=True, grado=nuevo[i].get("grado", 0))
                nuevo[i].pop("fuente", None)
            else:
                nuevo[i] = silencio(nuevo[i])
    return nuevo


def mutar(patron, seed, compas, probabilidad, pedal=0.5, audibles=None):
    """Evolución tipo Turing Machine, determinista para cada seed y compás. `audibles`
    (opcional): los pasos que deja pasar el filtro de notas; el cambio garantizado cae
    en uno de ellos, para que la mutación se oiga."""
    if probabilidad <= 0:
        return patron
    rng = random.Random(f"mutacion:{seed}:{compas}")
    nuevo = [dict(p) for p in patron]
    for i, paso in enumerate(nuevo):
        if paso["suena"] and rng.random() < probabilidad:
            anterior = nuevo[i - 1]["grado"] if i > 0 else 0
            paso["grado"] = _siguiente_grado(rng, anterior, pedal)
    sonando = [i for i, p in enumerate(nuevo) if p["suena"]]
    if audibles:
        sonando = [i for i in sonando if i in audibles] or sonando
    if sonando and pedal < 1 and all(nuevo[i]["grado"] == patron[i]["grado"] for i in sonando):
        # Cada mutación cambia al menos una nota. Sin esto, un patrón de pocas notas
        # con el pedal alto se quedaba pegado en la nota larga y dejaba de evolucionar.
        i = rng.choice(sonando)
        actual = nuevo[i]["grado"]
        anterior = nuevo[i - 1]["grado"] if i > 0 else 0
        for _ in range(12):
            g = _siguiente_grado(rng, anterior, pedal if actual != 0 else 0.0)
            if g != actual:
                nuevo[i]["grado"] = g
                break
    return nuevo
