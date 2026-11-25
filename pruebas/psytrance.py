"""Pruebas del estilo «Psytrance» (figuras riff, ráfaga, octavas, arpegio y pulsos).

  python3 -m pruebas.psytrance
"""

from goa import generador as g
from goa import generos
from goa.config import cargar, normalizar
from pruebas.escuchar_clasico import eventos
from pruebas.simular import RAIZ


def ok(cond, texto):
    print(("OK    " if cond else "FALLA ") + texto)
    return cond


def main():
    todo = True
    seeds = [f"P{i}" for i in range(40)]

    print("Figuras")
    for fig in g.FIGURAS_PSY:
        if fig == "piano":   # 4 compases con descansos y notas del acorde: se prueba en pruebas/piano.py
            continue
        pats = [g.clasico(s, fig, 4, familia="psytrance") for s in seeds]
        todo &= ok(all(len(p) == 64 for p in pats) and all(len(g.clasico(s, fig, 2, familia="psytrance")) == 32 for s in seeds),
                   f"{fig}: 32 pasos con frase 2, 64 con frase 4")
        raiz = [sum(1 for x in p if x["suena"] and x["grado"] == 0) / max(1, sum(x["suena"] for x in p)) for p in pats]
        if fig == "melodia":   # la melodía camina por grados: se prueba aparte
            continue
        piso = 0.35 if fig == "tresillo" else 0.4   # en LD Protest la raíz es el 44 %
        todo &= ok(min(raiz) >= piso, f"{fig}: la raíz manda ({min(raiz):.0%}-{max(raiz):.0%} de las notas)")
        primeras = [next(x for x in p if x["suena"]) for p in pats]
        todo &= ok(all(x["grado"] == 0 for x in primeras), f"{fig}: la primera nota es la raíz (a veces entra en el paso 2)")
    todo &= ok(len({g.figura_de(f"S{i}", "auto", "psytrance") for i in range(200)}) == len(g.FIGURAS_PSY) - 1,
               "auto: la seed pasa por todas las figuras (menos piano, que se elige a mano)")

    print("\nRiff con huecos")
    llenos = sum(sum(x["suena"] for x in g.clasico(s, "riff", 2, familia="psytrance", huecos=0.0)) for s in seeds)
    vacios = sum(sum(x["suena"] for x in g.clasico(s, "riff", 2, familia="psytrance", huecos=1.0)) for s in seeds)
    todo &= ok(vacios < llenos * 0.75, f"más huecos, menos notas ({llenos} → {vacios})")
    todo &= ok(all(any(not x["suena"] for x in g.clasico(s, "riff", 2, familia="psytrance")[:16]) for s in seeds),
               "el riff siempre deja huecos")
    cortas = [x.get("gate_mult") for s in seeds for x in g.clasico(s, "riff", 2, familia="psytrance") if x["suena"]]
    todo &= ok(cortas.count(0.55) > len(cortas) * 0.6, "notas cortas (staccato) con algunas largas de acento")

    print("\nRáfaga transpuesta")
    p = g.clasico("P1", "rafaga", 4, remate=0.0, familia="psytrance")
    bloques = [p[b * 16 + 5]["grado"] for b in range(4)]
    todo &= ok(len(set(bloques)) >= 2 and all(p[b * 16 + 5]["grado"] == p[b * 16 + 6]["grado"] for b in range(4)),
               f"el bloque repite su nota y cambia de altura por compás {bloques}")

    print("\nPulsos")
    evs = eventos(41, "frigio", dict(figura="pulsos", seed="P1", huecos=0.3, frase=4), None, 4, "psytrance")
    largos = {t for s, t, ti, n, v in evs if s == "LEAD" and ti == "note_on"}
    todo &= ok(all(t % 24 == 0 for t in largos), "una nota por tiempo, en la negra")

    print("\nMísticas")
    evs = eventos(44, "frigio", dict(figura="tresillo", seed="M1", frase=2, remate=0.0), None, 2, "psytrance")
    ons = sorted(t for s, t, ti, n, v in evs if s == "LEAD" and ti == "note_on")
    rel = [t - ons[0] for t in ons[:3]]
    todo &= ok(rel == [0, 8, 16], f"tresillo de corchea: pulsos {rel} (0, 8, 16 de la negra)")
    evs = eventos(45, "frigio", dict(figura="mantra", seed="M1", frase=4, raga="hijaz", ornamentos=0.0), None, 4, "psytrance")
    canto = [n % 12 for s, t, ti, n, v in evs if s == "LEAD" and ti == "note_on" and t >= 3 * 96 + evs[0][1]]
    todo &= ok({10, 1} <= set(canto), "mantra con Hijaz canta el ♭2 y la 3.ª mayor (segunda aumentada)")
    p = g.clasico("M1", "espacio", 2, familia="psytrance")
    todo &= ok(sum(x["suena"] for x in p) <= 12, f"espacio: pocas notas ({sum(x['suena'] for x in p)} en 2 compases)")
    p = g.clasico("M1", "descenso", 2, remate=0.0, familia="psytrance")
    linea = [p[i]["grado"] for i in (2, 6, 10, 14)]
    todo &= ok(all(p[i]["grado"] == 0 for i in (0, 4, 8, 12)) and linea[0] > linea[-1], f"descenso: raíz en cada tiempo y línea que baja {linea}")

    print("\nPuntillo y melodía")
    pats = [g.clasico(s, "puntillo", 2, familia="psytrance") for s in seeds]
    def grupos(p):
        ons = [i for i, x in enumerate(p[:16]) if x["suena"]]
        return [b - a for a, b in zip(ons, ons[1:])]
    todo &= ok(all(grupos(p).count(3) >= 2 for p in pats), "puntillo: agrupa de a 3 semicorcheas (al menos dos grupos de 3)")
    mel = [g.clasico(s, "melodia", 4, familia="psytrance") for s in seeds]
    ultimos = [[x for x in p if x["suena"]][-1]["grado"] for p in mel]
    todo &= ok(all(u == 0 for u in ultimos), "melodía: la frase resuelve en la raíz")
    saltos = [abs(b["grado"] - a["grado"]) for p in mel for a, b in zip([x for x in p if x["suena"]], [x for x in p if x["suena"]][1:])]
    todo &= ok(sum(1 for d in saltos if d <= 2) / len(saltos) > 0.75, "melodía: camina por grados (más de 75 % de pasos cortos)")

    print("\nEn el motor (16 compases)")
    for fig in g.FIGURAS_PSY:
        evs = eventos(41, "frigio", dict(figura=fig, seed="P3", frase=4, variar=0.7, mutacion=0.3, mutar_cada=4), None, 16, "psytrance")
        abiertas, ns = {}, []
        for s, t, ti, n, v in evs:
            if s == "LEAD" and ti == "note_on":
                abiertas[n] = t
            elif s == "LEAD" and ti == "note_off" and n in abiertas:
                ns.append((abiertas.pop(n), t))
        ns.sort()
        pisadas = sum(1 for a, b in zip(ns, ns[1:]) if b[0] < a[1])
        rejilla = 2 if fig == "tresillo" else 6     # el tresillo cae cada 8 pulsos: múltiplos de 2
        todo &= ok(ns and all(a % rejilla == 0 for a, _ in ns) and not pisadas, f"{fig}: {len(ns)} notas en su rejilla, ninguna pisada")

    print("\nGénero Psytrance")
    cfg = normalizar(cargar(RAIZ / "config.ejemplo.toml"))
    nuevo = generos.aplicar(cfg, "psytrance")
    todo &= ok(nuevo["secuencia"][0]["estilo"] == "psytrance" and nuevo["secuencia"][0]["posicion"] == "todos",
               "pone el estilo Psytrance en las secuencias, sonando en todas las semicorcheas")
    todo &= ok(nuevo["bajo"]["estilo"] == "rolling" and nuevo["musica"]["escala"] == "frigio", "bajo rolling y frigio")

    print("\nTodo bien" if todo else "\nHAY FALLAS")
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
