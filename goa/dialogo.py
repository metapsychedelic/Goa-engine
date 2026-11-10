"""Llamada y respuesta.

Dos voces que conversan dejando espacio. La llamada la toca el motor o
la tocas tú en vivo; la respuesta la toca el motor en el sinte que elijas,
también en el mismo que llamó.

Cada voz tiene su propio carácter: escala, relación tonal, octava, ámbito,
contorno de la frase, ritmo, densidad, cómo termina (tensión o reposo),
gate, velocidad y saltos.

La respuesta se arma desde la llamada (variación, espejo, eco) o como una
frase nueva. Con evolución, la frase cambia un poco en cada vuelta para
que la conversación no repita frases.

Las frases se guardan en grados de escala y se convierten a notas al
tocar, así siguen a la nota larga y a los acordes de los pads.
"""

import copy
import math
import random

from .escalas import Tonalidad

TICKS_POR_PASO = 6
PASOS_POR_COMPAS = 16
PASOS_POR_TIEMPO = 4

MODOS = ("motor", "en_vivo")
TRANSFORMACIONES = ("variacion", "espejo", "eco", "nueva")
CONTORNOS = ("libre", "sube", "baja", "arco", "valle")
RITMOS = ("semicorcheas", "corcheas", "mixto", "largas")
FINALES = ("suspendido", "tension", "reposo", "libre")
MOVIMIENTOS = ("conjunto", "abierto", "arpegio")
FORMAS = ("motivo", "frase")
# Grados de escala por sobre la raíz.
RELACIONES = {"unisono": 0, "tercera": 2, "cuarta": 3, "quinta": 4, "sexta": 5, "octava": 7}

# Grados donde una frase queda abierta (♭2, quinta, ♭7 en frigio) o descansa.
GRADOS_TENSION = (1, 4, 6)
GRADOS_REPOSO = (0,)
GRADOS_SUSPENDIDO = (4, 3)   # quinta o cuarta: queda abierta sin sonar a amenaza
# Notas del acorde de la escala con séptima (en frigio: Fm7). Base de los arpegios.
GRADOS_ACORDE = (0, 2, 4, 6)
# Colores oscuros, en semitonos sobre la raíz: ♭2, ♭6 y el tritono. El ♭2 y el ♭6
# son la esencia oscura del frigio (sobre todo resolviendo medio tono abajo);
# el tritono pesa poco: es lo que lleva una frase de misteriosa a terrorífica.
OSCUROS = {1: 1.0, 8: 1.0, 6: 0.25}


class Voz:
    """Carácter musical de la llamada o de la respuesta."""

    def __init__(self, cfg, tonica, escala_general):
        self.salida = cfg.get("salida", "FM-1")
        self.canal = int(cfg.get("canal", 4)) - 1
        escala = cfg.get("escala", "general")
        self.tonalidad = Tonalidad(tonica, escala_general if escala == "general" else escala)
        self.relacion = RELACIONES[cfg.get("relacion", "unisono")]
        self.octava = int(cfg.get("octava", 0))
        self.ambito = max(2, min(12, int(cfg.get("ambito", 5))))
        self.contorno = cfg.get("contorno", "arco")
        self.ritmo = cfg.get("ritmo", "mixto")
        self.densidad = float(cfg.get("densidad", 0.5))
        self.final = cfg.get("final", "tension")
        self.gate = float(cfg.get("gate", 0.7))
        self.velocidad = int(cfg.get("velocidad", 96))
        self.vel_random = float(cfg.get("vel_random", 0.15))
        self.saltos = float(cfg.get("saltos", 0.1))
        self.movimiento = cfg.get("movimiento", "abierto")
        self.oscuridad = float(cfg.get("oscuridad", 0.7))
        self.forma = cfg.get("forma", "motivo")
        for nombre, valor, opciones in (("contorno", self.contorno, CONTORNOS), ("ritmo", self.ritmo, RITMOS),
                                        ("final", self.final, FINALES), ("movimiento", self.movimiento, MOVIMIENTOS),
                                        ("forma", self.forma, FORMAS)):
            if valor not in opciones:
                raise ValueError(f"{nombre} debe ser una de: {', '.join(opciones)}")

    def nota(self, raiz, grado, adaptacion, tonalidad=None):
        n = (tonalidad or self.tonalidad).nota(raiz, grado + self.relacion, adaptacion) + 12 * self.octava
        return max(0, min(127, n))


