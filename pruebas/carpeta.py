"""Pruebas de lo sacado del análisis de la carpeta de MIDIs (0.54): bajo sincopado,
remate en fusas, voz doble de las secuencias y stabs de acordes en los pads.

  python3 -m pruebas.carpeta
"""

from goa.config import cargar, normalizar
from goa.motor import Motor
from pruebas.simular import RAIZ


def ok(cond, texto):
    print(("OK    " if cond else "FALLA ") + texto)
    return cond


def correr(ajustar, compases=4):
    cfg = cargar(RAIZ / "config.ejemplo.toml")
    cfg["entrada"].update(canal_disparo=2, nota_maxima=0)
    cfg["musica"].update(tonica="F", escala="frigio")
    for s in cfg["secuencia"]:
        s["activa"] = False
    cfg["bajo"]["activo"] = False
    cfg["pads"]["activo"] = False
    ajustar(cfg)
    cfg = normalizar(cfg)
    out = []
    m = Motor(cfg, lambda sal, tipo, canal, nota, vel: out.append((sal, m.tick, tipo, nota, vel)))
    m.start()
    m.nota_on(1, 41)
    for _ in range(compases * 96):
        m.reloj()
    m.stop()
    return out


def notas(out, salida):
    abiertas, res = {}, []
    for sal, t, tipo, n, v in out:
        if sal != salida:
            continue
        if tipo == "note_on":
            abiertas[n] = (t, v)
        elif tipo == "note_off" and n in abiertas:
            t0, v0 = abiertas.pop(n)
            res.append((t0, t, n, v0))
    return sorted(res)


