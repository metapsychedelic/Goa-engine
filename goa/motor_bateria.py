"""El motor toca la batería de la Circuit en los rises y fills (goa/bateria.py).

Un «plan» es una transición en curso: {"clave", "inicio", "fin" (pasos absolutos), "ev"
(golpes por paso relativo), "tipo", "nombre"}. Rise: los últimos `bateria_compases` de la
subida. Fill: los últimos `bateria_largo` pasos de una parte cuyo final lleva fill. Al terminar
(o en Stop) cada Drum vuelve a su sample normal y su pitch a 64.
"""

import logging

from . import bateria
from .secuencia import PASOS_POR_COMPAS, TICKS_POR_PASO

log = logging.getLogger(__name__)

# Si no se puede cambiar el sample (no sé el normal del Drum), los toms se hacen con pitch.
PITCH_TOM = {53: 76, 54: 64, 55: 52}


class BateriaMotor:
    def _bateria_reiniciar(self):
        self.bateria_plan = None
        self.bateria_pend = []        # [(tick, salida, canal, nota, vel)] golpes en mitad de paso y note_off
        self.bateria_estado = {}      # drum -> {"sample": valor mandado, "pitch": valor mandado}
        self.bateria_veces = {}       # nombre de la transición -> cuántas veces sonó
        self.bateria_prueba = None    # (clase, transición) pedida con «Probar»: suena en el próximo compás

    def probar_bateria(self, clase, t):
        """«Probar» de la app: el rise o fill `t` suena desde el próximo compás, sin la canción.
        Fill: en los últimos pasos de ese compás. Rise: sus `bateria_compases` compases."""
        if clase not in ("rise", "fill"):
            raise ValueError("Solo los rises y los fills tienen batería")
        if not t.get("bateria"):
            raise ValueError("Elige primero un tipo de batería")
        if not self.corriendo:
            raise ValueError("Dale Play primero: suena en el próximo compás")
        self.bateria_prueba = (clase, dict(t))

    def _bateria_cfg(self):
        b = (self.config or {}).get("bateria") or {}
        return b.get("salida", "Circuit"), int(b.get("canal", 10)) - 1, b

    def _bateria_transicion(self, clase, nombre):
        for t in (self.base or {}).get(clase, []) or []:
            if t.get("nombre") == nombre:
                return t
        return None

    def _bateria_planear(self, paso):
        """Primer paso de cada compás: ¿empieza (o ya está por empezar) un rise o un fill?"""
        compas = paso // PASOS_POR_COMPAS
        base = self.base or {}
        parte = self.conductor.parte(base, compas)
        datos = base["parte"][parte["i"]] if parte is not None and parte["i"] < len(base.get("parte", [])) else None
        fin_parte = None if parte is None else (compas - parte["dentro"] + parte["largo"]) * PASOS_POR_COMPAS
        # Rise de la canción: los últimos compases de la parte (haya o no riser de FX)
        sub = self.subida
        if datos is not None and datos.get("final") == "rise" and (sub is None or sub["origen"] != "manual"):
            t = self._bateria_transicion("rise", datos.get("final_rise"))
            if t and t.get("bateria"):
                inicio = max(fin_parte - parte["largo"] * PASOS_POR_COMPAS,
                             fin_parte - int(t.get("bateria_compases", 4)) * PASOS_POR_COMPAS)
                if inicio // PASOS_POR_COMPAS <= compas:
                    return self._bateria_nuevo("rise", t, inicio, fin_parte)
        # Subida pedida a mano (o del piloto): el rise elegido para el modo libre
        elif sub is not None:
            b = (self.config or {}).get("bateria") or {}
            t = self._bateria_transicion("rise", b.get("rise_libre", ""))
            if t and t.get("bateria"):
                fin = sub["hasta"]
                inicio = max(sub["desde"], fin - int(t.get("bateria_compases", 4)) * PASOS_POR_COMPAS)
                return self._bateria_nuevo("rise", t, inicio, fin)
        # Fill: últimos pasos de la parte
        if datos is not None and datos.get("final") in ("fill", "fill_break"):
            t = self._bateria_transicion("fill", datos.get("final_fill"))
            if t and t.get("bateria"):
                inicio = fin_parte - int(t.get("bateria_largo", 8))
                if inicio // PASOS_POR_COMPAS == compas:
                    return self._bateria_nuevo("fill", t, inicio, fin_parte)
        return None

    def _bateria_nuevo(self, clase, t, inicio, fin):
        clave = (clase, t["nombre"], inicio, fin)
        if self.bateria_plan is not None and self.bateria_plan["clave"] == clave:
            return self.bateria_plan
        vez = self.bateria_veces.get(t["nombre"], 0)
        self.bateria_veces[t["nombre"]] = vez + 1
        if clase == "rise":
            tipo, ev = bateria.rise(t, fin - inicio, vez)
        else:
            tipo, ev = bateria.fill(t, vez)
        log.info("Batería: %s «%s» (%s), %d pasos", clase, t["nombre"], tipo, fin - inicio)
        return {"clave": clave, "inicio": inicio, "fin": fin, "ev": ev, "tipo": tipo, "nombre": t["nombre"]}

    def _paso_bateria(self, paso):
        if paso % PASOS_POR_COMPAS == 0 and self.bateria_prueba is not None:
            clase, t = self.bateria_prueba
            self.bateria_prueba = None
            if clase == "rise":
                inicio, fin = paso, paso + int(t.get("bateria_compases", 4)) * PASOS_POR_COMPAS
            else:
                fin = paso + PASOS_POR_COMPAS
                inicio = fin - int(t.get("bateria_largo", 8))
            if self.bateria_plan is not None:
                self._bateria_soltar()
            plan = self._bateria_nuevo(clase, t, inicio, fin)
            plan["clave"] = ("prueba",) + plan["clave"]
            self.bateria_plan = plan
        en_prueba = self.bateria_plan is not None and self.bateria_plan["clave"][0] == "prueba"
        if paso % PASOS_POR_COMPAS == 0 and not en_prueba:
            plan = self._bateria_planear(paso)
            if plan is None and self.bateria_plan is not None and paso < self.bateria_plan["fin"]:
                if self.bateria_plan["clave"][0] == "rise":
                    self._bateria_soltar()   # la subida se canceló o la parte cambió: se corta
            elif plan is not None:
                if self.bateria_plan is not None and self.bateria_plan["clave"] != plan["clave"]:
                    self._bateria_soltar()
                self.bateria_plan = plan
        plan = self.bateria_plan
        if plan is None:
            return
        if paso >= plan["fin"]:
            self._bateria_soltar()
            return
        if paso < plan["inicio"]:
            return
        salida, canal, b = self._bateria_cfg()
        for g in plan["ev"].get(paso - plan["inicio"], ()):
            self._bateria_preparar(g, salida, canal, b)
            nota = bateria.NOTAS[g.drum]
            vel = max(1, min(127, int(g.vel)))
            if g.medio:
                self.bateria_pend.append((self.tick + TICKS_POR_PASO // 2, salida, canal, nota, vel))
            else:
                self.enviar(salida, "note_on", canal, nota, vel)
                self.bateria_pend.append((self.tick + 1, salida, canal, nota, 0))

    def _bateria_preparar(self, g, salida, canal, b):
        """Sample y pitch del Drum antes del golpe (solo si cambian)."""
        st = self.bateria_estado.setdefault(g.drum, {})
        pitch = g.pitch
        if g.sample is not None:
            if int(b.get(f"sample_d{g.drum}", -1)) >= 0:
                if st.get("sample") != g.sample:
                    self.enviar(salida, "control_change", canal, bateria.CC_SAMPLE[g.drum], int(g.sample))
                    st["sample"] = g.sample
            elif pitch is None and g.sample in PITCH_TOM:
                pitch = PITCH_TOM[g.sample]
        if pitch is not None:
            pitch = max(0, min(127, int(pitch)))
            if st.get("pitch") != pitch:
                self.enviar(salida, "control_change", canal, bateria.CC_PITCH[g.drum], pitch)
                st["pitch"] = pitch

    def _bateria_tick(self):
        if not self.bateria_pend:
            return
        quedan = []
        for p in self.bateria_pend:
            if p[0] <= self.tick:
                _, salida, canal, nota, vel = p
                if vel:
                    self.enviar(salida, "note_on", canal, nota, vel)
                    quedan.append((self.tick + 1, salida, canal, nota, 0))
                else:
                    self.enviar(salida, "note_off", canal, nota, 0)
            else:
                quedan.append(p)
        self.bateria_pend = quedan

    def _bateria_soltar(self):
        """Fin de la transición: cada Drum vuelve a su sample normal y a pitch 64."""
        salida, canal, b = self._bateria_cfg()
        for _, s, c, nota, vel in self.bateria_pend:
            if not vel:
                self.enviar(s, "note_off", c, nota, 0)
        self.bateria_pend = []
        for drum, st in self.bateria_estado.items():
            if "sample" in st:
                normal = int(b.get(f"sample_d{drum}", -1))
                if normal >= 0:
                    self.enviar(salida, "control_change", canal, bateria.CC_SAMPLE[drum], normal)
            if st.get("pitch", 64) != 64:
                self.enviar(salida, "control_change", canal, bateria.CC_PITCH[drum], 64)
        self.bateria_estado = {}
        self.bateria_plan = None
