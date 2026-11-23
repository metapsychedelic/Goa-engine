// Yantra · Editores de cada motor: pads, bajo, secuencias, diálogo, FX, tocado y clips.
// Scripts clásicos en orden: comparten el ámbito global con los demás archivos de js/.
// --- Motores: uno a la vez, todos con la misma forma ---

function motores() {
  // [clave, nombre corto, objeto de config, clave del activo]
  const lista = [["pads", "Pads", cfg.pads, "activo"], ["bajo", "Bajo", cfg.bajo, "activo"]];
  cfg.secuencia.forEach((s, i) => lista.push(["sec" + i, s.nombre, s, "activa"]));
  lista.push(["dialogo", "Diálogo", cfg.dialogo, "activo"]);
  lista.push(["fx", "FX", cfg.fx, "activo"]);
  if (cfg.texturas) lista.push(["texturas", "Texturas", cfg.texturas, "activo"]);
  if (cfg.looper) lista.push(["looper", "Looper", cfg.looper, "activo"]);
  if (cfg.tocado) lista.push(["tocado", "Tocado", cfg.tocado, "activo"]);
  return lista;
}

let motorSel = leerLocal("motor", "pads");

// --- Edición de escenas ---
// «Editar» en una escena o parte: suena, y todo lo que muevas queda guardado en ella al
// momento (el motor lo copia en cada cambio). Arriba, una franja dice qué escena editas,
// con «Descartar» (vuelve a como estaba al entrar) y «Listo». Los puntos en las pestañas
// marcan qué motores cambiaron: editando, contra cómo estaba la escena al entrar; si no,
// contra la última escena que lanzaste.
let edicion = null;   // {escena, nombre, original (datos de la escena al entrar)}
const RUTEO = new Set(["salida", "canal", "disparo", "escucha", "nombre", "cc_corte", "cc_resonancia", "cc_filtro", "filtro_reposo", "parar", "nivel"]);
function referenciaEscena() {
  if (edicion) return edicion.original;
  const i = cfg && cfg.forma.escena;
  if (i === undefined || i < 0 || !cfg.escena[i]) return null;
  try { return JSON.parse(cfg.escena[i].datos); } catch (e) { return null; }
}
function difiere(vivo, guardado) {
  if (!vivo || !guardado) return false;
  for (const k in guardado) {
    if (RUTEO.has(k) || !(k in vivo)) continue;
    if (JSON.stringify(vivo[k]) !== JSON.stringify(guardado[k])) return true;
  }
  return false;
}
function motorCambiado(clave, ref) {
  ref = ref === undefined ? referenciaEscena() : ref;
  if (!ref || !cfg) return false;
  if (clave.startsWith("sec")) { const i = parseInt(clave.slice(3)); return difiere(cfg.secuencia[i], (ref.secuencia || [])[i]); }
  const secciones = clave === "dialogo" ? ["dialogo", "llamada", "respuesta"] : [clave];
  return secciones.some((s) => difiere(cfg[s], ref[s]));
}
function marcarCambios() {
  const ref = referenciaEscena();
  document.querySelectorAll(".selector button[data-motor]").forEach((b) => b.classList.toggle("cambiado", motorCambiado(b.dataset.motor, ref)));
  const arm = document.querySelector("nav.tabs button[data-vista=armonia]");
  if (arm) arm.classList.toggle("cambiado", !!ref && difiere(cfg.musica, ref.musica));
  const mot = document.querySelector("nav.tabs button[data-vista=motores]");
  if (mot) mot.classList.toggle("cambiado", !!ref && motores().some(([c]) => motorCambiado(c, ref)));
}
async function entrarEdicion(datos) {
  try {
    await api("/api/editar", datos); await recargar(); await estado();
    aviso("Editando: lo que muevas queda guardado en la escena");
  } catch (e) { aviso(e.message, true); }
}
function pintarEdicion(e) {
  const cab = document.querySelector("header.top");
  if (cab) document.documentElement.style.setProperty("--alto-cab", cab.offsetHeight + "px");
  const b = $("edicion");
  if (!e) {
    if (edicion) { edicion = null; marcarCambios(); }
    $("edicion_caja").hidden = true;
    document.querySelectorAll("button.escena.editando").forEach((x) => x.classList.remove("editando"));
    return;
  }
  if (!edicion || edicion.escena !== e.escena) {
    edicion = {escena: e.escena, original: null};
    api("/api/editar/original").then((r) => { if (edicion && r.original) { edicion.original = JSON.parse(r.original); marcarCambios(); } }).catch(() => {});
  }
  edicion.nombre = e.nombre;
  if (!b.firstChild) {
    b.append(el("span", {className: "t"}),
      el("button", {type: "button", textContent: "Descartar", onclick: async () => {
        const f = fotoPartes(), nombre = edicion.nombre;
        try { await enviarPendiente(); await api("/api/editar/descartar"); await recargar(); await estado();
          avisoDeshacer(`«${nombre}» como estaba`, () => volverPartes(f)); } catch (x) { aviso(x.message, true); } }}),
      el("button", {type: "button", className: "prim", textContent: "Listo", onclick: async () => {
        try { await api("/api/editar/listo"); await recargar(); await estado(); aviso(`«${edicion ? edicion.nombre : "Escena"}» guardada`); } catch (x) { aviso(x.message, true); } }}));
  }
  b.querySelector(".t").replaceChildren(el("b", {textContent: `Editando «${e.nombre}»`}), el("br"),
    el("span", {className: "mut", textContent: e.cambios ? "Con cambios · se guardan solos" : "Lo que muevas se guarda solo"}));
  $("edicion_caja").hidden = false;
  document.querySelectorAll("button.escena[data-escena]").forEach((x) => x.classList.toggle("editando", Number(x.dataset.escena) === e.escena));
}

function renderSelector() {
  const sel = $("selector"); sel.innerHTML = "";
  const lista = motores();
  if (!lista.some((m) => m[0] === motorSel)) motorSel = "pads";
  for (const [clave, nombre, obj, k] of lista) {
    sel.append(el("button", {type: "button", role: "tab", textContent: nombre, "aria-selected": clave === motorSel ? "true" : "false",
      className: (obj[k] ? "" : "apagado") + (motorCambiado(clave) ? " cambiado" : ""), "data-motor": clave, onclick: () => { motorSel = clave; escribirLocal("motor", clave); renderMotores(); }}));
  }
  if (cfg.secuencia.length < 8) {
    sel.append(el("button", {type: "button", className: "mas", textContent: "+", "aria-label": "Añadir secuencia", title: "Añadir secuencia", onclick: agregarSecuencia}));
  }
}

function renderMotores() {
  renderSelector();
  const panel = $("motor_panel"); panel.innerHTML = "";
  if (motorSel === "pads") panel.append(...panelPads());
  else if (motorSel === "bajo") panel.append(...panelBajo());
  else if (motorSel === "dialogo") panel.append(...panelDialogo());
  else if (motorSel === "fx") panel.append(...panelFx());
  else if (motorSel === "texturas") panel.append(...panelTexturas());
  else if (motorSel === "looper") panel.append(...panelLooper());
  else if (motorSel === "tocado") panel.append(...panelTocado());
  else panel.append(...panelSecuencia(parseInt(motorSel.slice(3))));
  // «Copiar a otras partes…» igual en todos los motores, al final.
  if (cfg.parte && cfg.parte.length) {
    const m = motores().find((x) => x[0] === motorSel);
    const nombre = motorSel.startsWith("sec") ? `la secuencia ${m[1]}` : `el motor ${m[1]}`;
    panel.append(el("div", {style: "display:flex;flex-direction:column"}, [
      el("button", {type: "button", textContent: "Copiar a otras partes…", onclick: () => copiarMotorA(motorSel, nombre)})]));
  }
}
// Nombres de antes: cualquier cambio vuelve a dibujar el motor que está a la vista.
const renderPads = () => renderMotores(), renderBajo = () => renderMotores(), renderDialogo = () => renderMotores(), renderSecuencias = () => renderMotores();

function cabMotor(titulo, sub, obj, k, extra, accion) {
  const estado = el("span", {className: "pill", "data-salida": obj.salida || "", style: "display:none"});
  const chk = el("input", {type: "checkbox", className: "switch", checked: !!obj[k], "aria-label": `Activar ${titulo}`,
    onchange: () => { obj[k] = chk.checked; renderSelector(); renderMutes(); guardar(); }});
  return el("div", {className: "cabmotor"}, [
    el("div", {className: "tit"}, [el("b", {textContent: titulo}), el("span", {textContent: sub})]),
    el("div", {style: "display:flex;align-items:center;gap:8px;flex:none"}, [accion || null, extra || (obj.salida ? estado : null), el("label", {}, ["Activo", chk])]),
  ]);
}

// Botón pequeño (espiral que vuelve al centro) en la cabecera de cada secuencia.
const ICONO_FABRICA = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 12m-1.5 0a1.5 1.5 0 1 1 3 0a3.5 3.5 0 1 1 -7 0a5.5 5.5 0 1 1 11 0a7.5 7.5 0 1 1 -15 0"/><polyline points="1.6 9.5 1.5 12.2 4 11"/></svg>';
function botonFabrica(i, s) {
  return botonRestaurar(`la secuencia ${s.nombre}`, `Secuencia ${s.nombre}`, {motor: "secuencia", fila: i},
    "Se mantienen su salida MIDI, canal, nombre y seed, y las otras secuencias no cambian.");
}
const FABRICA = {
  pads: ["los pads", "Pads", "Se mantienen su salida MIDI, canal, programa, nota larga, género, seed y si suenan."],
  bajo: ["el bajo", "Bajo", "Se mantienen su salida MIDI, canal, programa, nota larga, género, seed y el CC del filtro de su sinte."],
  dialogo: ["la llamada y respuesta", "Llamada y respuesta", "Vuelven las dos voces. Se mantienen sus salidas MIDI, canales, programas, la nota larga, la entrada que escucha, el género y la seed."],
  fx: ["el FX", "FX", "Se mantienen su salida MIDI, canal, programa, nota larga, género, seed y el CC del corte."],
  texturas: ["las texturas", "Texturas", "Se mantienen su salida MIDI, canal, programa, nota larga, seed y el CC que respira."],
  tocado: ["el tocado", "Tocado", "No borra lo grabado. Se mantienen su salida MIDI, canal, programa y seed."],
  looper: ["el looper", "Looper", "Queda sin loop elegido. Se mantienen su salida MIDI, canal y el slot vacío para callar."],
};
function botonFabricaMotor(motor) {
  const [quien, titulo, conserva] = FABRICA[motor];
  return botonRestaurar(quien, titulo, {motor}, conserva);
}
function botonRestaurar(quien, titulo, datos, conserva) {
  const b = el("button", {type: "button", className: "icono-mini", title: "Restaurar ajustes de fábrica",
    "aria-label": `Restaurar ajustes de fábrica de ${quien}`,
    onclick: async () => {
      try { await enviarPendiente(); const d = await api("/api/fabrica", datos); await recargar(); estado();
        if (d.igual) aviso(`${titulo} ya estaba en ajustes de fábrica`); else avisoDeshacer(`${titulo} en ajustes de fábrica`, deshacerUltimo); }
      catch (e) { aviso(e.message, true); }
    }});
  b.innerHTML = ICONO_FABRICA;
  return b;
}

// Deshacer (cabecera): un paso atrás por toque. Antes manda lo que quedó esperando (el
// último deslizador movido) para que eso también se pueda deshacer.
async function deshacer() {
  const b = $("deshacer");
  b.disabled = true;
  try {
    await enviarPendiente();
    const d = await api("/api/deshacer", {});
    await recargar();
    aviso("Deshecho: " + d.deshecho);
    b.disabled = !d.quedan;
  } catch (e) { aviso(e.message, true); estado(); }
}

function salidaTexto(obj) {
  const canal = obj.disparo ? ` · nota larga canal ${obj.disparo}` : "";
  return `${obj.salida} · canal ${obj.canal}${canal}`;
}

function armoniaTexto(obj) {
  return guiadaDe(obj) ? "sigue la armonía" : "armonía libre";
}

// --- Pads ---

function panelPads() {
  const p = cfg.pads;
  const select = (opciones, k) => {
    const s = el("select", {onchange: () => { p[k] = s.value; guardar(); }});
    for (const [v, t] of opciones) s.append(el("option", {value: v, textContent: t, selected: v === p[k]}));
    return s;
  };
  const pulso = deslizador(p, "pulso", "Pulso", 0, 8, 1, (v) => v === 0 ? "sostenidos"
    : p.ritmo === "stabs" ? `stabs · ritmo ${((v - 1) % 4) + 1}` : `${v} golpe${v > 1 ? "s" : ""} por compás`);
  pulso.querySelector("input").addEventListener("change", () => renderMotores());
  return [
    cabMotor("Pads y drones", `${p.salida} · canal ${p.canal} · ${p.suenan ? "guían la armonía" : "callados, solo guían"}`, p, "activo", null, botonFabricaMotor("pads")),
    campo("Textura", segmentado([["acordes","Acordes"],["nota","Nota sola"],["raiz_acorde","Raíz + acorde"]], p.textura || "acordes",
      (v) => { p.textura = v; renderMotores(); guardar(); }, 3)),
    ayuda(p.textura === "nota" ? "Solo la raíz de cada acorde, grave: una guía clara de la progresión para programar encima."
      : p.textura === "raiz_acorde" ? "El acorde con su raíz una octava abajo. Ocupa una voz del sinte." : "Acordes completos."),
    bloqueVariante(p, "pads", "pads"),
    el("div", {className: "card principales"}, [
      el("label", {className: "campo"}, ["Progresión", (() => { const s = select(PROGRESIONES, "progresion");
        s.addEventListener("change", () => renderMotores()); return s; })()]),
      casilla(p, "azar", "Al azar", "Parte de la progresión elegida y la va variando: la primera vuelta suena tal cual y después cambia uno o dos acordes por otros de la escala.", () => renderMotores()),
      p.azar ? campo("Nueva variación cada (vueltas de la progresión)", segmentado([["1","1"],["2","2"],["4","4"]], String(p.azar_cada || 2), (v) => { p.azar_cada = parseInt(v); guardar(); }, 3)) : null,
      p.azar ? el("p", {className: "ayuda"}, [
        el("span", {textContent: "Suena: "}),
        el("strong", {id: "prog_azar", textContent: (ultimoEstado && ultimoEstado.progresion) || ""}),
        el("span", {textContent: " · " + (AZAR_ESCALA[cfg.musica.escala] || "") + " «Otra variante» (arriba) trae otras variaciones y se oye desde el próximo compás."})]) : null,
      el("label", {className: "campo"}, ["Tipo de acorde", select(ACORDES, "acorde")]),
      pulso,
      campo("Ritmo del pulso", segmentado([["euclides","Parejo (euclidiano)"],["stabs","Stabs psy"]], p.ritmo || "euclides",
        (v) => { p.ritmo = v; if (v === "stabs" && !p.pulso) p.pulso = 1; renderMotores(); guardar(); }, 2)),
      ayuda(p.ritmo === "stabs" ? "Acordes cortos a contratiempo, con ritmos sacados de packs de psytrance. El pulso (1 a 4) elige el ritmo: 1 · ....xx.xx.x.x.x. · 2 · x...x.xx.xx.x.x. · 3 · .x.x.xx.x.xx.xxx · 4 · x...x...x.....x."
        : "Parejo: los golpes del pulso se reparten en corcheas, el primero en el uno."),
      deslizador(p, "golpe", "Largo del golpe", 0.1, 1, 0.05,
        (x) => x < 0.3 ? `corto (${porcentaje(x)})` : x < 0.6 ? `medio (${porcentaje(x)})` : x < 0.95 ? `largo (${porcentaje(x)})` : "hasta el siguiente"),
      ayuda(p.pulso ? "Cuánto dura cada golpe del pulso. Corto se oye como pulso; largo, casi como un pad continuo. Si igual suena pegado, baja el release del sinte."
        : "Pulso en 0: los acordes suenan sostenidos y atacan solo al cambiar de acorde. El largo del golpe se usa cuando subes el pulso."),
    ]),
    el("div", {className: "grupos"}, [
      grupo("g-pads-ritmo", "Ritmo", `cambia cada ${p.cambia_cada} · ${p.ataque === "ligado" ? "ligado" : "reataca"} · rasgueo ${p.rasgueo}`, [
        campo("Cambia de acorde cada (compases)", segmentado([["4","4"],["8","8"],["16","16"],["32","32"]], String(p.cambia_cada), (v) => { p.cambia_cada = parseInt(v); guardar(); }, 4)),
        ayuda("Con pulso, los acordes suenan en un ritmo euclidiano suave en corcheas, el primero en el uno."),
        campo("Al cambiar de acorde", segmentado([["ligado","Ligado"],["reatacar","Vuelve a atacar"]], p.ataque, (v) => { p.ataque = v; renderMotores(); guardar(); }, 2)),
        p.ataque === "ligado" && !p.pulso ? deslizador(p, "suspensiones", "Suspensiones", 0, 1, 0.05, (x) => x === 0 ? "nunca" : `${porcentaje(x)} de los cambios`) : null,
        p.ataque === "ligado" && !p.pulso ? ayuda("Al cambiar de acorde, una voz se queda colgada y resuelve un tiempo después.") : null,
        deslizador(p, "rasgueo", "Entrada escalonada", 0, 24, 1, (v) => v === 0 ? "todas juntas" : v === 24 ? "una voz por tiempo" : v === 1 ? "1 pulso" : v + " pulsos"),
        ayuda("Al máximo, las voces entran de a una, una por tiempo (ambient). Con pulso se usa un rasgueo corto."),
      ]),
      grupo("g-pads-notas", "Notas", `${p.voces} voces · ${{cerrada: "juntas", abierta: "abiertas", amplia: "muy abiertas"}[p.apertura]}${p.drone ? " · drone" : ""}`, [
        casilla(p, "suenan", "Suenan", "Apagado: callados, solo guían la armonía de los demás", () => renderMotores()),
        casilla(p, "drone", "Drone en la raíz", "Una nota grave sostenida bajo los acordes"),
        campo("Separación de las voces", segmentado([["cerrada","Juntas"],["abierta","Abiertas"],["amplia","Muy abiertas"]], p.apertura, (v) => { p.apertura = v; guardar(); }, 3)),
        el("div", {className: "dos"}, [numeroDe(p, "voces", "Notas por acorde (MicroFreak: 4)", 2, 6), deslizador(p, "octava", "Octava", -2, 2, 1, octavaTexto)]),
        numeroDe(p, "velocidad", "Fuerza (1-127)", 1, 127),
      ]),
      grupo("g-pads-var", "Variación", `sorpresas ${porcentaje(p.variacion)} · parte desde ${p.base === "nota" ? "la nota larga" : "la tónica"}`, [
        deslizador(p, "variacion", "Sorpresas en la progresión", 0, 1, 0.05, porcentaje),
        ayuda("A veces cambia un acorde por uno emparentado que comparte dos notas."),
        campo("La progresión parte desde", segmentado([["nota","La nota larga"],["tonica","La tónica fija"]], p.base, (v) => { p.base = v; guardar(); }, 2)),
        ayuda("Con la nota larga, si cambias de nota en la Circuit la progresión se mueve con ella."),
      ]),
      grupo("g-pads-lfo", "Filtro y sonido del sinte", lfoResumen(p) === "apagado" ? "sin modular" : lfoResumen(p), [
        ayuda("Opcional: dos LFO que mueven por CC el filtro u otro control del sinte de los pads, sincronizados al compás. Sirve con la MicroFreak, la MC-101 o la FM-1."),
        ...editorLfo(p, "lfo", "LFO 1"),
        ...editorLfo(p, "lfo2", "LFO 2"),
      ]),
      grupo("g-pads-midi", "Salida MIDI", salidaTexto(p), [
        el("div", {className: "dos"}, [destinoDe(p, renderMotores), numeroDe(p, "canal", "Canal MIDI", 1, 16, renderMotores)]),
        numeroDe(p, "disparo", "Canal de su nota larga en la Circuit (0 = el general)", 0, 16, renderMotores),
        programaDe(p),
      ]),
    ]),
  ];
}

