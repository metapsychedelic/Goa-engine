"""Circuit Tracks por USB: envíos a reverb/delay de sus sintes, filtro maestro en las
subidas y el FX tocando sus baterías.

  python3 -m pruebas.circuit
"""

import json
from pathlib import Path

from goa.config import cargar, normalizar, salidas
from goa.motor import Motor

RAIZ = Path(__file__).resolve().parent.parent
PULSOS = 96  # por compás


def ok(cond, texto):
    print(("  ok   " if cond else "  FALLA ") + texto)
    return cond


def base(fx=None, **circuit):
    cfg = normalizar(cargar(RAIZ / "config.ejemplo.toml"))
    cfg["entrada"].update(canal_disparo=2, nota_maxima=0)
    cfg["secuencia"] = [dict(s, disparo=0) for s in cfg["secuencia"]]
    cfg["circuit"].update(dict(dict(activo=True), **circuit))
    if fx:
        cfg["fx"].update(fx)
    return normalizar(cfg)


class Registro:
    def __init__(self):
        self.motor = None
        self.msgs = []   # (pulso, salida, tipo, canal, a, b)

    def __call__(self, salida, tipo, canal, a, b):
        t = max(self.motor.tick, 0) if self.motor else 0
        self.msgs.append((t, salida, tipo, canal, a, b))

    def cc(self, numero, canal=15):
        return [(t, a, b) for t, s, tipo, c, a, b in self.msgs
                if s == "Circuit" and tipo == "control_change" and c == canal and a == numero]


def arrancar(cfg):
    r = Registro()
    m = Motor(cfg, r)
    r.motor = m
    m.start()
    m.nota_on(1, 45)
    return m, r


def compases(m, n):
    for _ in range(n * PULSOS):
        m.reloj()


def cambiar(m, **circuit):
    cfg = json.loads(json.dumps(m.base))
    cfg["circuit"].update(circuit)
    m.aplicar_config(normalizar(cfg))


def main():
    todo = True
    print("Envíos")
    m, r = arrancar(base(reverb_s1=40, delay_s2=10))
    compases(m, 2)
    todo &= ok([b for _, _, b in r.cc(88)] == [40], f"al arrancar manda la reverb de Synth 1 una vez {r.cc(88)}")
    todo &= ok([b for _, _, b in r.cc(112)] == [10], "y el delay de Synth 2")
    todo &= ok(r.cc(89) == [] and r.cc(111) == [], "-1 no toca los otros envíos")
    cambiar(m, reverb_s1=100, envios_compases=4)
    compases(m, 5)
    vals = [b for _, _, b in r.cc(88)]
    todo &= ok(vals[-1] == 100 and len(vals) > 20 and all(x < y for x, y in zip(vals, vals[1:])),
               f"un cambio va de a poco hasta 100 ({len(vals)} pasos, de {vals[0]} a {vals[-1]})")
    t = [p for p, _, _ in r.cc(88)]
    todo &= ok(t[-1] - t[1] <= 4 * PULSOS, "y llega en los 4 compases")
    antes = len(r.cc(88))
    cambiar(m, reverb_s1=5, envios_compases=0)
    compases(m, 1)
    todo &= ok([b for _, _, b in r.cc(88)[antes:]] == [5], "con 0 compases salta de golpe")
    m.start()
    compases(m, 1)
    todo &= ok([b for _, _, b in r.cc(88)][-1] == 5 and len(r.cc(88)) == antes + 2, "en cada Start los vuelve a mandar")

    print("Filtro maestro en la subida")
    m, r = arrancar(base(subida_filtro=True, filtro_tipo="pasa_altos", filtro_hasta=40))
    compases(m, 1)
    m.pedir_subida(4)
    compases(m, 6)
    f = r.cc(74)
    vals = [b for _, _, b in f]
    todo &= ok(vals[0] >= 64 and max(vals) == 104, f"pasa altos: sube desde 64 hasta 104 ({vals[0]} … {max(vals)})")
    todo &= ok(vals[-1] == 64, "en el drop vuelve a 64 (apagado)")
    drop = [p for p, _, b in f if b == 64][-1]
    todo &= ok(drop % PULSOS == 0, "y vuelve justo en el uno")
    todo &= ok(all(x <= y for x, y in zip(vals[:-1], vals[1:-1])), "solo sube durante la subida")
    m, r = arrancar(base(subida_filtro=True, filtro_tipo="pasa_bajos", filtro_hasta=50))
    compases(m, 1)
    m.pedir_subida(4)
    compases(m, 3)
    vals = [b for _, _, b in r.cc(74)]
    todo &= ok(vals and max(vals) <= 64 and min(vals) < 40, f"pasa bajos: baja desde 64 ({min(vals)})")
    m.stop()
    todo &= ok(r.cc(74)[-1][2] == 64, "Stop lo devuelve a 64")
    m, r = arrancar(base(subida_filtro=False))
    compases(m, 1)
    m.pedir_subida(4)
    compases(m, 6)
    todo &= ok(r.cc(74) == [], "sin la casilla no toca el filtro")
    m, r = arrancar(base(activo=False, subida_filtro=True, reverb_s1=30))
    compases(m, 1)
    m.pedir_subida(4)
    compases(m, 6)
    todo &= ok(not any(s == "Circuit" for _, s, *_ in r.msgs), "apagado no manda nada a la Circuit")
    m, r = arrancar(base(subida_filtro=True))
    compases(m, 1)
    m.pedir_subida(8)
    compases(m, 3)
    cambiar(m, activo=False)
    compases(m, 1)
    todo &= ok(r.cc(74)[-1][2] == 64, "apagarlo a mitad de la subida devuelve el filtro a 64")

    print("FX en las baterías")
    fx = dict(activo=True, salida="Circuit", canal=10, kit_circuit=True, locura=1.0, fondo=True)
    m, r = arrancar(base(activo=False, fx=fx))
    compases(m, 8)
    m.pedir_subida(4)
    compases(m, 6)
    notas = [(tipo, a) for _, s, tipo, c, a, b in r.msgs if s == "Circuit" and c == 9]
    todo &= ok(any(t == "note_on" for t, _ in notas), f"toca golpes en el canal 10 ({len(notas)} mensajes)")
    todo &= ok({a for _, a in notas} <= {60, 62, 64, 65}, f"solo las notas 60, 62, 64 y 65 {sorted({a for _, a in notas})}")
    otros = [tipo for _, s, tipo, c, a, b in r.msgs if s == "Circuit" and c == 9 and tipo not in ("note_on", "note_off")]
    todo &= ok(not otros, f"sin filtro ni pitch {set(otros)}")
    cfg = json.loads(json.dumps(m.base))
    cfg["fx"]["kit_circuit"] = False
    antes = len(r.msgs)
    m.aplicar_config(normalizar(cfg))
    sueltas = [a for _, s, tipo, c, a, b in r.msgs[antes:] if tipo == "note_off" and c == 9]
    todo &= ok(set(sueltas) <= {60, 62, 64, 65}, "al quitarlo suelta los golpes que sonaban, no otras notas")

    print("Puertos")
    todo &= ok("Circuit" in salidas(base()), "abre el puerto de la Circuit")
    todo &= ok("Circuit" not in salidas(base(activo=False)), "apagado no lo abre")

    print("\nTODO OK" if todo else "\nHAY FALLAS")
    return 0 if todo else 1


if __name__ == "__main__":
    raise SystemExit(main())
