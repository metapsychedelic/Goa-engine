"""Perfiles de género: un solo selector cambia escala, pads y llamada y respuesta.

Elegir un género escribe sus valores en la configuración, así después se puede
ajustar cualquier cosa a mano. Nunca toca destinos, canales, fuerza ni variantes,
ni las secuencias (el bajo queda como lo armaste).

Si los pads están desacoplados (`pads.genero_propio`), el género general no los
cambia y tienen su propio selector, que solo cambia los pads (siguen usando la
escala general, para no chocar con lo demás).
"""

import copy

GENEROS = {
    "goa": {
        "nombre": "Goa",
        "musica": {"escala": "frigio", "desplazamiento": 0.0},
        "pads": {"progresion": "i_bII", "acorde": "menor_add9", "cambia_cada": 16, "apertura": "abierta",
                 "ataque": "ligado", "drone": False, "rasgueo": 1, "pulso": 0, "variacion": 0.15},
        "dialogo": {"rejilla": "corcheas", "espacio": 1, "evolucion": 0.5, "mutar_cada": 4},
        "llamada": {"golpes": 3, "gate": 0.5, "oscuridad": 0.7},
        "respuesta": {"golpes": 2, "gate": 0.6, "oscuridad": 0.7},
    },
    "psy_chill": {
        "nombre": "Psy chill",
        "musica": {"escala": "dorico", "desplazamiento": 0.2},
        "pads": {"progresion": "i_IV_i_bVII", "acorde": "menor_add9", "cambia_cada": 4, "apertura": "abierta",
                 "ataque": "ligado", "drone": False, "rasgueo": 2, "pulso": 3, "variacion": 0.1},
        "dialogo": {"rejilla": "corcheas", "espacio": 1, "evolucion": 0.4, "mutar_cada": 4},
        "llamada": {"golpes": 3, "gate": 0.45, "oscuridad": 0.45},
        "respuesta": {"golpes": 3, "gate": 0.5, "oscuridad": 0.45},
    },
    "chillgressive": {
        "nombre": "Chillgressive",
        "musica": {"escala": "menor", "desplazamiento": 0.1},
        "pads": {"progresion": "i_bVI_bVII_v", "acorde": "menor_add9", "cambia_cada": 8, "apertura": "abierta",
                 "ataque": "ligado", "drone": False, "rasgueo": 1, "pulso": 0, "variacion": 0.1},
        "dialogo": {"rejilla": "semicorcheas", "espacio": 2, "evolucion": 0.4, "mutar_cada": 8},
        "llamada": {"golpes": 5, "gate": 0.4, "oscuridad": 0.7},
        "respuesta": {"golpes": 4, "gate": 0.4, "oscuridad": 0.7},
    },
    "chillout": {
        "nombre": "Chillout",
        "musica": {"escala": "menor", "desplazamiento": 0.5},
        "pads": {"progresion": "i_bVI_iv_v", "acorde": "novena", "cambia_cada": 4, "apertura": "cerrada",
                 "ataque": "ligado", "drone": False, "rasgueo": 3, "pulso": 0, "variacion": 0.1},
        "dialogo": {"rejilla": "corcheas", "espacio": 2, "evolucion": 0.3, "mutar_cada": 4},
        "llamada": {"golpes": 3, "gate": 0.7, "oscuridad": 0.45},
        "respuesta": {"golpes": 2, "gate": 0.8, "oscuridad": 0.45},
    },
    "ambient": {
        "nombre": "Ambient",
        "musica": {"escala": "lidio", "desplazamiento": 0.6},
        "pads": {"progresion": "pedal_I_II", "acorde": "novena", "cambia_cada": 16, "apertura": "amplia",
                 "ataque": "ligado", "drone": True, "rasgueo": 24, "pulso": 0, "variacion": 0.0},
        "dialogo": {"rejilla": "corcheas", "espacio": 3, "evolucion": 0.3, "mutar_cada": 8},
        "llamada": {"golpes": 2, "gate": 1.0, "oscuridad": 0.3},
        "respuesta": {"golpes": 1, "gate": 1.0, "oscuridad": 0.3},
    },
}

ORDEN = tuple(GENEROS)


def aplicar(cfg, genero, solo_pads=False):
    """Copia de `cfg` con el perfil del género aplicado."""
    if genero not in GENEROS:
        raise ValueError(f"Género desconocido: {genero!r}. Opciones: {', '.join(ORDEN)}")
    perfil = GENEROS[genero]
    nueva = copy.deepcopy(cfg)
    if solo_pads:
        nueva["pads"].update(perfil["pads"], genero=genero)
        return nueva
    nueva["musica"].update(perfil["musica"], genero=genero)
    for seccion in ("dialogo", "llamada", "respuesta"):
        nueva[seccion].update(perfil[seccion])
    if not nueva["pads"].get("genero_propio"):
        nueva["pads"].update(perfil["pads"], genero=genero)
    return nueva
