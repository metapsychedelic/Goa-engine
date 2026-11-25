"""Figura «piano» del psytrance (generador.piano_psy): golpes de notas del acorde en un
ciclo de 4 compases, con melancolía y psy. Igual al prototipo que aprobó el usuario.

  python3 -m pruebas.piano
"""

from pathlib import Path

from goa import generador
from goa.config import cargar, normalizar
from goa.motor import Motor

RAIZ = Path(__file__).resolve().parent.parent


def ok(cond, texto):
    print(("  ok   " if cond else "  FALLA ") + texto)
    return cond


def piano(**k):
    return generador.clasico(k.pop("seed", "luna"), figura="piano", familia="psytrance", piano=k)


def ataques(p, compas):
    return [i for i in range(16) if p[compas * 16 + i]["suena"] and not p[compas * 16 + i].get("eco")]


def seed_sin_giro():
    """Una seed cuyo arpegio parte de la raíz (la seed también elige desde qué nota parte)."""
    for k in range(200):
        p = piano(seed=f"s{k}", forma="arp_sube", ritmo="parejo", notas=3, melancolia=0, psy=0, suena="todos")
        if [p[i]["grado"] for i in ataques(p, 0)] == [0, 2, 4]:
            return f"s{k}"


def main():
    todo = True
    print("Forma y lugar")
    p = piano(forma="arp_sube", ritmo="parejo", notas=3, melancolia=0, psy=0, suena="todos")
    todo &= ok(len(p) == 64, "dura 4 compases")
    g = [p[i]["grado"] for i in ataques(p, 0)]
    todo &= ok(g == sorted(g) and all(x % 7 in (0, 2, 4) for x in g), f"arpegio que sube, notas del acorde {g}")
    sg = seed_sin_giro()
    todo &= ok(sg is not None, f"hay seeds que parten de la raíz: R 3 5 ({sg})")
    todo &= ok(ataques(p, 0)[0] % 4 == 0, f"ajuste «tiempo»: parte sobre un tiempo ({ataques(p, 0)})")
    p = piano(forma="arp_sube", ritmo="parejo", notas=3, melancolia=0, psy=0, suena="todos", ajuste="libre")
    todo &= ok(ataques(p, 0) == [6, 7, 8], f"«libre»: centrado exacto ({ataques(p, 0)})")
    p = piano(forma="salto", ritmo="parejo", notas=4, golpes=2, melancolia=0, psy=0, suena="todos")
    todo &= ok(len(ataques(p, 0)) == 8 and ataques(p, 0)[4] - ataques(p, 0)[0] == 8, "dos golpes por compás, a medio compás")
    p = piano(forma="grados_baja", ritmo="parejo", notas=3, separacion=2, melancolia=0, psy=0, suena="todos")
    a = ataques(p, 0)
    todo &= ok(a[1] - a[0] == 2 and a[2] - a[1] == 2, "separación: una semicorchea de aire entre notas")
    p = piano(forma="arp_sube", ritmo="parejo", notas=3, melancolia=0, psy=0, suena="todos", desplazar=2)
    todo &= ok(ataques(p, 0)[0] % 4 == 2, "«dónde cae» corre el golpe sobre el ajuste")

    print("Compases que descansan")
    for suena, mascara in generador.SUENA_PIANO.items():
        p = piano(suena=suena, psy=0)
        suenan = "".join("x" if any(q["suena"] for q in p[b * 16:(b + 1) * 16]) else "." for b in range(4))
        todo &= ok(suenan == mascara, f"{suena}: {suenan}")
    p = piano(suena="medio", inicio=1, psy=0)
    todo &= ok(not any(q["suena"] for q in p[:16]) and any(q["suena"] for q in p[16:32]), "«empieza en» el compás 2")

    print("Melancolía")
    for seed in ("luna", sg):
        p = piano(seed=seed, forma="arp_sube", ritmo="parejo", notas=4, melancolia=1.0, psy=0, suena="todos", rango="abierto")
        g = [p[i]["grado"] for i in ataques(p, 0)]
        todo &= ok(g[-1] % 7 == 2 and g[-2] == g[-1] + 1, f"termina en la tercera con suspiro {g}")
    todo &= ok(any(p[i].get("sostener") for i in ataques(p, 0)), "la última se alarga")
    todo &= ok(all(p[i].get("vel_mult", 1) < 1 for i in ataques(p, 0)), "y todo suena más suave")
    p = piano(forma="arp_sube", ritmo="parejo", notas=4, melancolia=0.4, psy=0, suena="todos", rango="abierto")
    todo &= ok(6 in [p[i]["grado"] for i in ataques(p, 0)], "séptima en vez de octava")
    p = piano(forma="abierto", ritmo="parejo", notas=5, melancolia=0, psy=0, suena="todos", rango="compacto")
    g = [p[i]["grado"] for i in ataques(p, 0)]
    todo &= ok(max(g) - min(g) <= 6 and max(g) <= 9, f"rango compacto: el golpe cabe en una octava {g}")
    p = piano(forma="abierto", ritmo="parejo", notas=5, melancolia=0, psy=0, suena="todos", rango="abierto")
    g2 = [p[i]["grado"] for i in ataques(p, 0)]
    todo &= ok(max(g2) - min(g2) > 7, f"abierto: puede pasar la octava {g2}")

    print("Psy")
    for ajuste, salto in (("tiempo", 4), ("corchea", 2), ("libre", 3)):
        p = piano(forma="arp_sube", ritmo="parejo", notas=3, melancolia=0, psy=1.0, suena="todos", ajuste=ajuste)
        a0, a1 = ataques(p, 0)[0], ataques(p, 1)[0]
        ecos = [i for i in range(16) if p[i].get("eco")]
        todo &= ok((a1 - a0) % 16 == salto, f"{ajuste}: la síncopa corre {salto} ({a0} → {a1})")
        if ajuste != "libre":
            todo &= ok(ecos and all(i % salto == 0 for i in ecos + ataques(p, 0)[:1]), f"{ajuste}: los ecos quedan en la grilla {ecos}")
    p = piano(forma="arp_sube", ritmo="parejo", notas=4, melancolia=0, psy=0.6, suena="todos")
    todo &= ok(sum(1 for q in p[:16] if q.get("semi")) == 1, "♭2 frigia en una nota interior")
    p = piano(psy=0.1, melancolia=0)
    todo &= ok(not any(q.get("semi") for q in p), "con poco psy no hay ♭2")

    print("En el motor")
    cfg = normalizar(cargar(RAIZ / "config.ejemplo.toml"))
    cfg["entrada"].update(canal_disparo=2, nota_maxima=0)
    s = dict(cfg["secuencia"][0], estilo="psytrance", figura="piano", disparo=0, activa=True, posicion="todos",
             piano_suena="todos", piano_psy=0.6, piano_melancolia=0.6, densidad=1.0, armonia="libre")
    cfg["secuencia"] = [s]
    cfg = normalizar(cfg)
    notas = []
    m = Motor(cfg, lambda salida, tipo, canal, a, b: notas.append((tipo, a, b)) if tipo == "note_on" and b else None)
    m.start()
    m.nota_on(1, 45)
    for _ in range(4 * 96):
        m.reloj()
    todo &= ok(len(notas) >= 8, f"suena ({len(notas)} notas en 4 compases)")
    vels = sorted({b for _, _, b in notas})
    todo &= ok(len(vels) >= 2 and vels[0] < cfg["secuencia"][0]["velocidad"], f"ecos y melancolía más suaves {vels}")
    clases = {(a - 45) % 12 for _, a, _ in notas}
    todo &= ok(1 in clases, f"la ♭2 suena sobre la raíz (A → B♭) {sorted(clases)}")

    print("\nTodo bien" if todo else "\nHAY FALLAS")
    return 0 if todo else 1


if __name__ == "__main__":
    raise SystemExit(main())