// --- Bajo ---

function panelBajo() {
  const b = cfg.bajo;
  return [
    cabMotor("Bajo", `${b.salida} · canal ${b.canal} · ${armoniaTexto(b)}`, b, "activo", null, botonFabricaMotor("bajo")),
    bloqueEstilo(b, {familias: FAMILIAS_BAJO, nombre: nombreBajo, clave: "bajo-estilo", dibujo: (v) => (ESTILOS_BAJO.find((x) => x[0] === v) || [])[2],
      ayuda: TEXTO_BAJO[b.estilo] + " Solo cambia el ritmo; tus ajustes se quedan.", elegir: (v) => {
        b.estilo = v; renderMotores(); guardar();
        if (ultimoEstado && ultimoEstado.corriendo && b.activo) aviso("El bajo cambia en el próximo compás"); }}),
    bloqueVariante(b, "bajo", "bajo"),
    el("div", {className: "card principales"}, [
      deslizador(b, "movimiento", "Movimiento", 0, 1, 0.05,
        (x) => x === 0 ? "solo la raíz" : x < 0.4 ? `camina poco (${porcentaje(x)})` : x < 0.7 ? `camina (${porcentaje(x)})` : `camina mucho (${porcentaje(x)})`),
      ["dub", "sub"].includes(b.estilo) ? null : deslizador(b, "sube", "Notas que suben", 0, 1, 0.05,
        (x) => x === 0 ? "siempre en la raíz" : x < 0.35 ? `un paso (${porcentaje(x)})` : x < 0.7 ? `hasta la quinta (${porcentaje(x)})` : `hasta la octava (${porcentaje(x)})`),
      ["dub", "sub"].includes(b.estilo) ? null : campo("Ciclo de alturas", segmentado([["0","Sin ciclo"],["5","De 5"],["7","De 7"]], String(b.ciclo || 0),
        (v) => { b.ciclo = parseInt(v); guardar(); renderMotores(); }, 3)),
      (b.ciclo && !["dub", "sub"].includes(b.estilo)) ? ayuda(`Zenonesque: el ritmo queda igual y las notas de la raíz rotan por un ciclo de ${b.ciclo} grados (raíz, octava, ♭2…). Como no calza con el compás, cae distinto cada vez y se repite recién cada ${b.ciclo} compases.`) : null,
      deslizador(b, "evolucion", "Evolución", 0, 1, 0.05,
        (x) => x === 0 ? "fijo" : x < 0.4 ? `cambia de a poco (${porcentaje(x)})` : x < 0.7 ? `va cambiando (${porcentaje(x)})` : `cambia mucho (${porcentaje(x)})`),
      deslizador(b, "transponer", "Transponer", -7, 7, 1, (x) => x === 0 ? "desde la raíz" : `${x > 0 ? "+" : ""}${x} grado${Math.abs(x) > 1 ? "s" : ""}${x === 4 ? " (la quinta)" : x === 2 ? " (la tercera)" : ""}`),
    ]),
    el("div", {className: "grupos"}, [
      grupo("g-bajo-filtro", "Filtro automático", b.filtro ? `CC ${b.filtro_cc} · se abre en ${b.filtro_ciclo} compases` : "apagado", [
        el("label", {className: "fila", style: "min-height:44px"}, [
          el("span", {}, ["Filtro automático", el("br"), el("span", {className: "mut", textContent: "El motor abre el filtro del sinte del bajo de a poco, por MIDI CC"})]),
          el("input", {type: "checkbox", className: "switch", checked: !!b.filtro, "aria-label": "Filtro automático",
            onchange: (e) => { b.filtro = e.target.checked; guardar(); renderMotores(); }})]),
        ...(b.filtro ? [
          campo("Qué controla", segmentado([["74","Corte (CC 74)"],["71","Resonancia (CC 71)"]], String(b.filtro_cc), (v) => { b.filtro_cc = parseInt(v); guardar(); renderMotores(); }, 2)),
          ayuda("CC de la MC-101. Otro sinte puede usar otros números."),
          campo("Se abre en (compases)", segmentado([["8","8"],["16","16"],["32","32"],["64","64"]], String(b.filtro_ciclo), (v) => { b.filtro_ciclo = parseInt(v); guardar(); renderMotores(); }, 4)),
          campo("Forma", segmentado([["sube","Sube y vuelve a cerrar"],["ola","Sube y baja"]], b.filtro_forma || "sube", (v) => { b.filtro_forma = v; guardar(); }, 2)),
          deslizador(b, "filtro_nota", "Golpe de filtro en cada nota", 0, 1, 0.05,
            (x) => x === 0 ? "no: solo el barrido lento" : x < 0.4 ? `suave (${porcentaje(x)})` : x < 0.7 ? `marcado (${porcentaje(x)})` : `muy marcado (${porcentaje(x)})`),
          ayuda("En el ataque de cada nota el filtro se abre y vuelve enseguida, como una envolvente; las notas ligadas de un slide no lo vuelven a abrir. Encima va el barrido lento."),
          deslizador(b, "filtro_min", "Cerrado", 0, 127, 1, (x) => String(x)),
          deslizador(b, "filtro_max", "Abierto", 0, 127, 1, (x) => String(x)),
          ayuda("En el modo canción vuelve a cerrarse en cada quiebre (cuando la energía baja) y empieza a abrirse de nuevo."),
        ] : []),
      ]),
      grupo("g-bajo-porta", "Portamento", b.porta ? `prendido · tiempo ${b.porta_tiempo}` : "apagado", [
        el("label", {className: "fila", style: "min-height:44px"}, [
          el("span", {}, ["Portamento del sinte", el("br"), el("span", {className: "mut", textContent: "El motor prende el glide del sinte del bajo (CC 65) para que los slides se deslicen"})]),
          el("input", {type: "checkbox", className: "switch", checked: !!b.porta, "aria-label": "Portamento del sinte",
            onchange: (e) => { b.porta = e.target.checked; guardar(); renderMotores(); }})]),
        b.porta ? deslizador(b, "porta_tiempo", "Tiempo del glide (CC 5)", 0, 127, 1, (x) => x < 20 ? `corto (${x})` : x < 60 ? `medio (${x})` : `largo (${x})`) : null,
        ayuda("El glide solo se oye entre notas ligadas: sube el «Slide» del bajo (grupo Ritmo). En la MC-101 el track del bajo debe estar en mono/legato."),
      ]),
      grupo("g-bajo-ritmo", "Ritmo", `${b.remates ? `remate cada ${b.frase}${b.remate_var > 0 ? " variado" : ""}` : "sin remates"} · swing ${porcentaje(b.swing * 2)} · densidad ${porcentaje(b.densidad)}`, [
        casilla(b, "remates", "Remates", "El último compás de la frase cierra con un remate (se alternan dos)", () => renderMotores()),
        ...(b.remates ? [
          campo("Frase de (compases)", segmentado([["2","2"],["4","4"],["8","8"]], String(b.frase), (v) => { b.frase = parseInt(v); guardar(); }, 3)),
          deslizador(b, "remate_var", "Variación del remate", 0, 1, 0.05,
            (x) => x === 0 ? "siempre los dos clásicos" : x < 0.4 ? `cambia poco (${porcentaje(x)})` : x < 0.7 ? `cambia bastante (${porcentaje(x)})` : `muy libre (${porcentaje(x)})`),
          b.remate_var > 0 ? campo("Rango de las notas que cambian", segmentado([["quinta","Hasta la quinta"],["octava","Hasta la octava"]], b.remate_rango || "octava",
            (v) => { b.remate_rango = v; guardar(); }, 2)) : null,
          deslizador(b, "remate_largas", "Nota larga en el remate", 0, 1, 0.05,
            (x) => x === 0 ? "nunca" : `en ${porcentaje(x)} de las frases`),
          b.remate_largas > 0 ? deslizador(b, "remate_largo", "Largo de la nota larga", 0.3, 1, 0.05,
            (x) => `${porcentaje(x)} del espacio hasta la siguiente`) : null,
          ayuda("Una nota del remate (nunca la última) se alarga hacia la siguiente y siempre termina antes de que empiece: nunca se pisan. A lo más una por remate."),
          ["rolling", "fullon", "chillgressive"].includes(b.estilo) ? deslizador(b, "remates_pack", "Remates de los packs", 0, 1, 0.05,
            (x) => x === 0 ? "nunca" : `en ${porcentaje(x)} de las frases`) : null,
          ["rolling", "fullon", "chillgressive"].includes(b.estilo) && b.remates_pack > 0 ? ayuda("Remates sacados de los bajos de tu carpeta de MIDIs (Apex): ♭7 y octava, ♭2 y ♭3, media frase en el ♭2 o el ♭3, el último tiempo un grado abajo. Siempre en la segunda mitad del compás, sin tocar el bombo.") : null,
          deslizador(b, "fusas", "Remate en fusas", 0, 1, 0.05, (x) => x === 0 ? "nunca" : x > 0.6 ? `en ${porcentaje(x)} de las frases · también el tiempo 3` : `en ${porcentaje(x)} de las frases`),
          ayuda("Un redoble corto antes del uno: las últimas notas del compás que cierra la frase se parten en dos fusas (la segunda repite, salta a la octava o cae en la ♭7)."),
          deslizador(b, "remate_marca", "Remate marcado", 0, 1, 0.05,
            (x) => x < 0.3 ? "como el resto (puede llevar slide)" : x < 0.7 ? `algo acentuado, sin slide (${porcentaje(x)})` : `acentuado, sin slide (${porcentaje(x)})`),
          ayuda("En cada frase cambian al azar las alturas de algunas notas del remate, nunca su ritmo (repetible con la variante). En 0 suenan siempre los dos remates clásicos del estilo."),
        ] : []),
        deslizador(b, "densidad", "Densidad", 0, 1, 0.05, (x) => x === 1 ? "todos los golpes" : `${porcentaje(x)} de los golpes`),
        deslizador(b, "swing", "Swing", 0, 0.5, 0.05, (x) => x === 0 ? "recto" : porcentaje(x * 2)),
        deslizador(b, "fantasmas", "Notas fantasma", 0, 1, 0.05, (x) => x === 0 ? "ninguna" : porcentaje(x)),
        ayuda("Golpes suaves en los huecos (nunca en el bombo)."),
      ]),
      grupo("g-bajo-notas", "Notas", `octava ${b.octava} · largo ${porcentaje(b.gate)} · slide ${porcentaje(b.slide)}`, [
        deslizador(b, "octava", "Octava", -2, 2, 1, octavaTexto),
        numeroDe(b, "velocidad", "Fuerza (1-127)", 1, 127),
        deslizador(b, "gate", "Largo de las notas", 0.05, 1, 0.05, porcentaje),
        deslizador(b, "slide", "Slide", 0, 1, 0.05, (x) => x === 0 ? "nunca" : `${porcentaje(x)} de las notas`),
        ayuda("Las notas con slide se pisan un instante con la siguiente: en un sinte en legato con glide, se deslizan."),
        deslizador(b, "acentos", "Acentos", 0, 1, 0.05, porcentaje),
        deslizador(b, "vel_random", "Variación de fuerza", 0, 1, 0.05, porcentaje),
      ]),
      ["dub", "sub"].includes(b.estilo) ? null : grupo("g-bajo-zenon", "Nota larga zenon", b.zenon > 0 ? `en ${porcentaje(b.zenon)} de las frases${b.caida ? ` · cae ${b.caida} st` : ""}` : "apagada", [
        deslizador(b, "zenon", "Frases con nota larga", 0, 1, 0.05, (x) => x === 0 ? "nunca" : `en ${porcentaje(x)} de las frases`, () => renderMotores()),
        ayuda("Zenonesque: en el compás antes del que cierra la frase, la segunda mitad pasa a ser una sola nota larga que entra justo después del bombo (no en el contratiempo como un bajo con glide) y cae de altura."),
        ...(b.zenon > 0 ? [
          deslizador(b, "caida", "Cuánto cae", 0, 24, 1, (x) => x === 0 ? "no cae" : `${x} semitono${x > 1 ? "s" : ""}${x === 12 ? " (una octava)" : ""}`, () => renderMotores()),
          b.caida > 0 ? numeroDe(b, "bend_rango", "Rango de pitch bend del sinte (semitonos)", 1, 24) : null,
          b.caida > 0 ? ayuda("La caída va por pitch bend: pon aquí el rango que tiene el sinte del bajo (en la MC-101 se ajusta por tono; si no coincide, cae más o menos de lo pedido). Vuelve al centro al terminar la nota.") : null,
        ] : []),
      ]),
      grupo("g-bajo-var", "Variación", `mutar cada ${b.mutar_cada} · ${armoniaTexto(b)}`, [
        numeroDe(b, "mutar_cada", "Cada (compases, de 1 a 64)", 1, 64, () => renderMotores()),
        ayuda("Cada vez puede cambiar un golpe (otra nota, un silencio, uno nuevo o corrido) y los cambios se acumulan. A veces uno vuelve a como era."),
        armoniaPropia(b, () => renderMotores()),
        ayuda(guiadaDe(b)
          ? "Guiada: sigue cada acorde de los pads" + (cfg.musica.anticipar ? " y antes de cada cambio va una nota que lleva a la raíz que viene." : ".")
          : "Libre: toca sobre la raíz de su nota larga, sin mirar el acorde."),
      ]),
      grupo("g-bajo-midi", "Salida MIDI", salidaTexto(b), [
        el("div", {className: "dos"}, [destinoDe(b, renderMotores), numeroDe(b, "canal", "Canal MIDI", 1, 16, renderMotores)]),
        numeroDe(b, "disparo", "Canal de su nota larga en la Circuit (0 = el general)", 0, 16, renderMotores),
        programaDe(b),
      ]),
    ]),
  ];
}

// --- Secuencias ---

// --- Editor de secuencia, por intención: cada tarjeta junta lo que sirve para lo mismo y lo que
// depende de un control aparece justo debajo de él, solo cuando ese control hace algo. Mismos
// controles y rangos completos del motor (docs/rediseno-secuencia.md).
const FAMILIAS = [["Rodantes", ["rolling","galope","arpegio3","acido"]], ["Con frase", ["clasico","psytrance"]],
  ["Con aire", ["psy_chill","euclidiano"]], ["Lentos", ["largas","ambient"]]];
const ORDEN_ESTILOS = FAMILIAS.flatMap((f) => f[1]);
const POSICION_NECESARIA = {largas: "todos", ambient: "todos", clasico: "todos", psytrance: "todos"};  // = generos.POSICION_NECESARIA
const nombreEstilo = (v) => (ESTILOS.find((x) => x[0] === v) || [, v])[1];
const gateTexto = (v) => v < 0.3 ? "corto" : v < 0.7 ? "medio" : "largo";
const octavaTexto = (v) => v === 0 ? "en su lugar" : (v > 0 ? "+" : "") + v + (Math.abs(v) === 1 ? " octava" : " octavas");

function elegirEstilo(s, v) {
  s.estilo = v;
  if (POSICION_NECESARIA[v]) s.posicion = POSICION_NECESARIA[v];  // sin esto, sus notas en el tiempo no sonarían
  renderMotores(); guardar();
}

function figuraTexto(s) {
  const lista = s.estilo === "clasico" ? FIGURAS : s.estilo === "psytrance" ? FIGURAS_PSY : null;
  if (!lista) return "";
  const f = lista.find((x) => x[0] === s.figura) || lista[0];
  return f[1].replace(" ✦", "");
}

// La sección Estilo, igual en la secuencia, el tocado y el bajo: abierta y plegable, los estilos
// por familia, ‹ › para pasar de uno a otro y, debajo, las opciones del estilo elegido.
function bloqueEstilo(obj, o) {
  const orden = o.familias.flatMap((f) => f[1]);
  const k = Math.max(0, orden.indexOf(obj.estilo));
  const mover = (d) => o.elegir(orden[(k + d + orden.length) % orden.length]);
  const nav = (txt, d, etiqueta) => el("button", {type: "button", className: "nav-estilo", textContent: txt, "aria-label": etiqueta,
    onclick: (e) => { e.preventDefault(); e.stopPropagation(); mover(d); }});
  const opciones = o.opciones || [];
  return recordar(el("details", {className: "grupo estilo-sec"}, [
    el("summary", {}, [
      el("span", {className: "cab"}, [el("b", {textContent: "Estilo"}), el("span", {textContent: o.nombre(obj.estilo) + (o.detalle ? ` · ${o.detalle}` : "")})]),
      nav("‹", -1, "Estilo anterior"), nav("›", 1, "Estilo siguiente")]),
    el("div", {className: "cuerpo"}, [
      ...o.familias.map(([familia, lista]) => el("div", {className: "familia"}, [
        el("span", {className: "familia-nombre", textContent: familia}),
        segmentado(lista.map((v) => [v, o.nombre(v), o.dibujo ? o.dibujo(v) : undefined]), obj.estilo, (v) => o.elegir(v), lista.length > 2 ? 4 : 2)])),
      ayuda(o.ayuda || "Cambia el patrón; tus ajustes se quedan."),
      opciones.length ? el("span", {className: "familia-nombre", textContent: `Opciones de ${o.nombre(obj.estilo)}`}) : null,
      ...opciones,
    ].filter(Boolean)),
  ]), o.clave, true);
}
// Estilos de secuencia (también los del tocado).
function estiloDeSecuencia(s, clave) {
  return bloqueEstilo(s, {familias: FAMILIAS, nombre: nombreEstilo, clave, detalle: figuraTexto(s), elegir: (v) => elegirEstilo(s, v),
    opciones: s.estilo === "clasico" ? panelClasico(s) : s.estilo === "psytrance" ? panelPsy(s) : []});
}
const FAMILIAS_BAJO = [["Rodantes", ["rolling","fullon","galope","tresillo"]], ["Con aire", ["offbeat","saltado","sincopado","trote","chillgressive"]],
  ["Lentos", ["dub","sub"]]];

