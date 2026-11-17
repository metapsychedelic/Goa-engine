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
    print("\nTodo bien" if todo else "\nHay errores")
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
