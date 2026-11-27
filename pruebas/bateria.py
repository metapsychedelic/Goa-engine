"""Batería de la Circuit en los rises y fills (goa/bateria.py y goa/motor_bateria.py).

  python3 -m pruebas.bateria
"""

from pathlib import Path

from goa import bateria
from goa.config import ESQUEMA_FILL, ESQUEMA_RISE, cargar, normalizar
from goa.motor import Motor

RAIZ = Path(__file__).resolve().parent.parent


def ok(cond, texto):
    print(("  ok   " if cond else "  FALLA ") + texto)
    return cond


def defecto(esquema, **kw):
    return dict({k: e[1] for k, e in esquema.items()}, **kw)


def base(partes, rise=(), fill=(), **bat):
    cfg = normalizar(cargar(RAIZ / "config.ejemplo.toml"))
    cfg["parte"] = partes
    cfg["rise"], cfg["fill"], cfg["break"] = list(rise), list(fill), []
    cfg["bateria"].update(bat)
    cfg["cancion"]["activa"] = bool(partes)
    return normalizar(cfg)


def tocar(cfg, compases, subida=None):
    ev = []
    m = Motor(cfg, lambda *a: ev.append((m.tick,) + a))
    m.start()
    m.nota_on(1, 41)
    for i in range(compases * 96):
        if subida and i == subida[0] * 96 - 10:
            m.pedir_subida(subida[1])
        m.reloj()
    m.stop()
    return [e for e in ev if e[1] == "Circuit" and e[3] == 9]