// --- Variante y clips: un solo componente para todos los motores ---
// Variante plegable: cerrada, la seed que suena, el clip y «Otra»; abierta, A/B, favoritas, la
// seed a mano y (si el motor tiene) la pestaña de clips. Los clips funcionan igual en todos:
// tocar uno entra en el próximo compás y prende el motor, el motor recuerda su nombre
// («· modificado» si después cambiaste algo), Parar lo calla, y salida/canal se quedan.
let clipsAbiertos = new Set();
const fabricas = {};   // clips de fábrica por motor (los manda la Pi una vez)
async function cargarFabrica(motor) {
  if (fabricas[motor]) return;
  fabricas[motor] = [];
  try { fabricas[motor] = (await (await fetch(`/api/clips/fabrica?motor=${motor}`)).json()).clips; renderMotores(); } catch (e) { delete fabricas[motor]; }
}
async function intentar(f) { try { await f(); } catch (e) { aviso(e.message, true); } }
async function aplicarAntes() { clearTimeout(temporizador); await api("/api/config", cfg); }

const IGNORAR_CLIP = new Set(["nombre", "con_variante", "fabrica", "activa", "activo", "disparo", "salida", "canal", "filtro_cc",
  "llamada_salida", "llamada_canal", "respuesta_salida", "respuesta_canal"]);
// Qué motor es cada id: «sec0», «bajo», «pads», «dialogo».
const motorDeId = (id) => id.startsWith("sec") ? "secuencia" : id;
function valoresDe(id) {
  if (id.startsWith("sec")) return cfg.secuencia[parseInt(id.slice(3))] || {};
  if (id === "dialogo") {
    const v = Object.assign({}, cfg.dialogo);
    for (const voz of ["llamada", "respuesta"]) for (const [k, x] of Object.entries(cfg[voz])) v[`${voz}_${k}`] = x;
    return v;
  }
  return cfg[id] || {};
}
const listaClipsDe = (id) => id.startsWith("sec") ? cfg.clip : id === "dialogo" ? (cfg.clip_dialogo || []) : (cfg["clip_" + id] || []);
function estadoClipDe(id) {
  // {clip, activa, cola} como una fila del lanzador.
  const e = ultimoEstado || {};
  if (id.startsWith("sec")) return (e.filas || [])[parseInt(id.slice(3))] || {};
  if (id === "dialogo") return e.fila_dialogo || {};
  const n = (e.clips_motor || {})[id];
  return {clip: n, activa: !!(n && cfg[id] && cfg[id].activo), cola: null};
}
function nombreClipDe(id) {
  const f = estadoClipDe(id);
  if (!f.activa || !f.clip) return "";
  const c = listaClipsDe(id).find((x) => x.nombre === f.clip) || (fabricas[motorDeId(id)] || []).find((x) => x.nombre === f.clip);
  if (!c) return f.clip;
  const v = valoresDe(id);
  const cambio = Object.keys(c).some((k) => !IGNORAR_CLIP.has(k) && !(k === "seed" && c.con_variante === false) && k in v && v[k] !== c[k]);
  return f.clip + (cambio ? " · modificado" : "");
}
const nombreClipFila = (i) => nombreClipDe(`sec${i}`);

function pestanaClip(id) {
  const n = nombreClipDe(id);
  return el("button", {type: "button", className: "pestana-clip" + (clipsAbiertos.has(id) ? " abierta" : ""), "data-pestana-clip": id,
    "aria-expanded": clipsAbiertos.has(id) ? "true" : "false", textContent: (n ? `Clip: ${n}` : "Sin clip") + " ▾",
    onclick: () => { clipsAbiertos.has(id) ? clipsAbiertos.delete(id) : clipsAbiertos.add(id); renderMotores(); }});
}

function cajaClips(m) {
  cargarFabrica(m.motor);
  const agrupar = leerLocal("clips_por_estilo", "0") === "1" && m.estiloDe;
  const clave = m.claveEstilo || "estilo";
  const lista = el("div", {className: "clips-lista"});
  const filaClip = (c, ci) => el("div", {className: "clip-fila"}, [
    el("button", {type: "button", className: "clip", "data-clip": c.nombre, onclick: () => intentar(() => m.lanzar({clip: ci}))}, [
      el("span", {className: "clip-nombre", textContent: c.nombre}),
      el("span", {className: "mut", textContent: [agrupar || !m.estiloDe ? "" : m.estiloDe(c), c.con_variante === false ? "sin variante" : c.seed].filter(Boolean).join(" · ")})]),
    el("button", {type: "button", className: "clip-menu", textContent: "⋯", "aria-label": `Opciones de ${c.nombre}`, onclick: () => menuClip(m, c, ci)}),
  ]);
  const clips = m.clips.map((c, ci) => [c, ci]);
  if (!clips.length) lista.append(el("p", {className: "mut", style: "margin:4px 0", textContent: "Todavía no guardas clips."}));
  else if (agrupar) {
    for (const v of m.ordenEstilos) {
      const de = clips.filter(([c]) => c[clave] === v);
      if (de.length) lista.append(el("span", {className: "familia-nombre", textContent: m.nombreEstilo(v)}), ...de.map(([c, ci]) => filaClip(c, ci)));
    }
  } else lista.append(...clips.map(([c, ci]) => filaClip(c, ci)));
  lista.append(el("button", {type: "button", className: "clip parar", textContent: "■ Parar en el próximo compás", "data-parar": "1", onclick: () => intentar(m.parar)}));
  const fab = fabricas[m.motor] || [];
  const caja = el("div", {className: "clips-caja", "data-clips-de": m.id}, [
    clips.length > 1 && m.estiloDe ? el("label", {className: "fila mut", style: "min-height:36px;font-size:13px"}, [
      el("span", {textContent: clave === "progresion" ? "Agrupar por progresión" : "Agrupar por estilo"}),
      el("input", {type: "checkbox", checked: !!agrupar, onchange: (e) => { escribirLocal("clips_por_estilo", e.target.checked ? "1" : "0"); renderMotores(); }})]) : null,
    lista,
    el("button", {type: "button", textContent: "+ Guardar lo que suena", onclick: () => hojaGuardarClip(m)}),
    fab.length ? recordar(el("details", {className: "voz"}, [el("summary", {}, [el("span", {textContent: "De fábrica"}), el("span", {className: "der mut", textContent: "uno por género"})]),
      el("div", {className: "cuerpo clips-fabrica", style: "padding-top:2px"}, fab.map((c) => el("button", {type: "button", className: "clip", "data-clip": c.nombre,
        onclick: () => intentar(() => m.lanzar({fabrica: c.fabrica}))}, [
        el("span", {className: "clip-nombre", textContent: c.nombre}),
        el("span", {className: "mut", textContent: m.estiloDe ? m.estiloDe(c) : "sin variante"})])))]), `fabrica-${m.motor}`, false) : null,
  ].filter(Boolean));
  setTimeout(pintarClips);
  return caja;
}

function hojaGuardarClip(m) {
  const nombre = el("input", {type: "text", value: m.nombrePorDefecto, maxLength: 40, "aria-label": "Nombre del clip"});
  const conSeed = el("input", {type: "checkbox", checked: true});
  let d;
  d = hoja("Guardar lo que suena", m.titulo, [
    el("label", {className: "campo"}, ["Nombre", nombre]),
    el("label", {className: "fila", style: "min-height:44px"}, [el("span", {}, ["Incluir la variante", el("br"),
      el("span", {className: "mut", textContent: `Con la seed ${m.seed}. Sin ella, al tocarlo se queda la variante que esté sonando`})]), conSeed]),
    el("div", {className: "acciones"}, [
      el("button", {type: "button", textContent: "Cancelar", onclick: () => d.close()}),
      el("button", {type: "button", className: "prim", textContent: "Guardar", onclick: () => intentar(async () => {
        await aplicarAntes(); await m.guardar({nombre: nombre.value, variante: conSeed.checked});
        d.close(); clipsAbiertos.add(m.id); await recargar(); aviso("Clip guardado"); })})]),
  ]);
  nombre.focus(); nombre.select();
}

function menuClip(m, c, ci) {
  const nombre = el("input", {type: "text", value: c.nombre, maxLength: 40, "aria-label": "Nombre del clip"});
  let d;
  d = hoja(c.nombre, [m.estiloDe ? m.estiloDe(c) : "", c.con_variante === false ? "sin variante" : c.seed].filter(Boolean).join(" · "), [
    el("label", {className: "campo"}, ["Renombrar", el("div", {style: "display:flex;gap:8px"}, [nombre,
      el("button", {type: "button", textContent: "Listo", onclick: () => intentar(async () => {
        await m.api("renombrar", {indice: ci, nombre: nombre.value}); d.close(); await recargar(); })})])]),
    el("div", {className: "acciones", style: "margin-top:12px"}, [
      el("button", {type: "button", className: "ancho", textContent: `Guardar lo que suena aquí (${m.quien})`, onclick: () => intentar(async () => {
        const antes = JSON.parse(JSON.stringify(c));
        await aplicarAntes(); await m.guardar({indice: ci}); d.close(); await recargar();
        avisoDeshacer(`«${c.nombre}» ahora guarda lo que suena`, async () => {
          await m.api("borrar", {indice: ci}); await m.api("restaurar", {indice: ci, clip: antes}); await recargar(); });
      })}),
      el("button", {type: "button", className: "ancho", style: "color:var(--bad);border-color:var(--badline)", textContent: "Borrar", onclick: () => intentar(async () => {
        const antes = JSON.parse(JSON.stringify(c));
        await m.api("borrar", {indice: ci}); d.close(); await recargar();
        avisoDeshacer(`Clip «${c.nombre}» borrado`, async () => { await m.api("restaurar", {indice: ci, clip: antes}); await recargar(); });
      })}),
    ]),
  ]);
}

// Lo que cambia de un motor a otro.
function clipsDeSecuencia(i, s) {
  return {id: `sec${i}`, motor: "secuencia", clips: cfg.clip, seed: s.seed, quien: `secuencia ${s.nombre}`,
    titulo: `Secuencia ${s.nombre} · ${nombreEstilo(s.estilo)}`, nombrePorDefecto: `${nombreEstilo(s.estilo)} ${s.seed}`,
    estiloDe: (c) => nombreEstilo(c.estilo), nombreEstilo, ordenEstilos: ORDEN_ESTILOS,
    lanzar: async (q) => { await api("/api/lanzar", Object.assign({fila: i}, q)); await recargar(); estado(); },
    parar: async () => { await api("/api/detener", {fila: i}); await recargar(); estado(); },
    guardar: (q) => api("/api/clip/guardar", Object.assign({fila: i}, q)),
    api: (accion, q) => api(`/api/clip/${accion}`, q)};
}
const nombreBajo = (v) => (ESTILOS_BAJO.find((x) => x[0] === v) || [, v])[1];
const nombreProgresion = (v) => ((PROGRESIONES.find((x) => x[0] === v) || [, v || ""])[1] || "").split(" · ")[0];
const CLIPS_MOTOR = {
  bajo: {titulo: "Bajo", estiloDe: (c) => nombreBajo(c.estilo), nombreEstilo: nombreBajo, ordenEstilos: () => ESTILOS_BAJO.map((x) => x[0])},
  pads: {titulo: "Pads", estiloDe: (c) => nombreProgresion(c.progresion), nombreEstilo: nombreProgresion, ordenEstilos: () => PROGRESIONES.map((x) => x[0]), claveEstilo: "progresion"},
  dialogo: {titulo: "Diálogo", estiloDe: null},
};
function clipsDeMotor(motor) {
  const o = CLIPS_MOTOR[motor];
  const sec = cfg[motor];
  return {id: motor, motor, clips: listaClipsDe(motor), seed: sec.seed, quien: o.titulo.toLowerCase(), titulo: o.titulo,
    nombrePorDefecto: `${o.estiloDe ? o.estiloDe(sec) + " " : ""}${sec.seed}`, estiloDe: o.estiloDe, nombreEstilo: o.nombreEstilo,
    ordenEstilos: o.ordenEstilos ? o.ordenEstilos() : [], claveEstilo: o.claveEstilo,
    lanzar: async (q) => { await aplicarAntes(); await api("/api/motor/clip/lanzar", Object.assign({motor}, q)); await recargar(); estado(); },
    parar: async () => { await aplicarAntes(); await api("/api/motor/clip/parar", {motor}); await recargar(); estado(); },
    guardar: (q) => api("/api/motor/clip/guardar", Object.assign({motor}, q)),
    api: (accion, q) => api(`/api/motor/clip/${accion}`, Object.assign({motor}, q))};
}

// La tarjeta Variante. obj: la sección con su seed · clave: dónde guarda A/B en este teléfono ·
// id: el motor para los clips (o null si ese motor no tiene clips).
function bloqueVariante(obj, clave, id, titulo = "Variante") {
  const m = id ? (id.startsWith("sec") ? clipsDeSecuencia(parseInt(id.slice(3)), obj) : clipsDeMotor(id)) : null;
  if (m) cargarFabrica(m.motor);
  const seed = el("input", {type: "text", value: obj.seed, style: "font-family:ui-monospace,Menlo,monospace", "aria-label": `${titulo} escrita a mano`,
    onchange: (e) => { const v = e.target.value.trim(); if (v && v !== obj.seed) { obj.seed = v; guardar(); renderMotores(); } }});
  const ab = varianteAB(obj, clave);
  const seedCab = el("span", {className: "seed-cab", textContent: obj.seed});
  const clip = id ? nombreClipDe(id) : "";
  // El «Otra» de arriba es el mismo de A/B: la que probabas pasa al historial y la nueva queda en B.
  ab.addEventListener("click", () => setTimeout(() => { seedCab.textContent = obj.seed; }));
  const otra = el("button", {type: "button", className: "prim otra-cab", textContent: "Otra", "aria-label": `Otra ${titulo.toLowerCase()}`,
    onclick: (e) => { e.preventDefault(); e.stopPropagation(); ab.querySelector(".ab-fila .prim").click(); seedCab.textContent = obj.seed; }});
  return recordar(el("details", {className: "card variante-card"}, [
    el("summary", {}, [
      el("span", {className: "cab"}, [el("b", {textContent: titulo}),
        id ? el("span", {"data-sub-clip": id, textContent: clip ? `Clip: ${clip}` : "Sin clip"}) : el("span", {textContent: "la seed arma las notas"})]),
      seedCab, otra]),
    el("div", {className: "cuerpo"}, [
      m ? el("div", {className: "fila", style: "gap:8px;justify-content:flex-end"}, [pestanaClip(id)]) : null,
      m && clipsAbiertos.has(id) ? cajaClips(m) : null,
      ab,
      el("details", {className: "voz"}, [el("summary", {}, [el("span", {textContent: "Escrita a mano"}), el("span", {className: "der", textContent: obj.seed})]),
        el("div", {className: "cuerpo"}, [el("label", {className: "campo"}, ["Seed (cualquier texto)", seed])])]),
    ].filter(Boolean)),
  ]), `variante-${clave}`, false);
}

function pintarFila(caja, f) {
  caja.querySelectorAll("[data-clip]").forEach((b) => {
    const n = b.dataset.clip;
    b.classList.toggle("cola", f.cola === n);
    b.classList.toggle("sonando", !!f.activa && f.clip === n && f.cola !== n);
  });
  const parar = caja.querySelector("[data-parar]");
  if (parar) parar.classList.toggle("cola", f.cola === "detener");
}

// Largo del patrón (secuencia y tocado): atajos y cualquier número de 2 a 64.
function campoLargo(s) {
  if (FRASEADOS.includes(s.estilo)) return [ayuda(`Con ${nombreEstilo(s.estilo)} el largo lo da la frase (en Estilo).`)];
  return [
    campo("Largo del patrón · de 2 a 64 pasos", segmentado([["16","16"],["13","13"],["11","11"],["7","7"]], String(s.largo), (v) => { s.largo = parseInt(v); renderMotores(); guardar(); }, 4)),
    numeroDe(s, "largo", "Pasos", 2, 64, renderMotores),
    ayuda("16 da un compás; 32 o 64, dos o cuatro. 13, 11 o 7 se desfasan contra el compás y el patrón va girando (polirritmia)."),
  ];
}

