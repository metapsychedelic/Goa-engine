// Yantra · Tema: canción, línea de tiempo, partes, energía, subida y forma.
// Scripts clásicos en orden: comparten el ámbito global con los demás archivos de js/.
// --- Canción ---
// La canción es una lista de partes (intro, build...). Cada parte tiene sus compases,
// una escena (lo que suena) y su energía. Con el modo canción prendido, al dar Play en
// la Circuit parte desde el principio y cambia de parte justo en el compás, igual que
// la cadena de escenas de la Circuit (con los mismos largos).

function duracionTexto(compases, bpm) {
  const t = Math.round(compases * 240 / bpm);
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;
}
const bpmCancion = () => (ultimoEstado && ultimoEstado.bpm) || 140;
const escenasCircuit = (partes) => partes.reduce((n, p) => n + Math.ceil(p.compases / 16), 0);

function textoTotal() {
  const total = cfg.parte.reduce((n, p) => n + p.compases, 0);
  if (!total) return "";
  const n = escenasCircuit(cfg.parte), bpm = bpmCancion();
  return `${total} compases · ${duracionTexto(total, bpm)} a ${Math.round(bpm)} BPM · ${n} escena${n === 1 ? "" : "s"} de la Circuit` +
    (n > 16 ? " (la Circuit tiene 16: acorta o junta partes)" : "");
}

function resumenParte(p) {
  const esc = p.escena >= 0 && cfg.escena[p.escena] ? cfg.escena[p.escena].nombre : "sigue lo que suena";
  const ener = Math.round(p.energia * 100) === Math.round(p.energia_fin * 100) ? `${Math.round(p.energia * 100)}`
    : `${Math.round(p.energia * 100)}→${Math.round(p.energia_fin * 100)}`;
  const subida = [p.pads_suben && "pads suben", p.roll && "roll", p.corte_bajo && "corte de bajo", p.tension && "tensión", p.hueco && "hueco", p.riser && "riser", p.scatter && "scatter"].filter(Boolean);
  return `${p.compases} compases · ${esc} · ${p.entrada === "golpe" ? "de golpe" : "suave"} · energía ${ener}${subida.length ? " · " + subida.join(", ") : ""}`;
}

async function accionParte(ruta, datos, mensaje) {
  try {
    clearTimeout(temporizador); await api("/api/config", cfg);
    await api(ruta, datos); await recargar(); estado();
    if (mensaje) aviso(mensaje);
  } catch (e) { aviso(e.message, true); }
}

function bloqueParte(p, i) {
  const c = cfg.cancion;
  const nombre = el("input", {type: "text", value: p.nombre, maxLength: 24,
    onchange: () => { p.nombre = nombre.value.trim() || p.nombre; renderCancion(); guardar(); }});
  const escena = el("select", {"aria-label": "Escena de la parte",
    onchange: () => { p.escena = parseInt(escena.value); renderCancion(); guardar(); }});
  escena.append(el("option", {value: -1, textContent: "— Sigue lo que suena —"}));
  cfg.escena.forEach((e, j) => escena.append(el("option", {value: j, textContent: `${j + 1} · ${e.nombre}`})));
  escena.value = String(p.escena);
  const mover = (d) => { const j = i + d; if (j < 0 || j >= cfg.parte.length) return;
    [cfg.parte[i], cfg.parte[j]] = [cfg.parte[j], cfg.parte[i]]; renderCancion(); guardar(); };
  const g = grupo(`g-parte-${i}`, `${i + 1} · ${p.nombre}`, resumenParte(p), [
    el("div", {className: "dos"}, [el("label", {className: "campo"}, ["Nombre", nombre]),
      numeroDe(p, "compases", "Compases", 1, 256, renderCancion)]),
    el("label", {className: "campo"}, ["Escena (lo que suena)", escena]),
    el("div", {className: "dos"}, [
      el("button", {type: "button", textContent: c.activa ? "Saltar aquí" : "Escuchar",
        onclick: () => accionParte("/api/parte/escuchar", {indice: i}, c.activa ? `${p.nombre} en el próximo compás` : `Suena ${p.nombre}`)}),
      c.activa ? null : el("button", {type: "button", className: "prim", textContent: "Editar",
        onclick: () => entrarEdicion({parte: i})}),
    ].filter(Boolean)),
    el("div", {}, [
      el("button", {type: "button", textContent: "Guardar lo que suena", style: "width:100%",
        onclick: async () => { const f = fotoPartes();
          await accionParte("/api/parte/guardar", {indice: i}, `Guardado en ${p.nombre}`);
          if (f.parte[i] && f.parte[i].escena >= 0) avisoDeshacer(`Guardado en ${p.nombre}`, () => volverPartes(f)); }}),
    ]),
    deslizador(p, "energia", "Energía al empezar", 0, 1, 0.05, (v) => Math.round(v * 100), () => renderCancion()),
    deslizador(p, "energia_fin", "Energía al terminar", 0, 1, 0.05, (v) => Math.round(v * 100), () => renderCancion()),
    campo("Entrada", segmentado([["suave", "Suave"], ["golpe", "De golpe"]], p.entrada, (v) => { p.entrada = v; renderCancion(); guardar(); }, 2)),
    h3("Apoyo a la subida (opcional)"),
    casilla(p, "pads_suben", "Los pads acompañan la subida", "El pulso acelera (de 2 a 8 golpes por compás), suben de fuerza y suman una voz al final. En la parte siguiente vuelven a lo de su escena.", () => renderCancion()),
    casilla(p, "roll", "Roll de las secuencias", `En ${p.compases >= 8 ? "los 2 últimos compases" : "el último compás"} repiten un tiempo, después medio, después una semicorchea: el loop que se encoge antes del cambio.`, () => renderCancion()),
    casilla(p, "corte_bajo", "Corte de bajo", `El bajo se calla en ${p.compases >= 8 ? "los 2 últimos compases" : "el último compás"} para que la parte siguiente pegue más.`, () => renderCancion()),
    casilla(p, "tension", "Acorde de tensión al final", "El último compás va a un acorde que pide resolver (♭II en frigio, V en menor armónica, ♭VII en menor) y la parte siguiente parte en la i. Lo siguen los pads, el bajo y las secuencias guiadas.", () => renderCancion()),
    casilla(p, "hueco", "Hueco antes del cambio", "El último tiempo de la parte, el motor queda en silencio.", () => renderCancion()),
    casilla(p, "riser", "Riser de FX", `Subida de FX en ${p.compases > 32 ? "los 32 últimos compases" : "toda la parte"}: riser, filtros que bajan y se abren, redobles en las secuencias con FX. En el uno de la parte siguiente, el drop con su caída.`, () => renderCancion()),
    casilla(p, "scatter", "Scatter de la MC-101", "Aprieta pads de Scatter de la MC-101 al final de la parte: suave, intenso en los 2 últimos compases y extremo en el último tiempo. Se suelta justo en el uno de la parte siguiente.", () => { renderCancion(); if (vista === "parte") renderParte(); }),
    ...(p.scatter ? bloqueScatter(p) : []),
    ayuda(p.entrada === "golpe" ? "Entra de una en su primer compás, con su energía (como un drop)."
      : `Llega de a poco en los compases antes (los de Transición en Vivo, como mucho la mitad de la parte anterior). Los motores entran y salen justo en su primer compás.`),
    el("div", {className: "dos"}, [
      el("div", {className: "dos", style: "gap:4px"}, [
        el("button", {type: "button", textContent: "↑", "aria-label": "Subir", disabled: i === 0, onclick: () => mover(-1)}),
        el("button", {type: "button", textContent: "↓", "aria-label": "Bajar", disabled: i === cfg.parte.length - 1, onclick: () => mover(1)})]),
      el("button", {type: "button", textContent: "Borrar parte", style: "color:var(--bad)",
        onclick: async () => { const f = fotoPartes(); cfg.parte.splice(i, 1); renderCancion(); await enviarConfig();
          avisoDeshacer(`Parte ${p.nombre} borrada`, () => volverPartes(f)); }}),
    ]),
  ]);
  g.dataset.parte = i;
  g.id = `g-parte-${i}`;
  if (i === parteSel) g.classList.add("elegida");
  return g;
}

