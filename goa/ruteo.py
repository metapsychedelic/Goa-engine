"""Ruteo de la cadena MIDI: por el dongle o por USB.

Los motores siguen apuntando a la salida que tengan (por ejemplo «CH345», el dongle). Con
`[ruteo] modo = "usb"`, lo que va al dongle se reparte por canal: los canales de la
MicroFreak (`microfreak_canales`) a su puerto USB y todo lo demás a la MC-101 por USB. El
reloj y el Start/Stop del reenvío (thru) van a la MC-101. Con «dongle», nada cambia.
"""


def canales(texto):
    """«3» o «3, 5» → {2} o {2, 4} (canales MIDI 0-15)."""
    hallados = set()
    for parte in str(texto or "").replace(";", ",").split(","):
        parte = parte.strip()
        if parte.isdigit() and 1 <= int(parte) <= 16:
            hallados.add(int(parte) - 1)
    return hallados


class Ruteo:
    def __init__(self, cfg=None):
        self.cambiar(cfg or {})

    def cambiar(self, cfg):
        r = cfg.get("ruteo") or {}
        self.usb = r.get("modo") == "usb"
        self.dongle = r.get("dongle", "CH345")
        self.mc101 = r.get("mc101", "MC-101")
        self.microfreak = r.get("microfreak", "MicroFreak")
        self.canales_mf = canales(r.get("microfreak_canales", "3"))

    def destino(self, clave, canal):
        """La salida real de un mensaje con canal."""
        if self.usb and clave == self.dongle:
            return self.microfreak if canal in self.canales_mf else self.mc101
        return clave

    def destino_sin_canal(self, clave):
        """Reloj, Start/Stop: por USB, a la MC-101 (la MicroFreak sigue su propio ajuste)."""
        if self.usb and clave == self.dongle:
            return self.mc101
        return clave


def salidas_ruteadas(cfg, claves):
    r = Ruteo(cfg)
    if not r.usb or r.dongle not in claves:
        return claves
    return [c for c in claves if c != r.dongle] + [r.mc101, r.microfreak]
