"""Pruebas de la obertura (0.97): capas por canal, etapas, final con silencio, escenas de
la MC-101 por Program Change en el canal de control, seed y caracteres.

  python3 -m pruebas.obertura
"""

import copy

from goa.config import cargar, normalizar
from goa.motor import Motor
from goa.obertura import Obertura
from goa.escalas import Tonalidad
from pruebas.simular import RAIZ


def ok(cond, texto):
    print(("OK    " if cond else "FALLA ") + texto)
    return cond


def correr(compases=40, cambios=None, tonica="E", **ob):
    cfg = cargar(RAIZ / "config.ejemplo.toml")
    cfg["entrada"].update(canal_disparo=2, nota_maxima=0)
    for s in cfg["secuencia"]:
        s["activa"] = False
    cfg["bajo"]["activo"] = False
    cfg["pads"]["activo"] = False
    cfg["musica"].update(tonica=tonica, escala="menor")
    cfg["obertura"].update(dict(activo=True, salida="MC", frases=4), **ob)
    cfg = normalizar(cfg)
    out = []
    m = Motor(cfg, lambda sal, tipo, canal, a, b: out.append((sal, m.tick, tipo, canal, a, b)))
    m.start()
    m.nota_on(1, 40)
    for t in range(compases * 96):
        if cambios and t % 96 == 40 and t // 96 in cambios:
            nuevo = copy.deepcopy(cfg)
            nuevo["obertura"].update(cambios[t // 96])
            m.aplicar_config(normalizar(nuevo))
        m.reloj()
    m.stop()
    return [e for e in out if e[0] == "MC"], m


def main():
    todo = True
    print("Capas, largo y final")
    out, _ = correr()
    ons = [e for e in out if e[2] == "note_on"]
    offs = [e for e in out if e[2] == "note_off"]
    canales = {e[3] for e in ons}
    todo &= ok(canales == {0, 1, 2, 3}, f"suenan las cuatro capas en sus canales ({sorted(c + 1 for c in canales)})")
    ultimo = max(e[1] for e in ons)
    todo &= ok(ultimo < 32 * 96, f"dura 32 compases (última nota en el compás {ultimo // 96 + 1})")
    golpe = 31 * 96 + 48
    todo &= ok(not [e for e in ons if e[1] > golpe], "después del golpe final (tiempo 3 del último compás) no entra nada")
    todo &= ok(not [e for e in offs if e[1] > 32 * 96], "todo termina antes del drop")
    abiertas = {}
    for e in out:
        if e[2] == "note_on":
            abiertas[(e[3], e[4])] = abiertas.get((e[3], e[4]), 0) + 1
        elif e[2] == "note_off":
            abiertas[(e[3], e[4])] = abiertas.get((e[3], e[4]), 0) - 1
    todo &= ok(all(v <= 0 for v in abiertas.values()), "ninguna nota queda colgada")
    primer = {c: min(e[1] for e in ons if e[3] == c) // 96 for c in canales}
    todo &= ok(primer[2] == 0 and primer[0] >= 8 and primer[1] >= 8,
               f"crece por capas: coro desde el compás 1, cuerdas desde el {primer[0] + 1}, cuernos desde el {primer[1] + 1}")
    perc = {e[4] for e in ons if e[3] == 3}
    todo &= ok(perc <= {36, 38, 49}, f"la percusión usa sus notas (taiko, tambor, golpe: {sorted(perc)})")
    fuerza = lambda a, b: [e[5] for e in ons if a * 96 <= e[1] < b * 96]  # noqa: E731
    todo &= ok(max(fuerza(0, 8)) < max(fuerza(24, 32)), "crescendo: el final es más fuerte que el comienzo")
    cc = [e for e in out if e[2] == "control_change" and e[4] == 11]
    todo &= ok(bool(cc) and cc[0][5] < cc[-1][5], "la expresión (CC 11) sube")
    todo &= ok(not [e for e in out if e[2] == "program_change"], "sin escena no manda Program Change")

    print("\nEscenas de la MC-101")
    out, _ = correr(escena=5, escena_vuelta=2, canal_control=16)
    pcs = [e for e in out if e[2] == "program_change"]
    ons = [e for e in out if e[2] == "note_on"]
    todo &= ok(len(pcs) == 2 and all(e[3] == 15 for e in pcs), "dos cambios de escena en el canal de control (16)")
    todo &= ok(pcs[0][4] == 4 and pcs[0][1] == 48, "la escena 5 sale en la mitad del compás de preparación")
    todo &= ok(min(e[1] for e in ons) >= 96, "y la obertura empieza en el uno siguiente")
    todo &= ok(pcs[1][4] == 1 and 32 * 96 + 48 < pcs[1][1] < 33 * 96, "la vuelta (escena 2) sale en el silencio del final")
    out, _ = correr(escena=5, preparar=False)
    pcs = [e for e in out if e[2] == "program_change"]
    todo &= ok(pcs and pcs[0][1] == 0 and min(e[1] for e in out if e[2] == "note_on") < 96, "sin preparación empieza de una")

    print("\nSeed y caracteres")
    a, _ = correr(seed="A")
    b, _ = correr(seed="A")
    c, _ = correr(seed="B")
    todo &= ok(a == b, "misma seed, misma obertura")
    todo &= ok(a != c, "otra seed, otra obertura")
    ton = Tonalidad("E", "menor")
    for car in ("batalla", "frigia", "tragica"):
        ob = Obertura({"caracter": car, "seed": "X"}, ton)
        plan = ob.plan()
        todo &= ok(len(plan) == 8 and plan[0] == "i", f"{car}: {' – '.join(plan[::2])}")
    todo &= ok(all("bII" in Obertura({"caracter": "frigia", "seed": s}, ton).plan() for s in "ABCD"), "la frigia siempre pasa por el ♭II")
    trag, _ = correr(caracter="tragica")
    bat, _ = correr(caracter="batalla")
    voces = lambda out: len([e for e in out if e[2] == "note_on" and e[3] == 1 and e[1] == 16 * 96])  # noqa: E731
    todo &= ok(voces(trag) == 4 and voces(bat) == 3, f"los acordes de cuernos llevan tercera solo en la trágica ({voces(trag)} y {voces(bat)} voces)")

    print("\nCapas apagadas y largo")
    out, _ = correr(canal_coro=0)
    todo &= ok(2 not in {e[3] for e in out if e[2] == "note_on"}, "canal 0: esa capa no suena")
    out, _ = correr(frases=1, compases=12)
    todo &= ok(max(e[1] for e in out if e[2] == "note_on") < 8 * 96, "una frase: 8 compases")

    print("\nSuena una vez")
    out, _ = correr(compases=70)
    todo &= ok(max(e[1] for e in out if e[2] == "note_on") < 32 * 96, "no se repite sola")

    todo &= chill()
    todo &= cine()
    todo &= formas_y_tema()
    todo &= robustez()

    print("\nSe guarda (como en la app)")
    import tomllib
    from goa.config import a_toml
    cfg = cargar(RAIZ / "config.ejemplo.toml")
    cfg["obertura"].update(activo=True, caracter="frigia", frases=6, escena=12, escena_vuelta=3, nota_taiko=41, seed="OB-9")
    vuelta = normalizar(tomllib.loads(a_toml(normalizar(cfg))))
    todo &= ok(all(vuelta["obertura"][k] == v for k, v in (("caracter", "frigia"), ("frases", 6), ("escena", 12),
                                                           ("escena_vuelta", 3), ("nota_taiko", 41), ("seed", "OB-9"))),
               "ningún ajuste se pierde al guardar y volver a cargar")

    from goa import forma
    cfg = cargar(RAIZ / "config.ejemplo.toml")
    cfg["obertura"].update(canal_cuernos=6, nota_golpe=57, caracter="frigia")
    escena = forma.foto(normalizar(cfg))
    vieja = copy.deepcopy(escena)
    vieja["obertura"].update(canal_cuernos=2, nota_golpe=49)   # una escena guardada antes
    cfg["obertura"].update(canal_cuernos=6)
    mezcla = forma.mezclar(normalizar(cfg), {"datos": vieja})
    todo &= ok("canal_cuernos" not in escena["obertura"] and mezcla["obertura"]["canal_cuernos"] == 6
               and mezcla["obertura"]["nota_golpe"] == 57 and mezcla["obertura"]["caracter"] == "frigia",
               "los canales y notas del kit son de ruteo: una escena o parte no los pisa (el carácter sí va con ella)")
    print("\nTodo bien" if todo else "\nHAY FALLAS")
    return todo


def colgadas(out):
    abiertas = {}
    for e in out:
        if e[2] in ("note_on", "note_off"):
            abiertas[(e[3], e[4])] = abiertas.get((e[3], e[4]), 0) + (1 if e[2] == "note_on" else -1)
    return [k for k, v in abiertas.items() if v > 0]


def sanas(out):
    return all(0 <= e[4] <= 127 and 0 <= e[5] <= 127 and 0 <= e[3] <= 15 for e in out if e[2] != "pitchwheel") and \
        all(e[5] >= 1 for e in out if e[2] == "note_on")


def chill():
    todo = True
    print("\nChill")
    for car in ("etereo", "lamento", "ritual"):
        out, _ = correr(modo="chill", caracter=car, seed="CH-1")
        ons = [e for e in out if e[2] == "note_on"]
        fin = max(e[1] for e in out if e[2] == "note_off")
        todo &= ok(fin <= 31 * 96 + 72 and not colgadas(out), f"{car}: termina en el tiempo 3 del último compás y deja silencio")
        todo &= ok(1 in {e[3] for e in ons} and len([e for e in ons if e[3] == 1]) >= 20, f"{car}: hay melodía en la pista 2 ({len([e for e in ons if e[3] == 1])} notas)")
        todo &= ok(49 not in {e[4] for e in ons if e[3] == 3 and e[1] > 30 * 96}, f"{car}: sin golpe al final")
        cc = [e[5] for e in out if e[2] == "control_change" and e[4] == 11 and e[3] == 0]
        todo &= ok(max(cc) > cc[0] and cc[-1] < max(cc) / 2, f"{car}: la expresión sube y al final se apaga ({cc[0]} → {max(cc)} → {cc[-1]})")
        todo &= ok(max(e[5] for e in ons) < 110, f"{car}: suave (fuerza máxima {max(e[5] for e in ons)})")
    lam, _ = correr(modo="chill", caracter="lamento")
    todo &= ok(not [e for e in lam if e[2] == "note_on" and e[3] == 2 and e[1] < 16 * 96], "lamento: el coro llega en la segunda mitad")
    rit, _ = correr(modo="chill", caracter="ritual")
    acordes = [e for e in rit if e[2] == "note_on" and e[3] == 0 and e[1] == 0]
    todo &= ok(len(acordes) == 2, "ritual: quintas abiertas (sin tercera)")
    ete, _ = correr(modo="chill", caracter="etereo")
    todo &= ok(len([e for e in ete if e[2] == "note_on" and e[3] == 0 and e[1] == 0]) == 4, "etéreo: acorde con novena")
    a, _ = correr(modo="chill", caracter="etereo", seed="S1")
    b, _ = correr(modo="chill", caracter="etereo", seed="S2")
    mel = lambda o: [(e[1], e[4]) for e in o if e[2] == "note_on" and e[3] == 1]  # noqa: E731
    todo &= ok(mel(a) != mel(b), "otra seed, otra melodía")
    todo &= ok(correr(modo="chill", caracter="batalla")[0] == correr(modo="chill", caracter="etereo")[0],
               "un carácter que no es del modo usa el primero del modo")
    out, _ = correr(modo="chill", caracter="etereo", escena=7, escena_vuelta=3)
    pcs = [e for e in out if e[2] == "program_change"]
    todo &= ok(len(pcs) == 2 and pcs[1][4] == 2 and 32 * 96 + 48 < pcs[1][1] < 33 * 96, "chill con escenas: la vuelta sale en el silencio del final")
    return todo


def bend_al_centro(out):
    ult = {}
    for e in out:
        if e[2] == "pitchwheel":
            ult[e[3]] = e[4]
    return all(v == 0 for v in ult.values())


def cine():
    todo = True
    print("\nCine")
    for car in ("neon", "titulos", "cosmos"):
        out, _ = correr(modo="cine", caracter=car, seed="CI-1")
        ons = [e for e in out if e[2] == "note_on"]
        fin = max(e[1] for e in out if e[2] in ("note_off", "pitchwheel"))
        todo &= ok(fin <= 31 * 96 + 72 and not colgadas(out), f"{car}: termina en el tiempo 3 y deja silencio")
        todo &= ok(all(len([e for e in ons if e[3] == k]) > 10 for k in range(4)), f"{car}: suenan las cuatro pistas")
        pw = [e for e in out if e[2] == "pitchwheel"]
        todo &= ok(pw and all(e[3] == 1 for e in pw) and all(-8192 <= e[4] <= 8191 for e in pw) and bend_al_centro(out),
                   f"{car}: el lead lleva bends ({len(pw)}) y siempre vuelve al centro")
        acorde = [e for e in ons if e[3] == 0 and e[1] == 0]
        todo &= ok(len(acorde) == 4, f"{car}: acordes de cuatro notas (con color)")
    tit, _ = correr(modo="cine", caracter="titulos")
    pulso = [e for e in tit if e[2] == "note_on" and e[3] == 2 and 16 * 96 <= e[1] < 17 * 96]
    todo &= ok(len(pulso) == 16, "títulos: pulso en semicorcheas")
    neon, _ = correr(modo="cine", caracter="neon")
    cae = [e[4] for e in neon if e[2] == "pitchwheel" and e[4] < -8191 / 2 * 1.5]
    todo &= ok(bool(cae), "neón: el lead cae un tono al final de la frase")
    out, _ = correr(modo="cine", caracter="neon", bend_rango=0)
    todo &= ok(not [e for e in out if e[2] == "pitchwheel"], "rango de bend 0: sin bends")
    out, _ = correr(compases=20, cambios={13: {"activo": False}}, modo="cine", caracter="neon")
    todo &= ok(bend_al_centro(out) and not colgadas(out), "apagada a medio camino: el bend vuelve al centro")
    return todo


def formas_y_tema():
    todo = True
    print("\nFormas")
    for forma in ("golpe", "ola", "respiro"):
        out, _ = correr(forma=forma)
        ons = [e for e in out if e[2] == "note_on"]
        n = lambda a, b: len([e for e in ons if a * 96 <= e[1] < b * 96])  # noqa: E731
        todo &= ok(not colgadas(out) and max(e[1] for e in ons) < 32 * 96, f"{forma}: limpia y del mismo largo")
        if forma == "golpe":
            todo &= ok(n(0, 4) > n(4, 8), "golpe: empieza lleno y después baja")
        if forma == "ola":
            todo &= ok(n(12, 16) > 2 * n(16, 20), "ola: falso final a la mitad")
            falso = [e for e in ons if e[1] == 15 * 96 + 48 and e[3] == 3 and e[4] == 49]
            todo &= ok(bool(falso) and not [e for e in ons if 15 * 96 + 48 < e[1] < 16 * 96], "ola: golpe y silencio antes de volver")
        if forma == "respiro":
            todo &= ok(n(16, 20) < n(12, 16) and n(28, 32) > n(16, 20), "respiro: se vacía y remata")
    print("\nTema del track")
    from goa import generador
    ob = Obertura({"tema_track": True}, Tonalidad("E", "menor"))
    mot = ob.motivo_de(generador.generar("A-1", "clasico", 16, False, None))
    todo &= ok(mot and len(mot) >= 3 and max(mot) - min(mot) <= 24, f"toma el motivo de la secuencia ({mot})")
    todo &= ok(ob.motivo_de([{"suena": True, "grado": 0}] * 16) is None, "un pedal no da motivo")
    a, _ = correr(tema_track=True)
    b, _ = correr()
    llamada = lambda o: [e[4] for e in o if e[2] == "note_on" and e[3] == 1 and 8 * 96 <= e[1] < 9 * 96]  # noqa: E731
    todo &= ok(llamada(a) != llamada(b), "con tema del track la llamada cambia")
    return todo


def robustez():
    todo = True
    print("\nEn loop")
    for modo, car in (("chill", "etereo"), ("chill", "ritual"), ("epico", "batalla"), ("cine", "titulos")):
        out, m = correr(compases=8 * 4 * 3, modo=modo, caracter=car, repetir=True)
        ons = [e for e in out if e[2] == "note_on"]
        todo &= ok(max(e[1] for e in ons) >= 94 * 96 and not m.obertura.terminada, f"{modo}/{car}: sigue sonando tres vueltas después")
        todo &= ok(not [e for e in out if e[2] == "program_change"], f"{modo}/{car}: sin escena no cambia nada")
        todo &= ok(not colgadas(out), f"{modo}/{car}: al parar no queda nada colgado")
    out, _ = correr(compases=8 * 4 * 3, modo="chill", caracter="etereo", repetir=True)
    vuelta = lambda k: [(e[1] - k * 24 * 96, e[4]) for e in out if e[2] == "note_on" and e[3] == 1 and 32 * 96 + k * 24 * 96 <= e[1] < 56 * 96 + k * 24 * 96]  # noqa: E731
    todo &= ok(vuelta(0) != vuelta(1), "cada vuelta trae otra melodía")

    print("\nApagar y cambiar en vivo")
    out, _ = correr(compases=20, cambios={12: {"activo": False}}, escena=5, escena_vuelta=2)
    pcs = [e for e in out if e[2] == "program_change"]
    todo &= ok(len(pcs) == 2 and pcs[1][4] == 1, "apagada a medio camino vuelve a la escena psy")
    todo &= ok(not colgadas(out) and not [e for e in out if e[2] == "note_on" and e[1] > 13 * 96], "y se calla sin dejar notas")
    out, _ = correr(compases=36, cambios={10: {"caracter": "frigia"}, 20: {"modo": "chill", "caracter": "lamento"}})
    todo &= ok(not colgadas(out) and max(e[1] for e in out if e[2] == "note_on") > 25 * 96,
               "cambiar carácter y modo en vivo sigue sin cortar ni colgar")
    out, _ = correr(compases=36, cambios={10: {"canal_cuernos": 6}})
    todo &= ok(not colgadas(out) and 5 in {e[3] for e in out if e[2] == "note_on" and e[1] > 11 * 96},
               "cambiar un canal en vivo: lo viejo se apaga y sigue por el nuevo")

    print("\nTodas las combinaciones")
    malas = []
    cuantas = 0
    for modo, cars in (("epico", ("batalla", "frigia", "tragica")), ("chill", ("etereo", "lamento", "ritual")),
                       ("cine", ("neon", "titulos", "cosmos"))):
        for car in cars:
            for frases in (1, 2, 3, 8):
                for forma, ton in (("crece", "C"), ("golpe", "F#"), ("ola", "B"), ("respiro", "E")):
                    cuantas += 1
                    out, _ = correr(compases=8 * frases + 3, modo=modo, caracter=car, frases=frases, tonica=ton, forma=forma,
                                    tema_track=frases % 2 == 1, seed=f"{car}{frases}{ton}")
                    if colgadas(out) or not sanas(out) or not bend_al_centro(out) or \
                            max(e[1] for e in out if e[2] == "note_off") > 8 * frases * 96:
                        malas.append((modo, car, frases, forma))
    todo &= ok(not malas, f"{cuantas} oberturas (3 modos × 3 caracteres × 4 largos × 4 formas) limpias{'' if not malas else ': ' + str(malas[:4])}")
    return todo


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
