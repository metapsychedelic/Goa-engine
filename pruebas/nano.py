"""nanoKONTROL2: LED Mode = External sin el Kontrol Editor (goa/nano.py).

  python3 -m pruebas.nano
"""

import sys
import types

from goa import nano


def ok(cond, texto):
    print(("  ok   " if cond else "  FALLA ") + texto)
    return cond


class Puerto:
    def __init__(self):
        self.enviados = []

    def send(self, msg):
        self.enviados.append(msg)


def main():
    todo = True
    falso = types.SimpleNamespace(Message=lambda tipo, data: (tipo, bytes(data)))
    sys.modules.setdefault("mido", falso)
    p = Puerto()
    nano.led_externo(p, 1, pausa=0)
    tipos = {t for t, _ in p.enviados}
    datos = [d for _, d in p.enviados]
    todo &= ok(len(p.enviados) == 6 and tipos == {"sysex"}, "seis mensajes SysEx, en orden")
    todo &= ok(all(b < 128 for d in datos for b in d), "sin F0/F7 adentro (mido los pone) y datos de 7 bits")
    todo &= ok(datos[1] == bytes.fromhex("42 40 00 01 13 00 1F 12 00"), "modo nativo de Korg en el canal 1")
    todo &= ok(datos[3][:7] == bytes.fromhex("42 40 00 01 13 00 7F") and len(datos[3]) == 400, "la escena completa (400 bytes)")
    todo &= ok(datos[5] == bytes.fromhex("42 40 00 01 13 00 1F 11 00"), "y al final la orden de guardarla")
    p = Puerto()
    nano.led_externo(p, 5, pausa=0)
    todo &= ok(all(d[1] == 0x44 for _, d in p.enviados if d[0] == 0x42), "con canal global 5 el byte 4g es 44")
    todo &= ok(all(d[:2] == bytes.fromhex("7E 7F") for _, d in p.enviados if d[0] == 0x7E), "la consulta de identidad no cambia")
    print("\nTodo bien" if todo else "\nHAY FALLAS")
    return 0 if todo else 1


if __name__ == "__main__":
    raise SystemExit(main())