// --- Loop de partes: como dejar una cadena de escenas en la Circuit ---
function loopMarcado() {
  const c = cfg.cancion || {};
  const d = c.loop_desde ?? -1, h = c.loop_hasta ?? -1;
  return d >= 0 && h >= d && h < cfg.parte.length ? [d, h] : null;
}
async function ponerLoop(loop) {
  try {
    await api("/api/cancion", loop ? {loop, activa: true} : {loop}); await recargar(); estado();   // el loop es del modo canción: lo prende
    if (!loop) aviso("Sin loop: el tema completo desde el próximo Play");
    else {
      const comp = cfg.parte.slice(loop[0], loop[1] + 1).reduce((n, p) => n + p.compases, 0);
      aviso(`Loop de la parte ${loop[0] + 1} a la ${loop[1] + 1} (${comp} compases), desde el próximo Play`);
    }
  } catch (e) { aviso(e.message, true); }
}
function bloqueLoop() {
  const lp = loopMarcado();
  const opciones = (sel) => cfg.parte.map((p, i) => el("option", {value: String(i), textContent: `${i + 1} · ${p.nombre}`, selected: i === sel}));
  const desde = el("select", {"aria-label": "Loop desde la parte"}, opciones(lp ? lp[0] : 0));
  const hasta = el("select", {"aria-label": "Loop hasta la parte"}, opciones(lp ? lp[1] : Math.min(cfg.parte.length - 1, 1)));
  const aplicar = () => { let d = parseInt(desde.value), h = parseInt(hasta.value); if (h < d) [d, h] = [h, d]; ponerLoop([d, h]); };
  desde.onchange = () => { if (lp) aplicar(); };
  hasta.onchange = () => { if (lp) aplicar(); };
  const comp = lp ? cfg.parte.slice(lp[0], lp[1] + 1).reduce((n, p) => n + p.compases, 0) : 0;
  return el("div", {style: "display:flex;flex-direction:column;gap:6px;border-top:1px solid var(--line);padding-top:10px;margin-top:2px"}, [
    el("div", {className: "fila"}, [
      el("span", {style: "font-size:13px;font-weight:650;color:var(--txt2)", textContent: lp ? `↻ Loop · ${comp} compases` : "Loop de partes"}),
      lp ? el("button", {type: "button", textContent: "Quitar", style: "min-height:32px;padding:0 12px;font-size:12px", onclick: () => ponerLoop(null)})
        : el("button", {type: "button", className: "prim", textContent: "Hacer loop", style: "min-height:32px;padding:0 12px;font-size:12px", onclick: aplicar})]),
    el("div", {className: "dos"}, [el("label", {className: "campo"}, ["Desde", desde]), el("label", {className: "campo"}, ["Hasta", hasta])]),
    el("span", {className: "mut", style: "font-size:12px", textContent: lp
      ? "Al dar Play parte en la primera del loop y repite solo esas partes, como la cadena de escenas de la Circuit. Cambiarlo vale desde el próximo Play."
      : "Para trabajar unas partes: deja la misma cadena de escenas en la Circuit y marca aquí las mismas partes."}),
  ]);
}
async function limpiarTodo() {
  // Lo que suena (o la parte que editas): todos los motores y las secuencias a sus valores
  // de fábrica y en silencio; quedan sus salidas y canales. Se puede deshacer.
  const nombre = edicion ? `«${edicion.nombre}»` : "Lo que suena";
  try {
    await enviarPendiente();
    await api("/api/limpiar", {});
    await recargar(); estado();
    avisoDeshacer(`${nombre}: todo de fábrica y en silencio`, deshacerUltimo);
  } catch (e) { aviso(e.message, true); }
}
async function cargarPlantilla() {
  let lista = [];
  try { lista = (await (await fetch("/api/plantillas")).json()).plantillas; } catch (e) { aviso("Sin conexión con la Pi", true); return; }
  if (!lista.length) { aviso("No hay plantillas", true); return; }
  const texto = lista.map((p, i) => `${i + 1}. ${p.nombre}: ${p.partes} partes, ${p.compases} compases. ${p.descripcion}`).join("\n");
  const r = prompt(`¿Qué plantilla?\n${texto}\n\nEscribe el número:`, "1");
  if (r === null) return;
  const p = lista[parseInt(r) - 1];
  if (!p) { aviso("Ese número no está en la lista", true); return; }
  const f = fotoPartes();
  await accionParte("/api/cancion/plantilla", {clave: p.clave}, `${p.nombre} cargada: elige qué suena en cada parte`);
  if (f.parte.length) avisoDeshacer(`${p.nombre} cargada`, () => volverPartes(f));
}

async function actualizarConPlantilla() {
  let lista = [];
  try { lista = (await (await fetch("/api/plantillas")).json()).plantillas; } catch (e) { aviso("Sin conexión con la Pi", true); return; }
  const m = /^\s*Template\s+(\d+)/.exec(cfg.cancion.nombre || "");
  let clave = m ? `template${m[1]}` : null;
  if (!lista.some((p) => p.clave === clave)) {
    const texto = lista.map((p, i) => `${i + 1}. ${p.nombre}`).join("\n");
    const r = prompt(`¿De qué plantilla es tu canción?\n${texto}\n\nEscribe el número:`, "1");
    if (r === null) return;
    const p = lista[parseInt(r) - 1];
    if (!p) { aviso("Ese número no está en la lista", true); return; }
    clave = p.clave;
  }
  const nombre = lista.find((p) => p.clave === clave).nombre;
  const fotoAntes = fotoPartes();
  try {
    clearTimeout(temporizador); await api("/api/config", cfg);
    const r = await api("/api/cancion/actualizar", {clave});
    await recargar(); estado();
    const cambios = r.cambios || [];
    if (!cambios.length) aviso("Tu canción ya estaba al día");
    else avisoDeshacer(`${cambios.length} cambio${cambios.length === 1 ? "" : "s"}: ${cambios.slice(0, 2).join(" · ")}${cambios.length > 2 ? "…" : ""}`, () => volverPartes(fotoAntes));
  } catch (e) { aviso(e.message, true); }
}

async function nuevaParte() {
  const nombre = prompt("Nombre de la parte (guarda lo que suena ahora como su escena)", `Parte ${cfg.parte.length + 1}`);
  if (nombre === null) return;
  const compases = parseInt(prompt("¿Cuántos compases dura?", "16"));
  if (isNaN(compases)) return;
  accionParte("/api/parte/nueva", {nombre, compases}, `${nombre} agregada`);
}

