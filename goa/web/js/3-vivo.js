// Yantra · Vivo, armonía, ajustes, controladores y escenas.
// Scripts clásicos en orden: comparten el ámbito global con los demás archivos de js/.
// --- Tocar ---

function renderMutes() {
  const cont = $("mutes"); cont.innerHTML = "";
  for (const [clave, nombre, obj, k] of motores()) {
    cont.append(el("button", {type: "button", className: "mute", "data-motor": clave, "aria-pressed": obj[k] ? "true" : "false",
      onclick: () => { obj[k] = !obj[k]; if (tocarVisible()) renderTocar(); else renderMutes(); if (vista === "motores" || (dosColumnas() && vista === "tocar")) renderMotores(); guardar(); }},
      [el("b", {textContent: nombre}), el("span", {textContent: obj[k] ? "suena" : "apagado"})]));
  }
  pintarMutes();
}

function pintarMutes() {
  const d = ultimoEstado;
  if (!d || !d.motores) return;
  document.querySelectorAll("#mutes .mute").forEach((b) => {
    const real = d.motores[b.dataset.motor];
    if (real === undefined) return;
    const pedido = b.getAttribute("aria-pressed") === "true";
    const cola = d.corriendo && real !== pedido;
    b.classList.toggle("cola", cola);
    b.querySelector("span").textContent = cola ? (pedido ? "entra" : "sale") : pedido ? "suena" : "apagado";
  });
}

// --- Armonía ---

function escalaCircuitTexto(m = cfg.musica) {
  const nombres = TONICAS.map((t) => t[0]);
  const i = nombres.indexOf(String(m.tonica).toUpperCase());
  const [escala, salto] = ESCALA_CIRCUIT[m.escala] || ["Chromatic", 0];
  const tonica = i < 0 ? m.tonica : nombres[(i + salto) % 12];
  return `En la Circuit (botón Scales): tónica ${tonica}, escala ${escala}. Así todo lo que toques queda dentro de la escala del motor`
    + (salto ? " (son las mismas notas, con otra tónica)." : ".");
}

