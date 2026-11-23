"""LFO de filtro de las secuencias: formas, sincronía al compás, CC solo cuando cambia
y pausa mientras el motor de FX interviene ese filtro.

  python3 -m pruebas.lfo
"""

import copy
import tomllib

from goa.config import normalizar
from goa.secuencia import Secuencia
from pruebas.simular import RAIZ, correr


def ok(cond, texto):
    print(("OK    " if cond else "ERROR ") + texto)
    return bool(cond)


def main():
    todo = True
    base = {"salida": "SEQ", "canal": 2, "lfo": True, "lfo_min": 20, "lfo_max": 100, "lfo_compases": 1}
    vals = {f: [Secuencia(dict(base, lfo_forma=f)).valor_lfo(t) for t in range(0, 97, 12)]
            for f in ("seno", "triangulo", "sube", "baja", "azar")}
    todo &= ok(vals["seno"][0] == 20 and vals["seno"][4] == 100 and vals["seno"][8] == 20, f"seno: abajo, arriba a mitad del compás, abajo ({vals['seno']})")
    todo &= ok(vals["triangulo"][4] == 100 and vals["sube"][0] == 20 and vals["sube"][7] > 85 and vals["baja"][0] == 100,
               "triángulo, sube y baja llegan a sus extremos a tiempo")
    a1 = [Secuencia(dict(base, lfo_forma="azar", seed="X")).valor_lfo(t) for t in range(0, 400, 3)]
    a2 = [Secuencia(dict(base, lfo_forma="azar", seed="X")).valor_lfo(t) for t in range(0, 400, 3)]
    a3 = [Secuencia(dict(base, lfo_forma="azar", seed="Y")).valor_lfo(t) for t in range(0, 400, 3)]
    saltos = max(abs(x - y) for x, y in zip(a1, a1[1:]))
    todo &= ok(a1 == a2 and a1 != a3 and all(20 <= v <= 100 for v in a1) and saltos < 35,
               f"al azar: repetible con la seed, dentro del rango y sin saltos bruscos (salto máximo {saltos})")

    cfg = tomllib.load(open(RAIZ / "config.ejemplo.toml", "rb"))
    cfg = copy.deepcopy(cfg)
    s = cfg["secuencia"][0]
    s.update(salida="SEQ", canal=4, lfo=True, lfo_cc=74, lfo_forma="seno", lfo_compases=2, lfo_min=10, lfo_max=110)
    cfg = normalizar(cfg)
    out = correr(cfg, {0: ("on", 41)}, compases=4)
    cc = [(t, ca, n, v) for t, sal, tipo, ca, n, v in out if sal == "SEQ" and tipo == "control_change" and n == 74]
    todo &= ok(cc and all(ca == 3 for _, ca, _, _ in cc) and min(v for *_, v in cc) <= 12 and max(v for *_, v in cc) >= 108,
               f"el motor manda el CC 74 por el canal de la secuencia y recorre el rango ({len(cc)} mensajes en 4 compases)")
    todo &= ok(all(v1 != v2 for (_, _, _, v1), (_, _, _, v2) in zip(cc, cc[1:])), "solo cuando el valor cambia")
    dos = tomllib.load(open(RAIZ / "config.ejemplo.toml", "rb"))
    dos["secuencia"][0].update(salida="SEQ", canal=4, lfo=True, lfo_cc=74, lfo2=True, lfo2_cc=71, lfo2_forma="triangulo", lfo2_compases=1)
    out = correr(normalizar(dos), {0: ("on", 41)}, compases=2)
    ccs = {n for t, sal, tipo, ca, n, v in out if sal == "SEQ" and tipo == "control_change"}
    todo &= ok(ccs == {74, 71}, f"dos LFO a la vez: corte y resonancia ({sorted(ccs)})")
    sin = copy.deepcopy(cfg)
    sin["secuencia"][0]["lfo"] = False
    out = correr(normalizar(sin), {0: ("on", 41)}, compases=2)
    todo &= ok(not any(tipo == "control_change" and sal == "SEQ" for _, sal, tipo, *_ in out), "apagado no manda nada")

    from goa.motor import Motor
    enviados = []
    m = Motor(cfg, lambda sal, tipo, canal, nota, vel: enviados.append((sal, tipo, nota)))
    m.start()
    m.cc_secuencias[("SEQ", 3, 74)] = (60, 64)  # el FX está interviniendo ese filtro
    for _ in range(96):
        m.reloj()
    todo &= ok(not any(t == "control_change" and n == 74 and s_ == "SEQ" for s_, t, n in enviados),
               "mientras el FX interviene el mismo filtro, el LFO espera")
    print("\nFiltro que se abre en las subidas")
    from goa.fx import curva_filtro
    def subida(**k):
        c = tomllib.load(open(RAIZ / "config.ejemplo.toml", "rb"))
        c["secuencia"][0].update(salida="SEQ", canal=4, cc_filtro=74, filtro_reposo=90, **k)
        c = normalizar(c)
        ev = []
        m = Motor(c, lambda sal, tipo, canal, nota, vel: ev.append((m.tick // 96, sal, tipo, nota, vel)))
        m.start()
        for compas in range(8):
            if compas == 1:
                m.pedir_subida(4)  # empieza en el compás 2 y el drop cae en el 6
            for t in range(96):
                m.reloj()
                if compas == 0 and t == 1:
                    m.nota_on(m.canal_disparo, 41)
                if t == 1 and compas:
                    m.nota_off(m.canal_disparo, 41)
                    m.nota_on(m.canal_disparo, 41)
        return [(c_, v) for c_, sal, tipo, n, v in ev if sal == "SEQ" and tipo == "control_change" and n == 74]
    cc = subida(subida_filtro=True, subida_desde=20, subida_hasta=100)
    durante = [v for c_, v in cc if c_ >= 1][:-1] if cc and cc[-1][1] == 90 else [v for c_, v in cc]
    todo &= ok(durante and durante[0] <= 25 and max(durante) == 100 and durante == sorted(durante),
               f"se abre de 20 a 100 a lo largo de la subida, siempre hacia arriba ({durante[0]} → {max(durante)})")
    todo &= ok(cc[-1][1] == 90, f"después del drop vuelve al reposo ({cc[-1]})")
    queda = subida(subida_filtro=True, subida_desde=20, subida_hasta=100, subida_despues="queda")
    todo &= ok(queda[-1][1] == 100, f"con «se queda ahí» el filtro sigue en 100 después del drop ({queda[-1]})")
    todo &= ok(not subida(), "sin la opción, la subida no toca el filtro")
    todo &= ok(curva_filtro(1.0, 100) == 127 and curva_filtro(1.0, 100, 90) == 90, "con el FX, el final de la subida también se elige (127 por defecto)")
    print("\nLFO de los pads (MicroFreak o MC-101)")
    from goa.motor import Motor
    from pruebas.dialogo import base
    c = normalizar(base())
    c["pads"].update(activo=True, salida="MicroFreak", canal=5, lfo=True, lfo_cc=23, lfo_forma="sube", lfo_compases=1,
                     lfo_min=10, lfo_max=90, lfo2=True, lfo2_cc=83, lfo2_compases=2)
    c = normalizar(c)
    evs, ref = [], {}
    m = Motor(c, lambda sal, tipo, canal, n, v: "m" in ref and tipo == "control_change" and evs.append((max(ref["m"].tick, 0), sal, canal, n, v)))
    ref["m"] = m
    m.start()
    for tick in range(2 * 96):
        m.reloj()
        if tick == 1:
            m.nota_on(m.canal_disparo, 41)
    corte = [(tk, v) for tk, sal, canal, n, v in evs if n == 23]
    todo &= ok(corte and all(sal == "MicroFreak" and canal == 4 for _, sal, canal, n, _ in evs if n in (23, 83)),
               "manda los CC por la salida y el canal de los pads")
    primera = [v for tk, v in corte if tk < 96]
    todo &= ok(primera[0] <= 12 and max(primera) >= 85 and primera == sorted(primera), f"«sube» en un compás de 10 a 90 ({primera[0]} → {max(primera)})")
    todo &= ok(any(n == 83 for _, _, _, n, _ in evs), "el segundo LFO mueve la resonancia (83)")
    c2 = normalizar(dict(c, pads=dict(c["pads"], lfo=False, lfo2=False)))
    evs.clear()
    m.aplicar_config(c2)
    desde = m.tick + 96
    for _ in range(2 * 96):
        m.reloj()
    todo &= ok(not any(n in (23, 83) and tk >= desde for tk, _, _, n, _ in evs), "apagados (desde el compás siguiente), no mandan nada")
    print("\nTodo bien" if todo else "\nHay errores")
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
