"""Dos aparatos iguales (dos dongles CH345): «CH345 #2» elige el segundo.

  python3 -m pruebas.puertos
"""

import sys
import types


def ok(cond, texto):
    print(("OK    " if cond else "ERROR ") + texto)
    return bool(cond)


def main():
    if "mido" not in sys.modules:
        try:
            import mido  # noqa: F401
        except ImportError:
            sys.modules["mido"] = types.SimpleNamespace(get_output_names=list, get_input_names=list)
    from goa.main import buscar_puerto
    from goa.web import _nombres_cortos
    n = ["Midi Through:Midi Through Port-0 14:0", "CH345:CH345 MIDI 1 20:0", "CH345:CH345 MIDI 1 24:0", "FM-1:FM-1 MIDI 1 28:0"]
    todo = True
    todo &= ok(buscar_puerto(n, "CH345") == n[1], "«CH345» sigue eligiendo el primero (como antes)")
    todo &= ok(buscar_puerto(n, "CH345 #2") == n[2] and buscar_puerto(n, "ch345#2") == n[2], "«CH345 #2» elige el segundo")
    todo &= ok(buscar_puerto(n, "CH345 #3") is None, "«CH345 #3» no existe: no se abre nada")
    todo &= ok(buscar_puerto(n, "FM-1") == n[3], "los demás, igual que siempre")
    todo &= ok(_nombres_cortos(n) == ["CH345 #1", "CH345 #2", "FM-1"], f"la app los muestra por separado ({_nombres_cortos(n)})")
    print("\nCambios de la app sin pedirle la lista de puertos al sistema")
    import goa.main as gm
    pedidas, abiertas = [], []
    class Falso:
        def __init__(self, nombre): self.name = nombre
        def close(self): pass
        def send(self, msg): pass
    gm.mido = types.SimpleNamespace(get_output_names=lambda: pedidas.append(1) or list(n), open_output=lambda nombre: abiertas.append(nombre) or Falso(nombre),
                                    Message=lambda *a, **k: (a, k))
    p = gm.Puertos(["FM-1"])
    p.revisar()
    pedidas.clear()
    p.cambiar_salidas(["FM-1"])
    p.cambiar_salidas(["FM-1", "CH345"])
    todo &= ok(not pedidas and "CH345" in p.abiertos and "FM-1" in p.abiertos,
               "cambiar de salidas usa la última lista: no frena el reloj enumerando puertos")
    p.cambiar_salidas(["FM-1"])
    todo &= ok(list(p.abiertos) == ["FM-1"], "una salida que ya nadie usa se cierra")
    p.enviar("FM-1", "note_on", 0, 60, 100)
    p.reenviar("FM-1", object())
    todo &= ok(not any(c.locked() for c in p.envios.values()) and p.envio("FM-1") is not p.envio("CH345"),
               "un candado de envío por puerto, y quedan libres")

    print("\nTodo bien" if todo else "\nHay errores")
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
