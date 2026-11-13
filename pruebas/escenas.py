"""Prueba escenas, transiciones graduales, el acorde puente y la energía, sin hardware.

  python3 -m pruebas.escenas            desde la carpeta goa-engine
"""

import copy
import tomllib

from goa import armonia, forma
from goa.config import a_toml, normalizar
from goa.escalas import Tonalidad
from goa.motor import Motor

from .dialogo import base, colgadas, ok

NOTA_LARGA = 41  # F2


def armar():
    cfg = normalizar(base())
    cfg["dialogo"]["activo"] = False
    cfg["pads"].update(activo=True, disparo=2, cambia_cada=4, suspensiones=0.0, rasgueo=1, salida="PADS", base="tonica")
    cfg["secuencia"][0].update(activa=True, disparo=2, salida="SEC", densidad=0.6)
    cfg["bajo"].update(activo=False, disparo=2, salida="BAJO")
    return cfg


class Prueba:
    """Motor andando con la nota larga; guarda (tick, salida, tipo, canal, nota, vel)."""

    def __init__(self, cfg):
        self.ev = []
        self.m = Motor(cfg, lambda sal, tipo, canal, nota, vel: self.ev.append((self.m.tick, sal, tipo, canal, nota, vel)))
        self.m.start()
        self.tick = 0
        self.registro = {}  # compás -> lo que se quiera mirar

    def correr(self, compases, mirar=None):
        for _ in range(compases * 96):
            self.m.reloj()
            p, r = divmod(self.tick, 6)
            if r == 1 and p % 16 == 0:
                self.m.nota_on(1, NOTA_LARGA)
            if mirar and r == 3 and p % 16 == 0:
                self.registro[p // 16] = mirar(self.m)
            self.tick += 1

    def terminar(self):
        self.m.stop()
        return self.ev


if __name__ == "__main__":
    todo = True

    print("Energía")
    cfg = armar()
    todo &= ok(forma.energizar(cfg, 0.5) == cfg, "con 0,5 todo queda tal como lo dejaste")
    baja, alta = forma.energizar(cfg, 0.0), forma.energizar(cfg, 1.0)
    s0, s1 = baja["secuencia"][0], alta["secuencia"][0]
    todo &= ok(s0["densidad"] < cfg["secuencia"][0]["densidad"] < s1["densidad"],
               f"densidad: calma {s0['densidad']} < normal {cfg['secuencia'][0]['densidad']} < clímax {s1['densidad']}")
    poca = copy.deepcopy(cfg)
    poca["secuencia"][0]["densidad"] = 0.2
    todo &= ok(forma.energizar(poca, 1.0)["secuencia"][0]["densidad"] <= 0.35 and forma.energizar(poca, 0.9)["secuencia"][0]["densidad"] < 0.35,
               "una densidad baja sigue siendo baja con la energía arriba (tu ajuste manda)")
    cero = copy.deepcopy(cfg)
    cero["bajo"]["fantasmas"] = 0.0
    todo &= ok(forma.energizar(cero, 1.0)["bajo"]["fantasmas"] == 0.0, "sin notas fantasma, la energía no las inventa")
    todo &= ok(baja["dialogo"]["espacio"] > alta["dialogo"]["espacio"], "en la calma el diálogo deja más espacio")
    todo &= ok(baja["musica"]["tension"] < alta["musica"]["tension"], "más energía, más tensión")
    todo &= ok(baja["pads"]["suspensiones"] > alta["pads"]["suspensiones"], "en la calma, más suspensiones en los pads")
    todo &= ok(normalizar(alta) == alta and normalizar(baja) == baja, "la energía nunca sale de los rangos")

    print("\nLa energía llega de a poco")
    pr = Prueba(armar())
    pr.correr(2)
    nueva = copy.deepcopy(pr.m.base)
    nueva["forma"]["energia"] = 1.0
    pr.m.aplicar_config(nueva)
    pr.correr(7, mirar=lambda m: m.conductor.energia)
    pasos = [pr.registro[c] for c in sorted(pr.registro)]
    subida = pasos[:pasos.index(1.0) + 1]
    todo &= ok(all(0 < b - a <= forma.PASO_ENERGIA + 1e-9 for a, b in zip(subida, subida[1:]))
               and all(x == 1.0 for x in pasos[len(subida):]), "sube un 10 % por compás hasta llegar: " + " → ".join(f"{x:.1f}" for x in pasos))
    pads_antes = [e for e in pr.ev if e[1] == "PADS" and e[2] == "note_on"]
    todo &= ok(len({e[4] for e in pads_antes}) <= 8, "los pads no se rearman en cada paso de la energía")
    todo &= ok(colgadas(pr.terminar()) == 0, "ninguna nota colgada")

    print("\nTransición a una escena (8 compases)")
    origen = armar()
    destino = copy.deepcopy(origen)
    destino["secuencia"][0].update(estilo="arpegio3", densidad=1.0, seed="OTRA-1234")
    destino["bajo"]["activo"] = True
    destino["dialogo"]["activo"] = True
    destino["forma"]["energia"] = 0.8
    escena = forma.escena_de(destino, "Clímax")
    destino = normalizar(forma.mezclar(origen, escena))
    todo &= ok(destino["pads"]["salida"] == "PADS" and destino["bajo"]["activo"], "la escena trae lo musical y deja los destinos")
    pr = Prueba(origen)
    pr.correr(2)
    inicio = pr.m._compas_actual() + 1
    pr.m.lanzar_escena(destino, 8, 0)
    pr.correr(10, mirar=lambda m: (m.secuencias[0].densidad, m.secuencias[0].estilo, m.bajo.activo, m.dialogo.activo))
    reg = {c - inicio: v for c, v in pr.registro.items() if c >= inicio}
    dens = [reg[i][0] for i in range(8)]
    todo &= ok(all(b >= a for a, b in zip(dens, dens[1:])) and dens[0] < dens[-1],
               "la densidad sube de a poco: " + " → ".join(f"{x:.2f}" for x in dens))
    todo &= ok(all(reg[i][1] == "rolling" for i in range(7)) and reg[7][1] == "arpegio3",
               "el estilo cambia recién en el último compás de la transición")
    entra_dialogo = next(i for i in range(8) if reg[i][3])
    entra_bajo = next(i for i in range(8) if reg[i][2])
    todo &= ok(0 < entra_dialogo < entra_bajo < 8, f"los motores entran de a uno: diálogo en el compás {entra_dialogo + 1}, bajo en el {entra_bajo + 1}")
    todo &= ok(pr.m.conductor.transicion is None and pr.m.base == destino, "al terminar queda exactamente la escena")
    todo &= ok(colgadas(pr.terminar()) == 0, "ninguna nota colgada")

    print("\nCambio de tonalidad con acorde puente")
    origen = armar()  # F frigio
    destino = copy.deepcopy(origen)
    destino["musica"].update(tonica="C", escala="menor")
    destino["pads"]["progresion"] = "i_bVI_bVII"
    pr = Prueba(origen)
    pr.correr(3)
    inicio = pr.m._compas_actual() + 1
    pr.m.lanzar_escena(destino, 4, 1)
    pr.correr(6, mirar=lambda m: (m.puente is not None, m.pads.raiz_acorde, frozenset(n % 12 for n in m.pads.sonando)))
    reg = {c - inicio: v for c, v in pr.registro.items() if c >= inicio}
    vieja, nueva = Tonalidad("F", "frigio"), Tonalidad("C", "menor")
    puente = [i for i in range(4) if reg[i][0]]
    todo &= ok(puente == [1, 2], f"el puente suena los 2 compases antes del cambio (compases {[i + 1 for i in puente]})")
    comunes = armonia.clases_de(vieja) & armonia.clases_de(nueva)
    todo &= ok(all(reg[i][2] <= comunes for i in puente),
               "el acorde puente es de las dos tonalidades: " + ", ".join(sorted({str(sorted(reg[i][2])) for i in puente})))
    todo &= ok(reg[3][1] % 12 == nueva.tonica, "en el cambio, la progresión nueva parte en su i (C)")
    todo &= ok(all(reg[i][2] <= armonia.clases_de(nueva) for i in range(3, 6)), "después todo queda en la escala nueva")
    todo &= ok(colgadas(pr.terminar()) == 0, "ninguna nota colgada")

    print("\nCambios de la app durante una transición")
    pr = Prueba(armar())
    pr.correr(2)
    destino = copy.deepcopy(pr.m.base)
    destino["secuencia"][0]["densidad"] = 1.0
    pr.m.lanzar_escena(destino, 8, 2)
    pr.correr(2)
    tocado = copy.deepcopy(pr.m.base)
    tocado["secuencia"][0]["gate"] = 0.9
    pr.m.aplicar_config(tocado)
    todo &= ok(pr.m.conductor.transicion is not None, "la transición sigue")
    pr.correr(8)
    todo &= ok(pr.m.secuencias[0].gate == 0.9 and pr.m.secuencias[0].densidad == 1.0, "y llega con tu cambio incluido")
    todo &= ok(colgadas(pr.terminar()) == 0, "ninguna nota colgada")

    print("\nGuardar escenas en el archivo")
    cfg = armar()
    cfg["escena"] = [forma.escena_de(cfg, "Intro"), forma.escena_de(cfg, "Clímax ñ")]
    leida = normalizar(tomllib.loads(a_toml(cfg)))
    todo &= ok(leida["escena"] == cfg["escena"], "las escenas se guardan y se leen iguales")
    todo &= ok(forma.resumen(cfg["escena"][0]).startswith("Goa"), "resumen: " + forma.resumen(cfg["escena"][0]))

    print("\nTODO BIEN" if todo else "\nHAY ERRORES")
    raise SystemExit(0 if todo else 1)