// Armonía. Desde la pestaña: la armonía del tema (la base que siguen las partes sin armonía
// propia). Desde una parte: «Sigue la del tema» (lo que cambies cambia la base) o «Propia».
function escenaDeArmonia() {
  if (!armoniaDesdeParte || parteVista < 0 || !cfg.parte[parteVista]) return -1;
  return cfg.parte[parteVista].escena;
}
function sigueTema(i) { return i >= 0 && cfg.escena[i] && !cfg.escena[i].armonia_propia; }
// La armonía guardada en una escena (la que editas ahora: la que suena, que es la más nueva).
function musicaDeEscena(i) {
  if (edicion && edicion.escena === i) return cfg.musica;
  try { return JSON.parse(cfg.escena[i].datos).musica || {}; } catch (x) { return {}; }
}
function tonoTexto(m) {
  const esc = (ESCALAS.find((e) => e[0] === m.escala) || ["", m.escala || ""])[1];
  return `${m.tonica || ""} ${(esc || "").toLowerCase()}`.trim();
}
function renderArmonia() {
  const caja = $("armonia_caja");
  if (!cfg.armonia_tema) cfg.armonia_tema = Object.assign({}, cfg.musica);
  const ie = escenaDeArmonia();
  const desdeParte = armoniaDesdeParte && parteVista >= 0;
  const propia = desdeParte && ie >= 0 && cfg.escena[ie] && cfg.escena[ie].armonia_propia;
  const base = !propia;   // se edita la armonía del tema
  const m = base ? cfg.armonia_tema : cfg.musica;
  // ¿Lo que suena ahora sigue la armonía del tema? Entonces cambiar la base también lo cambia ya.
  const sonando = cfg.forma ? cfg.forma.escena : -1;
  const reflejar = () => { if (base && (sonando < 0 || sigueTema(sonando) || (desdeParte && ie === sonando))) Object.assign(cfg.musica, cfg.armonia_tema); };
  const ES = {DO: "C", RE: "D", MI: "E", FA: "F", SOL: "G", LA: "A", SI: "B"};
  m.tonica = m.tonica.toUpperCase().replace(/^(DO|RE|MI|FA|SOL|LA|SI)/, (x) => ES[x]);
  const select = (opciones, k) => {
    const s = el("select", {onchange: () => { m[k] = s.value; reflejar(); renderArmonia(); guardar(); }});
    for (const [v, t] of opciones) s.append(el("option", {value: v, textContent: t, selected: v === m[k]}));
    return s;
  };
  const conPropia = cfg.parte.map((p, i) => [p, i]).filter(([p]) => p.escena >= 0 && cfg.escena[p.escena] && cfg.escena[p.escena].armonia_propia);
  const guiada = m.armonia === "guiada";
  caja.innerHTML = "";
  caja.append(...[
    el("h2", {textContent: desdeParte ? "Armonía de la parte" : "Armonía del tema"}),
    desdeParte && ie >= 0 ? campo("Esta parte", segmentado([["tema", "Sigue la del tema"], ["propia", "Propia"]], propia ? "propia" : "tema", async (v) => {
      try { clearTimeout(temporizador); await api("/api/config", cfg); await api("/api/escena/armonia", {escena: ie, propia: v === "propia"}); await recargar(); renderArmonia(); }
      catch (e) { aviso(e.message, true); } }, 2)) : null,
    ayuda(desdeParte && ie < 0 ? "Esta parte no tiene escena: suena lo que esté sonando."
      : propia ? `Esta parte tiene su propia armonía (${tonoTexto(cfg.musica)}). Si cambias la del tema, esta no se mueve.`
      : desdeParte ? `Usa la armonía del tema (${tonoTexto(cfg.armonia_tema)}): lo que cambies aquí cambia todas las partes que la siguen.`
      : cfg.parte.length ? `La siguen todas las partes sin armonía propia.${conPropia.length ? " Con la suya: " + conPropia.map(([p, i]) => `${i + 1} · ${p.nombre} (${tonoTexto(musicaDeEscena(p.escena))})`).join(", ") + "." : ""}`
      : "La armonía del tema. Las partes que armes la siguen, salvo las que tengan armonía propia."),
    campo("Género para todo", segmentado(GENEROS, m.genero, (v) => cambiarGenero(v, base ? {base: true} : {}), 3)),
    ayuda(GENERO_TEXTO[m.genero] + " Pone la escala y los ajustes de este género en todos los motores (lo mismo que sus clips de fábrica)."),
    el("div", {className: "dos"}, [el("label", {className: "campo"}, ["Tónica", select(TONICAS, "tonica")]),
      el("label", {className: "campo"}, ["Escala", select(ESCALAS, "escala")])]),
    ayuda(escalaCircuitTexto(m)),
    campo("Armonía", segmentado([["guiada","Guiada"],["libre","Libre"]], m.armonia, (v) => { m.armonia = v; reflejar(); renderArmonia(); guardar(); }, 2)),
    ayuda(guiada
      ? "Los pads guían: las secuencias, el bajo y el diálogo saben qué acorde suena y cuál viene. Sin pads activos, siguen el acorde de tu nota larga."
      : "Cada motor cuenta sus notas desde su raíz, sin mirar el acorde."),
    guiada ? deslizador(m, "tension", "Tensión", 0, 1, 0.05,
      (x) => x === 0 ? "solo notas del acorde" : x < 0.4 ? `pocas notas de paso (${porcentaje(x)})` : x < 0.7 ? `algunas (${porcentaje(x)})` : `muchas (${porcentaje(x)})`) : null,
    guiada ? ayuda("En las secuencias, cuántas notas fuera del acorde quedan en los tiempos débiles. En los fuertes siempre cae una nota del acorde.") : null,
    guiada ? casilla(m, "anticipar", "Anticipar los cambios de acorde", "La última nota antes del cambio lleva al acorde que viene") : null,
    guiada ? null : casilla(m, "seguir_pads", "Las secuencias siguen al acorde de los pads", "Su nota base sale del acorde que suena"),
    deslizador(m, "desplazamiento", "Pegado ↔ Desplazado", 0, 1, 0.05, desplTexto),
    ayuda("Corre las notas de la llamada, la respuesta y el pulso de los pads. Las secuencias y el bajo no se mueven."),
  ].filter(Boolean));
  // Los deslizadores y casillas cambian `m` y guardan: aquí se refleja en lo que suena antes de enviar.
  caja.oninput = reflejar; caja.onchange = reflejar;
}

