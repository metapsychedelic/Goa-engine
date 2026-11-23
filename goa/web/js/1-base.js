// Yantra · Base: constantes, utilidades, puertos MIDI y navegación.
// Scripts clásicos en orden: comparten el ámbito global con los demás archivos de js/.
const TONICAS = [["C","C · Do"],["C#","C# · Do#"],["D","D · Re"],["D#","D# · Re#"],["E","E · Mi"],["F","F · Fa"],["F#","F# · Fa#"],["G","G · Sol"],["G#","G# · Sol#"],["A","A · La"],["A#","A# · La#"],["B","B · Si"]];
// Cada progresión: [clave, texto · en qué escalas suena mejor]. Todas se pueden usar con cualquier escala.
const PROGRESIONES = [
  ["i_bII","i – ♭II · oscura, el gesto del Goa · frigio"],
  ["i_bII_bIII_bII","i – ♭II – ♭III – ♭II · la subida clásica del Goa · frigio"],
  ["i_bIII_bII_i","i – ♭III – ♭II – i · baja al ♭II y cierra · frigio"],
  ["i_bVI_bII","i – ♭VI – ♭II · oscura y amplia · frigio"],
  ["i_iv_bVI_bIII","i – iv – ♭VI – ♭III · el del drop psy · menor"],
  ["i_v_bVI_iv","i – v – ♭VI – iv · con menor armónica, V mayor"],
  ["i_v_bVI_bVII","i – v – ♭VI – ♭VII · la de los breakdowns · menor"],
  ["i_bIII_iv_bVII","i – ♭III – iv – ♭VII · el bajo sube y cae · menor, frigio"],
  ["i_bIII_bVII_iv","i – ♭III – ♭VII – iv · en quintas suena muy psy · menor, frigio"],
  ["i_ii_bIII_iv","i – ii – ♭III – iv · sube por grados (en frigio, ♭II) · menor, frigio"],
  ["iv_bIII_iv_i","iv – ♭III – iv – i · parte lejos y llega a la i · menor"],
  ["iv_bVII_i_bVII","iv – ♭VII – i – ♭VII · la i queda al medio · menor"],
  ["i_bII_bVII_i","i – ♭II – ♭VII – i · sube al ♭II y baja por el ♭VII · frigio"],
  ["i_iv_bII_i","i – iv – ♭II – i · ciclo largo para breaks · frigio"],
  ["i_bVII_bVI_bVII","i – ♭VII – ♭VI – ♭VII · va y vuelve, hipnótica · frigio, menor"],
  ["i_bVI_bVII","i – ♭VI – ♭VII · épica, para clímax · frigio, menor"],
  ["drone_modal","Drone modal · la raíz fija, acordes encima · frigio, todas"],
  ["i_v","i – v · oriental (con menor armónica suena V) · menor armónica, húngara"],
  ["andaluza","i – ♭VII – ♭VI – V · bajada andaluza · menor armónica"],
  ["i_bVI_bVII_v","i – ♭VI – ♭VII – v · chillgressive · menor"],
  ["i_bVI_iv_v","i – ♭VI – iv – v · chillout · menor"],
  ["i_IV","i – IV · abierta, psy chill · dórica"],
  ["i_IV_i_bVII","i – IV – i – ♭VII · psy chill · dórica"],
  ["pedal_I_II","I – II sobre la raíz · galáctica, ambient · lidia"]];
