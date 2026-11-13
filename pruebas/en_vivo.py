"""Prueba los cambios de configuración en vivo, sin hardware.

Mover algo en la app no debe volver a atacar los pads, y elegir el género de una
secuencia o del bajo no debe mover tus ajustes.

  python3 -m pruebas.en_vivo            desde la carpeta goa-engine
"""

import copy

from goa import generos
from goa.config import normalizar
from goa.motor import Motor

from .dialogo import base, colgadas, ok

NOTA_LARGA = 41


def armar():
    cfg = normalizar(base())
    cfg["dialogo"]["activo"] = False
    cfg["pads"].update(activo=True, disparo=2, cambia_cada=4, suspensiones=0.0, rasgueo=1, salida="PADS")
    cfg["secuencia"][0].update(activa=True, disparo=2, salida="SEC")
    return cfg


def tocar(cfg, cambios, compases=6):
    """Corre el motor; `cambios` = {tick: función(cfg) -> cfg nueva}. Devuelve los eventos."""
    ev = []
    m = Motor(cfg, lambda sal, tipo, canal, nota, vel: ev.append((m.tick, sal, tipo, nota)))
    m.start()
    for tick in range(compases * 96):
        m.reloj()
        p, r = divmod(tick, 6)
        if r == 1 and p % 16 == 0:
            m.nota_on(1, NOTA_LARGA)
        if tick in cambios:
            cfg = normalizar(cambios[tick](copy.deepcopy(cfg)))
            m.aplicar_config(cfg)
    m.stop()
    return ev


def de_pads(ev, desde, hasta):
    return [(t, ti, n) for t, s, ti, n in ev if s == "PADS" and desde <= t < hasta]


if __name__ == "__main__":
    todo = True
    CAMBIO = 96 + 40  # a mitad del compás 2 (el acorde cambia cada 4 compases)

    print("Pads al mover otras cosas")
    for nombre, cambio in [
        ("estilo de la secuencia", lambda c: (c["secuencia"][0].update(estilo="arpegio3"), c)[1]),
        ("swing de la secuencia", lambda c: (c["secuencia"][0].update(swing=0.3), c)[1]),
        ("tensión de la armonía", lambda c: (c["musica"].update(tension=0.8), c)[1]),
    ]:
        ev = tocar(armar(), {CAMBIO: cambio})
        todo &= ok(not de_pads(ev, CAMBIO, 4 * 96) and colgadas([(t, s, ti, 0, n, 0) for t, s, ti, n in ev]) == 0,
                   f"cambiar el {nombre}: los pads siguen sonando, sin cortarse ni volver a atacar")

    print("\nPads al cambiar sus propios ajustes")
    ev = tocar(armar(), {CAMBIO: lambda c: (c["pads"].update(velocidad=70), c)[1]})
    todo &= ok(not de_pads(ev, CAMBIO, 4 * 96), "la fuerza: no vuelve a atacar (se nota en el próximo acorde)")
    antes = tocar(armar(), {})
    ev = tocar(armar(), {CAMBIO: lambda c: (c["pads"].update(acorde="quintas"), c)[1]})
    cambiados = de_pads(ev, CAMBIO, CAMBIO + 12)
    sonando = {n for t, ti, n in de_pads(antes, 0, CAMBIO) if ti == "note_on"}
    nuevos = {n for t, ti, n in cambiados if ti == "note_on"}
    apagados = {n for t, ti, n in cambiados if ti == "note_off"}
    todo &= ok(cambiados and not (nuevos & sonando) and apagados <= sonando and len(apagados) < len(sonando),
               f"el acorde: pasa en ligado, las notas comunes siguen ({len(sonando - apagados)} se quedan)")
    reatacar = armar()
    reatacar["pads"]["ataque"] = "reatacar"
    ev = tocar(reatacar, {CAMBIO: lambda c: (c["secuencia"][0].update(gate=0.3), c)[1]})
    todo &= ok(not de_pads(ev, CAMBIO, 4 * 96), "con 'vuelve a atacar' tampoco se reataca por mover otra cosa")
    ev = tocar(armar(), {CAMBIO: lambda c: (c["pads"].update(canal=5), c)[1]})
    cortes = [n for t, ti, n in de_pads(ev, CAMBIO, CAMBIO + 1) if ti == "note_off"]
    todo &= ok(len(cortes) == len(sonando), "cambiar el canal: apaga las notas del canal de antes")
    ev = tocar(armar(), {CAMBIO: lambda c: (c["pads"].update(suenan=False), c)[1]})
    todo &= ok(colgadas([(t, s, ti, 0, n, 0) for t, s, ti, n in ev]) == 0 and
               not [1 for t, ti, n in de_pads(ev, CAMBIO + 1, 6 * 96) if ti == "note_on"],
               "callarlos: se apagan y no quedan notas colgadas")

    print("\nEl género de una secuencia o del bajo no mueve tus ajustes")
    cfg = normalizar(base())
    cfg["secuencia"][0].update(swing=0.2, gate=0.33, pedal=0.8, largas=0.4, slide=0.1)
    cfg["bajo"].update(swing=0.15, gate=0.4, movimiento=0.7, evolucion=0.5, frase=8)
    nueva = generos.aplicar(cfg, "chillgressive", parte="secuencia", indice=0)
    s0, s1 = cfg["secuencia"][0], nueva["secuencia"][0]
    todo &= ok(s1["estilo"] == "rolling" and all(s1[k] == s0[k] for k in ("swing", "gate", "pedal", "largas", "slide", "largo")),
               "secuencia: cambia el estilo, y el swing, largo, pedal y slide se quedan")
    amb = generos.aplicar(cfg, "ambient", parte="secuencia", indice=0)["secuencia"][0]
    todo &= ok(amb["estilo"] == "ambient" and amb["posicion"] == "todos" and amb["swing"] == 0.2,
               "ambient pone sus notas también en el tiempo (si no, no sonarían)")
    b0, b1 = cfg["bajo"], generos.aplicar(cfg, "psy_chill", parte="bajo")["bajo"]
    todo &= ok(b1["estilo"] == "galope" and all(b1[k] == b0[k] for k in ("swing", "gate", "movimiento", "evolucion", "frase")),
               "bajo: cambia el estilo, y tus ajustes se quedan")
    todo_cfg = generos.aplicar(cfg, "chillout")
    todo &= ok(todo_cfg["bajo"]["estilo"] == "dub" and todo_cfg["secuencia"][0]["swing"] != 0.2,
               "el 'Género para todo' de Música sí pone el perfil completo (es el atajo)")

    print("\nTodo bien" if todo else "\nHay errores")
    raise SystemExit(0 if todo else 1)
