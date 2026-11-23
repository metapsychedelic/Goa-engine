"""La forma de la música dentro del motor: escenas, modo canción, subidas, drops y
los efectos de cada parte. Es una parte de la clase Motor (se mezcla en ella), separada
de motor.py para que cada archivo se pueda leer de una vez.
"""

import logging

from . import armonia, copia, forma, fx, generador
from .azar import azar as azar_fijo
from .escalas import Tonalidad
from .pads import _cerca, progresion_aleatoria, raiz_tension
from .secuencia import PASOS_POR_COMPAS, TICKS_POR_PASO

log = logging.getLogger("goa")


class FormaMotor:
    """Métodos de Motor sobre escenas, canción y subidas (usa el estado de Motor)."""

    def _compas_actual(self):
        return max(self.tick, 0) // (TICKS_POR_PASO * PASOS_POR_COMPAS)

    def saltar_seccion(self, clave):
        """Piloto: pasa a la sección `clave` en el próximo compás."""
        if clave not in forma.PLAN:
            raise ValueError(f"Sección desconocida: {clave}")
        self.conductor.saltar_a = clave

    def saltar_parte(self, indice):
        """Canción: pasa a la parte `indice` en el próximo compás (para volver a cuadrar con la Circuit)."""
        if not (0 <= indice < len(self.base.get("parte", []))):
            raise ValueError("Esa parte no existe")
        r = forma.rango_loop(self.base)   # saltar toma el loop que está marcado ahora
        if r and not r[0] <= indice <= r[1]:
            raise ValueError("Esa parte está fuera del loop: quita el loop para ir a ella")
        self.saltar_parte_a = indice

    def quedarse_parte(self, compases=16):
        """Canción: la parte que suena dura `compases` más (lo que viene espera). Si la
        siguiente ya venía entrando, la actual vuelve en el próximo compás."""
        c = self.conductor
        compas = self._compas_actual()
        ahora = c.parte(self.base, compas) if self.corriendo else None
        if ahora is None:
            raise ValueError("La canción no está sonando")
        compases = max(1, min(64, int(compases)))
        inicio = compas - ahora["dentro"]
        fin = inicio + ahora["largo"]
        extra = c.cancion.get("extra")
        if extra is not None and extra["inicio"] == inicio:
            extra["n"] += compases
            extra["fin"] += compases
        else:
            c.cancion["extra"] = {"inicio": inicio, "fin": fin + compases, "n": compases, "i": ahora["i"], "vuelta": ahora["vuelta"]}
        if c.cancion.get("lanzada") == fin:
            c.cancion["lanzada"] = None
            self.relanzar_parte = True
        log.info("Canción: %s se queda %d compases más", self.base["parte"][ahora["i"]]["nombre"], compases)

    def _config_parte(self, indice):
        """La configuración de la parte `indice`: lo que suena ahora con el carácter de su escena."""
        from .config import normalizar  # aquí para no importar en círculo
        p = self.base["parte"][indice]
        if p["escena"] < 0 or p["escena"] >= len(self.base.get("escena", [])):
            return None  # sin escena: sigue lo que suena
        destino = normalizar(forma.mezclar(self.base, self.base["escena"][p["escena"]]))
        destino["forma"]["escena"] = p["escena"]
        return destino

    def _looper_parte_siguiente(self, compas):
        """Modo canción: si la parte siguiente empieza en el próximo compás, el looper de su
        escena (para pedir su loop un compás antes; una parte que entra de golpe se lanza
        recién en su uno). None si no hay parte nueva justo después."""
        ahora = self.conductor.parte(self.base, compas)
        if ahora is None or ahora["dentro"] != ahora["largo"] - 1:
            return None
        siguiente = self.conductor.parte(self.base, compas + 1)
        if siguiente is None:
            return None
        p = self.base["parte"][siguiente["i"]]
        escenas = self.base.get("escena", [])
        if not 0 <= p["escena"] < len(escenas):
            return None
        datos = escenas[p["escena"]]["datos"]
        datos = forma.json.loads(datos) if isinstance(datos, str) else datos
        if "looper" not in datos:
            return None  # escena de antes del looper: sigue lo que suena
        return dict(self.base.get("looper", {}), **{k: v for k, v in datos["looper"].items() if k not in forma.ENRUTAMIENTO})

    def _avanzar_cancion(self, compas):
        """Primer paso de cada compás, en modo canción: lanza cada parte para que llegue
        completa justo en su primer compás (junto con la escena de la Circuit)."""
        c = self.conductor
        if not forma.cancion_activa(self.base):
            c.cancion = None
            self.saltar_parte_a = None
            return
        partes = self.base["parte"]
        if self.saltar_parte_a is not None:
            r = forma.rango_loop(self.base)
            en_juego, desde = forma.partes_en_juego(self.base, r)
            c.cancion = {"origen": compas - forma.inicio_parte(en_juego, self.saltar_parte_a - desde), "lanzada": None, "loop": r}
            self.saltar_parte_a = None
        if c.cancion is None:
            # La canción parte aquí (en el Start, compás 0); con loop, en la primera parte del loop.
            c.cancion = {"origen": compas, "lanzada": None, "loop": forma.rango_loop(self.base)}
        extra = c.cancion.get("extra")
        if extra is not None and compas >= extra["fin"]:
            c.cancion["origen"] += extra["n"]   # la parte alargada ya terminó: la canción queda corrida
            del c.cancion["extra"]
        ahora = c.parte(self.base, compas)
        if ahora is None:
            return
        inicio_actual = compas - ahora["dentro"]
        objetivo = None
        if getattr(self, "relanzar_parte", False):
            self.relanzar_parte = False
            objetivo = (ahora["i"], compas)   # «quedarse» cuando la siguiente ya entraba: vuelve la actual
        elif ahora["dentro"] == 0 and c.cancion["lanzada"] != compas:
            objetivo = (ahora["i"], compas)  # la parte empieza ya y nadie la lanzó (inicio o salto)
        else:
            fin = inicio_actual + ahora["largo"]  # primer compás de la parte siguiente
            siguiente = c.parte(self.base, fin)
            if siguiente is not None and fin != c.cancion["lanzada"] and (siguiente["i"], siguiente["vuelta"]) != (ahora["i"], ahora["vuelta"]):
                p = partes[siguiente["i"]]
                # Suave: la transición ocupa como mucho la mitad de la parte que suena (que
                # se alcance a escuchar tal como es). Golpe: entra de una en el uno.
                largo_tr = 1 if p["entrada"] == "golpe" else max(1, min(int(self.base["forma"].get("transicion", 8)), ahora["largo"] // 2))
                if compas >= fin - largo_tr + 1:
                    objetivo = (siguiente["i"], fin)
        if objetivo is None:
            return
        indice, llega = objetivo
        c.cancion["lanzada"] = llega
        destino = self._config_parte(indice)
        if destino is None:
            return
        tr = c.transicion
        origen = tr.config(compas) if tr is not None else self.base
        c.lanzar(origen, destino, compas, llega - compas + 1, partes[indice]["escena"], escalonar=False)
        self.base = destino
        self.version_base += 1
        log.info("Canción: %s llega en el compás %d", partes[indice]["nombre"], llega + 1)

    def lanzar_escena(self, destino, compases, indice=None):
        """Pasa a la configuración `destino` (una escena) en `compases` compases, desde el próximo."""
        destino = copia.config(destino)
        if not (self.corriendo and self.tick >= 0):
            self.conductor.reiniciar()
            self.aplicar_config(destino)
            return
        compas = self._compas_actual()
        tr = self.conductor.transicion
        origen = tr.config(compas) if tr is not None else self.base
        self.conductor.lanzar(origen, destino, compas + 1, compases, indice)
        self.base = destino
        self.config_en_cola = destino
        self._looper(self.config)   # si llega en el próximo compás, su loop se pide ya
        log.info("Escena %s: transición de %d compases", indice, compases)

    def _subida_estado(self):
        """La subida de FX en curso (o pedida), para la app."""
        if self.subida_pedida is not None:
            return {"pedida": self.subida_pedida}
        if getattr(self, "subida_final", None):
            return {"pedida": self.subida_final, "final": True}
        if self.subida is None or not self.corriendo:
            return None
        paso = max(self.tick, 0) // TICKS_POR_PASO
        largo = (self.subida["hasta"] - self.subida["desde"]) // PASOS_POR_COMPAS
        return {"compas": (paso - self.subida["desde"]) // PASOS_POR_COMPAS + 1, "largo": largo,
                "origen": self.subida["origen"]}

    def _cancion_estado(self):
        """Dónde va la canción, para la app (None en modo libre)."""
        if not self.base or not forma.cancion_activa(self.base):
            return None
        loop = (self.conductor.cancion or {}).get("loop") if self.corriendo else forma.rango_loop(self.base)
        partes, desde = forma.partes_en_juego(self.base, loop)
        compas = self._compas_actual()
        ahora = self.conductor.parte(self.base, compas) if self.corriendo else None
        if ahora is None:
            return {"parte": None, "total": forma.total_cancion(partes), "loop": loop,
                    "pedida": self.saltar_parte_a}
        siguiente = self.conductor.parte(self.base, compas + ahora["largo"] - ahora["dentro"])
        pos = sum(p["compases"] for p in partes[:ahora["i"] - desde]) + ahora["dentro"]
        extra = (self.conductor.cancion or {}).get("extra")
        mas = extra["n"] if extra is not None else 0
        return {"parte": ahora["i"], "compas": ahora["dentro"] + 1, "largo": ahora["largo"], "extra": mas,
                "vuelta": ahora["vuelta"] + 1, "posicion": pos + 1, "total": forma.total_cancion(partes) + mas,
                "siguiente": siguiente["i"] if siguiente else None, "pedida": self.saltar_parte_a, "loop": loop}

    def _forma_estado(self):
        tr = self.conductor.transicion
        compas = self._compas_actual()
        base = (self.base or {}).get("forma", {})
        sec = self.conductor.seccion(self.base, compas) if self.base and self.corriendo else None
        duracion = base.get("duracion", "normal")
        piloto = None
        if base.get("piloto"):
            piloto = {"plan": [{"clave": k, "nombre": forma.SECCIONES_PILOTO[k]["nombre"],
                                "compases": forma.largo_seccion(k, duracion)} for k in forma.PLAN],
                      "seccion": sec[0] if sec else None, "compas": sec[2] + 1 if sec else None,
                      "largo": sec[3] if sec else None,
                      "siguiente": (forma.PLAN[self.conductor.piloto["i"] + 1] if self.conductor.piloto["i"] + 1 < len(forma.PLAN)
                                    else forma.PLAN[forma.VUELTA]) if sec else None}
        if piloto is not None and sec is not None:
            antes, ahora = forma._motores(self.base), forma._motores(forma.con_piloto(self.base, sec[0], sec[1]))
            piloto["calla"] = [k for k, v in antes.items() if v and not ahora.get(k)]
        return {
            "piloto": piloto,
            "energia": self.conductor.energia if self.conductor.energia is not None else base.get("energia", 0.5),
            "pedida": self.conductor.objetivo(self.base, compas) if self.base else 0.5,
            "escena": base.get("escena", -1),
            "director": self.director.descripcion(self) if self.corriendo else [],
            "transicion": None if tr is None or not self.corriendo else {
                "escena": tr.escena, "compases": tr.compases,
                "faltan": max(0, tr.fin - compas) if compas >= tr.inicio else tr.compases,
                "puente": self.puente is not None},
        }

    def pedir_subida(self, compases):
        """Subida de FX desde la app: empieza en el próximo compás y el drop cae al terminar.
        0 = cancelar (el drop cae en el próximo compás, sin caída)."""
        compases = int(compases)
        if compases not in (0, 4, 8, 16, 32):
            raise ValueError("La subida dura 4, 8, 16 o 32 compases")
        self.subida_final = None
        self.subida_pedida = compases

    def pedir_subida_final(self, compases):
        """Subida que termina justo al final de la parte que suena (sus últimos `compases`):
        espera hasta que falten esos compases. Sin canción, empieza en el próximo compás."""
        compases = int(compases)
        if compases not in (4, 8, 16, 32):
            raise ValueError("La subida dura 4, 8, 16 o 32 compases")
        self.subida_pedida = None
        self.subida_final = compases

    def _subida_auto(self, compas):
        """La subida que piden la canción (parte con riser) o el piloto (build y break)."""
        parte = self.conductor.parte(self.base, compas)
        if parte is not None:
            if not self.base["parte"][parte["i"]].get("riser"):
                return None
            inicio = compas - parte["dentro"]
            fin = inicio + parte["largo"]
            desde = max(inicio, fin - 32)  # como mucho 32 compases de subida
            if compas < desde:
                return None
            return {"desde": desde * PASOS_POR_COMPAS, "hasta": fin * PASOS_POR_COMPAS, "origen": "cancion"}
        sec = self.conductor.seccion(self.base, compas)
        if sec is not None and sec[0] in ("build", "break"):
            desde = compas - sec[2]
            return {"desde": desde * PASOS_POR_COMPAS, "hasta": (desde + sec[3]) * PASOS_POR_COMPAS, "origen": "piloto"}
        return None

    def _compas_subida(self, compas):
        """Primer paso de cada compás: termina la subida (drop), empieza la pedida o la automática."""
        paso = compas * PASOS_POR_COMPAS
        if self.subida is not None and paso >= self.subida["hasta"]:
            self._drop(paso)
        pedida, self.subida_pedida = self.subida_pedida, None
        final = getattr(self, "subida_final", None)
        if final:
            parte = self.conductor.parte(self.base, compas)
            if parte is None:
                pedida, self.subida_final = final, None
            else:
                fin = compas - parte["dentro"] + parte["largo"]
                if compas >= fin - final:
                    self.subida_final = None
                    self.subida = {"desde": paso, "hasta": fin * PASOS_POR_COMPAS, "origen": "manual"}
                    log.info("Subida hasta el final de la parte (%d compases)", fin - compas)
        if pedida == 0:
            if self.subida is not None:
                self._drop(paso, caida=False)
        elif pedida:
            self.subida = {"desde": paso, "hasta": paso + pedida * PASOS_POR_COMPAS, "origen": "manual"}
            log.info("Subida de %d compases", pedida)
        if self.subida is None or self.subida["origen"] != "manual":
            auto = self._subida_auto(compas)
            if auto is not None and auto["hasta"] > paso and (self.subida is None or auto != self.subida):
                self.subida = auto
            elif auto is None and self.subida is not None and self.subida["origen"] != "manual":
                self._drop(paso, caida=False)  # la parte o la sección cambió antes de terminar

    def _drop(self, paso, caida=True):
        """Fin de la subida: el riser se corta, la caída parte y los filtros vuelven a su lugar."""
        self.subida = None
        raiz = self.disparos[self.fx.disparo].raiz
        momento = self._momento(paso, raiz) if raiz is not None else None
        self.fx.drop(self.tick, raiz, momento, self.enviar, caida)
        self._soltar_filtros()

    def _soltar_filtros(self, secuencias=None):
        """Los filtros intervenidos vuelven a su reposo. Con `secuencias`, solo los que ya no se intervienen."""
        siguen = set()
        if secuencias is not None and self.subida is not None:
            siguen = {(s.salida, s.canal, s.cc_filtro) for s in self._con_filtro(secuencias) if s.fx or s.subida_filtro}
        for clave, (valor, reposo) in list(self.cc_secuencias.items()):
            if clave in siguen:
                continue
            if reposo is not None and valor != reposo:  # None: se queda donde llegó
                self.enviar(clave[0], "control_change", clave[1], clave[2], reposo)
            del self.cc_secuencias[clave]

    def _paso_fx(self, paso):
        if not self.fx.activo:
            return
        raiz = self.disparos[self.fx.disparo].raiz
        momento = self._momento(paso, raiz) if raiz is not None else None
        self.fx.paso(paso, self.tick, raiz, momento, self.subida, self.enviar)
        self.fx.tick(self.tick, self.enviar)  # lo que empieza en este paso sale ya, sin un pulso de atraso

    def _paso_texturas(self, paso):
        if not self.texturas.activo:
            return
        raiz = self.disparos[self.texturas.disparo].raiz
        momento = self._momento(paso, raiz) if raiz is not None else None
        self.texturas.paso(paso, self.tick, raiz, momento, self.subida, self.enviar)

    def _con_filtro(self, secuencias):
        """Las secuencias y el Tocado (su filtro en la subida y el FX funcionan igual)."""
        filtro = self.tocado.filtro if self.tocado is not None else None
        return list(secuencias) + ([filtro] if filtro is not None and filtro.activa else [])

    def _filtro_secuencias(self, paso):
        """En la subida, el filtro se va abriendo hasta el drop: en las secuencias con
        «filtro en la subida», de su «desde» a su «hasta»; en las que interviene el FX,
        primero baja y después se abre hasta su «hasta» (127 si no lo cambias)."""
        if self.subida is None:
            return
        t = fx.avance(self.subida, paso)
        for s in self._con_filtro(self.secuencias):
            disparo = getattr(s, "disparo", None)   # el Tocado no tiene disparo: lo tocas tú
            if not ((s.fx or s.subida_filtro) and s.activa) or (disparo is not None and self.disparos[disparo].raiz is None):
                continue
            if s.subida_filtro:
                # El último paso de la subida ya está en «hasta» (el drop cae justo después).
                largo = max(1, self.subida["hasta"] - self.subida["desde"] - 1)
                x = max(0.0, min(1.0, (paso - self.subida["desde"]) / largo))
                valor = round(s.subida_desde + (s.subida_hasta - s.subida_desde) * x ** 1.6)
            else:
                valor = fx.curva_filtro(t, s.filtro_reposo, s.subida_hasta)
            reposo = None if s.subida_filtro and s.subida_despues == "queda" else s.filtro_reposo
            clave = (s.salida, s.canal, s.cc_filtro)
            if self.cc_secuencias.get(clave, (None,))[0] != valor:
                self.cc_secuencias[clave] = (valor, reposo)
                self.enviar(s.salida, "control_change", s.canal, s.cc_filtro, valor)

    def _glitch(self, s, paso):
        """Intervención de FX en una secuencia: (paso del patrón que suena o None, redoble forzado).
        En la segunda mitad de la subida, redobles cada vez más seguidos. Fuera de la subida,
        a veces el último tiempo de la frase se traba en una nota (stutter) o queda en silencio."""
        if not s.fx:
            return None
        locura = max(self.fx.locura, 0.3)
        if self.subida is not None:
            t = fx.avance(self.subida, paso)
            if t >= 0.5 and azar_fijo(f"{s.seed}:fxr:{paso}") < locura * (t - 0.5) * 2.4:
                return None, True
            return None
        compas, lugar = divmod(paso, PASOS_POR_COMPAS)
        if compas % 4 != 3 or lugar < 12:
            return None
        if azar_fijo(f"{s.seed}:fxg:{self.fx.seed}:{compas}") >= self.fx.locura * 0.5:
            return None
        ventana = compas * PASOS_POR_COMPAS + 12
        for k in range(ventana - 1, ventana - 5, -1):
            p = s.patron[k % s.largo]
            if p["suena"] and generador.pasa_posicion(s.posicion, k):
                return k, True  # se traba en la última nota que sonó
        return ventana, False  # no había nota cerca: el tiempo queda en silencio (corte)

    def _scatter_pedido(self, paso):
        """El pad de Scatter que va en `paso` (1-16) o None: suave desde scatter_compases
        antes del final de la parte, intenso en los 2 últimos compases, extremo en el último tiempo."""
        compas = paso // PASOS_POR_COMPAS
        parte = self.conductor.parte(self.base, compas)
        if parte is None:
            return None
        p = self.base["parte"][parte["i"]]
        if not p.get("scatter"):
            return None
        fin = (compas - parte["dentro"] + parte["largo"]) * PASOS_POR_COMPAS
        falta = fin - paso   # pasos que quedan, contando este
        if falta <= 4:
            pad = p.get("scatter_extremo", 16)
        elif falta <= 2 * PASOS_POR_COMPAS:
            pad = p.get("scatter_intenso", 8)
        elif falta <= int(p.get("scatter_compases", 4)) * PASOS_POR_COMPAS:
            pad = p.get("scatter_suave", 1)
        else:
            return None
        return pad or None

    def _paso_scatter(self, paso):
        """Aprieta y suelta los pads de Scatter de la MC-101 (notas 60-75 en su canal de
        control). Cambiar de etapa suelta el pad anterior y aprieta el nuevo en el mismo paso;
        en el uno de la parte siguiente se suelta."""
        pad = self._scatter_pedido(paso)
        sc = self.base.get("scatter") or {}
        quiero = None if pad is None else (sc.get("salida", "MC-101"), int(sc.get("canal", 16)) - 1, 59 + int(pad))
        if quiero == self.scatter_nota:
            return
        self._soltar_scatter()
        if quiero is not None:
            self.enviar(quiero[0], "note_on", quiero[1], quiero[2], int(sc.get("fuerza", 100)))
            self.scatter_nota = quiero

    def _soltar_scatter(self):
        if getattr(self, "scatter_nota", None) is not None:
            salida, canal, nota = self.scatter_nota
            self.enviar(salida, "note_off", canal, nota, 0)
            self.scatter_nota = None

    def _en_hueco(self, paso):
        return self.hueco_desde is not None and self.hueco_desde <= paso < self.hueco_desde + 4

    def _efectos_parte(self, compas):
        """Canción: los efectos de subida de la parte que suena (todos opcionales).
        Roll de secuencias y corte de bajo en los últimos compases, acorde de tensión
        en el último compás (la parte siguiente resuelve en la i) y hueco en el último
        tiempo. Los pads que suben y el corte de bajo los aplica el conductor."""
        self.roll_desde, self.roll_compases, self.hueco_desde = None, 0, None
        self.tension_pc = self.tension_fin = None
        if self.resolver_en == compas:
            self.origen_progresion = compas  # después de la tensión, la progresión parte en su i
            self.resolver_en = None
        parte = self.conductor.parte(self.base, compas)
        if parte is None:
            return
        p = self.base["parte"][parte["i"]]
        if parte["dentro"] == 0 and parte["i"] > 0 and self.bajo is not None:
            # Un quiebre (la energía baja respecto de la parte anterior): el filtro del
            # bajo vuelve a cerrarse y empieza a abrirse de nuevo.
            antes = self.base["parte"][parte["i"] - 1]
            if p.get("energia", 0.5) < antes.get("energia_fin", antes.get("energia", 0.5)) - 0.1:
                self.bajo.reiniciar_filtro(compas)
        falta = parte["largo"] - parte["dentro"]  # compases que quedan, contando este
        if p.get("roll"):
            n = forma.compases_corte(parte["largo"])
            if falta <= n:
                self.roll_compases = n
                self.roll_desde = (compas - (n - falta)) * PASOS_POR_COMPAS
        if falta == 1:
            fin = (compas + 1) * PASOS_POR_COMPAS
            if p.get("hueco"):
                self.hueco_desde = fin - 4
            if p.get("tension"):
                self.tension_pc = (self.tonalidad.tonica + raiz_tension(self.tonalidad.intervalos)) % 12
                self.tension_fin = fin
                self.resolver_en = compas + 1

    def _momento_tension(self, paso, raiz):
        """El acorde de tensión, que pide resolver en la i en el uno de la parte siguiente."""
        tension = armonia.de_nota_larga(_cerca(self.tension_pc, raiz), self.tonalidad)
        tonica = armonia.de_nota_larga(_cerca(self.tonalidad.tonica % 12, raiz), self.tonalidad)
        return armonia.Momento(tension.raiz, tension.clases, tonica.raiz, tonica.clases,
                               max(1, self.tension_fin - paso))

    def _compas_forma(self, compas):
        """Primer paso de cada compás: entran los cambios de la app, la energía da un paso
        y avanza la transición entre escenas."""
        self._avanzar_cancion(compas)
        self.conductor.avanzar(self.base, compas)
        self._efectos_parte(compas)
        tr = self.conductor.transicion
        self.puente = None
        if tr is not None:
            if tr.puente(compas):
                d = tr.destino
                self.puente = (Tonalidad(d["musica"]["tonica"], d["musica"]["escala"]), d["pads"].get("base", "nota"),
                               (tr.fin) * PASOS_POR_COMPAS)
            if compas == tr.fin and forma.cambia_armonia(tr.origen, tr.destino):
                self.origen_progresion = compas  # la progresión nueva parte en su i
        efectiva = self.conductor.efectiva(self.base, compas)
        if efectiva != self.config:
            if self.config is not None and forma.cambia_armonia(self.config, efectiva):
                self.origen_progresion = self._origen_nueva(compas, self.config, efectiva)
            self._aplicar(efectiva)  # los cambios entran justo en el compás
            log.info("Entran los cambios (compás %d)", compas + 1)
        self.pads.origen = self.origen_progresion
        self._looper(self.config)   # con una escena en camino, pide su loop un compás antes
        self.config_en_cola = None
        self.conductor.terminar_si_corresponde(compas)
        f = self.base.get("forma", {})
        self.director.compas(self, compas, float(f.get("variacion", 0.0)), max(1, int(f.get("periodo", 16))),
                             self.base.get("pads", {}).get("seed", ""), bool(f.get("un_cambio", False)))

    def _origen_nueva(self, compas, antes, despues):
        """Compás donde parte una progresión nueva. Normalmente en su i. Pero si solo
        cambió la variante de la progresión al azar, el cambio se oye ya en este compás:
        entra en su segundo acorde, salvo que sea el mismo que suena (entonces en su i).
        Antes partía en la i y, si sonaba la i, no se oía nada hasta el próximo cambio
        (16 compases o más)."""
        pa, pb, ma, mb = antes["pads"], despues["pads"], antes["musica"], despues["musica"]
        if self.pads is None or (ma["tonica"], ma["escala"]) != (mb["tonica"], mb["escala"]) or pa["base"] != pb["base"]:
            return compas
        cambio = (compas - self.origen_progresion) // max(1, self.pads.cambia_cada)
        viejo = self.pads.lista(cambio)
        nuevo_cada = max(1, int(pb["cambia_cada"]))
        misma = (pa["progresion"] == pb["progresion"] and pa.get("azar") == pb.get("azar")
                 and (pa["progresion"] != "aleatoria" and not pa.get("azar") or pa.get("seed") == pb.get("seed")))
        if misma and pa["cambia_cada"] != pb["cambia_cada"]:
            # Solo cambió cada cuántos compases: el acorde que suena sigue y el próximo
            # llega en `nuevo_cada` compases (antes volvía a la i y se sentía que no cambiaba).
            return compas - cambio * nuevo_cada  # sigue en el mismo acorde (y en la misma vuelta)
        if (pa["progresion"] == pb["progresion"] and pa.get("azar") and pb.get("azar")
                and pa.get("seed") != pb.get("seed") and pa["cambia_cada"] == pb["cambia_cada"]):
            # Al azar con otra variante: salta a la primera variación nueva, en su segundo acorde.
            largo = len(self.pads.progresion)
            return compas - (int(pb.get("azar_cada", 2)) * largo + 1) * max(1, int(pb["cambia_cada"]))
        solo_variante = (pa["progresion"] == pb["progresion"] == "aleatoria" and pa.get("seed") != pb.get("seed")
                         and pa["cambia_cada"] == pb["cambia_cada"])
        if not solo_variante:
            return compas
        suena = viejo[cambio % len(viejo)]
        nueva = progresion_aleatoria(self.tonalidad.intervalos, str(pb.get("seed", "pads")))
        if len(nueva) > 1 and nueva[1] != suena:
            return compas - max(1, int(pb["cambia_cada"]))  # entra en su segundo acorde
        return compas

    def _momento_puente(self, paso, raiz):
        nueva, base, cambio = self.puente
        raiz_nueva = _cerca(nueva.tonica, raiz) if base == "tonica" else raiz
        return armonia.puente(self.tonalidad, nueva, raiz_nueva, max(1, cambio - paso))