const ESCALAS_COLOR = [["","La de Música"],["doble_armonica","Doble armónica"],["persa","Persa"],["enigmatica","Enigmática"]];
const COLOR_TEXTO = {
  "": "Toca en la escala de Música, como los demás motores.",
  doble_armonica: "1 ♭2 3 4 5 ♭6 7: oriental y «misteriosa». Sobre frigio dominante cambia solo la séptima.",
  persa: "1 ♭2 3 4 ♭5 ♭6 7: el tritono en vez de la quinta, muy tenso. Pads y bajo siguen en la escala de Música.",
  enigmatica: "1 ♭2 3 ♯4 ♯5 ♭7 7: ambigua y rara, sin quinta. Úsala en una secuencia sola, sobre una base firme.",
};
const INTERVALOS = {frigio: [0,1,3,5,7,8,10], menor_armonica: [0,2,3,5,7,8,11], frigio_dominante: [0,1,4,5,7,8,10],
  menor: [0,2,3,5,7,8,10], hungara_menor: [0,2,3,6,7,8,11], dorico: [0,2,3,5,7,9,10], lidio: [0,2,4,6,7,9,11],
  doble_armonica: [0,1,4,5,7,8,11]};
function notasDe(tonica, escala) {
  const i = TONICAS.findIndex((x) => x[0] === String(tonica).toUpperCase());
  return new Set((INTERVALOS[escala] || []).map((n) => (n + Math.max(i, 0)) % 12));
}

function renderPuente() {
  const caja = $("puente_caja"); caja.innerHTML = "";
  const actual = notasDe(cfg.musica.tonica, cfg.musica.escala);
  caja.append(el("h2", {textContent: "Entre escenas"}),
    ayuda("Al lanzar una escena con otra tonalidad, en los dos compases antes del cambio suena un acorde puente que es de las dos escalas (si no hay ninguno, la dominante de la nueva). Después, la progresión nueva parte en su i. Lo demás se mueve de a poco durante la transición."));
  if (!cfg.escena.length) { caja.append(el("p", {className: "mut", style: "margin:0", textContent: "Todavía no hay escenas (se guardan en Tocar)."})); return; }
  cfg.escena.forEach((e, i) => {
    let m = {};
    try { m = JSON.parse(e.datos).musica || {}; } catch (x) {}
    const comunes = [...notasDe(m.tonica, m.escala)].filter((n) => actual.has(n)).length;
    const misma = m.tonica === cfg.musica.tonica && m.escala === cfg.musica.escala;
    const texto = misma ? "misma tonalidad" : comunes >= 6 ? `muy emparentada (${comunes} de 7 notas)` : comunes >= 5 ? `emparentada (${comunes} de 7)` : `lejana (${comunes} de 7): el puente ayuda, mejor con transición larga`;
    caja.append(el("div", {className: "fila", style: "min-height:36px"}, [
      el("span", {textContent: `${i + 1} · ${e.nombre}`, style: "font-weight:600"}),
      el("span", {className: "mut", style: "text-align:right", textContent: `${m.tonica || "?"} ${((ESCALAS.find((x) => x[0] === m.escala) || ["", ""])[1]).toLowerCase()} · ${texto}`}),
    ]));
  });
}

// --- Ajustes ---

function renderAjustes() {
  const sc = cfg.scatter;
  if (sc) $("scatter_resto").replaceChildren(
    el("div", {className: "dos"}, [el("label", {className: "campo"}, ["Salida", puertoSelect("salida", sc.salida, (v) => { sc.salida = v; guardar(); })]),
      numeroDe(sc, "canal", "Canal de control", 1, 16)]),
    deslizador(sc, "fuerza", "Fuerza de los pads", 1, 127, 1, (v) => String(v)),
    ayuda("Cada parte elige si lo usa y qué pads, en «Apoyo a la subida». En la MC-101: canal de control igual a este y RX Scatter en ON."));
  const cd = $("canal_disparo"); cd.value = cfg.entrada.canal_disparo;
  cd.onchange = () => { cfg.entrada.canal_disparo = Math.max(1, Math.min(16, parseInt(cd.value) || 4)); cd.value = cfg.entrada.canal_disparo; guardar(); };
  const nm = $("nota_maxima"); nm.value = cfg.entrada.nota_maxima;
  nm.onchange = () => { const v = parseInt(nm.value); cfg.entrada.nota_maxima = isNaN(v) ? 4 : Math.max(0, Math.min(64, v)); nm.value = cfg.entrada.nota_maxima; guardar(); };
  $("cambio").replaceChildren(segmentado([["paso","Al tiro"],["compas","En el próximo compás"]], cfg.musica.cambio_de_nota, (v) => { cfg.musica.cambio_de_nota = v; guardar(); }, 2));
  $("adaptacion").replaceChildren(segmentado([["escala","Se quedan en la escala"],["transponer","Se transponen iguales"]], cfg.musica.adaptacion, (v) => { cfg.musica.adaptacion = v; guardar(); }, 2));
  $("entrada_puerto").replaceChildren(puertoSelect("entrada", cfg.entrada.puerto, (v) => { cfg.entrada.puerto = v; guardar(); }));
  const ta = $("thru_activo"); ta.checked = cfg.thru.activo;
  ta.onchange = () => { cfg.thru.activo = ta.checked; guardar(); };
  const tr = $("thru_reloj"); tr.checked = cfg.thru.reloj !== false;
  tr.onchange = () => { cfg.thru.reloj = tr.checked; guardar(); };
  $("thru_salida").replaceChildren(puertoSelect("salida", cfg.thru.salida, (v) => { cfg.thru.salida = v; guardar(); }));
  $("proyecto_nombre").textContent = cfg.app.proyecto || "Sin proyecto";
  $("proyecto_auto").checked = cfg.app.autoguardar !== false;
  renderControl();
  renderTeclado();
}

