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
    todo &= ok(m.estado()["progresion"] != texto and m.origen_progresion in (7, 6),
               f"otra variante cambia la progresión ({m.estado()['progresion']})")

    def raices(cfg, compases, cambio=None):
        """Raíz del acorde de los pads en cada compás (1 = el primero)."""
        m = Motor(cfg, lambda *a: None)
        m.start()
        r = {}
        for tick in range(compases * 96):
            if cambio and tick == cambio[0] * 96 - 30:
                m.aplicar_config(cambio[1])
            m.reloj()
            if tick % 96 == 1:
                m.nota_on(1, 41)
            if tick % 96 == 20:
                r[tick // 96 + 1] = m.pads.raiz_acorde
        return r

    # Otra variante al azar se oye en el compás siguiente, aunque suene la i.
    for seed_nueva in ("P-0BEE", "Q-1234", "R-9999", "S-0042"):
        cfg = normalizar(base())
        cfg["pads"].update(activo=True, disparo=2, progresion="i_bVI_bVII", azar=True, cambia_cada=16, seed="P-0001")
        cfg = normalizar(cfg)
        otra = normalizar(dict(cfg, pads=dict(cfg["pads"], seed=seed_nueva)))
        r = raices(cfg, 12, cambio=(5, otra))  # en el compás 5 suena la i
        todo &= ok(r[6] != r[5], f"otra variante ({seed_nueva}) se oye en el compás siguiente, sin esperar 16")

    # Cambiar cada cuántos compases en vivo: el próximo acorde llega a ese ritmo.
    for prog in ("aleatoria", "i_bVI_bVII"):
        cfg = normalizar(base())
        cfg["pads"].update(activo=True, disparo=2, progresion=prog, cambia_cada=16, seed="P-0001")
        otra = normalizar(dict(cfg, pads=dict(cfg["pads"], cambia_cada=4)))
        r = raices(cfg, 30, cambio=(6, otra))
        cambios = [c for c in range(7, 31) if r[c] != r[c - 1]]
        todo &= ok(r[7] == r[6] and cambios[:3] == [11, 15, 19],
                   f"{prog}: de 16 a 4 en vivo, el acorde sigue y cambia cada 4 ({cambios[:4]})")

    # «Al azar» como casilla: parte de la elegida y la va variando.
    ton = Tonalidad("F", "frigio")
    for clave in ("i_bII", "i_bII_bIII_bII", "i_bVI_bVII", "i_iv_bII_i"):
        elegida = pads.PROGRESIONES[clave]
        p = pads.Pads({"activo": True, "progresion": clave, "azar": True, "azar_cada": 2, "seed": "AZ-1"}, ton)
        n = len(p.progresion)
        primera = [p.lista(c)[c % n] for c in range(2 * n)]
        todo &= ok(primera == (elegida * 4)[:2 * n], f"{clave}: las dos primeras vueltas suenan tal cual")
        variaciones = [p.lista(c) for c in range(2 * n, 40 * n, 2 * n)]
        distintas = {tuple(v) for v in variaciones}
        todo &= ok(len(distintas) >= 2 and all(v[0] == 0 for v in variaciones), f"{clave}: después va variando, siempre parte en la i ({len(distintas)} variaciones)")
        cambios = [sum(a != b for a, b in zip(v, p.progresion)) for v in variaciones]
        todo &= ok(all(1 <= c <= 2 for c in cambios), f"{clave}: cada variación cambia uno o dos acordes")
        todo &= ok(all(pads.consonante(ton.intervalos, g) for v in variaciones for g in v if g not in elegida),
                   f"{clave}: los acordes nuevos son mayores o menores")
    p = pads.Pads({"activo": True, "progresion": "i_bII", "azar": True, "seed": "AZ-1"}, ton)
    todo &= ok(all(v[:3] == [0, 1, 0] for v in (p.lista(c) for c in range(0, 80, 4))), "i – ♭II al azar: i – ♭II – i – Y (la elegida se sigue oyendo)")
    vieja = normalizar({"pads": {"progresion": "aleatoria"}})
    todo &= ok(vieja["pads"]["progresion"] == "i_bII" and vieja["pads"]["azar"], "una configuración con «aleatoria» pasa a i – ♭II con «al azar»")

    # El frigio al azar ya no es casi siempre de dos acordes.
    largos = [len(pads.progresion_aleatoria(ESCALAS["frigio"], s)) for s in SEEDS]
    todo &= ok(sum(l >= 3 for l in largos) > len(largos) * 0.6,
               f"frigio al azar: la mayoría con 3 o 4 acordes ({sum(l >= 3 for l in largos)} de {len(largos)})")

    print("\nTODO BIEN" if todo else "\nHAY ERRORES")
    raise SystemExit(0 if todo else 1)
