"""Rises y fills: transiciones con nombre que eligen las partes (config.TRANSICIONES).

  python3 -m pruebas.transiciones
"""

import json
import tomllib
from pathlib import Path

from goa.config import a_toml, cargar, normalizar
from goa.motor import Motor

RAIZ = Path(__file__).resolve().parent.parent


def ok(cond, texto):
    print(("  ok   " if cond else "  FALLA ") + texto)
    return cond


def base(partes, **listas):
    cfg = normalizar(cargar(RAIZ / "config.ejemplo.toml"))
    for k in ("rise", "fill", "break"):
        cfg.pop(k, None)
    cfg["parte"] = partes
    cfg.update(listas)
    return cfg


def sonido(cfg, compases=40):
    ev = []
    m = Motor(normalizar(cfg), lambda *a: ev.append(a))
    m.start()
    m.nota_on(1, 41)
    for _ in range(compases * 96):
        m.reloj()
    return ev


def main():
    todo = True
    print("Partes de antes")
    vieja = [dict(nombre="Intro", compases=8, roll=True), dict(nombre="Build", compases=8, riser=True, pads_suben=True),
             dict(nombre="Drop", compases=8, hueco=True, corte_bajo=True), dict(nombre="Build 2", compases=8, riser=True, pads_suben=True),
             dict(nombre="Fin", compases=8)]
    n = normalizar(base(vieja))
    finales = [(p["final"], p["final_rise"], p["final_fill"], p["final_break"]) for p in n["parte"]]
    todo &= ok(finales == [("fill", "", "Fill 1", ""), ("rise", "Subida 1", "", ""), ("break", "", "", "Break 1"),
                           ("rise", "Subida 1", "", ""), ("nada", "", "", "")], f"cada parte elige su final {finales}")
    todo &= ok(len(n["rise"]) == 1, "dos subidas iguales comparten la misma transición")
    todo &= ok(n["parte"][1]["riser"] and n["parte"][1]["pads_suben"] and n["parte"][2]["hueco"], "los apoyos quedan en la parte")
    cfg_vieja = base(json.loads(json.dumps(vieja)))
    todo &= ok(sonido(cfg_vieja) == sonido(n), "suena exactamente igual que antes")

    print("Editar una transición")
    n["rise"][0]["pads_suben"] = False
    m = normalizar(n)
    todo &= ok(not m["parte"][1]["pads_suben"] and not m["parte"][3]["pads_suben"], "el cambio llega a todas las partes que la usan")
    m["rise"][0]["nombre"] = "Otra"   # la parte apunta a un nombre que ya no está
    m2 = normalizar(m)
    todo &= ok(not m2["parte"][1]["riser"] and m2["parte"][1]["final"] == "rise", "si la transición ya no existe, la parte queda sin apoyos")
    m2["parte"][0].update(final="nada")
    m3 = normalizar(m2)
    todo &= ok(not m3["parte"][0]["roll"], "elegir «nada» quita el fill")
    m3["parte"][4].update(final="fill_break", final_fill="Fill 1", final_break="Break 1")
    m4 = normalizar(m3)
    p = m4["parte"][4]
    todo &= ok(p["roll"] and p["hueco"] and p["corte_bajo"], "fill + break suma los dos")

    print("Guardar y cargar")
    vuelta = normalizar(tomllib.loads(a_toml(m4)))
    todo &= ok(vuelta == m4, "el TOML guarda las transiciones y queda igual al volver a cargar")
    todo &= ok(normalizar(m4) == m4, "normalizar dos veces no cambia nada")

    print("\nTodo bien" if todo else "\nHAY FALLAS")
    return 0 if todo else 1


if __name__ == "__main__":
    raise SystemExit(main())
