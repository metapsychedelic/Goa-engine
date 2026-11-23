"""Leer, validar y guardar la configuración (config.toml)."""

import os
import tempfile
import tomllib

import json

from . import armonia, bajo, dialogo, forma, fx, generador, generos, pads, raga
from .escalas import ESCALAS, ESCALAS_COLOR, nombre_a_clase

MAX_SECUENCIAS = 8
MAX_CLIPS = 64

# clave: (tipo, valor por defecto, mínimo, máximo u opciones)
ESQUEMA_SECCIONES = {
    "app": {"puerto": (int, 8080, 1024, 65535), "proyecto": (str, "", None, None),
            # Con un proyecto abierto, cada cambio queda también en su archivo.
            "autoguardar": (bool, True, None, None)},
    "entrada": {
        "puerto": (str, "Circuit", None, None),
        "canal_disparo": (int, 4, 1, 16),
        "nota_maxima": (int, 4, 0, 64),
    },
    "thru": {
        "activo": (bool, False, None, None),
        "salida": (str, "USB MIDI", None, None),
        # Con la MC-101 (u otra máquina de la cadena) como reloj maestro: el reloj y el
        # Start/Stop no se reenvían, así no vuelven a la maestra.
        "reloj": (bool, True, None, None),
    },
    "musica": {
        "tonica": (str, "F", None, None),
        "escala": (str, "frigio", None, tuple(ESCALAS)),
        "cambio_de_nota": (str, "paso", None, ("paso", "compas")),
        "adaptacion": (str, "escala", None, ("escala", "transponer")),
        "seguir_pads": (bool, False, None, None),
        "genero": (str, "goa", None, generos.ORDEN),
        "desplazamiento": (float, 0.0, 0.0, 1.0),
        "armonia": (str, "guiada", None, armonia.MODOS),
        "tension": (float, 0.3, 0.0, 1.0),
        "anticipar": (bool, True, None, None),
    },
    "pads": {
        "activo": (bool, False, None, None),
        "salida": (str, "CH345", None, None),
        "canal": (int, 3, 1, 16),
        "programa": (int, 0, 0, 128),           # Program Change del sinte (1-128); 0 = no lo cambia
        "base": (str, "nota", None, pads.BASES),
        "progresion": (str, "i_bII", None, tuple(pads.PROGRESIONES)),
        "azar": (bool, False, None, None),      # parte de la progresión elegida y la va variando
        "azar_cada": (int, 2, 1, 8),             # vueltas de la progresión entre una variación y otra
        "acorde": (str, "menor_add9", None, tuple(pads.ACORDES)),
        "cambia_cada": (int, 16, 1, 64),
        "voces": (int, 4, 2, 6),
        "octava": (int, 0, -2, 2),
        "apertura": (str, "abierta", None, pads.APERTURAS),
        "variacion": (float, 0.15, 0.0, 1.0),
        "ataque": (str, "ligado", None, pads.ATAQUES),
        "drone": (bool, False, None, None),
        "textura": (str, "acordes", None, pads.TEXTURAS),
        "rasgueo": (int, 1, 0, 24),
        "pulso": (int, 0, 0, 8),
        "ritmo": (str, "euclides", None, ("euclides", "stabs")),   # stabs: ritmos de stabs de acordes psy
        "golpe": (float, 0.35, 0.1, 1.0),   # largo de cada golpe del pulso (1 = hasta el siguiente)
        "suenan": (bool, True, None, None),
        "suspensiones": (float, 0.3, 0.0, 1.0),
        "genero": (str, "goa", None, generos.ORDEN),
        "velocidad": (int, 80, 1, 127),
        "seed": (str, "P-1C88", None, None),
        "disparo": (int, 0, 0, 16),
    },
    "dialogo": {
        "activo": (bool, False, None, None),
        "modo": (str, "motor", None, dialogo.MODOS),
        "forma": (str, "entrelazado", None, dialogo.FORMAS),
        "rejilla": (str, "corcheas", None, tuple(dialogo.REJILLAS)),
        "espacio": (int, 1, 0, 3),
        "densidad": (float, 1.0, 0.0, 1.0),      # cuántas notas de las frases suenan (el fader del nano)
        "compases_turno": (int, 2, 1, 8),
        "disparo": (int, 0, 0, 16),
        "escucha": (int, 4, 1, 16),
        "seguir_pads": (bool, True, None, None),
        "evolucion": (float, 0.5, 0.0, 1.0),
        "mutar_cada": (int, 4, 1, 64),
        "seed": (str, "CR-0001", None, None),
        "responde": (str, "contraste", None, dialogo.RESPONDE),
        "genero": (str, "goa", None, generos.ORDEN),
        "armonia": (str, "general", None, armonia.MODOS_MOTOR),
    },
}


def _esquema_voz(salida, canal, golpes, gate, velocidad):
    return {
        "salida": (str, salida, None, None),
        "canal": (int, canal, 1, 16),
        "programa": (int, 0, 0, 128),
        "golpes": (int, golpes, 1, 16),
        "octava": (int, 1, -3, 3),
        "oscuridad": (float, 0.7, 0.0, 1.0),
        "gate": (float, gate, 0.05, 1.0),
        "velocidad": (int, velocidad, 1, 127),
        "vel_random": (float, 0.15, 0.0, 1.0),
        "desplazamiento": (float, -1.0, -1.0, 1.0),  # menos de 0 = usa el general
        "filtro": (bool, False, None, None),  # el molde filtra sus notas (apagado: suena todo)
        "molde": (str, "", None, None),     # filtro de 16 pasos: x = pasa, ? = a veces, - = bloquea
        "molde_prob": (float, 0.5, 0.0, 1.0),  # probabilidad de los «a veces»
        "recorrido": (str, "adelante", None, generador.RECORRIDOS),  # orden de sus notas
        "molde_muta": (float, 0.0, 0.0, 1.0),   # el molde muta solo (cada «mutar cada» compases)
        "molde_estilo": (str, "goa", None, generador.ESTILOS_MOLDE),
        "variante": (int, 0, 0, 999),       # «Otra» / «Volver»: otra frase sin cambiar la seed
        "fija": (bool, False, None, None),  # «Fijar»: la mutación no la cambia
    }