// --- Teclado de la MicroFreak (goa/teclado.py) ---
function renderTeclado() {
  const t = cfg.teclado;
  const ta = $("teclado_activo"); ta.checked = t.activo;
  ta.onchange = () => { t.activo = ta.checked; guardar(); renderTeclado(); };
  const resto = $("teclado_resto");
  if (!t.activo) { resto.replaceChildren(ayuda("Para tocar en vivo a través del motor con Local Off: el pad que le manda la Circuit no cambia, y el motor le devuelve sus perillas.")); return; }
  resto.replaceChildren(...[
    el("div", {className: "campo"}, ["Puerto", puertoSelect("entrada", t.puerto, (v) => { t.puerto = v; guardar(); })]),
    el("div", {className: "dos"}, [numeroDe(t, "canal", "Canal en que manda (Output chan)", 1, 16), numeroDe(t, "canal_sinte", "Canal en que suena (el del pad)", 1, 16)]),
    el("label", {className: "fila", style: "min-height:44px"}, [el("span", {}, ["Devolverle sus perillas", el("br"), el("span", {className: "mut", textContent: "Con Local Off sus perillas no le cambian el sonido: el motor se las devuelve por USB"})]),
      el("input", {type: "checkbox", checked: t.perillas, onchange: (e) => { t.perillas = e.target.checked; guardar(); }})]),
    el("div", {id: "teclado_diag"}),
    cfg.tocado && cfg.tocado.activo ? null : el("p", {className: "ayuda", style: "color:var(--bad)", textContent: "Las teclas suenan con el Tocado: actívalo en Motores › Tocado."}),
    t.canal === t.canal_sinte ? el("p", {className: "ayuda", style: "color:var(--bad)", textContent: "Los dos canales tienen que ser distintos: si no, lo que el motor le devuelve vuelve a entrar como perillas."}) : null,
    ayuda(`En la MicroFreak (Utility › MIDI): Local Off · Output: USB · Output chan: ${t.canal} · Knob send CCs: On. El eco de MIDI (para la FM-1) queda como está.`),

  ].filter(Boolean));
}
function pintarTeclado(d) {
  const e = $("teclado_estado"); if (!e) return;
  const t = d.teclado;
  const diag = $("teclado_diag");
  if (!cfg || !cfg.teclado.activo) { e.textContent = "Apagado"; e.style.color = ""; return; }
  if (!t || !t.conectado) {
    e.textContent = "No la encuentro: revisa el cable USB"; e.style.color = "var(--bad)";
    if (diag) diag.replaceChildren(ayuda(`Busco un puerto que diga «${cfg.teclado.puerto}». Entradas que ve la Pi: ${(d.entradas || []).join(", ") || "ninguna"}.`));
    return;
  }
  e.style.color = "";
  e.textContent = `Conectada (${t.conectado})` + (t.ultimo ? " · último: " + t.ultimo : "");
  if (!diag) return;
  if (t.otro_canal) {
    diag.replaceChildren(el("p", {className: "ayuda", style: "color:var(--bad)"}, [
      `La MicroFreak manda por el canal ${t.otro_canal}, no por el ${cfg.teclado.canal}. `,
      el("button", {type: "button", className: "prim", textContent: `Usar el canal ${t.otro_canal}`, onclick: () => {
        cfg.teclado.canal = t.otro_canal; guardar(); renderTeclado(); }})]));
  } else if (!t.recibidos) {
    diag.replaceChildren(ayuda("Todavía no llega nada de la MicroFreak: toca una tecla. Si sigue igual, revisa en su Utility › MIDI que Output sea USB (o Both)."));
  } else {
    diag.replaceChildren();
  }
}

