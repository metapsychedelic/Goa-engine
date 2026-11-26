"""Filtro compartido de los rises (módulo «Rises y fills», etapa 3).

Un rise con `filtro` cierra a la vez los filtros de los que elijas (`filtro_quienes`) y los
va abriendo juntos hasta el drop: parten en `filtro_desde` y llegan a `filtro_hasta` justo en
el último paso. En el drop cada uno vuelve a su reposo (las secuencias y el Tocado al suyo,
el filtro maestro de la Circuit a 64 = apagado, el bajo con filtro automático sigue con el
suyo); los que no tienen reposo conocido (Synth 1 y 2 de la Circuit, pads, un bajo sin
filtro automático) se quedan en `filtro_hasta`.

Mientras dura, ese filtro es solo del rise: el LFO de la secuencia, el filtro de su subida,
el del FX y el filtro maestro de la Circuit en las subidas esperan.
"""

import logging

from .secuencia import PASOS_POR_COMPAS

log = logging.getLogger(__name__)

CURVA = 1.6      # abre lento al principio y rápido al final, como los filtros de la subida
CC_SYNTH = 74    # Circuit Tracks: frecuencia del filtro de Synth 1 y 2 (canales 1 y 2)


def quienes(t):
    return [q.strip() for q in str(t.get("filtro_quienes", "")).split(",") if q.strip()]


class FiltroMotor:
    def _filtro_grupo_reiniciar(self):
        self.filtro_grupo = None    # {"clave", "inicio", "fin", "voces": [...], "nombre"}

    def _filtro_voces(self, t):
        """Lo que se filtra, según el estado de los motores: (id, salida, canal, cc, desde, hasta, reposo)."""
        desde, hasta = int(t.get("filtro_desde", 15)), int(t.get("filtro_hasta", 127))
        cfg = self.config or {}
        c = cfg.get("circuit") or {}
        voces = []
        for q in quienes(t):
            if q == "circuit":
                # Filtro maestro: 64 = apagado, menos = pasa bajos. Cerrado = desde/2.
                voces.append((q, c.get("salida", "Circuit"), int(c.get("canal_control", 16)) - 1, 74,
                              max(0, min(63, desde // 2)), 64, 64))
            elif q in ("circuit_s1", "circuit_s2"):
                voces.append((q, c.get("salida", "Circuit"), 0 if q == "circuit_s1" else 1, CC_SYNTH, desde, hasta, None))
            elif q == "bajo" and self.bajo is not None and self.bajo.salida:
                b = self.bajo
                voces.append((q, b.salida, b.canal, b.filtro_cc, desde, hasta, "bajo" if getattr(b, "filtro", False) else None))
            elif q == "pads" and self.pads is not None and getattr(self.pads, "salida", None):
                voces.append((q, self.pads.salida, self.pads.canal, 74, desde, hasta, None))
            elif q == "tocado":
                f = self.tocado.filtro if self.tocado is not None else None
                if f is not None and getattr(f, "salida", None):
                    voces.append((q, f.salida, f.canal, f.cc_filtro, desde, hasta, f.filtro_reposo))
            elif q.startswith("sec:"):
                for s in self.secuencias:
                    if s.nombre == q[4:] and s.activa:
                        voces.append((q, s.salida, s.canal, s.cc_filtro, desde, hasta, s.filtro_reposo))
        return voces

    def _paso_filtro_grupo(self, paso):
        compas = paso // PASOS_POR_COMPAS
        if paso % PASOS_POR_COMPAS == 0:
            plan = None
            prueba = getattr(self, "filtro_prueba", None)
            if prueba is not None and paso >= prueba[2]:
                self.filtro_prueba = prueba = None
            rise = (prueba if prueba is not None and paso >= prueba[1] else None) or self._rise_en_curso(compas)
            if rise is not None and rise[0].get("filtro") and quienes(rise[0]):
                t, primero, fin = rise
                inicio = max(primero, fin - int(t.get("filtro_compases", 8)) * PASOS_POR_COMPAS)
                if inicio // PASOS_POR_COMPAS <= compas < fin // PASOS_POR_COMPAS:
                    plan = (t["nombre"], inicio, fin)
            g = self.filtro_grupo
            if g is not None and (plan is None or plan != g["clave"]) and paso < g["fin"]:
                self._soltar_filtro_grupo()   # la subida se canceló o cambió
            if plan is not None and (self.filtro_grupo is None or self.filtro_grupo["clave"] != plan):
                voces = self._filtro_voces(rise[0])
                self.filtro_grupo = {"clave": plan, "inicio": plan[1], "fin": plan[2], "voces": voces, "enviado": {}}
                log.info("Filtro compartido «%s»: %s", plan[0], ", ".join(v[0] for v in voces) or "nadie")
        g = self.filtro_grupo
        if g is None:
            return
        if paso >= g["fin"]:
            self._soltar_filtro_grupo()
            return
        if paso < g["inicio"]:
            return
        largo = max(1, g["fin"] - g["inicio"] - 1)
        x = max(0.0, min(1.0, (paso - g["inicio"]) / largo)) ** CURVA
        for v in g["voces"]:
            _, salida, canal, cc, desde, hasta, _ = v
            valor = round(desde + (hasta - desde) * x)
            clave = (salida, canal, cc)
            if g["enviado"].get(clave) != valor:
                g["enviado"][clave] = valor
                self.enviar(salida, "control_change", canal, cc, valor)

    def filtro_grupo_tiene(self, salida, canal, cc):
        """¿Ese filtro lo maneja ahora el rise? (los demás que lo mueven esperan)."""
        g = self.filtro_grupo
        return g is not None and any((v[1], v[2], v[3]) == (salida, canal, cc) for v in g["voces"])

    def _soltar_filtro_grupo(self):
        g, self.filtro_grupo = self.filtro_grupo, None
        if g is None:
            return
        for _, salida, canal, cc, _, hasta, reposo in g["voces"]:
            clave = (salida, canal, cc)
            if clave not in g["enviado"]:
                continue
            if reposo == "bajo":
                if self.bajo is not None:
                    self.bajo.filtro_ultimo = None   # su filtro automático vuelve a mandar el suyo
                continue
            valor = hasta if reposo is None else reposo
            if g["enviado"][clave] != valor:
                self.enviar(salida, "control_change", canal, cc, valor)
