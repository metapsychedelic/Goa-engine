"""Pruebas de la 0.96: género Zenon / dark prog, un cambio a la vez, armonía según la
energía, respuesta en el compás par y espacio para el bombo.

  python3 -m pruebas.zenon
"""

from goa import generos
from goa.config import cargar, normalizar
from goa.motor import Motor
from pruebas.carpeta import correr, notas, ok
from pruebas.simular import RAIZ


def con_motor(ajustar, compases):
    cfg = cargar(RAIZ / "config.ejemplo.toml")
    cfg["entrada"].update(canal_disparo=2, nota_maxima=0)
    for s in cfg["secuencia"]:
        s["activa"] = False
    cfg["bajo"]["activo"] = False
    cfg["pads"]["activo"] = False
    ajustar(cfg)
    cfg = normalizar(cfg)
    out = []
    m = Motor(cfg, lambda sal, tipo, canal, nota, vel: out.append((sal, m.tick, tipo, nota, vel)))
    m.start()
    m.nota_on(1, 41)
    vistos = []
    for _ in range(compases * 96):
        m.reloj()
        if m.tick % 96 == 1:
            vistos.append(list(m.director.efectos))
    m.stop()
    return out, vistos


def main():
    todo = True

    print("Género Zenon / dark prog")
    cfg = normalizar(generos.aplicar(normalizar(cargar(RAIZ / "config.ejemplo.toml")), "zenon"))
    todo &= ok(cfg["bajo"]["estilo"] == "zenon" and cfg["bajo"]["arco"] == 0.5, "bajo Zenon con arco")
    todo &= ok(cfg["forma"]["un_cambio"] and cfg["forma"]["espacio_bombo"] > 0, "un cambio a la vez y espacio para el bombo")
    todo &= ok(all(s["figura"] == "ciclo" and s["ciclo"] == 5 for s in cfg["secuencia"]), "secuencias en ciclo de 5")
    goa = normalizar(generos.aplicar(cfg, "goa"))
    todo &= ok(not goa["forma"]["un_cambio"] and goa["forma"]["espacio_bombo"] == 0 and goa["bajo"]["arco"] == 0,
               "otro género lo apaga")

    print("\nUn cambio a la vez")
    def director(un, secuencias=1, compases=200):
        def ajustar(c):
            c["forma"].update(variacion=1.0, periodo=8, un_cambio=un)
            c["bajo"].update(activo=True, salida="BAJO", disparo=0, estilo="zenon", filtro=True)
            for s in c["secuencia"][:secuencias]:
                s.update(activa=True, disparo=0)
        return con_motor(ajustar, compases)[1]
    libre, uno = director(False, 2, 96), director(True)
    todo &= ok(max(len(e) for e in libre) == 2, "sin la opción puede hacer dos cambios")
    todo &= ok(max(len(e) for e in uno) == 1, "con la opción, nunca más de uno")
    tipos = {e[0][0] for e in uno if e}
    todo &= ok(bool(tipos & {"bajo_arco", "bajo_abre"}), f"a veces toca el bajo ({', '.join(sorted(tipos))})")

    print("\nArmonía según la energía")
    def pads(energia):
        out = correr(lambda c: (c["pads"].update(activo=True, salida="PADS", disparo=0),
                                c["bajo"].update(activo=True, salida="BAJO", disparo=0),
                                c["forma"].update(energia=energia, pads_por_energia=True)), 8)
        return notas(out, "PADS"), notas(out, "BAJO")
    alto_p, alto_b = pads(0.9)
    bajo_p, _ = pads(0.2)
    todo &= ok(not alto_p and bool(alto_b), "con mucha energía los pads se callan y el bajo sigue")
    todo &= ok(bool(bajo_p), "con poca energía los pads suenan")
    medio_p, _ = pads(0.5)
    todo &= ok(bool(medio_p), "en el medio, como estén")

    print("\nRespuesta en el compás par")
    def sec(par):
        out = correr(lambda c: c["secuencia"][0].update(activa=True, disparo=0, salida="SEC", estilo="rolling",
                                                       posicion="todos", mutacion=0, respuesta_par=par), 8)
        return notas(out, "SEC")
    sin, con = sec(0.0), sec(1.0)
    t0 = sin[0][0] - sin[0][0] % 96
    cambios = [((a - t0) // 96, ((a - t0) % 96) // 6) for (a, _, n, _), (_, _, m, _) in zip(sin, con) if n != m]
    todo &= ok(len(sin) == len(con), "mismo ritmo")
    todo &= ok(bool(cambios) and all(c % 2 == 1 and l >= 12 for c, l in cambios),
               f"cambian solo notas del tiempo 4 del 2.º compás de cada par ({len(cambios)})")

    print("\nEspacio para el bombo")
    def encima(out, salida):
        return [(a, b) for a, b, _, _ in notas(out, salida) if any(a < k < b for k in range(a - a % 24 + 24, b, 24))]
    largo = lambda e: (lambda c: (c["bajo"].update(activo=True, salida="BAJO", disparo=0, estilo="zenon", seed="Z-27",
                                                    gate=0.95, arco=1.0),
                                  c["forma"].update(espacio_bombo=e)))  # noqa: E731
    sin = correr(largo(0.0), 8)
    con = correr(largo(0.5), 8)
    todo &= ok(bool(encima(sin, "BAJO")), f"sin espacio hay notas encima del bombo ({len(encima(sin, 'BAJO'))})")
    todo &= ok(not encima(con, "BAJO"), "con espacio, ninguna nota del bajo sigue sonando en el bombo")
    pw = [(t, v) for s, t, ti, v, _ in con if s == "BAJO" and ti == "pitchwheel"]
    todo &= ok(all(v == 0 for t, v in pw if t % 24 == 0), "el pitch bend vuelve al centro en cada bombo")
    seq = lambda e: (lambda c: (c["secuencia"][0].update(activa=True, disparo=0, salida="SEC", estilo="largas",  # noqa: E731
                                                         posicion="todos", gate=1.0, largas=1.0),
                                c["forma"].update(espacio_bombo=e)))
    todo &= ok(bool(encima(correr(seq(0.0), 8), "SEC")) and not encima(correr(seq(0.5), 8), "SEC"),
               "las secuencias también se cortan")

    print("\nTodo bien" if todo else "\nHAY FALLAS")
    return todo


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