// --- Tema: la línea de tiempo ---
// Partes × motores: qué suena en cada parte (de la escena de cada parte), dónde cambia de
// estilo o variante, la energía y los apoyos. Tocar un casillero entra a editar ese motor
// en esa parte; tocar el nombre de una parte la elige (su tarjeta, abajo).
let parteSel = null;
const cacheDatos = new Map();
function datosEscena(i) {
  const e = cfg.escena[i];
  if (!e) return null;
  if (!cacheDatos.has(e.datos)) { try { cacheDatos.set(e.datos, JSON.parse(e.datos)); } catch (x) { cacheDatos.set(e.datos, null); } }
  return cacheDatos.get(e.datos);
}
function seccionDe(datos, clave) {
  if (!datos) return null;
  if (clave.startsWith("sec")) return (datos.secuencia || [])[parseInt(clave.slice(3))] || null;
  return datos[clave] || null;
}
function suenaEn(datos, clave, k) { const s = seccionDe(datos, clave); return !!(s && s[k]); }
const SIGLAS = {pads: "Pa", bajo: "Ba", dialogo: "Di", fx: "FX", texturas: "Tx", looper: "Lp", tocado: "To"};
const sigla = (clave, nombre) => SIGLAS[clave] || (nombre || "").slice(0, 2);
function apoyosDe(p) {
  return [p.riser && "riser", p.roll && "roll", p.corte_bajo && "corte", p.tension && "tensión", p.hueco && "hueco", p.pads_suben && "pads", p.scatter && "scatter"].filter(Boolean);
}
function parteSonando() {
  const c = ultimoEstado && ultimoEstado.cancion;
  if (c && c.parte !== null && c.parte !== undefined) return c.parte;
  const e = cfg.forma.escena;
  return e >= 0 ? cfg.parte.findIndex((p) => p.escena === e) : -1;
}
function celdasLinea() {
  // [{clave, nombre, k, celdas: [{estado: "sin"|"off"|"on"|"cambia"}]}]
  const ms = motores();
  const datos = cfg.parte.map((p) => p.escena >= 0 ? datosEscena(p.escena) : null);
  return ms.map(([clave, nombre, , k]) => ({clave, nombre, k, celdas: cfg.parte.map((p, i) => {
    if (!datos[i]) return "sin";
    if (!suenaEn(datos[i], clave, k)) return "off";
    const antes = i > 0 && datos[i - 1] && suenaEn(datos[i - 1], clave, k) ? seccionDe(datos[i - 1], clave) : null;
    return antes && difiere(seccionDe(datos[i], clave), antes) ? "cambia" : "on";
  })}));
}
async function editarMotorEnParte(i, clave) {
  const p = cfg.parte[i];
  parteVista = i; escribirLocal("parte_vista", i);
  try {
    if (cfg.cancion.activa) {
      await api("/api/cancion", {activa: false});   // para editar, el tema deja de avanzar solo (se vuelve a prender en Tema)
    }
    const yaEdito = edicion && p.escena >= 0 && edicion.escena === p.escena;
    if (!yaEdito) { await api("/api/editar", {parte: i}); await recargar(); await estado(); }
    if (clave) { motorSel = clave; escribirLocal("motor", clave); mostrar("motores"); renderMotores(); }
    else if (vista === "parte") renderParte();
    aviso(`Editando ${p.nombre}${clave ? " · " + (motores().find((m) => m[0] === clave) || [, ""])[1] : ""}`);
  } catch (e) { aviso(e.message, true); }
}
function bloqueScatter(p) {
  const pad = (k, titulo, cuando) => {
    const sel = el("select", {"aria-label": `Pad de Scatter: ${titulo}`, onchange: () => { p[k] = parseInt(sel.value); guardar(); }},
      [el("option", {value: "0", textContent: "no suena"}), ...Array.from({length: 16}, (_, n) => el("option", {value: String(n + 1), textContent: `pad ${n + 1}`}))]);
    sel.value = String(p[k] ?? 0);
    return el("label", {className: "fila", style: "min-height:44px;gap:10px"}, [
      el("span", {style: "min-width:0"}, [el("b", {textContent: titulo, style: "font-weight:600"}), el("br"), el("span", {className: "mut", style: "font-size:12px", textContent: cuando})]),
      el("span", {style: "flex:none;width:120px"}, [sel])]);
  };
  const desde = p.scatter_compases || 4;
  const sc = cfg.scatter || {salida: "MC-101", canal: 16};
  return [el("div", {className: "card", style: "display:flex;flex-direction:column;gap:6px"}, [
    campo("Empieza antes del final (compases)", segmentado([["2","2"],["4","4"],["8","8"],["16","16"]], String(desde), (v) => { p.scatter_compases = parseInt(v); guardar(); renderCancion(); if (vista === "parte") renderParte(); }, 4)),
    desde > 2 ? pad("scatter_suave", "Suave", `desde ${desde} compases antes`) : null,
    pad("scatter_intenso", "Intenso", "los 2 últimos compases"),
    pad("scatter_extremo", "Extremo", "el último tiempo"),
    ayuda(`Sale por ${sc.salida}, canal ${sc.canal} (el de control de la MC-101; pad 1 = nota 60 … pad 16 = nota 75). En la MC-101, RX Scatter tiene que estar en ON. El canal se cambia en Ajustes.`),
  ].filter(Boolean))];
}
function elegirParte(i) {
  parteSel = parteSel === i ? null : i;
  renderCancion();
  if (parteSel !== null) { const g = document.getElementById(`g-parte-${i}`); if (g) { g.open = true; g.scrollIntoView({behavior: "smooth", block: "start"}); } }
}
// --- Copiar y pegar en la línea de tiempo ---
// Mantener apretado (o clic derecho) un casillero abre un menú: editar, copiar ese motor,
// pegarlo, igual en la siguiente parte, que no suene aquí; y para la parte entera, copiar
// y pegar (eligiendo qué motores). Copiar entra al modo pegar: cada toque pega ahí.
let portapapeles = null;   // {tipo: "motor", clave, nombre, desde, pegadas: []} | {tipo: "parte", desde, pegadas: []}
function hoja(titulo, sub, hijos) {
  const d = el("dialog", {className: "hoja", "aria-label": titulo}, [el("div", {className: "asa"}), el("h2", {textContent: titulo}),
    sub ? el("div", {className: "sub", textContent: sub}) : null, ...hijos].filter(Boolean));
  d.addEventListener("click", (e) => { if (e.target === d) d.close(); });
  d.addEventListener("close", () => d.remove());
  document.body.append(d); d.showModal();
  return d;
}
const nombreMotor = (clave) => (motores().find((m) => m[0] === clave) || [, clave])[1];
function resumenMotor(datos, clave) {
  const s = seccionDe(datos, clave);
  if (!s) return "";
  return [s.estilo, s.genero, s.seed || s.variante, s.progresion].filter(Boolean).slice(0, 3).join(" · ");
}
async function pegarMotor(desde, hacia, motoresLista) {
  const r = await api("/api/parte/copiar", {desde, hacia, motores: motoresLista});
  await recargar(); await estado();
  if (r.compartidas && r.compartidas.length) aviso(`Ojo: esa escena también la usa ${r.compartidas.join(", ")}, y cambió ahí también`, true);
  return r;
}
function menuCasillero(i, clave) {
  const p = cfg.parte[i], m = motores().find((x) => x[0] === clave);
  const datos = p.escena >= 0 ? datosEscena(p.escena) : null;
  const suena = datos && suenaEn(datos, clave, m[3]);
  const puedePegar = portapapeles && portapapeles.tipo === "motor" && portapapeles.clave === clave && portapapeles.desde !== i;
  let d;
  const accion = (txt, fn, extra = {}) => el("button", Object.assign({type: "button", textContent: txt, onclick: async () => { d.close(); try { await fn(); } catch (e) { aviso(e.message, true); } }}, extra));
  d = hoja(`${m[1]} · ${p.nombre}`, !datos ? "Parte sin escena todavía" : suena ? (resumenMotor(datos, clave) || "Suena en esta parte") : "No suena en esta parte", [
    el("div", {className: "acciones"}, [
      accion("Editar", () => editarMotorEnParte(i, clave), {className: "prim ancho"}),
      accion("Copiar", async () => { if (!datos) throw new Error(`${p.nombre} todavía no tiene escena: edítala primero`);
        portapapeles = {tipo: "motor", clave, nombre: m[1], desde: i, pegadas: []}; pintarPegar(); renderCancion(); }, {disabled: !datos}),
      accion(puedePegar ? `Pegar ${portapapeles.nombre} de ${cfg.parte[portapapeles.desde].nombre}` : "Pegar", async () => {
        await pegarMotor(portapapeles.desde, [i], [clave]); aviso(`${m[1]} de ${cfg.parte[portapapeles.desde].nombre} pegado en ${p.nombre}`); }, {disabled: !puedePegar}),
      accion("Igual en la siguiente", async () => { if (!datos) throw new Error(`${p.nombre} todavía no tiene escena`);
        await pegarMotor(i, [i + 1], [clave]); aviso(`${m[1]} de ${p.nombre} también en ${cfg.parte[i + 1].nombre}`); }, {disabled: !datos || i + 1 >= cfg.parte.length}),
      accion("Que no suene aquí", async () => { await api("/api/parte/apagar", {parte: i, motor: clave}); await recargar(); await estado(); aviso(`${m[1]} callado en ${p.nombre}`); },
        {disabled: !suena, className: "peligro"}),
    ]),
    el("h3", {textContent: `Toda la parte ${p.nombre}`}),
    el("div", {className: "acciones"}, [
      accion("Copiar la parte", async () => { if (!datos) throw new Error(`${p.nombre} todavía no tiene escena`);
        portapapeles = {tipo: "parte", desde: i, pegadas: []}; pintarPegar(); renderCancion(); }, {disabled: !datos}),
      accion("Pegar una parte aquí", () => elegirMotoresYPegar(portapapeles.desde, i), {disabled: !(portapapeles && portapapeles.tipo === "parte" && portapapeles.desde !== i)}),
    ]),
  ]);
}
function elegirMotoresYPegar(desde, hacia) {
  const origen = datosEscena(cfg.parte[desde].escena);
  const ms = motores();
  const marcas = ms.map(([clave, nombre, , k]) => el("input", {type: "checkbox", checked: true, "aria-label": nombre, "data-clave": clave}));
  let d;
  d = hoja(`Pegar ${cfg.parte[desde].nombre} en ${cfg.parte[hacia].nombre}`, "Elige qué motores llevar: lo demás de la parte queda como está.", [
    el("div", {style: "display:flex;flex-direction:column;gap:2px;max-height:50vh;overflow:auto;margin-bottom:12px"}, ms.map(([clave, nombre, , k], n) =>
      el("label", {className: "fila", style: "min-height:44px;justify-content:flex-start;gap:12px"}, [marcas[n],
        el("span", {}, [nombre, el("br"), el("span", {className: "mut", style: "font-size:12px", textContent: suenaEn(origen, clave, k) ? (resumenMotor(origen, clave) || "suena") : "no suena"})])]))),
    el("div", {className: "acciones"}, [
      el("button", {type: "button", textContent: "Cancelar", onclick: () => d.close()}),
      el("button", {type: "button", className: "prim", textContent: "Pegar", onclick: async () => {
        const elegidos = marcas.filter((x) => x.checked).map((x) => x.dataset.clave);
        d.close();
        if (!elegidos.length) return;
        try { await pegarMotor(desde, [hacia], elegidos);
          if (portapapeles) { portapapeles.pegadas.push(hacia); pintarPegar(); }
          aviso(`${elegidos.length} motor${elegidos.length > 1 ? "es" : ""} de ${cfg.parte[desde].nombre} en ${cfg.parte[hacia].nombre}`); } catch (e) { aviso(e.message, true); } }}),
    ]),
  ]);
}
function pintarPegar() {
  const caja = $("pegar_caja"), b = $("pegar");
  if (!portapapeles) { caja.hidden = true; return; }
  const pp = portapapeles, origen = cfg.parte[pp.desde] ? cfg.parte[pp.desde].nombre : "";
  b.replaceChildren(
    el("span", {className: "t"}, [el("b", {textContent: pp.tipo === "motor" ? `Pegando ${pp.nombre} de ${origen}` : `Pegando la parte ${origen}`}), el("br"),
      el("span", {className: "mut", textContent: (pp.tipo === "motor" ? `Toca casilleros de ${pp.nombre}` : "Toca el nombre de otra parte") + (pp.pegadas.length ? ` · pegado en ${pp.pegadas.length}` : "")})]),
    el("button", {type: "button", className: "prim", textContent: "Listo", onclick: () => { portapapeles = null; pintarPegar(); renderCancion(); }}));
  caja.hidden = false;
}
function apretar(boton, alApretar) {
  // Mantener apretado ~0,45 s (o clic derecho): abre el menú; el clic que sigue no cuenta.
  let reloj = null, largo = false;
  const cortar = () => { clearTimeout(reloj); reloj = null; };
  boton.addEventListener("pointerdown", (e) => { largo = false; cortar(); reloj = setTimeout(() => { largo = true; if (navigator.vibrate) navigator.vibrate(15); alApretar(); }, 450); });
  for (const ev of ["pointerup", "pointerleave", "pointercancel"]) boton.addEventListener(ev, cortar);
  boton.addEventListener("contextmenu", (e) => { e.preventDefault(); cortar(); largo = true; alApretar(); });
  boton.addEventListener("click", (e) => { if (largo) { e.stopImmediatePropagation(); e.preventDefault(); largo = false; } }, true);
}
async function tocarCasillero(i, clave) {
  const pp = portapapeles;
  if (pp && pp.tipo === "motor") {
    if (clave !== pp.clave || i === pp.desde) { aviso(`Estás pegando ${pp.nombre}: toca un casillero de esa columna, o «Listo»`); return; }
    try { await pegarMotor(pp.desde, [i], [clave]); pp.pegadas.push(i); pintarPegar(); renderCancion();
      aviso(`${pp.nombre} pegado en ${cfg.parte[i].nombre}`); } catch (e) { aviso(e.message, true); }
    return;
  }
  editarMotorEnParte(i, clave);
}
function tocarNombreParte(i) {
  const pp = portapapeles;
  if (pp && pp.tipo === "parte") { if (i !== pp.desde) elegirMotoresYPegar(pp.desde, i); return; }
  abrirParte(i);
}
// --- Parte: lo que suena en una parte, y desde ahí cada motor ---
// parteVista: índice de la parte, o -1 para «lo que suena ahora» (sin parte).
let parteVista = parseInt(leerLocal("parte_vista", "-1"));
function abrirParte(i) { parteVista = i; escribirLocal("parte_vista", i); mostrar("parte"); }
function nombreVista() { return parteVista >= 0 && cfg.parte[parteVista] ? cfg.parte[parteVista].nombre : "Lo que suena"; }
function pintarVolver() {
  for (const id of ["volver_motores", "volver_armonia"]) {
    const caja = $(id); if (!caja) continue;
    const i = parteVista;
    const enArmonia = id === "volver_armonia";
    const ir = async (j) => {
      if (enArmonia) { await editarMotorEnParte(j, null); mostrar("armonia"); renderArmonia(); }
      else await editarMotorEnParte(j, motorSel);
      pintarVolver();
    };
    const vecinas = i >= 0 && cfg.parte[i] ? el("div", {className: "der"}, [
      i > 0 ? el("button", {type: "button", className: "vecina", "aria-label": `Parte anterior: ${cfg.parte[i - 1].nombre}`, title: cfg.parte[i - 1].nombre,
        onclick: () => ir(i - 1)}, [el("span", {textContent: `‹ ${i} · ${cfg.parte[i - 1].nombre}`})]) : null,
      i < cfg.parte.length - 1 ? el("button", {type: "button", className: "vecina sig", "aria-label": `Parte siguiente: ${cfg.parte[i + 1].nombre}`, title: cfg.parte[i + 1].nombre,
        onclick: () => ir(i + 1)}, [el("span", {textContent: `${i + 2} · ${cfg.parte[i + 1].nombre} ›`})]) : null,
    ].filter(Boolean)) : null;
    caja.replaceChildren(...[el("button", {type: "button", className: "atras", onclick: () => mostrar("parte")},
      [el("span", {textContent: "‹", style: "font-size:22px;line-height:1"}), (i >= 0 && cfg.parte[i] ? `${i + 1} · ` : "") + nombreVista()]), vecinas].filter(Boolean));
  }
}
function editandoVista() { return parteVista >= 0 && !!edicion && cfg.parte[parteVista] && cfg.parte[parteVista].escena === edicion.escena; }
function textoArmonia(m) {
  if (!m) return "";
  const esc = (ESCALAS.find((e) => e[0] === m.escala) || ["", m.escala || ""])[1];
  return [`${m.tonica || ""} ${(esc || "").toLowerCase()}`.trim(), m.progresion, m.armonia].filter(Boolean).join(" · ");
}
async function abrirMotor(clave) {
  if (parteVista >= 0) {
    if (clave === "armonia") { await editarMotorEnParte(parteVista, null); mostrar("armonia"); renderArmonia(); }
    else await editarMotorEnParte(parteVista, clave);
  } else if (clave === "armonia") { mostrar("armonia"); renderArmonia(); }
  else { motorSel = clave; escribirLocal("motor", clave); mostrar("motores"); renderMotores(); }
}
function renderParte() {
  const caja = $("parte_caja");
  if (!caja || !cfg) return;
  if (parteVista >= cfg.parte.length) parteVista = -1;
  const i = parteVista, p = i >= 0 ? cfg.parte[i] : null;
  const vivo = !p || p.escena < 0 || editandoVista();
  const datos = vivo ? null : datosEscena(p.escena);
  const fuente = (clave) => vivo ? seccionDe({...cfg, secuencia: cfg.secuencia}, clave) : seccionDe(datos, clave);
  const desde = p ? cfg.parte.slice(0, i).reduce((s, x) => s + x.compases, 1) : 0;
  const ms = motores();
  const filas = [["armonia", "Armonía", null]].concat(ms.map(([c, n, , k]) => [c, n, k])).map(([clave, nombre, k]) => {
    const s = clave === "armonia" ? (vivo ? cfg.musica : datos && datos.musica) : fuente(clave);
    const suena = clave === "armonia" ? true : !!(s && s[k]);
    const resumen = clave === "armonia" ? textoArmonia(s) : !s ? "Sin escena todavía" : suena ? (resumenMotor({x: s}, "x") || "suena") : "no suena aquí";
    const cambio = editandoVista() && (clave === "armonia" ? edicion.original && difiere(cfg.musica, edicion.original.musica) : motorCambiado(clave));
    return el("button", {type: "button", onclick: () => abrirMotor(clave), "aria-label": `${nombre}: ${resumen}. Abrir`}, [
      el("span", {className: "punto" + (suena ? " si" : "")}),
      el("span", {className: "txt" + (suena ? "" : " callado")}, [el("b", {textContent: nombre}), el("span", {textContent: resumen})]),
      cambio ? el("span", {className: "cambio", "aria-hidden": "true"}) : null,
      el("span", {className: "mut", "aria-hidden": "true", textContent: "›"}),
    ].filter(Boolean));
  });
  const nav = el("div", {className: "volver"}, [
    el("button", {type: "button", className: "atras", onclick: () => mostrar("cancion")}, [el("span", {textContent: "‹", style: "font-size:22px;line-height:1"}), "Tema"]),
    p ? el("div", {className: "der"}, [
      el("button", {type: "button", textContent: "‹", "aria-label": "Parte anterior", disabled: i === 0, onclick: () => abrirParte(i - 1)}),
      el("button", {type: "button", textContent: "›", "aria-label": "Parte siguiente", disabled: i === cfg.parte.length - 1, onclick: () => abrirParte(i + 1)})]) : null,
  ].filter(Boolean));
  const cab = el("div", {style: "display:flex;flex-direction:column;gap:6px"}, [
    p ? el("div", {className: "mut", style: "font-size:11px;font-family:'Plex Mono Local',monospace", textContent: `PARTE ${i + 1} · COMPASES ${desde}–${desde + p.compases - 1}`}) : null,
    el("h1", {style: "margin:0;font-size:26px;font-weight:700", textContent: p ? p.nombre : "Lo que suena ahora"}),
    p ? el("div", {className: "chips-info"}, [
      el("span", {textContent: `${p.compases} compases`}), el("span", {textContent: p.entrada === "golpe" ? "de golpe" : "suave"}),
      el("span", {textContent: `energía ${Math.round(p.energia * 100)} → ${Math.round(p.energia_fin * 100)}`}),
      ...apoyosDe(p).map((a) => el("span", {textContent: a}))]) :
      ayuda("Lo que está sonando, sin parte: lo que muevas aquí no queda en ninguna parte hasta que lo guardes en una (o crees una con lo que suena)."),
  ].filter(Boolean));
  const acciones = p && !editandoVista() ? el("div", {className: "dos"}, [
    el("button", {type: "button", className: "prim", textContent: "Editar esta parte", onclick: () => editarMotorEnParte(i, null)}),
    el("button", {type: "button", textContent: cfg.cancion.activa ? "Saltar aquí" : "Escuchar",
      onclick: () => accionParte("/api/parte/escuchar", {indice: i}, cfg.cancion.activa ? `${p.nombre} en el próximo compás` : `Suena ${p.nombre}`)}),
  ]) : !p ? el("button", {type: "button", textContent: "+ Parte con lo que suena", onclick: nuevaParte}) : null;
  const limpiar = el("button", {type: "button", textContent: p ? `Limpiar ${p.nombre}` : "Limpiar lo que suena",
    title: "Todos los motores y las secuencias a sus valores de fábrica, en silencio",
    onclick: async () => { if (p && !editandoVista()) { await editarMotorEnParte(i, null); if (!editandoVista()) return; } await limpiarTodo(); if (vista === "parte") renderParte(); }});
  const ajustes = p ? bloqueParte(p, i) : null;
  if (ajustes) { ajustes.open = true; ajustes.querySelector("summary b").textContent = "Entrada, apoyos y ajustes de la parte"; }
  caja.replaceChildren(...[nav, cab, acciones, el("div", {className: "motores-lista"}, filas), limpiar, ajustes,
    p && !vivo ? null : null].filter(Boolean));
}

