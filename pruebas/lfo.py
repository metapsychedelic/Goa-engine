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
    print("\nTodo bien" if todo else "\nHay errores")
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
