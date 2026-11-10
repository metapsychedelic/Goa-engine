"""Prueba los perfiles de género, el pulso de los pads y Pegado ↔ Desplazado, sin hardware.

  python3 -m pruebas.generos            desde la carpeta goa-engine
"""

import tomllib

from goa import generos
from goa.config import a_toml, normalizar
from goa.escalas import Tonalidad
from goa.motor import Motor

from .dialogo import base, colgadas, correr, grilla, max_simultaneas, ok


def con_genero(genero, **dialogo):
    cfg = normalizar(generos.aplicar(base(**dialogo), genero))
    cfg["pads"].update(activo=True, disparo=2)
    return cfg


def notas_de(salida, sal, canal):
    return [(t, n) for t, s, tipo, c, n, _ in salida if tipo == "note_on" and s == sal and c == canal]


if __name__ == "__main__":
    todo = True

    print("Perfiles de género")
    original = base()
    for genero in generos.ORDEN:
        cfg = con_genero(genero)
        Motor(cfg, lambda *a: None)
        salida, _ = correr(cfg)
        escala = set(Tonalidad(cfg["musica"]["tonica"], cfg["musica"]["escala"]).intervalos)
        ons = [n for _, _, tipo, _, n, _ in salida if tipo == "note_on"]
        en_escala = all((n - 5) % 12 in escala for n in ons)
        todo &= ok(ons and en_escala and colgadas(salida) == 0,
                   f"{generos.GENEROS[genero]['nombre']:<14} {cfg['musica']['escala']:<8} "
                   f"pads {cfg['pads']['progresion']:<13} · {len(ons)} notas, en la escala, sin colgadas")
    cfg = con_genero("ambient")
    todo &= ok(cfg["musica"]["escala"] == "lidio" and cfg["pads"]["drone"] and cfg["pads"]["rasgueo"] == 24,
               "ambient: lidia, drone y voces que entran de a una")
    todo &= ok(cfg["secuencia"] == original["secuencia"], "el género no toca las secuencias")
    todo &= ok(all(cfg[v][k] == original[v][k] for v in ("llamada", "respuesta") for k in ("salida", "canal", "velocidad"))
               and cfg["pads"]["salida"] == original["pads"]["salida"] and cfg["dialogo"]["seed"] == original["dialogo"]["seed"],
               "ni los destinos, canales, fuerza ni variantes")

    desacoplado = base()
    desacoplado["pads"]["genero_propio"] = True
    cfg = generos.aplicar(desacoplado, "chillout")
    todo &= ok(cfg["pads"] == desacoplado["pads"] and cfg["musica"]["genero"] == "chillout",
               "pads desacoplados: el género general no los cambia")
    cfg = generos.aplicar(cfg, "ambient", solo_pads=True)
    todo &= ok(cfg["pads"]["progresion"] == "pedal_I_II" and cfg["pads"]["genero"] == "ambient"
               and cfg["musica"]["escala"] == "menor" and cfg["dialogo"]["rejilla"] == "corcheas",
               "su propio género cambia solo los pads (ambient sobre chillout)")
    todo &= ok(normalizar(tomllib.loads(a_toml(normalizar(cfg)))) == normalizar(cfg), "se guarda y se lee igual")

    print("\nPegado ↔ Desplazado (llamada y respuesta)")
    cfg = base()
    cfg["musica"]["desplazamiento"] = 0.0
    s0, _ = correr(cfg)
    todo &= ok(all(t % 12 in (0, 1) for t, _, tipo, *_ in s0 if tipo == "note_on"), "en 0 todo cae en corcheas")
    cfg = base()
    cfg["musica"]["desplazamiento"] = 1.0
    s1, _ = correr(cfg)
    ons = [t for t, _, tipo, *_ in s1 if tipo == "note_on"]
    for c in (0, 4, 8):
        print(f"  compás {c + 1:>2}: {grilla(s1, cfg, c)}")
    todo &= ok(any(t % 12 >= 6 for t in ons), "en 100 % hay notas corridas a semicorcheas débiles")
    todo &= ok(all(grilla(s1, cfg, c)[0] == "L" and any(t == c * 96 or t == c * 96 + 1 for t in ons) for c in range(16)),
               "el uno de la llamada nunca se mueve")
    todo &= ok(max_simultaneas(s1) == 1 and colgadas(s1) == 0, "no se pisan y no quedan notas colgadas")
    todo &= ok(correr(cfg)[0] == s1, "misma variante, mismo desplazamiento")
    mono = base()
    mono["musica"]["desplazamiento"] = 1.0
    mono["respuesta"].update(salida=mono["llamada"]["salida"], canal=mono["llamada"]["canal"])
    mono["llamada"]["gate"] = mono["respuesta"]["gate"] = 1.0
    todo &= ok(max_simultaneas(correr(mono)[0]) == 1, "mismo sinte y largo 100 %: aun corridas, nunca dos notas juntas")
    cfg = base()
    cfg["musica"]["desplazamiento"] = 1.0
    cfg["llamada"]["desplazamiento"] = 0.0
    s2, _ = correr(cfg)
    llamada = notas_de(s2, cfg["llamada"]["salida"], cfg["llamada"]["canal"] - 1)
    todo &= ok(all(t % 12 in (0, 1) for t, _ in llamada), "una voz con ajuste propio en 0 sigue pegada aunque el general esté en 100 %")

    print("\nPulso de los pads")

    def pads(pulso, desplazamiento, compases=12, **extra):
        cfg = base()
        cfg["dialogo"]["activo"] = False
        cfg["musica"]["desplazamiento"] = desplazamiento
        cfg["pads"].update(activo=True, disparo=2, pulso=pulso, cambia_cada=4, variacion=0.0, **extra)
        salida, motor = correr(cfg, compases=compases)
        return [e for e in salida if e[1] == cfg["pads"]["salida"]], cfg
    s3, cfg = pads(3, 0.0)
    golpes = sorted({t for t, _, tipo, *_ in s3 if tipo == "note_on" and t >= 96})
    pasos = sorted({(t % 96) // 6 for t in golpes})  # con rasgueo, las voces entran a 1 pulso de distancia
    todo &= ok(pasos == [0, 6, 12], f"3 golpes por compás en corcheas: pasos {pasos} (el primero en el uno)")
    todo &= ok(colgadas(s3) == 0, "sin notas colgadas")
    sonando, pisa = set(), False
    for t, _, tipo, _, n, _ in s3:
        if tipo == "note_on":
            pisa |= n in sonando
            sonando.add(n)
        else:
            sonando.discard(n)
    todo &= ok(not pisa, "un golpe termina antes del siguiente")
    acordes = {t // 96 // 4: frozenset(n for tt, _, tipo, _, n, _ in s3 if tipo == "note_on" and tt // 6 == t // 6)
               for t in golpes if t % 96 == 0}
    todo &= ok(len(set(acordes.values())) == 2, "cambia de acorde cada 4 compases y el uno ya suena con el acorde nuevo")
    s4, _ = pads(3, 1.0, compases=16)
    corridos = {t % 96 for t, _, tipo, *_ in s4 if tipo == "note_on" and t >= 96}
    todo &= ok(any(p % 12 != 0 for p in corridos) and colgadas(s4) == 0,
               "desplazado: algunos golpes se corren y siguen sin colgarse")
    todo &= ok(min(t % 96 for t, _, tipo, *_ in s4 if tipo == "note_on" and t >= 96) == 0, "el golpe del uno no se mueve")
    s5, _ = pads(0, 0.0, compases=4, rasgueo=24, voces=4)
    entradas = sorted(t for t, _, tipo, *_ in s5 if tipo == "note_on")[:4]
    todo &= ok([b - a for a, b in zip(entradas, entradas[1:])] == [24, 24, 24], "rasgueo 24: una voz por tiempo")

    print("\nTodo bien" if todo else "\nHay errores")
    raise SystemExit(0 if todo else 1)
