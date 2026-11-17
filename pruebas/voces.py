"""Pruebas de «Con la otra voz» (0.54): corrimiento, complementar y separar entre
dos secuencias que suenan juntas.

  python3 -m pruebas.voces
"""

import sys

from goa.config import normalizar
from pruebas.escuchar_clasico import eventos

CHOCAN = {1, 2, 6, 10, 11}
LEAD = dict(estilo="psytrance", figura="riff", seed="P1", huecos=0.5, frase=4, octava=1, gate=0.5)
SEC = dict(estilo="psytrance", figura="pulsos", seed="P3", huecos=0.2, frase=4, octava=0, gate=0.5)


def ok(cond, texto):
    print(("OK    " if cond else "FALLA ") + texto)
    return cond


def notas(evs, salida):
    abiertas, res = {}, []
    for sal, t, tipo, n, _ in evs:
        if sal != salida:
            continue
        if tipo == "note_on":
            abiertas[n] = t
        elif tipo == "note_off" and n in abiertas:
            res.append((abiertas.pop(n), t, n))
    return res


def correr(extra=None, lead=None, sec=None, compases=8):
    return eventos(41, "frigio", lead or LEAD, None, compases, "psytrance", {}, None, dict(sec or SEC, **(extra or {})))


def choques(evs):
    """Ticks en que la segunda voz suena encima del lead a distancia de segunda, séptima
    o tritono (a menos de una octava) o en la misma nota."""
    total = 0
    for a, b, n in notas(evs, "SEC"):
        for c, d, m in notas(evs, "LEAD"):
            if min(b, d) > max(a, c) and (n == m or (abs(n - m) < 12 and abs(n - m) % 12 in CHOCAN)):
                total += min(b, d) - max(a, c)
    return total


def ataques(evs, salida):
    return sorted({a for a, _, _ in notas(evs, salida)})