function lineaVertical() { return !window.matchMedia("(min-width: 700px)").matches; }
function renderLinea() {
  if (!cfg.parte.length) return null;
  const pistas = celdasLinea();
  const sonando = parteSonando();
  const editando = edicion ? cfg.parte.findIndex((p) => p.escena === edicion.escena) : -1;
  const pp = portapapeles;
  const marcaPegar = (m, i) => !pp || pp.tipo !== "motor" || m.clave !== pp.clave ? "" : i === pp.desde ? " fuente" : pp.pegadas.includes(i) ? " pegada" : " destino";
  const celda = (m, est, i) => { const b = el("button", {type: "button",
    className: `lt-c ${est === "on" ? "on" : est === "cambia" ? "on cambia" : est}${i === editando ? " editando" : ""}${marcaPegar(m, i)}`,
    textContent: est === "cambia" ? "◆" : "",
    "aria-label": `${m.nombre} en ${cfg.parte[i].nombre}: ${est === "sin" ? "parte sin escena" : est === "off" ? "no suena" : est === "cambia" ? "suena, cambia" : "suena"} · ${pp && pp.tipo === "motor" ? "pegar aquí" : "editar; mantén apretado para copiar y más"}`,
    onclick: () => tocarCasillero(i, m.clave)});
    apretar(b, () => menuCasillero(i, m.clave)); return b; };
  const total = cfg.parte.reduce((s, p) => s + p.compases, 0);
  const lp = loopMarcado();
  const enLoop = (i) => !lp ? "" : i >= lp[0] && i <= lp[1] ? " en-loop" : " fuera-loop";
  let caja;
  if (lineaVertical()) {
    const cols = `84px repeat(${pistas.length}, minmax(0, 1fr)) 22px`;
    const altura = (p) => Math.max(32, Math.round(p.compases * 1.6 + 8));
    const filas = cfg.parte.map((p, i) => el("div", {className: "lt-fila" + (i === parteSel ? " sel" : "") + enLoop(i), style: `grid-template-columns:${cols};height:${altura(p)}px`}, [
      el("button", {type: "button", className: "lt-parte" + (p.entrada === "golpe" ? " golpe" : "") + (i === sonando ? " suena" : "") + enLoop(i), onclick: () => tocarNombreParte(i),
        "aria-label": `${p.nombre}, ${p.compases} compases: elegir`},
        [el("b", {textContent: p.nombre}), el("span", {textContent: `${p.compases}${apoyosDe(p).length ? " · " + apoyosDe(p).join(" ") : ""}`})]),
      ...pistas.map((m) => celda(m, m.celdas[i], i)),
      el("div", {className: "lt-en", "aria-hidden": "true"}, [el("i", {style: `height:${Math.max(3, Math.round((altura(p) - 6) * (p.energia + p.energia_fin) / 2))}px;opacity:${0.35 + 0.65 * (p.energia + p.energia_fin) / 2}`})]),
    ]));
    const cab = el("div", {className: "lt-v"}, [
      el("div", {className: "lt-fila", style: `grid-template-columns:${cols}`}, [el("span", {className: "lt-lab", textContent: "Parte"}),
        ...pistas.map((m) => el("span", {className: "lt-lab", style: "justify-content:center;font-family:'Plex Mono Local',monospace;font-size:10px", title: m.nombre, textContent: sigla(m.clave, m.nombre)})),
        el("span", {className: "lt-lab", style: "font-size:9px", textContent: "en."})]),
      ...filas,
      el("div", {className: "lt-cab", id: "lt_cab", style: "display:none;left:0;right:0;width:auto;height:2px"})]);
    caja = el("div", {className: "linea" + (pp ? (pp.tipo === "motor" ? " pegando" : " pegando-parte") : ""), id: "linea"}, [cab]);
    caja.dataset.vertical = "1";
    caja._alturas = cfg.parte.map(altura);
  } else {
    const cols = `104px ${cfg.parte.map((p) => p.compases + "fr").join(" ")}`;
    const fila = (lab, hijos) => [lab, ...hijos];
    let x = 0; const pts = [];
    cfg.parte.forEach((p) => { pts.push(`${x},${(40 - p.energia * 36).toFixed(1)}`); x += p.compases; pts.push(`${x},${(40 - p.energia_fin * 36).toFixed(1)}`); });
    const svg = `<svg viewBox="0 0 ${total} 40" preserveAspectRatio="none" width="100%" height="34" role="img" aria-label="Energía de cada parte"><polyline points="0,40 ${pts.join(" ")} ${total},40" fill="rgba(191,198,255,.14)" stroke="none"/><polyline points="${pts.join(" ")}" fill="none" stroke="#BFC6FF" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>`;
    const energia = el("div", {style: "grid-column:2 / -1;background:var(--card2);border-radius:8px;padding:3px 0"}); energia.innerHTML = svg;
    let desde = 1;
    const grid = el("div", {className: "lt-h", style: `grid-template-columns:${cols}`}, [
      ...fila(el("span", {className: "lt-lab", textContent: "Partes"}), cfg.parte.map((p, i) => { const d = desde; desde += p.compases;
        return el("button", {type: "button", className: "lt-parte" + (p.entrada === "golpe" ? " golpe" : "") + (i === parteSel ? " sel" : "") + (i === sonando ? " suena" : "") + enLoop(i),
          onclick: () => tocarNombreParte(i), title: p.nombre, "aria-label": `${p.nombre}, compás ${d}, ${p.compases} compases: elegir`}, [el("b", {textContent: p.nombre}), el("span", {textContent: String(d)})]); })),
      el("span", {className: "lt-lab", textContent: "Energía"}), energia,
      ...pistas.flatMap((m) => fila(el("span", {className: "lt-lab", textContent: m.nombre}), m.celdas.map((est, i) => celda(m, est, i)))),
      ...fila(el("span", {className: "lt-lab", textContent: "Apoyos"}), cfg.parte.map((p) => el("span", {className: "lt-apoyo", textContent: apoyosDe(p).join(" · ")}))),
      el("div", {className: "lt-cab", id: "lt_cab", style: "display:none;top:0;bottom:0"}),
    ]);
    caja = el("div", {className: "linea" + (pp ? (pp.tipo === "motor" ? " pegando" : " pegando-parte") : ""), id: "linea"}, [grid]);
  }
  const ley = el("div", {className: "linea-ley"}, [
    el("span", {}, [el("i", {style: "background:#5A5F96"}), "suena"]),
    el("span", {}, [el("i", {style: "background:#9AA2E6"}), "cambia de estilo o variante ◆"]),
    el("span", {}, [el("i", {style: "background:repeating-linear-gradient(45deg,transparent 0 3px,#33334a 3px 6px)"}), "parte sin escena"]),
    el("span", {}, [el("i", {style: "width:3px;background:var(--txt)"}), "entra de golpe"]),
  ]);
  const nota = el("p", {className: "ayuda", style: "margin:0", textContent: "Toca un casillero para editar ese motor en esa parte; mantenlo apretado (o clic derecho) para copiar, pegar y más. Toca el nombre de una parte para ver sus ajustes."});
  setTimeout(() => moverCabezal(), 0);
  return el("div", {style: "display:flex;flex-direction:column;gap:8px"}, [caja, ley, nota]);
}
let claveLinea = "";
function refrescarLinea() {
  // Lo que cambia solo (la parte que suena, la que editas): se vuelve a dibujar si cambió
  // y no estás escribiendo en una tarjeta de parte.
  if (!cfg || (vista !== "cancion" && vista !== "parte")) return;
  const editando = edicion ? edicion.escena : -1;
  const clave = `${vista}|${parteSonando()}|${editando}|${lineaVertical()}`;
  const activo = document.activeElement;
  const escribiendo = activo && /INPUT|SELECT|TEXTAREA/.test(activo.tagName) && ($("cancion_caja").contains(activo) || $("parte_caja").contains(activo));
  if (clave !== claveLinea && !escribiendo) { claveLinea = clave; if (vista === "parte") renderParte(); else renderCancion(); }
  else moverCabezal();
}
window.matchMedia("(min-width: 700px)").addEventListener("change", () => refrescarLinea());
function moverCabezal() {
  const cab = $("lt_cab"), caja = $("linea");
  if (!cab || !caja || !cfg) return;
  const c = ultimoEstado && ultimoEstado.cancion;
  if (!c || !c.posicion || !c.total) { cab.style.display = "none"; return; }
  cab.style.display = "block";
  const f = (c.posicion - 1) / c.total;
  if (caja.dataset.vertical) {
    // por filas: la parte y dónde va dentro de ella
    let y = 22 + 3, i = 0;   // cabecera
    for (; i < c.parte; i++) y += caja._alturas[i] + 3;
    y += Math.round(caja._alturas[c.parte] * (c.compas - 1) / Math.max(1, c.largo));
    cab.style.top = y + "px";
  } else {
    cab.style.left = `calc(104px + 3px + (100% - 107px) * ${f.toFixed(4)})`;
  }
}

