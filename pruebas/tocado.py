"""Tocado: tocar con el teclado de la MicroFreak a través del motor, con estilo.

  python3 -m pruebas.tocado
"""

import json
from pathlib import Path

from goa.config import cargar, normalizar, salidas
from goa.motor import Motor

RAIZ = Path(__file__).resolve().parent.parent
COMPAS = 96


def ok(cond, texto):
    print(("  ok   " if cond else "  FALLA ") + texto)
    return cond


def base(**tocado):
    cfg = normalizar(cargar(RAIZ / "config.ejemplo.toml"))
    for s in cfg["secuencia"]:
        s["activa"] = False
    cfg["entrada"].update(canal_disparo=2, nota_maxima=0)
    cfg["pads"].update(activo=True, suenan=False, disparo=0)
    cfg["tocado"].update(dict(activo=True, salida="FM-1", canal=4), **tocado)
    return normalizar(cfg)


class Sesion:
    """El motor corriendo, con la nota larga de la Circuit en cada compás."""

    def __init__(self, cfg):
        self.salida = []
        self.m = Motor(cfg, lambda sal, tipo, canal, a, b: self.salida.append((self.m.tick, sal, tipo, canal, a, b)))
        self.m.start()

    def pulsos(self, n, toques=()):
        """toques: {pulso relativo: [(tecla, vel, largo en pulsos)]}"""
        apagar = {}
        inicio = self.m.tick + 1
        for k in range(n):
            self.m.reloj()
            t = self.m.tick
            if t % COMPAS == 1:
                self.m.nota_on(1, 41)
            for tecla, vel, largo in dict(toques).get(t - inicio, []):
                self.m.tocado_on(tecla, vel)
                apagar.setdefault(t + largo, []).append(tecla)
            for tecla in apagar.pop(t, []):
                self.m.tocado_off(tecla)

    def notas(self, desde=0):
        return [(t, a, b) for t, sal, tipo, canal, a, b in self.salida
                if sal == "FM-1" and canal == 3 and tipo == "note_on" and t >= desde]

    def colgadas(self):
        on = {}
        for t, sal, tipo, canal, a, b in self.salida:
            if sal != "FM-1" or canal != 3:
                continue
            if tipo == "note_on":
                on[a] = on.get(a, 0) + 1
            elif tipo == "note_off" and on.get(a):
                on[a] -= 1
        return sum(on.values())


def ritmo(compases, tecla=60):
    """Un ritmo con cortas, largas y acentos: en cada compás 1, 1-y, 2-y (larga), 4."""
    toques = {}
    for c in range(compases):
        b = c * COMPAS
        toques[b + 0] = [(tecla, 110, 10)]
        toques[b + 12] = [(tecla, 70, 6)]
        toques[b + 36] = [(tecla, 90, 30)]
        toques[b + 72] = [(tecla, 120, 8)]
    return toques


def en_escala(m, nota):
    t = m.tonalidad
    return (nota - t.tonica) % 12 in t.intervalos


