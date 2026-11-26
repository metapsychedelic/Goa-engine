"""Filtro compartido de los rises (goa/motor_filtro.py).

  python3 -m pruebas.filtro_grupo
"""

from pathlib import Path

from goa.config import ESQUEMA_RISE, cargar, normalizar
from goa.motor import Motor

RAIZ = Path(__file__).resolve().parent.parent


def ok(cond, texto):
    print(("  ok   " if cond else "  FALLA ") + texto)
    return cond


def rise(**kw):
    return dict({k: e[1] for k, e in ESQUEMA_RISE.items()}, **kw)


def base(partes, rises, **extra):
    cfg = normalizar(cargar(RAIZ / "config.ejemplo.toml"))
    cfg["parte"], cfg["rise"], cfg["fill"], cfg["break"] = partes, rises, [], []
    cfg["cancion"]["activa"] = bool(partes)
    for k, v in extra.items():
        cfg[k].update(v)
    return normalizar(cfg)


def tocar(cfg, compases, antes=None):
    ev = []
    m = Motor(cfg, lambda *a: ev.append((m.tick // 96,) + a))
    m.start()
    m.nota_on(1, 41)
    for i in range(compases * 96):
        if antes:
            antes(m, i)
        m.reloj()
    m.stop()
    return m, ev


def cc(ev, salida, canal, numero):
    return [(e[0], e[5]) for e in ev if e[2] == "control_change" and e[1] == salida and e[3] == canal and e[4] == numero]


def main():
    todo = True
    cfg0 = normalizar(cargar(RAIZ / "config.ejemplo.toml"))
    sec = cfg0["secuencia"][0]
    print("Canción: la parte con final «rise» y filtro compartido")
    r = rise(nombre="R", riser=False, filtro=True, filtro_compases=4, filtro_desde=10, filtro_hasta=120,
             filtro_quienes=f"circuit,circuit_s1,sec:{sec['nombre']}")
    partes = [dict(nombre="A", compases=8, final="rise", final_rise="R"), dict(nombre="B", compases=4)]
    cfg = base(partes, [r], circuit={"activo": True})
    m, ev = tocar(cfg, 11)
    s1 = cc(ev, "Circuit", 0, 74)
    todo &= ok(s1 and s1[0] == (4, 10) and all(4 <= c < 8 for c, _ in s1), f"Synth 1 parte cerrado en el compás 5 y se abre hasta el drop ({s1[:2]}…{s1[-1:]})")
    vals = [v for _, v in s1]
    todo &= ok(vals == sorted(vals) and vals[-1] == 120, "sube siempre y llega a «hasta» en el último paso")
    maestro = cc(ev, "Circuit", 15, 74)
    todo &= ok(maestro and maestro[0] == (4, 5) and maestro[-1] == (7, 64), f"filtro maestro: de {maestro[0]} a apagado (64) justo antes del drop")
    s = cc(ev, sec["salida"], sec["canal"] - 1, sec["cc_filtro"])
    todo &= ok(s and s[0][1] == 10 and s[-1] == (8, sec["filtro_reposo"]), f"la secuencia vuelve a su reposo en el drop ({s[-1]})")
    todo &= ok(not cc(ev, "Circuit", 1, 74), "Synth 2 (no elegido) no se toca")

    print("Los demás esperan")
    cfg = base(partes, [r], circuit={"activo": True, "subida_filtro": True})
    cfg["parte"][0]["riser"] = True
    cfg["secuencia"][0]["subida_filtro"] = True
    cfg = normalizar(cfg)
    m, ev = tocar(cfg, 11)
    s = cc(ev, sec["salida"], sec["canal"] - 1, sec["cc_filtro"])
    en_grupo = [v for c, v in s if 4 <= c < 8]
    todo &= ok(en_grupo and en_grupo[0] == 10 and en_grupo == sorted(en_grupo), "el filtro de la subida de la secuencia no pelea con el compartido")
    maestro = [v for c, v in cc(ev, "Circuit", 15, 74) if 4 <= c < 8]
    todo &= ok(maestro == sorted(maestro) and max(maestro) <= 64, f"el filtro maestro de las subidas de la Circuit espera ({maestro[:3]}…)")

    print("Modo libre: subida del botón con el rise elegido")
    cfg = base([], [r], bateria={"rise_libre": "R"}, circuit={"activo": True})
    m, ev = tocar(cfg, 8, antes=lambda m, i: m.pedir_subida(4) if i == 96 + 50 else None)
    s1 = cc(ev, "Circuit", 0, 74)
    todo &= ok(s1 and s1[0] == (2, 10) and s1[-1][0] < 6, f"cierra en el uno de la subida y abre hasta el drop ({s1[0]}…{s1[-1]})")

    print("Probar")
    m, ev = tocar(base([], [r], circuit={"activo": True}), 5, antes=lambda m, i: m.probar_bateria("rise", r) if i == 50 else None)
    s1 = cc(ev, "Circuit", 0, 74)
    todo &= ok(s1 and s1[0] == (1, 10) and s1[-1][1] == 120, f"«Probar» un rise sin batería abre el filtro desde el próximo compás ({s1[0]}…{s1[-1]})")

    print("Stop a mitad")
    m, ev = tocar(base(partes, [r], circuit={"activo": True}), 6)
    fin = cc(ev, "Circuit", 15, 74)
    todo &= ok(fin and fin[-1][1] == 64, f"en Stop el filtro maestro vuelve a 64 ({fin[-1:]})")
    print("Todo bien" if todo else "HAY FALLAS")
    return todo


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