function renderCancion() {
  const caja = $("cancion_caja");
  if (!caja || !cfg) return;
  const c = cfg.cancion;
  const chk = el("input", {type: "checkbox", className: "switch", checked: c.activa, "aria-label": "Modo canción",
    onchange: async () => { try { await api("/api/cancion", {activa: chk.checked}); await recargar(); estado();
      aviso(chk.checked ? "Modo canción: parte desde el principio al dar Play en la Circuit" : "Modo libre"); } catch (e) { aviso(e.message, true); } }});
  const barra = el("div", {className: "cbarra", id: "cancion_barra"}, cfg.parte.map((p, i) => el("i", {style: `flex:${p.compases}`, "data-i": i})));
  const fin = el("div", {className: "chips", role: "group", "aria-label": "Al terminar"});
  for (const [k, t] of [["repetir", "repite"], ["quedarse", "se queda en la última"]]) fin.append(el("button", {type: "button", textContent: t, "aria-pressed": c.al_final === k ? "true" : "false",
    onclick: async () => { c.al_final = k; renderCancion(); try { await api("/api/cancion", {al_final: k}); } catch (e) { aviso(e.message, true); } }}));
  caja.replaceChildren(
    el("div", {className: "dos"}, [
      el("button", {type: "button", textContent: "Lo que suena ›", onclick: () => abrirParte(-1)}),
      el("button", {type: "button", textContent: edicion ? `Limpiar «${edicion.nombre}»` : "Limpiar", onclick: limpiarTodo,
        title: "Todos los motores y las secuencias a sus valores de fábrica, en silencio"})]),
    ...[renderLinea()].filter(Boolean),
    el("div", {className: "energia"}, [
      el("div", {className: "fila"}, [
        el("div", {style: "display:flex;flex-direction:column;gap:2px;min-width:0"}, [
          el("span", {style: "font-size:13px;font-weight:650;color:var(--txt2)", textContent: cfg.parte.length ? `Modo canción · ${c.nombre}` : "Modo canción"}),
          el("span", {className: "mut", id: "cancion_linea", style: "font-size:12px",
            textContent: !c.activa ? "Apagado: modo libre, como siempre" : cfg.parte.length ? "Parte desde el principio al dar Play en la Circuit" : "Agrega partes para empezar"})]),
        chk]),
      cfg.parte.length ? barra : null,
      el("span", {className: "mut", id: "cancion_total", style: "font-size:12px", textContent: textoTotal()}),
      cfg.parte.length ? el("div", {className: "fila"}, [el("span", {className: "mut", textContent: "Al terminar"}), fin]) : null,
      cfg.parte.length > 1 ? bloqueLoop() : null,
    ]),
    el("div", {style: "display:flex;flex-direction:column;gap:8px"}, [
      cfg.parte.length < 32 ? el("button", {type: "button", textContent: "+ Parte con lo que suena", onclick: nuevaParte}) : null,
      el("button", {type: "button", textContent: "Cargar plantilla…", onclick: cargarPlantilla}),
      el("button", {type: "button", textContent: "Actualizar con la plantilla…", onclick: actualizarConPlantilla}),
      cfg.parte.some((p) => p.escena < 0) ? ayuda("Las partes sin escena siguen lo que suena. Para elegir qué suena en una: arma el sonido en modo libre y toca «Guardar lo que suena» en esa parte.") : null,
      ayuda("Arma cada parte en modo libre: toca «Editar» en la parte, y todo lo que muevas (secuencias, pads, bajo…) queda guardado en ella al momento. Arriba aparece «Listo» para terminar y «Descartar» para volverla a como estaba. «Escuchar» solo la hace sonar, sin editarla."),
      ayuda("Para tocar con la Circuit: prende el modo canción y arma su cadena de escenas con los mismos largos. Al dar Play en la Circuit los dos parten juntos. Si se desfasan (por ejemplo, saltaste una escena en la Circuit), usa «Saltar aquí» en la parte que corresponde."),
    ]),
  );
  if (ultimoEstado) pintarCancion(ultimoEstado);
  if (vista === "parte") renderParte();
}

