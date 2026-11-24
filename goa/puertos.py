"""goa-ports: lista los puertos MIDI y prueba una salida.

  goa-ports                      lista entradas y salidas
  goa-ports --probar FM-1 2      toca unas notas en la salida "FM-1", canal 2
  goa-ports --escuchar Circuit   muestra lo que llega de la Circuit (Ctrl+C para salir)
  goa-ports --nano-led           pone el nanoKONTROL2 en LED Mode = External (canal global 1)
  goa-ports --nano-led 2         lo mismo si su canal MIDI global es otro
"""

import argparse
import re
import time

import mido


def buscar(nombres, parte):
    from .main import buscar_puerto
    return buscar_puerto(nombres, parte)


def con_numero(nombres):
    """Cada puerto con una pista cuando hay dos aparatos iguales (dos dongles CH345):
    cómo llamarlos en el motor para elegir cada uno («CH345 #2»)."""
    base = [re.sub(r"\s+\d+:\d+$", "", n) for n in nombres]
    vistos = {}
    for n, b in zip(nombres, base):
        vistos[b] = vistos.get(b, 0) + 1
        corto = b.split(":")[-1].strip()
        yield n, (f"(en el motor: «{corto} #{vistos[b]}»)" if base.count(b) > 1 else "")


def main():
    parser = argparse.ArgumentParser(description="Puertos MIDI del motor Goa")
    parser.add_argument("--probar", nargs=2, metavar=("SALIDA", "CANAL"))
    parser.add_argument("--escuchar", metavar="ENTRADA")
    parser.add_argument("--nano-led", nargs="?", const=1, type=int, metavar="CANAL")
    args = parser.parse_args()

    if args.nano_led:
        from . import nano
        nombre = buscar(mido.get_output_names(), "nanoKONTROL2")
        if not nombre:
            print("No encuentro el nanoKONTROL2. Revisa el cable USB.")
            return
        print(f"Escribiendo la escena de fábrica con LED Mode = External en {nombre}...")
        with mido.open_output(nombre) as out:
            nano.led_externo(out, args.nano_led)
        print("Listo. Desenchúfalo y vuelve a enchufarlo, y prueba sus botones (goa-restart si el motor ya corría).")
        return

    if args.probar:
        parte, canal = args.probar[0], int(args.probar[1]) - 1
        nombre = buscar(mido.get_output_names(), parte)
        if not nombre:
            print(f"No encuentro una salida que contenga {parte!r}.")
            return
        print(f"Tocando en {nombre}, canal {canal + 1}...")
        with mido.open_output(nombre) as out:
            for nota in (53, 54, 53, 60, 65):
                out.send(mido.Message("note_on", channel=canal, note=nota, velocity=100))
                time.sleep(0.25)
                out.send(mido.Message("note_off", channel=canal, note=nota, velocity=0))
                time.sleep(0.05)
        print("Listo.")
        return

    if args.escuchar:
        nombre = buscar(mido.get_input_names(), args.escuchar)
        if not nombre:
            print(f"No encuentro una entrada que contenga {args.escuchar!r}.")
            return
        print(f"Escuchando {nombre}. Ctrl+C para salir.")
        relojes = 0
        inicio = time.time()
        with mido.open_input(nombre) as entrada:
            try:
                for msg in entrada:
                    if msg.type == "clock":
                        relojes += 1
                        if relojes % 96 == 0:
                            bpm = 60 * 96 / 24 / (time.time() - inicio)
                            print(f"  reloj OK · ~{bpm:.1f} BPM")
                            inicio = time.time()
                    else:
                        print(" ", msg)
            except KeyboardInterrupt:
                pass
        return

    print("Entradas:")
    for n, extra in con_numero(mido.get_input_names()):
        print("  ", n, extra)
    print("Salidas:")
    for n, extra in con_numero(mido.get_output_names()):
        print("  ", n, extra)


if __name__ == "__main__":
    main()
