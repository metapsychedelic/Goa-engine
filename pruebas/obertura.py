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
    todo &= forma_larga()
    todo &= enlazar()
    todo &= paletas()
    todo &= esculpir()

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


def directo(ob_cfg, compases, largo_parte=None, partes=None, tonica="E"):
    """La obertura sola, con el reloj a mano; `partes`: lista de largos de partes seguidas."""
    ob = Obertura(dict({"activo": True}, **ob_cfg), Tonalidad(tonica, "menor"))
    out = []
    enviar = lambda sal, tipo, canal, a, b: out.append((sal, t, tipo, canal, a, b))  # noqa: E731
    lista = []
    for largo in partes or ([largo_parte] if largo_parte else []):
        ultima = len(lista) + largo >= sum(partes or [largo_parte])
        lista += [{"dentro": d, "largo": largo, "vuelta": 0, "sigue": not ultima} for d in range(largo)]
    for t in range(compases * 96):
        if t % 6 == 0:
            c = t // 96
            ob.paso(t // 6, t, enviar, None, lista[c] if c < len(lista) else None)
        ob.tick(t, enviar)
    ob.apagar(enviar)
    return out, ob


def forma_larga():
    todo = True
    print("\nForma larga")
    out, ob = directo({"modo": "chill", "caracter": "etereo", "largo_parte": True, "seed": "L-1"}, 128, largo_parte=128)
    ons = [e for e in out if e[2] == "note_on"]
    todo &= ok(max(e[1] for e in ons) > 120 * 96 and max(e[1] for e in out if e[2] == "note_off") <= 127 * 96 + 72,
               "largo de la parte: una parte de 128 compases es un solo arco que termina con ella")
    todo &= ok(ob.etapa(0) == 0 and ob.etapa(120) == 3 and ob.largo == 128, "el arco se estira: etapa 1 al comienzo, 4 al final")
    letras = "".join(ob.seccion(c) for c in range(0, 128, 16))
    todo &= ok(len(set(letras)) >= 2 and letras[-1] == "A", f"secciones a lo largo de la parte ({letras})")
    acordes = lambda a, b: {e[4] for e in ons if e[3] == 0 and a * 96 <= e[1] < b * 96}  # noqa: E731
    todo &= ok(any(acordes(16 * i, 16 * i + 16) != acordes(0, 16) for i in range(1, 8)), "las secciones cambian la armonía")
    sin, _ = directo({"modo": "chill", "caracter": "etereo", "largo_parte": True, "seed": "L-1", "secciones": False}, 128, largo_parte=128)
    todo &= ok(sin != out, "sin secciones es otra cosa (la misma progresión todo el rato)")
    out, ob = directo({"modo": "chill", "largo_parte": True, "escena": 9, "escena_vuelta": 2}, 70, partes=[32, 32])
    pcs = [e for e in out if e[2] == "program_change"]
    todo &= ok([e[4] for e in pcs].count(8) == 1, "dos partes seguidas con la misma escena: la cambia una sola vez")
    todo &= ok(not colgadas(out), "sin notas colgadas entre partes")
    out, _ = directo({"modo": "chill", "largo_parte": True, "repetir": True}, 66, partes=[32, 32])
    todo &= ok(len([e for e in out if e[2] == "note_on" and 31 * 96 <= e[1] < 33 * 96]) > 4, "en loop pasa de una parte a otra sin silencio")
    out, _ = directo({"modo": "cine", "caracter": "neon", "largo_parte": True}, 40)
    todo &= ok(max(e[1] for e in out if e[2] == "note_on") < 32 * 96, "sin canción usa su propio largo")
    print("\nSecciones en loop")
    out, ob = directo({"modo": "chill", "caracter": "lamento", "repetir": True, "seed": "S-3"}, 32 * 5)
    letras = "".join(ob.seccion(0, k) for k in range(5))
    todo &= ok(len(set(letras)) >= 2, f"cada vuelta es una sección ({letras})")
    print("\nOrquestación viva")
    out, ob = directo({"modo": "chill", "caracter": "etereo", "largo_parte": True, "viva": 1.0, "seed": "V-2"}, 128, largo_parte=128)
    ons = [e for e in out if e[2] == "note_on"]
    por = [{e[3] for e in ons if v * 16 * 96 <= e[1] < (v + 1) * 16 * 96} for v in range(8)]
    todo &= ok(any(len(x) < 4 for x in por[1:6]), f"capas que salen y entran ({[len(x) for x in por]} por tramo)")
    quieto, _ = directo({"modo": "chill", "caracter": "etereo", "largo_parte": True, "viva": 0.0, "seed": "V-2"}, 128, largo_parte=128)
    q = [{e[3] for e in quieto if e[2] == "note_on" and v * 16 * 96 <= e[1] < (v + 1) * 16 * 96} for v in range(8)]
    todo &= ok(all(len(x) >= 2 for x in por) and por[0] == q[0] and por[7] == q[7], "nunca menos de dos; el comienzo y el cierre completos")
    return todo


def enlazar():
    todo = True
    print("\nEnlazar partes")
    cfg = {"modo": "chill", "caracter": "etereo", "largo_parte": True, "enlazar": True, "seed": "E-1"}
    out, _ = directo(cfg, 100, partes=[32, 32, 32])
    ons = [e for e in out if e[2] == "note_on"]
    capas = lambda c: {e[3] for e in ons if c * 96 <= e[1] < (c + 1) * 96}  # noqa: E731
    sonando_al_cambio = lambda c: [e for e in out if e[2] == "note_off" and c * 96 - 24 < e[1] <= c * 96 + 2]  # noqa: E731
    todo &= ok(len(capas(32)) > len(capas(0)) and len(capas(64)) > len(capas(0)), f"la parte siguiente no vuelve a la intro ({len(capas(0))} capas al empezar, {len(capas(32))} y {len(capas(64))} al enlazar)")
    todo &= ok(all(sonando_al_cambio(c) or [e for e in ons if c * 96 - 24 <= e[1] < c * 96] for c in (32, 64)), "sin silencio entre partes")
    todo &= ok(max(e[1] for e in out if e[2] == "note_off") <= 95 * 96 + 72, "la última parte sí termina (se apaga y deja silencio)")
    todo &= ok(not colgadas(out) and bend_al_centro(out), "sin notas colgadas")
    suelto, _ = directo(dict(cfg, enlazar=False), 66, partes=[32, 32])
    todo &= ok(not [e for e in suelto if e[2] == "note_on" and 31 * 96 + 72 <= e[1] < 32 * 96] and len({e[3] for e in suelto if e[2] == "note_on" and 32 * 96 <= e[1] < 33 * 96}) <= 2,
               "sin enlazar: cada parte termina y vuelve a empezar")
    print("\nEnlazar en el modo canción del motor")
    from goa import forma as fm
    base = cargar(RAIZ / "config.ejemplo.toml")
    base["entrada"].update(canal_disparo=2, nota_maxima=0)
    for sq in base["secuencia"]:
        sq["activa"] = False
    base["bajo"]["activo"] = base["pads"]["activo"] = False
    base["obertura"].update(activo=True, salida="MC", modo="chill", caracter="etereo", largo_parte=True, enlazar=True)
    a = fm.escena_de(normalizar(base), "A")
    b2 = copy.deepcopy(base)
    b2["obertura"]["caracter"] = "lamento"
    b = fm.escena_de(normalizar(b2), "B")
    c2 = copy.deepcopy(base)
    c2["obertura"]["activo"] = False
    cc = fm.escena_de(normalizar(c2), "C")
    base["escena"] = [a, b, cc]
    base["parte"] = [dict(nombre="A", compases=32, escena=0), dict(nombre="B", compases=32, escena=1), dict(nombre="C", compases=8, escena=2)]
    base["cancion"]["activa"] = True
    cfg_m = normalizar(base)
    out = []
    m = Motor(cfg_m, lambda sal, tipo, canal, x, y: out.append((sal, m.tick, tipo, canal, x, y)))
    m.start()
    m.nota_on(1, 40)
    for _ in range(74 * 96):
        m.reloj()
    m.stop()
    out = [e for e in out if e[0] == "MC"]
    ons = [e for e in out if e[2] == "note_on"]
    todo &= ok(bool([e for e in ons if 31 * 96 + 60 <= e[1] < 32 * 96 + 12]) or bool([e for e in out if e[2] == "note_off" and 31 * 96 + 72 < e[1] <= 32 * 96 + 2]),
               "de la parte A a la B sigue sonando")
    todo &= ok(not [e for e in ons if 63 * 96 + 72 <= e[1] < 72 * 96] and bool([e for e in ons if e[1] >= 72 * 96]),
               "antes de la parte C (sin obertura) se apaga y queda callada; al volver la canción a la A, suena de nuevo")
    todo &= ok(not colgadas(out), "sin notas colgadas")
    return todo


def paletas():
    todo = True
    print("\nEspacial y fantasía")
    for modo, cars in (("espacial", ("galaxia", "interestelar", "nebulosa")), ("fantasia", ("mazmorra", "castillo", "bosque"))):
        for car in cars:
            out, _ = directo({"modo": modo, "caracter": car, "seed": "N-1"}, 34)
            ons = [e for e in out if e[2] == "note_on"]
            fin = max(e[1] for e in out if e[2] in ("note_off", "pitchwheel"))
            todo &= ok(all([e for e in ons if e[3] == k] for k in range(4)) and fin <= 31 * 96 + 72 and not colgadas(out) and bend_al_centro(out),
                       f"{car}: cuatro pistas, termina en el tiempo 3, limpia")
    gal, _ = directo({"modo": "espacial", "caracter": "galaxia"}, 34)
    todo &= ok(len([e for e in gal if e[2] == "note_on" and e[3] == 2 and 20 * 96 <= e[1] < 21 * 96]) == 16, "galaxia: secuencia en semicorcheas")
    inter, _ = directo({"modo": "espacial", "caracter": "interestelar"}, 34)
    tic = [e[1] % 96 for e in inter if e[2] == "note_on" and e[3] == 3 and e[4] == 38 and e[1] < 96]
    todo &= ok(tic == [0, 24, 48, 72], "interestelar: tic-tac en negras desde el primer compás")
    neb, _ = directo({"modo": "espacial", "caracter": "nebulosa"}, 34)
    acordes = sorted({e[1] // 96 for e in neb if e[2] == "note_on" and e[3] == 0})
    todo &= ok(all(c % 4 == 0 for c in acordes), "nebulosa: el fondo cambia cada 4 compases")
    cas, _ = directo({"modo": "fantasia", "caracter": "castillo"}, 34)
    todo &= ok(any((e[4] - 40) % 12 == 11 for e in cas if e[2] == "note_on" and e[3] in (0, 1)), "castillo: menor armónica (la sensible del V mayor)")
    maz, _ = directo({"modo": "fantasia", "caracter": "mazmorra"}, 2)
    fondo = sorted(e[4] for e in maz if e[2] == "note_on" and e[3] == 0 and e[1] == 0)
    todo &= ok(fondo and all((x - fondo[0]) % 12 in (0, 7) for x in fondo), "mazmorra: quintas paralelas (sin tercera)")
    return todo


def esculpir():
    todo = True
    print("\nRespiración por CC")
    out, _ = directo({"modo": "chill", "respira_cc": 74, "respira_compases": 8, "respira_rango": 0.4}, 34)
    cc = [e for e in out if e[2] == "control_change" and e[4] == 74]
    todo &= ok({e[3] for e in cc} == {0, 1, 2} and min(e[5] for e in cc) < 45 and max(e[5] for e in cc) > 83,
               "el CC 74 respira en las tres pistas tonales, alrededor de 64")
    todo &= ok(all(e[5] == 64 for e in cc if e[1] == cc[-1][1]), "al terminar vuelve a 64 (sin cambio)")
    print("\nPor instrumento")
    base, _ = directo({"modo": "cine", "caracter": "neon", "seed": "P-1"}, 34)
    otra, _ = directo({"modo": "cine", "caracter": "neon", "seed": "P-1", "seed_coro": "OTRA"}, 34)
    canal = lambda o, k: [e for e in o if e[3] == k and e[2] in ("note_on", "note_off")]  # noqa: E731
    todo &= ok(canal(base, 2) != canal(otra, 2) and all(canal(base, k) == canal(otra, k) for k in (0, 1, 3)),
               "seed propia: cambia solo ese instrumento")
    menos, _ = directo({"modo": "cine", "caracter": "neon", "seed": "P-1", "nivel_cuernos": 0.5}, 34)
    v = lambda o: [e[5] for e in o if e[2] == "note_on" and e[3] == 1]  # noqa: E731
    todo &= ok(all(abs(a / 2 - b) <= 1 for a, b in zip(v(base), v(menos))), "nivel: la fuerza de ese instrumento a la mitad")
    arriba, _ = directo({"modo": "chill", "seed": "P-1", "octava_coro": 1}, 34)
    normal, _ = directo({"modo": "chill", "seed": "P-1"}, 34)
    n = lambda o: [e[4] for e in o if e[2] == "note_on" and e[3] == 2]  # noqa: E731
    todo &= ok([x + 12 for x in n(normal)] == n(arriba), "octava: el coro una octava arriba")
    cuenta = lambda o, k: len([e for e in o if e[2] == "note_on" and e[3] == k])  # noqa: E731
    for capa, k, modo in (("cuernos", 1, "chill"), ("coro", 2, "cine"), ("percusion", 3, "chill"), ("cuerdas", 0, "cine")):
        poco, _ = directo({"modo": modo, "caracter": "ritual" if modo == "chill" else "cosmos", "seed": "D-1", f"densidad_{capa}": 0.0}, 34)
        mucho, _ = directo({"modo": modo, "caracter": "ritual" if modo == "chill" else "cosmos", "seed": "D-1", f"densidad_{capa}": 1.0}, 34)
        todo &= ok(cuenta(poco, k) < cuenta(mucho, k) and not colgadas(poco) and not colgadas(mucho),
                   f"densidad de {capa}: {cuenta(poco, k)} → {cuenta(mucho, k)} notas")
    print("\nAcordes")
    acorde = lambda o: sorted(e[4] for e in o if e[2] == "note_on" and e[3] == 0 and e[1] == 0)  # noqa: E731
    cinco, _ = directo({"modo": "cine", "caracter": "neon", "voces": 5}, 4)
    todo &= ok(len(acorde(cinco)) == 5, f"cinco voces ({acorde(cinco)})")
    norm, _ = directo({"modo": "cine", "caracter": "neon"}, 4)
    inv, _ = directo({"modo": "cine", "caracter": "neon", "inversion": 1}, 4)
    todo &= ok(acorde(inv)[0] == acorde(norm)[1] and len(acorde(inv)) == len(acorde(norm)), "inversión: la nota de abajo pasa arriba")
    ab, _ = directo({"modo": "cine", "caracter": "neon", "abierto": True}, 4)
    todo &= ok(max(acorde(ab)) - min(acorde(ab)) > max(acorde(norm)) - min(acorde(norm)), "abierto: más separado")
    ped, _ = directo({"modo": "chill", "pedal": True}, 4)
    todo &= ok(40 in acorde(ped), "pedal: la tónica grave abajo")
    print("\nArticulación y feel")
    cortos, _ = directo({"modo": "chill", "seed": "A-1", "legato_cuerdas": 0.5}, 4)
    largo = lambda o: [b[1] - a[1] for a in o if a[2] == "note_on" and a[3] == 0 for b in o if b[2] == "note_off" and b[3] == 0 and b[4] == a[4] and b[1] > a[1]][:1]  # noqa: E731
    todo &= ok(largo(cortos)[0] < largo(normal)[0] * 0.6, f"legato 0,5: notas más cortas ({largo(normal)[0]} → {largo(cortos)[0]} pulsos)")
    sw, _ = directo({"modo": "cine", "caracter": "neon", "swing": 0.5}, 12)
    arp = [e[1] % 24 for e in sw if e[2] == "note_on" and e[3] == 2]
    todo &= ok(16 in arp and 12 not in arp, "swing: las corcheas a contratiempo se atrasan")
    hum, _ = directo({"modo": "chill", "humanizar": 1.0}, 34)
    todo &= ok(not colgadas(hum) and len({e[5] for e in hum if e[2] == "note_on" and e[3] == 0}) > len({e[5] for e in normal if e[2] == "note_on" and e[3] == 0}),
               "humanizar: más variación de fuerza, sin notas colgadas")
    print("\nTodo mezclado")
    import random as _r
    malas = []
    for i in range(40):
        r = _r.Random(i)
        cfg = {"modo": r.choice(("epico", "chill", "cine", "espacial", "fantasia")), "seed": f"M{i}", "enlazar": r.random() < 0.5, "forma": r.choice(("crece", "golpe", "ola", "respiro")),
               "repetir": r.random() < 0.4, "frases": r.choice((1, 2, 4, 8)), "viva": r.random(), "respira_cc": r.choice((0, 74, 71)),
               "voces": r.randint(0, 5), "abierto": r.random() < 0.5, "inversion": r.randint(0, 2), "pedal": r.random() < 0.5,
               "swing": r.random() / 2, "humanizar": r.random(), "tema_track": r.random() < 0.5}
        for capa in ("cuerdas", "cuernos", "coro", "percusion"):
            cfg.update({f"densidad_{capa}": r.random(), f"nivel_{capa}": r.random() * 1.5, f"legato_{capa}": 0.2 + r.random() * 1.3})
            if capa != "percusion":
                cfg[f"octava_{capa}"] = r.randint(-2, 2)
        partes = [r.choice((16, 32, 48, 96)) for _ in range(r.randint(1, 3))] if r.random() < 0.5 else None
        if partes:
            cfg["largo_parte"] = True
        out, _ = directo(cfg, (sum(partes) if partes else 8 * cfg["frases"]) + 6, partes=partes, tonica=r.choice("CDEFGAB"))
        if colgadas(out) or not sanas(out) or not bend_al_centro(out):
            malas.append(i)
    todo &= ok(not malas, f"40 configuraciones al azar con todo movido: limpias{'' if not malas else ' ' + str(malas)}")
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
                       ("cine", ("neon", "titulos", "cosmos")), ("espacial", ("galaxia", "interestelar", "nebulosa")),
                       ("fantasia", ("mazmorra", "castillo", "bosque"))):
        for car in cars:
            for frases in (1, 2, 3, 8):
                for forma, ton in (("crece", "C"), ("golpe", "F#"), ("ola", "B"), ("respiro", "E")):
                    cuantas += 1
                    out, _ = correr(compases=8 * frases + 3, modo=modo, caracter=car, frases=frases, tonica=ton, forma=forma,
                                    tema_track=frases % 2 == 1, seed=f"{car}{frases}{ton}")
                    if colgadas(out) or not sanas(out) or not bend_al_centro(out) or \
                            max(e[1] for e in out if e[2] == "note_off") > 8 * frases * 96:
                        malas.append((modo, car, frases, forma))
    todo &= ok(not malas, f"{cuantas} oberturas (5 modos × 3 caracteres × 4 largos × 4 formas) limpias{'' if not malas else ': ' + str(malas[:4])}")
    return todo


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