ESQUEMA_SECCIONES["llamada"] = _esquema_voz("FM-1", 4, 3, 0.5, 100)
ESQUEMA_SECCIONES["respuesta"] = _esquema_voz("MicroFreak", 3, 2, 0.6, 92)
ESQUEMA_SECCIONES["bajo"] = {
    "activo": (bool, False, None, None),
    "salida": (str, "CH345", None, None),
    "canal": (int, 4, 1, 16),
    "programa": (int, 0, 0, 128),
    "disparo": (int, 0, 0, 16),            # canal de su nota larga; 0 = el general
    "genero": (str, "goa", None, generos.ORDEN),
    "estilo": (str, "rolling", None, bajo.ESTILOS),
    "armonia": (str, "general", None, armonia.MODOS_MOTOR),
    "movimiento": (float, 0.3, 0.0, 1.0),
    "sube": (float, 0.0, 0.0, 1.0),        # notas que suben desde la raíz (bajo full-on)
    "filtro": (bool, False, None, None),   # filtro automático por CC (se abre de a poco)
    "filtro_cc": (int, 74, 0, 127),        # MC-101: 74 = corte, 71 = resonancia
    "filtro_min": (int, 25, 0, 127),
    "filtro_max": (int, 100, 0, 127),
    "filtro_ciclo": (int, 32, 4, 128),     # compases en abrirse
    "filtro_forma": (str, "sube", None, ("sube", "ola")),
    "filtro_nota": (float, 0.5, 0.0, 1.0), # golpe de filtro en el ataque de cada nota (0 = no)
    "porta": (bool, False, None, None),    # prende el portamento del sinte (CC 65) para los slides
    "porta_tiempo": (int, 30, 0, 127),     # tiempo del portamento (CC 5)
    "evolucion": (float, 0.0, 0.0, 1.0),
    "mutar_cada": (int, 4, 1, 64),
    "transponer": (int, 0, -7, 7),       # grados de escala
    "densidad": (float, 1.0, 0.0, 1.0),
    "swing": (float, 0.0, 0.0, 0.5),
    "slide": (float, 0.0, 0.0, 1.0),
    "acentos": (float, 0.2, 0.0, 1.0),
    "fantasmas": (float, 0.0, 0.0, 1.0),
    "remates": (bool, True, None, None),
    "remate_var": (float, 0.3, 0.0, 1.0),     # cuánto cambia el remate en cada frase
    "remate_rango": (str, "octava", None, ("quinta", "octava")),
    "remate_largas": (float, 0.0, 0.0, 1.0),  # frases cuyo remate alarga una nota
    "remate_largo": (float, 0.75, 0.3, 1.0),  # cuánto del hueco hasta la siguiente ocupa
    "remate_marca": (float, 1.0, 0.0, 1.0),   # 0 = como el resto, 1 = acentuado y sin slide
    "fusas": (float, 0.0, 0.0, 1.0),          # remate en fusas: proporción de frases que cierran con un redoble
    "remates_pack": (float, 0.0, 0.0, 1.0),   # frases cuyo remate sale de los bajos de los packs (rolling, full-on, chillgressive)
    "zenon": (float, 0.0, 0.0, 1.0),          # frases con la nota larga zenon (justo después del bombo)
    "caida": (int, 0, 0, 24),                 # semitonos que cae la nota larga con el pitch bend (0 = no cae)
    "bend_rango": (int, 12, 1, 24),           # rango de pitch bend del sinte del bajo
    "arco": (float, 0.0, 0.0, 1.0),           # notas largas que suben y vuelven con el pitch bend
    "arco_alto": (int, 12, 1, 24),            # cuánto sube el arco (semitonos)
    "ciclo": (int, 0, 0, 7),                  # ciclo de alturas: 0 = sin ciclo, 5 o 7 notas (otro valor = sin ciclo)
    "frase": (int, 4, 1, 8),
    "octava": (int, 0, -2, 2),
    "gate": (float, 0.6, 0.05, 1.0),
    "velocidad": (int, 100, 1, 127),
    "vel_random": (float, 0.1, 0.0, 1.0),
    "seed": (str, "B-0001", None, None),
}

ESQUEMA_SECCIONES["forma"] = {
    "energia": (float, 0.5, 0.0, 1.0),       # 0,5 = cada motor tal como lo dejaste
    "transicion": (int, 8, 1, 16),           # compases para pasar de una escena a otra
    "escena": (int, -1, -1, forma.MAX_ESCENAS - 1),  # la última escena lanzada (-1 = ninguna)
    "variacion": (float, 0.4, 0.0, 1.0),     # cuánto cambia el director en cada período
    "periodo": (int, 16, 8, 32),             # compases de cada período del director
    "un_cambio": (bool, False, None, None),  # el director cambia una sola cosa por período (zenonesque)
    "pads_por_energia": (bool, False, None, None),  # con mucha energía los pads solo guían; con poca suenan
    "espacio_bombo": (float, 0.0, 0.0, 1.0), # bajo y secuencias se cortan antes de cada bombo (0 = no)
    "piloto": (bool, False, None, None),     # piloto automático: intro, build, clímax, break, drop
    "duracion": (str, "normal", None, tuple(forma.DURACIONES)),
}

# FX: un sinte propio (por defecto un canal de la MC-101) con zaps, burbujas, ácido,
# glitch, el riser de las subidas y la caída del drop. Ver fx.py.
ESQUEMA_SECCIONES["fx"] = {
    "activo": (bool, False, None, None),
    "salida": (str, "MC-101", None, None),
    "canal": (int, 1, 1, 16),
    "programa": (int, 0, 0, 128),
    "disparo": (int, 0, 0, 16),              # canal de su nota larga; 0 = el general
    "genero": (str, "goa", None, generos.ORDEN),
    "locura": (float, 0.4, 0.0, 1.0),        # cuántos gestos (la energía la sube y la baja)
    **{g: (bool, True, None, None) for g in fx.GESTOS},  # qué gestos puede tocar
    "riser": (bool, True, None, None),       # en las subidas toca el riser
    "caida": (bool, True, None, None),       # en el drop, la caída
    "octava": (int, 1, -2, 3),
    "velocidad": (int, 100, 1, 127),
    "cc_corte": (int, 74, 0, 127),           # CC del filtro del sinte de FX
    "filtro_reposo": (int, 100, 0, 127),     # dónde queda el filtro cuando no hay gestos
    "seed": (str, "FX-0001", None, None),
    # Dónde caen los gestos y cuánto se repiten (ver fx._gesto).
    "donde": (str, "frase", None, fx.DONDE),
    "repetir": (int, 8, 1, 32),              # compases: qué gesto va en cada lugar se repite
    "caos": (float, 0.2, 0.0, 1.0),          # cuánto cambia en cada vuelta (gestos y filtro)
    # Fondo: notas largas con el filtro en ritmo (ver fx._fondo).
    "fondo": (bool, False, None, None),
    "fondo_notas": (str, "raiz", None, fx.FONDO_NOTAS),
    "fondo_largo": (int, 2, 1, 8),           # compases: cada cuánto se vuelven a atacar
    "fondo_octava": (int, 0, -2, 2),
    "fondo_fuerza": (int, 90, 1, 127),
    "filtro_modo": (str, "pluck", None, fx.FILTRO_MODOS),
    "filtro_division": (str, "16", None, tuple(fx.DIVISIONES)),
    "filtro_golpes": (int, 5, 1, 16),        # pluck: golpes euclidianos en 16 semicorcheas
    "filtro_rotar": (int, 0, 0, 15),
    "filtro_caida": (int, 9, 1, 48),         # pluck: pulsos que tarda en cerrarse (6 = una semicorchea)
    "filtro_min": (int, 25, 0, 127),
    "filtro_max": (int, 115, 0, 127),
    "movimiento": (float, 1.0, 0.0, 1.0),    # cuánto del rango usa (macro para el nanoKONTROL2)
    "resonancia": (bool, False, None, None),
    "cc_resonancia": (int, 71, 0, 127),
    "reso_min": (int, 20, 0, 127),
    "reso_max": (int, 90, 0, 127),
    "reso_ciclo": (int, 6, 1, 64),           # semicorcheas de una vuelta (6 = desfasada contra el compás)
}

