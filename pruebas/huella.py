"""La franja «Lo que toca ahora» del editor de secuencia: la huella que anota el motor
tiene que ser lo que de verdad salió por MIDI, paso por paso.

  python3 -m pruebas.huella
"""

from goa.config import normalizar
from goa.motor import Motor

from .dialogo import base, ok


def main():
    todo = True
    cfg = normalizar(base())
    for i, s in enumerate(cfg["secuencia"]):
        s.update(activa=i == 0, disparo=2, mutacion=0, mutacion_ritmo=0, canal=12)  # un canal solo para ella
    cfg["pads"]["activo"] = False
    salidas = []
    ref = {}
    m = Motor(cfg, lambda sal, tipo, canal, n, v: tipo == "note_on" and v > 0 and "m" in ref
              and salidas.append((max(ref["m"].tick, 0), (sal, canal), n)))
    ref["m"] = m
    s = m.secuencias[0]
    m.start()
    for tick in range(3 * 96):
        m.reloj()
        if tick == 1:
            m.nota_on(1, 45)
    s = m.secuencias[0]
    huella = s.huella
    todo &= ok(len(huella) == s.largo, f"la huella mide lo que el patrón ({len(huella)} pasos)")
    todo &= ok(sum(1 for p in huella if p) > 0, f"anotó notas ({sum(1 for p in huella if p)})")
    # El último compás: lo que salió por el canal de la secuencia, paso a paso.
    reales = {}
    for t, c, n in salidas:
        if c == (s.salida, s.canal) and t >= 2 * 96:
            reales.setdefault((t - 2 * 96) // 6, set()).add(n)
    vistos = {i: p[0] for i, p in enumerate(huella) if p}
    todo &= ok(set(vistos) == set(reales), f"calla y suena en los mismos pasos {sorted(vistos)} / {sorted(reales)}")
    todo &= ok(all(vistos[i] in reales[i] for i in vistos), "con las mismas notas")
    todo &= ok(s.huella_paso == 15, f"marca el último paso tocado ({s.huella_paso})")
    s.activa = False
    for _ in range(96):
        m.reloj()
    todo &= ok(not any(s.huella), "apagada, la huella queda vacía")
    print("\n" + ("Todo bien" if todo else "HAY FALLAS"))
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