// Qué da cada escala con la progresión al azar (solo acordes mayores y menores).
const AZAR_ESCALA = {
  frigio: "Frigio: lo más Goa al azar. Usa i, ♭II, ♭III, iv, ♭VI y ♭vii; prefiere el ♭II.",
  frigio_dominante: "Frigio dominante: oriental, pero tiene pocos acordes limpios (I, ♭II, iv, ♭vii): salen pocas variaciones.",
  menor: "Menor natural: la más versátil al azar. ♭VI y ♭VII le dan el aire épico de trance.",
  menor_armonica: "Menor armónica: el V mayor le da tensión que vuelve a la i. Usa i, iv, V y ♭VI.",
  hungara_menor: "Húngara menor: muy exótica en melodías, pero solo tiene i, V, ♭VI y vii limpios: pocas variaciones.",
  dorico: "Dórica: luminosa, ideal para psy chill. El IV mayor es su color.",
  lidio: "Lidia: flotante y espacial (ambient). El II mayor es su color.",
  doble_armonica: "Doble armónica (bizantina): la «misteriosa» del psytrance. Como el frigio dominante con séptima mayor; acordes limpios I, ♭II, iii e iv: pocas variaciones.",
};
const ACORDES = [["quintas","Quintas abiertas"],["sus2","Sus2"],["menor_add9","Menor add9 (de la escala)"],["triada","Tríada"],["cluster","Cluster suave"],["septima","Séptima (m7 / maj7)"],["novena","Novena (con 5 voces)"]];
// Escala equivalente en la Circuit (botón Scales): [escala de la Circuit, semitonos a sumar a la tónica].
// Frigio dominante = menor armónica una quinta abajo; lidia = mayor una quinta arriba (mismas notas).
const ESCALA_CIRCUIT = {frigio: ["Phrygian", 0], menor_armonica: ["Harmonic Minor", 0], frigio_dominante: ["Harmonic Minor", 5],
  menor: ["Natural Minor", 0], hungara_menor: ["Hungarian Minor", 0], dorico: ["Dorian", 0], lidio: ["Major", 7], doble_armonica: ["Hungarian Minor", 5]};
const ESCALAS = [["frigio","Frigio"],["menor_armonica","Menor armónica"],["frigio_dominante","Frigio dominante"],["menor","Menor natural"],["hungara_menor","Húngara menor"],["dorico","Dórica"],["lidio","Lidia"],["doble_armonica","Doble armónica"]];
const GENEROS = [["goa","Goa"],["psytrance","Psytrance"],["psy_chill","Psy chill"],["chillgressive","Chillgressive"],["chillout","Chillout"],["ambient","Ambient"]];
const GENERO_TEXTO = {goa: "Frigio, i – ♭II, llamada y respuesta en corcheas, pegada al beat.",
  psytrance: "Frigio, i – ♭II cada 16 compases, riffs con huecos para el bombo, notas cortas y bajo rolling.",
  psy_chill: "Dórica, i – IV – i – ♭VII con pulso suave en los pads, motivos cortos.",
  chillgressive: "Menor, i – ♭VI – ♭VII – v cada 8 compases, diálogo en semicorcheas.",
  chillout: "Menor, acordes de séptima y novena juntos, notas largas y algo de swing.",
  ambient: "Lidia, drone y acordes que duran 16 compases, voces que entran de a una, mucho espacio."};
const nombreGenero = (g) => (GENEROS.find((x) => x[0] === g) || [g, g])[1];
function desplTexto(x) {
  const t = x === 0 ? "pegado al beat" : x < 0.35 ? "casi pegado" : x < 0.7 ? "algo desplazado" : "desplazado";
  return x === 0 ? t : `${t} (${Math.round(x * 100)} %)`;
}
const ESTILOS = [["rolling","Rolling"],["galope","Galope"],["arpegio3","Arpegio 3"],["acido","Ácido 303"],
  ["psy_chill","Psy chill"],["euclidiano","Euclidiano"],["largas","Notas largas"],["ambient","Ambient"],["clasico","Goa clásico"],["psytrance","Psytrance"]];
const POSICIONES = [["onbeat","Con el bombo"],["offbeat","Entre bombos"],["todos","Todas"],["desplazado","Corrida"]];
const POS_TEXTO = {onbeat: "Las notas caen junto al bombo.", offbeat: "Entre bombo y bombo: el clásico del psytrance.",
  todos: "Todas las semicorcheas.", desplazado: "Corrida una semicorchea: sensación de tropiezo."};
const RELACIONES = [["unisono","La nota larga"],["tercera","Su tercera"],["quinta","Su quinta"],["octava","Octava arriba"]];
const FASES = {llamada: "Llamando", respuesta: "Respondiendo", conversando: "Conversando", escuchando: "Escuchándote"};
const FORMAS_TEXTO = {entrelazado: "La respuesta toca solo en los huecos que deja la llamada, en el mismo compás.",
  turnos: "La llamada toca unos compases y después contesta la respuesta."};