# Texturas: notas largas que respiran (un CC que sube y vuelve en cada una) mezcladas
# con notas cortas, en un canal propio de la MC-101. Ver texturas.py.
ESQUEMA_SECCIONES["texturas"] = {
    "activo": (bool, False, None, None),
    "salida": (str, "MC-101", None, None),
    "canal": (int, 2, 1, 16),
    "programa": (int, 0, 0, 128),
    "disparo": (int, 0, 0, 16),              # canal de su nota larga; 0 = el general
    "densidad": (float, 0.5, 0.0, 1.0),      # cuántas notas (la energía la sube y la baja)
    "largas": (float, 0.6, 0.0, 1.0),        # 0 = solo cortas, 1 = solo largas
    "largo": (int, 2, 1, 4),                 # largo típico de las largas, en compases (1, 2 o 4)
    "octava": (int, 0, -2, 3),
    "registro": (int, 2, 1, 3),              # en cuántas octavas se reparten las notas
    "velocidad": (int, 90, 1, 127),
    "cc": (int, 74, 0, 127),                 # qué respira: 74 corte, 71 resonancia (MC-101)
    "reposo": (int, 40, 0, 127),             # dónde queda ese CC entre notas largas
    "profundidad": (float, 0.6, 0.0, 1.0),   # cuánto se abre en cada nota larga
    "seed": (str, "TX-0001", None, None),
}

# Obertura: preludio orquestal de batalla por capas que desemboca en el drop (ver obertura.py
# y docs/molde-obertura.md). Cada capa a un canal de la escena «orquesta» de la MC-101.
ESQUEMA_SECCIONES["obertura"] = {
    "activo": (bool, False, None, None),
    "salida": (str, "MC-101", None, None),
    "modo": (str, "epico", None, ("epico", "chill", "cine")),
    "caracter": (str, "batalla", None, ("batalla", "frigia", "tragica", "etereo", "lamento", "ritual",
                                        "neon", "titulos", "cosmos")),
    "forma": (str, "crece", None, ("crece", "golpe", "ola", "respiro")),
    "tema_track": (bool, False, None, None),  # llamada, tema y melodía siguen el motivo de la 1.ª secuencia
    "bend_rango": (int, 2, 0, 24),            # cine: semitonos del pitch bend del lead (0 = sin bends)
    "repetir": (bool, False, None, None),     # en loop (sin final): vuelve a la etapa 2 cada vez distinta
    "frases": (int, 4, 1, 8),                 # frases de 8 compases (4 = 32 compases)
    "velocidad": (int, 115, 1, 127),          # la fuerza del final (crece hasta ahí)
    "expresion": (bool, True, None, None),    # crescendo también por CC 11
    "canal_cuerdas": (int, 1, 0, 16),         # 0 = esa capa no suena
    "canal_cuernos": (int, 2, 0, 16),
    "canal_coro": (int, 3, 0, 16),
    "canal_percusion": (int, 4, 0, 16),
    "nota_taiko": (int, 36, 0, 127),
    "nota_tambor": (int, 38, 0, 127),
    "nota_golpe": (int, 49, 0, 127),
    "escena": (int, 0, 0, 128),               # escena «orquesta» de la MC-101 (1-128; 0 = no cambia)
    "escena_vuelta": (int, 0, 0, 128),        # escena a la que vuelve antes del drop (0 = no cambia)
    "canal_control": (int, 16, 1, 16),        # canal de control de la MC-101 (el de las escenas)
    "preparar": (bool, True, None, None),     # con escena: un compás antes para que la MC cambie (cambia en el uno)
    "seed": (str, "OB-0001", None, None),
}

# Looper: loops de samples en una pista Looper de la MC-101. Cada escena elige qué slot
# (1-16) suena; el motor manda el Program Change del slot (PC 0-15 = clip 1-16 en el
# canal de la pista) un compás antes de que llegue la escena, y la MC-101 lo cambia en
# su cuantización (Master Step Length; con 16 pasos cae justo en el uno).
ESQUEMA_SECCIONES["looper"] = {
    "activo": (bool, False, None, None),
    "salida": (str, "MC-101", None, None),
    "canal": (int, 4, 1, 16),
    "clip": (int, 0, 0, 16),                 # 0 = ningún loop (callado)
    "parar": (int, 0, 0, 16),                # slot vacío que se lanza para callar (0 = no calla)
    "cada": (int, 1, 1, 16),                 # compases: el loop entra en múltiplos de esto desde el Start
    "nivel": (int, 100, 1, 127),             # volumen de la pista al volver a sonar (callado sin slot vacío = CC 7 a 0)
}

# Scatter de la MC-101 en las subidas: cada pad de Scatter (1-16) es una nota 60-75 en el
# canal de control de la MC-101 (RX Scatter en ON). Suena mientras la nota está apretada.
# Es de la máquina, no de la escena: cada parte elige si lo usa y qué pads.
# Armonía del tema: la base que siguen las escenas (partes) que no tienen armonía propia.
# Cambiarla cambia todas esas partes; una parte con armonía propia (otra tonalidad) no se mueve.
ESQUEMA_SECCIONES["armonia_tema"] = dict(ESQUEMA_SECCIONES["musica"])

ESQUEMA_SECCIONES["scatter"] = {
    "salida": (str, "MC-101", None, None),
    "canal": (int, 16, 1, 16),               # canal de control de la MC-101
    "fuerza": (int, 100, 1, 127),
}

# Controlador (Korg nanoKONTROL2 en modo CC): cada canal maneja un motor y el transporte
# las escenas. Ver goa/control.py.
ESQUEMA_SECCIONES["control"] = {
    "activo": (bool, False, None, None),
    "puerto": (str, "nanoKONTROL2", None, None),
    "canal": (int, 1, 1, 16),                # canal MIDI global del nanoKONTROL2
    "luces": (bool, True, None, None),       # prende sus botones (LED Mode External)
    "subida": (int, 8, 1, 32),               # compases de la subida del botón REC
}

# Tocado: el secuenciador que se toca con el teclado de la MicroFreak (goa/tocado.py).
ESQUEMA_SECCIONES["tocado"] = {
    "activo": (bool, False, None, None),
    "salida": (str, "FM-1", None, None),
    "canal": (int, 4, 1, 16),
    "programa": (int, 0, 0, 128),
    "modo": (str, "una_tecla", None, ("una_tecla", "contorno")),
    "estilo": (str, "rolling", None, ("rolling", "galope", "arpegio3", "acido", "psy_chill", "euclidiano",
                                      "largas", "ambient", "clasico", "psytrance")),   # los de las secuencias
    "octava": (int, 0, -2, 2),
    "pasos": (int, 16, 1, 128),              # largo de la grabación que queda en loop (semicorcheas, hasta 8 compases)
    "cuantizar": (str, "estricta", None, ("estricta", "suave", "swing", "libre")),
    "grilla": (int, 16, 8, 16),              # cuantizar a semicorcheas (16) o a corcheas (8)
    "seed": (str, "TC-0001", None, None),
    "loop": (str, "", None, 60000),          # lo grabado (JSON, lo escribe el motor): va en escenas y proyecto
}

