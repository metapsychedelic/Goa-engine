"""Plantillas de canción: estructuras listas para el modo canción.

Cada plantilla tiene su proyecto gemelo en la Circuit (mismos nombres y compases),
armado con herramientas/circuit_cancion.py a partir de esta misma lista, así que
los dos lados nunca se desfasan. Las partes vienen sin escena: cada una «sigue lo
que suena» hasta que le guardas lo que quieres con «Guardar lo que suena».
"""

PLANTILLAS = {
    "template1": {
        "nombre": "Template 1 · slot 32",
        "descripcion": "Psytrance a 140 BPM, 176 compases (unos 5 minutos). En la Circuit: proyecto 32.",
        "bpm": 140,
        "circuit_proyecto": 32,
        # (nombre, compases, energía al empezar, al terminar, entrada)
        "partes": [
            ("Intro", 16, 0.2, 0.3, "suave"),
            ("Intro bombo", 16, 0.35, 0.45, "suave"),
            ("Build", 16, 0.45, 0.75, "suave"),
            ("Groove A", 16, 0.65, 0.65, "suave"),
            ("Groove B", 16, 0.7, 0.7, "suave"),
            ("Break", 8, 0.25, 0.2, "golpe"),
            ("Rise", 8, 0.3, 0.85, "suave"),
            ("Climax A", 16, 0.85, 0.85, "golpe"),
            ("Climax B", 16, 0.9, 0.9, "suave"),
            ("Break 2", 8, 0.3, 0.3, "golpe"),
            ("Drop", 16, 0.95, 0.9, "golpe"),
            ("Groove C", 16, 0.75, 0.7, "suave"),
            ("Outro", 8, 0.5, 0.3, "suave"),
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
