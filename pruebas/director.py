"""Prueba el director (variación de mediano y largo plazo), sin hardware.

  python3 -m pruebas.director            desde la carpeta goa-engine
"""

import copy

from goa import director
from goa.config import normalizar
from goa.motor import Motor

from .dialogo import base, colgadas, ok


def armar(variacion=1.0, periodo=16):
    cfg = normalizar(base())
    cfg["dialogo"].update(activo=True, disparo=2)
    cfg["pads"].update(activo=True, disparo=2, salida="PADS")
    cfg["bajo"].update(activo=True, disparo=2, salida="BAJO")
    cfg["secuencia"][0].update(activa=True, disparo=2, salida="SEC", mutacion=0.0)
    cfg["secuencia"][1].update(activa=True, disparo=2, salida="SEC2", mutacion=0.0)
    cfg["forma"].update(variacion=variacion, periodo=periodo)
    return cfg


def correr(cfg, compases):
    ev, efectos, patrones = [], {}, {}
    m = Motor(cfg, lambda sal, tipo, canal, nota, vel: ev.append((m.tick, sal, tipo, canal, nota, vel)))
    m.start()
    for tick in range(compases * 96):
        m.reloj()
        p, r = divmod(tick, 6)
        if r == 1 and p % 16 == 0:
            m.nota_on(1, 41)
        if r == 3 and p % 16 == 0:
            c = p // 16
            efectos[c] = tuple(m.director.descripcion(m))
            patrones[c] = [copy.deepcopy(s.patron) for s in m.secuencias]
    m.stop()
    return ev, efectos, patrones, m


if __name__ == "__main__":
    todo = True

    print("Transformaciones de un motivo")
    pat = [{"suena": True, "grado": g, "acento": False} for g in (0, 2, 4, 1)]
    todo &= ok([p["grado"] for p in director.transformar(pat, "tercera")] == [2, 4, 6, 3], "una tercera arriba")
    todo &= ok([p["grado"] for p in director.transformar(pat, "espejo")] == [0, -2, -4, -1], "en espejo")
    todo &= ok([p["grado"] for p in director.transformar(pat, "corrido")] == [1, 0, 2, 4], "corrido en el tiempo")

    print("\nCon variación al máximo, 80 compases, períodos de 16")
    cfg = armar()
    ev, efectos, patrones, m = correr(cfg, 80)
    por_periodo = [efectos[c] for c in (8, 24, 40, 56, 72)]
    print("      " + " | ".join(", ".join(e) or "—" for e in por_periodo))
    todo &= ok(not por_periodo[0], "el primer período suena tal como lo armaste")
    todo &= ok(all(por_periodo[1:]), "después cada período trae algo")
    todo &= ok(len(set(por_periodo[1:])) >= 3, "y no siempre lo mismo")
    todo &= ok(all(efectos[c] == efectos[c - c % 16] for c in efectos if c % 16), "los cambios solo entran en el borde del período")
    todo &= ok(m.base == normalizar(cfg) or m.base == cfg, "tu configuración no cambia")
    todo &= ok(colgadas(ev) == 0, "ninguna nota colgada (con cambios de sinte y pads que se callan)")

    print("\nTodo vuelve al terminar el período")
    original = patrones[8]
    revisados, vuelve = 0, True
    for c in (24, 40, 56, 72):
        for i, nombre in enumerate(("A", "B")):
            if not any(x.startswith(nombre + ":") and ("hermana" in x or "motivo" in x) for x in efectos[c]):
                revisados += 1
                vuelve &= patrones[c][i] == original[i]
    todo &= ok(vuelve and revisados > 0, f"cuando no le toca, cada secuencia vuelve a su patrón original ({revisados} casos)")
    hermanas = [c for c in efectos if any("hermana" in t for t in efectos[c])]
    if hermanas:
        c = hermanas[0]
        i = 0 if any(t.startswith("A:") and "hermana" in t for t in efectos[c]) else 1
        distintas = sum(a["grado"] != b["grado"] for a, b in zip(patrones[c][i], original[i]) if a["suena"])
        suenan = sum(1 for p in original[i] if p["suena"])
        todo &= ok(0 < distintas <= max(2, suenan // 2), f"la variante hermana cambia pocas notas ({distintas} de {suenan})")

    print("\nDeterminista y respetuoso")
    ev2, efectos2, _, _ = correr(armar(), 80)
    todo &= ok(ev2 == ev and efectos2 == efectos, "la misma configuración hace el mismo viaje")
    _, efectos0, _, _ = correr(armar(variacion=0.0), 48)
    todo &= ok(not any(efectos0.values()), "con variación en 0 el director no hace nada")
    congelada = armar()
    for s in congelada["secuencia"]:
        s["bloqueada"] = True
    _, efectos_c, patrones_c, _ = correr(congelada, 80)
    todo &= ok(all(p == patrones_c[8] for p in patrones_c.values()), "una secuencia congelada nunca cambia")
    _, efectos32, _, _ = correr(armar(periodo=32), 80)
    todo &= ok(not efectos32[20] and bool(efectos32[40]), "con períodos de 32, el primer cambio llega en el compás 33")

    print("\nClips con el director andando")
    fallas, entraron = 0, 0
    for largo in (8, 16, 32):
        for estilo in ("rolling", "acido", "arpegio3"):
            cfg = armar()
            m = Motor(cfg, lambda *a: None)
            m.start()
            try:
                for tick in range(60 * 96):
                    m.reloj()
                    if tick % 96 == 1:
                        m.nota_on(1, 41)
                    if tick % (7 * 96) == 300:  # a mitad de un período, con cambios del director puestos
                        for fila in (0, 1):
                            nueva = dict(cfg["secuencia"][fila], estilo=estilo, largo=largo, seed=f"{tick:04X}-CLIP")
                            m.lanzar(fila, nueva, "clip")
                            entraron += 1
            except Exception:  # noqa: BLE001
                fallas += 1
    todo &= ok(fallas == 0 and entraron > 0, f"un clip con otro largo o estilo entra sin romper nada ({entraron} clips)")
    cfg = armar()
    m = Motor(cfg, lambda *a: None)
    m.start()
    pegados = 0
    for tick in range(60 * 96):
        m.reloj()
        if tick % 96 == 1:
            m.nota_on(1, 41)
        if tick == 20 * 96 + 50:
            m.lanzar(1, dict(cfg["secuencia"][1], seed="OTRO-CLIP"), "clip")
        if tick % 96 == 10 and tick > 21 * 96:
            s = m.secuencias[1]
            if 21 * 96 < tick < 32 * 96:  # el período en que entró el clip
                pegados += getattr(s, "_director_patron", None) is not None
    todo &= ok(pegados == 0, "un cambio pensado para el patrón anterior no se pega encima del clip nuevo")

    print("\nTODO BIEN" if todo else "\nHAY ERRORES")
    raise SystemExit(0 if todo else 1)
