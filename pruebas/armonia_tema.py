"""Armonía del tema: la base que siguen las partes sin armonía propia.

  python3 -m pruebas.armonia_tema
"""

import copy
import json
import tomllib
from pathlib import Path

from goa import forma
from goa.config import normalizar

from .fabrica import ok

RAIZ = Path(__file__).resolve().parent.parent


def base():
    with open(RAIZ / "config.ejemplo.toml", "rb") as f:
        return tomllib.load(f)


def escena(cfg, nombre, tonica, escala="frigio"):
    c = normalizar(copy.deepcopy(cfg))
    c["musica"].update(tonica=tonica, escala=escala)
    e = forma.escena_de({k: v for k, v in c.items() if k != "armonia_tema"}, nombre)
    del e["armonia_propia"]   # como las escenas de antes
    return e


def main():
    todo = True
    print("Tema de antes (sin armonía del tema)")
    raw = base()
    raw["escena"] = [escena(raw, "Intro", "F"), escena(raw, "Drop", "F"), escena(raw, "Break", "G", "menor")]
    raw["parte"] = [{"nombre": n, "escena": i, "compases": 16} for i, n in enumerate(("Intro", "Drop", "Break"))] + [{"nombre": "Drop 2", "escena": 1, "compases": 16}]
    antes = {i: json.loads(e["datos"])["musica"] for i, e in enumerate(raw["escena"])}
    cfg = normalizar(raw)
    todo &= ok(cfg["armonia_tema"]["tonica"] == "F" and cfg["armonia_tema"]["escala"] == "frigio", "la base es la que más se repite (Fa frigio)")
    todo &= ok([e["armonia_propia"] for e in cfg["escena"]] == [False, False, True], "Intro y Drop la siguen; Break (Sol menor) queda con la suya")
    suena = [normalizar(forma.mezclar(cfg, e))["musica"] for e in cfg["escena"]]
    todo &= ok(all({k: suena[i][k] for k in antes[i]} == antes[i] for i in antes), "cada parte suena con la misma armonía que antes")
    todo &= ok(normalizar(json.loads(json.dumps(cfg)))["escena"] == cfg["escena"], "guardado y abierto de nuevo, no se vuelve a migrar")

    print("\nCambiar la base")
    cfg["armonia_tema"].update(tonica="E", tension=0.7)
    suena = [normalizar(forma.mezclar(cfg, e))["musica"] for e in cfg["escena"]]
    todo &= ok(suena[0]["tonica"] == "E" and suena[1]["tonica"] == "E" and suena[1]["tension"] == 0.7, "las que siguen el tema pasan a Mi")
    todo &= ok(suena[2]["tonica"] == "G" and suena[2]["escala"] == "menor", "Break, con armonía propia, no se mueve")

    print("\nEscenas nuevas y guardar encima")
    vivo = normalizar(forma.mezclar(cfg, cfg["escena"][0]))
    todo &= ok(forma.escena_de(vivo, "x")["armonia_propia"] is False, "con la armonía del tema suenando, la escena nueva la sigue")
    otra = dict(vivo, musica=dict(vivo["musica"], tonica="A"))
    todo &= ok(forma.escena_de(otra, "x")["armonia_propia"] is True, "con otra tonalidad, queda propia")
    todo &= ok(forma.escena_de(vivo, "x", cfg["escena"][2])["armonia_propia"] is True, "guardar encima de una propia la deja propia")
    todo &= ok(forma.escena_de(otra, "x", cfg["escena"][0])["armonia_propia"] is True, "guardar otra tonalidad encima de una que seguía el tema la vuelve propia")

    print("\nTema nuevo")
    nuevo = normalizar(base())
    todo &= ok(nuevo["armonia_tema"] == nuevo["musica"], "sin partes, la base es la armonía que suena")

    print("\n" + ("Todo bien" if todo else "HAY FALLAS"))
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