// --- nanoKONTROL2 (goa/control.py) ---
const MAPA_CONTROL = [
  ["Pads", "voces del acorde", "variación"], ["Bajo", "densidad", "filtro (apertura)"],
  ["Secuencia A", "densidad", "mutación"], ["Secuencia B", "densidad", "mutación"],
  ["Diálogo", "densidad", "oscuridad"], ["FX", "filtro en reposo", "locura"],
  ["Texturas", "densidad", "profundidad"], ["Looper", "filtro (CC 74)", "resonancia (CC 71)"],
];
function renderControl() {
  const c = cfg.control;
  const ca = $("control_activo"); ca.checked = c.activo;
  ca.onchange = () => { c.activo = ca.checked; guardar(); renderControl(); };
  const resto = $("control_resto");
  if (!c.activo) { resto.replaceChildren(ayuda("Ocho canales para ocho motores (fader, perilla, S, M y R) y el transporte para las escenas. Conéctalo por USB a la Pi.")); return; }
  const tabla = el("table", {className: "mapa"}, [
    el("tr", {}, ["", "Motor", "Fader", "Perilla"].map((t) => el("th", {textContent: t}))),
    ...MAPA_CONTROL.map(([m, f, p], i) => el("tr", {}, [String(i + 1), m, f, p].map((t) => el("td", {textContent: t})))),
  ]);
  resto.replaceChildren(
    el("div", {className: "campo"}, ["Puerto", puertoSelect("entrada", c.puerto, (v) => { c.puerto = v; guardar(); })]),
    el("div", {className: "dos"}, [numeroDe(c, "canal", "Canal MIDI global", 1, 16), numeroDe(c, "subida", "Compases de la subida (REC)", 1, 32)]),
    el("label", {className: "fila", style: "min-height:44px"}, [el("span", {}, ["Prender sus botones", el("br"), el("span", {className: "mut", textContent: "Pide LED Mode = External en el Kontrol Editor de Korg"})]),
      el("input", {type: "checkbox", checked: c.luces, onchange: (e) => { c.luces = e.target.checked; guardar(); }})]),
    tabla,
    ayuda("S: solo (otra vez y vuelven los demás) · M: prende o apaga el motor · R: seed nueva (en el looper, el loop siguiente)."),
    ayuda("◀ TRACK ▶ elige escena · PLAY la lanza · STOP vuelve a la de antes · SET guarda lo que suena como escena nueva · ◀ MARKER ▶ energía −/+ · CYCLE piloto · REW deshacer · REC subida."),
    ayuda("Faders y perillas recogen el valor: no cambian nada hasta que pasan por donde está el motor (así nada salta, tampoco después de cambiar de escena). Modo CC: al prenderlo, mantén SET + CYCLE."),
  );
}
function pintarControl(d) {
  const e = $("control_estado"); if (!e) return;
  const c = d.control;
  if (!cfg || !cfg.control.activo) { e.textContent = "Apagado"; return; }
  if (!c || !c.conectado) { e.textContent = "No lo encuentro: revisa el cable USB"; e.style.color = "var(--bad)"; return; }
  e.style.color = "";
  const partes = ["Conectado"];
  if (c.solo) partes.push("solo: " + c.solo);
  if (c.ultimo) partes.push("último: " + c.ultimo);
  e.textContent = partes.join(" · ");
}

function render() {
  renderTocar();
  renderMotores();
  renderArmonia();
  renderPuente();
  renderCancion();
  renderAjustes();
}