def main():
    todo = True
    print("Generadores")
    for tipo in bateria.TIPOS_RISE:
        t = defecto(ESQUEMA_RISE, bateria=tipo)
        a, ev = bateria.rise(t, 64)
        _, ev2 = bateria.rise(t, 64)
        golpes = sum(len(v) for v in ev.values())
        todo &= ok(a == tipo and golpes > 4 and ev.keys() == ev2.keys(), f"rise {tipo}: {golpes} golpes, igual con la misma seed")
        todo &= ok(max(ev) < 62, f"rise {tipo}: silencio antes del drop")
    for tipo in bateria.TIPOS_FILL:
        t = defecto(ESQUEMA_FILL, bateria=tipo)
        a, ev = bateria.fill(t)
        todo &= ok(a == tipo and bool(ev) and max(ev) < 8, f"fill {tipo}: {sum(len(v) for v in ev.values())} golpes en 8 pasos")
    t = defecto(ESQUEMA_RISE, bateria="seed", bateria_seed="x")
    tipos = {bateria.rise(dict(t, bateria_seed=str(i)), 64)[0] for i in range(30)}
    todo &= ok(len(tipos) >= 4, f"«seed» elige el tipo: {sorted(tipos)}")
    r = defecto(ESQUEMA_RISE, bateria="redoble", bateria_intensidad=1.0)
    _, ev = bateria.rise(r, 64)
    todo &= ok(any(g.medio for v in ev.values() for g in v), "con intensidad alta el redoble llega a fusas")

    print("Motor: fill al final de una parte")
    fill = defecto(ESQUEMA_FILL, nombre="F", bateria="toms", bateria_largo=8)
    partes = [dict(nombre="A", compases=4, final="fill", final_fill="F"), dict(nombre="B", compases=4)]
    cfg = base(partes, fill=[fill])
    ev = tocar(cfg, 6)
    notas = [e for e in ev if e[2] == "note_on" and e[5] > 0]
    todo &= ok(bool(notas) and all(3 * 96 + 48 <= e[0] < 4 * 96 for e in notas), f"{len(notas)} golpes en los últimos 8 pasos de la parte")
    todo &= ok(not any(e[2] == "control_change" and e[4] == 50 for e in ev), "sin el sample normal del Drum 4 no cambia samples")
    pitches = {e[5] for e in ev if e[2] == "control_change" and e[4] == 55}
    todo &= ok(len(pitches) >= 2 and 64 in pitches, f"los toms salen con el pitch y vuelve a 64 ({sorted(pitches)})")

    cfg = base(partes, fill=[fill], sample_d4=33)
    ev = tocar(cfg, 6)
    samples = [e[5] for e in ev if e[2] == "control_change" and e[4] == 50]
    todo &= ok(set(samples[:-1]) <= {53, 54, 55} and samples[-1] == 33, f"con el sample normal: toms 53-55 y vuelve al 33 ({samples})")
    offs = sum(1 for e in ev if e[2] == "note_off")
    ons = sum(1 for e in ev if e[2] == "note_on")
    todo &= ok(ons == offs, f"cada golpe tiene su note_off ({ons}/{offs})")

    print("Motor: rise")
    rise = defecto(ESQUEMA_RISE, nombre="R", bateria="redoble", bateria_compases=2, bateria_intensidad=1.0)
    partes = [dict(nombre="A", compases=4, final="rise", final_rise="R"), dict(nombre="B", compases=4)]
    ev = tocar(base(partes, rise=[rise], sample_d2=16), 6)
    notas = [e for e in ev if e[2] == "note_on" and e[5] > 0]
    todo &= ok(bool(notas) and all(2 * 96 <= e[0] < 4 * 96 for e in notas), f"rise de canción: {len(notas)} golpes en los 2 últimos compases")
    todo &= ok(any(e[0] % 6 == 3 for e in notas), "fusas a mitad de paso")
    s2 = [e[5] for e in ev if e[2] == "control_change" and e[4] == 18]
    todo &= ok(s2 == [22, 16], f"Drum 2 pasa al snare roll y vuelve a su sample ({s2})")

    libre = base([], rise=[dict(rise, nombre="L")], rise_libre="L")
    ev = tocar(libre, 8, subida=(2, 4))
    notas = [e for e in ev if e[2] == "note_on" and e[5] > 0]
    todo &= ok(bool(notas) and all(4 * 96 <= e[0] < 6 * 96 for e in notas), f"subida del botón en modo libre: {len(notas)} golpes")
    sin = base([], rise=[dict(rise, nombre="L")])
    todo &= ok(not tocar(sin, 8, subida=(2, 4)), "sin rise elegido para el modo libre, nada")

    print("Probar desde la app")
    cfg = base([], fill=[fill], sample_d4=33)
    pev = []
    m = Motor(cfg, lambda *a: pev.append((m.tick,) + a))
    try:
        m.probar_bateria("fill", fill)
        todo &= ok(False, "sin Play avisa")
    except ValueError:
        todo &= ok(True, "sin Play avisa que hay que darle Play")
    m.start()
    for _ in range(int(1.5 * 96)):
        m.reloj()
    m.probar_bateria("fill", fill)
    for _ in range(3 * 96):
        m.reloj()
    notas = [e for e in pev if e[1] == "Circuit" and e[2] == "note_on" and e[5] > 0]
    todo &= ok(bool(notas) and all(2 * 96 + 48 <= e[0] < 3 * 96 for e in notas), f"el fill suena al final del próximo compás ({len(notas)} golpes)")
    samples = [e[5] for e in pev if e[1] == "Circuit" and e[2] == "control_change" and e[4] == 50]
    todo &= ok(samples[-1:] == [33], "y devuelve el sample")
    pev.clear()
    m.probar_bateria("rise", rise)
    for _ in range(4 * 96):
        m.reloj()
    notas = [e for e in pev if e[1] == "Circuit" and e[2] == "note_on" and e[5] > 0]
    todo &= ok(bool(notas) and all(5 * 96 <= e[0] < 7 * 96 for e in notas), f"el rise suena sus 2 compases desde el próximo ({len(notas)} golpes)")
    try:
        m.probar_bateria("fill", dict(fill, bateria=""))
        todo &= ok(False, "sin tipo avisa")
    except ValueError:
        todo &= ok(True, "sin tipo de batería avisa")

    print("Velocity y entrada limpia")
    suave = defecto(ESQUEMA_RISE, bateria="redoble", bateria_vel_desde=20, bateria_vel_hasta=60)
    _, ev = bateria.rise(suave, 64)
    vels = [g.vel for k in sorted(ev) for g in ev[k]]
    todo &= ok(min(vels) >= 17 and max(vels) <= 60 and vels[0] < vels[-1], f"el redoble sube de {min(vels)} a {max(vels)} (pedido 20 → 60)")
    _, ev = bateria.fill(defecto(ESQUEMA_FILL, bateria="redoble", bateria_vel_desde=90, bateria_vel_hasta=100))
    todo &= ok(all(90 <= g.vel <= 100 for v in ev.values() for g in v), "el fill respeta su rango de velocity")
    crash = dict(rise, crash=True, crash_drum=4, crash_sample=40)
    partes = [dict(nombre="A", compases=4, final="rise", final_rise="R"), dict(nombre="B", compases=4)]
    ev = tocar(base(partes, rise=[crash], sample_d2=16, sample_d4=33), 6)
    ultimo_golpe = max(e[0] for e in ev if e[2] == "note_on" and e[5] > 0 and e[4] == 62)
    vuelta = [e[0] for e in ev if e[2] == "control_change" and e[4] == 18 and e[5] == 16]
    todo &= ok(vuelta and ultimo_golpe < vuelta[0] < 4 * 96, f"el Drum 2 vuelve a su sample en el silencio antes del drop (tick {vuelta[0] if vuelta else None})")
    carga = [e[0] for e in ev if e[2] == "control_change" and e[4] == 50 and e[5] == 40]
    todo &= ok(carga and ultimo_golpe < carga[0] < 4 * 96, f"el crash queda cargado en el silencio antes del drop (tick {carga[:1]})")
    c = [(e[0], e[2], e[4], e[5]) for e in ev if e[0] >= 4 * 96 and e[4] in (50, 65) and e[2] in ("control_change", "note_on")]
    todo &= ok(c[:2] == [(4 * 96, "note_on", 65, 127), (4 * 96 + 24, "control_change", 50, 33)],
               f"en el uno: crash en el Drum 4 y un tiempo después vuelve a su sample ({c[:2]})")
    m_ev = []
    m = Motor(base(partes, rise=[crash], sample_d2=16, sample_d4=33), lambda *a: m_ev.append(a))
    m.start()
    for _ in range(4 * 96 - 3):
        m.reloj()
    m.stop()
    todo &= ok(("control_change", 9, 50, 33) in [e[1:] for e in m_ev if e[0] == "Circuit"][-6:], "Stop con el crash cargado: el Drum 4 vuelve a su sample")

    print("Stop a mitad")
    m_ev = []
    cfg = base(partes, rise=[rise], sample_d2=16)
    m = Motor(cfg, lambda *a: m_ev.append(a))
    m.start()
    for _ in range(int(3.5 * 96)):
        m.reloj()
    m.stop()
    fin = [e for e in m_ev if e[0] == "Circuit" and e[2] == 9 and e[1] == "control_change"][-2:]
    todo &= ok(("control_change", 9, 18, 16) in [e[1:] for e in fin] and ("control_change", 9, 34, 64) in [e[1:] for e in fin],
               f"en Stop vuelven sample y pitch ({fin})")
    print("Todo bien" if todo else "HAY FALLAS")
    return todo


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