function panelSecuencia(i) {
  const s = cfg.secuencia[i];
  const texto = (k, etiqueta, extra = {}) => {
    const inp = el("input", Object.assign({type: "text", value: s[k],
      onchange: () => { s[k] = inp.value.trim() || s[k]; inp.value = s[k]; renderMotores(); renderMutes(); guardar(); }}, extra));
    return el("label", {className: "campo"}, [etiqueta, inp]);
  };
  const conFrase = FRASEADOS.includes(s.estilo);
  const usaCada = s.mutacion > 0 || s.mutacion_ritmo > 0 || s.molde_muta > 0;
  const pos = POSICIONES.find((x) => x[0] === s.posicion)[1].toLowerCase();
  const rel = RELACIONES.find((x) => x[0] === s.relacion)[1].toLowerCase();
  return [
    cabMotor(`Secuencia ${s.nombre}`, `${s.salida} · canal ${s.canal} · ${armoniaTexto(s)}`, s, "activa", null, botonFabrica(i, s)),
    franjaPatron(i),
    estiloDeSecuencia(s, "sec-estilo"),
    bloqueVariante(s, `sec-${s.nombre}`, `sec${i}`),
    el("div", {className: "grupos"}, [
      grupo("sec-mas", "Más o menos notas", [porcentaje(s.densidad), pos, conFrase ? `frase de ${s.frase || 2}` : `${s.largo} pasos`, `largo ${gateTexto(s.gate)}`, s.filtro ? "con filtro" : ""].filter(Boolean).join(" · "), [
        deslizador(s, "densidad", "Densidad", 0, 1, 0.05, (v) => v === 1 ? "todas las notas" : porcentaje(v)),
        campo("Dónde caen las notas", segmentado(POSICIONES, s.posicion, (v) => { s.posicion = v; renderMotores(); guardar(); }, 2)),
        ayuda(POS_TEXTO[s.posicion]),
        ...campoLargo(s),
        deslizador(s, "gate", "Largo de las notas", 0.05, 1, 0.05, (v) => `${gateTexto(v)} (${porcentaje(v)})`),
        deslizador(s, "gate_random", "Variación del largo", 0, 1, 0.05, porcentaje),
        deslizador(s, "largas", "Notas sostenidas sobre los silencios", 0, 1, 0.05, porcentaje),
        el("span", {className: "familia-nombre", textContent: "Filtro y orden"}),
        moldeEditor(s, "La seed arma las notas y el filtro decide cuáles pasan: ● = pasa, ? = a veces, vacío = bloqueado. Cambiar la seed cambia las notas que pasan.",
          null, "Orden de los pasos", () => s.mutar_cada, () => renderMotores()),
      ]),
      grupo("sec-mutar", "Que cambie solo", s.bloqueada ? "congelada" : !usaCada ? "fija" :
        [s.mutacion ? `notas ${porcentaje(s.mutacion)}` : "", s.mutacion_ritmo ? `ritmo ${porcentaje(s.mutacion_ritmo)}` : "", s.molde_muta ? "filtro" : "", `cada ${s.mutar_cada}`].filter(Boolean).join(" · "), [
        deslizador(s, "mutacion", "Mutación de notas", 0, 1, 0.05, (v) => s.bloqueada ? "congelada" : v === 0 ? "fija" : porcentaje(v), () => renderMotores()),
        deslizador(s, "mutacion_ritmo", "Mutación de ritmo", 0, 1, 0.05, (v) => s.bloqueada ? "congelada" : v === 0 ? "apagada" : porcentaje(v), () => renderMotores()),
        ayuda("Además de las notas, el ritmo cambia de a poco: mueve una nota a un lugar vecino, agrega o quita una, o vuelve al ritmo original. Respeta dónde caen las notas y la cantidad se mantiene cerca de la original."),
        usaCada ? numeroDe(s, "mutar_cada", "Cada (compases, de 1 a 64)", 1, 64, () => renderMotores()) : null,
        usaCada && s.molde_muta > 0 ? ayuda("También marca cada cuánto muta el filtro de notas.") : null,
        casilla(s, "bloqueada", "Congelar el patrón", "La mutación no lo cambia (un clip guardado congelado entra congelado)", () => renderMotores()),
      ]),
      grupo("sec-groove", "Groove", [`swing ${Math.round(s.swing * 200)} %`, `acentos ${porcentaje(s.acentos)}`, s.repeticion ? `redobles ${porcentaje(s.repeticion)}` : "sin redobles",
        i > 0 && (s.corrimiento || s.complementar || s.separar) ? "con la otra voz" : ""].filter(Boolean).join(" · "), [
        deslizador(s, "swing", "Swing", 0, 0.5, 0.05, (v) => Math.round(v * 200) + " %"),
        deslizador(s, "acentos", "Acentos", 0, 1, 0.05, porcentaje),
        ayuda("En Ácido 303, acentos y slides son la cantidad total; en los otros estilos se suman."),
        el("div", {className: "dos"}, [numeroDe(s, "velocidad", "Fuerza normal (1-127)", 1, 127), numeroDe(s, "acento", "Fuerza del acento (1-127)", 1, 127)]),
        deslizador(s, "vel_random", "Variación de fuerza", 0, 1, 0.05, porcentaje),
        deslizador(s, "repeticion", "Redobles", 0, 1, 0.05, porcentaje),
        ...(i > 0 ? [
          el("span", {className: "familia-nombre", textContent: "Con la otra voz"}),
          ayuda(`Para que dos secuencias no se pisen. Esta mira a la primera secuencia activa de la lista (la ${cfg.secuencia[0].nombre || "1"}, normalmente el lead). Todo es opcional: en cero toca libre.`),
          deslizador(s, "corrimiento", "Corrimiento", 0, 15, 1, (v) => v === 0 ? "en su lugar" : `entra ${v} semicorchea${v > 1 ? "s" : ""} tarde`),
          ayuda("Corre el patrón dentro de la rejilla. 1 o 3 suelen caer en los huecos del lead; 2 lo pone a contratiempo. Moverlo en vivo es un efecto en sí."),
          deslizador(s, "complementar", "Complementar", 0, 1, 0.05, (v) => v === 0 ? "apagado" : v <= 0.5 ? `${porcentaje(v)} · cede en los tiempos y acentos del lead` : v < 1 ? `${porcentaje(v)} · cede también en el resto` : "100 % · hocket: solo en los huecos del lead"),
          ayuda("Calla donde el lead ataca: hasta 50 % cede en sus tiempos fuertes y acentos, más arriba también en las demás notas. Al 100 % las dos voces arman una sola línea (hocket). Necesita un lead con huecos: con un pedal que toca todas las semicorcheas, esta voz se queda casi muda."),
          casilla(s, "separar", "Separar las notas", "Arregla los choques con el lead. En las notas: si choca de cerca (segunda, séptima o tritono a menos de una octava, o la misma nota), va a la nota consonante más cercana, primero del acorde; la ♭9 del frigio (raíz abajo, ♭2 arriba) se respeta, y si el lead ataca encima de una nota larga que choca, esa nota se corta. En el ritmo: las notas corridas (tresillos, swing) que caerían pegadas a un golpe del lead se alinean con él, para que no suenen como flam", () => renderMotores()),
        ] : []),
      ]),
      grupo("sec-altura", "Altura", [octavaTexto(s.octava), `desde ${rel}`, `slides ${porcentaje(s.slide)}`, s.raga ? `raga ${s.raga}` : "", s.escala_color ? "color" : ""].filter(Boolean).join(" · "), [
        deslizador(s, "octava", "Octava (brillo)", -3, 3, 1, octavaTexto),
        campo("Parte desde", segmentado(RELACIONES, s.relacion, (v) => { s.relacion = v; renderMotores(); guardar(); }, 2)),
        deslizador(s, "saltos", "Saltos de octava", 0, 1, 0.05, porcentaje),
        deslizador(s, "slide", "Slides", 0, 1, 0.05, porcentaje),
        ayuda("Para que los slides deslicen, pon el sinte en mono o legato con glide."),
        deslizador(s, "pedal", "Vuelve a la nota larga", 0, 1, 0.05, porcentaje),
        ayuda("Cuánto regresa a la nota base entre las demás: más alto, más hipnótico."),
        deslizador(s, "deslices", "Deslices de notas", 0, 1, 0.05, (v) => v === 0 ? "apagado" : porcentaje(v)),
        ayuda("Opcional. Notas que respiran (se sostienen sobre la raíz que sigue), notas llenas y aproximaciones por grado al adorno que viene, todo en la rejilla y sin pisarse. No cambia la escala."),
        campo("Voz doble", segmentado([["","No"],["tercera","3.ª"],["cuarta","4.ª"],["quinta","5.ª"],["sexta","6.ª"],["octava","8.ª"]], s.doble || "", (v) => { s.doble = v; guardar(); }, 6)),
        ayuda("Una segunda voz paralela por grados de la escala, un poco más suave (como los stabs de dos notas de los packs). Necesita un sinte polifónico."),
        deslizador(s, "techo", "Techo (nota más alta)", 36, 127, 1, (v) => v >= 127 ? "sin techo" : `${nombreMidi(v)} · lo de arriba baja una octava`),
        ayuda("Si una seed o el director la llevan muy aguda, lo que pasa del techo vuelve a sonar una octava abajo: misma nota, mismo ritmo."),
        deslizador(s, "semitono", "♭2 (medio tono sobre la raíz)", 0, 1, 0.05, (v) => v === 0 ? "como sale" : porcentaje(v)),
        ayuda("Cambia notas de los pasos débiles por el medio tono sobre la raíz: la tensión hipnótica del psytrance. Los tiempos fuertes quedan firmes."),
        campo("Escala de color", segmentado(ESCALAS_COLOR, s.escala_color || "", (v) => { s.escala_color = v; renderMotores(); guardar(); }, 2)),
        ayuda(COLOR_TEXTO[s.escala_color || ""]),
        campo("Raga", segmentado(RAGAS, s.raga || "", (v) => { s.raga = v; renderMotores(); guardar(); }, 3)),
        ayuda(RAGA_TEXTO[s.raga || ""]),
        ...(s.raga ? [
          deslizador(s, "ornamentos", "Ornamentos de la raga", 0, 1, 0.05, (v) => v === 0 ? "solo la escala" : v < 0.3 ? `${porcentaje(v)} · sin frase típica` : `${porcentaje(v)} · con frase típica`),
          numeroDe(s, "bend_rango", "Rango de pitch bend del sinte (semitonos, 0 = sin bend)", 0, 24),
          ayuda("Todo cae en la rejilla de semicorcheas, sin fusas ni notas pisadas: los ornamentos toman los pasos de nota fija (Sa o Pa) que rodean a la nota adornada. Kan: el paso antes lleva la gracia que manda la raga. Gamak: los pasos después de una nota que tiembla hacen el trino (vecina, nota). Meend: la nota llega deslizándose con el pitch bend (pon el rango de tu sinte; 0 = sin bend). Andolan: vaivén de un cuarto de tono en las notas que tiemblan cuando se sostienen. Desde 30 %, en Goa clásico la respuesta cierra con la frase típica de la raga."),
        ] : []),
        armoniaPropia(s, () => renderMotores()),
      ]),
      grupo("sec-sonido", "Sonido del sinte", [`filtro CC ${s.cc_filtro}`, s.subida_filtro ? "se abre en las subidas" : "", lfoResumen(s) === "apagado" ? "" : lfoResumen(s), s.fx ? "la interviene el FX" : ""].filter(Boolean).join(" · "), [
        el("div", {className: "dos"}, [numeroDe(s, "cc_filtro", "CC del filtro (0-127)", 0, 127), numeroDe(s, "filtro_reposo", "Reposo (0-127)", 0, 127)]),
        ayuda("El reposo es dónde vuelve el filtro después de una subida: ponlo donde tienes la perilla del sinte. CC 74 = corte en la MC-101 y en la FM-1 con Shrub; en la MicroFreak es el 23."),
        el("label", {className: "fila", style: "min-height:44px"}, [
          el("span", {}, ["Se abre en las subidas", el("br"), el("span", {className: "mut", textContent: "Durante el rise el filtro se va abriendo hasta el drop"})]),
          el("input", {type: "checkbox", className: "switch", checked: !!s.subida_filtro, "aria-label": "Se abre en las subidas",
            onchange: (e) => { s.subida_filtro = e.target.checked; guardar(); renderMotores(); }})]),
        ...(s.subida_filtro ? [
          deslizador(s, "subida_desde", "Parte en", 0, 127, 1, (x) => `${x} (${Math.round(x / 1.27)} %)`),
          deslizador(s, "subida_hasta", "Al final de la subida", 0, 127, 1, (x) => x >= 127 ? "abierto del todo (127)" : `${x} (${Math.round(x / 1.27)} %)`),
          campo("Después del drop", segmentado([["vuelve","Vuelve al reposo"],["queda","Se queda ahí"]], s.subida_despues || "vuelve", (v) => { s.subida_despues = v; guardar(); renderMotores(); }, 2)),
          ayuda("Se abre cada vez más rápido y llega a «Al final de la subida» justo en el drop. Mientras dura la subida, un LFO sobre el mismo CC espera."),
        ] : []),
        ...editorLfo(s, "lfo", "LFO 1"),
        ...editorLfo(s, "lfo2", "LFO 2"),
        ayuda("Van sincronizados al compás y pueden mover cosas distintas a la vez (por ejemplo, corte y resonancia). Si el motor de FX interviene el mismo filtro en una subida, ese LFO espera y sigue después."),
        casilla(s, "fx", "La interviene el motor de FX",
          "En las subidas su filtro baja y se va abriendo hasta el drop, y suma redobles cada vez más seguidos. Fuera de las subidas, a veces el último tiempo de la frase se traba (stutter). Cuánto, lo decide la Locura del FX.", () => renderMotores()),
        s.fx && !s.subida_filtro ? deslizador(s, "subida_hasta", "Filtro al final de la subida", 0, 127, 1, (x) => x >= 127 ? "abierto del todo (127)" : `${x} (${Math.round(x / 1.27)} %)`) : null,
      ]),
      grupo("sec-midi", "Salida MIDI", salidaTexto(s), [
        el("div", {className: "dos"}, [texto("nombre", "Nombre", {maxLength: 12}), destinoDe(s, renderMotores)]),
        el("div", {className: "dos"}, [numeroDe(s, "canal", "Canal MIDI", 1, 16, renderMotores), numeroDe(s, "disparo", "Canal de su nota larga (0 = general)", 0, 16, renderMotores)]),
        programaDe(s),
        el("button", {type: "button", textContent: "Eliminar secuencia", style: "color:var(--bad);border-color:var(--badline)",
          onclick: async () => { cfg.secuencia.splice(i, 1); motorSel = "pads"; render(); await enviarConfig(); avisoDeshacer(`Secuencia ${s.nombre} eliminada`, deshacerUltimo); }}),
      ]),
    ]),
  ].filter(Boolean);
}

// --- Lo que toca ahora: la franja de arriba del editor de secuencia ---
let patronTimer = null;
function franjaPatron(i) {
  const barras = el("div", {className: "pt-barras"});
  const info = el("span", {className: "mut", textContent: ""});
  const rango = el("span", {className: "mut", textContent: ""});
  const caja = el("div", {className: "card pt", "aria-label": "Lo que toca ahora"}, [
    el("div", {className: "fila", style: "gap:8px"}, [el("b", {textContent: "Lo que toca ahora"}), info]),
    barras, rango]);
  let firma = "";
  const pintar = (d) => {
    if (!d.corriendo || !d.activa) {
      if (firma !== "quieto" + d.activa) {
        firma = "quieto" + d.activa;
        barras.replaceChildren(el("p", {className: "mut pt-vacio", textContent: !d.activa ? "No suena: actívala arriba para oírla." : "Dale Play para ver lo que toca."}));
        info.textContent = ""; rango.textContent = "";
      }
      return;
    }
    const pasos = d.pasos.length ? d.pasos : Array(d.largo).fill(null);
    const notas = pasos.filter(Boolean).map((p) => p[0]);
    const bajo = notas.length ? Math.min(...notas) : 60, alto = notas.length ? Math.max(...notas) : 60;
    const nueva = JSON.stringify(pasos);
    if (nueva !== firma) {
      firma = nueva;
      const filas = [];
      for (let f = 0; f < pasos.length; f += 16) {
        filas.push(el("div", {className: "pt-fila"}, pasos.slice(f, f + 16).map((p, k) => {
          const n = f + k;
          const alto100 = p ? 22 + Math.round(78 * (alto > bajo ? (p[0] - bajo) / (alto - bajo) : 0.5)) : 0;
          return el("div", {className: "pt-paso" + (p ? (p[1] ? " fuerte" : "") : " calla") + (n % 4 === 0 ? " tiempo" : ""), "data-n": n,
            title: p ? nombreMidi(p[0]) : "silencio"}, [el("i", {style: p ? `height:${alto100}%` : ""})]);
        })));
      }
      barras.replaceChildren(...filas);
      rango.textContent = notas.length ? (bajo === alto ? nombreMidi(bajo) : `de ${nombreMidi(bajo)} a ${nombreMidi(alto)}`) + ` · ${notas.length} notas de ${pasos.length} pasos`
        : d.raiz === false ? `espera su nota larga (canal ${cfg.secuencia[i].disparo || "general"} de la Circuit)` : "calla en esta vuelta";
    }
    barras.querySelectorAll(".pt-paso.ahora").forEach((x) => x.classList.remove("ahora"));
    if (d.ahora !== null) {
      const c = barras.querySelector(`.pt-paso[data-n="${d.ahora}"]`);
      if (c) c.classList.add("ahora");
      info.textContent = `paso ${d.ahora + 1} / ${pasos.length}`;
    }
  };
  clearInterval(patronTimer);
  const pedir = async () => {
    if (!document.body.contains(caja) || vista !== "motores" || document.hidden) {
      if (!document.body.contains(caja)) clearInterval(patronTimer);
      return;
    }
    try { const r = await fetch(`/api/patron?sec=${i}`); if (r.ok) pintar(await r.json()); } catch (e) {}
  };
  patronTimer = setInterval(pedir, 250);
  setTimeout(pedir, 0);
  return caja;
}