function pintarCancion(d) {
  const c = d.cancion;
  const linea = $("cancion_linea");
  document.querySelectorAll("#cancion_barra i").forEach((b) => {
    const i = parseInt(b.dataset.i);
    b.classList.toggle("actual", !!c && c.parte === i);
    b.classList.toggle("hecho", !!c && c.parte !== null && i < c.parte);
  });
  document.querySelectorAll("#cancion_caja details[data-parte]").forEach((g) => g.classList.toggle("parte-actual", !!c && c.parte === parseInt(g.dataset.parte)));
  const total = $("cancion_total");
  if (total) total.textContent = textoTotal();
  if (!linea || !c || !cfg.cancion.activa) return;
  if (c.pedida !== null && c.pedida !== undefined) { linea.textContent = `${cfg.parte[c.pedida].nombre} en el próximo compás`; return; }
  if (c.parte === null) { linea.textContent = "Parte desde el principio al dar Play en la Circuit"; return; }
  const p = cfg.parte[c.parte], sig = c.siguiente !== null ? cfg.parte[c.siguiente] : null;
  linea.textContent = `${p ? p.nombre : "?"} · compás ${c.compas} de ${c.largo}` + (sig ? ` · luego ${sig.nombre}` : "") +
    ` · ${duracionTexto(c.posicion - 1, bpmCancion())} de ${duracionTexto(c.total, bpmCancion())}` + (c.vuelta > 1 ? ` · vuelta ${c.vuelta}` : "");
}

