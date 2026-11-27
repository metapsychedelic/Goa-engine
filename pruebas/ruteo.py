"""Ruteo de la cadena: dongle o USB (goa/ruteo.py y Puertos en goa/main.py).

  python3 -m pruebas.ruteo
"""

import sys
import types
from pathlib import Path

try:
    import mido
except ImportError:   # sin mido (fuera de la Pi): lo justo para probar el ruteo
    mido = types.ModuleType("mido")

    class Message:
        def __init__(self, tipo, **kw):
            self.type = tipo
            self.__dict__.update(kw)
    mido.Message = Message
    mido.get_output_names = lambda: []
    mido.get_input_names = lambda: []
    sys.modules["mido"] = mido

from goa.config import cargar, entrada_puerto, normalizar, salidas
from goa.main import Puertos
from goa.ruteo import Ruteo, canales

RAIZ = Path(__file__).resolve().parent.parent


def ok(cond, texto):
    print(("  ok   " if cond else "  FALLA ") + texto)
    return cond


class Falso:
    def __init__(self, nombre):
        self.name, self.enviados = nombre, []

    def send(self, msg):
        self.enviados.append(msg)

    def close(self):
        pass


def cfg_con(**ruteo):
    cfg = normalizar(cargar(RAIZ / "config.ejemplo.toml"))
    cfg["entrada"]["puerto"] = "CH345"
    cfg["secuencia"][0]["salida"] = "CH345"
    cfg["ruteo"].update(ruteo)
    return normalizar(cfg)


def puertos(cfg):
    p = Puertos(salidas(cfg), Ruteo(cfg))
    for clave in p.salidas:
        p.abiertos[clave] = Falso(clave)
    return p


def main():
    todo = True
    todo &= ok(canales("3, 5") == {2, 4} and canales("x,0,17") == set(), "canales «3, 5» → 3 y 5; lo inválido se ignora")

    print("Dongle (como siempre)")
    cfg = cfg_con()
    todo &= ok("CH345" in salidas(cfg) and "MC-101" not in salidas(cfg), "abre el dongle, no la MC-101 por USB")
    todo &= ok(entrada_puerto(cfg) == "CH345", "escucha la entrada de siempre")
    p = puertos(cfg)
    p.enviar("CH345", "note_on", 0, 60, 100)
    p.enviar("CH345", "note_on", 2, 60, 100)
    todo &= ok(len(p.abiertos["CH345"].enviados) == 2, "todo sale por el dongle")

    print("USB")
    cfg = cfg_con(modo="usb", microfreak_canales="3")
    s = salidas(cfg)
    todo &= ok("CH345" not in s and "MC-101" in s and "MicroFreak" in s, f"abre la MC-101 y la MicroFreak, no el dongle ({s})")
    todo &= ok(entrada_puerto(cfg) == "Circuit Tracks", "escucha a la Circuit por USB")
    p = puertos(cfg)
    p.enviar("CH345", "note_on", 0, 60, 100)      # canal 1 → MC-101
    p.enviar("CH345", "note_on", 2, 62, 100)      # canal 3 → MicroFreak
    p.enviar("CH345", "control_change", 15, 7, 0)  # canal 16 → MC-101
    mc, mf = p.abiertos["MC-101"].enviados, p.abiertos["MicroFreak"].enviados
    todo &= ok([m.channel for m in mc] == [0, 15] and [m.channel for m in mf] == [2], "por canal: el 3 a la MicroFreak, el resto a la MC-101")
    p.abiertos["Circuit"] = Falso("Circuit")
    p.enviar("Circuit", "note_on", 9, 60, 100)
    todo &= ok(len(p.abiertos["Circuit"].enviados) == 1, "lo que no va al dongle no se toca (la Circuit sigue igual)")
    p.reenviar("CH345", mido.Message("clock"))
    p.reenviar("CH345", mido.Message("note_on", channel=2, note=50))
    todo &= ok(mc[-1].type == "clock" and mf[-1].note == 50, "reenvío: el reloj a la MC-101 y las notas por su canal")

    print("Cambiar de modo en vivo")
    p.ruteo.cambiar(cfg_con())
    p.abiertos["CH345"] = Falso("CH345")
    p.enviar("CH345", "note_on", 2, 60, 100)
    todo &= ok(len(p.abiertos["CH345"].enviados) == 1, "de vuelta a dongle, sale por el dongle")
    print("Todo bien" if todo else "HAY FALLAS")
    return todo


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
