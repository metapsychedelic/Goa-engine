"""Pruebas del estilo «Goa clásico» (generador.clasico y su paso por el motor).

  python3 -m pruebas.clasico
"""

from goa import generador as g
from pruebas.escuchar_clasico import eventos


def ok(cond, texto):
    print(("OK    " if cond else "FALLA ") + texto)
    return cond


def grados(patron, desde=0, n=16):
    return [(p["suena"], p["grado"], p["octava"]) for p in patron[desde:desde + n]]


def main():
    todo = True
    seeds = [f"S{i}" for i in range(40)]

    print("Forma de la frase")
    for fig in g.FIGURAS:
        todo &= ok(all(len(g.clasico(s, fig, 2)) == 32 and len(g.clasico(s, fig, 4)) == 64 for s in seeds),
                   f"{fig}: 32 pasos con frase 2, 64 con frase 4")
        todo &= ok(all(g.clasico(s, fig, 4) == g.clasico(s, fig, 4) for s in seeds[:5]), f"{fig}: misma seed, mismo patrón")
        todo &= ok(all(g.clasico(s, fig, 4)[0]["grado"] == 0 and g.clasico(s, fig, 4)[0]["suena"] for s in seeds),
                   f"{fig}: la frase parte en la raíz")
        if fig == "ciclo":
            continue  # el ciclo no calza con el compás: se prueba aparte
        todo &= ok(all(grados(g.clasico(s, fig, 4, remate=0.0), 0) == grados(g.clasico(s, fig, 4, remate=0.0), 16)
                       for s in seeds), f"{fig}: sin respuesta, el compás 2 repite el 1")
        todo &= ok(all(grados(g.clasico(s, fig, 4), 0) == grados(g.clasico(s, fig, 4), 32) for s in seeds),
                   f"{fig}: A B A C (el compás 3 repite el 1)")

    print("\nPedal")
    partes = []
    for s in seeds:
        p = g.clasico(s, "pedal", 2, pedal=0.5)
        sonando = [x for x in p if x["suena"]]
        partes.append(sum(1 for x in sonando if x["grado"] == 0) / len(sonando))
    todo &= ok(min(partes) >= 0.5 and max(partes) <= 0.95, f"la raíz manda: {min(partes):.0%}-{max(partes):.0%} de las notas")
    todo &= ok(all(sum(x["suena"] for x in g.clasico(s, "pedal", 2)[:16]) >= 15 for s in seeds),
               "rodante: 15 o 16 semicorcheas por compás")
    todo &= ok(all({x["octava"] for x in g.clasico(s, "pedal", 2)[:16] if x["grado"] == 0} == {0, 1} for s in seeds),
               "la raíz salta entre dos octavas")
    cambia = [s for s in seeds if grados(g.clasico(s, "pedal", 2, remate=0.6), 8, 8) != grados(g.clasico(s, "pedal", 2, remate=0.6), 24, 8)]
    todo &= ok(len(cambia) == len(seeds), "con respuesta, la segunda mitad del compás 2 cambia")

    print("\nCiclo")
    for largo in (3, 5, 6, 7):
        bien = True
        for s in seeds:
            p = g.clasico(s, "ciclo", 2, remate=0.0, ciclo=largo)
            gr = [x["grado"] for x in p]
            bien &= all(gr[i] == gr[i + largo] for i in range(len(gr) - largo))
            bien &= [i for i, x in enumerate(p) if x["acento"]] == list(range(0, 32, largo))
        todo &= ok(bien, f"ciclo de {largo}: se repite cada {largo} pasos y acentúa cada vuelta")
    todo &= ok(all(max(x["grado"] for x in g.clasico(s, "ciclo", 2, registro=1)) <= 7 for s in seeds),
               "registro 1: no pasa la octava")
    p4 = g.clasico("D9", "ciclo", 4, remate=0.0, ciclo=6)
    todo &= ok(p4[0]["grado"] == 0 and [x["grado"] for x in p4[:6]] == [x["grado"] for x in g.clasico("D9", "ciclo", 4, remate=0.0, ciclo=6)[:6]],
               "el ciclo vuelve a empezar con la frase")

    print("\nAcordes")
    a = g.clasico("E2", "acordes", 4, remate=0.0)
    tiempos = [tuple(x["grado"] for x in a[t * 4:t * 4 + 4] if x["suena"]) for t in range(4)]
    todo &= ok(all(t[0] == 0 for t in tiempos), "cada tiempo parte en la raíz del acorde")
    evs = eventos(45, "frigio", dict(figura="acordes", frase=4, remate=0.0, seed="E2", octava=1), "i_bVI_bVII_v", 8)
    on = [e for e in evs if e[0] == "LEAD" and e[2] == "note_on"]
    t0 = on[0][1]
    raices = [min(e[3] for e in on if (e[1] - t0) // 96 == c) % 12 for c in range(0, 8, 2)]
    todo &= ok(len(set(raices)) == 4, f"sigue la progresión de los pads: raíces {raices}")

    print("\nEn el motor")
    evs = eventos(44, "frigio", dict(figura="pedal", frase=2, remate=0.5, seed="PEDAL-1"), None, 8)
    on = [e for e in evs if e[0] == "LEAD" and e[2] == "note_on"]
    todo &= ok(len(on) >= 8 * 15, f"suena todo el tiempo: {len(on)} notas en 8 compases")
    todo &= ok(all(e[3] % 12 in (8, 9, 11, 1, 3, 4, 6) for e in on), "todas las notas en G# frigio")

    print("\nMutación")
    base = g.clasico("M-1", "ciclo", 2, remate=0.0, ciclo=6)
    mutado = base
    for compas in range(1, 30):
        mutado = g.mutar_clasico(mutado, "M-1", compas, 0.6)
    todo &= ok([x["grado"] for x in mutado[::6]] == [0] * len(mutado[::6]), "la raíz del ciclo nunca muta")
    gr = [x["grado"] for x in mutado]
    todo &= ok(all(gr[i] == gr[i + 6] for i in range(10)), "el ciclo sigue siendo ciclo después de mutar")
    todo &= ok(mutado != base, "pero sí cambia")
    ped = g.clasico("M-2", "pedal", 4, remate=0.5)
    mp = g.mutar_clasico(ped, "M-2", 4, 0.5)
    todo &= ok(grados(mp, 0) == grados(mp, 32), "en el pedal la mutación respeta A B A C")

    print("\nRespuestas distintas")
    for fig in g.FIGURAS:
        base = g.clasico("V-1", fig, 4, remate=0.7)
        otras = [g.con_respuesta(base, g.clasico("V-1", fig, 4, remate=0.7, vuelta=v), 4) for v in (1, 2, 3)]
        todo &= ok(all(grados(o, 0) == grados(base, 0) and grados(o, 32) == grados(base, 32) for o in otras),
                   f"{fig}: el compás A no cambia entre vueltas")
        todo &= ok(len({tuple(grados(o, 48)) for o in otras + [base]}) >= 2, f"{fig}: la respuesta C sí cambia")
    todo &= ok(g.clasico("V-1", "pedal", 4, vuelta=0) == g.clasico("V-1", "pedal", 4), "la vuelta 0 es el patrón de siempre")
    ajustes = dict(figura="pedal", frase=4, remate=0.7, seed="V-2")
    fijo = eventos(44, "frigio", ajustes, None, 16)
    vario = eventos(44, "frigio", dict(ajustes, variar=1.0), None, 16)
    notas_de = lambda evs, c0, c1: [e[3] for e in evs if e[0] == "LEAD" and e[2] == "note_on" and c0 * 96 <= e[1] < c1 * 96]  # noqa: E731
    todo &= ok(notas_de(fijo, 0, 4) == notas_de(fijo, 4, 8), "sin variar, la frase se repite igual")
    todo &= ok(notas_de(vario, 0, 4) == notas_de(fijo, 0, 4) and notas_de(vario, 4, 8) != notas_de(vario, 0, 4),
               "con variar, la segunda vuelta trae otra respuesta")
    todo &= ok(notas_de(vario, 4, 5) == notas_de(vario, 0, 1), "pero el compás A de la segunda vuelta es el mismo")

    print("\nTecho")
    alto = dict(figura="ciclo", ciclo=3, registro=3, frase=2, remate=0.0, seed="OCT-3", octava=2)
    sin = [e[3] for e in eventos(44, "frigio", alto, None, 4) if e[0] == "LEAD" and e[2] == "note_on"]
    con = [e[3] for e in eventos(44, "frigio", dict(alto, techo=79), None, 4) if e[0] == "LEAD" and e[2] == "note_on"]
    todo &= ok(max(sin) > 79 and max(con) <= 79, f"techo G5: la más alta pasa de {max(sin)} a {max(con)}")
    todo &= ok([n % 12 for n in sin] == [n % 12 for n in con] and len(sin) == len(con), "mismas notas y mismo ritmo, solo más graves")

    print("\nDeslices")
    aj = dict(figura="pedal", frase=4, remate=0.6, seed="PEDAL-1")
    lead = lambda evs: [(e[1], e[3]) for e in evs if e[0] == "LEAD" and e[2] == "note_on"]  # noqa: E731
    clases = lambda ns: {n % 12 for _, n in ns}  # noqa: E731
    golpes = lambda ns: len({t // 6 for t, _ in ns})  # noqa: E731
    base = lead(eventos(44, "frigio", aj, None, 8))
    todo &= ok(lead(eventos(44, "frigio", dict(aj, deslices=0.0), None, 8)) == base, "en 0 suena igual que sin el control")
    alto = lead(eventos(44, "frigio", dict(aj, deslices=1.0), None, 8))
    todo &= ok(clases(alto) <= {8, 9, 11, 1, 3, 4, 6}, "no cambia la escala (sigue en G# frigio)")
    todo &= ok(golpes(alto) < golpes(base), f"respira: ataca menos pasos ({golpes(base)} → {golpes(alto)})")
    todo &= ok(len(set(alto)) and alto != base, "suma aproximaciones en la rejilla")

    def medir(aj):
        """(notas fuera de la rejilla, notas de 2 pulsos o menos, notas que se pisan)."""
        evs = eventos(44, "frigio", aj, None, 16)
        abiertas, ns = {}, []
        for sal, t, tipo, n, v in evs:
            if sal == "LEAD" and tipo == "note_on":
                abiertas[n] = t
            elif sal == "LEAD" and tipo == "note_off" and n in abiertas:
                ns.append((abiertas.pop(n), t))
        ns.sort()
        return (sum(1 for a, b in ns if a % 6), sum(1 for a, b in ns if b - a <= 2),
                sum(1 for (a1, b1), (a2, b2) in zip(ns, ns[1:]) if a2 < b1))

    print("\nEn la rejilla (sin redobles ni notas pisadas)")
    ci = dict(figura="ciclo", ciclo=6, registro=2, frase=4, remate=0.6, seed="D9", octava=1, variar=0.5)
    for nombre, extra in (("deslices 100 %", dict(aj, deslices=1.0)), ("Bhairav pedal", dict(aj, raga="bhairav", ornamentos=1.0)),
                          ("Todi ciclo", dict(ci, raga="todi", ornamentos=1.0)), ("Hijaz ciclo", dict(ci, raga="hijaz", ornamentos=1.0)),
                          ("Hijaz + deslices", dict(ci, raga="hijaz", ornamentos=1.0, deslices=1.0))):
        todo &= ok(medir(extra) == (0, 0, 0), f"{nombre}: todo en semicorcheas, nada de fusas ni pisadas {medir(extra)}")

    print("\nRagas")
    from goa import raga
    todo &= ok(all(len(r["escala"]) == 7 for r in raga.RAGAS.values()), "todas las ragas tienen 7 notas (sirven en «transponer»)")
    todo &= ok(all(all(c in r["escala"] for c in r["pakad"]) and all(c in r["escala"] for c in r["oscila"])
                   for r in raga.RAGAS.values()), "frases típicas y notas que tiemblan están en su escala")
    for nombre, r in raga.RAGAS.items():
        evs = eventos(40, "frigio", dict(aj, raga=nombre, ornamentos=0.8, bend_rango=2), None, 8)
        ns = lead(evs)
        fuera = clases(ns) - {(40 + c) % 12 for c in r["escala"]}
        bends = [e for e in evs if e[0] == "LEAD" and e[2] == "pitchwheel"]
        todo &= ok(not fuera, f"{r['nombre']}: todas las notas en su escala desde E")
        todo &= ok(bends and bends[-1][3] == 0 and max(abs(e[3]) for e in bends) <= 8192,
                   f"{r['nombre']}: {len(bends)} mensajes de pitch bend (meend/andolan) y termina al centro")
    sin_bend = [e for e in eventos(40, "frigio", dict(aj, raga="bhairav", ornamentos=1.0, bend_rango=0), None, 8)
                if e[2] == "pitchwheel"]
    todo &= ok(not sin_bend, "con rango 0 no manda pitch bend")
    solo = lead(eventos(40, "frigio", dict(aj, raga="bhairav", ornamentos=0.0), None, 8))
    todo &= ok(golpes(solo) == golpes(lead(eventos(40, "frigio", aj, None, 8))), "ornamentos 0: solo cambia la escala")
    p = g.clasico("B7", "pedal", 4, remate=0.8, raga="bhairav")
    todo &= ok([x["grado"] for x in p[-4:]] == [9, 10, 8, 7], "Goa clásico con Bhairav cierra con G m r S (sobre la raíz)")

    print("\nTodo bien" if todo else "\nHAY FALLAS")
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