// --- Variante A/B: comparar la guardada con la que estás probando ---
function varianteAB(obj, clave) {
  const leer = () => { try { return JSON.parse(leerLocal("ab:" + clave, "null")); } catch (e) { return null; } };
  let v = leer();
  // Si la seed cambió por fuera (otra parte, un clip, deshacer), la que suena pasa a ser la A.
  if (!v || (obj.seed !== v.a && obj.seed !== v.b)) v = {a: obj.seed, b: null, hist: (v && v.hist) || [], fav: (v && v.fav) || []};
  const escribir = () => { v.hist = v.hist.filter((x, k, h) => x && x !== v.a && x !== v.b && h.indexOf(x) === k).slice(-8); escribirLocal("ab:" + clave, JSON.stringify(v)); };
  const oir = (seed) => { obj.seed = seed; escribir(); guardar(); repintar(); };
  const caja = el("div", {className: "ab"});
  const repintar = () => {
    const oye = obj.seed === v.a ? "a" : "b";
    const boton = (letra, texto, seed) => el("button", {type: "button", className: "ab-op" + (oye === letra ? " oye" : ""), "aria-pressed": oye === letra ? "true" : "false",
      disabled: !seed, onclick: () => seed && oir(seed)}, [
      el("b", {textContent: `${letra.toUpperCase()} · ${texto}`}), el("span", {className: "ab-seed", textContent: seed ? (v.fav.includes(seed) ? "★ " : "") + seed : "—"})]);
    const otra = el("button", {type: "button", className: "prim", textContent: "Otra", onclick: () => {
      if (v.b) v.hist.push(v.b);
      v.b = seedNueva(); oir(v.b); }});
    const acciones = [];
    if (v.b) {
      acciones.push(el("button", {type: "button", textContent: oye === "b" ? "Quedarme con B" : "Quedarme con A", onclick: () => {
        if (oye === "b") { v.hist.push(v.a); v.a = v.b; } else v.hist.push(v.b);
        v.b = null; oir(v.a); aviso(`Variante ${v.a} guardada`); }}));
    }
    const actual = obj.seed;
    acciones.push(el("button", {type: "button", textContent: v.fav.includes(actual) ? "★ Favorita" : "☆ Marcar favorita", className: v.fav.includes(actual) ? "activo" : "",
      onclick: () => { v.fav = v.fav.includes(actual) ? v.fav.filter((x) => x !== actual) : v.fav.concat([actual]).slice(-12); escribir(); repintar(); }}));
    const sonaron = [...v.fav.filter((x) => x !== v.a && x !== v.b), ...v.hist.slice().reverse().filter((x) => !v.fav.includes(x))].slice(0, 8);
    caja.replaceChildren(
      el("div", {className: "ab-fila"}, [boton("a", "la guardada", v.a), boton("b", "probando", v.b), otra]),
      el("div", {className: "molde-presets"}, acciones),
      sonaron.length ? el("div", {className: "chips ab-hist"}, [el("span", {className: "mut", textContent: "Sonaron:"}),
        ...sonaron.map((x) => el("button", {type: "button", textContent: (v.fav.includes(x) ? "★ " : "") + x, "aria-label": `Probar ${x}`,
          onclick: () => { if (v.b && v.b !== x) v.hist.push(v.b); v.b = x; oir(x); }}))]) : el("span", {hidden: true}),
    );
  };
  escribir(); repintar();
  return caja;
}

// --- Copiar un motor a otras partes (desde el editor) ---
function copiarMotorA(clave, nombre) {
  const desde = editandoVista() ? parteVista : -1;
  const partes = cfg.parte.map((p, j) => [p, j]).filter(([, j]) => j !== desde);
  const marcas = partes.map(([p, j]) => el("input", {type: "checkbox", "aria-label": p.nombre, "data-j": j}));
  let d;
  d = hoja(`Copiar ${nombre}`, desde >= 0 ? `Desde ${cfg.parte[desde].nombre}. En las partes que elijas, solo cambia este motor.` : "Lo que suena ahora. En las partes que elijas, solo cambia este motor.", [
    el("div", {style: "display:flex;flex-direction:column;gap:2px;max-height:50vh;overflow:auto;margin-bottom:12px"}, partes.map(([p, j], n) =>
      el("label", {className: "fila", style: "min-height:44px;justify-content:flex-start;gap:12px"}, [marcas[n],
        el("span", {}, [p.nombre, el("br"), el("span", {className: "mut", style: "font-size:12px", textContent: `${p.compases} compases`})])]))),
    el("div", {className: "acciones"}, [
      el("button", {type: "button", textContent: "Cancelar", onclick: () => d.close()}),
      el("button", {type: "button", className: "prim", textContent: "Copiar", onclick: async () => {
        const hacia = marcas.filter((x) => x.checked).map((x) => parseInt(x.dataset.j));
        if (!hacia.length) { d.close(); return; }
        let r = null;
        try { r = await api("/api/parte/copiar", {desde, hacia, motores: [clave]}); } catch (e) { aviso(e.message, true); }
        d.close();
        if (r) { aviso(`Copiado a ${hacia.length} parte${hacia.length > 1 ? "s" : ""}: ${nombre}`); await recargar(); }
      }}),
    ]),
  ]);
}

const FRASEADOS = ["clasico", "psytrance"];  // estilos cuyo patrón dura una frase de 2 o 4 compases
const FIGURAS_PSY = [["auto","Auto (seed)"],["riff","Riff"],["rafaga","Ráfaga"],["octavas","Octavas"],["arpegio","Arpegio"],["pulsos","Pulsos"],
  ["espacio","Espacio ✦"],["mantra","Mantra ✦"],["tresillo","Tresillo ✦"],["descenso","Descenso ✦"],["puntillo","Puntillo"],["melodia","Melodía"]];
const FIGURA_PSY_TEXTO = {
  auto: "La seed elige la figura: cambia la seed para pasar por las cinco.",
  riff: "El riff del psytrance: deja huecos donde cae el bombo, raíz en dos octavas y el color (♭7, ♭3, ♭2) al cierre de cada medio compás. Notas cortas, alguna larga de acento.",
  rafaga: "Un bloque de notas iguales a mitad de compás que cambia de altura en cada compás (4.ª, raíz, ♭7…): una progresión hecha con el riff.",
  octavas: "Rolling de octavas (semicorcheas, o corcheas con más huecos); el paso 15 cambia de color en cada compás.",
  arpegio: "Célula de 8 pasos con silencios, raíz alta y color de acorde (♭3, 5.ª, ♭7) en sus notas interiores.",
  pulsos: "Negras de raíz en octavas que se sostienen; el último tiempo cambia de nota en cada compás. Para bajo, stabs o un lead que respira.",
  espacio: "✦ Místico. Solo raíz, octava (notas de un tiempo y medio) y una nota corta en el contratiempo: lo místico es el aire. Más huecos, más silencio.",
  mantra: "✦ Místico. Drone de raíz de tres tiempos y, al final de la frase, un canto lento en negras con anacrusa de ♭7. Con la raga Hijaz canta 1 ♭2 3 ♭2.",
  tresillo: "✦ Místico. Tresillos de corchea (raíz, ♭2, 4.ª) y tresillos de negra sobre el 4/4: el galope oriental.",
  puntillo: "Notas cada 3 semicorcheas (3-3-2, 3-3-3-3-2-2): el acento cruza el compás sin salir de la rejilla. Raíz con alguna octava y color al final del compás. Huecos elige de la máscara más llena a la más vacía.",
  melodia: "Una línea por grados que sube en el compás A, baja desde el ♭6 en el B y resuelve en la raíz al cerrar la frase. Con armonía guiada y pads cae en el acorde; con menor armónica suena a drop de psytrance.",
  descenso: "✦ Místico. La raíz en cada tiempo y entre medio una línea que baja por la escala (♭7 ♭6 5 4), acento en el tres."};
function panelPsy(s) {
  const fig = s.figura && FIGURAS_PSY.some((f) => f[0] === s.figura) ? s.figura : "auto";
  return [el("div", {className: "card principales"}, [
    campo("Figura", segmentado(FIGURAS_PSY, fig, (v) => { s.figura = v; renderMotores(); guardar(); }, 3)),
    ayuda(FIGURA_PSY_TEXTO[fig]),
    deslizador(s, "huecos", "Huecos", 0, 1, 0.05, (v) => v < 0.3 ? `${porcentaje(v)} · riff lleno` : v < 0.7 ? `${porcentaje(v)} · clásico` : `${porcentaje(v)} · mucho aire`),
    ayuda("De la máscara de riff más llena a la más vacía (sacadas de un pack de psytrance). En octavas pasa a corcheas y en pulsos acorta las notas."),
    campo("Frase", segmentado([["2","2 compases (A B)"],["4","4 compases (A B A C)"]], String(s.frase || 2), (v) => { s.frase = parseInt(v); guardar(); }, 2)),
    deslizador(s, "remate", "Respuesta (cuánto cambia el compás B)", 0, 1, 0.05, (v) => v === 0 ? "loop exacto" : porcentaje(v)),
    deslizador(s, "variar", "Respuestas distintas", 0, 1, 0.05, (v) => { const n = 1 + Math.round(v * 3); return n === 1 ? "siempre la misma" : `${n} respuestas que se turnan`; }),
  ])];
}

// Goa clásico: figura, frase y respuesta (solo con ese estilo).
const FIGURAS = [["auto","Auto (seed)"],["pedal","Pedal"],["ciclo","Ciclo"],["acordes","Acordes"]];
const FIGURA_TEXTO = {
  auto: "La seed elige la figura: cambia la seed para pasar por las tres.",
  pedal: "Rodante: las 16 semicorcheas con la raíz en dos octavas y adornos que vuelven (♭2, ♭7, 4.ª, 5.ª).",
  ciclo: "Un motivo de 3, 5, 6 o 7 notas que corre sobre el compás: el acento se va corriendo y vuelve a calzar al empezar la frase.",
  acordes: "Arpegio por tiempo (raíz, octava, tercera o segunda arriba) que sigue el acorde que suena. Con pads o armonía guiada cambia con la progresión."};
const RAGAS = [["","Sin raga"],["bhairav","Bhairav"],["bhairavi","Bhairavi"],["todi","Todi"],["marwa","Marwa"],["hijaz","Hijaz (israelí)"]];
const RAGA_TEXTO = {
  "": "Sin raga: la secuencia usa la escala de Música (o su escala de color).",
  bhairav: "1 ♭2 3 4 5 ♭6 7 · la doble armónica de Bhairav: re y dha tiemblan, el re llega con gracia del ga y cierra con G m r S. La más «Goa».",
  bhairavi: "1 ♭2 ♭3 4 5 ♭6 ♭7 · todo komal (frigio): devocional, oscura. Cierra con m g r S.",
  todi: "1 ♭2 ♭3 ♯4 5 ♭6 7 · seria, mucho pathos: el re toma su gracia del ga y tiembla. Cierra con g r g r S.",
  marwa: "1 ♭2 3 ♯4 5 6 7 · crepuscular e inquieta: el re pesa más que la tónica. Cierra con G M G r S.",
  hijaz: "1 ♭2 3 4 5 ♭6 ♭7 · freygish / Ahava Rabbah del Goa israelí: segunda aumentada, trino en el ♭2 y la caída ♭6 5 4 3 ♭2 1."};

function panelClasico(s) {
  const fig = s.figura && FIGURAS.some((f) => f[0] === s.figura) ? s.figura : "auto";
  const conCiclo = fig === "ciclo" || fig === "auto";
  return [el("div", {className: "card principales"}, [
    campo("Figura", segmentado(FIGURAS, fig, (v) => { s.figura = v; renderMotores(); guardar(); }, 2)),
    ayuda(FIGURA_TEXTO[fig]),
    campo("Frase", segmentado([["2","2 compases (A B)"],["4","4 compases (A B A C)"]], String(s.frase || 2), (v) => { s.frase = parseInt(v); guardar(); }, 2)),
    deslizador(s, "remate", "Respuesta (cuánto cambia la segunda mitad)", 0, 1, 0.05, (v) => v === 0 ? "loop exacto" : v < 0.4 ? "sutil" : v < 0.75 ? porcentaje(v) : `${porcentaje(v)} · con corrida`),
    deslizador(s, "variar", "Respuestas distintas", 0, 1, 0.05, (v) => { const n = 1 + Math.round(v * 3); return n === 1 ? "siempre la misma" : `${n} respuestas que se turnan`; }),
    ayuda("Cada vez que vuelve la frase toca otra respuesta (el compás A queda igual) y después de unas vueltas regresa a la primera."),
    ...(conCiclo ? [
      campo("Largo del ciclo", segmentado([["0","Seed"],["3","3"],["5","5"],["6","6"],["7","7"]], String(s.ciclo || 0), (v) => { s.ciclo = parseInt(v); guardar(); }, 5)),
      campo("Octavas del ciclo", segmentado([["1","1"],["2","2"],["3","3"]], String(s.registro || 2), (v) => { s.registro = parseInt(v); guardar(); }, 3)),
    ] : []),
    ayuda("«Vuelve a la nota larga» (en Notas) regula cuánta raíz lleva el pedal. La mutación cambia una nota y todas sus repeticiones, sin tocar la raíz."),
  ])];
}

function nombreMidi(n) {
  return ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"][n % 12] + (Math.floor(n / 12) - 1);
}

function h3(texto) { return el("h3", {textContent: texto}); }

function agregarSecuencia() {
  const base = cfg.secuencia[cfg.secuencia.length - 1] || {salida: "FM-1", canal: 2, estilo: "rolling", posicion: "offbeat", relacion: "unisono",
    octava: 0, largo: 16, gate: 0.55, pedal: 0.5, mutacion: 0, mutar_cada: 8, mutacion_ritmo: 0, bloqueada: false, programa: 0, velocidad: 96, acento: 124, genero: cfg.musica.genero};
  const usadas = new Set(cfg.secuencia.map((s) => s.nombre));
  let letra = "A";
  for (let k = 0; k < 26; k++) { letra = String.fromCharCode(65 + k); if (!usadas.has(letra)) break; }
  cfg.secuencia.push(Object.assign({}, base, {nombre: letra, seed: seedNueva(), activa: true}));
  motorSel = "sec" + (cfg.secuencia.length - 1); escribirLocal("motor", motorSel);
  render(); guardar();
}

// --- Diálogo ---

function golpesTexto(d, v, papel) {
  // Cuántos golpes caben de verdad: en el entrelazado, la respuesta vive en los huecos.
  const lugares = d.rejilla === "corcheas" ? 8 : 16;
  const pedido = Math.min(v.golpes, lugares);
  if (papel !== "respuesta" || d.forma !== "entrelazado" || d.modo === "en_vivo") return `${pedido} de ${lugares}`;
  const l = cfg.llamada.golpes;
  const ocup = new Set([...Array(lugares).keys()].filter((i) => (i * Math.min(l, lugares)) % lugares < Math.min(l, lugares)));
  const libres = [...Array(lugares).keys()].filter((i) => !ocup.has(i) &&
    ![...ocup].some((j) => { const dd = ((i - j) % lugares + lugares) % lugares; return dd >= 1 && dd <= d.espacio; })).length;
  return libres >= pedido ? `${pedido} de ${lugares}` : `${pedido} pedidos · caben ${libres}`;
}

// --- Molde: filtro de notas. La seed arma las notas y el filtro decide cuáles pasan ---

const CERRADO = "----------------";
const MOLDES = [["xxxxxxxxxxxxxxxx", "Abrir todo"], ["x---x---x---x---", "Tiempos"], ["--x---x---x---x-", "Contras"],
  ["-xxx-xxx-xxx-xxx", "Sin bombo"], ["xxxxxxxx--------", "Inicio"], ["--------xxxxxxxx", "Final"], [CERRADO, "Cerrar todo"]];

const RECORRIDOS = [["adelante","Adelante"],["atras","Atrás"],["pendulo","Péndulo"],["azar","Al azar"]];
const PINCELES = [["x","● Pasa"],["?","? A veces"]];

function moldeLimpio(m) {
  // Como en el motor (goa/secuencia.py): 16 pasos, x pasa, ? a veces, - bloquea; vacío = cerrado.
  return [...(m || "")].map((c) => "x?-".includes(c) ? c : "x").join("").slice(0, 16).padEnd(16, "-");
}

function moldeTexto(m, obj) {
  const partes = [];
  if (obj && obj.filtro) {
    m = moldeLimpio(m);
    const igual = MOLDES.find(([valor]) => valor === m);
    if (igual) partes.push(igual[1].toLowerCase());
    else {
      const n = (m.match(/x/g) || []).length, q = (m.match(/\?/g) || []).length;
      partes.push(n || q ? [n ? `${n} pasan` : "", q ? `${q} a veces` : ""].filter(Boolean).join(", ") : "cerrado");
    }
    if (obj.molde_muta > 0) partes.push("muta");
  } else partes.push("sin filtro");
  if (obj && obj.recorrido && obj.recorrido !== "adelante") partes.push(RECORRIDOS.find((r) => r[0] === obj.recorrido)[1].toLowerCase());
  return partes.join(" · ");
}

function moldeEditor(obj, ayudaTexto, resumen, textoOrden, cada, alMutar) {
  // Filtro de notas: prendido y vacío no suena nada; tocas los pasos que quieres oír.
  // Tocar un paso abierto lo vuelve a cerrar. Los tiempos del bombo siempre se marcan.
  let pincel = "x";
  const caja = el("div", {style: "display:flex;flex-direction:column;gap:8px"});
  const actualizar = () => { if (resumen) resumen.textContent = moldeTexto(obj.molde, obj); };
  const pintar = () => {
    caja.innerHTML = "";
    const sw = el("input", {type: "checkbox", className: "switch", checked: !!obj.filtro, "aria-label": "Filtro de notas",
      onchange: () => {
        obj.filtro = sw.checked;
        if (obj.filtro && !/[x?]/.test(obj.molde || "")) obj.molde = CERRADO;  // parte cerrado: vas abriendo pasos
        pintar(); guardar(); actualizar();
      }});
    caja.appendChild(el("label", {className: "fila", style: "min-height:44px"}, [
      el("span", {}, ["Filtro de notas", el("br"), el("span", {className: "mut",
        textContent: obj.filtro ? "Solo pasan las notas de los pasos abiertos" : "Apagado: suena todo lo que arma la seed"})]), sw]));
    if (obj.filtro) {
      const m = moldeLimpio(obj.molde);
      caja.appendChild(segmentado(PINCELES, pincel, (v) => { pincel = v; pintar(); }, 2));
      const fila = el("div", {className: "molde"});
      [...m].forEach((c, i) => {
        const estado = {x: "pasa", "?": "a veces", "-": "bloqueado"}[c];
        const b = el("button", {type: "button",
          className: (i % 4 === 0 ? "bombo " : "") + ({x: "x", "?": "talvez"}[c] || ""),
          "aria-label": `Paso ${i + 1}${i % 4 === 0 ? " (bombo)" : ""}: ${estado}`,
          textContent: c === "x" ? "●" : c === "?" ? "?" : (i % 4 === 0 ? String(i / 4 + 1) : ""),
          onclick: () => {
            obj.molde = m.slice(0, i) + (c === pincel ? "-" : pincel) + m.slice(i + 1);
            pintar(); guardar(); actualizar();
          }});
        fila.appendChild(b);
      });
      caja.appendChild(fila);
      caja.appendChild(el("div", {className: "molde-ley"}, [el("span", {className: "kick"}), "bombo"]));
      caja.appendChild(el("div", {className: "molde-presets"}, MOLDES.map(([valor, nombre]) =>
        el("button", {type: "button", textContent: nombre, onclick: () => { obj.molde = valor; pintar(); guardar(); actualizar(); }}))));
      caja.appendChild(el("div", {className: "molde-presets"}, [["goa", "🎲 Goa"], ["psy", "🎲 Psy"]].map(([estilo, nombre]) =>
        el("button", {type: "button", textContent: nombre, onclick: async () => {
          // Lo arma el motor (goa/generador.py): los pesos viven en un solo lugar.
          try { obj.molde = (await (await fetch(`/api/molde/azar?estilo=${estilo}`)).json()).molde; }
          catch (e) { aviso("Sin conexión con la Pi", true); return; }
          obj.molde_estilo = estilo; pintar(); guardar(); actualizar(); }}))));
      caja.appendChild(ayuda(ayudaTexto));
      if (m.includes("?")) {
        caja.appendChild(deslizador(obj, "molde_prob", "Probabilidad de los ?", 0, 1, 0.05, porcentaje));
        caja.appendChild(ayuda("En cada compás, cada ? deja pasar la nota con esta probabilidad."));
      }
      caja.appendChild(deslizador(obj, "molde_muta", "El filtro muta solo", 0, 1, 0.05,
        (v) => v === 0 ? "no" : `${porcentaje(v)} cada ${cada()} compases`, () => { actualizar(); if (alMutar) alMutar(); }));
      caja.appendChild(ayuda(`Cada cierto número de compases abre o cierra uno o dos pasos, al estilo ${(obj.molde_estilo || "goa") === "psy" ? "psy" : "goa"} (el del último 🎲). La fila de arriba muestra el filtro de partida.`));
    }
    caja.appendChild(campo(textoOrden, segmentado(RECORRIDOS, obj.recorrido || "adelante", (v) => { obj.recorrido = v; pintar(); guardar(); actualizar(); }, 4)));
  };
  pintar();
  return caja;
}

