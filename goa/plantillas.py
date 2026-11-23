"""Plantillas de canción: estructuras listas para el modo canción.

Cada plantilla tiene su proyecto gemelo en la Circuit (mismos nombres y compases),
armado con herramientas/circuit_cancion.py a partir de esta misma lista, así que
los dos lados nunca se desfasan. Las partes vienen sin escena: cada una «sigue lo
que suena» hasta que le guardas lo que quieres con «Guardar lo que suena».
"""

PLANTILLAS = {
    "template1": {
        "nombre": "Template 1 · Psytrance · slot 32",
        "descripcion": "Psytrance a 140 BPM, 16 escenas, 240 compases (unos 6:51; las subidas de 8). En la Circuit: proyecto 32.",
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
            ("Break", 16, 0.25, 0.2, "golpe"),
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
        "descripcion": "Dark minimal estilo Zenonesque a 142 BPM, 16 escenas, 240 compases (unos 6:46; las subidas de 8). Pocos elementos que entran de a uno, percusión glitch solo aguda (el grave queda para bombo y bajo), sin grandes drops. En la Circuit: proyecto 33.",
        "bpm": 142,
        "circuit_proyecto": 33,
        "partes": [
            ("Intro", 16, 0.15, 0.25, "suave"),
            ("Intro 2", 16, 0.25, 0.3, "suave"),
            ("Pulso", 16, 0.35, 0.4, "suave"),
            ("Groove A", 16, 0.45, 0.45, "suave"),
            ("Groove B", 16, 0.5, 0.5, "suave"),
            ("Groove C", 16, 0.55, 0.55, "suave"),
            ("Break", 16, 0.3, 0.3, "golpe"),
            ("Rise", 8, 0.35, 0.75, "suave"),
            ("Climax A", 16, 0.75, 0.75, "golpe"),
            ("Climax B", 16, 0.8, 0.8, "suave"),
            ("Break 2", 16, 0.35, 0.35, "golpe"),
            ("Rise 2", 8, 0.4, 0.85, "suave"),
            ("Climax C", 16, 0.85, 0.85, "golpe"),
            ("Groove D", 16, 0.75, 0.7, "suave"),
            ("Outro", 16, 0.5, 0.3, "suave"),
            ("Final", 16, 0.25, 0.1, "suave"),
        ],
    },
    "template3": {
        "nombre": "Template 3 · Goa clásico · slot 34",
        "descripcion": "Goa clásico a 140 BPM, 16 escenas, 240 compases (unos 6:51; las subidas de 8). Bombo tipo 909, snare, toms que rematan, breakdown largo y ride. En la Circuit: proyecto 34.",
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
            ("Break 2", 16, 0.3, 0.3, "golpe"),
            ("Rise 2", 8, 0.35, 0.9, "suave"),
            ("Drop", 16, 0.95, 0.9, "golpe"),
            ("Groove D", 16, 0.75, 0.7, "suave"),
            ("Groove E", 16, 0.7, 0.6, "suave"),
            ("Outro", 16, 0.5, 0.25, "suave"),
        ],
    },
    "template4": {
        "nombre": "Template 4 · Goa tribal · slot 35",
        "descripcion": "Goa tribal a 140 BPM, 16 escenas, 240 compases (unos 6:51; las subidas de 8). Congas y toms tejidos, tambores antes del bombo, ceremonia a medio tiempo. En la Circuit: proyecto 35.",
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
            ("Circulo", 16, 0.35, 0.35, "golpe"),
            ("Fuego 2", 8, 0.4, 0.9, "suave"),
            ("Trance C", 16, 0.95, 0.9, "golpe"),
            ("Trance D", 16, 0.9, 0.85, "suave"),
            ("Danza C", 16, 0.75, 0.7, "suave"),
            ("Danza final", 16, 0.7, 0.6, "suave"),
            ("Despedida", 16, 0.45, 0.2, "suave"),
        ],
    },
    "template5": {
        "nombre": "Template 5 · Goa épico · slot 40",
        "descripcion": "Goa épico a 140 BPM, 224 compases (unos 6:24). Arcos largos, redobles en dos olas, crash cada 8 compases, valles largos. En la Circuit: proyecto 40.",
        "bpm": 140,
        "circuit_proyecto": 40,
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
    "template6": {
        "nombre": "Template 6 · Psy chill · slot 41",
        "descripcion": "Psy chill a 104 BPM con shuffle, 16 escenas, 240 compases (unos 9:14; las subidas de 8). Bombo redondo, clap largo, congas y blips. Para el género Psy chill (escala dórica). En la Circuit: proyecto 41.",
        "bpm": 104,
        "genero": "psy_chill",
        "escala_circuit": "dorian",
        "circuit_proyecto": 41,
        "partes": [
            ("Intro", 16, 0.15, 0.2, "suave"),
            ("Intro 2", 16, 0.2, 0.3, "suave"),
            ("Entra bombo", 16, 0.3, 0.4, "suave"),
            ("Groove A", 16, 0.5, 0.55, "suave"),
            ("Groove B", 16, 0.6, 0.6, "suave"),
            ("Groove C", 16, 0.65, 0.65, "suave"),
            ("Break", 16, 0.25, 0.25, "golpe"),
            ("Rise", 8, 0.3, 0.75, "suave"),
            ("Viaje A", 16, 0.7, 0.7, "golpe"),
            ("Viaje B", 16, 0.75, 0.75, "suave"),
            ("Respiro", 16, 0.3, 0.3, "golpe"),
            ("Rise 2", 8, 0.35, 0.8, "suave"),
            ("Viaje C", 16, 0.8, 0.8, "golpe"),
            ("Viaje D", 16, 0.75, 0.7, "suave"),
            ("Outro", 16, 0.45, 0.3, "suave"),
            ("Final", 16, 0.25, 0.1, "suave"),
        ],
    },
    "template7": {
        "nombre": "Template 7 · Chillgressive · slot 42",
        "descripcion": "Chillgressive a 120 BPM, 16 escenas, 240 compases (unos 8:00; las subidas de 8). Groove progresivo de hats en semicorcheas, clap en 2 y 4, breaks largos. Para el género Chillgressive (escala menor). En la Circuit: proyecto 42.",
        "bpm": 120,
        "genero": "chillgressive",
        "escala_circuit": "natural minor",
        "circuit_proyecto": 42,
        "partes": [
            ("Intro", 16, 0.15, 0.2, "suave"),
            ("Intro 2", 16, 0.2, 0.3, "suave"),
            ("Pulso", 16, 0.3, 0.4, "suave"),
            ("Groove A", 16, 0.5, 0.55, "suave"),
            ("Groove B", 16, 0.6, 0.65, "suave"),
            ("Groove C", 16, 0.65, 0.65, "suave"),
            ("Break", 16, 0.25, 0.3, "golpe"),
            ("Rise", 8, 0.35, 0.8, "suave"),
            ("Drive A", 16, 0.75, 0.75, "golpe"),
            ("Drive B", 16, 0.8, 0.8, "suave"),
            ("Drive C", 16, 0.8, 0.8, "suave"),
            ("Break 2", 16, 0.3, 0.3, "golpe"),
            ("Rise 2", 8, 0.35, 0.85, "suave"),
            ("Drive D", 16, 0.85, 0.8, "golpe"),
            ("Outro", 16, 0.45, 0.3, "suave"),
            ("Final", 16, 0.25, 0.1, "suave"),
        ],
    },
    "template8": {
        "nombre": "Template 8 · Chillout · slot 43",
        "descripcion": "Chillout downtempo a 92 BPM con swing, 16 escenas, 240 compases (unos 10:26; las subidas de 8). Beat quebrado, snare con cuerpo, shaker y congas. Para el género Chillout (escala menor). En la Circuit: proyecto 43.",
        "bpm": 92,
        "genero": "chillout",
        "escala_circuit": "natural minor",
        "circuit_proyecto": 43,
        "partes": [
            ("Intro", 16, 0.15, 0.2, "suave"),
            ("Intro 2", 16, 0.2, 0.3, "suave"),
            ("Llega el beat", 16, 0.3, 0.4, "suave"),
            ("Tema A", 16, 0.45, 0.5, "suave"),
            ("Tema B", 16, 0.55, 0.6, "suave"),
            ("Tema C", 16, 0.55, 0.55, "suave"),
            ("Pausa", 16, 0.25, 0.25, "golpe"),
            ("Vuelta", 8, 0.3, 0.6, "suave"),
            ("Tema D", 16, 0.6, 0.65, "golpe"),
            ("Tema E", 16, 0.6, 0.6, "suave"),
            ("Tema F", 16, 0.55, 0.55, "suave"),
            ("Pausa 2", 16, 0.25, 0.25, "golpe"),
            ("Vuelta 2", 8, 0.3, 0.65, "suave"),
            ("Tema G", 16, 0.65, 0.6, "golpe"),
            ("Final", 16, 0.4, 0.25, "suave"),
            ("Cierre", 16, 0.2, 0.1, "suave"),
        ],
    },
    "template9": {
        "nombre": "Template 9 · Ambient · slot 44",
        "descripcion": "Ambient a 76 BPM, 16 escenas, 240 compases (unos 12:38; las subidas de 8, suaves). Sin bombo fijo: latidos suaves, percusión casi inaudible, texturas, swells y mucha reverb. Para el género Ambient. En la Circuit: proyecto 44.",
        "bpm": 76,
        "genero": "ambient",
        "escala_circuit": "major",
        "circuit_proyecto": 44,
        "partes": [
            ("Intro", 16, 0.1, 0.12, "suave"),
            ("Intro 2", 16, 0.12, 0.15, "suave"),
            ("Pulso", 16, 0.18, 0.2, "suave"),
            ("Groove A", 16, 0.25, 0.3, "suave"),
            ("Groove B", 16, 0.3, 0.35, "suave"),
            ("Groove C", 16, 0.35, 0.4, "suave"),
            ("Break", 16, 0.2, 0.2, "suave"),
            ("Rise", 8, 0.25, 0.45, "suave"),
            ("Climax A", 16, 0.45, 0.45, "suave"),
            ("Climax B", 16, 0.5, 0.5, "suave"),
            ("Break 2", 16, 0.3, 0.3, "suave"),
            ("Rise 2", 8, 0.3, 0.5, "suave"),
            ("Climax C", 16, 0.5, 0.45, "suave"),
            ("Groove D", 16, 0.35, 0.35, "suave"),
            ("Outro", 16, 0.25, 0.15, "suave"),
            ("Final", 16, 0.1, 0.05, "suave"),
        ],
    },
}


