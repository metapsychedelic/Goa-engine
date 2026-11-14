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
    cfg["forma"]["variacion"] = 0.0  # sin director: acá se mide solo la mutación
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

    from goa import generador
    pegados = []
    for estilo in generador.ESTILOS:
        for pedal in (0.0, 0.5, 0.8, 0.95):
            for seed in ("A1", "B2", "C3"):
                patron = generador.generar(seed, estilo, 16, pedal)
                if not any(p["suena"] for p in patron):
                    continue
                for compas in range(4, 64, 4):
                    nuevo = generador.mutar(patron, seed, compas, 0.2, pedal)
                    if [p["grado"] for p in nuevo] == [p["grado"] for p in patron]:
                        pegados.append((estilo, pedal, seed, compas))
                    patron = nuevo
    todo &= ok(not pegados, "cada mutación cambia al menos una nota, en todos los estilos, aunque el pedal sea alto"
               + (f" (pegados: {pegados[:3]})" if pegados else ""))

    print("\nMutación de ritmo")
    ritmo = lambda pat: [bool(p["suena"]) for p in pat]  # noqa: E731
    fuera, lejos, cambia, quieto = 0, 0, 0, 0
    for estilo in generador.ESTILOS:
        for posicion in generador.POSICIONES:
            for largo in (16, 13, 7):
                p = generador.generar("R1", estilo, largo, 0.5)
                base = ritmo(p)
                validos = lambda pat: [i for i, x in enumerate(pat) if x["suena"]  # noqa: E731
                                       and (largo % 4 or generador.pasa_posicion(posicion, i))]
                n0 = max(1, len(validos(p)))
                quieto += ritmo(generador.mutar(p, "R1", 4, 0.5, 0.5)) != base  # sin ritmo, el ritmo no se toca
                for compas in range(4, 200, 4):
                    q = generador.mutar_ritmo(p, "R1", compas, 0.7, posicion, base)
                    cambia += ritmo(q) != ritmo(p)
                    if largo % 4 == 0:
                        fuera += sum(1 for i, x in enumerate(q) if x["suena"] and not base[i]
                                     and not generador.pasa_posicion(posicion, i))
                    n = len(validos(q))
                    lejos += n0 > 1 and not (n0 * 0.5 - 1 <= n <= n0 * 1.5 + 1)
                    p = q
    todo &= ok(quieto == 0, "con la mutación de ritmo apagada, el ritmo no cambia (como antes)")
    todo &= ok(cambia > 1000, f"con la mutación de ritmo, el ritmo cambia ({cambia} veces)")
    todo &= ok(fuera == 0, "nunca agrega ni mueve una nota a un lugar donde no suena (el offbeat no pasa al bombo)")
    todo &= ok(lejos == 0, "la cantidad de notas se queda entre la mitad y una vez y media de la original")

    cfg = copy.deepcopy(BASE)
    for sec in cfg["secuencia"]:
        sec.update(activa=True, mutacion=0.3, mutacion_ritmo=0.6, mutar_cada=2)
    def ritmos(variacion, congelar=False):
        c = copy.deepcopy(cfg)
        c["forma"].update(variacion=variacion, periodo=8)
        for sec in c["secuencia"]:
            sec["bloqueada"] = congelar
        m = Motor(normalizar(c), lambda *a: None)
        m.start()
        vistos = []
        for tick in range(48 * 96):
            m.reloj()
            if tick % 96 == 1:
                m.nota_on(m.canal_disparo, 41)
            if tick % 96 == 50:
                g = getattr(m.secuencias[0], "_director_patron", None)
                vistos.append(ritmo(g[1] if g is not None else m.secuencias[0].patron))
        return vistos
    r = ritmos(0.0)
    todo &= ok(len({tuple(x) for x in r}) > 5, "en el motor, el ritmo de la secuencia evoluciona")
    todo &= ok(r == ritmos(1.0), "y evoluciona igual con la variación larga andando")
    todo &= ok(len({tuple(x) for x in ritmos(0.0, congelar=True)}) == 1, "congelada, el ritmo no cambia")

    print("\nTodo bien" if todo else "\nHay errores")
    raise SystemExit(0 if todo else 1)
