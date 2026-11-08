"""goa-ports: lista los puertos MIDI y prueba una salida.

  goa-ports                      lista entradas y salidas
  goa-ports --probar FM-1 2      toca unas notas en la salida "FM-1", canal 2
  goa-ports --escuchar Circuit   muestra lo que llega de la Circuit (Ctrl+C para salir)
"""

import argparse
import time

import mido


def buscar(nombres, parte):
    for n in nombres:
        if parte.lower() in n.lower():
            return n
    return None


def main():
    parser = argparse.ArgumentParser(description="Puertos MIDI del motor Goa")
    parser.add_argument("--probar", nargs=2, metavar=("SALIDA", "CANAL"))
    parser.add_argument("--escuchar", metavar="ENTRADA")
    args = parser.parse_args()

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
    for n in mido.get_input_names():
        print("  ", n)
    print("Salidas:")
    for n in mido.get_output_names():
        print("  ", n)


if __name__ == "__main__":
    main()
