"""Los 64 samples del banco de baterías «FROM GOA TO PSYT» de la Circuit Tracks, por nombre.

Reconstruido de la medición del audio de cada sample (energía por bandas, fundamental y
caída) que se hizo para las plantillas (herramientas/circuit_cancion.py). Los marcados
«sin medir» no se usaron entonces: se pueden completar sacando los nombres de la Circuit.
El número es el valor del CC de «patch select» de cada Drum (8, 18, 44, 50), probado en
la Circuit del usuario: manda el número de sample directo.
"""

MUESTRAS = {
    0: "Bombo con sub largo 1", 1: "Bombo corto 1", 2: "Bombo con sub largo 2", 3: "Bombo corto 2",
    4: "Bombo corto 3", 5: "Bombo corto 4", 6: "Bombo corto 5", 7: "Bombo corto 6",
    8: "Bombo con sub largo 3", 9: "Bombo con sub largo 4", 10: "Bombo con sub largo 5", 11: "Bombo con sub largo 6",
    12: "Bombo con sub largo 7", 13: "Bombo suave (latido)", 14: "Bombo con sub largo 8", 15: "Bombo con sub largo 9",
    16: "Clap 1", 17: "Clap 2", 18: "Clap 3", 19: "Clap 4",
    20: "Sample 20 (sin medir)", 21: "Snare 1", 22: "Snare roll", 23: "Snare 2",
    24: "Blip con sub", 25: "Snare con cuerpo", 26: "Snare con sub", 27: "Tom-snare",
    28: "Sample 28 (sin medir)", 29: "Sample 29 (sin medir)", 30: "Sample 30 (sin medir)", 31: "Grave 1",
    32: "Hat cerrado 1", 33: "Hat cerrado 2", 34: "Hat cerrado 3", 35: "Hat abierto",
    36: "Hat medio", 37: "Shaker 1", 38: "Hat corto", 39: "Hat abierto largo (ride)",
    40: "Crash", 41: "Swell de platillo", 42: "Hat fino", 43: "Shaker 2",
    44: "Conga", 45: "Percusión / blip", 46: "Bombo con sub largo 10", 47: "Grave 2",
    48: "Boom con sub 1", 49: "Boom con sub 2 (4 s)", 50: "Boom con sub 3", 51: "Boom medio",
    52: "Sample 52 (sin medir)", 53: "Tom agudo (377 Hz)", 54: "Tom medio (280 Hz)", 55: "Tom grave (226 Hz)",
    56: "Blip con sub 1", 57: "Blip con sub 2", 58: "Blip con sub 3", 59: "Blip con sub 4",
    60: "Atmósfera (drone 3 s)", 61: "Reversa", 62: "Zap", 63: "Riser",
}

# Los que no conviene usar en patrones (sub largo: chocan con el bajo del motor).
CON_SUB = {0, 2, 8, 9, 10, 11, 12, 14, 15, 24, 26, 31, 46, 47, 48, 49, 50, 56, 57, 58, 59}
