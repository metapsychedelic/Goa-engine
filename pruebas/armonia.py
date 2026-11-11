"""Prueba la armonía guiada (mapa armónico de los pads), el modo libre y las opciones, sin hardware.

  python3 -m pruebas.armonia            desde la carpeta goa-engine
"""

import tomllib

from goa import generador
from goa.config import a_toml, normalizar
from goa.escalas import Tonalidad

from .dialogo import base, colgadas, correr, ok

NOTA_LARGA = 41  # F2, la que manda correr() en cada compás


def armar(modo="guiada", tension=0.3, secuencia=True, dialogo=False, **pads):
    cfg = base()
    cfg["musica"].update(armonia=modo, tension=tension)
    cfg["dialogo"]["activo"] = dialogo
    cfg["pads"].update(dict(activo=True, disparo=2, progresion="andaluza", acorde="triada",
                            cambia_cada=2, variacion=0.0, suspensiones=0.0), **pads)
    s = cfg["secuencia"][0]
    s.update(activa=secuencia, disparo=2, estilo="rolling", swing=0.0, saltos=0.0, mutacion=0.0)
    return cfg


def eventos(salida, sal, canal, tipo="note_on"):
    return [(t, n) for t, s, ti, c, n, _ in salida if ti == tipo and s == sal and c == canal]


def de_secuencia(salida, cfg):
    s = cfg["secuencia"][0]
    return eventos(salida, s["salida"], s["canal"] - 1)


def en_escala(salida, cfg):
    escala = Tonalidad(cfg["musica"]["tonica"], cfg["musica"]["escala"])
    return all((n - escala.tonica) % 12 in escala.intervalos for _, _, ti, _, n, _ in salida if ti == "note_on")


def es_aproximacion(n, clases, tonalidad):
    """Nota común con el acorde que viene, o un paso de escala junto a una de sus notas."""
    return n % 12 in clases or any(tonalidad.nota(n, d, "escala") % 12 in clases for d in (1, -1))


