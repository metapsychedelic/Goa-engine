"""Pruebas de lo sacado del segundo análisis de la carpeta de MIDIs (0.92): bajo
«trote» 3-3-2, remates de los packs, ciclo de alturas, nota larga zenon y progresiones nuevas.

  python3 -m pruebas.aprendido
"""

import tomllib

from goa import bajo, pads
from goa.config import a_toml, cargar, normalizar
from pruebas.carpeta import correr, notas, ok
from pruebas.simular import RAIZ


def bajo_notas(compases=8, **ajustes):
    out = correr(lambda c: c["bajo"].update(activo=True, salida="BAJO", disparo=0, **ajustes), compases)
    return notas(out, "BAJO")


def por_compas(ns):
    t0 = ns[0][0] - ns[0][0] % 96
    comp = {}
    for a, _, n, _ in ns:
        comp.setdefault((a - t0) // 96, []).append((((a - t0) % 96) // 6, n))
    return comp


def main():
    todo = True

    print("Bajo trote 3-3-2")
    ns = bajo_notas(4, estilo="trote", frase=4, remates=False, movimiento=0)
    lugares = {l for c in por_compas(ns).values() for l, _ in c}
    todo &= ok(lugares == {1, 3, 6, 9, 11, 14}, f"·B·B··B··B·B··B· (pasos {sorted(lugares)})")
    todo &= ok(all(ns[i][1] <= ns[i + 1][0] for i in range(len(ns) - 1)), "las notas no se pisan")
    con = bajo_notas(8, estilo="trote", frase=4)
    todo &= ok(not {l for c in por_compas(con).values() for l, _ in c} & {0, 4, 8, 12}, "con remates tampoco cae en el bombo")

    print("\nRemates de los packs")
    sin = bajo_notas(16, estilo="rolling", frase=2, remate_var=0)
    con = bajo_notas(16, estilo="rolling", frase=2, remate_var=0, remates_pack=1.0)
    cs, cc = por_compas(sin), por_compas(con)
    todo &= ok(all(cs[k] == cc[k] for k in cs if k % 2 == 0), "los compases que no cierran la frase no cambian")
    cierres = [k for k in cc if k % 2 == 1]
    distintos = sum(1 for k in cierres if cs.get(k) != cc.get(k))
    todo &= ok(distintos >= len(cierres) // 2, f"los compases que cierran usan los remates del pack ({distintos} de {len(cierres)})")
    todo &= ok(all(l >= 8 for k in cierres for l, n in cc[k] if (l, n) not in cs[k]), "el remate solo cambia la segunda mitad del compás")
    todo &= ok(not {l for c in cc.values() for l, _ in c} & {0, 4, 8, 12}, "nunca en el bombo")
    galope = bajo_notas(8, estilo="galope", frase=2, remate_var=0)
    galope_pack = bajo_notas(8, estilo="galope", frase=2, remate_var=0, remates_pack=1.0)
    todo &= ok(galope == galope_pack, "en los estilos que no son rolling no cambia nada")
    todo &= ok(all(len(r) and min(r) >= 9 and not set(r) & {12} for r in bajo.REMATES_PACK), "todos los remates del pack viven en la segunda mitad")

    print("\nCiclo de alturas")
    base = bajo_notas(10, estilo="rolling", remates=False, movimiento=0)
    todo &= ok(len({n for _, _, n, _ in base}) == 1, "sin ciclo, rolling quieto: una sola nota")
    for k in (5, 7):
        ns = bajo_notas(2 * k + 2, estilo="rolling", remates=False, movimiento=0, ciclo=k)
        comp = por_compas(ns)
        alturas = [n for c in sorted(comp) for _, n in comp[c]]
        todo &= ok(len(set(alturas)) > 1, f"ciclo {k}: rotan las alturas ({len(set(alturas))} notas distintas)")
        todo &= ok(comp[0] != comp[1] and comp[0] == comp[k], f"ciclo {k}: cada compás distinto y vuelve a empezar en el compás {k + 1}")
        todo &= ok({l for c in comp.values() for l, _ in c} == {l for c in por_compas(base).values() for l, _ in c},
                   f"ciclo {k}: el ritmo no cambia")
    quieto = bajo_notas(4, estilo="rolling", remates=False, movimiento=0)
    todo &= ok(all(bajo_notas(4, estilo="rolling", remates=False, movimiento=0, ciclo=k) == quieto for k in (3, 4)),
               "un ciclo que no existe (3, 4) suena como sin ciclo")
    ns = bajo_notas(16, estilo="trote", remates=False, movimiento=0, ciclo=5)
    comp = por_compas(ns)
    todo &= ok(comp[0] != comp[1] and comp[0] == comp[5], "también en el trote: vuelve a empezar en el compás 6")

    print("\nNota larga zenon")
    out = correr(lambda c: c["bajo"].update(activo=True, salida="BAJO", disparo=0, estilo="rolling", frase=4,
                                            remates=False, movimiento=0, zenon=1.0, caida=7), 12)
    ns = notas(out, "BAJO")
    comp = por_compas(ns)
    largas = [(a, b) for a, b, _, _ in ns if b - a > 30]
    todo &= ok(bool(largas) and all(((a - ns[0][0] + ns[0][0] % 96) % 96) // 6 == 9 for a, _ in largas),
               f"una nota larga justo después del bombo del tiempo 3 ({len(largas)} en 12 compases)")
    todo &= ok(all(k % 4 == 2 for k in comp if any(l == 9 and k in comp for l, _ in comp[k]) and len(comp[k]) < 12),
               "va en el compás antes del que cierra la frase")
    bends = [(t, v) for sal, t, tipo, v, _ in out if sal == "BAJO" and tipo == "pitchwheel"]
    todo &= ok(bool(bends) and min(v for _, v in bends) < -3000 and bends[-1][1] == 0, "cae con el pitch bend y vuelve al centro")
    sin_caida = correr(lambda c: c["bajo"].update(activo=True, salida="BAJO", disparo=0, estilo="rolling", frase=4,
                                                  remates=False, movimiento=0, zenon=1.0, caida=0), 12)
    todo &= ok(not any(t == "pitchwheel" for _, _, t, _, _ in sin_caida), "con caída 0 no manda pitch bend")
    todo &= ok(all(ns[i][1] <= ns[i + 1][0] for i in range(len(ns) - 1)), "no se pisa con la siguiente")

    print("\nBajo zenon: notas largas, a veces sincopadas")
    from goa.bajo import MASCARAS_ZENON
    vistos, en_bombo = set(), []
    for i in range(40):
        comp = por_compas(bajo_notas(2, estilo="zenon", seed=f"Z-{i}", remates=False, movimiento=0, gate=0.95))
        vistos.add(tuple(l for l, _ in comp[0]))
        en_bombo += [i] if {l for l, _ in comp[0]} & {0, 4, 8, 12} else []
    todo &= ok(not en_bombo, f"ninguna figura empieza en el bombo (40 variantes) {en_bombo or ''}")
    todo &= ok(len(vistos) == len(MASCARAS_ZENON), f"la variante recorre las {len(MASCARAS_ZENON)} figuras ({len(vistos)})")
    ns = bajo_notas(2, estilo="zenon", seed="Z-2", remates=False, movimiento=0, gate=0.95)
    largos = [b - a for a, b, _, _ in ns]
    todo &= ok(sum(largos) / len(largos) >= 10, f"notas largas (promedio {sum(largos) / len(largos):.1f} ticks, un paso = 6)")
    out = correr(lambda c: c["bajo"].update(activo=True, salida="BAJO", disparo=0, estilo="zenon", seed="Z-2",
                                            remates=False, movimiento=0, gate=0.95, arco=1.0, arco_alto=12), 4)
    pw = [v for sal, t, tipo, v, _ in out if sal == "BAJO" and tipo == "pitchwheel"]
    todo &= ok(bool(pw) and max(pw) > 8000 and pw[-1] == 0, "arco: el bend sube una octava y vuelve al centro")
    todo &= ok(not any(t == "pitchwheel" for _, _, t, _, _ in correr(lambda c: c["bajo"].update(
        activo=True, salida="BAJO", disparo=0, estilo="zenon", seed="Z-2", arco=0.0), 4)), "sin arco no hay bend")

    print("\nProgresiones nuevas")
    nuevas = ("i_v_bVI_bVII", "iv_bIII_iv_i", "iv_bVII_i_bVII", "i_bIII_bVII_iv", "i_bIII_iv_bVII", "i_ii_bIII_iv")
    todo &= ok(all(k in pads.PROGRESIONES for k in nuevas), "están en pads.PROGRESIONES")
    for clave in nuevas:
        out = correr(lambda c: c["pads"].update(activo=True, salida="PADS", disparo=0, progresion=clave, cambia_cada=1), 8)
        ns = notas(out, "PADS")
        acordes = {}
        for a, _, n, _ in ns:
            acordes.setdefault(a // 96, set()).add(n % 12)
        distintos = len({frozenset(v) for v in acordes.values()})
        todo &= ok(distintos >= 3, f"{clave}: suenan {distintos} acordes distintos")

    print("\nLos ajustes nuevos se guardan")
    cfg = cargar(RAIZ / "config.ejemplo.toml")
    cfg["bajo"].update(estilo="zenon", remates_pack=0.6, ciclo=5, zenon=0.5, caida=5, bend_rango=2, arco=0.4, arco_alto=7)
    cfg["pads"].update(progresion="iv_bIII_iv_i")
    vuelta = normalizar(tomllib.loads(a_toml(normalizar(cfg))))
    perdidos = [k for k, v in (("estilo", "zenon"), ("arco", 0.4), ("arco_alto", 7), ("remates_pack", 0.6), ("ciclo", 5), ("zenon", 0.5), ("caida", 5), ("bend_rango", 2)) if vuelta["bajo"].get(k) != v]
    perdidos += [] if vuelta["pads"]["progresion"] == "iv_bIII_iv_i" else ["progresion"]
    todo &= ok(not perdidos, f"ninguno se pierde al guardar y volver a cargar {perdidos or ''}")

    print("\nTodo bien" if todo else "\nHAY FALLAS")
    return todo


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
