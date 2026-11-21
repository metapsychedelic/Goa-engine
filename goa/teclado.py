"""El teclado de la MicroFreak, conectado por USB a la Pi.

Con Local Off la MicroFreak no se toca a sí misma: ni sus teclas ni sus perillas le
cambian el sonido (el pad que le manda la Circuit sigue igual). Las teclas quedan para
el motor (goa/tocado.py), y las perillas vuelven a funcionar porque el motor le devuelve sus CC (y la
cinta de pitch bend) por USB, en el canal en que suena.

En la MicroFreak (Utility › MIDI): Local Off, Output = USB, Output chan = el `canal`
de acá (10), Knob send CCs = On. El canal de salida tiene que ser distinto del canal en
que suena: así lo que el motor le devuelve no vuelve a entrar como si fueran perillas.

Todo esto corre en el callback de mido, sin esperar el reloj: devolver una perilla es
un mensaje, y la MicroFreak tiene que responder al instante.
"""

import logging

log = logging.getLogger("goa.teclado")


class Teclado:
    def __init__(self, ctx):
        self.ctx = ctx
        self.conectado = None
        self.ultimo = None
        self.notas = set()   # teclas apretadas ahora (para la app y para tocar después)

    def recibir(self, msg):
        cfg = self.ctx.config["teclado"]
        if getattr(msg, "channel", None) != cfg["canal"] - 1:
            return
        if msg.type in ("control_change", "pitchwheel"):
            if cfg["perillas"]:
                self._devolver(cfg, msg)
            return
        if msg.type == "note_on" and msg.velocity > 0:
            self.notas.add(msg.note)
            self.ultimo = f"nota {msg.note} ({msg.velocity})"
            with self.ctx.candado:
                self.ctx.motor.tocado_on(msg.note, msg.velocity)   # al instante, sin esperar el reloj
        elif msg.type in ("note_on", "note_off"):
            self.notas.discard(msg.note)
            with self.ctx.candado:
                self.ctx.motor.tocado_off(msg.note)

    def _devolver(self, cfg, msg):
        canal = cfg["canal_sinte"] - 1
        with self.ctx.candado:
            if msg.type == "control_change":
                self.ctx.puertos.enviar(cfg["puerto"], "control_change", canal, msg.control, msg.value)
            else:
                self.ctx.puertos.enviar(cfg["puerto"], "pitchwheel", canal, msg.pitch, 0)

    def estado(self):
        return {"conectado": self.conectado, "ultimo": self.ultimo, "apretadas": len(self.notas)}
