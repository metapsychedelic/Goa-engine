"""Korg nanoKONTROL2: LED Mode = External sin el Kontrol Editor de Korg.

El Kontrol Editor ya no corre en todos los sistemas. Esto le manda al nano los mismos
mensajes SysEx que manda el editor al escribir la escena de fábrica con LED Mode =
External (grabados del editor por el proyecto Overtone, licencia MIT): consulta de
identidad, modo nativo, la escena completa (los CC de fábrica, los que usa Yantra, en
modo CC) y la orden de guardarla en el nano. Queda guardado: sobrevive al apagarlo.

  goa-ports --nano-led             (o el botón en Ajustes › nanoKONTROL2)

Ojo: reescribe la escena del nano con la de fábrica. Si le habías cambiado números de CC
en el editor, vuelven a los de fábrica (Yantra usa justo esos).
"""

import time

IDENTIDAD = bytes.fromhex("F0 7E 7F 06 01 F7")
MODO = bytes.fromhex("F0 42 40 00 01 13 00 1F 12 00 F7")
GUARDAR = bytes.fromhex("F0 42 40 00 01 13 00 1F 11 00 F7")
# La escena de fábrica con LED Mode = External (Current Scene Data Dump).
ESCENA = bytes.fromhex(
    "F0 42 40 00 01 13 00 7F 7F 02 03 05 40 00 00 00"
    "01 10 01 00 00 00 00 7F 00 01 00 10 00 00 7F 00"
    "01 00 20 00 7F 00 00 01 00 30 00 7F 00 00 01 00"
    "40 00 7F 00 10 00 01 00 01 00 7F 00 01 00 00 11"
    "00 7F 00 01 00 00 21 00 7F 00 01 00 31 00 00 7F"
    "00 01 00 41 00 00 7F 00 10 01 00 02 00 00 7F 00"
    "01 00 12 00 7F 00 00 01 00 22 00 7F 00 00 01 00"
    "32 00 7F 00 01 00 00 42 00 7F 00 10 01 00 00 03"
    "00 7F 00 01 00 00 13 00 7F 00 01 00 23 00 00 7F"
    "00 01 00 33 00 00 7F 00 01 00 43 00 7F 00 00 10"
    "01 00 04 00 7F 00 00 01 00 14 00 7F 00 00 01 00"
    "24 00 7F 00 01 00 00 34 00 7F 00 01 00 00 44 00"
    "7F 00 10 01 00 00 05 00 7F 00 01 00 15 00 00 7F"
    "00 01 00 25 00 00 7F 00 01 00 35 00 7F 00 00 01"
    "00 45 00 7F 00 00 10 01 00 06 00 7F 00 00 01 00"
    "16 00 7F 00 01 00 00 26 00 7F 00 01 00 00 36 00"
    "7F 00 01 00 46 00 00 7F 00 10 01 00 07 00 00 7F"
    "00 01 00 17 00 00 7F 00 01 00 27 00 7F 00 00 01"
    "00 37 00 7F 00 00 01 00 47 00 7F 00 10 00 01 00"
    "3A 00 7F 00 01 00 00 3B 00 7F 00 01 00 00 2E 00"
    "7F 00 01 00 3C 00 00 7F 00 01 00 3D 00 00 7F 00"
    "01 00 3E 00 7F 00 00 01 00 2B 00 7F 00 00 01 00"
    "2C 00 7F 00 01 00 00 2A 00 7F 00 01 00 00 29 00"
    "7F 00 01 00 2D 00 00 7F 00 7F 7F 7F 7F 00 7F 00"
    "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00"
    "00 F7"
)


def mensajes(canal=1):
    """Los seis mensajes, en orden, para el nano en su canal MIDI global `canal` (1-16):
    el tercer byte de los de Korg (4g) lleva ese canal."""
    lista = [IDENTIDAD, MODO, IDENTIDAD, ESCENA, IDENTIDAD, GUARDAR]
    g = max(1, min(16, int(canal))) - 1
    return [m if m[1] != 0x42 else m[:2] + bytes([0x40 | g]) + m[3:] for m in lista]


def led_externo(puerto, canal=1, pausa=0.15):
    """Manda los mensajes a un puerto de salida abierto (mido). `pausa` entre uno y otro:
    el nano necesita un momento para guardar la escena."""
    import mido
    for m in mensajes(canal):
        puerto.send(mido.Message("sysex", data=m[1:-1]))
        time.sleep(pausa)