const modoCancion = () => !!(cfg.cancion && cfg.cancion.activa && cfg.parte && cfg.parte.length);
function renderTocar() {
  const conCancion = modoCancion();
  ahoraFirma = "";
  $("tocar_escenas").replaceChildren(...(conCancion ? [bloqueAhora(),
    recordar(el("details", {className: "grupo"}, [el("summary", {}, [el("span", {className: "cab"}, [el("b", {textContent: "Escenas sueltas"}),
      el("span", {textContent: "lanzar una escena a mano (sale del orden del tema)"})])]), el("div", {className: "cuerpo"}, [bloqueEscenas()])]), "g-vivo-escenas", false)]
    : [bloqueEscenas()]));
  const caja = $("tocar_extra"); caja.innerHTML = "";
  caja.append(...[bloqueEnergia(), conCancion ? null : bloqueSubida(), bloqueFrases(), conCancion ? null : bloquePiloto()].filter(Boolean));
  $("tocar_forma").replaceChildren(bloqueForma());
  renderMutes();
  if (ultimoEstado) pintarTocar(ultimoEstado);
}

// --- Vivo con el tema: qué suena, qué viene y qué hacer después ---
let ahoraFirma = "";
function bloqueAhora() {
  const caja = el("div", {id: "ahora", style: "display:flex;flex-direction:column;gap:14px"});
  pintarAhoraCaja(caja, ultimoEstado && ultimoEstado.cancion);
  return caja;
}
function pedirCancion(datos, mensaje) {
  return (async () => { try { await api("/api/cancion", datos); aviso(mensaje); estado(); } catch (e) { aviso(e.message, true); } })();
}
function pedirSubidaFinal(n) {
  return (async () => { try { await api("/api/subida", {compases: n, final: true}); aviso(`Subida en los últimos ${n} compases de la parte`); estado(); } catch (e) { aviso(e.message, true); } })();
}
function irAOtraParte() {
  let d;
  d = hoja("Ir a otra parte", "Entra en el próximo compás y el tema sigue desde ahí.", [
    el("div", {className: "motores-lista", style: "max-height:60vh;overflow:auto;margin-bottom:12px"}, cfg.parte.flatMap((p, j) =>
      loopMarcado() && (j < loopMarcado()[0] || j > loopMarcado()[1]) ? [] : el("button", {type: "button", onclick: () => { d.close(); pedirCancion({saltar: j}, `${p.nombre} en el próximo compás`); }}, [
        el("span", {className: "punto" + (ultimoEstado && ultimoEstado.cancion && ultimoEstado.cancion.parte === j ? " si" : "")}),
        el("span", {style: "flex:1;min-width:0"}, [p.nombre, el("br"), el("span", {className: "mut", style: "font-size:12px", textContent: `${p.compases} compases · ${p.entrada === "golpe" ? "de golpe" : "suave"}`})]),
        el("span", {className: "mut", textContent: "›"})]))),
    el("div", {className: "acciones"}, [el("button", {type: "button", className: "ancho", textContent: "Cancelar", onclick: () => d.close()})]),
  ]);
}
function pintarAhoraCaja(caja, c) {
  const sonando = c && c.parte !== null && c.parte !== undefined;
  const firma = sonando ? `${c.parte}|${c.siguiente}|${c.largo}|${c.pedida}` : `quieto|${c && c.pedida}`;
  if (firma === ahoraFirma && caja.childElementCount) {
    if (sonando) {
      $("ahora_compas").textContent = `${c.compas} / ${c.largo}`;
      const faltan = c.largo - c.compas + 1;
      const sig = cfg.parte[c.siguiente];
      $("ahora_sigue").textContent = c.pedida !== null && c.pedida !== undefined ? `Pediste ${cfg.parte[c.pedida].nombre}: entra en el próximo compás`
        : sig ? `Sigue: ${sig.nombre} en ${faltan} compás${faltan === 1 ? "" : "es"} · ${sig.entrada === "golpe" ? "de golpe" : "suave"}` : "Es la última parte";
      const inicio = cfg.parte.slice(0, c.parte).reduce((n, p) => n + p.compases, 0);
      document.querySelectorAll("#ahora_mapa i").forEach((x, k) => {
        x.classList.toggle("hecho", k < c.parte); x.classList.toggle("actual", k === c.parte); });
      $("ahora_tiempo").textContent = `${duracionTexto(inicio + c.compas - 1, bpmCancion())} / ${duracionTexto(c.total, bpmCancion())}`;
    }
    return;
  }
  ahoraFirma = firma;
  const mapa = el("div", {className: "cbarra", id: "ahora_mapa", style: "height:12px"}, cfg.parte.map((p) => el("i", {style: `flex:${p.compases} 1 0`, title: p.nombre})));
  if (!sonando) {
    const primera = c && c.pedida !== null && c.pedida !== undefined ? cfg.parte[c.pedida] : cfg.parte[0];
    caja.replaceChildren(el("div", {className: "energia"}, [
      el("span", {className: "mut", style: "font-size:12px;letter-spacing:.06em", textContent: "TEMA · " + (cfg.cancion.nombre || "")}),
      mapa,
      el("b", {style: "font-size:20px", textContent: "Dale Play en la Circuit"}),
      el("span", {className: "mut", textContent: `Parte en ${primera ? primera.nombre : "la primera parte"}, en el uno.`}),
    ]));
    return;
  }
  const p = cfg.parte[c.parte] || {nombre: "?"};
  const sig = cfg.parte[c.siguiente];
  const accion = (titulo, sub, fn, prim) => el("button", {type: "button", className: "vivo-accion" + (prim ? " prim" : ""), onclick: fn}, [
    el("b", {textContent: titulo}), el("span", {textContent: sub})]);
  caja.replaceChildren(
    el("div", {className: "energia ahora"}, [
      el("div", {className: "fila"}, [el("span", {className: "mut", style: "font-size:12px;letter-spacing:.06em", textContent: "AHORA"}),
        el("span", {className: "mut", id: "ahora_tiempo", style: "font-size:12px"})]),
      mapa,
      el("div", {className: "fila", style: "align-items:baseline"}, [
        el("b", {style: "font-size:24px;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap", textContent: p.nombre}),
        el("span", {className: "n", id: "ahora_compas", style: "font-size:22px"})]),
      el("span", {className: "mut", id: "ahora_sigue"}),
    ]),
    el("div", {style: "display:flex;flex-direction:column;gap:8px"}, [
      h3(`Después de ${p.nombre}`),
      el("div", {className: "vivo-acciones"}, [
        accion("Quedarse 16 más", sig ? `${sig.nombre} espera` : "la parte sigue", () => pedirCancion({quedarse: 16}, `${p.nombre} sigue 16 compases más`)),
        sig ? accion(`${sig.nombre} ya`, "en el próximo compás", () => pedirCancion({saltar: c.siguiente}, `${sig.nombre} en el próximo compás`), true) : null,
      ].filter(Boolean)),
      el("button", {type: "button", textContent: "Ir a otra parte…", onclick: irAOtraParte}),
    ]),
    el("div", {className: "energia"}, [
      el("div", {className: "fila"}, [
        el("div", {style: "display:flex;flex-direction:column;gap:2px;min-width:0"}, [
          el("span", {style: "font-size:13px;font-weight:650;color:var(--txt2)", textContent: sig ? `Subida hacia ${sig.nombre}` : "Subida"}),
          el("span", {className: "mut", id: "subida_linea", style: "font-size:12px", textContent: "Riser, filtros y redobles hasta el drop"})]),
      ]),
      el("div", {className: "chips", role: "group", "aria-label": "Subida al final de la parte"}, [
        ...[4, 8, 16].map((n) => el("button", {type: "button", textContent: `últimos ${n}`, style: "flex:1", onclick: () => pedirSubidaFinal(n)})),
        el("button", {type: "button", textContent: "✕", "aria-label": "Cancelar la subida", id: "subida_cancelar", style: "display:none",
          onclick: async () => { try { await api("/api/subida", {compases: 0}); aviso("La subida para en el próximo compás"); estado(); } catch (e) { aviso(e.message, true); } }}),
      ]),
      el("div", {className: "cbarra", id: "subida_barra", style: "display:none"}, [el("i", {style: "flex:0;background:var(--acc)"}), el("i", {style: "flex:1"})]),
    ]),
  );
  pintarAhoraCaja(caja, c);   // completa compás, mapa y «sigue»
}