// --- Energía ---

let energiaTocando = 0, energiaTemp = null;

function textoEnergia(x) {
  return x < 0.2 ? "calma" : x < 0.4 ? "tranquilo" : x < 0.6 ? "normal" : x < 0.8 ? "arriba" : "clímax";
}

function bloqueEnergia() {
  const f = cfg.forma;
  const numero = el("span", {className: "n", id: "energia_n", textContent: Math.round(f.energia * 100)});
  const r = el("input", {type: "range", min: 0, max: 100, step: 1, value: Math.round(f.energia * 100), id: "energia", "aria-label": "Energía",
    oninput: () => {
      energiaTocando = Date.now();
      f.energia = parseInt(r.value) / 100; numero.textContent = r.value;
      clearTimeout(energiaTemp);
      energiaTemp = setTimeout(() => api("/api/energia", {energia: f.energia}).catch((e) => aviso(e.message, true)), 250);
    }});
  if (cfg.cancion.activa && cfg.parte.length) r.disabled = true;  // en modo canción la maneja cada parte
  return el("div", {className: "energia"}, [
    el("div", {className: "fila"}, [el("label", {htmlFor: "energia", style: "font-size:13px;font-weight:650;color:var(--txt2)"}, ["Energía ", el("span", {className: "mut", id: "energia_t", textContent: "· " + textoEnergia(f.energia)})]), numero]),
    r,
    r.disabled ? ayuda("En modo canción la energía la maneja cada parte (en Tema, cada parte tiene la suya).") : null,
    el("div", {className: "ley"}, [el("span", {textContent: "calma"}), el("span", {textContent: "50 = tus ajustes", style: "text-align:center"}), el("span", {textContent: "clímax"})]),
  ]);
}

// --- Subida de FX ---

function bloqueSubida() {
  const hay = cfg.fx.activo || cfg.secuencia.some((s) => s.fx);
  const chips = el("div", {className: "chips", role: "group", "aria-label": "Lanzar subida"});
  for (const n of [8, 16, 32]) chips.append(el("button", {type: "button", textContent: String(n), "aria-label": `Subida de ${n} compases`,
    onclick: async () => { try { await api("/api/subida", {compases: n}); aviso(`Subida de ${n} compases desde el próximo compás`); estado(); } catch (e) { aviso(e.message, true); } }}));
  chips.append(el("button", {type: "button", textContent: "✕", "aria-label": "Cancelar la subida", id: "subida_cancelar", style: "display:none",
    onclick: async () => { try { await api("/api/subida", {compases: 0}); aviso("La subida para en el próximo compás"); estado(); } catch (e) { aviso(e.message, true); } }}));
  return el("div", {className: "energia"}, [
    el("div", {className: "fila"}, [
      el("div", {style: "display:flex;flex-direction:column;gap:2px;min-width:0"}, [
        el("span", {style: "font-size:13px;font-weight:650;color:var(--txt2)", textContent: "Subida"}),
        el("span", {className: "mut", id: "subida_linea", style: "font-size:12px", textContent: hay ? "Riser, filtros y redobles hasta el drop" : "Prende el FX o marca FX en una secuencia"})]),
      chips]),
    el("div", {className: "cbarra", id: "subida_barra", style: "display:none"}, [el("i", {style: "flex:0;background:var(--acc)"}), el("i", {style: "flex:1"})]),
  ]);
}

