"""Prueba la llamada y respuesta sin hardware.

  python3 -m pruebas.dialogo            desde la carpeta goa-engine

Muestra la conversación en una grilla por compás (L = llamada, R = respuesta)
y revisa que no queden notas colgadas, que la misma seed suene igual,
que con el mismo sinte las voces no se pisen y que el modo en vivo responda.
"""

import itertools
import tomllib
from pathlib import Path

from goa import dialogo
from goa.config import a_toml, clip_de_dialogo, normalizar, secciones_de_clip
from goa.escalas import nombre_midi
from goa.motor import Motor

RAIZ = Path(__file__).resolve().parent.parent


def base(**dialogo_extra):
    with open(RAIZ / "config.ejemplo.toml", "rb") as f:
        cfg = normalizar(tomllib.load(f))
    for s in cfg["secuencia"]:
        s["activa"] = False
    cfg["dialogo"].update(activo=True, disparo=2, **dialogo_extra)
    return cfg


def correr(cfg, compases=12, vivo=None):
    """vivo: lista de (paso, nota, pasos de duración) que tocas en el canal de escucha."""
    salida = []
    motor = Motor(cfg, lambda sal, tipo, canal, nota, vel: salida.append((motor.tick, sal, tipo, canal, nota, vel)))
    motor.start()
    apagar = {}
    for tick in range(compases * 16 * 6):
        motor.reloj()
        paso, resto = divmod(tick, 6)
        if resto == 1:
            if paso % 16 == 0:
                motor.nota_on(1, 41)  # nota larga F2 en el canal 2; la Circuit la repite cada vuelta
            for p, nota, dur in vivo or []:
                if p == paso:
                    motor.nota_on(motor.dialogo.escucha, nota, 100)
                    apagar[paso + dur] = apagar.get(paso + dur, []) + [nota]
            for nota in apagar.pop(paso, []):
                motor.nota_off(motor.dialogo.escucha, nota)
    motor.stop()
    return salida