def main():
    todo = True

    print("Bajo sincopado")
    out = correr(lambda c: c["bajo"].update(activo=True, salida="BAJO", disparo=0, estilo="sincopado", frase=4))
    ns = notas(out, "BAJO")
    t0 = ns[0][0] - ns[0][0] % 96
    lugares = {((a - t0) % 96) // 6 for a, _, _, _ in ns}
    todo &= ok(not lugares & {0, 4, 8, 12}, f"nunca cae en el bombo (pasos {sorted(lugares)})")
    todo &= ok({2, 3, 6, 11} <= lugares, "toca en la «y» y la «a» del tiempo (..xx..x...xx..x.)")

    print("\nRemate en fusas")
    sin = notas(correr(lambda c: c["bajo"].update(activo=True, salida="BAJO", disparo=0, estilo="rolling", frase=4)), "BAJO")
    con = notas(correr(lambda c: c["bajo"].update(activo=True, salida="BAJO", disparo=0, estilo="rolling", frase=4,
                                                  fusas=1.0)), "BAJO")
    fusas = [a for a, b, n, v in con if (a - t0) % 6 == 3]
    todo &= ok(len(con) > len(sin) and bool(fusas), f"el compás que cierra suma fusas ({len(sin)} → {len(con)} notas)")
    todo &= ok(all(((a - t0) // 96) % 4 == 3 for a in fusas), "solo en el compás que cierra la frase")
    todo &= ok(all(con[i][1] <= con[i + 1][0] for i in range(len(con) - 1)), "las fusas no se pisan")

    print("\nVoz doble")
    def sec(doble):
        def ajustar(c):
            c["secuencia"][0].update(activa=True, salida="LEAD", disparo=0, estilo="psytrance", figura="riff",
                                     posicion="todos", seed="P1", doble=doble, octava=1)
        return notas(correr(ajustar, 2), "LEAD")
    sola, doble = sec(""), sec("cuarta")
    todo &= ok(len(doble) == 2 * len(sola), f"cada nota suma su cuarta ({len(sola)} → {len(doble)})")
    pares = {}
    for a, b, n, v in doble:
        pares.setdefault(a, []).append(n)
    intervalos = {max(x) - min(x) for x in pares.values() if len(x) == 2}
    todo &= ok(intervalos <= {4, 5, 6}, f"la segunda voz va una cuarta de escala arriba (semitonos {sorted(intervalos)})")

    print("\nStabs de acordes en los pads")
    def pads(ritmo, pulso):
        def ajustar(c):
            c["pads"].update(activo=True, suenan=True, salida="PADS", disparo=0, ritmo=ritmo, pulso=pulso,
                             progresion="i_bII", cambia_cada=4)
        return notas(correr(ajustar, 2), "PADS")
    for k, mascara in enumerate(("....xx.xx.x.x.x.", "x...x.xx.xx.x.x.")):
        ns = pads("stabs", k + 1)
        golpes = sorted({(a % 96) // 6 for a, _, _, _ in ns})   # el rasgueo corre las voces 1-3 pulsos
        esperado = [i for i, ch in enumerate(mascara) if ch == "x"]
        todo &= ok(golpes == esperado, f"pulso {k + 1}: acordes en {mascara}")
    euclides = pads("euclides", 4)
    todo &= ok(bool(euclides) and all(((a % 96) // 6) % 2 == 0 for a, _, _, _ in euclides), "el pulso parejo sigue en corcheas")

    print("\nLos ajustes nuevos se guardan (como en la app)")
    import tomllib
    from goa.config import a_toml
    cfg = cargar(RAIZ / "config.ejemplo.toml")
    sec = dict(estilo="psytrance", figura="puntillo", frase=4, remate=0.7, ciclo=5, registro=3, variar=0.6, huecos=0.2,
               techo=80, doble="cuarta", deslices=0.4, raga="hijaz", ornamentos=0.8, bend_rango=12)
    cfg["secuencia"][0].update(sec)
    cfg["bajo"].update(estilo="sincopado", fusas=0.7)
    cfg["pads"].update(ritmo="stabs", pulso=3, progresion="i_iv_bVI_bIII")
    vuelta = normalizar(tomllib.loads(a_toml(normalizar(cfg))))
    perdidos = [k for k, v in sec.items() if vuelta["secuencia"][0].get(k) != v]
    perdidos += [k for k, v in (("estilo", "sincopado"), ("fusas", 0.7)) if vuelta["bajo"].get(k) != v]
    perdidos += [k for k, v in (("ritmo", "stabs"), ("pulso", 3)) if vuelta["pads"].get(k) != v]
    todo &= ok(not perdidos, f"ninguno se pierde al guardar y volver a cargar {perdidos or ''}")

    print("\nRestaurar ajustes de fábrica (una secuencia)")
    from goa.config import ESQUEMA_SECUENCIA, fabrica_secuencia
    from goa.motor import Motor
    cfg = normalizar(cargar(RAIZ / "config.ejemplo.toml"))
    propia = dict(nombre="Lead", salida="MicroFreak", canal=5, programa=12, disparo=3, seed="MIO-7", cc_filtro=23, genero="psytrance")
    cfg["secuencia"][0].update(propia, estilo="psytrance", figura="riff", mutacion=0.8, separar=True, corrimiento=3,
                               raga="hijaz", lfo=True, swing=0.3, octava=2, activa=True)
    otra = dict(cfg["secuencia"][1])
    cfg["secuencia"][0] = fabrica_secuencia(cfg["secuencia"][0])
    cfg = normalizar(cfg)
    s0 = cfg["secuencia"][0]
    todo &= ok(all(s0[k] == v for k, v in propia.items()) and s0["activa"], "conserva salida, canal, programa, nota larga, nombre, seed, CC y género")
    fabrica = {k: v[1] for k, v in ESQUEMA_SECUENCIA.items()}
    distintos = [k for k in fabrica if k not in propia and k != "activa" and s0[k] != fabrica[k]]
    todo &= ok(not distintos, f"todo lo demás queda de fábrica {distintos or ''}")
    todo &= ok(cfg["secuencia"][1] == normalizar({"secuencia": [otra]})["secuencia"][0] or cfg["secuencia"][1] == otra,
               "no toca las otras secuencias")
    m = Motor(cfg, lambda *a: None)
    m.start()
    m.nota_on(1, 45)
    for _ in range(96 * 4):
        m.reloj()
    todo &= ok(True, "el motor arranca con la secuencia restaurada")
    base = dict(cfg, entrada=dict(cfg["entrada"], canal_disparo=2, nota_maxima=0))
    base["secuencia"] = [dict(x, disparo=0) for x in cfg["secuencia"]]
    original = Motor(normalizar(base), lambda *a: None).secuencias[0].patron
    mutando = dict(base, secuencia=[dict(base["secuencia"][0], mutacion=1.0, mutar_cada=1, mutacion_ritmo=0.5), base["secuencia"][1]])
    m = Motor(normalizar(mutando), lambda *a: None)
    m.start()
    m.nota_on(1, 45)
    for _ in range(96 * 12):
        m.reloj()
    muto = m.secuencias[0].patron != original
    m.aplicar_config(normalizar(dict(mutando, secuencia=[fabrica_secuencia(mutando["secuencia"][0]), mutando["secuencia"][1]])))
    m.reiniciar_secuencia(0)
    todo &= ok(muto and m.secuencias[0].patron == original, "deshace lo que mutó aunque solo cambie la mutación")

    print("\nTodo bien" if todo else "\nHAY FALLAS")
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