def main():
    bien = True
    base = correr()
    bien &= ok(correr({"corrimiento": 0, "complementar": 0.0, "separar": False}) == base,
               "con los tres controles en cero suena exactamente igual que antes")
    bien &= ok(notas(base, "LEAD") == notas(correr({"corrimiento": 3, "complementar": 1.0, "separar": True}), "LEAD"),
               "la voz de referencia (el lead) no cambia")

    sin = ataques(base, "SEC")
    for k in (1, 2, 5):
        corrida = ataques(correr({"corrimiento": k}), "SEC")
        largo = 4 * 16 * 6   # la frase de 4 compases
        bien &= ok({(t - 6 * k) % largo for t in corrida if t >= 6 * k} <= {t % largo for t in sin},
                   f"corrimiento {k}: el mismo patrón, {k} semicorchea(s) más tarde")

    lead = set(ataques(base, "LEAD"))
    hocket = ataques(correr({"complementar": 1.0}), "SEC")
    bien &= ok(not lead & set(hocket), f"complementar 100 %: nunca ataca junto al lead ({len(hocket)} notas)")
    medio = ataques(correr({"complementar": 0.5}), "SEC")
    bien &= ok(len(hocket) <= len(medio) <= len(sin), "complementar: cuanto más alto, menos notas")

    bien &= ok(choques(base) > 0, f"sin separar hay choques ({choques(base)} ticks)")
    for nombre, lead_, sec_ in (
            ("riff + pulsos", LEAD, SEC),
            ("pedal Goa + espacio", dict(LEAD, estilo="clasico", figura="pedal", seed="PEDAL-1"),
             dict(SEC, figura="espacio", seed="M1", huecos=0.4)),
            ("melodía + acordes Goa", dict(LEAD, figura="melodia", seed="Q2", huecos=0.1),
             dict(SEC, estilo="clasico", figura="acordes", seed="E2"))):
        evs = correr({"separar": True}, lead_, sec_)
        bien &= ok(choques(evs) == 0, f"separar ({nombre}): ninguna segunda, séptima ni tritono contra el lead")
        escala = {0, 1, 3, 5, 7, 8, 10}
        bien &= ok(all((n - 41) % 12 in escala for _, _, n in notas(evs, "SEC")), f"separar ({nombre}): todo dentro de la escala")

    # La ♭9 lejana (raíz abajo, ♭2 del lead arriba) no se toca: es la tensión del frigio.
    lead85 = dict(LEAD, estilo="clasico", figura="ciclo", ciclo=5, registro=2, seed="C5-9", raga="hijaz", ornamentos=0.5)
    sec85 = dict(SEC, figura="tresillo", seed="T1", huecos=0.3, corrimiento=2, techo=53, ornamentos=0.0)
    con, sin_ = correr({"separar": True}, lead85, sec85), correr({"separar": False}, lead85, sec85)
    a = {t: n for t, _, n in notas(con, "SEC")}
    b = {t: n for t, _, n in notas(sin_, "SEC")}
    raices_movidas = sum(1 for t in a if t in b and b[t] % 12 == 5 and a[t] != b[t])
    bien &= ok(raices_movidas == 0, "separar no le quita la raíz al secundario por una ♭9 lejana")

    def flams(evs):
        """Ataques del secundario a 1-3 ticks de uno del lead (sin caer junto a otro del lead)."""
        lead = {u for u, _, _ in notas(evs, "LEAD")}
        return sum(1 for t, _, _ in notas(evs, "SEC") if t not in lead and any(0 < abs(t - u) <= 3 for u in lead))
    bien &= ok(flams(sin_) > 0 and flams(con) == 0,
               f"separar: el tresillo no queda a 1-3 ticks de un ataque del lead (antes {flams(sin_)} flams)")

    lead64 = dict(LEAD, figura="tresillo", seed="M1", huecos=0.3)
    sec64 = dict(SEC, estilo="clasico", figura="pedal", seed="B7")
    antes64, con64 = flams(correr({}, lead64, sec64)), flams(correr({"separar": True}, lead64, sec64))
    bien &= ok(antes64 > 0 and con64 == 0, f"separar: con el tresillo en el lead, el secundario va con él (antes {antes64} flams)")

    # Tresillo sobre tresillo con corrimiento 1: la nota que se endereza no puede quedar
    # pegada al golpe tardío del lead en el paso anterior.
    tt = correr({"separar": True, "corrimiento": 1}, lead64, dict(SEC, figura="tresillo", seed="P-tresillo", huecos=0.4))
    bien &= ok(flams(tt) == 0, "separar: tresillo sobre tresillo corrido 1, sin flams")
    # Muestra de la matriz: estilos y figuras unos encima de otros, varios corrimientos.
    from goa import generador
    voces = [dict(estilo=e_, seed="X-" + e_) for e_ in ("rolling", "galope", "arpegio3", "acido", "psy_chill", "largas")]
    voces += [dict(estilo="clasico", figura=f, seed="G-" + f, frase=4) for f in generador.FIGURAS]
    voces += [dict(estilo="psytrance", figura=f, seed="P-" + f, frase=4, huecos=0.4) for f in generador.FIGURAS_PSY]
    malos = 0
    for k, a_ in enumerate(voces):
        for j, b_ in enumerate(voces):
            c = (k * 7 + j * 3) % 16
            evs = eventos(41, "frigio", dict(a_, octava=1, gate=0.5), None, 2, "psytrance", {}, None,
                          dict(b_, octava=0, gate=0.5, corrimiento=c, separar=True))
            malos += bool(flams(evs) or choques(evs))
    bien &= ok(malos == 0, f"separar: {len(voces) ** 2} pares de estilos con corrimientos variados, sin flams ni choques")

    # Swing distinto en cada voz: separar alinea los pasos impares.
    for sl, ss in ((0.3, 0.0), (0.0, 0.3), (0.5, 0.2)):
        con_sw = correr({"separar": True, "swing": ss}, dict(LEAD, swing=sl), dict(SEC, figura="riff", seed="P7"))
        sin_sw = correr({"swing": ss}, dict(LEAD, swing=sl), dict(SEC, figura="riff", seed="P7"))
        bien &= ok(flams(con_sw) == 0 < flams(sin_sw), f"separar con swing {sl} / {ss}: sin flams (antes {flams(sin_sw)})")

    # Con armonía guiada, separar no saca las notas del acorde en los tiempos fuertes.
    def del_acorde(evs):
        pads, bien_, tot = notas(evs, "PADS"), 0, 0
        for t, _, n in notas(evs, "SEC"):
            acorde = {m % 12 for c, d, m in pads if c <= t < d}
            if (t // 6) % 4 == 0 and acorde:
                tot += 1
                bien_ += n % 12 in acorde
        return bien_ / max(1, tot)
    prog = lambda sep: eventos(41, "menor_armonica", dict(LEAD, figura="melodia", seed="Q2"), "i_iv_bVI_bIII", 8,  # noqa: E731
                               "psytrance", {}, {"suenan": True}, dict(SEC, estilo="clasico", figura="acordes", seed="E2", separar=sep))
    sin_sep, con_sep = del_acorde(prog(False)), del_acorde(prog(True))
    bien &= ok(con_sep >= sin_sep - 0.02, f"separar con progresión: notas del acorde en los tiempos {sin_sep:.0%} → {con_sep:.0%}")

    cfg = normalizar({"secuencia": [{"corrimiento": 3, "complementar": 0.7, "separar": True}]})
    s = cfg["secuencia"][0]
    bien &= ok((s["corrimiento"], s["complementar"], s["separar"]) == (3, 0.7, True), "los tres se guardan en la secuencia")
    print("\nTodo bien." if bien else "\nHay fallas.")
    return 0 if bien else 1


if __name__ == "__main__":
    sys.exit(main())
