"""mido falso para probar goa.main sin hardware: un dongle con entrada y salida."""

ENTRADAS = ["USB MIDI Interface:USB MIDI Interface MIDI 1 24:0"]
SALIDAS = ["USB MIDI Interface:USB MIDI Interface MIDI 1 24:0"]
ENVIADOS = []
CALLBACKS = []


class Message:
    def __init__(self, type, **kw):
        self.type = type
        self.__dict__.update(kw)

    def __repr__(self):
        datos = " ".join(f"{k}={v}" for k, v in self.__dict__.items() if k != "type")
        return f"<{self.type} {datos}>"


class _Puerto:
    def __init__(self, name):
        self.name = name

    def send(self, msg):
        ENVIADOS.append(msg)

    def close(self):
        pass


def get_input_names():
    return list(ENTRADAS)


def get_output_names():
    return list(SALIDAS)


def open_output(name):
    return _Puerto(name)


def open_input(name, callback=None):
    CALLBACKS.append(callback)
    return _Puerto(name)
