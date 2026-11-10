"""Prueba la llamada y respuesta euclidiana sin hardware.

  python3 -m pruebas.dialogo            desde la carpeta goa-engine

Muestra la conversación en una grilla por compás (L = llamada, R = respuesta)
y revisa que todo caiga en la rejilla, que la llamada siempre tenga el uno,
que la respuesta respete el espacio, que nada se pise y que siga a los pads.
"""

import tomllib
from pathlib import Path

from goa.config import a_toml, clip_de_dialogo, normalizar, secciones_de_clip
from goa.escalas import Tonalidad
from goa.motor import Motor

RAIZ = Path(__file__).resolve().parent.parent


def base(**extra):
    with open(RAIZ / "config.ejemplo.toml", "rb") as f:
        cfg = normalizar(tomllib.load(f))
    for s in cfg["secuencia"]:
        s["activa"] = False
    cfg["dialogo"].update(activo=True, disparo=2, **extra)
    return cfg


def correr(cfg, compases=16, vivo=None):
    """vivo: (paso, nota) que tocas en el canal de escucha (cada nota dura 1 paso)."""
    salida = []
    motor = Motor(cfg, lambda sal, tipo, canal, nota, vel: salida.append((motor.tick, sal, tipo, canal, nota, vel)))
    motor.start()
    apagar = {}
    for tick in range(compases * 16 * 6):
        motor.reloj()
        paso, resto = divmod(tick, 6)
        if resto == 1:
            if paso % 16 == 0:
                motor.nota_on(1, 41)  # nota larga F2; la Circuit la repite cada vuelta
            for p, nota in vivo or []:
                if p == paso:
                    motor.nota_on(motor.dialogo.escucha, nota, 100)
                    apagar[paso + 1] = apagar.get(paso + 1, []) + [nota]
            for nota in apagar.pop(paso, []):
                motor.nota_off(motor.dialogo.escucha, nota)
    motor.stop()
    return salida, motor


def voces(cfg):
    return {(cfg["llamada"]["salida"], cfg["llamada"]["canal"] - 1): "L",
            (cfg["respuesta"]["salida"], cfg["respuesta"]["canal"] - 1): "R"}