def main():
    todo = True
    print("Una tecla: cada estilo, siempre en la escala y en el acorde en el tiempo")
    from goa.generador import ESTILOS
    for estilo in ESTILOS:
        s = Sesion(base(estilo=estilo, modo="una_tecla"))
        s.pulsos(COMPAS)  # un compás para que suenen los pads
        desde = s.m.tick
        s.pulsos(4 * COMPAS, {k * 12: [(60, 90 + (k % 3) * 15, 8)] for k in range(32)})   # corcheas
        notas = s.notas(desde)
        fuera = [n for _, n, _ in notas if not en_escala(s.m, n)]
        distintas = len({n for _, n, _ in notas})
        todo &= ok(notas and not fuera and distintas > 1 and s.colgadas() == 0,
                   f"{estilo}: {len(notas)} notas, {distintas} alturas distintas, ninguna fuera de la escala, sin colgadas")
    s = Sesion(base(estilo="rolling"))
    s.pulsos(COMPAS + 5)
    antes = len(s.notas())
    s.m.tocado_on(60, 100)
    todo &= ok(len(s.notas()) == antes + 1, "suena al instante, en el mismo pulso (sin cuantizar ni esperar)")
    s.m.tocado_off(60)

    print("\nLos ajustes del estilo se notan")
    def melodia(**k):
        s = Sesion(base(**dict({"estilo": "arpegio3"}, **k)))
        s.pulsos(COMPAS)
        desde = s.m.tick
        s.pulsos(2 * COMPAS, {k * 24 + 6: [(60, 90, 8)] for k in range(8)})   # una nota por tiempo, en el contratiempo
        return [n for _, n, _ in s.notas(desde)]
    arp = melodia()
    todo &= ok(len(set(arp[:3])) == 3, f"arpegio 3 con notas sueltas: sigue el arpegio nota a nota {arp[:6]}")
    todo &= ok(melodia(relacion="quinta") != arp, "cambiar «Parte desde» cambia las notas")
    todo &= ok(melodia(estilo="psytrance", figura="octavas") != melodia(estilo="psytrance", figura="riff"), "cambiar la figura cambia las notas")
    todo &= ok(melodia(raga="hijaz") != arp, "la raga cambia la escala")
    def con_loop(estilo):
        s = Sesion(base(estilo="rolling", pasos=16))
        s.pulsos(COMPAS - 1)
        s.m.tocado.accion("grabar", s.m.tick)
        s.pulsos(COMPAS + 1, {1 + k * 24: [(60, 90, 8)] for k in range(4)})
        cfg = json.loads(json.dumps(s.m.base)); cfg["tocado"]["estilo"] = estilo
        s.m.aplicar_config(normalizar(cfg))
        s.pulsos(COMPAS)
        desde = s.m.tick
        s.pulsos(2 * COMPAS)
        return [n for _, n, _ in s.notas(desde)]
    todo &= ok(con_loop("arpegio3") != con_loop("acido"), "cambiar el estilo después de grabar cambia lo que suena el loop")

    print("\nContorno")
    s = Sesion(base(modo="contorno", estilo="rolling"))
    s.pulsos(COMPAS)
    desde = s.m.tick
    toques = {i * 12 + 6: [(tecla, 90, 6)] for i, tecla in enumerate(range(55, 79, 3))}
    s.pulsos(COMPAS, toques)
    alturas = [n for _, n, _ in s.notas(desde)]
    todo &= ok(alturas == sorted(alturas) and len(set(alturas)) >= 5 and all(en_escala(s.m, n) for n in alturas),
               f"teclas que suben: las notas suben y caen en la escala {alturas}")

    print("\nGrabar y loop (en pasos)")
    s = Sesion(base(estilo="arpegio3", pasos=32))
    s.pulsos(COMPAS // 2)  # a mitad del compás 1 (pulso 47)
    s.m.tocado.accion("grabar", s.m.tick)
    s.pulsos(COMPAS // 2)  # hasta el último pulso del compás
    todo &= ok(s.m.tocado.estado == "armado", "Grabar espera el próximo compás")
    s.pulsos(2 * COMPAS, ritmo(2))  # 32 pasos = 2 compases, desde el uno
    s.pulsos(1)
    todo &= ok(s.m.tocado.estado == "loop" and len(s.m.tocado.grabadas) == 8, f"después de 32 pasos queda en loop ({len(s.m.tocado.grabadas)} notas)")
    desde = s.m.tick
    s.pulsos(8 * COMPAS)
    lugares = sorted({(t - desde) % COMPAS for t, _, _ in s.notas(desde)})
    todo &= ok(lugares == [0, 12, 36, 72], f"el loop repite tu ritmo: pulsos {lugares}")
    todo &= ok(s.colgadas() == len(s.m.tocado.sonando), "sin notas colgadas (solo las que están sonando)")
    primera = [n for _, n, _ in s.notas(desde)]
    cfg = json.loads(json.dumps(s.m.base))
    cfg["tocado"]["seed"] = "OTRA"
    s.m.aplicar_config(normalizar(cfg))
    desde2 = s.m.tick
    s.pulsos(8 * COMPAS)
    segunda = s.notas(desde2)
    todo &= ok(sorted({(t - desde2) % COMPAS for t, _, _ in segunda}) == lugares and [n for _, n, _ in segunda] != primera,
               "otra variante: mismas posiciones, otras notas")
    s.m.tocado.accion("parar", s.m.tick)
    antes = len(s.notas())
    s.pulsos(2 * COMPAS)
    todo &= ok(len(s.notas()) == antes and s.m.tocado.estado == "pausa", "Parar: el loop calla")
    s.m.tocado.accion("seguir", s.m.tick)
    s.pulsos(COMPAS)
    todo &= ok(len(s.notas()) > antes, "Seguir: vuelve")
    s.m.stop()
    todo &= ok(s.colgadas() == 0, "al parar el reloj no queda nada colgado")

    # Un loop de 3 pasos: se repite cada 3 semicorcheas (polirritmo contra el compás).
    s3 = Sesion(base(pasos=3))
    s3.pulsos(COMPAS - 1)
    s3.m.tocado.accion("grabar", s3.m.tick)
    s3.pulsos(1)
    s3.pulsos(18, {0: [(60, 100, 4)]})
    desde = s3.m.tick
    s3.pulsos(COMPAS)
    todo &= ok(s3.m.tocado.largo == 18 and sorted({(t - desde) % 18 for t, _, _ in s3.notas(desde)}) == [(18 - (desde % 18)) % 18 if False else ((s3.m.tocado.inicio - desde) % 18)],
               "un loop de 3 pasos se repite cada 3 semicorcheas")

    print("\nCuantización")
    def grabar_fuera(modo):
        s = Sesion(base(pasos=16, cuantizar=modo))
        s.pulsos(COMPAS - 1)
        s.m.tocado.accion("grabar", s.m.tick)
        # Notas corridas: 2 pulsos tarde en el paso 0, 2 antes del paso 3, 1 tarde en el paso 8.
        s.pulsos(COMPAS + 2, {1 + 2: [(60, 100, 5)], 1 + 16: [(60, 90, 7)], 1 + 49: [(60, 80, 4)]})
        return [g[:2] for g in s.m.tocado.grabadas]
    todo &= ok(grabar_fuera("estricta") == [(0, 6), (18, 6), (48, 6)], f"estricta: a la semicorchea {grabar_fuera('estricta')}")
    todo &= ok(grabar_fuera("libre") == [(2, 5), (16, 7), (49, 4)], f"libre: tal cual {grabar_fuera('libre')}")
    suave = grabar_fuera("suave")
    todo &= ok([q for q, _ in suave] == [1, 17, 48], f"suave: a mitad de camino {suave}")
    s8 = Sesion(base(pasos=16, cuantizar="estricta", grilla=8))
    s8.pulsos(COMPAS - 1)
    s8.m.tocado.accion("grabar", s8.m.tick)
    s8.pulsos(COMPAS + 2, {1 + 4: [(60, 100, 30)], 1 + 16: [(60, 90, 7)], 1 + 49: [(60, 80, 4)]})
    g8 = [g[:2] for g in s8.m.tocado.grabadas]
    todo &= ok(g8 == [(0, 12), (12, 12), (48, 12)], f"estricta a corcheas: todo cae en corcheas y nada se monta sobre la siguiente {g8}")
    swing = grabar_fuera("swing")
    todo &= ok([q for q, _ in swing] == [0, 20, 48], f"swing: las del contratiempo un poco tarde {swing}")
    sa = Sesion(base(pasos=16))
    sa.pulsos(COMPAS - 5)
    sa.m.tocado.accion("grabar", sa.m.tick)
    sa.pulsos(5, {2: [(60, 100, 2)]})   # tocada 2 pulsos antes del uno y soltada antes
    sa.pulsos(COMPAS + 1)
    todo &= ok(sa.m.tocado.grabadas and sa.m.tocado.grabadas[0][0] == 0, f"una nota tocada justo antes del uno cuenta desde el uno {sa.m.tocado.grabadas}")

    print("\nLo grabado se guarda")
    texto = s.m.tocado.serializar()
    todo &= ok(texto and s.m.tocado.cambio_loop, "al terminar de grabar pide guardarlo")
    cfg = json.loads(json.dumps(s.m.base))
    cfg["tocado"]["loop"] = texto
    nueva = Sesion(normalizar(cfg))
    todo &= ok(nueva.m.tocado.estado == "loop" and len(nueva.m.tocado.grabadas) == 8, "al prender con la configuración guardada, el loop vuelve")
    nueva.pulsos(COMPAS + 1)
    todo &= ok(sorted({t % COMPAS for t, _, _ in nueva.notas()}) == lugares, "y suena con tu ritmo desde el uno")
    from goa import forma
    escena = forma.escena_de(normalizar(cfg), "con loop")
    todo &= ok(json.loads(escena["datos"])["tocado"]["loop"] == texto, "las escenas guardan el loop")
    cfg_vacia = json.loads(json.dumps(cfg))
    cfg_vacia["tocado"]["loop"] = ""
    nueva.m.aplicar_config(normalizar(cfg_vacia))
    nueva.pulsos(COMPAS)
    todo &= ok(nueva.m.tocado.estado == "libre" and not nueva.m.tocado.grabadas, "una escena sin loop lo saca")
    nueva.m.aplicar_config(normalizar(cfg))
    nueva.pulsos(COMPAS)
    todo &= ok(nueva.m.tocado.estado == "loop" and nueva.m.tocado.inicio % COMPAS == 0, "y una con loop lo trae, desde el uno del compás")

    print("\nCambio de acorde con una nota larga")
    s = Sesion(base(estilo="bajo"))
    s.pulsos(COMPAS)
    s.m.tocado_on(60, 100)
    reataques = 0
    for _ in range(16):
        clases = s.m._momento_tocado(max(s.m.tick, 0) // 6)
        s.pulsos(COMPAS)
        sonando = list(s.m.tocado.sonando)
        m = s.m._momento_tocado(max(s.m.tick, 0) // 6)
        if m is not None and sonando and all(n % 12 in m.clases for n in sonando):
            reataques += 1
        del clases
    s.m.tocado_off(60)
    todo &= ok(reataques == 16, "una larga sostenida siempre queda en el acorde que suena (se vuelve a atacar si choca)")
    todo &= ok(s.colgadas() == 0, "y al soltarla no queda colgada")

    print("\nSalida")
    todo &= ok("FM-1" in salidas(base()), "abre la salida elegida")
    print("\nTodo bien" if todo else "\nHAY FALLAS")
    raise SystemExit(0 if todo else 1)


if __name__ == "__main__":
    main()
