"""Simula la Circuit: reloj, Start y notas largas, sin hardware.

  python3 -m pruebas.simular            desde la carpeta goa-engine
"""

import tomllib
from pathlib import Path

from goa.escalas import nombre_midi
from goa.motor import Motor

RAIZ = Path(__file__).resolve().parent.parent


def correr(config, eventos, compases=4):
    """eventos: dict {paso: ("on"|"off", nota)} enviados justo después del pulso."""
    salida = []
    motor = Motor(config, lambda sal, tipo, canal, nota, vel: salida.append((motor.tick, sal, tipo, canal, nota, vel)))
    motor.start()
    for tick in range(compases * 16 * 6):
        motor.reloj()
        paso, resto = divmod(tick, 6)
        if resto == 1 and paso in eventos:  # llega 1 pulso tarde, como en la vida real
            tipo, nota = eventos[paso]
            (motor.nota_on if tipo == "on" else motor.nota_off)(motor.canal_disparo, nota)
    motor.stop()
    return salida


def mostrar(salida, nombre):
    pasos = {}
    for tick, sal, tipo, canal, nota, vel in salida:
        if tipo == "note_on" and sal == nombre:
            pasos[tick // 6] = (nota, vel)
    for compas in range(max(pasos) // 16 + 1 if pasos else 0):
        fila = []
        for p in range(compas * 16, compas * 16 + 16):
            if p in pasos:
                nota, vel = pasos[p]
                n = nombre_midi(nota)
                fila.append(n.upper() if vel >= 110 else n.lower())
            else:
                fila.append("·")
        print(f"  compás {compas + 1}: " + " ".join(f"{x:>4}" for x in fila))


if __name__ == "__main__":
    with open(RAIZ / "config.ejemplo.toml", "rb") as f:
        config = tomllib.load(f)
    config["secuencia"][1]["activa"] = True

    # F2 sostenida 2 compases, luego Gb2 1 compás, luego se suelta.
    eventos = {0: ("on", 41), 32: ("off", 41), 33: ("on", 42), 48: ("off", 42)}
    salida = correr(config, eventos, compases=4)

    for s in ("FM-1", "MicroFreak"):
        print(f"\n{s} (MAYÚSCULA = acento)")
        mostrar(salida, s)

    ons = sum(1 for x in salida if x[2] == "note_on")
    offs = sum(1 for x in salida if x[2] == "note_off")
    print(f"\nnote_on: {ons} · note_off: {offs} · {'OK, sin notas colgadas' if ons == offs else 'ERROR: notas colgadas'}")

    otra = correr(config, eventos, compases=4)
    print("Misma seed, misma salida:", "OK" if otra == salida else "ERROR")