# Teclado de la MicroFreak por USB, para tocar en vivo a través del motor (goa/teclado.py).
# Con Local Off en la MicroFreak sus perillas no le cambian el sonido: el motor recibe
# sus CC (Knob send CCs = On) y se los devuelve por USB en el canal en que suena.
ESQUEMA_SECCIONES["teclado"] = {
    "activo": (bool, False, None, None),
    "puerto": (str, "MicroFreak", None, None),
    "canal": (int, 10, 1, 16),               # Output chan de la MicroFreak
    "perillas": (bool, True, None, None),    # devolverle sus perillas (con Local Off)
    "canal_sinte": (int, 3, 1, 16),          # canal en que suena la MicroFreak (el del pad)
}

# Modo canción: la canción es una lista de partes (intro, build, groove...), cada una
# con sus compases, la escena que suena y su curva de energía. Ver forma.py.
ESQUEMA_SECCIONES["cancion"] = {
    "activa": (bool, False, None, None),     # False = modo libre (como siempre)
    "nombre": (str, "Mi canción", None, None),
    "al_final": (str, "repetir", None, ("repetir", "quedarse")),  # como la cadena de escenas de la Circuit
    # Loop de partes (como una cadena de escenas en la Circuit): al dar Play parte en
    # «loop_desde» y repite hasta «loop_hasta» (índices de partes; -1 = sin loop).
    "loop_desde": (int, -1, -1, 31),
    "loop_hasta": (int, -1, -1, 31),
}
ESQUEMA_PARTE = {
    "nombre": (str, "Parte", None, None),
    "compases": (int, 16, 1, 256),
    "escena": (int, -1, -1, forma.MAX_ESCENAS - 1),  # -1 = sigue lo que suena
    "energia": (float, 0.5, 0.0, 1.0),               # energía al empezar la parte
    "energia_fin": (float, 0.5, 0.0, 1.0),           # y al terminarla
    "entrada": (str, "suave", None, ("suave", "golpe")),
    "pads_suben": (bool, False, None, None),         # los pads acompañan la subida (opcional)
    "roll": (bool, False, None, None),               # las secuencias hacen un roll al final
    "corte_bajo": (bool, False, None, None),         # el bajo se calla al final
    "tension": (bool, False, None, None),            # el último compás va a un acorde de tensión
    "hueco": (bool, False, None, None),              # el último tiempo, el motor en silencio
    "riser": (bool, False, None, None),              # subida de FX en la parte (riser, filtros, stutter) y drop al terminar
    # Scatter de la MC-101 al final de la parte: suave desde `scatter_compases` antes del
    # final, intenso en los 2 últimos compases y extremo en el último tiempo (pad 0 = esa
    # etapa no suena). Se suelta justo en el uno de la parte siguiente.
    "scatter": (bool, False, None, None),
    "scatter_compases": (int, 4, 1, 32),
    "scatter_suave": (int, 1, 0, 16),
    "scatter_intenso": (int, 8, 0, 16),
    "scatter_extremo": (int, 16, 0, 16),
}
MAX_PARTES = 32

ESQUEMA_ESCENA = {
    "nombre": (str, "Escena", None, None),
    "energia": (float, 0.5, 0.0, 1.0),
    # False: su armonía es la del tema (armonia_tema). True: tiene la suya (la de sus datos).
    # Sin la clave (escenas de antes) es True: suena igual que siempre.
    "armonia_propia": (bool, True, None, None),
}
MAX_DATOS_ESCENA = 60000

# Un clip de diálogo guarda la conversación completa, con quién llama y los destinos,
# para que al lanzarlo entre tal como se armó. Las voces van con prefijo para que
# quede plano en el archivo: llamada_salida, respuesta_escala...
VOCES = ("llamada", "respuesta")
ESQUEMA_CLIP_DIALOGO = dict(
    {"nombre": (str, "Diálogo", None, None)},
    **{k: v for k, v in ESQUEMA_SECCIONES["dialogo"].items() if k != "activo"},
    **{f"{voz}_{k}": v for voz in VOCES for k, v in ESQUEMA_SECCIONES[voz].items()},
    con_variante=(bool, True, None, None),
)