// --- Escenas ---

let editarEscenas = false;

function resumenEscena(e) {
  let d = {};
  try { d = JSON.parse(e.datos); } catch (x) {}
  const suenan = [];
  if ((d.pads || {}).activo) suenan.push("pads");
  if ((d.bajo || {}).activo) suenan.push("bajo");
  for (const s of d.secuencia || []) if (s.activa) suenan.push(s.nombre);
  if ((d.dialogo || {}).activo) suenan.push("diálogo");
  if ((d.fx || {}).activo) suenan.push("FX");
  const m = d.musica || {};
  return `${nombreGenero(m.genero || "")} · ${m.tonica || ""} ${((ESCALAS.find((x) => x[0] === m.escala) || ["", ""])[1]).toLowerCase()} · ${suenan.join(", ") || "silencio"}`;
}

function bloqueEscenas() {
  const f = cfg.forma;
  const grilla = el("div", {className: "escenas", id: "escenas"});
  cfg.escena.forEach((e, i) => {
    const barra = el("i", {style: `width:${Math.round(e.energia * 100)}%`});
    const boton = el("button", {type: "button", className: "escena", "data-escena": i, onclick: () => editarEscenas ? null : lanzarEscena(i)}, [
      el("span", {className: "t"}, [el("span", {textContent: `${i + 1} · ${e.nombre}`}), el("span", {className: "e"})]),
      el("span", {className: "d", textContent: resumenEscena(e)}),
      el("span", {className: "barra"}, [barra]),
    ]);
    if (editarEscenas) {
      grilla.append(el("div", {style: "display:flex;flex-direction:column;gap:4px;min-width:0"}, [boton,
        el("button", {type: "button", textContent: "Editar", style: "font-size:12px;padding:0 6px", onclick: async () => { editarEscenas = false; await entrarEdicion({escena: i}); abrirParte(-1); }}),
        el("div", {className: "dos", style: "gap:4px"}, [
          el("button", {type: "button", textContent: "Guardar aquí", style: "font-size:12px;padding:0 6px", onclick: () => guardarEscena(i)}),
          el("button", {type: "button", textContent: "Borrar", style: "font-size:12px;padding:0 6px;color:var(--bad)", onclick: () => borrarEscena(i)}),
        ])]));
    } else grilla.append(boton);
  });
  if (cfg.escena.length < 16) {
    grilla.append(el("button", {type: "button", className: "escena nueva", onclick: () => guardarEscena(null)}, ["+ Guardar lo que suena"]));
  }
  const chips = el("div", {className: "chips", role: "group", "aria-label": "Compases de transición"});
  for (const n of [1, 4, 8, 16]) chips.append(el("button", {type: "button", textContent: n === 1 ? "al compás" : String(n), "aria-pressed": f.transicion === n ? "true" : "false",
    onclick: () => { f.transicion = n; renderTocar(); guardar(); }}));
  return el("div", {style: "display:flex;flex-direction:column;gap:8px"}, [
    el("div", {className: "fila"}, [h3("Escenas"), cfg.escena.length ? el("button", {type: "button", textContent: editarEscenas ? "Listo" : "Editar",
      style: "min-height:32px;padding:0 12px;font-size:12px", onclick: () => { editarEscenas = !editarEscenas; renderTocar(); }}) : null]),
    grilla,
    el("div", {className: "fila"}, [el("span", {className: "mut", textContent: "Transición (compases)"}), chips]),
    cfg.escena.length ? null : ayuda("Una escena guarda cómo suena todo ahora (géneros, estilos, variantes, qué motores suenan y la energía). Al lanzarla, el motor llega a ella de a poco, sin cortar."),
  ]);
}