const ESTILOS_BAJO = [["sincopado","Sincopado","· · B B · · B ·"],["rolling","Rolling","K B B B"],["fullon","Full-on","K B B B ♪"],["tresillo","Tresillo","K ³B B"],
  ["galope","Galope","K · B B"],["saltado","Saltado","K B · B"],["offbeat","Offbeat","K · B ·"],
  ["chillgressive","Chillgressive","K B b B"],["trote","Trote 3-3-2","· B · B · · B ·"],["dub","Dub","B · · b"],["sub","Sub","B — —"]];
const LFO_FORMAS = [["seno","Seno"],["triangulo","Triángulo"],["azar","Al azar"],["sube","Sube"],["baja","Baja"]];
const LFO_CICLOS = [["0.25","1 tiempo"],["0.5","2 tiempos"],["1","1 compás"],["2","2 compases"],["4","4 compases"],["8","8 compases"],["16","16 compases"],["32","32 compases"]];
const TEXTO_BAJO = {rolling: "Bombo, bajo, bajo, bajo: el rolling clásico del Goa y el full-on.",
  fullon: "Rolling con una celda melódica por tiempo (raíz, quinta, octava y el ♭2 en frigio).",
  tresillo: "Bombo y dos notas en tresillo: un balanceo más oscuro, muy Goa de los 90.",
  galope: "Bombo, silencio, bajo, bajo: el galope, más espaciado.",
  saltado: "Bombo, bajo, silencio, bajo: rolling con aire, minimal.",
  offbeat: "Una corchea a contratiempo: el bajo del progressive y del psy chill.",
  chillgressive: "Rolling oscuro, notas cortas y un acento que se mueve por la frase.",
  sincopado: "Progresivo: lejos del bombo, notas largas en la «y» y la «a» del tiempo, cambia de nota con el acorde.",
  trote: "Grupos de 3+3+2 entre los bombos (packs Progressive y Apex): una síncopa que avanza y nunca cae en el bombo.",
  dub: "En el uno, antes del tres y en el tres: notas largas y mucho silencio.",
  sub: "Una nota grave por acorde, ligada: casi un drone."};

let cfg = null, temporizador = null, uid = 0, ultimoEstado = null;
const $ = (id) => document.getElementById(id);
const leerLocal = (k, d) => { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } };
const escribirLocal = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };

function el(tag, props = {}, hijos = []) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "style") e.style.cssText = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (k in e && k !== "list") e[k] = v; else e.setAttribute(k, v);
  }
  for (const h of [].concat(hijos)) if (h != null && h !== false) e.append(h);
  return e;
}

function avisoDeshacer(texto, deshacerFn) {
  // En vez de preguntar antes: lo hace, y el aviso trae «Deshacer» por unos segundos.
  const a = $("aviso");
  const b = el("button", {type: "button", className: "aviso-deshacer", textContent: "Deshacer", onclick: async () => {
    a.className = "guardado"; try { await deshacerFn(); aviso("Deshecho"); } catch (e) { aviso(e.message, true); } }});
  a.replaceChildren(el("span", {textContent: texto}), b);
  a.className = "guardado ver accion";
  clearTimeout(a._t);
  a._t = setTimeout(() => a.className = "guardado", 6000);
}
const deshacerUltimo = async () => { await enviarPendiente(); await api("/api/deshacer", {}); await recargar(); estado(); };
const fotoPartes = () => JSON.parse(JSON.stringify({escena: cfg.escena, parte: cfg.parte, nombre: cfg.cancion.nombre}));
async function volverPartes(f) {
  await enviarPendiente();
  await api("/api/escena/restaurar", {escena: f.escena, parte: f.parte});
  cfg = await (await fetch("/api/config")).json();
  cfg.cancion.nombre = f.nombre; await api("/api/config", cfg);
  await recargar(); estado();
}
function aviso(texto, error = false) {
  const a = $("aviso");
  a.textContent = texto;
  a.className = "guardado ver" + (error ? " error" : "");
  clearTimeout(a._t);
  a._t = setTimeout(() => a.className = "guardado" + (error ? " error" : ""), error ? 4000 : 1200);
}