ESQUEMA_SECUENCIA = {
    "nombre": (str, "A", None, None),
    "disparo": (int, 0, 0, 16),
    "activa": (bool, True, None, None),
    "salida": (str, "FM-1", None, None),
    "canal": (int, 1, 1, 16),
    "programa": (int, 0, 0, 128),
    "genero": (str, "goa", None, generos.ORDEN),
    "armonia": (str, "general", None, armonia.MODOS_MOTOR),
    "estilo": (str, "rolling", None, generador.ESTILOS),
    "posicion": (str, "offbeat", None, generador.POSICIONES),
    "relacion": (str, "unisono", None, tuple(generador.RELACIONES)),
    "octava": (int, 0, -3, 3),
    "techo": (int, 127, 36, 127),           # nota más alta: lo que pasa baja de octava (127 = sin techo)
    "doble": (str, "", None, ("", "tercera", "cuarta", "quinta", "sexta", "octava")),  # voz paralela
    "deslices": (float, 0.0, 0.0, 1.0),       # notas de gracia, ligados y notas que respiran (0 = apagado)
    "corrimiento": (int, 0, 0, 15),           # el patrón entra N semicorcheas tarde
    "complementar": (float, 0.0, 0.0, 1.0),   # calla donde ataca la primera secuencia (100 % = hocket)
    "separar": (bool, False, None, None),     # evita segundas, séptimas y tritonos con la primera secuencia
    "raga": (str, "", None, raga.NOMBRES),     # "" = sin raga · bhairav, bhairavi, todi, marwa, hijaz
    "ornamentos": (float, 0.5, 0.0, 1.0),     # cuánto adorna la raga: kan, meend, gamak, andolan
    "bend_rango": (int, 2, 0, 24),            # semitonos del pitch bend del sinte (0 = no usa pitch bend)
    "largo": (int, 16, 2, 64),
    "gate": (float, 0.55, 0.05, 1.0),
    "pedal": (float, 0.5, 0.0, 1.0),
    # Goa clásico (solo ese estilo): figura, frase de 2 o 4 compases, cuánto cambia la
    # respuesta, largo del ciclo (0 = lo elige la seed) y octavas que abarca el ciclo.
    "figura": (str, "auto", None, generador.FIGURAS_CON_AUTO),
    "frase": (int, 2, 2, 4),
    "remate": (float, 0.5, 0.0, 1.0),
    "zenon": (float, 0.0, 0.0, 1.0),          # frases con la nota larga zenon (justo después del bombo)
    "caida": (int, 0, 0, 24),                 # semitonos que cae la nota larga con el pitch bend (0 = no cae)
    "bend_rango": (int, 12, 1, 24),           # rango de pitch bend del sinte del bajo
    "arco": (float, 0.0, 0.0, 1.0),           # notas largas que suben y vuelven con el pitch bend
    "arco_alto": (int, 12, 1, 24),            # cuánto sube el arco (semitonos)
    "ciclo": (int, 0, 0, 7),
    "registro": (int, 2, 1, 3),
    "variar": (float, 0.0, 0.0, 1.0),       # respuestas distintas en cada vuelta de la frase (0 = siempre la misma)
    "huecos": (float, 0.5, 0.0, 1.0),       # psytrance: de la máscara de riff más llena a la más vacía
    "seed": (str, "goa", None, None),
    "mutacion": (float, 0.0, 0.0, 1.0),
    "mutar_cada": (int, 8, 1, 64),
    "respuesta_par": (float, 0.0, 0.0, 1.0),  # en el 2.º compás de cada par, el último tiempo cambia de notas
    "mutacion_ritmo": (float, 0.0, 0.0, 1.0),
    "bloqueada": (bool, False, None, None),
    "velocidad": (int, 96, 1, 127),
    "acento": (int, 124, 1, 127),
    "densidad": (float, 1.0, 0.0, 1.0),
    "gate_random": (float, 0.0, 0.0, 1.0),
    "vel_random": (float, 0.0, 0.0, 1.0),
    "swing": (float, 0.0, 0.0, 0.5),
    "slide": (float, 0.0, 0.0, 1.0),
    "acentos": (float, 0.0, 0.0, 1.0),
    "saltos": (float, 0.0, 0.0, 1.0),
    "repeticion": (float, 0.0, 0.0, 1.0),
    "largas": (float, 0.0, 0.0, 1.0),
    "escala_color": (str, "", None, ("",) + tuple(ESCALAS_COLOR)),  # "" = la de Música
    "filtro": (bool, False, None, None),  # el molde filtra sus notas (apagado: suena todo)
    "molde": (str, "", None, None),  # filtro de 16 pasos: x = pasa, ? = a veces, - = bloquea
    "molde_prob": (float, 0.5, 0.0, 1.0),  # probabilidad de los «a veces»
    "recorrido": (str, "adelante", None, generador.RECORRIDOS),  # orden de los pasos: adelante, atrás, péndulo, al azar
    "molde_muta": (float, 0.0, 0.0, 1.0),   # el molde muta solo (cada «mutar cada» compases)
    "molde_estilo": (str, "goa", None, generador.ESTILOS_MOLDE),  # cómo arma y muta: goa o psy
    "semitono": (float, 0.0, 0.0, 1.0),  # cuánto aparece el ♭2 sobre la raíz en los pasos débiles
    "fx": (bool, False, None, None),         # el motor de FX la interviene: filtro y stutter en las subidas, glitches
    "cc_filtro": (int, 74, 0, 127),          # CC del filtro de su sinte
    "subida_filtro": (bool, False, None, None),  # el filtro se abre durante la subida (sin el FX)
    "subida_desde": (int, 20, 0, 127),       # dónde parte al empezar la subida
    "subida_hasta": (int, 127, 0, 127),      # cuánto queda abierto justo en el drop
    "subida_despues": (str, "vuelve", None, ("vuelve", "queda")),  # después del drop: al reposo o se queda
    "lfo": (bool, False, None, None),        # LFO de filtro por CC (opcional)
    "lfo_cc": (int, 74, 0, 127),             # 74 = corte, 71 = resonancia; 20 y 21 = wavetable A y B (FM-1 con Shrub)
    "lfo_forma": (str, "seno", None, ("seno", "triangulo", "sube", "baja", "azar")),
    "lfo_compases": (float, 4.0, 0.25, 32.0),  # una vuelta del LFO, en compases
    "lfo_min": (int, 30, 0, 127),
    "lfo_max": (int, 100, 0, 127),
    "lfo2": (bool, False, None, None),       # un segundo LFO (p. ej. resonancia junto al corte)
    "lfo2_cc": (int, 71, 0, 127),
    "lfo2_forma": (str, "triangulo", None, ("seno", "triangulo", "sube", "baja", "azar")),
    "lfo2_compases": (float, 8.0, 0.25, 32.0),
    "lfo2_min": (int, 20, 0, 127),
    "lfo2_max": (int, 80, 0, 127),
    "filtro_reposo": (int, 110, 0, 127),     # dónde vuelve el filtro después de la subida
}

# El Tocado arma su melodía con una secuencia del estilo elegido: lleva los mismos
# ajustes de patrón que una secuencia (figura, frase, respuesta, raga…).
TOCADO_PATRON = ("genero", "figura", "frase", "remate", "variar", "ciclo", "registro", "huecos", "pedal",
                 "saltos", "raga", "ornamentos", "escala_color", "semitono", "relacion", "acentos", "acento", "largo")
# Ajustes de una secuencia que el Tocado usa sin tocar el ritmo que grabaste: cómo toma
# la armonía, techo, voz doble, slide, mutación de notas, recorrido, fuerza al azar,
# filtro en la subida, FX y los dos LFO de filtro. Más los adaptados al loop (gate,
# densidad, repetición). No van los que deciden el ritmo (posición, corrimiento, molde,
# mutación de ritmo, swing): el ritmo es el tuyo.
TOCADO_EXTRA = ("armonia", "techo", "doble", "slide", "mutacion", "mutar_cada", "bloqueada", "recorrido",
                "vel_random", "gate", "gate_random", "densidad", "repeticion",
                "fx", "cc_filtro", "subida_filtro", "subida_desde", "subida_hasta", "subida_despues", "filtro_reposo",
                "lfo", "lfo_cc", "lfo_forma", "lfo_compases", "lfo_min", "lfo_max",
                "lfo2", "lfo2_cc", "lfo2_forma", "lfo2_compases", "lfo2_min", "lfo2_max")
for _clave in TOCADO_PATRON + TOCADO_EXTRA:
    ESQUEMA_SECCIONES["tocado"][_clave] = ESQUEMA_SECUENCIA[_clave]
# Los pads también tienen los dos LFO por CC (filtro u otro parámetro de su sinte).
for _clave in ("lfo", "lfo_cc", "lfo_forma", "lfo_compases", "lfo_min", "lfo_max",
               "lfo2", "lfo2_cc", "lfo2_forma", "lfo2_compases", "lfo2_min", "lfo2_max"):
    ESQUEMA_SECCIONES["pads"][_clave] = ESQUEMA_SECUENCIA[_clave]
# Largo de cada nota del loop: el tuyo (como lo tocaste) o el del estilo (su gate).
ESQUEMA_SECCIONES["tocado"]["largo_nota"] = (str, "tuyo", None, ("tuyo", "estilo"))


# Un clip guarda el carácter musical de una secuencia; el destino lo pone la fila
# del disparador donde se lanza.
CLAVES_DESTINO = ("disparo", "activa", "salida", "canal", "cc_filtro", "filtro_reposo")
ESQUEMA_CLIP = dict({k: v for k, v in ESQUEMA_SECUENCIA.items() if k not in CLAVES_DESTINO},
                    con_variante=(bool, True, None, None))  # False: al tocarlo, la secuencia conserva su seed

