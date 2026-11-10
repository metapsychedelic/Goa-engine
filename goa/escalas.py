"""Escalas, nombres de notas y conversión de grados a notas MIDI."""

ESCALAS = {
    "frigio": [0, 1, 3, 5, 7, 8, 10],
    "menor_armonica": [0, 2, 3, 5, 7, 8, 11],
    "frigio_dominante": [0, 1, 4, 5, 7, 8, 10],
    "menor": [0, 2, 3, 5, 7, 8, 10],
    "hungara_menor": [0, 2, 3, 6, 7, 8, 11],
    "dorico": [0, 2, 3, 5, 7, 9, 10],      # menor con sexta mayor: abierto, psy chill
    "lidio": [0, 2, 4, 6, 7, 9, 11],       # cuarta aumentada: espacial, para ambient
}

_NOMBRES = {
    "C": 0, "DO": 0, "D": 2, "RE": 2, "E": 4, "MI": 4, "F": 5, "FA": 5,
    "G": 7, "SOL": 7, "A": 9, "LA": 9, "B": 11, "SI": 11,
}


def nombre_a_clase(nombre):
    """'F', 'Fa', 'F#', 'Gb', 'Sib' -> clase de altura 0..11."""
    n = nombre.strip().upper()
    alteracion = 0
    while n and n[-1] in "#B" and n not in _NOMBRES:
        alteracion += 1 if n[-1] == "#" else -1
        n = n[:-1]
    if n not in _NOMBRES:
        raise ValueError(f"Nota desconocida: {nombre!r}")
    return (_NOMBRES[n] + alteracion) % 12


def nombre_midi(nota):
    nombres = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    return f"{nombres[nota % 12]}{nota // 12 - 1}"


class Tonalidad:
    def __init__(self, tonica, escala):
        if escala not in ESCALAS:
            raise ValueError(f"Escala desconocida: {escala!r}. Opciones: {', '.join(ESCALAS)}")
        self.tonica = nombre_a_clase(tonica)
        self.intervalos = ESCALAS[escala]
        # Todas las notas MIDI de la escala, de 0 a 127.
        self.notas = [n for n in range(128) if (n - self.tonica) % 12 in self.intervalos]

    def nota(self, raiz, grados, modo):
        """Nota que está `grados` pasos de escala por sobre `raiz`.

        modo "escala": la raíz se ajusta a la escala de la tonalidad y se
        cuenta dentro de ella (transposición diatónica).
        modo "transponer": la escala se construye desde la raíz misma,
        así el patrón se mueve igual con cualquier nota.
        """
        if modo == "transponer":
            octava, i = divmod(grados, 7)
            return _limitar(raiz + self.intervalos[i] + 12 * octava)
        indice = min(range(len(self.notas)), key=lambda k: abs(self.notas[k] - raiz))
        destino = max(0, min(len(self.notas) - 1, indice + grados))
        return self.notas[destino]


def _limitar(nota):
    while nota > 127:
        nota -= 12
    while nota < 0:
        nota += 12
    return nota