if __name__ == "__main__":
    todo = True

    print("Secuencias guiadas")
    cfg = armar()
    salida, motor = correr(cfg, compases=16)
    notas = de_secuencia(salida, cfg)
    ton = motor.tonalidad
    momentos = {t: motor.pads.momento(t // 6, NOTA_LARGA) for t, _ in notas}
    fuertes = [(t, n) for t, n in notas if generador.es_fuerte(cfg["secuencia"][0]["posicion"], t // 6)]
    todo &= ok(bool(fuertes) and all(n % 12 in momentos[t].clases for t, n in fuertes),
               f"en los tiempos fuertes, notas del acorde ({len(fuertes)} de {len(notas)} notas)")
    largo = 2 * 96
    cambios = list(range(largo, 16 * 96, largo))
    ultimas = [max((tn for tn in notas if tn[0] < c), default=None) for c in cambios]
    bien = [es_aproximacion(n, momentos[t].clases_siguiente, ton) for t, n in ultimas]
    todo &= ok(all(bien), f"la última nota antes de cada cambio lleva al acorde que viene ({len(ultimas)} cambios)")
    raices = {motor.pads.momento(c // 6, NOTA_LARGA).raiz % 12 for c in [0] + cambios}
    todo &= ok(len(raices) == 4, "sigue los 4 acordes de la progresión (andaluza)")
    todo &= ok(en_escala(salida, cfg) and colgadas(salida) == 0, "todo en la escala y sin notas colgadas")
    todo &= ok(correr(cfg, compases=16)[0] == salida, "misma variante, misma salida")

    cfg = armar(cambia_cada=8)
    notas = de_secuencia(correr(cfg, compases=8)[0], cfg)
    compases = [[(t % 96, n) for t, n in notas if t // 96 == c] for c in range(1, 7)]
    todo &= ok(all(c == compases[0] for c in compases), "con el mismo acorde, el motivo se repite igual (no varía al azar)")

    cfg = armar(tension=0.0)
    salida, motor = correr(cfg, compases=16)
    notas = de_secuencia(salida, cfg)
    fuera = [(t, n) for t, n in notas if n % 12 not in motor.pads.momento(t // 6, NOTA_LARGA).clases
             and not motor.pads.momento(t // 6, NOTA_LARGA).cambia_pronto]
    todo &= ok(not fuera, "tensión 0: todas son notas del acorde (salvo las que anticipan)")

    sin_anticipar = armar(tension=0.0)
    sin_anticipar["musica"]["anticipar"] = False
    salida, motor = correr(sin_anticipar, compases=16)
    todo &= ok(all(n % 12 in motor.pads.momento(t // 6, NOTA_LARGA).clases for t, n in de_secuencia(salida, sin_anticipar)),
               "sin anticipar: la última nota se queda en el acorde que suena")

    print("\nModo libre")
    libre = de_secuencia(correr(armar("libre"))[0], armar())
    todo &= ok(libre != de_secuencia(correr(armar())[0], armar()), "libre suena distinto de guiada")
    todo &= ok(libre == de_secuencia(correr(armar("libre", tension=1.0))[0], armar()),
               "en libre la tensión no cambia nada (suena como antes)")
    propio = armar()
    propio["secuencia"][0]["armonia"] = "libre"
    todo &= ok(de_secuencia(correr(propio)[0], propio) == libre, "una secuencia en libre aunque el general sea guiada")
    propio = armar("libre")
    propio["secuencia"][0]["armonia"] = "guiada"
    todo &= ok(de_secuencia(correr(propio)[0], propio) == de_secuencia(correr(armar())[0], armar()),
               "y en guiada aunque el general sea libre")

    print("\nSin pads")
    cfg = armar(activo=False)
    salida, motor = correr(cfg, compases=8)
    clases = {motor.tonalidad.nota(NOTA_LARGA, g, "escala") % 12 for g in (0, 2, 4)}
    todo &= ok(all(n % 12 in clases for t, n in de_secuencia(salida, cfg) if generador.es_fuerte("offbeat", t // 6)),
               "la armonía es el acorde de la escala sobre la nota larga")

    print("\nPads que solo guían")
    cfg = armar(suenan=False)
    salida, motor = correr(cfg, compases=16)
    todo &= ok(not eventos(salida, cfg["pads"]["salida"], cfg["pads"]["canal"] - 1), "los pads no mandan notas")
    notas = de_secuencia(salida, cfg)
    todo &= ok(len({n % 12 for t, n in notas if t % largo == 6}) >= 3 and colgadas(salida) == 0,
               "pero las secuencias igual siguen la progresión")

    print("\nSuspensiones")
    cfg = armar(secuencia=False, suspensiones=1.0, rasgueo=0)
    salida, motor = correr(cfg, compases=16)
    pads = eventos(salida, cfg["pads"]["salida"], cfg["pads"]["canal"] - 1)
    resoluciones = [t for t, _ in pads if t % largo == 26]
    todo &= ok(len(resoluciones) >= 3, f"una voz resuelve un tiempo después del cambio ({len(resoluciones)} cambios)")
    sonando, maximo = set(), 0
    for t, s, ti, c, n, _ in salida:
        if s == cfg["pads"]["salida"] and c == cfg["pads"]["canal"] - 1:
            (sonando.add if ti == "note_on" else sonando.discard)(n)
            maximo = max(maximo, len(sonando))
    todo &= ok(maximo <= cfg["pads"]["voces"] and colgadas(salida) == 0, "nunca más voces que las del acorde, sin colgadas")
    sin = armar(secuencia=False, suspensiones=0.0, rasgueo=0)
    todo &= ok(not [t for t, _ in eventos(correr(sin)[0], cfg["pads"]["salida"], cfg["pads"]["canal"] - 1) if t % largo == 26],
               "sin suspensiones, el acorde cambia de una vez")

    print("\nLlamada y respuesta guiada")
    cfg = armar(secuencia=False, dialogo=True)
    cfg["llamada"]["oscuridad"] = cfg["respuesta"]["oscuridad"] = 0.6
    salida, motor = correr(cfg, compases=16)
    malas = 0
    for voz in ("llamada", "respuesta"):
        notas = eventos(salida, cfg[voz]["salida"], cfg[voz]["canal"] - 1)
        for c in range(16):
            del_compas = [tn for tn in notas if tn[0] // 96 == c]
            if not del_compas:
                continue
            t, n = max(del_compas)
            m = motor.pads.momento(t // 6, NOTA_LARGA)
            if not (n % 12 in m.clases or (m.cambia_pronto and es_aproximacion(n, m.clases_siguiente, ton))):
                malas += 1
    todo &= ok(malas == 0, "cada voz cierra su motivo en el acorde (o llevando al que viene)")
    todo &= ok(en_escala(salida, cfg) and colgadas(salida) == 0, "todo en la escala y sin notas colgadas")
    ultra = armar(secuencia=False, dialogo=True)
    ultra["llamada"]["oscuridad"] = 1.0
    salida, motor = correr(ultra, compases=16)
    llamada = eventos(salida, ultra["llamada"]["salida"], ultra["llamada"]["canal"] - 1)
    todo &= ok(any((n - motor.pads.momento(t // 6, NOTA_LARGA).raiz) % 12 == 1 for t, n in llamada),
               "ultra oscuro conserva su ♭2 contra la raíz del acorde")
    libre = armar("libre", secuencia=False, dialogo=True)
    propio = armar(secuencia=False, dialogo=True)
    propio["dialogo"]["armonia"] = "libre"
    todo &= ok(correr(libre)[0] == correr(propio)[0], "el diálogo en libre aunque el general sea guiada")

    print("\nVoicing de los pads (MicroFreak: 4 voces, filtro compartido)")
    from goa import generos
    for genero in generos.ORDEN:
        cfg = normalizar(generos.aplicar(base(), genero))
        cfg["dialogo"]["activo"] = False
        cfg["pads"].update(activo=True, disparo=2)
        salida, motor = correr(cfg, compases=64)
        sonando, maximo, choques = set(), 0, 0
        largo = cfg["pads"]["cambia_cada"] * 96
        for t, sal, ti, c, n, _ in salida:
            if sal != cfg["pads"]["salida"] or c != cfg["pads"]["canal"] - 1:
                continue
            (sonando.add if ti == "note_on" else sonando.discard)(n)
            maximo = max(maximo, len(sonando))
            if t % largo >= 96:  # pasado el primer compás del acorde (las suspensiones ya resolvieron)
                choques += any((b - a) % 12 == 1 for a in sonando for b in sonando if b > a)
        todo &= ok(maximo <= cfg["pads"]["voces"] and not choques,
                   f"{generos.GENEROS[genero]['nombre']:<14} máx. {maximo} notas (drone incluido), sin medio tono ni ♭9 entre voces")

    print("\nConfiguración")
    cfg = normalizar(armar(suenan=False, suspensiones=0.7))
    cfg["dialogo"]["armonia"] = "libre"
    todo &= ok(normalizar(tomllib.loads(a_toml(cfg))) == cfg, "se guarda y se lee igual")
    todo &= ok(normalizar(base())["musica"]["armonia"] == "guiada", "por defecto la armonía es guiada")

    print("\nTodo bien" if todo else "\nHay errores")
    raise SystemExit(0 if todo else 1)