// --- LFO de filtro de las secuencias (dos por secuencia) ---
// Qué puede mover un LFO, por sinte (de sus tablas MIDI). «Otro CC» deja poner cualquier número.
const LFO_SINTES = [
  ["MC-101 / FM-1", [["74","Corte"],["71","Resonancia"],["73","Ataque"],["72","Release"],["20","Wavetable A (FM-1)"],["21","Wavetable B (FM-1)"]]],
  ["MicroFreak", [["23","Corte"],["83","Resonancia"],["10","Wave"],["12","Timbre"],["13","Shape"]]],
];
const LFO_DESTINOS = LFO_SINTES.flatMap(([, l]) => l);
const LFO_NOMBRE_CC = {74: "corte", 71: "resonancia", 73: "ataque", 72: "release", 20: "wavetable A", 21: "wavetable B",
  23: "corte (MicroFreak)", 83: "resonancia (MicroFreak)", 10: "wave (MicroFreak)", 12: "timbre (MicroFreak)", 13: "shape (MicroFreak)"};

function lfoResumen(s) {
  const activos = [["lfo", s.lfo], ["lfo2", s.lfo2]].filter(([, a]) => a).map(([p]) => {
    const cc = s[`${p}_cc`];
    return `${LFO_NOMBRE_CC[cc] || "CC " + cc} ${(LFO_FORMAS.find((x) => x[0] === (s[`${p}_forma`] || "seno")) || LFO_FORMAS[0])[1].toLowerCase()}`;
  });
  return activos.length ? activos.join(" + ") : "apagado";
}

function editorLfo(s, p, titulo) {
  const k = (x) => `${p}${x}`;
  const cc = s[k("_cc")];
  const otro = p === "lfo" ? "lfo2" : "lfo";
  const choca = s[p] && s[otro] && s[`${otro}_cc`] === cc;
  return [
    el("label", {className: "fila", style: "min-height:44px"}, [
      el("span", {}, [titulo, el("br"), el("span", {className: "mut", textContent: s[p] ? `Mueve ${LFO_NOMBRE_CC[cc] || "el CC " + cc}` : "Apagado"})]),
      el("input", {type: "checkbox", className: "switch", checked: !!s[p], "aria-label": titulo,
        onchange: (e) => { s[p] = e.target.checked; guardar(); renderMotores(); }})]),
    ...(s[p] ? [
      ...LFO_SINTES.map(([sinte, lista]) => campo(`Qué mueve · ${sinte}`, segmentado(lista, String(cc), (v) => { s[k("_cc")] = parseInt(v); guardar(); renderMotores(); }, sinte === "MicroFreak" ? 3 : 2))),
      numeroDe(s, k("_cc"), "Otro CC (número)", 0, 127, renderMotores),
      [20, 21].includes(cc) ? ayuda("Posición de wavetable de la FM-1 con Shrub: el timbre va cambiando. La MC-101 no tiene este control.") : null,
      choca ? ayuda("Los dos LFO mueven lo mismo y se van a pisar: elige otra cosa para uno de ellos.") : null,
      campo("Forma", segmentado(LFO_FORMAS, s[k("_forma")] || "seno", (v) => { s[k("_forma")] = v; guardar(); renderMotores(); }, 3)),
      campo("Una vuelta dura", segmentado(LFO_CICLOS, String(s[k("_compases")]), (v) => { s[k("_compases")] = parseFloat(v); guardar(); renderMotores(); }, 4)),
      numeroDecimal(s, k("_compases"), "Otra duración (compases, de 0,25 a 32)", 0.25, 32, 0.25, renderMotores),
      deslizador(s, k("_min"), "Abajo", 0, 127, 1, (x) => String(x)),
      deslizador(s, k("_max"), "Arriba", 0, 127, 1, (x) => String(x)),
    ] : []),
  ];
}

function moldePlegable(obj, texto, textoOrden, cada) {
  const resumen = el("span", {className: "der", textContent: moldeTexto(obj.molde, obj)});
  return el("details", {className: "voz"}, [
    el("summary", {}, [el("span", {textContent: "Filtro y orden (opcional)"}), resumen]),
    el("div", {className: "cuerpo"}, [moldeEditor(obj, texto, resumen, textoOrden, cada)]),
  ]);
}

function filaFrase(v, titulo, alCambiar) {
  // Otra · Volver · Fijar: elegir la frase de una voz sin tocar la seed.
  const cambiar = (f) => { f(); alCambiar(); guardar(); };
  return el("div", {style: "display:flex;flex-direction:column;gap:4px"}, [
    el("span", {className: "mut", textContent: `${titulo} · frase ${(v.variante || 0) + 1}${v.fija ? " · fijada" : ""}`}),
    el("div", {className: "molde-presets"}, [
      el("button", {type: "button", textContent: "Otra frase", onclick: () => cambiar(() => { v.variante = (v.variante || 0) + 1; v.fija = false; })}),
      el("button", {type: "button", textContent: "Volver", disabled: !v.variante, onclick: () => cambiar(() => { v.variante = Math.max(0, (v.variante || 0) - 1); })}),
      el("button", {type: "button", textContent: v.fija ? "Fijada ✓" : "Fijar", className: v.fija ? "activo" : "", onclick: () => cambiar(() => { v.fija = !v.fija; })}),
    ]),
  ]);
}

function frasesDialogo(alCambiar) {
  const vivo = cfg.dialogo.modo === "en_vivo";
  return el("div", {style: "display:flex;flex-direction:column;gap:10px"}, [
    vivo ? null : filaFrase(cfg.llamada, "Llamada", alCambiar),
    filaFrase(cfg.respuesta, "Respuesta", alCambiar),
  ].filter(Boolean));
}

function bloqueFrases() {
  // En Tocar, solo si el diálogo suena: cambiar o fijar frases sin ir a Motores.
  if (!cfg.dialogo.activo) return null;
  return el("div", {className: "card", style: "display:flex;flex-direction:column;gap:10px"}, [
    h3("Frases del diálogo"),
    frasesDialogo(() => renderTocar()),
    ayuda("«Otra frase» cambia las notas y el ritmo de esa voz en el próximo compás; «Volver» trae la anterior; «Fijar» la congela."),
  ]);
}

function bloqueVoz(v, titulo, papel, extra = []) {
  const d = cfg.dialogo;
  const estado = el("span", {className: "pill", "data-salida": v.salida});
  const lugares = d.rejilla === "corcheas" ? 8 : 16;
  const golpes = deslizador(v, "golpes", "Golpes", 1, lugares, 1, () => golpesTexto(d, v, papel));
  golpes.querySelector("input").addEventListener("change", () => renderMotores());
  return recordar(el("details", {className: "voz"}, [
    el("summary", {}, [el("span", {textContent: `${titulo} · ${v.salida} canal ${v.canal}`}), el("span", {className: "der"}, [estado])]),
    el("div", {className: "cuerpo"}, [
      golpes,
      deslizador(v, "oscuridad", "Luminoso ↔ Oscuro", 0, 1, 0.05, colorTexto),
      moldePlegable(v, `La seed arma la frase y el filtro decide dónde cae: ● = pasa, ? = a veces, vacío = bloqueado. Una nota que cae en un paso bloqueado se corre al abierto más cercano. ${d.rejilla === "corcheas" ? "En corcheas cada lugar ocupa 2 pasos." : ""}`, "Orden de sus notas", () => cfg.dialogo.mutar_cada),
      ...extra.filter(Boolean),
      el("div", {className: "dos"}, [destinoDe(v, renderMotores), numeroDe(v, "canal", "Canal MIDI", 1, 16, renderMotores)]),
      numeroDe(v, "programa", "Parche (Program Change, 0 = no cambia)", 0, 128),
      deslizador(v, "octava", "Octava", -3, 3, 1, octavaTexto),
      numeroDe(v, "velocidad", "Fuerza (1-127)", 1, 127),
      deslizador(v, "gate", "Largo de las notas", 0.05, 1, 0.05, porcentaje),
      ayuda("Nunca pisa a la nota siguiente, de ninguna de las dos voces."),
      deslizador(v, "vel_random", "Variación de fuerza", 0, 1, 0.05, porcentaje),
      desplazamientoPropio(v),
    ]),
  ]), `voz-${papel}`, false);
}

function desplazamientoPropio(v) {
  // Cada voz usa el Pegado ↔ Desplazado general (en Armonía) o uno propio.
  const caja = el("div", {style: "display:flex;flex-direction:column;gap:12px"});
  const pintar = () => {
    caja.innerHTML = "";
    const propio = v.desplazamiento >= 0;
    const chk = el("input", {type: "checkbox", checked: propio, onchange: () => {
      v.desplazamiento = chk.checked ? cfg.musica.desplazamiento : -1; pintar(); guardar(); }});
    caja.append(el("label", {className: "fila", style: "min-height:44px"}, [el("span", {}, ["Pegado ↔ Desplazado propio", el("br"),
      el("span", {className: "mut", textContent: propio ? "Esta voz tiene su propio ajuste" : `Usa el general (${desplTexto(cfg.musica.desplazamiento)})`})]), chk]));
    if (propio) caja.append(deslizador(v, "desplazamiento", "Pegado ↔ Desplazado de esta voz", 0, 1, 0.05, desplTexto));
  };
  pintar();
  return caja;
}

function colorGeneral() {
  // Mueve la oscuridad de las dos voces juntas; cada voz tiene además su propio control.
  const vivo = cfg.dialogo.modo === "en_vivo";
  const voces = vivo ? [cfg.respuesta] : [cfg.llamada, cfg.respuesta];
  const general = {v: voces.reduce((a, x) => a + x.oscuridad, 0) / voces.length};
  const control = deslizador(general, "v", vivo ? "Luminoso ↔ Oscuro" : "Luminoso ↔ Oscuro (las dos voces)", 0, 1, 0.05, colorTexto);
  const r = control.querySelector("input");
  r.addEventListener("input", () => { for (const x of voces) x.oscuridad = general.v; });
  r.addEventListener("change", () => renderMotores());
  return control;
}

function panelDialogo() {
  const d = cfg.dialogo;
  const vivo = d.modo === "en_vivo";
  const fase = el("span", {className: "pill", id: "dialogo_fase", textContent: "En silencio"});
  const mismo = el("button", {type: "button", textContent: vivo ? "Responder en el sinte donde toco" : "Responder en el mismo sinte que llama",
    onclick: () => {
      if (vivo) { cfg.respuesta.canal = d.escucha; }
      else { cfg.respuesta.salida = cfg.llamada.salida; cfg.respuesta.canal = cfg.llamada.canal; }
      renderMotores(); guardar(); aviso("La respuesta va al mismo sinte");
    }});
  const rehacer = () => { renderMotores(); guardar(); };
  const espacio = d.forma === "entrelazado" || vivo ? deslizador(d, "espacio", "Espacio", 0, 3, 1,
    (x) => x === 0 ? "pueden ir pegadas" : `la respuesta espera ${x} ${d.rejilla === "corcheas" ? "corchea" : "semicorchea"}${x > 1 ? "s" : ""}`) : null;
  if (espacio) espacio.querySelector("input").addEventListener("change", () => renderMotores());
  const sub = vivo ? "Llamas tú · responde en tus huecos" : `${d.forma === "entrelazado" ? "Entrelazado" : "Por turnos"} · ${d.rejilla} · ${armoniaTexto(d)}`;
  return [
    cabMotor("Llamada y respuesta", sub, d, "activo", fase, botonFabricaMotor("dialogo")),
    campo("Quién llama", segmentado([["motor","El motor"],["en_vivo","Yo, en vivo"]], d.modo, (x) => { d.modo = x; rehacer(); }, 2)),
    vivo ? ayuda("El motor escucha dónde tocas en cada compás y en el siguiente responde en tus huecos.")
      : campo("Cómo conversan", segmentado([["entrelazado","Entrelazado"],["turnos","Por turnos"]], d.forma, (x) => { d.forma = x; rehacer(); }, 2)),
    vivo ? null : ayuda(FORMAS_TEXTO[d.forma]),
    bloqueVariante(d, "dialogo", "dialogo"),
    el("div", {className: "card principales"}, [
      colorGeneral(),
      deslizador(d, "densidad", "Densidad", 0, 1, 0.05, (x) => x >= 1 ? "todas las notas" : `${porcentaje(x)} de las notas (la primera de cada voz siempre)`),
      deslizador(d, "evolucion", "Mutación", 0, 1, 0.05, (x) => x === 0 ? "fija" : `${porcentaje(x)} cada ${d.mutar_cada} compases`),
      espacio,
      frasesDialogo(() => renderMotores()),
    ]),
    el("div", {className: "grupos"}, [
      grupo("g-dlg-ritmo", "Ritmo", `${d.rejilla}${d.forma === "turnos" && !vivo ? ` · turnos de ${d.compases_turno}` : ""} · espacio ${d.espacio}`, [
        campo("Rejilla", segmentado([["corcheas","Corcheas"],["semicorcheas","Semicorcheas"]], d.rejilla, (x) => {
          d.rejilla = x; const n = x === "corcheas" ? 8 : 16;
          for (const v of [cfg.llamada, cfg.respuesta]) v.golpes = Math.min(v.golpes, n);
          rehacer(); }, 2)),
        ayuda(d.rejilla === "corcheas" ? "Todo cae en el tiempo o en su contratiempo: siempre con el bombo." : "Más rápido y sincopado."),
        d.forma === "turnos" && !vivo ? campo("Compases por turno", segmentado([["1","1"],["2","2"],["4","4"]], String(d.compases_turno), (x) => { d.compases_turno = parseInt(x); guardar(); }, 3)) : null,
      ]),
      grupo("g-dlg-voces", "Voces", vivo ? `respuesta: ${cfg.respuesta.salida}` : `llamada: ${cfg.llamada.salida} · respuesta: ${cfg.respuesta.salida}`, [
        campo("La respuesta contesta", segmentado([["contraste","Con lo suyo"],["eco","Eco"],["espejo","Espejo"],["cierra","Cerrando"]], d.responde || "contraste", (x) => { d.responde = x; renderMotores(); guardar(); }, 4)),
        ayuda({contraste: "Con sus propias notas, como siempre.", eco: "Repite las notas de la llamada.", espejo: "Las notas de la llamada dadas vuelta: si la llamada sube, la respuesta baja.", cierra: "Con sus notas, pero termina en la raíz: la llamada pregunta y la respuesta cierra."}[d.responde || "contraste"]),
        vivo ? null : bloqueVoz(cfg.llamada, "Llamada", "llamada"),
        bloqueVoz(cfg.respuesta, "Respuesta", "respuesta", [mismo]),
      ]),
      grupo("g-dlg-var", "Variación", `mutar cada ${d.mutar_cada} · ${armoniaTexto(d)}`, [
        numeroDe(d, "mutar_cada", "Cada (compases, de 1 a 64)", 1, 64, () => renderMotores()),
        armoniaPropia(d, () => renderMotores()),
        guiadaDe(d) ? ayuda("Guiada: se mueve con cada acorde de los pads y cada voz cierra su motivo en el acorde (ultra oscuro queda colgado a propósito).") : null,
        guiadaDe(d) ? null : casilla(d, "seguir_pads", "Sigue a los pads", cfg.pads.activo ? "Usa su escala y se mueve con cada acorde" : "Los pads están apagados", () => renderMotores()),
      ]),
      grupo("g-dlg-midi", "Salida MIDI", vivo ? `escucha canal ${d.escucha}` : `nota larga ${d.disparo ? "canal " + d.disparo : "general"}`, [
        vivo ? numeroDe(d, "escucha", "Canal donde toco la llamada", 1, 16) : numeroDe(d, "disparo", "Canal de su nota larga en la Circuit (0 = el general)", 0, 16),
        ayuda("Los destinos de cada voz están en Voces."),
      ]),
    ]),
  ];
}

// --- FX ---

const GESTOS_FX = [["zap", "Zaps", "2 tiempos · láser que cae en picada y su eco"], ["burbujas", "Burbujas", "1 tiempo · fusas que caminan por la escala"],
  ["acido", "Ácido", "2 tiempos · un pedazo de 303 con el filtro chillando"], ["glitch", "Glitch", "2 tiempos · redobles que saltan de octava y quinta"],
  ["barrido", "Barrido", "1 compás · nota larga con el filtro abriéndose (o cerrándose)"], ["gate", "Gate", "2 tiempos · el filtro corta la nota en ritmo euclidiano"],
  ["eco", "Eco", "1 compás · ecos en corchea con puntillo, cada vez más oscuros"], ["escalera", "Escalera", "1 tiempo · fusas que suben por el acorde, el filtro abriéndose"]];