# --- Generación de frases ---
# Una frase es una lista de notas: dict(paso, grado, dur, dv), con `paso` relativo
# al inicio de la frase, `dur` en pulsos de reloj y `dv` la diferencia de
# velocidad respecto a la velocidad base de la voz (acentos y matices).


def _rejilla(ritmo):
    """Separación entre posibles notas y peso de cada posición."""
    if ritmo == "semicorcheas":
        return 1, lambda i: 1.0
    if ritmo == "corcheas":
        return 2, lambda i: 1.0
    if ritmo == "largas":
        return 4, lambda i: 1.0
    return 1, lambda i: 1.0 if i % 2 == 0 else 0.45  # mixto: corcheas con algunas semicorcheas


# Células de un tiempo (4 semicorcheas, x = nota). La frase se arma con un motivo
# de un compás hecho de estas células, que se repite con pequeños cambios: así
# tiene groove y queda amarrada al bombo en vez de ser notas sueltas.
CELULAS = {
    "semicorcheas": ("xxxx", "x.xx", "xx.x", "xxx.", ".xxx", "x.x.", "xx.."),
    "corcheas": ("x.x.", "x...", "..x.", "x.x."),
    "mixto": ("x.x.", "x.xx", "xx.x", "x...", "..xx", "xxx.", "x..x", "..x."),
    "largas": ("x...",),
}
# Cuántas notas por tiempo busca cada ritmo con densidad 0 y con densidad 1.
NOTAS_POR_TIEMPO = {"semicorcheas": (2.0, 4.0), "corcheas": (1.0, 2.0), "mixto": (1.0, 3.0), "largas": (1.0, 1.0)}


def _celula(rng, voz):
    if rng.random() > min(1.0, 0.25 + voz.densidad):
        return "...."  # tiempo en silencio: deja espacio
    poca, mucha = NOTAS_POR_TIEMPO[voz.ritmo]
    objetivo = poca + (mucha - poca) * voz.densidad
    celulas = CELULAS[voz.ritmo]
    pesos = [1 / (1 + 2 * abs(c.count("x") - objetivo)) for c in celulas]
    return rng.choices(celulas, pesos)[0]