def mostrar(salida, cfg, compases):
    voces = {}
    for clave, letra in (("llamada", "L"), ("respuesta", "R")):
        voces[(cfg[clave]["salida"], cfg[clave]["canal"] - 1)] = voces.get((cfg[clave]["salida"], cfg[clave]["canal"] - 1), "") + letra
    pasos = {}
    for tick, sal, tipo, canal, nota, vel in salida:
        if tipo == "note_on":
            pasos[tick // 6] = nombre_midi(nota)
    marca = {}
    for tick, sal, tipo, canal, nota, vel in salida:
        if tipo == "note_on":
            marca[tick // 6] = voces.get((sal, canal), "?")
    for compas in range(compases):
        fila = [f"{marca[p]}{pasos[p]}" if p in pasos else "·" for p in range(compas * 16, compas * 16 + 16)]
        print(f"  {compas + 1:>2}: " + " ".join(f"{x:>5}" for x in fila))


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
    salida = correr(cfg)
    print("Modo motor · llamada en FM-1 (L), respuesta en MicroFreak (R)")
    mostrar(salida, cfg, 12)
    todo &= ok(colgadas(salida) == 0, "sin notas colgadas")
    todo &= ok(correr(cfg) == salida, "misma seed, misma conversación")
    sinte = {(x[1], x[3]) for x in salida if x[2] == "note_on"}
    todo &= ok(len(sinte) == 2, "suenan las dos voces en sus sintes")

    cfg = base(evolucion=0.0)
    mismo = correr(cfg)
    ons = [x for x in mismo if x[2] == "note_on"]
    _, ciclo = Motor(cfg, lambda *a: None).dialogo._ciclo_pasos()
    vuelta1 = [(t // 6 % ciclo, n) for t, _, _, _, n, _ in ons if t < ciclo * 6]
    vuelta2 = [(t // 6 % ciclo, n) for t, _, _, _, n, _ in ons if ciclo * 6 <= t < 2 * ciclo * 6]
    todo &= ok(vuelta1 == vuelta2, "evolución 0: la frase se repite igual")
    cfg = base(evolucion=0.6)
    ons = [x for x in correr(cfg) if x[2] == "note_on"]
    vuelta1 = [(t // 6 % ciclo, n) for t, _, _, _, n, _ in ons if t < ciclo * 6]
    vuelta2 = [(t // 6 % ciclo, n) for t, _, _, _, n, _ in ons if ciclo * 6 <= t < 2 * ciclo * 6]
    todo &= ok(vuelta1 != vuelta2, "evolución 60 %: la frase cambia en cada vuelta")

    cfg = base(pausa=0, descanso=0)
    cfg["respuesta"].update(salida=cfg["llamada"]["salida"], canal=cfg["llamada"]["canal"])
    cfg["llamada"]["gate"] = cfg["respuesta"]["gate"] = 1.0
    print("\nMismo sinte, sin pausa, gate 100 %")
    salida = correr(cfg, compases=8)
    mostrar(salida, cfg, 4)
    todo &= ok(max_simultaneas(salida) == 1, "con el mismo sinte nunca suenan dos notas a la vez")

    errores = 0
    for (t, c, r, f), m in zip(itertools.product(dialogo.TRANSFORMACIONES, dialogo.CONTORNOS, dialogo.RITMOS,
                                                 dialogo.FINALES), itertools.cycle(dialogo.MOVIMIENTOS)):
        cfg = base(transformacion=t, compases_llamada=1, compases_respuesta=1)
        cfg["llamada"].update(contorno=c, ritmo=r, final=f, escala="hungara_menor", relacion="quinta", movimiento=m)
        cfg["respuesta"].update(contorno=c, ritmo=r, final=f, octava=-1, densidad=0.2,
                                movimiento=dialogo.MOVIMIENTOS[(dialogo.MOVIMIENTOS.index(m) + 1) % 3])
        s = correr(cfg, compases=6)
        if colgadas(s) or not any(x[2] == "note_on" for x in s):
            errores += 1
    todo &= ok(errores == 0, "todas las combinaciones de transformación, contorno, ritmo y final suenan")

    print("\nModo en vivo · tocas C4 D#4 F4 G#4 y la respuesta entra tras 2 tiempos de silencio")
    cfg = base(modo="en_vivo", escucha=4, transformacion="variacion")
    tocadas = [(16, 60, 2), (18, 63, 2), (20, 65, 2), (22, 68, 4)]
    salida = correr(cfg, compases=4, vivo=tocadas)
    mostrar(salida, cfg, 4)
    resp = [x for x in salida if x[2] == "note_on"]
    todo &= ok(bool(resp) and min(t for t, *_ in resp) // 6 >= 30, "responde después de tu frase y del silencio")
    todo &= ok(all(abs(n - 62) <= 14 for _, _, _, _, n, _ in resp), "responde en el registro de lo que tocaste")
    todo &= ok(colgadas(salida) == 0, "sin notas colgadas en vivo")

    cfg = base(modo="en_vivo", escucha=4, transformacion="eco")
    cfg["respuesta"]["densidad"] = 0.6
    salida = correr(cfg, compases=4, vivo=tocadas)
    notas = [nombre_midi(n) for _, _, t, _, n, _ in salida if t == "note_on"]
    todo &= ok(notas == ["C4", "D#4", "F4", "G#4"], f"eco devuelve tu frase: {' '.join(notas)}")

    print("\nCarácter")
    from goa.dialogo import Voz, frase, _oscuro
    import random
    def colores(osc):
        v = Voz({"oscuridad": osc, "movimiento": "conjunto", "final": "libre", "forma": "frase"}, "F", "frigio")
        notas = [n for i in range(300) for n in frase(random.Random(i), v, 32)]
        return sum(1 for n in notas if _oscuro(v, n["grado"])) / len(notas), \
            sum(1 for n in notas if v.tonalidad.intervalos[n["grado"] % 7] == 6) / len(notas)
    poca, _ = colores(0.0)
    mucha, _ = colores(1.0)
    todo &= ok(poca < 0.02 < mucha, f"oscuridad 0 casi sin ♭2 ni ♭6 ({poca:.0%}), en 100 % aparecen ({mucha:.0%})")
    notas = [n for forma in ("frase", "motivo") for i in range(200) for n in
             frase(random.Random(i), Voz({"movimiento": "arpegio", "final": "libre", "oscuridad": 0, "forma": forma}, "F", "frigio"), 32)]
    todo &= ok(all(n["grado"] % 7 in (0, 2, 4, 6) for n in notas), "arpegio: solo notas del acorde menor con séptima")
    v = Voz({"movimiento": "abierto", "final": "libre", "oscuridad": 0.5, "forma": "frase"}, "F", "frigio")
    saltos = [abs(b["grado"] - a["grado"]) for i in range(200) for f in [frase(random.Random(i), v, 32)]
              for a, b in zip(f, f[1:])]
    abiertos = sum(1 for x in saltos if x in (2, 3, 4, 7)) / len(saltos)
    todo &= ok(0.45 < abiertos < 0.85, f"abierto: terceras, cuartas, quintas y octavas, con algún grado conjunto ({abiertos:.0%})")
    figuras = {}
    for dens, esperado in ((0.2, {3}), (0.5, {4}), (0.75, {4}), (0.95, {5})):
        v = Voz({"densidad": dens, "forma": "motivo"}, "F", "frigio")
        figuras[dens] = {len(frase(random.Random(i), v, 32)) for i in range(100)} == esperado
    todo &= ok(all(figuras.values()), "motivo: densidad baja 3 notas, media 3 + 1 larga, alta arpegio")
    v = Voz({"densidad": 0.5, "forma": "motivo", "ritmo": "semicorcheas"}, "F", "frigio")
    f = frase(random.Random(3), v, 32)
    todo &= ok(f[-1]["dur"] > 3 * f[0]["dur"] and f[-1]["paso"] < 8, "3 cortas y una larga, y después silencio")
    def color(osc):
        v = Voz({"oscuridad": osc, "forma": "frase", "movimiento": "conjunto", "final": "libre"}, "F", "frigio")
        notas = [n for i in range(300) for n in frase(random.Random(i), v, 32)]
        return sum(1 for n in notas if v.tonalidad.intervalos[n["grado"] % 7] in (1, 8)) / len(notas)
    todo &= ok(color(0.9) > color(0.5) * 1.3, f"sobre 50 % la oscuridad atrae ♭2 y ♭6 ({color(0.5):.0%} → {color(0.9):.0%})")
    v = Voz({"final": "suspendido"}, "F", "frigio")
    todo &= ok(all(frase(random.Random(i), v, 32)[-1]["grado"] % 7 in (3, 4) for i in range(100)),
               "final suspendido: termina en quinta o cuarta")

    print("\nClips de diálogo")
    cfg = base(modo="en_vivo", transformacion="espejo", escucha=7)
    cfg["respuesta"].update(salida="FM-1", canal=4, escala="frigio_dominante", relacion="quinta")
    clip = clip_de_dialogo(cfg, "Vivo espejo")
    cfg["clip_dialogo"] = [clip]
    guardada = normalizar(tomllib.loads(a_toml(cfg)))
    todo &= ok(guardada["clip_dialogo"] == [clip], "el clip se guarda y se lee igual del archivo")

    otra = base(modo="motor", transformacion="variacion")  # lo que está armado ahora es otra cosa
    salida = []
    motor = Motor(otra, lambda sal, tipo, canal, nota, vel: salida.append((motor.tick, sal, tipo, canal, nota, vel)))
    motor.start()
    for tick in range(3 * 16 * 6):
        motor.reloj()
        paso, resto = divmod(tick, 6)
        if resto == 1 and paso % 16 == 0:
            motor.nota_on(1, 41)
        if tick == 5 * 6:  # se lanza a mitad del primer compás
            motor.lanzar_dialogo(*secciones_de_clip(clip), clip["nombre"])
            esperando = motor.estado()["fila_dialogo"]["cola"] == "Vivo espejo" and motor.dialogo.modo == "motor"
        if tick == 16 * 6 + 1:
            d = motor.dialogo
            entro = (d.clip == "Vivo espejo" and d.modo == "en_vivo" and d.transformacion == "espejo"
                     and d.escucha == 6 and d.respuesta.salida == "FM-1" and d.respuesta.canal == 3)
    todo &= ok(esperando, "lanzado a mitad de compás, queda en cola y sigue el diálogo anterior")
    todo &= ok(entro, "en el compás siguiente entra con todo su seteo: quién llama, destinos y carácter")
    motor.detener_dialogo()
    todo &= ok(motor.dialogo.activo and motor.estado()["fila_dialogo"]["cola"] == "detener", "parar queda en cola hasta el compás")
    for _ in range(16 * 6):
        motor.reloj()
    motor.stop()
    todo &= ok(not motor.dialogo.activo and colgadas(salida) == 0, "se detiene en el compás sin dejar notas colgadas")

    print("\nTodo bien" if todo else "\nHay errores")
    raise SystemExit(0 if todo else 1)