# Clips del bajo y de los pads: sus valores musicales (sin salida, canal ni nota larga), un
# nombre y si traen la variante (seed). Viven en clip_bajo y clip_pads.
RUTEO_MOTOR = ("activo", "salida", "canal", "disparo", "filtro_cc")
LISTA_CLIPS = {"bajo": "clip_bajo", "pads": "clip_pads"}
ESQUEMA_CLIP_MOTOR = {m: dict({"nombre": (str, "Clip", None, None)},
                              **{k: v for k, v in ESQUEMA_SECCIONES[m].items() if k not in RUTEO_MOTOR},
                              con_variante=(bool, True, None, None))
                      for m in LISTA_CLIPS}


class ConfigError(ValueError):
    pass


def _valor(clave, valor, esquema):
    tipo, defecto, minimo, extra = esquema
    if valor is None:
        return defecto
    try:
        if tipo is bool:
            if isinstance(valor, str):
                valor = valor.lower() in ("true", "1", "si", "sí")
            return bool(valor)
        valor = tipo(valor)
    except (TypeError, ValueError):
        raise ConfigError(f"Valor inválido para {clave}: {valor!r}")
    if tipo is str:
        # Los textos se cortan a 40 caracteres; un número como máximo pide otro largo
        # (el loop del Tocado guarda sus notas en JSON).
        valor = valor.strip()[:extra if isinstance(extra, int) and not isinstance(extra, bool) else 40]
        if isinstance(extra, tuple) and valor not in extra:
            raise ConfigError(f"{clave} debe ser una de: {', '.join(extra)}")
        return valor
    if minimo is not None and extra is not None:
        valor = max(minimo, min(extra, valor))
    return valor


TOCADO_ESTILOS_0_64 = {"goa": "rolling", "mantra": "arpegio3", "raga": "clasico", "bajo": "galope"}


def normalizar(cfg):
    """Devuelve una configuración limpia y completa, o lanza ConfigError."""
    if not isinstance(cfg, dict):
        raise ConfigError("La configuración debe ser un objeto")
    limpia = {}
    if isinstance(cfg.get("pads"), dict) and cfg["pads"].get("progresion") == "aleatoria":
        # «Al azar» ya no es una progresión del menú: es una casilla que varía la elegida.
        cfg = dict(cfg, pads=dict(cfg["pads"], progresion="i_bII", azar=True))
    if isinstance(cfg.get("bajo"), dict) and cfg["bajo"].get("estilo") in bajo.ALIAS:
        cfg = dict(cfg, bajo=dict(cfg["bajo"], estilo=bajo.ALIAS[cfg["bajo"]["estilo"]]))
    cfg = _migrar_moldes(cfg)
    if isinstance(cfg.get("tocado"), dict) and cfg["tocado"].get("estilo") in TOCADO_ESTILOS_0_64:
        # Los estilos propios del Tocado (0.64-0.65) pasan a los de las secuencias.
        cfg = dict(cfg, tocado=dict(cfg["tocado"], estilo=TOCADO_ESTILOS_0_64[cfg["tocado"]["estilo"]]))
    if isinstance(cfg.get("bajo"), dict) and cfg["bajo"].get("estilo") in ESTILOS_BAJO_RETIRADOS:
        # Un estilo de bajo que se sacó (deepnotic, 0.45): sigue con el más parecido.
        cfg["bajo"] = dict(cfg["bajo"], estilo=ESTILOS_BAJO_RETIRADOS[cfg["bajo"]["estilo"]])
    for seccion, esquema in ESQUEMA_SECCIONES.items():
        datos = cfg.get(seccion) or {}
        limpia[seccion] = {k: _valor(k, datos.get(k), e) for k, e in esquema.items()}
    try:
        nombre_a_clase(limpia["musica"]["tonica"])
    except ValueError as e:
        raise ConfigError(str(e))
    secuencias = cfg.get("secuencia") or []
    if not isinstance(secuencias, list):
        raise ConfigError("secuencia debe ser una lista")
    limpia["secuencia"] = [
        {k: _valor(k, (s or {}).get(k), e) for k, e in ESQUEMA_SECUENCIA.items()}
        for s in secuencias[:MAX_SECUENCIAS]
    ]
    clips = cfg.get("clip") or []
    if not isinstance(clips, list):
        raise ConfigError("clip debe ser una lista")
    limpia["clip"] = [{k: _valor(k, (s or {}).get(k), e) for k, e in ESQUEMA_CLIP.items()}
                      for s in clips[:MAX_CLIPS]]
    clips = cfg.get("clip_dialogo") or []
    if not isinstance(clips, list):
        raise ConfigError("clip_dialogo debe ser una lista")
    limpia["clip_dialogo"] = [{k: _valor(k, (s or {}).get(k), e) for k, e in ESQUEMA_CLIP_DIALOGO.items()}
                              for s in clips[:MAX_CLIPS]]
    for motor, lista in LISTA_CLIPS.items():
        clips = cfg.get(lista) or []
        if not isinstance(clips, list):
            raise ConfigError(f"{lista} debe ser una lista")
        limpia[lista] = [{k: _valor(k, (s or {}).get(k), e) for k, e in ESQUEMA_CLIP_MOTOR[motor].items()}
                         for s in clips[:MAX_CLIPS]]
    escenas = cfg.get("escena") or []
    if not isinstance(escenas, list):
        raise ConfigError("escena debe ser una lista")
    limpia["escena"] = [_escena(e) for e in escenas[:forma.MAX_ESCENAS]]
    if limpia["forma"]["escena"] >= len(limpia["escena"]):
        limpia["forma"]["escena"] = -1
    partes = cfg.get("parte") or []
    if not isinstance(partes, list):
        raise ConfigError("parte debe ser una lista")
    limpia["parte"] = [{k: _valor(k, (p or {}).get(k), e) for k, e in ESQUEMA_PARTE.items()}
                       for p in partes[:MAX_PARTES]]
    for p in limpia["parte"]:
        if p["escena"] >= len(limpia["escena"]):
            p["escena"] = -1
    if not isinstance(cfg.get("armonia_tema"), dict):
        _migrar_armonia_tema(limpia)
    return limpia


def _musica_de_escena(escena):
    datos = escena["datos"]
    datos = json.loads(datos) if isinstance(datos, str) else datos
    return {k: v for k, v in (datos.get("musica") or {}).items() if k in ESQUEMA_SECCIONES["musica"]}


