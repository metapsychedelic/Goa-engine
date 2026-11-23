"""Rendimiento del motor: cuánto tarda cada pulso del reloj (24 por negra).

A 140 BPM llega un pulso cada 17,9 ms; en la Pi el motor tiene que quedar muy por
debajo para no atrasar el MIDI. Mide el promedio y los peores pulsos (p99, máximo).

  python3 -m pruebas.rendimiento
"""

import statistics
import time

from .huella_sonora import escenarios


def medir(cfg, compases):
    from goa.motor import Motor
    m = Motor(cfg, lambda *a: None)
    m.start()
    tiempos = []
    for tick in range(compases * 96):
        t0 = time.perf_counter()
        m.reloj()
        tiempos.append(time.perf_counter() - t0)
        if tick % 96 == 1:
            for c in sorted(m.disparos):
                if m.disparos[c].raiz is None:
                    m.nota_on(c, 41)
    tiempos.sort()
    return statistics.mean(tiempos) * 1e6, tiempos[int(len(tiempos) * 0.99)] * 1e6, tiempos[-1] * 1e6


def main():
    esc = escenarios()
    for nombre in ("todos_los_motores", "cancion_template1"):
        cfg, compases = esc[nombre]
        prom, p99, peor = medir(cfg, compases)
        print(f"{nombre:20s} promedio {prom:7.1f} µs · p99 {p99:8.1f} µs · peor {peor:9.1f} µs")


if __name__ == "__main__":
    main()