const GESTO_TEXTO = {zap: "zap", burbujas: "burbujas", acido: "ácido", glitch: "glitch", barrido: "barrido", gate: "gate", eco: "eco", escalera: "escalera", riser: "riser", caida: "caída"};
const FILTRO_MODOS = [["pluck", "Pluck", "golpes"], ["pasos", "Pasos", "16 valores"], ["sh", "S&H", "al azar"], ["wobble", "Wobble", "va y viene"], ["rampa", "Rampa", "sube y cae"], ["quieto", "Quieto", "no lo toca"]];
const DIVISIONES_FX = [["32", "1/32"], ["16", "1/16"], ["8t", "1/8 T"], ["8", "1/8"], ["4", "1/4"], ["2", "1/2"], ["1c", "1 comp."], ["2c", "2 comp."]];
function euclidesTexto(golpes, rotar) {
  let s = "";
  for (let i = 0; i < 16; i++) { s += ((i + rotar) * golpes) % 16 < golpes ? "●" : "·"; if (i % 4 === 3 && i < 15) s += " "; }
  return s;
}

function panelFx() {
  const x = cfg.fx;
  const gestos = GESTOS_FX.filter(([k]) => x[k]).map(([, n]) => n.toLowerCase());
  return [
    cabMotor("FX", `${x.salida} · canal ${x.canal} · ${gestos.join(", ") || "sin gestos"}`, x, "activo",
      el("span", {className: "pill", id: "fx_gesto", textContent: "En silencio"}), botonFabricaMotor("fx")),
    campo("Carácter de los gestos · qué gestos aparecen y cuántos", segmentado(GENEROS, x.genero, (v) => cambiarGenero(v, {parte: "fx"}), 3)),
    ayuda({goa: "Goa: zaps, ácido y glitches, todos a la mano.", psytrance: "Psytrance: zaps y glitches, algo de ácido.", psy_chill: "Psy chill: sobre todo burbujas, pocos zaps.",
      chillgressive: "Chillgressive: de todo, un poco menos seguido.", chillout: "Chillout: burbujas y algún zap, espaciados.",
      ambient: "Ambient: solo burbujas, muy de vez en cuando."}[x.genero]),
    bloqueVariante(x, "fx", null),
    el("div", {className: "card principales"}, [
      deslizador(x, "locura", "Locura", 0, 1, 0.05, (v) => v === 0 ? "solo subidas y fondo" : v < 0.3 ? `poca (${porcentaje(v)})` : v < 0.7 ? `media (${porcentaje(v)})` : `mucha (${porcentaje(v)})`),
      ayuda("Cuántos lugares tienen gesto. La energía la sube y la baja. También decide cuánto se traban las secuencias con FX."),
      deslizador(x, "caos", "Caos", 0, 1, 0.05, (v) => v === 0 ? "se repite igual" : v < 0.4 ? `poco (${porcentaje(v)})` : `mucho (${porcentaje(v)})`),
      ayuda("Cuánto cambia en cada vuelta: algunos gestos cambian y el filtro del fondo hace locuras (el doble de rápido, saltos, se congela)."),
    ]),
    el("div", {className: "grupos"}, [
      grupo("g-fx-gestos", "Gestos", `${gestos.join(", ") || "ninguno"} · ${{frase: "al final de la frase", compas: "al final del compás", tiempo: "en cualquier tiempo"}[x.donde]} · se repiten cada ${x.repetir}`, [
        campo("Dónde caen", segmentado([["frase", "Fin de frase", "cada 4 compases"], ["compas", "Fin de compás", "cada compás"], ["tiempo", "Cualquier tiempo", "más suelto"]], x.donde, (v) => { x.donde = v; guardar(); renderMotores(); }, 3)),
        campo("Se repiten cada", segmentado([["2","2 comp."],["4","4 comp."],["8","8 comp."],["16","16 comp."]], String(x.repetir), (v) => { x.repetir = parseInt(v); guardar(); renderMotores(); }, 4)),
        ayuda("Cada gesto empieza en un tiempo, dura tiempos enteros y termina justo en el uno siguiente. El mismo gesto vuelve en el mismo lugar cada vuelta (con caos, algunos cambian)."),
        ...GESTOS_FX.map(([k, n, d]) => casilla(x, k, n, d, () => renderMotores())),
        ayuda("Las notas salen del acorde que suena (o de la escala). Solo el zap usa pitch bend; los demás saltan entre notas, así que nunca desafinan."),
      ]),
      grupo("g-fx-fondo", "Fondo: notas largas", x.fondo ? `${{raiz: "la raíz", acorde: "notas del acorde", quinta: "raíz y quinta", octavas: "octavas"}[x.fondo_notas]} · cada ${x.fondo_largo} compás${x.fondo_largo > 1 ? "es" : ""}` : "apagado", [
        el("label", {className: "fila", style: "min-height:44px"}, [
          el("span", {}, ["Notas largas de fondo", el("br"), el("span", {className: "mut", textContent: "Suenan siempre, y el filtro les da el ritmo"})]),
          el("input", {type: "checkbox", className: "switch", checked: !!x.fondo, "aria-label": "Notas largas de fondo",
            onchange: (e) => { x.fondo = e.target.checked; guardar(); renderMotores(); }})]),
        ...(x.fondo ? [
          campo("Qué notas", segmentado([["raiz", "Raíz"], ["acorde", "Del acorde", "va cambiando"], ["quinta", "Raíz + quinta"], ["octavas", "Octavas", "alterna"]], x.fondo_notas, (v) => { x.fondo_notas = v; guardar(); renderMotores(); }, 2)),
          campo("Se vuelven a atacar cada", segmentado([["1","1 comp."],["2","2 comp."],["4","4 comp."],["8","8 comp."]], String(x.fondo_largo), (v) => { x.fondo_largo = parseInt(v); guardar(); renderMotores(); }, 4)),
          deslizador(x, "fondo_octava", "Octava", -2, 2, 1, octavaTexto),
          numeroDe(x, "fondo_fuerza", "Fuerza (1-127)", 1, 127),
          ayuda("Si cambia el acorde, la nota cambia en el tiempo siguiente. En la MC-101 usa un sonido polifónico con sustain (pad, drone, bajo largo): los gestos suenan encima."),
        ] : []),
      ]),
      x.fondo ? grupo("g-fx-filtro", "Filtro en ritmo", `${FILTRO_MODOS.find((m) => m[0] === x.filtro_modo)[1]}${x.filtro_modo === "pluck" ? ` ${x.filtro_golpes}/16` : x.filtro_modo === "quieto" ? "" : " " + DIVISIONES_FX.find((d) => d[0] === x.filtro_division)[1]} · ${x.filtro_min}–${x.filtro_max}${x.resonancia ? " · resonancia" : ""}`, [
        campo("Cómo se mueve", segmentado(FILTRO_MODOS, x.filtro_modo, (v) => { x.filtro_modo = v; guardar(); renderMotores(); }, 3)),
        ...(x.filtro_modo === "pluck" ? [
          deslizador(x, "filtro_golpes", "Golpes en el compás", 1, 16, 1, (v) => `${v} de 16`, () => renderMotores()),
          deslizador(x, "filtro_rotar", "Correr el ritmo", 0, 15, 1, (v) => v === 0 ? "sin correr" : `${v} semicorchea${v > 1 ? "s" : ""}`, () => renderMotores()),
          el("div", {className: "mut", style: "font-family:monospace;font-size:16px;letter-spacing:1px", textContent: euclidesTexto(x.filtro_golpes, x.filtro_rotar)}),
          deslizador(x, "filtro_caida", "Cierre", 1, 48, 1, (v) => v <= 4 ? "seco" : v <= 12 ? `${v} pulsos` : `largo (${v} pulsos)`),
          ayuda("En cada golpe el filtro se abre de una y se va cerrando: ritmo euclidiano (los golpes repartidos lo más parejo posible)."),
        ] : x.filtro_modo === "quieto" ? [] : [
          campo("División", segmentado(DIVISIONES_FX, x.filtro_division, (v) => { x.filtro_division = v; guardar(); renderMotores(); }, 4)),
          ayuda({pasos: "Una fila de 16 valores que se repite (cambia la variante para otra; con caos va mutando).", sh: "Un valor al azar en cada división (sample & hold).",
            wobble: "Sube y baja suave en cada división.", rampa: "Sube en cada división y cae de golpe."}[x.filtro_modo]),
        ]),
        ...(x.filtro_modo === "quieto" ? [] : [
          el("div", {className: "dos"}, [numeroDe(x, "filtro_min", "Más cerrado", 0, 127), numeroDe(x, "filtro_max", "Más abierto", 0, 127)]),
          deslizador(x, "movimiento", "Movimiento", 0, 1, 0.05, (v) => v === 0 ? "quieto al medio" : porcentaje(v)),
        ]),
        casilla(x, "resonancia", "Mover la resonancia", "Va y viene en un ciclo propio, desfasado del compás", () => renderMotores()),
        ...(x.resonancia ? [
          deslizador(x, "reso_ciclo", "Ciclo de la resonancia", 1, 64, 1, (v) => `${v} semicorchea${v > 1 ? "s" : ""}${16 % v ? " (desfasada)" : ""}`),
          el("div", {className: "dos"}, [numeroDe(x, "reso_min", "Resonancia mín.", 0, 127), numeroDe(x, "reso_max", "Resonancia máx.", 0, 127)]),
          numeroDe(x, "cc_resonancia", "CC de la resonancia", 0, 127),
        ] : []),
        ayuda("Mientras un gesto mueve el filtro (ácido, barrido, gate, eco, escalera) o en el riser, el fondo lo suelta. En la MC-101, corte = CC 74 y resonancia = CC 71."),
      ]) : null,
      grupo("g-fx-subida", "Subida y drop", `${x.riser ? "riser" : "sin riser"} · ${x.caida ? "caída en el drop" : "sin caída"}`, [
        casilla(x, "riser", "Riser en las subidas", "Golpes que se van densificando (negras, corcheas, semicorcheas, fusas), el pitch subiendo hasta el drop y el filtro que baja y se va abriendo."),
        casilla(x, "caida", "Caída en el drop", "Una nota que se desploma con el pitch y el filtro en los dos compases después del drop."),
        ayuda("Las subidas se lanzan en Tocar (8, 16 o 32 compases), con «Riser» en una parte de la canción, y solas en el build y el break del piloto. Para que el riser suba una octava entera, pon el rango de pitch bend del sinte en 12."),
      ]),
      grupo("g-fx-notas", "Notas", `octava ${x.octava} · fuerza ${x.velocidad}`, [
        deslizador(x, "octava", "Octava", -2, 3, 1, octavaTexto),
        numeroDe(x, "velocidad", "Fuerza (1-127)", 1, 127),
      ]),
      grupo("g-fx-midi", "Salida MIDI", `${salidaTexto(x)} · filtro CC ${x.cc_corte}`, [
        el("div", {className: "dos"}, [destinoDe(x, renderMotores), numeroDe(x, "canal", "Canal MIDI", 1, 16, renderMotores)]),
        ayuda("Un canal libre de la MC-101 (una pista con un sonido para efectos)."),
        el("div", {className: "dos"}, [numeroDe(x, "cc_corte", "CC del filtro", 0, 127), numeroDe(x, "filtro_reposo", "Filtro en reposo (0-127)", 0, 127)]),
        ayuda("Los gestos con filtro, el fondo, el riser y la caída lo mueven por ese CC. Sin fondo, después lo dejan en el reposo."),
        numeroDe(x, "disparo", "Canal de su nota larga en la Circuit (0 = el general)", 0, 16, renderMotores),
        programaDe(x),
      ]),
    ].filter(Boolean)),
  ];
}

function panelTexturas() {
  const x = cfg.texturas;
  const cc = {74: "corte", 71: "resonancia"}[x.cc] || `CC ${x.cc}`;
  return [
    cabMotor("Texturas", `${x.salida} · canal ${x.canal} · respira el ${cc}`, x, "activo", null, botonFabricaMotor("texturas")),
    ayuda("Notas largas que respiran (el filtro sube despacio y vuelve en cada una) mezcladas con notas cortas, en un canal propio de la MC-101. Salen del acorde que suena. Usa un sonido polifónico con release, tipo pad o pluck largo."),
    bloqueVariante(x, "texturas", null),
    el("div", {className: "card principales"}, [
      deslizador(x, "densidad", "Cantidad", 0, 1, 0.05, (v) => v === 0 ? "nada" : v < 0.3 ? `poca (${porcentaje(v)})` : v < 0.7 ? `media (${porcentaje(v)})` : `mucha (${porcentaje(v)})`),
      deslizador(x, "largas", "Largas o cortas", 0, 1, 0.05, (v) => v === 0 ? "solo cortas" : v === 1 ? "solo largas" : v < 0.4 ? `más cortas (${porcentaje(v)} largas)` : v > 0.6 ? `más largas (${porcentaje(v)})` : `mitad y mitad`),
      ayuda("La energía sube y baja la cantidad. En las subidas aparecen más largas y respiran más hondo."),
    ]),
    el("div", {className: "grupos"}, [
      grupo("g-tx-largas", "Notas largas", `${x.largo} compás${x.largo > 1 ? "es" : ""} · respira el ${cc}`, [
        campo("Duran sobre todo", segmentado([["1","1 compás"],["2","2 compases"],["4","4 compases"]], String(x.largo), (v) => { x.largo = parseInt(v); guardar(); renderMotores(); }, 3)),
        campo("Qué respira", segmentado([["74","Corte (CC 74)"],["71","Resonancia (CC 71)"]], String(x.cc), (v) => { x.cc = parseInt(v); guardar(); renderMotores(); }, 2)),
        deslizador(x, "profundidad", "Cuánto se abre", 0, 1, 0.05, (v) => v === 0 ? "nada (sin modulación)" : `${porcentaje(v)}`),
        numeroDe(x, "reposo", "Reposo entre notas (0-127)", 0, 127),
        ayuda("En cada nota larga el CC sube despacio hasta la mitad de la nota y vuelve al reposo. Si el acorde cambia y la nota ya no le pertenece, termina sola."),
      ]),
      grupo("g-tx-notas", "Notas", `${x.registro || 2} octava${(x.registro || 2) > 1 ? "s" : ""} desde la ${x.octava} · fuerza ${x.velocidad}`, [
        campo("Se reparten en", segmentado([["1","1 octava"],["2","2 octavas"],["3","3 octavas"]], String(x.registro || 2), (v) => { x.registro = parseInt(v); guardar(); renderMotores(); }, 3)),
        deslizador(x, "octava", "Octava más baja", -2, 3, 1, octavaTexto),
        numeroDe(x, "velocidad", "Fuerza (1-127)", 1, 127),
        ayuda("Graves y agudas mezcladas al azar dentro de esas octavas (las largas prefieren abajo). Octava 0 parte en C3. Las cortas siguen una figura rítmica que cambia cada 4 compases, con un motivo de 2 compases que se repite, nunca en el tiempo del bombo."),
      ]),
      grupo("g-tx-midi", "Salida MIDI", salidaTexto(x), [
        el("div", {className: "dos"}, [destinoDe(x, renderMotores), numeroDe(x, "canal", "Canal MIDI", 1, 16, renderMotores)]),
        ayuda("Un canal de la MC-101 distinto al de los FX y al del bajo."),
        numeroDe(x, "disparo", "Canal de su nota larga en la Circuit (0 = el general)", 0, 16, renderMotores),
        programaDe(x),
      ]),
    ]),
  ];
}

// --- Tocado: lo que tocas en la MicroFreak, con estilo (goa/tocado.py) ---
const ESTADOS_TOCADO = {libre: "En vivo", armado: "Armado", grabando: "Grabando", loop: "Loop", pausa: "Pausa"};
function pasosTexto(n) {
  return n % 16 === 0 ? `${n} pasos (${n / 16} compás${n > 16 ? "es" : ""})` : n % 4 === 0 ? `${n} pasos (${n / 4} tiempos)` : `${n} pasos`;
}