def _inicios(rng, voz, largo):
    """Dónde empieza cada nota: motivo de un compás repetido con variaciones."""
    tiempos = max(1, largo // PASOS_POR_TIEMPO - 1)  # el último tiempo respira
    motivo = [_celula(rng, voz) for _ in range(min(4, tiempos))]
    if motivo[0] == "....":
        motivo[0] = rng.choice([c for c in CELULAS[voz.ritmo] if c[0] == "x"])
    celdas = []
    for t in range(tiempos):
        celda = motivo[t % len(motivo)]
        if t >= len(motivo) and rng.random() < 0.3:
            celda = _celula(rng, voz)  # la repetición cambia un poco
        celdas.append(celda)
    return [t * PASOS_POR_TIEMPO + i for t, c in enumerate(celdas) for i, ch in enumerate(c) if ch == "x"]


def _curva(contorno, x):
    if contorno == "sube":
        return x
    if contorno == "baja":
        return 1 - x
    if contorno == "arco":
        return math.sin(math.pi * x)
    return 1 - math.sin(math.pi * x)  # valle


def _cercano(grado, opciones):
    """El grado de las opciones (en cualquier octava) más cercano a `grado`."""
    candidatos = [o + 7 * k for o in opciones for k in range(-2, 3)]
    return min(candidatos, key=lambda c: (abs(c - grado), c))


ULTRA_OSCURO = 0.85


def _cerrar(notas, voz):
    if notas and voz.final != "libre":
        opciones = {"tension": GRADOS_TENSION, "reposo": GRADOS_REPOSO, "suspendido": GRADOS_SUSPENDIDO}[voz.final]
        if voz.final == "tension" and voz.oscuridad >= ULTRA_OSCURO:
            opciones = (1,)  # ultra oscuro: la pregunta queda colgada en el ♭2
        notas[-1]["grado"] = _cercano(notas[-1]["grado"], opciones)
    return notas


def _oscuro(voz, grado):
    """Peso del color oscuro de un grado (0 si no es oscuro)."""
    return OSCUROS.get(voz.tonalidad.intervalos[(grado + voz.relacion) % 7], 0.0)


def _aclarar(rng, voz, notas):
    """Dosifica los colores oscuros según la oscuridad de la voz.

    Bajo 50 % los ♭2 y ♭6 se van filtrando hacia la nota vecina; el tritono casi
    siempre se evita. Sobre 50 % además atrae el ♭2 y el ♭6 como vecinos de la raíz
    y la quinta en las notas de paso: el color oscuro del Goa frigio."""
    atraccion = max(0.0, voz.oscuridad - 0.5) * 1.4  # en 100 %: 70 % de las notas de paso
    for k, n in enumerate(notas):
        peso = _oscuro(voz, n["grado"])
        if peso and rng.random() >= voz.oscuridad * peso:
            for vecino in (n["grado"] - 1, n["grado"] + 1):
                if not _oscuro(voz, vecino):
                    n["grado"] = vecino
                    break
        elif (not peso and 0 < k < len(notas) - 1 and _oscuro(voz, n["grado"] + 1) == 1.0
              and rng.random() < atraccion):
            n["grado"] += 1
    return notas


def _candidatos(voz, anterior, rng):
    """Notas a las que puede ir la melodía desde `anterior`, según el movimiento."""
    bajo, alto = -3, voz.ambito + 3
    if voz.movimiento == "arpegio":
        opciones = {a + 7 * k for a in GRADOS_ACORDE for k in range(-1, 3)}
    elif voz.movimiento == "abierto":
        # Cuartas, quintas, octavas y terceras; algún grado conjunto para unirlas.
        opciones = {anterior + p for p in (-7, -4, -3, -2, -1, 0, 1, 2, 3, 4, 7)}
    else:
        pasos = (-2, -1, 0, 1, 2) + ((-4, 4, -7, 7) if rng.random() < voz.saltos else ())
        opciones = {anterior + p for p in pasos}
    return [g for g in opciones if bajo <= g <= alto] or [anterior]


def _melodia(rng, voz, n):
    grados = []
    anterior = 0
    for k in range(n):
        if voz.contorno == "libre":
            objetivo = anterior + rng.choice((-3, -2, -1, 1, 2, 3))
        else:
            x = k / (n - 1) if n > 1 else 0.0
            objetivo = _curva(voz.contorno, x) * voz.ambito
        if k == 0:
            # Arranca en un punto de apoyo: la raíz, la quinta o una nota del acorde.
            apoyos = GRADOS_ACORDE if voz.movimiento == "arpegio" else (0, 4)
            g = _cercano(round(objetivo), apoyos)
        else:
            abierto = voz.movimiento == "abierto"

            def costo(c):
                salto = abs(c - anterior)
                # En abierto el contorno es gravedad, no riel: deja saltar cuartas y quintas.
                return (abs(c - objetivo) * (0.45 if abierto else 1.0) + rng.random() * 1.5
                        + (0.8 if c == anterior else 0)                        # no machacar la misma nota
                        - (0.75 if abierto and salto in (3, 4) else 0)
                        # Aterriza en el acorde menor con séptima: la tercera menor ancla
                        # el color menor; sin ella, cuartas y quintas suenan luminosas.
                        - (0.7 if abierto and c % 7 in GRADOS_ACORDE else 0)
                        + (0.0 if salto < 7 else 1.5 * (1 - voz.saltos)))      # octavas, según saltos
            g = min(_candidatos(voz, anterior, rng), key=costo)
        grados.append(g)
        anterior = g
    return grados


def motivo(rng, voz, largo):
    """Figura corta; la densidad elige cuál:

    baja: 3 notas cortas · media: 3 cortas y una larga · alta: pequeño arpegio.
    Después, silencio hasta el final del turno: el espacio es parte de la frase."""
    d = voz.densidad
    figura = "tres" if d < 0.35 else ("tres_y_larga" if d < 0.65 else "arpegio")
    corta = {"semicorcheas": 1, "mixto": 1, "corcheas": 2, "largas": 4}[voz.ritmo]
    if voz.ritmo == "mixto" and rng.random() < 0.4:
        corta = 2
    inicio = 0 if rng.random() < 0.75 else 2  # a veces entra en anacrusa
    n = {"tres": 3, "tres_y_larga": 4, "arpegio": 5 if d > 0.85 else 4}[figura]
    pasos = [inicio + k * corta for k in range(n)]
    if figura == "arpegio":
        acorde = sorted({a + 7 * k for a in GRADOS_ACORDE for k in range(0, 2)})
        sube = voz.contorno in ("sube", "arco") or (voz.contorno == "libre" and rng.random() < 0.5)
        if sube:
            desde = rng.choice((0, 1, 2))  # raíz, tercera o quinta
            grados = acorde[desde:desde + n]
        else:
            desde = rng.choice((4, 5, 6))  # octava, novena… baja hacia la raíz
            grados = acorde[max(0, desde - n + 1):desde + 1][::-1]
    else:
        corta_voz = copy.copy(voz)
        # Figuras cortas: poco recorrido; en ultra oscuro, giros de medio tono.
        corta_voz.ambito = 2 if voz.oscuridad >= ULTRA_OSCURO else min(voz.ambito, 4)
        if voz.oscuridad >= ULTRA_OSCURO:
            corta_voz.movimiento = "conjunto"
        grados = _melodia(rng, corta_voz, n)
    notas = []
    for k, (paso, grado) in enumerate(zip(pasos, grados)):
        larga = figura == "tres_y_larga" and k == n - 1
        if larga:
            dur_pasos = min(8, max(corta, largo - paso - PASOS_POR_TIEMPO))
            dur = max(1, round(dur_pasos * TICKS_POR_PASO * max(voz.gate, 0.9)))
        else:
            dur = max(1, round(corta * TICKS_POR_PASO * voz.gate))
        dv = round(voz.vel_random * 20 * rng.uniform(-1, 1)) + (8 if k == 0 else 0) + (6 if larga else 0)
        notas.append({"paso": paso, "grado": grado, "dur": dur, "dv": dv})
    return _cerrar(_aclarar(rng, voz, notas), voz)


def frase(rng, voz, largo):
    """Frase nueva de `largo` pasos según el carácter de la voz."""
    if voz.forma == "motivo":
        return motivo(rng, voz, largo)
    separacion, _ = _rejilla(voz.ritmo)
    util = max(separacion, largo - PASOS_POR_TIEMPO)  # deja respirar el final
    inicios = _inicios(rng, voz, largo)
    if len(inicios) < 2:
        medio = (util // 2) // separacion * separacion
        if medio > inicios[0]:
            inicios.append(medio)
    grados = _melodia(rng, voz, len(inicios))
    notas = []
    for k, inicio in enumerate(inicios):
        ultima = k + 1 == len(inicios)
        hueco = (min(util, inicio + 8) if ultima else inicios[k + 1]) - inicio
        # Notas cortas y con pulso; solo la última y las "largas" pueden durar más de un tiempo.
        tope = 8 if ultima or voz.ritmo == "largas" else PASOS_POR_TIEMPO
        dur = max(1, round(min(hueco, tope) * TICKS_POR_PASO * voz.gate))
        dv = round(voz.vel_random * 25 * rng.uniform(-1, 1)) + (8 if k == 0 else 0)
        notas.append({"paso": inicio, "grado": grados[k], "dur": dur, "dv": dv})
    return _cerrar(_aclarar(rng, voz, notas), voz)


def _encajar(notas, largo):
    """Comprime una frase que no cabe en `largo` pasos, manteniendo su forma."""
    if not notas:
        return notas
    util = max(1, largo - 2)
    fin = max(n["paso"] for n in notas) + 1
    if fin <= util:
        return notas
    factor = util / fin
    vistas, encajadas = set(), []
    for n in notas:
        paso = min(util - 1, int(n["paso"] * factor))
        if paso in vistas:
            continue
        vistas.add(paso)
        encajadas.append(dict(n, paso=paso, dur=max(1, round(n["dur"] * factor))))
    return encajadas


def responder(rng, llamada, voz_llamada, voz, transformacion, largo, densidad_ref, parecido=1.0):
    """Respuesta a una frase de llamada.

    `parecido` (solo en variación): en 1 la respuesta calca el ritmo y la dirección
    de cada intervalo de la llamada; bajo 0.5 usa su propia figura y su propio
    ritmo, y cuanto más bajo, más contesta en dirección contraria."""
    if transformacion == "nueva" or not llamada:
        return frase(rng, voz, largo)
    propio = transformacion == "variacion" and parecido < 0.5
    if propio:
        notas = frase(rng, voz, largo)  # su propia figura y ritmo; las notas se rehacen abajo
    else:
        notas = [dict(n) for n in _encajar(llamada, largo)]
    direcciones = [(b["grado"] > a["grado"]) - (b["grado"] < a["grado"]) for a, b in zip(llamada, llamada[1:])] or [0]
    g0 = notas[0]["grado"]
    if transformacion == "espejo":
        for n in notas:
            n["grado"] = g0 - (n["grado"] - g0)
    elif transformacion == "variacion":
        # Mismo ritmo y misma dirección de cada intervalo, con otros intervalos:
        # suena emparentada sin repetir la frase.
        acorde = sorted({a + 7 * k for a in GRADOS_ACORDE for k in range(-1, 3)})
        if voz.movimiento == "arpegio":
            # Parte desde distintas notas del acorde para no repetir la respuesta.
            inicio = rng.choice((2, 4, 6, 7) if voz.contorno == "baja" else (0, 2, 4, 6))
        else:
            inicio = voz.ambito // 2 if voz.contorno == "baja" else rng.choice((0, 2, 4))
        nuevos = [inicio]
        for i in range(len(notas) - 1):
            direccion = direcciones[i % len(direcciones)]
            if rng.random() >= parecido:
                # Contesta en sentido contrario (o se mueve si la llamada repetía).
                direccion = -direccion if direccion else rng.choice((1, -1))
            previo = nuevos[-1]
            if direccion == 0:
                g = previo if rng.random() < 0.6 else previo + rng.choice((1, -1))
            elif voz.movimiento == "arpegio":
                # La nota del acorde siguiente en esa dirección (o la otra si salta).
                lado = [x for x in acorde if (x - previo) * direccion > 0]
                lado.sort(key=lambda x: abs(x - previo))
                salta = len(lado) > 1 and rng.random() < max(voz.saltos, 0.35)
                g = lado[1 if salta else 0] if lado else previo
            elif voz.movimiento == "abierto":
                g = previo + direccion * rng.choice((3, 4, 4, 1) if rng.random() >= voz.saltos else (7,))
            else:
                g = previo + direccion * (rng.choice((3, 4)) if rng.random() < voz.saltos else rng.choice((1, 1, 2)))
            nuevos.append(max(-3, min(voz.ambito + 3, g)))
        for n, g in zip(notas, nuevos):
            n["grado"] = g
    # Densidad menor que la de la llamada: quita notas, nunca la primera ni la última.
    # En forma motivo la densidad ya eligió la figura: no se quitan notas.
    if not propio and voz.forma == "frase" and densidad_ref > 0 and voz.densidad < densidad_ref and len(notas) > 2:
        queda = voz.densidad / densidad_ref
        notas = [notas[0]] + [n for n in notas[1:-1] if rng.random() < queda] + [notas[-1]]
    # Articulación propia de la respuesta.
    if not propio and voz_llamada is not None and voz_llamada.gate > 0:
        factor = voz.gate / voz_llamada.gate
        for n in notas:
            n["dur"] = max(1, round(n["dur"] * factor))
    for n in notas:
        n["dv"] = n["dv"] + round(voz.vel_random * 15 * rng.uniform(-1, 1))
    # El eco devuelve la frase tal cual (tus notas, en vivo); el resto se dosifica y se cierra.
    return notas if transformacion == "eco" else _cerrar(_aclarar(rng, voz, notas), voz)


def evolucionar(rng, notas, voz, cantidad, largo):
    """Cambia un poco la frase en cada vuelta (acumulativo, determinista por seed)."""
    if cantidad <= 0 or not notas:
        return notas
    separacion, _ = _rejilla(voz.ritmo)
    util = max(separacion, largo - max(2, separacion))
    nuevas = [dict(n) for n in notas]
    for n in nuevas:
        if rng.random() < cantidad:
            n["grado"] = max(-2, min(voz.ambito + 2, n["grado"] + rng.choice((-2, -1, 1, 2))))
    if voz.forma == "motivo":  # la figura conserva su forma; cambian las notas
        return _cerrar(_aclarar(rng, voz, nuevas), voz)
    if len(nuevas) > 2 and rng.random() < cantidad * 0.3:
        del nuevas[rng.randrange(1, len(nuevas) - 1)]  # una nota menos
    if rng.random() < cantidad * 0.3:
        ocupados = {n["paso"] for n in nuevas}
        libres = [i for i in range(0, util, separacion) if i not in ocupados]
        if libres:
            paso = rng.choice(libres)
            vecina = min(nuevas, key=lambda n: abs(n["paso"] - paso))
            nuevas.append({"paso": paso, "grado": vecina["grado"] + rng.choice((-1, 1)),
                           "dur": max(1, round(separacion * TICKS_POR_PASO * voz.gate)), "dv": 0})
            nuevas.sort(key=lambda n: n["paso"])
    return _cerrar(_aclarar(rng, voz, nuevas), voz)


# --- Tiempo ---

LARGA = 3 * TICKS_POR_PASO  # una nota de más de 3 semicorcheas pesa en la armonía


def _eventos(notas, inicio, voz, limite):
    """Notas de una frase a eventos del plan. Marca las que pesan: la primera,
    la última y las largas, que al seguir a los pads caen en notas del acorde."""
    ultima = len(notas) - 1
    return [(inicio + n["paso"], voz, n["grado"], n["dur"], n["dv"], limite,
             k == 0 or k == ultima or n["dur"] >= LARGA) for k, n in enumerate(notas)]


def _al_acorde(nota, clases):
    """La nota del acorde más cercana (si empata, la de abajo)."""
    for distancia in range(7):
        for candidata in (nota - distancia, nota + distancia):
            if candidata % 12 in clases and 0 <= candidata <= 127:
                return candidata
    return nota


class Dialogo:
    def __init__(self, cfg, cfg_llamada, cfg_respuesta, tonica, escala, adaptacion):
        self.activo = bool(cfg.get("activo", False))
        self.modo = cfg.get("modo", "motor")
        self.escucha = int(cfg.get("escucha", 4)) - 1
        self.compases_llamada = max(1, int(cfg.get("compases_llamada", 2)))
        self.compases_respuesta = max(1, int(cfg.get("compases_respuesta", 2)))
        self.pausa = max(0, int(cfg.get("pausa", 2)))          # tiempos
        self.descanso = max(0, int(cfg.get("descanso", 2)))    # compases
        self.transformacion = cfg.get("transformacion", "variacion")
        self.evolucion = float(cfg.get("evolucion", 0.3))
        self.parecido = float(cfg.get("parecido", 0.3))
        self.seed = str(cfg.get("seed", "CR-0001"))
        self.seguir_pads = bool(cfg.get("seguir_pads", True))
        for nombre, valor, opciones in (("modo", self.modo, MODOS),
                                        ("transformacion", self.transformacion, TRANSFORMACIONES)):
            if valor not in opciones:
                raise ValueError(f"{nombre} debe ser una de: {', '.join(opciones)}")
        self.llamada = Voz(cfg_llamada, tonica, escala)
        self.respuesta = Voz(cfg_respuesta, tonica, escala)
        self.tonalidad = Tonalidad(tonica, escala)
        self.adaptacion = adaptacion
        self.disparo = None  # lo resuelve el motor
        self.acorde = None   # clases de altura del acorde de los pads, si los sigue
        self.clip = None     # nombre del clip de diálogo que suena, si vino del disparador
        self.sonando = {}    # (salida, canal, nota) -> tick en que se apaga
        self.reiniciar()

    @property
    def largo_llamada(self):
        return self.compases_llamada * PASOS_POR_COMPAS

    @property
    def largo_respuesta(self):
        return self.compases_respuesta * PASOS_POR_COMPAS

    def reiniciar(self):
        self.inicio = None        # paso donde empezó la conversación (modo motor)
        self.ultimo_paso = None
        self.ciclo = -1
        self.plan = []            # (paso, voz, grado, dur, dv, limite, importante)
        self.frase_llamada = None
        self.frase_nueva = None   # base de la respuesta "nueva", que también evoluciona
        self.fase = None
        # En vivo
        self.captura = []         # (tick relativo, nota, velocidad, duración)
        self.sostenidas = {}      # nota -> (tick, velocidad)
        self.tick0 = None
        self.ultimo_off = None
        self.respondiendo_hasta = None
        self.raiz_vivo = None
        self.respuestas = 0

    # --- Modo motor ---

    def _ciclo_pasos(self):
        respuesta = self.largo_llamada + self.pausa * PASOS_POR_TIEMPO
        total = respuesta + self.largo_respuesta + self.descanso * PASOS_POR_COMPAS
        return respuesta, -(-total // PASOS_POR_COMPAS) * PASOS_POR_COMPAS  # redondea a compases

    def _planificar(self, ciclo, paso):
        evoluciona = self.evolucion > 0
        if self.frase_llamada is None:
            self.frase_llamada = frase(random.Random(f"llamada:{self.seed}"), self.llamada, self.largo_llamada)
        elif evoluciona:
            rng = random.Random(f"evolucion:{self.seed}:{ciclo}")
            self.frase_llamada = evolucionar(rng, self.frase_llamada, self.llamada, self.evolucion, self.largo_llamada)
        rng = random.Random(f"respuesta:{self.seed}:{ciclo if evoluciona else 0}")
        if self.transformacion == "nueva":
            if self.frase_nueva is None:
                self.frase_nueva = frase(random.Random(f"nueva:{self.seed}"), self.respuesta, self.largo_respuesta)
            elif evoluciona:
                self.frase_nueva = evolucionar(rng, self.frase_nueva, self.respuesta, self.evolucion,
                                               self.largo_respuesta)
            resp = self.frase_nueva
        else:
            resp = responder(rng, self.frase_llamada, self.llamada, self.respuesta, self.transformacion,
                             self.largo_respuesta, self.llamada.densidad, self.parecido)
        inicio_resp, _ = self._ciclo_pasos()
        fin_llamada = paso + self.largo_llamada
        fin_resp = paso + inicio_resp + self.largo_respuesta
        self.plan = (_eventos(self.frase_llamada, paso, "llamada", fin_llamada)
                     + _eventos(resp, paso + inicio_resp, "respuesta", fin_resp))

    def _fase_motor(self, pos):
        inicio_resp, _ = self._ciclo_pasos()
        if pos < self.largo_llamada:
            return "llamada"
        if pos < inicio_resp:
            return "espacio"
        if pos < inicio_resp + self.largo_respuesta:
            return "respuesta"
        return "espacio"

    # --- Modo en vivo ---

    def entrada_on(self, nota, velocidad, tick):
        if not self.activo or self.modo != "en_vivo" or self.respondiendo_hasta is not None:
            return
        if not self.captura and not self.sostenidas:
            self.tick0 = tick
        self.sostenidas[nota] = (tick, velocidad)
        self.fase = "escuchando"

    def entrada_off(self, nota, tick):
        empezada = self.sostenidas.pop(nota, None)
        if empezada is None:
            return
        inicio, velocidad = empezada
        self.captura.append((inicio - self.tick0, nota, velocidad, max(1, tick - inicio)))
        self.ultimo_off = tick

    def _frase_de_captura(self, raiz):
        captura = sorted(self.captura)
        primera = min(n for _, n, _, _ in captura)
        clase = (raiz if raiz is not None else self.tonalidad.tonica) % 12
        # La raíz queda en el registro de lo que tocaste: la nota de esa clase justo debajo.
        self.raiz_vivo = primera - ((primera - clase) % 12)
        notas_escala = self.tonalidad.notas

        def indice(n):
            return min(range(len(notas_escala)), key=lambda k: abs(notas_escala[k] - n))

        base = indice(self.raiz_vivo)
        media = sum(v for _, _, v, _ in captura) / len(captura)
        notas, vistas = [], set()
        for rel, nota, velocidad, dur in captura:
            paso = round(rel / TICKS_POR_PASO)
            if paso in vistas:  # acordes: se queda con una nota por paso
                continue
            vistas.add(paso)
            notas.append({"paso": paso, "grado": indice(nota) - base, "dur": dur,
                          "dv": round(velocidad - media)})
        return notas

    def _responder_en_vivo(self, paso, raiz):
        llamada = self._frase_de_captura(raiz)
        self.captura = []
        self.tick0 = None
        rng = random.Random(f"vivo:{self.seed}:{self.respuestas}")
        self.respuestas += 1
        # En vivo la referencia de densidad es media: sobre 50 % responde con todas tus notas.
        resp = responder(rng, llamada, None, self.respuesta, self.transformacion, self.largo_respuesta, 0.5,
                         self.parecido)
        if not resp:
            return
        fin = paso + min(self.largo_respuesta, max(n["paso"] for n in resp) + PASOS_POR_TIEMPO)
        self.plan = _eventos(resp, paso, "respuesta", fin)
        self.respondiendo_hasta = fin
        self.fase = "respuesta"

    # --- Llamado por el motor en cada paso ---

    def paso(self, paso, tick, raiz, enviar, acorde=None):
        if not self.activo or paso == self.ultimo_paso:
            return
        self.acorde = acorde
        if self.modo == "en_vivo":
            self.ultimo_paso = paso
            self._paso_vivo(paso, tick, raiz, enviar)
            return
        if raiz is None:
            if self.inicio is not None:
                self.apagar(enviar)
                self.reiniciar()
            return
        self.ultimo_paso = paso
        if self.inicio is None:
            if paso % PASOS_POR_COMPAS != 0:
                return  # la conversación empieza en un compás de la Circuit
            self.inicio = paso
        _, ciclo_pasos = self._ciclo_pasos()
        pos = paso - self.inicio
        if pos % ciclo_pasos == 0:
            self.ciclo = pos // ciclo_pasos
            self._planificar(self.ciclo, paso)
        self.fase = self._fase_motor(pos % ciclo_pasos)
        self._tocar(paso, tick, raiz, enviar)

    def _paso_vivo(self, paso, tick, raiz, enviar):
        if self.respondiendo_hasta is not None:
            self._tocar(paso, tick, self.raiz_vivo, enviar)
            if paso >= self.respondiendo_hasta:
                self.respondiendo_hasta = None
                self.plan = []
                self.fase = None
            return
        if not self.captura or self.sostenidas:
            return
        silencio = tick - self.ultimo_off >= max(1, self.pausa) * PASOS_POR_TIEMPO * TICKS_POR_PASO
        larga = self.captura[-1][0] >= self.largo_llamada * TICKS_POR_PASO
        if (silencio or larga) and paso % PASOS_POR_TIEMPO == 0:
            self._responder_en_vivo(paso, raiz)
            self._tocar(paso, tick, self.raiz_vivo, enviar)

    def _tocar(self, paso, tick, raiz, enviar):
        if raiz is None:
            return
        for evento in [e for e in self.plan if e[0] == paso]:
            _, nombre, grado, dur, dv, limite, importante = evento
            voz = self.llamada if nombre == "llamada" else self.respuesta
            if self.acorde:
                # Siguiendo a los pads: la escala de los pads, contada desde la raíz del
                # acorde, y las notas que pesan caen en notas del acorde.
                nota = voz.nota(raiz, grado, "escala", self.tonalidad)
                if importante:
                    nota = _al_acorde(nota, self.acorde)
            else:
                nota = voz.nota(raiz, grado, self.adaptacion)
            velocidad = max(1, min(127, voz.velocidad + dv))
            dur = max(1, min(dur, (limite - paso) * TICKS_POR_PASO - 1))
            clave = (voz.salida, voz.canal, nota)
            if clave in self.sonando:
                enviar(voz.salida, "note_off", voz.canal, nota, 0)
            enviar(voz.salida, "note_on", voz.canal, nota, velocidad)
            # El final se cuenta desde la grilla, no desde el pulso en que llegó:
            # si la nota larga llegó tarde, la nota no se alarga ni pisa a la siguiente.
            self.sonando[clave] = paso * TICKS_POR_PASO + dur
        self.plan = [e for e in self.plan if e[0] > paso]

    def tick(self, tick, enviar):
        for clave, fin in list(self.sonando.items()):
            if fin <= tick:
                salida, canal, nota = clave
                enviar(salida, "note_off", canal, nota, 0)
                del self.sonando[clave]

    def apagar(self, enviar):
        for salida, canal, nota in self.sonando:
            enviar(salida, "note_off", canal, nota, 0)
        self.sonando = {}
