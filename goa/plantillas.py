"""Plantillas de canción: estructuras listas para el modo canción.

Cada plantilla tiene su proyecto gemelo en la Circuit (mismos nombres y compases),
armado con herramientas/circuit_cancion.py a partir de esta misma lista, así que
los dos lados nunca se desfasan. Las partes vienen sin escena: cada una «sigue lo
que suena» hasta que le guardas lo que quieres con «Guardar lo que suena».
"""

PLANTILLAS = {
    "template1": {
        "nombre": "Template 1 · Psytrance · slot 32",
        "descripcion": "Psytrance a 140 BPM, 232 compases (unos 6:38), 16 escenas. En la Circuit: proyecto 32.",
        "bpm": 140,
        "circuit_proyecto": 32,
        # (nombre, compases, energía al empezar, al terminar, entrada)
        "partes": [
            ("Intro", 16, 0.2, 0.3, "suave"),
            ("Intro bombo", 16, 0.35, 0.45, "suave"),
            ("Build", 16, 0.45, 0.75, "suave"),
            ("Groove A", 16, 0.65, 0.65, "suave"),
            ("Groove B", 16, 0.7, 0.7, "suave"),
            ("Groove C", 16, 0.75, 0.75, "suave"),
            ("Break", 8, 0.25, 0.2, "golpe"),
            ("Rise", 8, 0.3, 0.85, "suave"),
            ("Climax A", 16, 0.85, 0.85, "golpe"),
            ("Climax B", 16, 0.9, 0.9, "suave"),
            ("Groove D", 16, 0.8, 0.8, "suave"),
            ("Break 2", 16, 0.3, 0.25, "golpe"),
            ("Rise 2", 8, 0.35, 0.9, "suave"),
            ("Drop", 16, 0.95, 0.9, "golpe"),
            ("Groove E", 16, 0.75, 0.7, "suave"),
            ("Outro", 16, 0.5, 0.25, "suave"),
        ],
    },
    "template2": {
        "nombre": "Template 2 · Dark minimal · slot 33",
        "descripcion": "Dark minimal estilo Zenonesque a 142 BPM, 224 compases (unos 6:19). Pocos elementos que entran de a uno, percusión glitch, sin grandes drops. En la Circuit: proyecto 33.",
        "bpm": 142,
        "circuit_proyecto": 33,
        "partes": [
            ("Intro", 16, 0.15, 0.25, "suave"),
            ("Pulso", 16, 0.3, 0.4, "suave"),
            ("Capa 1", 16, 0.45, 0.45, "suave"),
            ("Capa 2", 16, 0.5, 0.5, "suave"),
            ("Capa 3", 16, 0.55, 0.55, "suave"),
            ("Respiro", 8, 0.3, 0.3, "golpe"),
            ("Tension", 16, 0.5, 0.7, "suave"),
            ("Nucleo A", 16, 0.75, 0.75, "golpe"),
            ("Nucleo B", 16, 0.8, 0.8, "suave"),
            ("Respiro 2", 8, 0.35, 0.35, "golpe"),
            ("Nucleo C", 16, 0.8, 0.8, "golpe"),
            ("Fragmento", 16, 0.65, 0.65, "suave"),
            ("Nucleo D", 16, 0.85, 0.85, "suave"),
            ("Disolucion", 16, 0.6, 0.4, "suave"),
            ("Final", 16, 0.3, 0.15, "suave"),
        ],
    },
    "template3": {
        "nombre": "Template 3 · Goa clásico · slot 34",
        "descripcion": "Goa clásico a 140 BPM, 216 compases (unos 6:10). Bombo tipo 909, snare, toms que rematan, breakdown largo y ride. En la Circuit: proyecto 34.",
        "bpm": 140,
        "circuit_proyecto": 34,
        "partes": [
            ("Intro", 16, 0.2, 0.3, "suave"),
            ("Intro bombo", 16, 0.35, 0.5, "suave"),
            ("Groove A", 16, 0.6, 0.6, "suave"),
            ("Groove B", 16, 0.65, 0.65, "suave"),
            ("Toms", 16, 0.7, 0.7, "suave"),
            ("Breakdown", 16, 0.25, 0.3, "golpe"),
            ("Rise", 8, 0.35, 0.85, "suave"),
            ("Climax A", 16, 0.85, 0.85, "golpe"),
            ("Climax B", 16, 0.9, 0.9, "suave"),
            ("Groove C", 16, 0.7, 0.7, "suave"),
            ("Break 2", 8, 0.3, 0.3, "golpe"),
            ("Rise 2", 8, 0.35, 0.9, "suave"),
            ("Drop", 16, 0.95, 0.9, "golpe"),
            ("Groove D", 16, 0.75, 0.7, "suave"),
            ("Outro", 16, 0.5, 0.25, "suave"),
        ],
    },
    "template4": {
        "nombre": "Template 4 · Goa tribal · slot 35",
        "descripcion": "Goa tribal a 140 BPM, 200 compases (unos 5:43). Congas y toms tejidos, tambores antes del bombo, ceremonia a medio tiempo. En la Circuit: proyecto 35.",
        "bpm": 140,
        "circuit_proyecto": 35,
        "partes": [
            ("Llamado", 16, 0.2, 0.3, "suave"),
            ("Tambores", 16, 0.35, 0.45, "suave"),
            ("Entra el bombo", 16, 0.55, 0.55, "golpe"),
            ("Danza A", 16, 0.6, 0.65, "suave"),
            ("Danza B", 16, 0.7, 0.7, "suave"),
            ("Ceremonia", 16, 0.4, 0.45, "golpe"),
            ("Fuego", 8, 0.45, 0.85, "suave"),
            ("Trance A", 16, 0.85, 0.85, "golpe"),
            ("Trance B", 16, 0.9, 0.9, "suave"),
            ("Circulo", 8, 0.35, 0.35, "golpe"),
            ("Fuego 2", 8, 0.4, 0.9, "suave"),
            ("Trance C", 16, 0.95, 0.9, "golpe"),
            ("Danza final", 16, 0.7, 0.6, "suave"),
            ("Despedida", 16, 0.45, 0.2, "suave"),
        ],
    },
    "template5": {
        "nombre": "Template 5 · Goa épico",
        "descripcion": "Goa épico a 140 BPM, 224 compases (unos 6:24). Arcos largos, redobles en dos olas, crash cada 8 compases, valles largos.",
        "bpm": 140,
        "circuit_proyecto": None,
        "partes": [
            ("Amanecer", 16, 0.15, 0.25, "suave"),
            ("Despertar", 16, 0.3, 0.45, "suave"),
            ("Camino", 16, 0.55, 0.6, "suave"),
            ("Camino 2", 16, 0.65, 0.7, "suave"),
            ("Valle", 16, 0.3, 0.25, "golpe"),
            ("Ascenso", 8, 0.3, 0.6, "suave"),
            ("Ascenso 2", 8, 0.6, 0.9, "suave"),
            ("Cumbre A", 16, 0.9, 0.9, "golpe"),
            ("Cumbre B", 16, 0.9, 0.9, "suave"),
            ("Meseta", 16, 0.75, 0.7, "suave"),
            ("Valle 2", 8, 0.3, 0.35, "golpe"),
            ("Ascenso 3", 8, 0.45, 0.9, "suave"),
            ("Cumbre final", 16, 0.95, 0.95, "golpe"),
            ("Cumbre final 2", 16, 0.95, 0.9, "suave"),
            ("Descenso", 16, 0.65, 0.45, "suave"),
            ("Ocaso", 16, 0.35, 0.15, "suave"),
        ],
    },
}


def partes_de(clave):
    """Las partes de una plantilla, listas para la configuración (sin escena)."""
    p = PLANTILLAS[clave]
    return [{"nombre": n, "compases": c, "escena": -1, "energia": a, "energia_fin": b, "entrada": e}
            for n, c, a, b, e in p["partes"]]


def lista():
    """Para la app: clave, nombre, descripción, partes y compases totales."""
    return [{"clave": k, "nombre": p["nombre"], "descripcion": p["descripcion"], "partes": len(p["partes"]),
             "compases": sum(x[1] for x in p["partes"]), "bpm": p["bpm"]} for k, p in PLANTILLAS.items()]
