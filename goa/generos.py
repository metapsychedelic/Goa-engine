"""Perfiles de género para cada motor: pads, llamada y respuesta y cada secuencia.

Cada motor tiene su propio selector de género, independiente de los demás: se
puede tener pads ambient, un diálogo chillgressive y un bajo psy chill. Elegir
un género escribe sus valores en la configuración de ese motor, así después se
ajusta todo a mano. Nunca toca destinos, canales, fuerza ni variantes.

La escala es común a todos (en Música), para que nada choque. El género de
Música es un atajo: pone la escala y el mismo género en todos los motores.
"""

import copy

from .generador import ESTILOS_POR_GENERO

GENEROS = {
    "goa": {
        "nombre": "Goa",
        "musica": {"escala": "frigio", "desplazamiento": 0.0, "tension": 0.4},
        "pads": {"progresion": "i_bII", "acorde": "menor_add9", "cambia_cada": 16, "apertura": "abierta",
                 "ataque": "ligado", "drone": False, "rasgueo": 1, "pulso": 0, "variacion": 0.15, "suspensiones": 0.3},
        "dialogo": {"rejilla": "corcheas", "espacio": 1, "evolucion": 0.5, "mutar_cada": 4},
        "llamada": {"golpes": 3, "gate": 0.5, "oscuridad": 0.7},
        "respuesta": {"golpes": 2, "gate": 0.6, "oscuridad": 0.7},
    },
    "psy_chill": {
        "nombre": "Psy chill",
        "musica": {"escala": "dorico", "desplazamiento": 0.2, "tension": 0.3},
        "pads": {"progresion": "i_IV_i_bVII", "acorde": "menor_add9", "cambia_cada": 4, "apertura": "abierta",
                 "ataque": "ligado", "drone": False, "rasgueo": 2, "pulso": 3, "variacion": 0.1, "suspensiones": 0.4},
        "dialogo": {"rejilla": "corcheas", "espacio": 1, "evolucion": 0.4, "mutar_cada": 4},
        "llamada": {"golpes": 3, "gate": 0.45, "oscuridad": 0.45},
        "respuesta": {"golpes": 3, "gate": 0.5, "oscuridad": 0.45},
    },
    "chillgressive": {
        "nombre": "Chillgressive",
        "musica": {"escala": "menor", "desplazamiento": 0.1, "tension": 0.5},
        "pads": {"progresion": "i_bVI_bVII_v", "acorde": "menor_add9", "cambia_cada": 8, "apertura": "abierta",
                 "ataque": "ligado", "drone": False, "rasgueo": 1, "pulso": 0, "variacion": 0.1, "suspensiones": 0.2},
        "dialogo": {"rejilla": "semicorcheas", "espacio": 2, "evolucion": 0.4, "mutar_cada": 8},
        "llamada": {"golpes": 5, "gate": 0.4, "oscuridad": 0.7},
        "respuesta": {"golpes": 4, "gate": 0.4, "oscuridad": 0.7},
    },
    "chillout": {
        "nombre": "Chillout",
        "musica": {"escala": "menor", "desplazamiento": 0.5, "tension": 0.2},
        "pads": {"progresion": "i_bVI_iv_v", "acorde": "novena", "cambia_cada": 4, "apertura": "cerrada",
                 "ataque": "ligado", "drone": False, "rasgueo": 3, "pulso": 0, "variacion": 0.1, "suspensiones": 0.5},
        "dialogo": {"rejilla": "corcheas", "espacio": 2, "evolucion": 0.3, "mutar_cada": 4},
        "llamada": {"golpes": 3, "gate": 0.7, "oscuridad": 0.45},
        "respuesta": {"golpes": 2, "gate": 0.8, "oscuridad": 0.45},
    },
    "ambient": {
        "nombre": "Ambient",
        "musica": {"escala": "lidio", "desplazamiento": 0.6, "tension": 0.1},
        "pads": {"progresion": "pedal_I_II", "acorde": "novena", "cambia_cada": 16, "apertura": "amplia",
                 "ataque": "ligado", "drone": True, "rasgueo": 24, "pulso": 0, "variacion": 0.0, "suspensiones": 0.6},
        "dialogo": {"rejilla": "corcheas", "espacio": 3, "evolucion": 0.3, "mutar_cada": 8},
        "llamada": {"golpes": 2, "gate": 1.0, "oscuridad": 0.3},
        "respuesta": {"golpes": 1, "gate": 1.0, "oscuridad": 0.3},
    },
}

# Carácter de una secuencia por género (el estilo es el primero de su lista).
SECUENCIAS = {
    "goa": {"posicion": "offbeat", "largo": 16, "gate": 0.55, "pedal": 0.5, "swing": 0.0, "largas": 0.0},
    "psy_chill": {"posicion": "offbeat", "largo": 16, "gate": 0.5, "pedal": 0.6, "swing": 0.05, "largas": 0.0},
    "chillgressive": {"posicion": "offbeat", "largo": 16, "gate": 0.45, "pedal": 0.55, "swing": 0.0, "largas": 0.0},
    "chillout": {"posicion": "todos", "largo": 16, "gate": 0.9, "pedal": 0.5, "swing": 0.1, "largas": 0.6},
    "ambient": {"posicion": "todos", "largo": 13, "gate": 1.0, "pedal": 0.4, "swing": 0.0, "largas": 1.0},
}
for _g, _s in SECUENCIAS.items():
    _s["estilo"] = ESTILOS_POR_GENERO[_g][0]

ORDEN = tuple(GENEROS)
PARTES = ("pads", "dialogo", "secuencia")


def aplicar(cfg, genero, parte=None, indice=None):
    """Copia de `cfg` con el perfil del género aplicado.

    parte = None: atajo de Música (escala, desplazamiento y todos los motores).
    parte = "pads", "dialogo" o "secuencia" (con su índice): solo ese motor."""
    if genero not in GENEROS:
        raise ValueError(f"Género desconocido: {genero!r}. Opciones: {', '.join(ORDEN)}")
    if parte is not None and parte not in PARTES:
        raise ValueError(f"Motor desconocido: {parte!r}. Opciones: {', '.join(PARTES)}")
    perfil = GENEROS[genero]
    nueva = copy.deepcopy(cfg)
    if parte in (None, "pads"):
        nueva["pads"].update(perfil["pads"], genero=genero)
    if parte in (None, "dialogo"):
        nueva["dialogo"].update(perfil["dialogo"], genero=genero)
        for voz in ("llamada", "respuesta"):
            nueva[voz].update(perfil[voz])
    if parte == "secuencia":
        secuencias = nueva.get("secuencia") or []
        if not isinstance(indice, int) or not 0 <= indice < len(secuencias):
            raise ValueError("Secuencia desconocida")
        secuencias[indice].update(SECUENCIAS[genero], genero=genero)
    if parte is None:
        nueva["musica"].update(perfil["musica"], genero=genero)
        for s in nueva.get("secuencia") or []:
            s.update(SECUENCIAS[genero], genero=genero)
    return nueva
