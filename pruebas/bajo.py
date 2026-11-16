"""Prueba el generador de líneas de bajo, sin hardware.

  python3 -m pruebas.bajo            desde la carpeta goa-engine
"""

import tomllib

from goa import bajo, generos
from goa.config import a_toml, normalizar
from goa.escalas import Tonalidad
from goa.motor import Motor

from .dialogo import base, colgadas, correr, ok

NOTA_LARGA = 41  # F2, la que manda correr() en cada compás


def armar(genero="goa", modo="guiada", cambia_cada=2, pads=True, **extra):
    cfg = normalizar(generos.aplicar(base(), genero))
    cfg["musica"]["armonia"] = modo
    cfg["dialogo"]["activo"] = False
    cfg["pads"].update(activo=pads, disparo=2, suenan=False, cambia_cada=cambia_cada, variacion=0.0)
    cfg["bajo"].update(dict(activo=True, disparo=2, salida="BAJO", canal=4), **extra)
    return cfg


def notas_de(salida):
    return [(t, n) for t, s, ti, c, n, _ in salida if s == "BAJO" and ti == "note_on"]


def solapes_largos(salida):
    """Veces que dos notas del bajo suenan juntas más de 3 pulsos (el slide se pisa solo un instante)."""
    sonando, malos = {}, 0
    for t, s, ti, c, n, _ in salida:
        if s != "BAJO":
            continue
        if ti == "note_on":
            sonando[n] = t
        else:
            inicio = sonando.pop(n, t)
            malos += sum(1 for m, t0 in sonando.items() if min(t, 10 ** 9) - max(inicio, t0) > 3)
    return malos


