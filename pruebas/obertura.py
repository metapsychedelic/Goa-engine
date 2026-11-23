"""Pruebas de la obertura (0.97): capas por canal, etapas, final con silencio, escenas de
la MC-101 por Program Change en el canal de control, seed y caracteres.

  python3 -m pruebas.obertura
"""

from goa.config import cargar, normalizar
from goa.motor import Motor
from goa.obertura import Obertura
from goa.escalas import Tonalidad
from pruebas.simular import RAIZ


def ok(cond, texto):
    print(("OK    " if cond else "FALLA ") + texto)
    return cond


def correr(compases=40, **ob):
    cfg = cargar(RAIZ / "config.ejemplo.toml")
    cfg["entrada"].update(canal_disparo=2, nota_maxima=0)
    for s in cfg["secuencia"]:
        s["activa"] = False
    cfg["bajo"]["activo"] = False
    cfg["pads"]["activo"] = False
    cfg["musica"].update(tonica="E", escala="menor")
    cfg["obertura"].update(dict(activo=True, salida="MC", frases=4), **ob)
    cfg = normalizar(cfg)
    out = []
    m = Motor(cfg, lambda sal, tipo, canal, a, b: out.append((sal, m.tick, tipo, canal, a, b)))
    m.start()
    m.nota_on(1, 40)
    for _ in range(compases * 96):
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

    print("\nSe guarda (como en la app)")
    import tomllib
    from goa.config import a_toml
    cfg = cargar(RAIZ / "config.ejemplo.toml")
    cfg["obertura"].update(activo=True, caracter="frigia", frases=6, escena=12, escena_vuelta=3, nota_taiko=41, seed="OB-9")
    vuelta = normalizar(tomllib.loads(a_toml(normalizar(cfg))))
    todo &= ok(all(vuelta["obertura"][k] == v for k, v in (("caracter", "frigia"), ("frases", 6), ("escena", 12),
                                                           ("escena_vuelta", 3), ("nota_taiko", 41), ("seed", "OB-9"))),
               "ningún ajuste se pierde al guardar y volver a cargar")

    print("\nTodo bien" if todo else "\nHAY FALLAS")
    return todo


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