def _migrar_armonia_tema(limpia):
    """Tema de antes de la armonía del tema (0.91): la base es la armonía que más se repite
    entre las escenas de sus partes (o la que suena, si no hay); las escenas con esa misma
    armonía la siguen y las demás quedan con la suya. Todo suena igual que antes."""
    usadas = [p["escena"] for p in limpia["parte"] if p["escena"] >= 0] or list(range(len(limpia["escena"])))
    completas = []
    for i in usadas:
        m = dict(limpia["musica"], **_musica_de_escena(limpia["escena"][i]))
        completas.append(json.dumps(m, sort_keys=True))
    if completas:
        base = json.loads(max(set(completas), key=lambda x: (completas.count(x), -completas.index(x))))
    else:
        base = dict(limpia["musica"])
    limpia["armonia_tema"] = {k: base[k] for k in ESQUEMA_SECCIONES["armonia_tema"]}
    for e in limpia["escena"]:
        e["armonia_propia"] = dict(limpia["musica"], **_musica_de_escena(e)) != limpia["armonia_tema"]


ESTILOS_BAJO_RETIRADOS = {"deepnotic": "offbeat"}


def _migrar_molde(d, prefijo=""):
    """Antes el molde era una guía (x = siempre nota, . = libre); ahora es un filtro que
    se prende y se apaga. Un molde pintado de antes queda prendido, y sus . pasan."""
    if not isinstance(d, dict) or prefijo + "filtro" in d:
        return d
    molde = str(d.get(prefijo + "molde") or "")
    if not set(molde) - {"."}:
        return d
    return dict(d, **{prefijo + "filtro": True, prefijo + "molde": molde.replace(".", "x")})


def _migrar_moldes(cfg):
    cfg = dict(cfg)
    for voz in VOCES:
        cfg[voz] = _migrar_molde(cfg.get(voz))
    for lista in ("secuencia", "clip"):
        if isinstance(cfg.get(lista), list):
            cfg[lista] = [_migrar_molde(x) for x in cfg[lista]]
    if isinstance(cfg.get("clip_dialogo"), list):
        clips = []
        for c in cfg["clip_dialogo"]:
            for voz in VOCES:
                c = _migrar_molde(c, voz + "_")
            clips.append(c)
        cfg["clip_dialogo"] = clips
    return cfg


def _escena(e):
    """Una escena: nombre, energía y su foto (JSON, ver forma.foto)."""
    if not isinstance(e, dict):
        raise ConfigError("Escena inválida")
    limpia = {k: _valor(k, e.get(k), esq) for k, esq in ESQUEMA_ESCENA.items()}
    datos = e.get("datos", "{}")
    if not isinstance(datos, str):
        datos = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    if len(datos) > MAX_DATOS_ESCENA:
        raise ConfigError("Escena demasiado grande")
    try:
        if not isinstance(json.loads(datos), dict):
            raise ValueError
    except ValueError:
        raise ConfigError(f"La escena {limpia['nombre']} está dañada")
    limpia["datos"] = datos
    return limpia


def clip_de(secuencia, nombre, variante=True):
    """El carácter musical de una secuencia, listo para guardarse como clip.
    variante=False: guarda todo menos la seed (al tocarlo, la secuencia sigue con la suya)."""
    clip = {k: secuencia[k] for k in ESQUEMA_CLIP if k in secuencia}
    clip["nombre"] = nombre.strip()[:40] or secuencia.get("nombre", "Clip")
    clip["con_variante"] = bool(variante)
    return clip


def clip_de_motor(cfg, motor, nombre, variante=True):
    """Lo que suena en el bajo o los pads, listo para guardarse como clip."""
    seccion = cfg[motor]
    clip = {k: seccion[k] for k in ESQUEMA_CLIP_MOTOR[motor] if k in seccion}
    clip["nombre"] = nombre.strip()[:40] or "Clip"
    clip["con_variante"] = bool(variante)
    return clip


def con_clip_de_motor(seccion, clip):
    """La sección del bajo o los pads con el clip puesto: su salida, canal y si suena se quedan."""
    fuera = {"nombre", "con_variante"} | (set() if clip.get("con_variante", True) else {"seed"})
    return dict(seccion, **{k: v for k, v in clip.items() if k not in fuera})


def clip_aplicado(fila, clip):
    """La secuencia de la fila con el clip puesto (lo que suena al lanzarlo)."""
    fuera = {"nombre", "con_variante"} | (set() if clip.get("con_variante", True) else {"seed"})
    return dict(fila, **{k: v for k, v in clip.items() if k not in fuera}, activa=True)


def clip_de_dialogo(cfg, nombre, variante=True):
    """La conversación que está armada, lista para guardarse como clip."""
    clip = {"nombre": nombre.strip()[:40] or "Diálogo"}
    clip.update({k: v for k, v in cfg["dialogo"].items() if k != "activo"})
    for voz in VOCES:
        clip.update({f"{voz}_{k}": v for k, v in cfg[voz].items()})
    clip["con_variante"] = bool(variante)
    return clip


RUTEO_DIALOGO = ("disparo",) + tuple(f"{voz}_{k}" for voz in VOCES for k in ("salida", "canal"))


def dialogo_con_clip(cfg, clip):
    """Las secciones dialogo, llamada y respuesta con el clip puesto. Igual que en las secuencias,
    el bajo y los pads: salidas, canales y nota larga se quedan como están; sin variante, la seed también."""
    actual = clip_de_dialogo(cfg, "")
    fuera = {"nombre", "con_variante"} | set(RUTEO_DIALOGO) | (set() if clip.get("con_variante", True) else {"seed"})
    actual.update({k: v for k, v in clip.items() if k not in fuera and k in actual})
    return secciones_de_clip(actual)


def secciones_de_clip(clip):
    """De un clip de diálogo a las secciones dialogo, llamada y respuesta."""
    dialogo = {k: clip[k] for k in ESQUEMA_SECCIONES["dialogo"] if k in clip}
    dialogo["activo"] = True
    voces = {voz: {k: clip[f"{voz}_{k}"] for k in ESQUEMA_SECCIONES[voz]} for voz in VOCES}
    return dialogo, voces["llamada"], voces["respuesta"]


def _suenan_en_cancion(cfg):
    """Modo canción: qué motores (pads, bajo, diálogo) suenan en alguna parte, para
    abrir sus puertos desde el principio y no perder las primeras notas de la parte."""
    suenan = set()
    if not cfg.get("cancion", {}).get("activa"):
        return suenan
    for p in cfg.get("parte", []):
        if 0 <= p["escena"] < len(cfg["escena"]):
            try:
                datos = json.loads(cfg["escena"][p["escena"]]["datos"])
            except ValueError:
                continue
            for motor in ("pads", "bajo", "dialogo", "fx", "texturas", "looper", "obertura"):
                if (datos.get(motor) or {}).get("activo"):
                    suenan.add(motor)
    return suenan


