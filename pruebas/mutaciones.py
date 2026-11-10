"""Prueba las mutaciones de las secuencias y del diálogo, sin hardware.

  python3 -m pruebas.mutaciones            desde la carpeta goa-engine

Revisa que cada estilo mute en los compases que corresponde, que sin mutación
o congelada no cambie, y que mover un control en la app no borre lo mutado.
"""

import copy
import tomllib
from pathlib import Path

from goa.config import normalizar
from goa.motor import Motor

RAIZ = Path(__file__).resolve().parent.parent
with open(RAIZ / "config.ejemplo.toml", "rb") as f:
    BASE = normalizar(tomllib.load(f))


def correr(ajuste=None, dialogo=None, compases=48, tocar=None):
    """Notas por compás. `tocar`: {compás: función(cfg)} cambia la config a mitad de ese compás."""
    cfg = copy.deepcopy(BASE)
    for i, s in enumerate(cfg["secuencia"]):
        s["activa"] = i == 0 and ajuste is not None
    if ajuste is not None:
        cfg["secuencia"][0].update(ajuste)
    cfg["dialogo"].update(activo=dialogo is not None, disparo=0, **(dialogo or {}))
    porcompas = {}
    m = Motor(cfg, lambda sal, t, c, n, v: t == "note_on" and porcompas.setdefault(m.tick // 96, []).append(((m.tick % 96) // 6, n)))
    m.start()
    for tick in range(compases * 96):
        m.reloj()
        paso, r = divmod(tick, 6)
        if r == 1 and paso % 16 == 0:
            m.nota_on(cfg["entrada"]["canal_disparo"] - 1, 41)
        if tocar and tick % 96 == 40 and tick // 96 in tocar:
            tocar[tick // 96](cfg)
            m.aplicar_config(copy.deepcopy(cfg))  # como cuando mueves un control en la app
    m.stop()
    return [tuple(porcompas.get(c, [])) for c in range(compases)]


def cambios(compases):
    return [c for c in range(1, len(compases)) if compases[c] != compases[c - 1]]


def ok(condicion, texto):
    print(("OK    " if condicion else "ERROR ") + texto)
    return condicion


if __name__ == "__main__":
    todo = True
    for estilo in ("rolling", "galope", "arpegio3", "acido"):
        fijo = correr({"estilo": estilo, "mutacion": 0.0})
        muta = correr({"estilo": estilo, "mutacion": 0.8, "mutar_cada": 2})
        congelado = correr({"estilo": estilo, "mutacion": 0.8, "mutar_cada": 2, "bloqueada": True})
        todo &= ok(not cambios(fijo) and not cambios(congelado)
                   and cambios(muta) and all(c % 2 == 0 for c in cambios(muta)),
                   f"{estilo}: sin mutación y congelada no cambia; con mutación cambia cada 2 compases")

    def mover_otro_control(cfg):
        cfg["secuencia"][0]["velocidad"] = 90       # un control que no cambia el patrón
        cfg["pads"]["velocidad"] = 70
    ajuste = {"mutacion": 0.8, "mutar_cada": 2}
    sin = correr(ajuste)
    con = correr(ajuste, tocar={9: mover_otro_control, 21: mover_otro_control})
    todo &= ok([[n for _, n in c] for c in sin] == [[n for _, n in c] for c in con],
               "mover un control en la app no borra lo que la secuencia ya mutó")

    def otra_variante(cfg):
        cfg["secuencia"][0]["seed"] = "OTRA-0001"
    todo &= ok(correr(ajuste, tocar={9: otra_variante})[12] != sin[12], "cambiar la variante sí cambia el patrón")

    print()
    dlg = {"evolucion": 1.0, "mutar_cada": 2}
    d_sin = correr(dialogo=dlg)
    def oscuridad_respuesta(cfg):
        cfg["respuesta"]["velocidad"] = 80
    d_con = correr(dialogo=dlg, tocar={9: oscuridad_respuesta})
    todo &= ok(all(d_con[c] for c in range(1, 48)), "el diálogo no se calla al mover uno de sus controles")
    todo &= ok([[n for _, n in c] for c in d_sin] == [[n for _, n in c] for c in d_con],
               "y sigue con lo que ya había mutado")
    def mas_golpes(cfg):
        cfg["llamada"]["golpes"] = 5
        cfg["dialogo"]["espacio"] = 0  # que la respuesta no pierda lugares: se cuentan las notas
    d_golpes = correr(dialogo=dlg, tocar={9: mas_golpes})
    todo &= ok(len(d_golpes[10]) > len(d_sin[10]), "más golpes en la llamada se escuchan desde el compás siguiente")

    print("\nTodo bien" if todo else "\nHay errores")
    raise SystemExit(0 if todo else 1)