def partes_de(clave):
    """Las partes de una plantilla, listas para la configuración (sin escena)."""
    p = PLANTILLAS[clave]
    return [{"nombre": n, "compases": c, "escena": -1, "energia": a, "energia_fin": b, "entrada": e}
            for n, c, a, b, e in p["partes"]]


def actualizar(partes, clave):
    """Pone al día una canción ya armada con su plantilla sin perder lo tuyo.

    Sigue el orden de la plantilla: cada parte que ya tenías (por nombre) conserva su
    escena, energía, entrada y apoyos, y solo toma los compases de la plantilla; las
    partes nuevas de la plantilla entran sin escena. Las tuyas que la plantilla no
    tiene quedan al final. Devuelve (partes, cambios) con un texto por cada cambio.
    """
    tuyas = [dict(p) for p in partes]
    usadas = set()
    nuevas, cambios = [], []
    for base in partes_de(clave):
        i = next((i for i, p in enumerate(tuyas) if i not in usadas and p.get("nombre") == base["nombre"]), None)
        if i is None:
            nuevas.append(base)
            cambios.append(f"{base['nombre']}: nueva ({base['compases']} compases, sin escena)")
            continue
        usadas.add(i)
        p = tuyas[i]
        if p.get("compases") != base["compases"]:
            cambios.append(f"{base['nombre']}: {p.get('compases')} → {base['compases']} compases")
            p["compases"] = base["compases"]
        nuevas.append(p)
    for i, p in enumerate(tuyas):
        if i not in usadas:
            nuevas.append(p)
            cambios.append(f"{p.get('nombre')}: no está en la plantilla, queda al final")
    return nuevas, cambios


def clave_de(nombre):
    """La plantilla de una canción por su nombre («Template 6 · Psy chill …» → template6)."""
    import re
    m = re.match(r"\s*Template\s+(\d+)", nombre or "")
    clave = f"template{m.group(1)}" if m else None
    return clave if clave in PLANTILLAS else None


def lista():
    """Para la app: clave, nombre, descripción, partes y compases totales."""
    return [{"clave": k, "nombre": p["nombre"], "descripcion": p["descripcion"], "partes": len(p["partes"]),
             "compases": sum(x[1] for x in p["partes"]), "bpm": p["bpm"],
             "energias": [[x[1], round((x[2] + x[3]) / 2, 2)] for x in p["partes"]]} for k, p in PLANTILLAS.items()]