def salidas(cfg):
    """Todos los puertos de salida que usa la configuración."""
    claves = [s["salida"] for s in cfg["secuencia"]]
    cancion = _suenan_en_cancion(cfg)
    if cfg["thru"]["activo"]:
        claves.append(cfg["thru"]["salida"])
    if cfg["pads"]["activo"] or "pads" in cancion:
        claves.append(cfg["pads"]["salida"])
    if cfg["bajo"]["activo"] or "bajo" in cancion:
        claves.append(cfg["bajo"]["salida"])
    if cfg["fx"]["activo"] or "fx" in cancion:
        claves.append(cfg["fx"]["salida"])
    if cfg["texturas"]["activo"] or "texturas" in cancion:
        claves.append(cfg["texturas"]["salida"])
    if cfg["obertura"]["activo"] or "obertura" in cancion:
        claves.append(cfg["obertura"]["salida"])
    if cfg["looper"]["activo"] or cfg["looper"]["clip"] or "looper" in cancion:   # apagado, sigue abierta para callarlo
        claves.append(cfg["looper"]["salida"])
    if cfg["tocado"]["activo"]:
        claves.append(cfg["tocado"]["salida"])
    if any(p.get("scatter") for p in cfg.get("parte", [])) and cfg.get("cancion", {}).get("activa"):
        claves.append(cfg["scatter"]["salida"])
    if cfg["teclado"]["activo"] and cfg["teclado"]["perillas"]:
        claves.append(cfg["teclado"]["puerto"])  # para devolverle sus perillas
    if cfg["control"]["activo"] and cfg["control"]["luces"]:
        claves.append(cfg["control"]["puerto"])  # para prender sus botones
    if cfg["dialogo"]["activo"] or "dialogo" in cancion:
        if cfg["dialogo"]["modo"] == "motor":
            claves.append(cfg["llamada"]["salida"])
        claves.append(cfg["respuesta"]["salida"])
    return claves


def cargar(ruta):
    with open(ruta, "rb") as f:
        return normalizar(tomllib.load(f))


def _toml(valor):
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, (int, float)):
        return repr(valor)
    return json.dumps(valor, ensure_ascii=False)


def a_toml(cfg):
    lineas = ["# Configuración del motor Goa (guardada por la app).",
              "# Las opciones están explicadas en config.ejemplo.toml.", ""]
    for seccion in ESQUEMA_SECCIONES:
        lineas.append(f"[{seccion}]")
        lineas += [f"{k} = {_toml(v)}" for k, v in cfg[seccion].items()]
        lineas.append("")
    for s in cfg["secuencia"]:
        lineas.append("[[secuencia]]")
        lineas += [f"{k} = {_toml(v)}" for k, v in s.items()]
        lineas.append("")
    for s in cfg.get("clip", []):
        lineas.append("[[clip]]")
        lineas += [f"{k} = {_toml(v)}" for k, v in s.items()]
        lineas.append("")
    for lista in LISTA_CLIPS.values():
        for s in cfg.get(lista, []):
            lineas.append(f"[[{lista}]]")
            lineas += [f"{k} = {_toml(v)}" for k, v in s.items()]
            lineas.append("")
    for s in cfg.get("clip_dialogo", []):
        lineas.append("[[clip_dialogo]]")
        lineas += [f"{k} = {_toml(v)}" for k, v in s.items()]
        lineas.append("")
    for s in cfg.get("escena", []):
        lineas.append("[[escena]]")
        lineas += [f"{k} = {_toml(v)}" for k, v in s.items()]
        lineas.append("")
    for s in cfg.get("parte", []):
        lineas.append("[[parte]]")
        lineas += [f"{k} = {_toml(v)}" for k, v in s.items()]
        lineas.append("")
    return "\n".join(lineas)


def guardar(ruta, cfg, texto=None):
    """Escritura atómica: nunca deja el archivo a medias, ni vacío si se corta la luz
    justo después (fsync antes de reemplazarlo). La versión anterior queda como
    `.respaldo`: si el archivo se daña, el motor arranca con ella (ver main.cargar_seguro)."""
    ruta = os.fspath(ruta)   # también una Path (los proyectos): antes, al sobrescribir, fallaba
    carpeta = os.path.dirname(os.path.abspath(ruta))
    fd, temporal = tempfile.mkstemp(dir=carpeta, prefix=".config-", suffix=".toml")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(a_toml(cfg) if texto is None else texto)   # `texto`: ya convertido (no dos veces)
        f.flush()
        os.fsync(f.fileno())
    if os.path.exists(ruta):
        try:
            os.replace(ruta, ruta + ".respaldo")
        except OSError:
            pass
    os.replace(temporal, ruta)
    try:
        d = os.open(carpeta, os.O_RDONLY)
        try:
            os.fsync(d)
        finally:
            os.close(d)
    except OSError:
        pass


# Lo que «Restaurar ajustes de fábrica» no toca: a dónde y cómo suena (salida, canal,
# programa, CCs del sinte), su nota larga, si está prendida, su nombre, el género del
# proyecto y la seed (el patrón propio de esa secuencia).
CONSERVAR_EN_FABRICA = ("nombre", "disparo", "activa", "salida", "canal", "programa", "genero", "seed",
                        "cc_filtro", "lfo_cc", "lfo2_cc")


def fabrica_secuencia(secuencia):
    """La secuencia con todos sus ajustes musicales en los valores de fábrica."""
    nueva = {clave: valor for clave, (_, valor, _, _) in ESQUEMA_SECUENCIA.items()}
    nueva.update({k: secuencia[k] for k in CONSERVAR_EN_FABRICA if k in secuencia})
    return nueva


# Lo que «Restaurar ajustes de fábrica» no toca en los otros motores: si está prendido,
# a dónde y cómo suena (salida, canal, programa y los CC de su sinte), su nota larga o la
# entrada que escucha, el género y la seed.
CONSERVAR_EN_FABRICA_MOTOR = ("activo", "suenan", "salida", "canal", "programa", "disparo", "escucha", "genero", "seed",
                              "filtro_cc", "cc_corte", "cc", "parar", "loop")
MOTORES_FABRICA = {"pads": ("pads",), "bajo": ("bajo",), "dialogo": ("dialogo", "llamada", "respuesta"),
                   "fx": ("fx",), "texturas": ("texturas",), "looper": ("looper",), "tocado": ("tocado",),
                   "obertura": ("obertura",)}


def _fabrica_seccion(seccion, datos):
    nueva = {clave: valor for clave, (_, valor, _, _) in ESQUEMA_SECCIONES[seccion].items()}
    nueva.update({k: datos[k] for k in CONSERVAR_EN_FABRICA_MOTOR if k in datos and k in nueva})
    return nueva


def fabrica_bajo(bajo):
    """El bajo con todos sus ajustes musicales en los valores de fábrica."""
    return _fabrica_seccion("bajo", bajo)


def fabrica_motor(cfg, motor, fila=0):
    """Copia de `cfg` con un motor en sus ajustes de fábrica: "secuencia" (con su fila),
    "pads", "bajo", "dialogo" (con sus voces de llamada y respuesta), "fx" o "texturas"."""
    nueva = dict(cfg)
    if motor == "secuencia":
        filas = list(cfg["secuencia"])
        if not 0 <= fila < len(filas):
            raise IndexError("No existe esa secuencia")
        filas[fila] = fabrica_secuencia(filas[fila])
        nueva["secuencia"] = filas
    elif motor in MOTORES_FABRICA:
        for seccion in MOTORES_FABRICA[motor]:
            nueva[seccion] = _fabrica_seccion(seccion, cfg.get(seccion) or {})
    else:
        raise ValueError(f"Motor desconocido: {motor!r}")
    return nueva