async function lanzarEscena(i) {
  try {
    clearTimeout(temporizador); await api("/api/config", cfg);
    await api("/api/escena/lanzar", {indice: i}); await recargar(); estado();
    aviso(cfg.forma.transicion > 1 ? `Hacia ${cfg.escena[i].nombre} en ${cfg.forma.transicion} compases` : `${cfg.escena[i].nombre} en el próximo compás`);
  } catch (e) { aviso(e.message, true); }
}

async function guardarEscena(i) {
  const actual = i === null ? `Escena ${cfg.escena.length + 1}` : cfg.escena[i].nombre;
  const nombre = prompt(i === null ? "Nombre de la escena" : "Guardar lo que suena ahora en esta escena. Nombre:", actual);
  if (nombre === null) return;
  try {
    clearTimeout(temporizador); await api("/api/config", cfg);
    await api("/api/escena/guardar", i === null ? {nombre} : {nombre, indice: i}); await recargar(); aviso("Escena guardada");
  } catch (e) { aviso(e.message, true); }
}

async function borrarEscena(i) {
  const f = fotoPartes(), nombre = cfg.escena[i].nombre;
  try { await api("/api/escena/borrar", {indice: i}); await recargar(); avisoDeshacer(`Escena ${nombre} borrada`, () => volverPartes(f)); } catch (e) { aviso(e.message, true); }
}