def compas(notas, c):
    return [(t % 96, n) for t, n in notas if t // 96 == c]


if __name__ == "__main__":
    todo = True

    print("Estilos")
    for estilo in bajo.ESTILOS:
        cfg = armar("goa", estilo=estilo, evolucion=0.5, mutar_cada=2, slide=0.3, fantasmas=0.4, swing=0.2)
        salida, motor = correr(cfg, compases=16)
        notas = notas_de(salida)
        escala = Tonalidad(cfg["musica"]["tonica"], cfg["musica"]["escala"])
        en_escala = all((n - escala.tonica) % 12 in escala.intervalos for _, n in notas)
        sin_bombo = estilo not in bajo.PSY or all(t % 24 >= 6 for t, _ in notas)
        todo &= ok(notas and en_escala and colgadas(salida) == 0 and not solapes_largos(salida) and sin_bombo,
                   f"{estilo:<14} {len(notas):>3} notas · en la escala, monofónico, sin colgadas"
                   + (", nunca en el tiempo del bombo" if estilo in bajo.PSY else ""))
        todo &= ok(correr(cfg, compases=16)[0] == salida, "  misma variante, mismo bajo (con evolución)")
    tres = notas_de(correr(armar(estilo="tresillo", remates=False), compases=2)[0])
    todo &= ok({t % 24 for t, _ in tres} == {8, 16}, "tresillo: dos notas de tresillo después de cada bombo")
    off = notas_de(correr(armar(estilo="offbeat", remates=False, movimiento=0), compases=2)[0])
    todo &= ok({(t % 96) // 6 for t, _ in off} == {2, 6, 10, 14}, "offbeat: una corchea a contratiempo")
    sal = notas_de(correr(armar(estilo="saltado", remates=False, movimiento=0), compases=2)[0])
    todo &= ok({(t % 96) // 6 % 4 for t, _ in sal} == {1, 3}, "saltado: K B · B")
    full = notas_de(correr(armar(estilo="fullon", remates=False, movimiento=0, cambia_cada=8), compases=2)[0])
    todo &= ok(len({n for _, n in full}) > 1 and compas(full, 0) == compas(full, 1),
               "full-on: celdas melódicas por tiempo que se repiten cada compás")

    print("\nPor género")
    for genero in generos.ORDEN:
        cfg = armar(genero)
        primero = generos.ESTILOS_BAJO_POR_GENERO[genero][0]
        todo &= ok(cfg["bajo"]["estilo"] == primero, f"{generos.GENEROS[genero]['nombre']:<14} pone {primero}")
    todo &= ok(set(bajo.ESTILOS) == {e for es in generos.ESTILOS_BAJO_POR_GENERO.values() for e in es},
               "todos los estilos aparecen en algún género")

    print("\nArmonía guiada")
    for estilo in ("rolling", "galope", "offbeat", "dub"):
        cfg = armar(estilo=estilo, remates=False, movimiento=0.3)
        salida, motor = correr(cfg, compases=16)
        notas = notas_de(salida)
        primeras = [(c, min(compas(notas, c))) for c in range(16) if compas(notas, c)]
        raices = all(n % 12 == motor.pads.momento(c * 16, NOTA_LARGA).raiz % 12 for c, (_, n) in primeras)
        malas = 0
        for c in range(1, 16, 2):  # acordes cada 2 compases
            t, n = max(compas(notas, c))
            m = motor.pads.momento(c * 16 + t // 6, NOTA_LARGA)
            if m.cambia_pronto:
                malas += m.siguiente % 12 not in {motor.tonalidad.nota(n, d, "escala") % 12 for d in (-1, 0, 1)}
        todo &= ok(raices and malas == 0, f"{estilo:<8} empieza cada compás en la raíz y lleva a la raíz que viene")
    notas = notas_de(correr(armar(modo="libre", remates=False, movimiento=0, evolucion=0), compases=8)[0])
    todo &= ok({n % 12 for _, n in notas} == {NOTA_LARGA % 12}, "libre: toca la raíz de su nota larga")

    print("\nFrases, remates y evolución")
    cfg = armar(cambia_cada=8, movimiento=0.6, evolucion=0.0)
    notas = notas_de(correr(cfg, compases=8)[0])
    todo &= ok(compas(notas, 0) == compas(notas, 1) == compas(notas, 2), "los compases de la frase se repiten igual")
    todo &= ok(compas(notas, 3) != compas(notas, 0), "el último compás cierra con un remate")
    todo &= ok([n for _, n in compas(notas, 3)] != [n for _, n in compas(notas, 7)], "los remates alternan entre dos")
    quieto = notas_de(correr(armar(cambia_cada=16, evolucion=0.0, remates=False), compases=16)[0])
    todo &= ok(all(compas(quieto, c) == compas(quieto, 0) for c in range(16)), "evolución 0: no cambia nunca")
    cfg = armar(cambia_cada=16, evolucion=1.0, mutar_cada=4, remates=False)
    vivo = notas_de(correr(cfg, compases=16)[0])
    todo &= ok(compas(vivo, 0) == compas(vivo, 3) and compas(vivo, 4) == compas(vivo, 7),
               "entre mutaciones, los compases se repiten")
    distintos = len({tuple(compas(vivo, c)) for c in (0, 4, 8, 12)})
    todo &= ok(distintos >= 3, f"evolución 1, cada 4 compases: el bajo va cambiando ({distintos} versiones en 16 compases)")

    print("\nOpciones")
    raiz = notas_de(correr(armar(cambia_cada=16, remates=False, movimiento=0), compases=1)[0])
    quinta = notas_de(correr(armar(cambia_cada=16, remates=False, movimiento=0, transponer=4), compases=1)[0])
    todo &= ok({n - r for (_, n), (_, r) in zip(quinta, raiz)} == {7}, "transponer 4 grados: toca la quinta")
    lleno = notas_de(correr(armar(cambia_cada=16, remates=False, densidad=1.0), compases=4)[0])
    ralo = notas_de(correr(armar(cambia_cada=16, remates=False, densidad=0.4), compases=4)[0])
    todo &= ok(len(ralo) < len(lleno) * 0.75 and compas(ralo, 0) == compas(ralo, 1), "densidad: menos golpes, siempre los mismos")
    sw = notas_de(correr(armar(cambia_cada=16, remates=False, swing=0.5), compases=1)[0])
    todo &= ok({t % 12 for t, _ in sw if (t // 6) % 2 == 1} == {9}, "swing: las semicorcheas débiles se atrasan")
    salida = correr(armar(cambia_cada=16, remates=False, slide=1.0, movimiento=1.0), compases=2)[0]
    pisadas = sum(1 for i, (t, s, ti, c, n, _) in enumerate(salida) if s == "BAJO" and ti == "note_on"
                  and any(e[1] == "BAJO" and e[2] == "note_off" and e[0] > t for e in salida[:i]))
    todo &= ok(colgadas(salida) == 0 and not solapes_largos(salida), "slide: se pisan un instante y no quedan colgadas")
    fant = correr(armar(cambia_cada=16, remates=False, fantasmas=1.0, estilo="galope"), compases=1)[0]
    suaves = [v for t, s, ti, c, n, v in fant if s == "BAJO" and ti == "note_on" and v < 60]
    todo &= ok(suaves and all(t % 24 >= 6 for t, n in notas_de(fant)), "notas fantasma: golpes suaves, nunca en el bombo")

    print("\nCambio al vuelo")
    cfg = armar(cambia_cada=16, remates=False, estilo="rolling")
    ev = []
    m = Motor(cfg, lambda sal, tipo, canal, nota, vel: ev.append((m.tick, sal, tipo, nota)))
    m.start()
    for tick in range(4 * 96):
        m.reloj()
        p, r = divmod(tick, 6)
        if r == 1 and p % 16 == 0:
            m.nota_on(1, NOTA_LARGA)
        if tick == 96 + 30:  # a mitad del compás 2
            cfg2 = normalizar(dict(cfg, bajo=dict(cfg["bajo"], estilo="offbeat")))
            m.aplicar_config(cfg2)
            todo &= ok(m.estado()["cambios_en_cola"], "el estilo nuevo queda en cola")
    m.stop()
    ons = [(t, n) for t, s, ti, n in ev if s == "BAJO" and ti == "note_on"]
    resto = [(t % 96) // 6 for t, _ in ons if 96 + 36 <= t < 192]
    nuevo = {(t % 96) // 6 for t, _ in ons if 192 <= t < 288}
    todo &= ok(resto and set(resto) <= {l for l in range(16) if l % 4}, f"el compás en curso termina con el estilo de antes {sorted(set(resto))}")
    todo &= ok(nuevo == {2, 6, 10, 14}, "y el nuevo entra justo en el próximo compás")
    cfg = armar(cambia_cada=16, remates=False, evolucion=1.0, mutar_cada=1)
    m = Motor(cfg, lambda *a: None)
    m.start()
    for tick in range(6 * 96):
        m.reloj()
        if tick % 96 == 1:
            m.nota_on(1, NOTA_LARGA)
    patron = dict(m.bajo.patron)
    m.aplicar_config(normalizar(dict(cfg, bajo=dict(cfg["bajo"], velocidad=90, mutar_cada=16))))
    for tick in range(96):
        m.reloj()
    todo &= ok(patron != m.bajo.base and m.bajo.patron == patron and m.bajo.velocidad == 90,
               "cambiar la fuerza en vivo no borra lo que el bajo ya mutó")

    print("\nConfiguración")
    cfg = armar("chillout")
    todo &= ok(cfg["bajo"]["estilo"] == "dub" and cfg["bajo"]["genero"] == "chillout", "el género para todo también pone el bajo")
    solo = generos.aplicar(armar("goa"), "ambient", parte="bajo")
    todo &= ok(solo["bajo"]["estilo"] == "sub" and solo["pads"]["genero"] == "goa", "el género del bajo no toca a los demás")
    viejo = base()
    viejo["bajo"] = {"estilo": "psy_chill"}
    todo &= ok(normalizar(viejo)["bajo"]["estilo"] == "galope", "una configuración de la v0.18.0 (psy_chill) pasa a galope")
    cfg = normalizar(cfg)
    todo &= ok(normalizar(tomllib.loads(a_toml(cfg))) == cfg, "se guarda y se lee igual")

    print("\nRemates del rolling: marcados, no un desliz")
    from goa.bajo import Bajo
    from goa.escalas import Tonalidad as T
    b = Bajo({"activo": True, "estilo": "rolling", "slide": 1.0, "remates": True, "frase": 4, "remate_var": 0.0}, T("F", "frigio"))
    sal = []
    for paso in range(4 * 16):
        b.paso(paso, paso * 6, 41, None, False, lambda *a: sal.append((paso,) + a))
        b.tick(paso * 6 + 5, lambda *a: sal.append((paso,) + a))
    ons = [(p_, n, v) for p_, _, t, _, n, v in sal if t == "note_on"]
    remate = b.remate(3)
    desde = 3 * 16 + min(remate) // 4 * 4
    rem = [x for x in ons if x[0] >= desde]
    resto = [x for x in ons if x[0] < 3 * 16]
    cortas = all(any(t == "note_off" and n == r[1] and p_ == r[0] for p_, _, t, _, n, _ in sal) for r in rem)
    todo &= ok(sorted(p_ - 48 for p_, _, _ in rem) == sorted(remate) and cortas and min(v for _, _, v in rem) > max(v for _, _, v in resto),
               f"el remate cambia el ritmo, va sin slide (aunque el slide esté al máximo) y acentuado ({len(rem)} notas)")
    import goa.bajo as gb
    def remates_de(var, seed="B-0001", frases=12, rango="octava"):
        bb = Bajo({"activo": True, "estilo": "rolling", "frase": 4, "seed": seed, "remate_var": var, "remate_rango": rango}, T("F", "frigio"))
        return [tuple(sorted(bb.remate(f * 4 + 3).items())) for f in range(frases)]
    clasicos = remates_de(0.0)
    todo &= ok(set(clasicos) == {tuple(sorted(r.items())) for r in gb.REMATES["rolling"]} and clasicos[0] != clasicos[1],
               "variación en 0: se alternan los dos remates clásicos del estilo")
    var = remates_de(0.5)
    todo &= ok(len(set(var)) > 2 and var == remates_de(0.5) and var != remates_de(0.5, seed="B-0777"),
               f"con variación cada frase cambia algunas notas ({len(set(var))} remates distintos en 12 frases), repetible con la variante")
    quinta = remates_de(1.0, rango="quinta")
    todo &= ok(all(g <= 4 for r in quinta for _, g in r) and all(l % 4 for r in remates_de(1.0) for l, _ in r),
               "el rango «hasta la quinta» se respeta y nunca cae en el bombo")

    cierran = all(max(Bajo({"activo": True, "estilo": e, "seed": f"S{k}", "remate_var": v}, T("F", "frigio")).remate(f * 4 + 3))
                  == max(gb.REMATES[e][f % 2]) and
                  set(Bajo({"activo": True, "estilo": e, "seed": f"S{k}", "remate_var": v}, T("F", "frigio")).remate(f * 4 + 3))
                  == set(gb.REMATES[e][f % 2])
                  for e in gb.REMATES if e != "sub" for k in range(20) for v in (0.6, 1.0) for f in range(6))
    todo &= ok(cierran, "con variación cambian alturas (y a veces una nota se alarga): el remate nunca pierde ni gana notas")

    largas = []
    for k in range(40):
        bb = Bajo({"activo": True, "estilo": "rolling", "seed": f"L{k}", "remate_var": 1.0}, T("F", "frigio"))
        r, l = bb._remate(3)
        if l:
            largas.append((bb, r, l))
    bb, r, l = largas[0]
    sal = []
    for paso in range(4 * 16):
        bb.paso(paso, paso * 6, 41, None, False, lambda *a: sal.append((paso,) + a))
        bb.tick(paso * 6 + 5, lambda *a: sal.append((paso,) + a))
    larga = 48 + min(l)
    sig = 48 + min(x for x in r if x > min(l))
    on = next(i for i, x in enumerate(sal) if x[0] == larga and x[2] == "note_on")
    off = next(x for x in sal[on + 1:] if x[2] == "note_off" and x[4] == sal[on][4])
    todo &= ok(largas and off[0] >= sig, f"con variación alta, a veces una nota del remate se alarga hasta la siguiente ({len(largas)} de 40 variantes)")

    print("\nNotas que suben")
    def golpes_sube(sube, estilo="rolling", compases=4):
        bb = Bajo({"activo": True, "estilo": estilo, "sube": sube, "remates": False, "movimiento": 0.0}, T("F", "frigio"))
        return [bb.golpes(c) for c in range(compases)]
    cero = golpes_sube(0.0)
    todo &= ok(all(g.grado == 0 for c in cero for g in c.values()), "en 0 el rolling se queda en la raíz")
    for nivel, tope in ((0.2, 2), (0.6, 4), (1.0, 7)):
        gs = golpes_sube(nivel)
        grados = [g.grado for c in gs for g in c.values()]
        todo &= ok(max(grados) > 0 and max(grados) <= tope and all(l % 4 for c in gs for l in c)
                   and gs[0] != gs[1],
                   f"en {int(nivel * 100)} %: suben notas hasta el grado {max(grados)} (tope {tope}), nunca en el bombo, y cambia entre compases")
    uno, dos = golpes_sube(0.2), golpes_sube(1.0)
    todo &= ok(sum(g.grado > 0 for c in dos for g in c.values()) > sum(g.grado > 0 for c in uno for g in c.values()),
               "más alto el control, más notas suben")
    cfg = armar(estilo="rolling", sube=1.0)
    salida, _ = correr(cfg, compases=8)
    todo &= ok(colgadas(salida) == 0 and not solapes_largos(salida), "con el bajo sonando: sin notas colgadas ni encimadas")

    print("\nTodo bien" if todo else "\nHay errores")
    raise SystemExit(0 if todo else 1)