function pintarSubida(d) {
  const linea = $("subida_linea"), cancelar = $("subida_cancelar"), barra = $("subida_barra");
  if (!linea) return;
  const s = d.subida;
  const origen = s && {manual: "", cancion: " (canción)", piloto: " (piloto)"}[s.origen];
  if (cancelar) cancelar.style.display = s && (s.pedida || s.origen === "manual") ? "" : "none";
  if (barra) barra.style.display = s && s.largo ? "" : "none";
  if (!s) { const hay = cfg.fx.activo || cfg.secuencia.some((x) => x.fx);
    linea.textContent = hay ? "Riser, filtros y redobles hasta el drop" : "Prende el FX o marca FX en una secuencia"; return; }
  if (s.pedida !== undefined) { linea.textContent = s.final ? `En los últimos ${s.pedida} compases de la parte` : s.pedida ? `Empieza en el próximo compás (${s.pedida})` : "Para en el próximo compás"; return; }
  linea.textContent = `Subiendo${origen} · compás ${s.compas} de ${s.largo} · drop en ${s.largo - s.compas + 1}`;
  const [a, b] = barra.children;
  a.style.flex = String(s.compas); b.style.flex = String(Math.max(0, s.largo - s.compas));
}

// --- Forma: variación larga (y piloto) ---

const PLAN = [["intro","Intro",16],["build","Build",16],["climax","Clímax",32],["break","Break",8],["drop","Drop",32]];
const FACTOR = {corta: 0.5, normal: 1, larga: 2};

function bloquePiloto() {
  const f = cfg.forma;
  const chk = el("input", {type: "checkbox", className: "switch", checked: f.piloto, "aria-label": "Piloto automático",
    onchange: async () => { f.piloto = chk.checked; try { await api("/api/piloto", {activo: f.piloto}); renderTocar(); estado(); } catch (e) { aviso(e.message, true); } }});
  const plan = el("div", {className: "plan", id: "plan"});
  for (const [k, nombre, n] of PLAN) plan.append(el("button", {type: "button", "data-sec": k, "aria-label": `Saltar a ${nombre}`,
    onclick: async () => { try { await api("/api/piloto", {seccion: k}); f.piloto = true; renderTocar(); aviso(`${nombre} en el próximo compás`); } catch (e) { aviso(e.message, true); } }},
    [nombre, el("small", {textContent: String(Math.max(4, Math.floor(n * FACTOR[f.duracion])))})]));
  const dur = el("div", {className: "chips", role: "group", "aria-label": "Duración de las secciones"});
  for (const [k, t] of [["corta","corta"],["normal","normal"],["larga","larga"]]) dur.append(el("button", {type: "button", textContent: t, "aria-pressed": f.duracion === k ? "true" : "false",
    onclick: async () => { f.duracion = k; try { await api("/api/piloto", {duracion: k}); renderTocar(); } catch (e) { aviso(e.message, true); } }}));
  return el("div", {className: "energia"}, [
    el("div", {className: "fila"}, [
      el("div", {style: "display:flex;flex-direction:column;gap:2px;min-width:0"}, [
        el("span", {style: "font-size:13px;font-weight:650;color:var(--txt2)", textContent: "Piloto automático"}),
        el("span", {className: "mut", id: "piloto_linea", style: "font-size:12px", textContent: f.piloto ? "Arranca en el próximo borde de frase" : "Apagado: tú manejas la energía"})]),
      chk]),
    plan,
    el("div", {className: "fila"}, [el("span", {className: "mut", textContent: "Secciones"}), dur]),
    f.piloto ? null : ayuda("Arma la forma solo: intro, build, clímax, break y drop, moviendo la energía y quién suena. Toca una sección para saltar a ella. Si mueves la energía, el piloto se apaga y tomas el control."),
  ]);
}

function bloqueForma() {
  const f = cfg.forma;
  const chips = el("div", {className: "chips", role: "group", "aria-label": "Compases de cada período"});
  for (const n of [16, 32]) chips.append(el("button", {type: "button", textContent: String(n), "aria-pressed": f.periodo === n ? "true" : "false",
    onclick: () => { f.periodo = n; renderTocar(); guardar(); }}));
  return el("div", {className: "energia", id: "forma_caja"}, [
    deslizador(f, "variacion", "Variación larga", 0, 1, 0.05, (x) => x === 0 ? "apagada" : x < 0.35 ? `poca (${porcentaje(x)})` : x < 0.7 ? `media (${porcentaje(x)})` : `mucha (${porcentaje(x)})`),
    el("div", {className: "fila"}, [el("span", {className: "mut", textContent: "Cambia cada (compases)"}), chips]),
    el("span", {className: "mut", id: "director_linea", textContent: ""}),
  ]);
}

function pintarTocar(d) {
  if (modoCancion() !== !!$("ahora") && vista === "tocar") { renderTocar(); return; }
  const ahora = $("ahora");
  if (ahora) pintarAhoraCaja(ahora, d.cancion);
  const pl = d.forma && d.forma.piloto;
  if (!!pl !== !!cfg.forma.piloto && Date.now() - energiaTocando > 1500) { cfg.forma.piloto = !!pl; renderTocar(); return; }
  const linea = $("piloto_linea");
  if (linea && pl) {
    const nombre = (k) => (PLAN.find((x) => x[0] === k) || [k, k])[1];
    linea.textContent = pl.seccion ? `${nombre(pl.seccion)} · compás ${pl.compas} de ${pl.largo} · luego ${nombre(pl.siguiente)}` : "Arranca en el próximo borde de frase";
    let pasada = true;
    document.querySelectorAll("#plan [data-sec]").forEach((b) => {
      const actual = b.dataset.sec === pl.seccion;
      if (actual) pasada = false;
      b.classList.toggle("actual", actual);
      b.classList.toggle("hecho", !!pl.seccion && pasada && !actual);
    });
  }
  document.querySelectorAll("#mutes .mute").forEach((b) => {
    const calla = !!(pl && pl.calla && pl.calla.includes(b.dataset.motor));
    b.classList.toggle("piloto", calla);
    if (calla) { b.classList.remove("cola"); b.querySelector("span").textContent = "piloto"; }
  });
  const dl = $("director_linea");
  if (dl && d.forma) dl.textContent = !cfg.forma.variacion ? "Sin variación larga: todo suena tal como lo armaste."
    : d.forma.director && d.forma.director.length ? "Este período: " + d.forma.director.join(" · ")
    : "Este período: tal como lo armaste. Variantes hermanas, motivos que vuelven, octavas, cambio de roles y pads que solo guían entran al empezar cada período.";
  const f = d.forma;
  if (!f || !cfg) return;
  const tr = f.transicion;
  document.querySelectorAll("#escenas [data-escena]").forEach((b) => {
    const i = parseInt(b.dataset.escena);
    const cola = tr && tr.escena === i;
    const actual = !cola && f.escena === i;
    b.classList.toggle("cola", !!cola);
    b.classList.toggle("actual", actual);
    b.querySelector(".e").textContent = cola ? (tr.puente ? "puente…" : `en ${tr.faltan + 1} comp.`) : actual ? "sonando" : "";
  });
  if (Date.now() - energiaTocando > 1500) {
    const r = $("energia");
    const real = Math.round(f.energia * 100), pedida = Math.round(f.pedida * 100);
    if (r && document.activeElement !== r) r.value = pedida;
    const n = $("energia_n");
    if (n) n.textContent = real === pedida ? real : `${real} → ${pedida}`;
    const t2 = $("energia_t");
    if (t2) t2.textContent = "· " + textoEnergia(f.energia);
  }
}

async function api(ruta, datos) {
  await enviarPendiente();   // un cambio que todavía esperaba sus 350 ms va primero (si no, se perdía)
  const r = await fetch(ruta, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(datos || {})});
  const d = await r.json();
  if (!r.ok) throw new Error(d.error || "No se pudo");
  return d;
}

