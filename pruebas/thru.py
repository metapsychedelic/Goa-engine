"""Prueba el modo dongle de goa.main con un mido falso.

  python3 -m pruebas.thru     desde la carpeta goa-engine
"""

import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "falso_mido"))
import mido  # noqa: E402  (el falso)

from goa.config import guardar, cargar  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


def main():
    cfg = cargar(RAIZ / "config.ejemplo.toml")
    cfg["app"]["puerto"] = 8091
    cfg["entrada"]["puerto"] = "USB MIDI"
    cfg["thru"]["activo"] = True
    cfg["thru"]["salida"] = "USB MIDI"
    cfg["secuencia"][0]["salida"] = "USB MIDI"
    ruta = Path(tempfile.mkdtemp()) / "config.toml"
    guardar(ruta, cfg)

    sys.argv = ["goa", "--config", str(ruta)]
    from goa import main as programa
    programa.signal.signal = lambda *a: None  # en un hilo no se pueden registrar señales
    threading.Thread(target=programa.main, daemon=True).start()
    for _ in range(50):
        if mido.CALLBACKS:
            break
        time.sleep(0.1)
    cb = mido.CALLBACKS[0]

    M = mido.Message
    cb(M("start"))
    cb(M("note_on", channel=0, note=60, velocity=100))   # nota de la Circuit para la MicroFreak
    cb(M("note_on", channel=1, note=41, velocity=100))   # nota larga, canal 2
    for _ in range(16 * 6):
        cb(M("clock"))
    cb(M("note_off", channel=0, note=60, velocity=0))

    reenviados = [m for m in mido.ENVIADOS if m.type in ("start", "clock") or getattr(m, "channel", None) == 0]
    disparo = [m for m in mido.ENVIADOS if getattr(m, "channel", None) == 1]
    goa = [m for m in mido.ENVIADOS if m.type == "note_on" and m.channel == 3]
    relojes = sum(1 for m in mido.ENVIADOS if m.type == "clock")
    print(f"reenviados de la Circuit: {len(reenviados)} (relojes {relojes} de 96)")
    print(f"notas Goa en canal 4: {len(goa)} · primeras: {[m.note for m in goa[:6]]}")
    print(f"mensajes del canal de disparo reenviados: {len(disparo)} (debe ser 0)")
    ok = relojes == 96 and any(m.type == "start" for m in mido.ENVIADOS) and len(goa) > 0 and not disparo
    print("OK" if ok else "ERROR")


if __name__ == "__main__":
    main()