function panelTocado() {
  const x = cfg.tocado;
  const accion = (a) => async () => { try { const d = await api("/api/tocado", {accion: a}); pintarTocado({tocado: d.tocado}); } catch (e) { aviso(e.message, true); } };
  const largoLoop = () => {
    // Acortar o alargar el loop ya grabado (no borra nada: volver al largo original lo deja igual).
    const valor = el("span", {id: "tocado_largo_txt", textContent: "sin loop", style: "color:var(--mut)"});
    const r = el("input", {type: "range", id: "tocado_largo", min: 1, max: 128, step: 1, value: 16, disabled: true, "aria-label": "Largo del loop",
      oninput: () => { valor.textContent = pasosTexto(parseInt(r.value)); },
      onchange: async () => { try { const d = await api("/api/tocado", {accion: "largo", pasos: parseInt(r.value)}); pintarTocado({tocado: d.tocado}); } catch (e) { aviso(e.message, true); } }});
    const original = el("button", {type: "button", id: "tocado_original", textContent: "Largo original", disabled: true,
      onclick: async () => { try { const d = await api("/api/tocado", {accion: "largo", pasos: parseInt(original.dataset.pasos)}); pintarTocado({tocado: d.tocado}); } catch (e) { aviso(e.message, true); } }});
    return el("div", {}, [
      el("label", {className: "campo"}, [el("span", {className: "fila", style: "gap:8px"}, [el("b", {textContent: "Largo del loop", style: "font-weight:600"}), valor]), r]),
      original,
      ayuda("Después de grabar: acórtalo (por ejemplo a 4 pasos) o alárgalo hasta 128 (repite lo grabado). No borra nada: «Largo original» lo deja como lo grabaste."),
    ]);
  };
  return [
    cabMotor("Tocado", `${x.salida} · canal ${x.canal} · ${x.modo === "contorno" ? "contorno" : "una tecla"} · ${nombreEstilo(x.estilo)}`, x, "activo",
      null, botonFabricaMotor("tocado")),
    ayuda("Tocas en el teclado de la MicroFreak: tú pones el ritmo (cortas, largas, fuertes, suaves) y el motor pone las notas, siempre en la escala y el acorde que suena. Nunca desafina."),
    cfg.teclado && cfg.teclado.activo ? null : el("p", {className: "ayuda", style: "color:var(--bad)", textContent: "Activa el teclado de la MicroFreak en Ajustes para tocar."}),
    campo("Cómo tocas", segmentado([["una_tecla", "Una tecla"], ["contorno", "Contorno"]], x.modo, (v) => { x.modo = v; guardar(); renderMotores(); }, 2)),
    ayuda(x.modo === "contorno" ? "La tecla cuenta: más agudo, la nota sube. Cae siempre en la escala, y en los tiempos fuertes en una nota del acorde."
      : "Da lo mismo qué tecla aprietes: cada nota que tocas toma la nota siguiente de una secuencia del estilo (la de la variante). Tú pones el ritmo; el estilo, la melodía."),
    ...(x.modo === "contorno" ? [] : [
      bloqueEstilo(x, {familias: FAMILIAS, nombre: nombreEstilo, clave: "tocado-estilo", detalle: figuraTexto(x),
        ayuda: "El mismo de las secuencias, con sus ajustes.", elegir: (v) => { x.estilo = v; guardar(); renderMotores(); },
        opciones: x.estilo === "clasico" ? panelClasico(x) : x.estilo === "psytrance" ? panelPsy(x) : []}),
    ]),
    el("div", {className: "card principales"}, [
      deslizador(x, "octava", "Octava", -2, 2, 1, octavaTexto, () => renderMotores()),
      x.modo === "contorno" ? null : bloqueVariante(x, "tocado", null, "Variante de notas"),
      x.modo === "contorno" ? null : ayuda("La variante cambia qué notas elige el estilo, sin tocar tu ritmo (también el del loop)."),
    ].filter(Boolean)),
    el("div", {className: "card principales"}, [
      deslizador(x, "pasos", "Largo de la grabación", 1, 128, 1, pasosTexto),
      campo("Cuantización", segmentado([["estricta", "Estricta"], ["suave", "Suave"], ["swing", "Swing"], ["libre", "Libre"]], x.cuantizar, (v) => { x.cuantizar = v; guardar(); renderMotores(); }, 4)),
      x.cuantizar === "libre" ? null : campo("Rejilla", segmentado([["16", "Semicorcheas"], ["8", "Corcheas"]], String(x.grilla), (v) => { x.grilla = parseInt(v); guardar(); }, 2)),
      ayuda({estricta: "Inicio y largo de cada nota a la rejilla, sin notas montadas: el loop queda justo. Descuenta un pelo de retraso (lo que tarda la tecla).",
        suave: "Cada nota se mueve a mitad de camino hacia la semicorchea: ordena sin perder tu toque.",
        swing: "A la semicorchea, con las del contratiempo un poco tarde: groove.",
        libre: "Tal cual lo tocaste."}[x.cuantizar]),
      el("div", {className: "fila", style: "gap:10px;align-items:center"}, [
        el("button", {type: "button", className: "prim", id: "tocado_grabar", textContent: "Grabar", style: "flex:1", onclick: accion("grabar")}),
        el("span", {className: "pill", id: "tocado_pill", textContent: "…", style: "white-space:nowrap"}),
      ]),
      el("div", {className: "dos"}, [
        el("button", {type: "button", id: "tocado_parar", textContent: "Parar loop", onclick: () => accion(document.getElementById("tocado_parar").dataset.seguir ? "seguir" : "parar")()}),
        el("button", {type: "button", id: "tocado_borrar", textContent: "Borrar", onclick: () => { if (confirm("¿Borrar lo grabado?")) accion("borrar")(); }}),
      ]),
      largoLoop(),
      ayuda("Grabar empieza en el próximo compás y dura los pasos elegidos (hasta 128 = 8 compases); después queda en loop con la cuantización elegida. Puedes seguir tocando encima. El loop guarda tu ritmo: las notas las vuelve a elegir en cada vuelta, con el estilo y la armonía de ese momento."),
    ].filter(Boolean)),
    el("div", {className: "grupos"}, [
      x.modo === "contorno" ? null : grupo("g-tc-notas", "Notas del estilo", `desde ${RELACIONES.find((r) => r[0] === x.relacion)[1].toLowerCase()}${x.raga ? " · raga " + x.raga : ""} · acentos ${porcentaje(x.acentos)}`, [
        ayuda("Los mismos ajustes de nota que una secuencia: cambian qué notas elige el estilo para lo que tocas (y para el loop, en la vuelta siguiente)."),
        campo("Parte desde", segmentado(RELACIONES, x.relacion, (v) => { x.relacion = v; guardar(); renderMotores(); }, 2)),
        ...campoLargo(x),
        deslizador(x, "pedal", "Vuelve a la nota larga", 0, 1, 0.05, porcentaje),
        deslizador(x, "saltos", "Saltos de octava", 0, 1, 0.05, porcentaje),
        deslizador(x, "semitono", "♭2 (medio tono sobre la raíz)", 0, 1, 0.05, (v) => v === 0 ? "como sale" : porcentaje(v)),
        campo("Raga", segmentado(RAGAS, x.raga || "", (v) => { x.raga = v; renderMotores(); guardar(); }, 3)),
        ayuda(RAGA_TEXTO[x.raga || ""]),
        campo("Escala de color", segmentado(ESCALAS_COLOR, x.escala_color || "", (v) => { x.escala_color = v; renderMotores(); guardar(); }, 2)),
        ayuda(COLOR_TEXTO[x.escala_color || ""]),
        deslizador(x, "acentos", "Acentos", 0, 1, 0.05, porcentaje),
        numeroDe(x, "acento", "Fuerza del acento", 1, 127),
        ayuda("Donde el estilo pone un acento, la nota sale al menos con esa fuerza aunque la toques suave."),
        campo("Orden de las notas", segmentado([["adelante","Adelante"],["atras","Atrás"],["pendulo","Péndulo"],["azar","Al azar"]], x.recorrido || "adelante", (v) => { x.recorrido = v; guardar(); }, 4)),
        ayuda("En qué orden recorre la melodía del estilo: tu primera nota toma la primera, la segunda la siguiente…"),
        campo("Voz doble", segmentado([["","No"],["tercera","3.ª"],["cuarta","4.ª"],["quinta","5.ª"],["sexta","6.ª"],["octava","8.ª"]], x.doble || "", (v) => { x.doble = v; guardar(); }, 6)),
        ayuda("Una segunda voz paralela por grados de la escala, un poco más suave. Necesita un sinte polifónico."),
        deslizador(x, "techo", "Techo (nota más alta)", 36, 127, 1, (v) => v >= 127 ? "sin techo" : `${nombreMidi(v)} · lo de arriba baja una octava`),
        deslizador(x, "vel_random", "Variación de fuerza", 0, 1, 0.05, porcentaje),
      ]),
      x.modo === "contorno" ? null : grupo("g-tc-var", "Variación", `${x.bloqueada ? "congelada" : x.mutacion === 0 ? "sin mutación" : `${porcentaje(x.mutacion)} cada ${x.mutar_cada}`} · ${armoniaTexto(x)}`, [
        deslizador(x, "mutacion", "Mutación de notas", 0, 1, 0.05, (v) => x.bloqueada ? "congelada" : v === 0 ? "fija" : `${porcentaje(v)} cada ${x.mutar_cada}`, () => renderMotores()),
        numeroDe(x, "mutar_cada", "Mutar cada (compases)", 1, 64, () => renderMotores()),
        casilla(x, "bloqueada", "Congelar", "La mutación no cambia las notas", () => renderMotores()),
        ayuda("Cambia de a poco las notas que el estilo elige. Tu ritmo no se toca."),
        armoniaPropia(x, () => renderMotores()),
        ayuda("Guiada: en los tiempos fuertes, nota del acorde que suena. Libre: solo la escala (nunca desafina, pero puede chocar con el acorde)."),
      ]),
      grupo("g-tc-loop", "Sonido del loop", [x.largo_nota === "estilo" ? `largo del estilo ${porcentaje(x.gate)}` : "tu largo", x.densidad < 1 ? `densidad ${porcentaje(x.densidad)}` : "", x.repeticion ? `redobles ${porcentaje(x.repeticion)}` : "", x.slide ? `slides ${porcentaje(x.slide)}` : ""].filter(Boolean).join(" · "), [
        ayuda("Cómo suena lo grabado, sin mover tu ritmo: cada nota sigue en su lugar."),
        campo("Largo de cada nota", segmentado([["tuyo","Como lo tocaste"],["estilo","El del estilo"]], x.largo_nota || "tuyo", (v) => { x.largo_nota = v; guardar(); renderMotores(); }, 2)),
        ...(x.largo_nota === "estilo" ? [
          deslizador(x, "gate", "Largo de las notas", 0.05, 1, 0.05, porcentaje),
          deslizador(x, "gate_random", "Variación del largo", 0, 1, 0.05, porcentaje),
        ] : []),
        deslizador(x, "densidad", "Densidad", 0, 1, 0.05, (v) => v === 1 ? "todas tus notas" : `${porcentaje(v)} de tus notas`),
        deslizador(x, "repeticion", "Redobles", 0, 1, 0.05, porcentaje),
        deslizador(x, "slide", "Slides", 0, 1, 0.05, (v) => v === 0 ? "nunca" : `${porcentaje(v)} de las notas`),
        ayuda("Densidad calla algunas de tus notas (siempre las mismas). Redobles: un segundo golpe en media semicorchea. Slide: la nota se pisa con la siguiente; pon el sinte en mono o legato con glide."),
      ]),
      grupo("g-tc-filtro", "Filtro del sinte", [x.subida_filtro ? `se abre en las subidas hasta ${Math.round(x.subida_hasta / 1.27)} %` : "", x.fx ? "FX" : "", lfoResumen(x) === "apagado" ? "" : lfoResumen(x)].filter(Boolean).join(" · ") || "apagado", [
        el("label", {className: "fila", style: "min-height:44px"}, [
          el("span", {}, ["Se abre en las subidas", el("br"), el("span", {className: "mut", textContent: "Durante el rise el filtro se va abriendo hasta el drop"})]),
          el("input", {type: "checkbox", className: "switch", checked: !!x.subida_filtro, "aria-label": "Se abre en las subidas",
            onchange: (e) => { x.subida_filtro = e.target.checked; guardar(); renderMotores(); }})]),
        ...(x.subida_filtro ? [
          deslizador(x, "subida_desde", "Parte en", 0, 127, 1, (v) => `${v} (${Math.round(v / 1.27)} %)`),
          deslizador(x, "subida_hasta", "Al final de la subida", 0, 127, 1, (v) => v >= 127 ? "abierto del todo (127)" : `${v} (${Math.round(v / 1.27)} %)`),
          campo("Después del drop", segmentado([["vuelve","Vuelve al reposo"],["queda","Se queda ahí"]], x.subida_despues || "vuelve", (v) => { x.subida_despues = v; guardar(); renderMotores(); }, 2)),
        ] : []),
        casilla(x, "fx", "Lo interviene el motor de FX", "En las subidas su filtro baja y se va abriendo hasta el drop (sin redobles ni stutter: el ritmo es el tuyo).", () => renderMotores()),
        x.subida_filtro || x.fx ? el("div", {className: "dos"}, [numeroDe(x, "cc_filtro", "CC del filtro", 0, 127), numeroDe(x, "filtro_reposo", "Reposo (0-127)", 0, 127)]) : null,
        x.subida_filtro || x.fx ? ayuda("En la MicroFreak el corte es el CC 23; en la FM-1 con Shrub y la MC-101, el 74. El reposo es dónde vuelve después del drop: ponlo donde tienes la perilla.") : null,
        ...editorLfo(x, "lfo", "LFO 1"),
        ...editorLfo(x, "lfo2", "LFO 2"),
      ]),
      grupo("g-tc-midi", "Salida MIDI", salidaTexto(x), [
        el("div", {className: "dos"}, [destinoDe(x, renderMotores), numeroDe(x, "canal", "Canal MIDI", 1, 16, renderMotores)]),
        programaDe(x),
      ]),
    ].filter(Boolean)),
  ].filter(Boolean);
}
function pintarTocado(d) {
  const t = d.tocado; if (!t) return;
  const pill = $("tocado_pill");
  if (pill) {
    let texto = ESTADOS_TOCADO[t.estado] || t.estado;
    if (t.estado === "grabando" || t.estado === "loop") texto += ` · ${t.paso || 1}/${t.pasos}`;
    pill.textContent = texto;
    pill.className = "pill" + (t.estado === "grabando" ? " bad" : t.estado === "loop" ? " ok" : "");
  }
  const parar = $("tocado_parar");
  if (parar) {
    const seguir = t.estado === "pausa";
    parar.textContent = seguir ? "Seguir el loop" : "Parar loop";
    parar.disabled = !(t.notas || t.estado === "grabando" || t.estado === "armado");
    if (seguir) parar.dataset.seguir = "1"; else delete parar.dataset.seguir;
  }
  const borrar = $("tocado_borrar"); if (borrar) borrar.disabled = !t.notas;
  const largo = $("tocado_largo"), largoTxt = $("tocado_largo_txt"), original = $("tocado_original");
  const hay = !!t.notas && (t.estado === "loop" || t.estado === "pausa");
  if (largo && document.activeElement !== largo) {
    largo.disabled = !hay;
    if (hay) largo.value = t.pasos;
    largoTxt.textContent = hay ? pasosTexto(t.pasos) + (t.grabado !== t.pasos ? ` · grabado ${t.grabado}` : "") : "sin loop";
  }
  if (original) { original.disabled = !hay || t.grabado === t.pasos; original.dataset.pasos = t.grabado; }
  const grabar = $("tocado_grabar"); if (grabar) grabar.textContent = t.estado === "grabando" || t.estado === "armado" ? "Grabar de nuevo" : "Grabar";
}

function panelLooper() {
  const x = cfg.looper;
  const slots = [["0", "Callado"]];
  for (let i = 1; i <= 16; i++) slots.push([String(i), String(i)]);
  // Otro motor que manda al mismo sinte y canal: sus Program Change chocarían.
  const choca = motores().filter(([k, , o]) => k !== "looper" && o.salida === x.salida && Number(o.canal) === Number(x.canal)).map((m) => m[1]);
  if (cfg.dialogo && cfg.llamada && cfg.llamada.salida === x.salida && Number(cfg.llamada.canal) === Number(x.canal)) choca.push("Llamada");
  if (cfg.dialogo && cfg.respuesta && cfg.respuesta.salida === x.salida && Number(cfg.respuesta.canal) === Number(x.canal)) choca.push("Respuesta");
  return [
    cabMotor("Looper", `${x.salida} · canal ${x.canal} · ${x.clip ? "loop " + x.clip : "callado"}`, x, "activo", null, botonFabricaMotor("looper")),
    ayuda("Loops de samples de la pista Looper de la MC-101. Elige el loop que suena y guarda la escena: cada escena (y cada parte de la canción) lanza el suyo. El motor lo pide en la mitad del compás antes de donde debe entrar, y la MC-101 lo cambia justo en el uno."),
    choca.length ? el("p", {className: "ayuda", style: "color:var(--bad)", textContent: `Ojo: ${choca.join(", ")} también va a ${x.salida} canal ${x.canal}. Sus Program Change cambiarían el loop: usa otro canal para el looper o para ese motor.`}) : null,
    el("div", {className: "card principales"}, [
      campo("Loop que suena (slot de la MC-101)", segmentado(slots, String(x.clip), (v) => { x.clip = parseInt(v); guardar(); renderMotores(); }, 6)),
      ayuda(x.clip ? `Suena el slot ${x.clip}. Guarda la escena para que lo recuerde.` :
        x.parar ? `Callado: lanza el slot ${x.parar} (vacío) para callar la pista.` : "Callado: baja el volumen de la pista a 0 en el uno (y lo devuelve cuando vuelve a sonar)."),
      ayuda("Apagar el interruptor de arriba también lo calla, en el uno siguiente (o cuando entra la escena)."),
    ]),
    el("div", {className: "grupos"}, [
      grupo("g-lp-sync", "En sincronía", `entra cada ${x.cada} compás${x.cada > 1 ? "es" : ""}`, [
        campo("El loop entra cada", segmentado([["1","1 compás"],["2","2"],["4","4"],["8","8"]], String(x.cada), (v) => { x.cada = parseInt(v); guardar(); renderMotores(); }, 4)),
        ayuda("Pon el largo de tus loops: un loop de 4 compases elegido en cualquier momento espera el inicio de la frase (contado desde el Start de la Circuit) y entra siempre en el uno de la frase. Con una escena o parte, entra con ella; si la escena llega a mitad de frase, el loop espera el uno de la frase. Ojo: la MC-101 con MSTRSTEPLEN 16 cambia en cualquier compás, así que con loops de 64 pasos pon 4 acá."),
      ]),
      grupo("g-lp-midi", "Salida MIDI", `${salidaTexto(x)}${x.parar ? ` · calla con el slot ${x.parar}` : ""}`, [
        el("div", {className: "dos"}, [destinoDe(x, renderMotores), numeroDe(x, "canal", "Canal MIDI (el de la pista Looper)", 1, 16, renderMotores)]),
        numeroDe(x, "parar", "Slot vacío para callar (0 = calla con el volumen)", 0, 16, renderMotores),
        numeroDe(x, "nivel", "Volumen de la pista al volver a sonar", 1, 127),
        ayuda("Sin slot vacío, para callar el motor baja el volumen de la pista (CC 7) a 0 y al volver lo sube a este valor: ponlo donde tienes el nivel de la pista en la MC-101. Solo calla lo que el motor hizo sonar."),
        ayuda("En la MC-101: el canal de la pista Looper tiene que ser este (4 por defecto); el cambio de clip es Program Change 0-15 en el canal de la pista (tabla MIDI de Roland). El cambio de loop espera el Master Step Length ([TEMPO]): con 16 pasos cae justo en el uno en que entra la escena; más largo, entra después. Para callar no hace falta un slot vacío: basta apagarlo o elegir «Callado»."),
      ]),
    ]),
 ].filter(Boolean);
}

// --- Clips (dentro de cada secuencia y del diálogo) ---

function pintarClips() {
  if (!ultimoEstado) return;
  document.querySelectorAll("[data-sub-clip]").forEach((s) => {
    const n = nombreClipDe(s.dataset.subClip);
    const t = n ? `Clip: ${n}` : "Sin clip";
    if (s.textContent !== t) s.textContent = t;
  });
  document.querySelectorAll("[data-pestana-clip]").forEach((b) => {
    const n = nombreClipDe(b.dataset.pestanaClip);
    const t = (n ? `Clip: ${n}` : "Sin clip") + " ▾";
    if (b.textContent !== t) b.textContent = t;
  });
  document.querySelectorAll("[data-clips-de]").forEach((caja) => pintarFila(caja, estadoClipDe(caja.dataset.clipsDe)));
}