def grilla(salida, cfg, compas):
    v = voces(cfg)
    fila = ["."] * 16
    for tick, sal, tipo, canal, nota, vel in salida:
        if tipo == "note_on" and compas * 16 <= tick // 6 < compas * 16 + 16:
            fila[tick // 6 - compas * 16] = v.get((sal, canal), "?")
    return "".join(fila)


def colgadas(salida):
    sonando = {}
    for _, sal, tipo, canal, nota, _ in salida:
        clave = (sal, canal, nota)
        sonando[clave] = sonando.get(clave, 0) + (1 if tipo == "note_on" else -1)
    return sum(v for v in sonando.values() if v > 0)


def max_simultaneas(salida):
    actuales, maximo = set(), 0
    for _, sal, tipo, canal, nota, _ in salida:
        (actuales.add if tipo == "note_on" else actuales.discard)((sal, canal, nota))
        maximo = max(maximo, len(actuales))
    return maximo


def ok(condicion, texto):
    print(("OK    " if condicion else "ERROR ") + texto)
    return condicion


if __name__ == "__main__":
    todo = True
    cfg = base()
    salida, motor = correr(cfg)
    print("Entrelazado · corcheas · espacio 1 · llamada 3 golpes, respuesta 2")
    for c in range(0, 9, 4):
        print(f"  compás {c + 1:>2}: {grilla(salida, cfg, c)}")
    ons = [(t, sal, canal) for t, sal, tipo, canal, _, _ in salida if tipo == "note_on"]
    todo &= ok(all(t % 12 in (0, 1) for t, *_ in ons), "todas las notas caen en corcheas")
    todo &= ok(all(grilla(salida, cfg, c)[0] == "L" for c in range(16)), "la llamada cae en el uno de cada compás")
    todo &= ok(max_simultaneas(salida) == 1, "nunca suenan dos notas a la vez: no se pisan")
    todo &= ok(colgadas(salida) == 0, "sin notas colgadas")
    todo &= ok(correr(cfg)[0] == salida, "misma variante, misma conversación")
    todo &= ok({"L", "R"} <= set("".join(grilla(salida, cfg, c) for c in range(16))), "suenan las dos voces")

    def respeta_espacio(cfg, salida):
        for c in range(16):
            g = grilla(salida, cfg, c)
            lugares = g[::2]
            for i, x in enumerate(lugares):
                if x == "R":
                    for d in range(1, cfg["dialogo"]["espacio"] + 1):
                        if lugares[(i - d) % 8] == "L":
                            return False
        return True
    for espacio in (0, 1, 2):
        c2 = base(espacio=espacio)
        if espacio == 2:
            c2["llamada"]["golpes"] = 2
        s2, _ = correr(c2)
        todo &= ok(respeta_espacio(c2, s2), f"espacio {espacio}: la respuesta espera {espacio} corcheas después de la llamada"
                                           f" ({grilla(s2, c2, 0)})")

    cfg = base(evolucion=0.0)
    s0, _ = correr(cfg)
    todo &= ok(len({grilla(s0, cfg, c) for c in range(16)}) == 1, "mutación 0: el patrón no cambia")
    cfg = base(evolucion=1.0, mutar_cada=2)
    s1, _ = correr(cfg)
    notas = lambda s, c: [n for t, _, tipo, _, n, _ in s if tipo == "note_on" and t // 96 == c]
    todo &= ok(len({tuple(notas(s1, c)) for c in range(16)}) > 1, "mutación 100 %: cambia cada 2 compases")
    todo &= ok(all(grilla(s1, cfg, c)[0] == "L" for c in range(16)), "aun mutando, la llamada sigue cayendo en el uno")

    cfg = base(rejilla="semicorcheas")
    cfg["llamada"]["golpes"] = 5
    s3, _ = correr(cfg)
    todo &= ok(max_simultaneas(s3) == 1 and colgadas(s3) == 0, f"semicorcheas: {grilla(s3, cfg, 0)}")

    cfg = base(forma="turnos", compases_turno=2)
    s4, _ = correr(cfg, compases=8)
    turnos = [set(grilla(s4, cfg, c)) - {"."} for c in range(8)]
    todo &= ok(turnos == [{"L"}, {"L"}, {"R"}, {"R"}] * 2, "por turnos: 2 compases la llamada, 2 la respuesta")

    cfg = base()
    cfg["respuesta"].update(salida=cfg["llamada"]["salida"], canal=cfg["llamada"]["canal"])
    cfg["llamada"]["gate"] = cfg["respuesta"]["gate"] = 1.0
    s5, _ = correr(cfg)
    todo &= ok(max_simultaneas(s5) == 1, "mismo sinte y largo 100 %: un sinte mono nunca recibe dos notas juntas")

    def clases(oscuridad):
        c = base()
        c["llamada"]["oscuridad"] = c["respuesta"]["oscuridad"] = oscuridad
        s, _ = correr(c)
        return {(n - 5) % 12 for _, _, tipo, _, n, _ in s if tipo == "note_on"}
    todo &= ok(1 not in clases(0.0) and 1 in clases(1.0), "luminoso sin ♭2; ultra oscuro con ♭2 contra la raíz")

    print("\nSiguiendo a los pads (i – ♭II, cada 4 compases)")
    cfg = base()
    cfg["pads"].update(activo=True, progresion="i_bII", cambia_cada=4, disparo=2, variacion=0.0)
    s6, motor = correr(cfg)
    voz = {cfg["llamada"]["salida"], cfg["respuesta"]["salida"]}
    escala = set(Tonalidad("F", "frigio").intervalos)
    ons = [(t, n) for t, sal, tipo, _, n, _ in s6 if tipo == "note_on" and sal in voz]
    todo &= ok(all((n - 5) % 12 in escala for _, n in ons), "todas las notas en la escala de los pads")
    unos = {(t // 96 // 4) % 2: n % 12 for t, n in ons if t % 96 < 2 and (t // 96) % 4 == 0}
    todo &= ok(unos == {0: 5, 1: 6}, "el uno de la llamada sigue la raíz del acorde: F y luego G♭")

    print("\nEn vivo: tocas en el uno y el tres; responde el compás siguiente en tus huecos")
    cfg = base(modo="en_vivo", escucha=4)
    s7, _ = correr(cfg, compases=4, vivo=[(16, 60), (24, 63)])
    print(f"  compás 2 (tocas):    L.......L.......")
    print(f"  compás 3 (responde): {grilla(s7, cfg, 2)}")
    resp = grilla(s7, cfg, 2)
    todo &= ok("R" in resp and resp[0] != "R" and resp[8] != "R", "responde en los huecos que dejaste")
    todo &= ok(grilla(s7, cfg, 1) == "." * 16, "mientras tocas, no responde encima")
    notas_r = [n for t, _, tipo, _, n, _ in s7 if tipo == "note_on"]
    todo &= ok(all(55 <= n <= 80 for n in notas_r), f"responde cerca de tu registro ({notas_r})")

    print("\nClips de diálogo")
    cfg = base(forma="turnos", rejilla="semicorcheas", espacio=2)
    cfg["respuesta"].update(salida="FM-1", canal=4, golpes=5, oscuridad=1.0)
    clip = clip_de_dialogo(cfg, "Turnos oscuros")
    cfg["clip_dialogo"] = [clip]
    todo &= ok(normalizar(tomllib.loads(a_toml(cfg)))["clip_dialogo"] == [clip], "el clip se guarda y se lee igual")
    otra = base()
    motor = Motor(otra, lambda *a: None)
    motor.start()
    for tick in range(2 * 16 * 6):
        motor.reloj()
        paso, resto = divmod(tick, 6)
        if resto == 1 and paso % 16 == 0:
            motor.nota_on(1, 41)
        if tick == 5 * 6:
            motor.lanzar_dialogo(*secciones_de_clip(clip), clip["nombre"])
            esperando = motor.dialogo.forma == "entrelazado"
    d = motor.dialogo
    todo &= ok(esperando and d.clip == "Turnos oscuros" and d.forma == "turnos" and d.rejilla == "semicorcheas"
               and d.respuesta.golpes == 5 and d.respuesta.salida == "FM-1",
               "el clip entra en el compás siguiente con todo su seteo")

    print("\nTodo bien" if todo else "\nHay errores")
    raise SystemExit(0 if todo else 1)