function guardar() {
  clearTimeout(temporizador);
  temporizador = setTimeout(enviarConfig, 350);
}
async function enviarConfig() {
  temporizador = null;
  try {
    const r = await fetch("/api/config", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(cfg)});
    const d = await r.json();
    if (!r.ok) { aviso(d.error || "No se pudo aplicar", true); if (r.status === 400 && /otra parte|nanoKONTROL/.test(d.error || "")) recargar(); }
    else { aviso(d.aviso || "Aplicado", !!d.aviso); $("deshacer").disabled = false; }
  } catch (e) { aviso("Sin conexión con la Pi", true); }
}
// Si hay un cambio esperando los 350 ms de guardar(), lo manda ya.
async function enviarPendiente() {
  if (temporizador) { clearTimeout(temporizador); await enviarConfig(); }
}

function segmentado(opciones, valor, alCambiar, columnas) {
  // opciones: [valor, texto] o [valor, texto, detalle chico debajo]
  const nombre = "s" + (uid++);
  const cont = el("div", {className: "seg", style: `grid-template-columns:repeat(${columnas},minmax(0,1fr))`});
  for (const [v, texto, detalle] of opciones) {
    const id = nombre + v;
    cont.append(el("input", {type: "radio", name: nombre, id, value: v, checked: v === valor, onchange: () => alCambiar(v)}),
                el("label", {htmlFor: id}, [texto, detalle ? el("small", {textContent: detalle}) : null]));
  }
  return cont;
}

function campo(texto, control) {
  return el("div", {style: "display:flex;flex-direction:column;gap:6px;font-size:13px;color:var(--txt2)"}, [texto, control]);
}

function deslizador(s, k, texto, min, max, paso, formato, alSoltar) {
  const valor = el("span", {textContent: formato(s[k]), style: "color:var(--mut)"});
  const r = el("input", {type: "range", min, max, step: paso, value: s[k], "aria-label": texto,
    oninput: () => { s[k] = parseFloat(r.value); valor.textContent = formato(s[k]); guardar(); },
    onchange: () => { if (alSoltar) alSoltar(); }});
  return el("label", {className: "campo"}, [el("span", {className: "fila", style: "gap:8px"}, [el("b", {textContent: texto, style: "font-weight:600"}), valor]), r]);
}

function colorTexto(x) {
  const nombre = x < 0.15 ? "luminoso" : x < 0.5 ? "claro" : x < 0.85 ? "oscuro" : "ultra oscuro";
  return `${nombre} (${Math.round(x * 100)} %)`;
}

function seedNueva() {
  const hex = () => Math.floor(Math.random() * 65536).toString(16).toUpperCase().padStart(4, "0");
  return hex() + "-" + hex();
}

function recordar(det, clave, porDefecto) {
  // Cada grupo se acuerda de si lo dejaste abierto o cerrado (en este teléfono).
  const g = leerLocal("abierto:" + clave, null);
  det.open = g === null ? porDefecto : g === "1";
  det.addEventListener("toggle", () => escribirLocal("abierto:" + clave, det.open ? "1" : "0"));
  return det;
}

function grupo(clave, nombre, resumen, hijos) {
  // Un grupo de «más ajustes»: cerrado muestra su nombre y un resumen de lo que tiene adentro.
  return recordar(el("details", {className: "grupo"}, [
    el("summary", {}, [el("span", {className: "cab"}, [el("b", {textContent: nombre}), el("span", {textContent: resumen})])]),
    el("div", {className: "cuerpo"}, hijos.filter(Boolean)),
  ]), clave, false);
}

function ayuda(texto) {
  return el("p", {className: "ayuda", textContent: texto});
}

function porcentaje(v) { return Math.round(v * 100) + " %"; }

