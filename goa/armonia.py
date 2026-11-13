"""Mapa armónico compartido.

Los pads guían la armonía: saben qué acorde suena, cuál viene y en cuántos
pasos llega (la progresión es determinista). Las secuencias y la llamada y
respuesta lo leen en cada paso. Sin pads, la armonía es el acorde de la
escala sobre la nota larga, y no se puede anticipar nada.

Modo guiado (por defecto):
- Los motivos conservan su ritmo y su forma; solo se ajustan las alturas.
- En los tiempos fuertes (y la última nota de cada voz en el diálogo) caen
  notas del acorde. En los débiles, la tensión decide cuántas notas de paso quedan.
- Con "anticipar", la última nota antes de un cambio de acorde lleva al acorde
  que viene: una nota común se queda; si no, va un paso de escala junto a su
  nota más cercana.

Modo libre: como antes, cada motor cuenta grados desde su raíz sin mirar el acorde.

Todo queda dentro de la escala: las notas del acorde y las de paso salen de ella.
"""

from dataclasses import dataclass

MODOS = ("guiada", "libre")
MODOS_MOTOR = ("general", "guiada", "libre")
VENTANA_ANTICIPAR = 4  # la última nota del último tiempo antes del cambio


@dataclass(frozen=True)
class Momento:
    raiz: int                       # raíz del acorde que suena
    clases: frozenset               # sus clases de altura (notas del acorde)
    siguiente: int | None = None    # raíz del acorde que viene
    clases_siguiente: frozenset | None = None
    falta: int | None = None        # pasos hasta el cambio (None: no se sabe)

    @property
    def cambia_pronto(self):
        """True si en el último tiempo antes de un cambio a un acorde distinto."""
        return (self.falta is not None and 0 < self.falta <= VENTANA_ANTICIPAR
                and self.clases_siguiente is not None and self.clases_siguiente != self.clases)


def de_nota_larga(raiz, tonalidad):
    """Sin pads: el acorde de la escala sobre la nota larga (raíz, tercera y quinta)."""
    return Momento(raiz, frozenset(tonalidad.nota(raiz, g, "escala") % 12 for g in (0, 2, 4)))


def nota_del_acorde(nota, clases):
    """La nota del acorde más cercana; en empate, la de abajo (más oscura)."""
    for d in (0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5, -6, 6):
        if (nota + d) % 12 in clases:
            return nota + d
    return nota


def aproximacion(nota, momento, tonalidad):
    """Nota que lleva al acorde que viene, desde el lado por donde viene la línea."""
    meta = nota_del_acorde(nota, momento.clases_siguiente)
    if meta == nota:
        return nota  # nota común con el acorde que viene: se queda, es la unión más suave
    return tonalidad.nota(meta, 1 if nota > meta else -1, "escala")


def ajustar(nota, momento, tonalidad, fuerte, ultima, tension, anticipar, azar):
    """Altura guiada por la armonía para una nota que ya calculó su motor.

    fuerte: tiempo fuerte o nota que cierra un motivo (va a nota del acorde).
    ultima: última nota antes del cambio de acorde (si anticipar, lleva al que viene).
    azar: número de 0 a 1 determinista de esa nota (para la tensión)."""
    if momento is None:
        return nota
    if ultima and anticipar and momento.cambia_pronto:
        return aproximacion(nota, momento, tonalidad)
    if fuerte or azar >= tension:
        return nota_del_acorde(nota, momento.clases)
    return nota


def clases_de(tonalidad):
    """Clases de altura de una tonalidad (sus 7 notas)."""
    return frozenset((tonalidad.tonica + i) % 12 for i in tonalidad.intervalos)


def parentesco(vieja, nueva):
    """Cuántas notas comparten dos tonalidades (7 = las mismas)."""
    return len(clases_de(vieja) & clases_de(nueva))


def triada(tonalidad, raiz):
    return frozenset(tonalidad.nota(raiz, g, "escala") % 12 for g in (0, 2, 4))


# Grados (de la tonalidad nueva) que sirven de puente, en orden de preferencia:
# V, ♭III, iv, ♭VI, ♭VII, ii. El i no: llegar a la tónica antes de tiempo le quita el efecto.
GRADOS_PUENTE = (4, 2, 3, 5, 6, 1)


def puente(vieja, nueva, raiz_nueva, falta):
    """Momento del acorde puente entre dos tonalidades.

    Es un acorde de la tonalidad nueva cuyas tres notas también están en la vieja:
    suena bien antes del cambio (es de la escala que todavía suena) y lleva a la
    nueva. Si no hay ninguno común, se usa su V (la dominante). `raiz_nueva` es la
    nota (MIDI) donde va el i de la tonalidad nueva; `falta`, los pasos hasta el cambio."""
    comunes = clases_de(vieja)
    tonica = nueva.nota(raiz_nueva, 0, "escala")
    raiz = None
    for grado in GRADOS_PUENTE:
        candidata = nueva.nota(tonica, grado, "escala")
        if triada(nueva, candidata) <= comunes:
            raiz = candidata
            break
    if raiz is None:
        raiz = nueva.nota(tonica, 4, "escala")
    return Momento(raiz, triada(nueva, raiz), tonica, triada(nueva, tonica), falta)
