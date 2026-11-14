"""Prueba la progresión al azar de los pads, sin hardware.

  python3 -m pruebas.progresiones        desde la carpeta goa-engine
"""

from collections import Counter

from goa import pads
from goa.config import normalizar
from goa.escalas import ESCALAS, Tonalidad
from goa.motor import Motor

from .dialogo import base, ok

SEEDS = [f"P-{k:04X}" for k in range(300)]


def correr(cfg, compases, cambio=None):
    """Corre el motor; en el compás `cambio[0]` aplica la configuración `cambio[1]`."""
    m = Motor(cfg, lambda *a: None)
    m.start()
    for tick in range(compases * 96):
        if cambio and tick == cambio[0] * 96 - 30:
            m.aplicar_config(cambio[1])
        m.reloj()
        if tick % 96 == 1:
            m.nota_on(1, 41)
    return m


if __name__ == "__main__":
    todo = True

    print("Solo acordes que suenan bien")
    malos, formas, repetidos = [], set(), 0
    for nombre, iv in ESCALAS.items():
        for seed in SEEDS:
            p = pads.progresion_aleatoria(iv, seed)
            formas.add(len(p))
            malos += [(nombre, seed, g) for g in p if not pads.consonante(iv, g)]
            repetidos += any(a == b for a, b in zip(p, p[1:] + p[:1]))
            todo &= p[0] == 0
    todo &= ok(not malos, "ningún acorde disminuido ni aumentado, en ninguna escala")
    todo &= ok(repetidos == 0, "nunca repite el mismo acorde dos cambios seguidos (tampoco al dar la vuelta)")
    todo &= ok(formas <= {2, 3, 4} and len(formas) == 3, "progresiones de 2, 3 o 4 acordes, siempre partiendo en la i")

    print("\nEl color de cada escala")
    def mas_comun(escala, posicion=1):
        iv = ESCALAS[escala]
        c = Counter(pads.numeral(iv, pads.progresion_aleatoria(iv, s)[posicion]) for s in SEEDS)
        return c.most_common(1)[0][0], c
    todo &= ok(mas_comun("frigio")[0] == "♭II", "frigio: el segundo acorde más común es ♭II")
    todo &= ok(mas_comun("dorico")[0] == "IV", "dórica: el segundo acorde más común es IV")
    todo &= ok(mas_comun("lidio")[1]["II"] > 40, "lidia: el II mayor aparece seguido")
    def acordes_fuera_de_i(escala):
        return Counter(len(set(pads.progresion_aleatoria(ESCALAS[escala], s)) - {0}) for s in SEEDS)
    fr, me = acordes_fuera_de_i("frigio"), acordes_fuera_de_i("menor")
    todo &= ok(fr[3] < me[3] and fr[1] > me[1],
               f"frigio: se mueve menos que la menor (acordes fuera de la i: frigio {dict(fr)}, menor {dict(me)})")
    distintas = len({tuple(pads.progresion_aleatoria(ESCALAS["menor"], s)) for s in SEEDS})
    todo &= ok(distintas > 40, f"menor natural: mucha variedad ({distintas} progresiones distintas)")
    todo &= ok(pads.progresion_aleatoria(ESCALAS["menor"], "X") == pads.progresion_aleatoria(ESCALAS["menor"], "X"),
               "la misma seed da la misma progresión")

    print("\nTocando")
    malos = 0
    for nombre in ESCALAS:
        ton = Tonalidad("F", nombre)
        for seed in SEEDS[:40]:
            p = pads.Pads({"activo": True, "progresion": "aleatoria", "seed": seed, "variacion": 0.6}, ton)
            for nota in range(53, 65):   # nota larga en cualquier nota de la escala, no solo la tónica
                if (nota - ton.tonica) % 12 not in ton.intervalos:
                    continue
                for cambio in range(8):
                    malos += not p._consonante(nota, p._grado(cambio, nota))
    todo &= ok(malos == 0, "con la nota larga en cualquier grado y con sorpresas, nunca cae en un disminuido")
    fijos = 0
    ton = Tonalidad("F", "frigio")
    for seed in SEEDS[:60]:
        p = pads.Pads({"activo": True, "progresion": "i_bVI_bVII", "seed": seed, "variacion": 1.0}, ton)
        fijos += sum(not p._consonante(None, p._grado(c)) for c in range(1, 12)
                     if p._grado(c) != p.progresion[c % 3])
    todo &= ok(fijos == 0, "las sorpresas de las progresiones fijas tampoco caen en un disminuido")

    cfg = normalizar(base())
    cfg["pads"].update(activo=True, disparo=2, progresion="aleatoria", cambia_cada=1, seed="P-0001")
    m = correr(cfg, 6)
    texto = m.estado()["progresion"]
    todo &= ok(texto.startswith("i") and "–" in texto, f"el estado muestra la progresión ({texto})")
    otra = normalizar(dict(cfg, pads=dict(cfg["pads"], seed="P-0BEE")))
    m = correr(cfg, 12, cambio=(7, otra))
    todo &= ok(m.estado()["progresion"] != texto and m.origen_progresion == 7,
               f"otra variante cambia la progresión y la nueva parte en su i ({m.estado()['progresion']})")

    print("\nTODO BIEN" if todo else "\nHAY ERRORES")
    raise SystemExit(0 if todo else 1)