function numeroDe(obj, k, etiqueta, min, max, alCambiar) {
  const inp = el("input", {type: "number", min, max, value: obj[k],
    onchange: () => { const n = parseInt(inp.value); obj[k] = isNaN(n) ? obj[k] : Math.max(min, Math.min(max, n)); inp.value = obj[k]; if (alCambiar) alCambiar(); guardar(); }});
  return el("label", {className: "campo"}, [etiqueta, inp]);
}

function numeroDecimal(obj, k, etiqueta, min, max, paso, alCambiar) {
  const inp = el("input", {type: "number", min, max, step: paso, value: obj[k], inputMode: "decimal",
    onchange: () => { const n = parseFloat(String(inp.value).replace(",", ".")); obj[k] = isNaN(n) ? obj[k] : Math.max(min, Math.min(max, n)); inp.value = obj[k]; if (alCambiar) alCambiar(); guardar(); }});
  return el("label", {className: "campo"}, [etiqueta, inp]);
}

function programaDe(obj) {
  return el("div", {style: "display:flex;flex-direction:column;gap:4px"}, [
    numeroDe(obj, "programa", "Parche (Program Change, 0 = no cambia)", 0, 128),
    ayuda("Le pide ese parche al sinte al dar Play y cada vez que una escena o una parte de la canción lo cambia (en su primer compás). Se guarda en las escenas."),
  ]);
}

// --- Elegir puerto MIDI ---
// Un menú con los puertos que ve la Pi ahora mismo (se actualiza solo al conectar
// o desconectar algo). El puerto elegido sigue en la lista aunque esté
// desconectado, y "Otro nombre…" deja escribirlo a mano.
const selectoresPuerto = [];

function puertoSelect(tipo, actual, alElegir) {
  const sel = el("select", {});
  const otro = el("input", {type: "text", placeholder: "Parte del nombre, p. ej. FM-1", style: "display:none;margin-top:6px"});
  const caja = el("div", {}, [sel, otro]);
  const info = {sel, tipo, actual};
  info.pintar = () => {
    if (document.activeElement === sel) return;  // no cambiarle las opciones mientras lo usas
    const lista = (ultimoEstado && ultimoEstado[tipo === "entrada" ? "entradas" : "disponibles"]) || [];
    const conectado = (n) => lista.some((x) => x.toLowerCase().includes(n.toLowerCase()));
    const opciones = [...lista];
    if (info.actual && !conectado(info.actual)) opciones.push(info.actual);
    const firma = JSON.stringify([opciones, info.actual, lista]);
    if (sel.dataset.firma === firma) return;
    sel.dataset.firma = firma;
    sel.replaceChildren();
    for (const n of opciones) {
      const texto = conectado(n) ? n : `${n} (desconectado)`;
      sel.append(el("option", {value: n, textContent: texto}));
    }
    sel.append(el("option", {value: "\u0000otro", textContent: "Otro nombre…"}));
    // El valor guardado puede ser parte del nombre ("CH345" de "USB2.0-MIDI CH345"): se marca el que lo contiene.
    const elegido = opciones.find((n) => n === info.actual)
      || opciones.find((n) => n.toLowerCase().includes((info.actual || "").toLowerCase()));
    sel.value = elegido !== undefined ? elegido : "\u0000otro";
  };
  sel.onchange = () => {
    if (sel.value === "\u0000otro") { otro.style.display = ""; otro.value = info.actual || ""; otro.focus(); return; }
    otro.style.display = "none";
    info.actual = sel.value; alElegir(sel.value);
  };
  otro.onchange = () => {
    const v = otro.value.trim(); if (!v) return;
    otro.style.display = "none"; info.actual = v; sel.dataset.firma = ""; info.pintar(); alElegir(v);
  };
  selectoresPuerto.push(info);
  info.pintar();
  return caja;
}

function pintarPuertos() {
  for (let i = selectoresPuerto.length - 1; i >= 0; i--) {
    if (!selectoresPuerto[i].sel.isConnected) selectoresPuerto.splice(i, 1);  // de un render anterior
    else selectoresPuerto[i].pintar();
  }
}

