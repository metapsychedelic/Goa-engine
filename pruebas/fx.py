"""Prueba el motor de FX sin hardware.

  python3 -m pruebas.fx            desde la carpeta goa-engine

Revisa los gestos (zaps, burbujas, ácido, glitch), la subida desde la app (riser
que se densifica, pitch que sube, filtro que baja y se abre), el drop con la caída,
la intervención de las secuencias marcadas con FX (filtro y stutter), las partes
con riser en el modo canción y el piloto.
"""

import copy

from goa import forma
from goa.config import a_toml, normalizar, salidas
from goa.fx import BEND_MAX, curva_filtro
from goa.motor import Motor

from .dialogo import base, ok

TC = 96  # ticks por compás


def armar(**fx):
    cfg = base()
    cfg["dialogo"]["activo"] = False
    cfg["fx"].update(dict(dict(activo=True, salida="MC-101", canal=2, disparo=2), **fx))
    return normalizar(cfg)


def correr(cfg, compases, en_compas=None):
    """Corre el motor con la nota larga F2 en el canal 2. en_compas: {compás: función(motor)}."""
    salida = []
    m = Motor(cfg, lambda sal, tipo, canal, n, v: salida.append((m.tick, sal, tipo, canal, n, v)))
    m.start()
    for tick in range(compases * TC):
        if en_compas and tick % TC == 50 and tick // TC in en_compas:
            en_compas[tick // TC](m)
        m.reloj()
        if tick % TC == 1:
            m.nota_on(1, 41)  # la Circuit repite la nota larga en cada vuelta
    return salida, m


def de(salida, sal, tipo=None):
    return [x for x in salida if x[1] == sal and (tipo is None or x[2] == tipo)]


if __name__ == "__main__":
    todo = True

    # --- La curva del filtro ---
    v = [curva_filtro(t / 100, 100) for t in range(101)]
    todo &= ok(v[0] == 100 and min(v) == v[25] and v[100] == 127, f"filtro: parte en el reposo, baja en el primer cuarto y termina abierto ({v[0]} → {v[25]} → {v[100]})")
    todo &= ok(all(b >= a for a, b in zip(v[25:], v[26:])), "filtro: después del primer cuarto solo sube")
    todo &= ok(all(abs(b - a) <= 8 for a, b in zip(v, v[1:])), "filtro: nunca salta de golpe")

    # --- Gestos fuera de la subida ---
    cfg = armar(locura=1.0)
    salida, m = correr(cfg, 32)
    ons = de(salida, "MC-101", "note_on")
    todo &= ok(len(ons) > 20, f"con locura al máximo hay gestos ({len(ons)} notas en 32 compases)")
    todo &= ok(all(x[3] == 1 for x in de(salida, "MC-101")), "todo el FX sale por su canal (2)")
    bends = de(salida, "MC-101", "pitchwheel")
    todo &= ok(bends and all(-8192 <= x[4] <= 8191 for x in bends), f"zaps y glitches con pitch bend ({len(bends)} mensajes)")
    m.stop()
    todo &= ok(not m.fx.sonando and m.fx.bend == 0, "stop: no queda ninguna nota ni pitch colgado")
    cfg0 = armar(locura=0.0)
    salida0, _ = correr(cfg0, 32)
    todo &= ok(not de(salida0, "MC-101", "note_on"), "con locura 0 no hay gestos")
    a, _ = correr(cfg, 16)
    b, _ = correr(cfg, 16)
    todo &= ok(a == b, "misma variante, mismos gestos")
    cfg2 = copy.deepcopy(cfg)
    cfg2["fx"]["seed"] = "OTRA"
    c, _ = correr(cfg2, 16)
    todo &= ok(a != c, "otra variante, otros gestos")
    sin = armar(locura=1.0, zap=False, burbujas=False, acido=False, glitch=False)
    s2, _ = correr(sin, 16)
    todo &= ok(not de(s2, "MC-101", "note_on"), "sin gestos elegidos no toca nada")
    amb = armar(locura=1.0, genero="ambient")
    s3, _ = correr(amb, 32)
    todo &= ok(0 < len(de(s3, "MC-101", "note_on")) < len(ons), "ambient: pocos gestos y suaves (solo burbujas)")
    todo &= ok(not de(s3, "MC-101", "pitchwheel"), "ambient: sin zaps ni glitches")

    # Afinación: todas las notas del FX están en la escala (F frigio)
    escala = {(5 + i) % 12 for i in (0, 1, 3, 5, 7, 8, 10)}
    todo &= ok(all(x[4] % 12 in escala for x in ons), "todas las notas del FX están en la escala")

    # --- Subida desde la app: 8 compases desde el compás 4, drop en el 12 ---
    cfg = armar(locura=0.0)  # sin gestos sueltos: solo el riser
    cfg["secuencia"][0].update(activa=True, disparo=2, fx=True, cc_filtro=74, filtro_reposo=110)
    cfg = normalizar(cfg)
    salida, m = correr(cfg, 16, {3: lambda m: m.pedir_subida(8)})
    riser = [x for x in de(salida, "MC-101", "note_on") if 4 * TC <= x[0] < 12 * TC]
    por_cuarto = [sum(1 for x in riser if 4 * TC + q * 2 * TC <= x[0] < 4 * TC + (q + 1) * 2 * TC) for q in range(4)]
    todo &= ok(por_cuarto == sorted(por_cuarto) and por_cuarto[0] < por_cuarto[3], f"riser: los golpes se densifican {por_cuarto}")
    todo &= ok(not [x for x in de(salida, "MC-101", "note_on") if x[0] < 4 * TC], "riser: nada antes de la subida")
    vels = [x[5] for x in riser]
    todo &= ok(vels[0] < vels[-1], f"riser: crece de fuerza ({vels[0]} → {vels[-1]})")
    pb = [x for x in de(salida, "MC-101", "pitchwheel") if x[0] < 12 * TC]
    todo &= ok(pb and pb[-1][4] > 7000 and all(b[4] >= a[4] for a, b in zip(pb, pb[1:])), "riser: el pitch solo sube, hasta arriba")
    cc = [x for x in de(salida, "MC-101", "control_change") if x[0] < 12 * TC]
    todo &= ok(cc and min(c[5] for c in cc) < 40 and cc[-1][5] >= 120, "riser: el filtro baja y termina abierto")
    caida = [x for x in de(salida, "MC-101") if x[0] >= 12 * TC]
    todo &= ok(any(x[2] == "note_on" and x[0] == 12 * TC for x in caida), "drop: la caída parte justo en el uno")
    pb2 = [x[4] for x in caida if x[2] == "pitchwheel"]
    todo &= ok(pb2 and pb2[0] > 7000 and min(pb2) < -7000 and pb2[-1] == 0, "caída: el pitch se desploma y vuelve al centro")
    seq_cc = de(salida, "FM-1", "control_change")
    todo &= ok(seq_cc and all(x[3] == 3 and x[4] == 74 for x in seq_cc), "secuencia con FX: su filtro por el CC 74 de su canal")
    dentro = [x[5] for x in seq_cc if x[0] < 12 * TC]
    todo &= ok(dentro[0] <= 110 and min(dentro) < 30 and dentro[-1] >= 120, f"secuencia: el filtro baja y se abre ({dentro[0]} → {min(dentro)} → {dentro[-1]})")
    todo &= ok(seq_cc[-1][0] == 12 * TC and seq_cc[-1][5] == 110, "secuencia: en el drop el filtro vuelve a su reposo")
    todo &= ok(all(abs(b[5] - a[5]) <= 10 for a, b in zip(seq_cc, seq_cc[1:]) if b[0] < 12 * TC), "secuencia: el filtro nunca salta durante la subida")
    notas_fm = [x for x in de(salida, "FM-1", "note_on")]
    antes = sum(1 for x in notas_fm if 4 * TC <= x[0] < 8 * TC)
    final = sum(1 for x in notas_fm if 10 * TC <= x[0] < 12 * TC) * 2
    todo &= ok(final > antes, f"secuencia: redobles al final de la subida ({antes} → {final} notas cada 4 compases)")

    # Cancelar
    salida, m = correr(cfg, 10, {3: lambda m: m.pedir_subida(8), 5: lambda m: m.pedir_subida(0)})
    todo &= ok(not [x for x in de(salida, "MC-101", "note_on") if x[0] >= 6 * TC], "cancelar: la subida para en el próximo compás, sin caída")
    todo &= ok(de(salida, "FM-1", "control_change")[-1][5] == 110, "cancelar: el filtro vuelve a su reposo")

    # Stop a mitad de la subida
    salida, m = correr(cfg, 6, {3: lambda m: m.pedir_subida(8)})
    m.stop()
    todo &= ok(m.subida is None and not m.cc_secuencias, "stop: se olvida la subida y los filtros vuelven")

    # --- Glitches de las secuencias fuera de la subida ---
    cfg = armar(locura=1.0, activo=False)
    cfg["secuencia"][0].update(activa=True, disparo=2, fx=True)
    cfg = normalizar(cfg)
    con, _ = correr(cfg, 16)
    cfg_sin = copy.deepcopy(cfg)
    cfg_sin["secuencia"][0]["fx"] = False
    sin, _ = correr(cfg_sin, 16)
    fm_con, fm_sin = de(con, "FM-1", "note_on"), de(sin, "FM-1", "note_on")
    distinto = {x[0] // 6 % 64 for x in fm_con} ^ {x[0] // 6 % 64 for x in fm_sin}
    fuera = [p for p in distinto if p % 16 < 12 or (p // 16) % 4 != 3]
    todo &= ok(fm_con != fm_sin and not fuera, "glitch: solo cambia el último tiempo de la frase")
    todo &= ok(not de(con, "MC-101"), "con el FX apagado, la voz de FX calla (las secuencias igual se intervienen)")

    # --- Canción: parte con riser ---
    cfg = armar(locura=0.0)
    cfg["pads"]["disparo"] = 2
    c2 = copy.deepcopy(cfg)
    cfg["escena"] = [forma.escena_de(c2, "A")]
    cfg["parte"] = [dict(nombre="Build", compases=8, escena=0, energia=0.5, energia_fin=0.8, riser=True),
                    dict(nombre="Drop", compases=8, escena=0, energia=0.9, energia_fin=0.9, entrada="golpe")]
    cfg["cancion"]["activa"] = True
    cfg = normalizar(cfg)
    salida, m = correr(cfg, 12)
    on = de(salida, "MC-101", "note_on")
    todo &= ok(on and on[0][0] < TC and any(x[0] == 8 * TC for x in on), "canción: riser en toda la parte y caída en el uno de la siguiente")
    todo &= ok(not [x for x in on if 9 * TC <= x[0] < 10 * TC and x[5] > 0 and x[4] != on[-1][4]], "canción: después de la caída no vuelve el riser")

    # --- Piloto: el riser va en el build y en el break ---
    cfg = armar(locura=0.0)
    cfg["forma"].update(piloto=True, duracion="corta", energia=0.2)
    cfg = normalizar(cfg)
    _, m2 = correr(cfg, 10)
    todo &= ok(m2.subida is not None and m2.subida["origen"] == "piloto", "piloto: en el build hay subida")

    # --- Configuración ---
    cfg = armar()
    texto = a_toml(cfg)
    todo &= ok("[fx]" in texto and "locura" in texto, "la configuración guarda la sección [fx]")
    todo &= ok("MC-101" in salidas(cfg), "abre el puerto del FX")
    e = forma.escena_de(cfg, "E")
    todo &= ok('"fx"' in e["datos"] and "cc_corte" not in e["datos"], "las escenas guardan el FX (sin destinos ni CC)")
    todo &= ok(forma.energizar(cfg, 1.0)["fx"]["locura"] > cfg["fx"]["locura"] > forma.energizar(cfg, 0.0)["fx"]["locura"],
               "la energía sube y baja la locura")

    print("\nTODO BIEN" if todo else "\nHAY ERRORES")
