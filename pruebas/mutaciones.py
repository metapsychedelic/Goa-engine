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

    print("\nMolde de las secuencias: un filtro de notas (opcional)")
    from .armonia import armar as armar_arm, de_secuencia
    from .dialogo import correr as correr_d
    def pasos(molde, densidad=0.4, compases=8, filtro=True, seed=None):
        cfg = armar_arm(modo="libre")
        cfg["secuencia"][0].update(densidad=densidad, posicion="todos", molde=molde, filtro=filtro)
        if seed:
            cfg["secuencia"][0]["seed"] = seed
        cfg = normalizar(cfg)
        sal = de_secuencia(correr_d(cfg, compases=compases)[0], cfg)
        return sal, [{(t // 6) % 16 for t, _ in sal if (t // 6) // 16 == c} for c in range(1, compases)]
    base_, base_pasos = pasos("", filtro=False)
    todo &= ok(pasos("x-x-x-x-x-x-x-x-", filtro=False)[0] == base_, "filtro apagado: suena igual que siempre, aunque haya molde")
    todo &= ok(not pasos("")[0], "filtro prendido y vacío: no suena nada (se van abriendo pasos)")
    todo &= ok(pasos("x" * 16)[0] == base_, "todo abierto: suena igual que sin filtro")
    _, mitad = pasos("--------xxxxxxxx")
    todo &= ok(any(mitad) and all(m == {p for p in b if p >= 8} for m, b in zip(mitad, base_pasos)),
               "abierta la segunda mitad: suenan justo las notas de la seed que caen ahí")
    _, a = pasos("x.x.x.x.x.x.x.x.".replace(".", "-"), seed="ZZ-1")
    _, b = pasos("x.x.x.x.x.x.x.x.".replace(".", "-"), seed="QQ-7")
    todo &= ok(a != b, "con el filtro puesto, otra seed suena distinto")

    print("\nPasos «a veces» y orden de los pasos")
    def con(densidad=1.0, compases=16, **extra):
        cfg = armar_arm(modo="libre")
        cfg["secuencia"][0].update(densidad=densidad, posicion="todos", **extra)
        cfg = normalizar(cfg)
        return de_secuencia(correr_d(cfg, compases=compases)[0], cfg)
    todos = con()
    paso_ = next(p for p in range(16) if all(any((t // 6) == c * 16 + p for t, _ in todos) for c in range(1, 16)))
    q = "-" * paso_ + "?" + "-" * (15 - paso_)
    sal = con(filtro=True, molde=q, molde_prob=0.5)
    uno = [any((t // 6) == c * 16 + paso_ for t, _ in sal) for c in range(1, 16)]
    todo &= ok(0 < sum(uno) < len(uno), f"un ? al 50 %: deja pasar la nota en unos compases y en otros no ({sum(uno)} de {len(uno)})")
    todo &= ok(con(filtro=True, molde=q, molde_prob=0.5) == sal, "y es repetible: misma seed, mismo resultado")
    todo &= ok(not con(filtro=True, molde=q, molde_prob=0.0), "al 0 % nunca pasa")
    from goa import generador as gen
    todo &= ok([gen.recorrer("atras", k, 4, "s") for k in range(4)] == [3, 2, 1, 0]
               and [gen.recorrer("pendulo", k, 4, "s") for k in range(8)] == [0, 1, 2, 3, 2, 1, 0, 1]
               and sorted(gen.recorrer("azar", k, 16, "s") for k in range(16)) == list(range(16))
               and [gen.recorrer("azar", k, 16, "s") for k in range(16)] != [gen.recorrer("azar", k, 16, "s") for k in range(16, 32)],
               "orden: atrás, péndulo y al azar (cada vuelta en otro orden, sin repetir pasos)")
    adelante, atras = con(), con(recorrido="atras")
    todo &= ok(sorted(n for _, n in adelante[:16]) == sorted(n for _, n in atras[:16]) and adelante[:16] != atras[:16],
               "al revés: las mismas notas en otro orden")

    print("\nEl molde muta solo (opcional) y 🎲 Goa / Psy")
    import random as _r
    rng = _r.Random(3)
    goa_m = [gen.molde_al_azar(rng, "goa") for _ in range(200)]
    psy_m = [gen.molde_al_azar(rng, "psy") for _ in range(200)]
    en_tiempos = lambda ms: sum(m[i] == "x" for m in ms for i in (0, 4, 8, 12)) / len(ms)  # noqa: E731
    en_contras = lambda ms: sum(m[i] == "x" for m in ms for i in (2, 6, 10, 14)) / len(ms)  # noqa: E731
    todo &= ok(all("x" in m for m in goa_m + psy_m) and en_tiempos(goa_m) > en_tiempos(psy_m) and en_contras(psy_m) > en_contras(goa_m),
               f"goa llena los tiempos ({en_tiempos(goa_m):.1f} de 4); psy los deja al bombo y vive en los contratiempos ({en_contras(psy_m):.1f} de 4)")
    from goa.motor import Motor
    def moldes(muta, compases=33, molde="x---x---x---x---"):
        cfg = armar_arm(modo="libre")
        cfg["secuencia"][0].update(filtro=True, molde=molde, molde_muta=muta, mutar_cada=4, mutacion=0.0)
        m = Motor(normalizar(cfg), lambda *a: None)
        vistos = []
        for c in range(1, compases):
            m.secuencias[0].evolucionar(c)
            vistos.append(m.secuencias[0].molde_vivo)
        return vistos
    quieto, vivo = moldes(0.0), moldes(1.0)
    cambios = sum(1 for a, b in zip(vivo, vivo[1:]) if a != b)
    todo &= ok(len(set(quieto)) == 1 and quieto[0] == "x---x---x---x---", "en 0 el molde no se mueve")
    from goa import generador as gen
    pat = [{"suena": True, "grado": 0} for _ in range(16)]
    oidos = [any(gen.mutar(pat, f"S{k}", 4, 0.01, 0.5, audibles={2, 6})[i]["grado"] != 0 for i in (2, 6)) for k in range(20)]
    todo &= ok(all(oidos), "con el filtro puesto, el cambio garantizado de la mutación cae en un paso que se oye")
    original = "x---x---x---x---"
    todo &= ok(cambios >= 5 and all(sum(x != y for x, y in zip(m_, original)) <= 2 for m_ in vivo)
               and all(m_[k] == original[k] for m_ in vivo for k in (0, 4, 8, 12)) and all("x" in m_ for m_ in vivo),
               f"al máximo se aleja 1 o 2 pasos de lo que pintaste y vuelve; los pasos del bombo nunca cambian ({cambios} cambios en 32)")
    todo &= ok(moldes(1.0) == vivo, "es repetible: misma seed, mismo camino")
    vacio = moldes(0.5, molde="")
    todo &= ok(any("x" in m or "?" in m for m in vacio), "desde un filtro cerrado también empieza a abrir pasos")

    print("\nTodo bien" if todo else "\nHay errores")
    raise SystemExit(0 if todo else 1)