function destinoDe(obj, alCambiar) {
  return el("label", {className: "campo"}, ["Destino (puerto)",
    puertoSelect("salida", obj.salida, (v) => { obj.salida = v; if (alCambiar) alCambiar(); guardar(); })]);
}

function casilla(obj, k, titulo, detalle, alCambiar) {
  const chk = el("input", {type: "checkbox", checked: !!obj[k], onchange: () => { obj[k] = chk.checked; if (alCambiar) alCambiar(); guardar(); }});
  return el("label", {className: "fila", style: "min-height:44px"}, [el("span", {}, [titulo, detalle ? el("br") : null, detalle ? el("span", {className: "mut", textContent: detalle}) : null]), chk]);
}

function armoniaPropia(obj, alCambiar) {
  // Cada motor usa la armonía general (en Armonía) o una propia.
  const general = cfg.musica.armonia === "guiada" ? "Guiada" : "Libre";
  return campo("Armonía", segmentado([["general", `General (${general})`],["guiada","Guiada"],["libre","Libre"]], obj.armonia || "general",
    (v) => { obj.armonia = v; if (alCambiar) alCambiar(); guardar(); }, 3));
}

function guiadaDe(obj) {
  return (obj.armonia && obj.armonia !== "general" ? obj.armonia : cfg.musica.armonia) === "guiada";
}

async function cambiarGenero(genero, motor = {}) {
  // motor: {} = todo · {parte: "pads"} · {parte: "dialogo"} · {parte: "bajo"} · {parte: "secuencia", indice}
  const nombres = {pads: "Pads", bajo: "Bajo", dialogo: "Diálogo", fx: "FX", secuencia: `Secuencia ${(cfg.secuencia[motor.indice] || {}).nombre}`};
  try {
    clearTimeout(temporizador);  // primero aplica lo último que cambiaste
    await api("/api/config", cfg);
    await api("/api/genero", Object.assign({genero}, motor));
    await recargar();
    aviso((motor.parte ? nombres[motor.parte] + ": " : "Todo en ") + nombreGenero(genero));
  } catch (e) { aviso(e.message, true); }
}

// --- Navegación ---

// La app nueva parte en Tema (la línea de tiempo); una sola vez, también para quien ya tenía otra guardada.
let vista = leerLocal("vista_v2", null) === null ? "cancion" : leerLocal("vista", "cancion");
escribirLocal("vista_v2", 1);
// Tablet horizontal (pantalla ancha): Tocar queda siempre a la izquierda y las pestañas eligen
// lo de la derecha. Se elige solo por el ancho; en el teléfono todo sigue igual.
const ancha = window.matchMedia("(min-width: 1000px)");
const dosColumnas = () => false;   // (la app nueva usa una columna también en pantalla ancha)
const tocarVisible = () => vista === "tocar" || dosColumnas();
function mostrar(v) {
  vista = v; escribirLocal("vista", v);
  const derecha = dosColumnas() && v === "tocar" ? "motores" : v;
  for (const s of document.querySelectorAll(".vista")) s.hidden = s.id !== "v-" + derecha;
  // Parte y sus motores son parte de Tema. Armonía es su propia pestaña, salvo si la abriste desde una parte.
  const pestana = ["parte", "motores"].includes(derecha) || (derecha === "armonia" && armoniaDesdeParte) ? "cancion" : derecha;
  for (const b of document.querySelectorAll("nav.tabs button")) b.setAttribute("aria-selected", b.dataset.vista === pestana ? "true" : "false");
  if (cfg && (derecha === "motores" || derecha === "armonia")) pintarVolver();
  if (cfg && derecha === "parte") renderParte();
  if (dosColumnas() && cfg) { renderTocar(); if (derecha === "motores") renderMotores(); }
  window.scrollTo(0, 0);
}
let armoniaDesdeParte = false;   // true: se abrió desde una parte (edita esa parte, con «‹ volver»)
document.querySelectorAll("nav.tabs button").forEach((b) => b.onclick = () => {
  if (b.dataset.vista === "armonia") { armoniaDesdeParte = false; mostrar("armonia"); renderArmonia(); }
  else mostrar(b.dataset.vista);
});
ancha.addEventListener("change", () => mostrar(vista));

