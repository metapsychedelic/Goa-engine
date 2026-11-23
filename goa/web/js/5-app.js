// Yantra · Actualización, temas, estado y arranque (va última: usa todo lo anterior).
// Scripts clásicos en orden: comparten el ámbito global con los demás archivos de js/.
// --- Actualización ---
let versionActual = null;
async function buscarActualizacion(buscar) {
  const est = $("act_estado"), lista = $("act_cambios");
  if (buscar) { est.textContent = "Buscando en GitHub…"; $("act_buscar").disabled = true; }
  let d;
  try { d = await (await fetch("/api/actualizacion" + (buscar ? "?buscar=1" : ""))).json(); }
  catch (e) { est.textContent = "No pude preguntarle al motor."; $("act_buscar").disabled = false; return; }
  $("act_buscar").disabled = false;
  if (!d.git) { est.textContent = "Esta instalación no viene de GitHub: se actualiza a mano."; $("act_buscar").hidden = true; return; }
  versionActual = d.version;
  $("act_anterior").hidden = !d.hay_anterior;
  lista.hidden = true; $("act_instalar").hidden = true;
  if (d.error) { est.textContent = `Tienes la ${d.version}. ${d.error}`; return; }
  if (!buscar) { est.textContent = d.en_anterior ? `Estás en una versión anterior (${d.version}). «Buscar actualización» te lleva a la última.` : `Tienes la versión ${d.version}.`; return; }
  if (d.hay_nueva) {
    est.textContent = d.version_nueva !== d.version ? `Hay una versión nueva: ${d.version_nueva} (tienes la ${d.version}).` : `Hay cambios nuevos en la ${d.version_nueva}.`;
    lista.replaceChildren(...d.cambios.map((c) => el("li", {textContent: c.split("\n")[0]})));
    lista.hidden = !d.cambios.length;
    $("act_instalar").hidden = false;
    $("act_instalar").textContent = d.servicio ? "Actualizar y reiniciar" : "Actualizar";
  } else {
    est.textContent = `Tienes la última versión (${d.version}).`;
  }
}
async function cambiarVersion(ruta, pregunta) {
  if (!confirm(pregunta)) return;
  const est = $("act_estado");
  for (const b of ["act_buscar", "act_instalar", "act_anterior"]) $(b).disabled = true;
  est.textContent = ruta.endsWith("anterior") ? "Volviendo a la versión anterior…" : "Bajando la versión nueva y probándola con tu configuración…";
  try {
    const d = await api(ruta);
    if (!d.reinicia) {
      await buscarActualizacion(false);
      est.textContent = d.cambio === false ? `Ya tenías la última versión (${d.version}).`
        : `Quedó la versión ${d.version}. Reinicia el motor para usarla (goa-restart).`;
    } else {
      est.textContent = `Instalada la ${d.version}. Reiniciando el motor…`;
      if (d.instalar) aviso("Esta versión cambia la instalación: cuando puedas, corre ./install.sh en la Pi", true);
      await esperarReinicio(d.version);
      return;
    }
  } catch (e) { est.textContent = e.message; }
  for (const b of ["act_buscar", "act_instalar", "act_anterior"]) $(b).disabled = false;
}
async function esperarReinicio(version) {
  // El motor se apaga y systemd lo levanta: espera a que conteste un proceso nuevo
  // (otro «inicio») y recarga la página (la app también puede haber cambiado).
  let antes = null;
  try { antes = (await (await fetch("/api/estado", {cache: "no-store"})).json()).inicio; } catch (e) { /* ya se apagó */ }
  await new Promise((r) => setTimeout(r, 2500));
  for (let k = 0; k < 60; k++) {
    try {
      const d = await (await fetch("/api/estado", {cache: "no-store"})).json();
      if (d.inicio !== antes) { location.reload(); return; }
    } catch (e) { /* todavía arrancando */ }
    await new Promise((r) => setTimeout(r, 1000));
  }
  $("act_estado").textContent = "El motor tarda en volver. Recarga la página en un rato; si no vuelve, revisa con goa-log en la Pi.";
}
$("act_buscar").onclick = () => buscarActualizacion(true);
$("act_instalar").onclick = () => cambiarVersion("/api/actualizar",
  "¿Actualizar ahora? El motor se reinicia y el sonido se corta unos segundos.");
$("act_anterior").onclick = () => cambiarVersion("/api/actualizar/anterior",
  "¿Volver a la versión anterior? El motor se reinicia y el sonido se corta unos segundos.");
buscarActualizacion(false);

async function recargar() {
  cfg = await (await fetch("/api/config")).json();
  render();
}

async function guardarProyecto(nombre, nuevo) {
  try {
    let r;
    try { r = await api("/api/proyecto/guardar", {nombre, nuevo}); }
    catch (e) {
      if (!/Ya hay un proyecto/.test(e.message)) throw e;
      if (!confirm(`Ya hay un proyecto «${nombre}». ¿Reemplazarlo con lo que suena ahora?`)) return;
      r = await api("/api/proyecto/guardar", {nombre, nuevo, sobrescribir: true});
    }
    await recargar(); pintarProyecto(true); aviso(r.aviso || "Proyecto guardado", !!r.aviso);
  } catch (e) { aviso("No se guardó: " + e.message, true); }
}
function pintarProyecto(alDia) {
  const p = $("proyecto_estado");
  if (!cfg || !cfg.app.proyecto) { p.textContent = "sin guardar"; p.className = "pill mal"; return; }
  p.textContent = alDia ? "guardado" : (cfg.app.autoguardar ? "guardando…" : "cambios sin guardar");
  p.className = alDia ? "pill ok" : "pill mal";
}
$("proyecto_guardar").onclick = async () => {
  let nombre = cfg.app.proyecto, nuevo = false;
  if (!nombre) { nombre = prompt("Nombre del proyecto"); if (!nombre) return; nuevo = true; }
  await guardarProyecto(nombre, nuevo);
};
$("proyecto_guardar_como").onclick = async () => {
  const nombre = prompt("Nombre del proyecto nuevo", cfg.app.proyecto || ""); if (!nombre) return;
  await guardarProyecto(nombre, nombre.trim() !== (cfg.app.proyecto || ""));
};
$("proyecto_auto").onchange = (e) => { cfg.app.autoguardar = e.target.checked; guardar(); };
$("proyecto_abrir").onclick = async () => {
  const lista = $("proyecto_lista");
  if (lista.style.display === "flex") { lista.style.display = "none"; return; }
  const d = await (await fetch("/api/proyectos")).json();
  lista.innerHTML = "";
  if (!d.proyectos.length) lista.append(el("p", {className: "mut", style: "margin:0", textContent: "Todavía no hay proyectos guardados."}));
  for (const p of d.proyectos) {
    lista.append(el("div", {className: "fila"}, [
      el("button", {textContent: p.nombre, style: "flex:1;text-align:left", onclick: async () => {
        if (!cfg.app.proyecto && !confirm(`Lo que suena ahora no está guardado en ningún tema. ¿Abrir ${p.nombre} igual?`)) return;
        await enviarPendiente();
        try { await api("/api/proyecto/abrir", {nombre: p.archivo}); lista.style.display = "none"; await recargar(); aviso("Proyecto abierto"); }
        catch (e) { aviso(e.message, true); } }}),
      el("button", {textContent: "Borrar", "aria-label": `Borrar ${p.nombre}`, style: "color:var(--bad)", onclick: async () => {
        if (!confirm(`¿Borrar el proyecto ${p.nombre}? No se puede deshacer.`)) return;
        try { await api("/api/proyecto/borrar", {nombre: p.archivo}); $("proyecto_abrir").click(); $("proyecto_abrir").click(); }
        catch (e) { aviso(e.message, true); } }}),
    ]));
  }
  lista.style.display = "flex";
};

// --- Temas: la lista al tocar el nombre en la cabecera, y la bienvenida ---
function nombreTema() { return (cfg && (cfg.app.proyecto || "")) || ""; }
function pintarTemaCab() {
  const n = $("tema_cab_nombre");
  if (n && cfg) n.textContent = nombreTema() || "Sin guardar · toca para elegir";
}
async function abrirTema(p) {
  if (!cfg.app.proyecto && !confirm(`Lo que suena ahora no está guardado en ningún tema. ¿Abrir ${p.nombre} igual?`)) return false;
  await enviarPendiente();
  try { await api("/api/proyecto/abrir", {nombre: p.archivo}); await recargar(); aviso(`${p.nombre} abierto`); return true; }
  catch (e) { aviso(e.message, true); return false; }
}
async function hojaTemas() {
  let lista = [];
  try { lista = (await (await fetch("/api/proyectos")).json()).proyectos; } catch (e) {}
  const actual = nombreTema();
  const bpm = bpmCancion();
  let d;
  d = hoja("Tus temas", actual ? `Abierto: ${actual}` : "Lo que suena ahora no está guardado", [
    lista.length ? el("div", {className: "motores-lista", style: "max-height:50vh;overflow:auto;margin-bottom:12px"}, lista.map((p) => {
      const abierto = p.nombre === actual;
      return el("button", {type: "button", style: abierto ? "background:var(--accbg)" : "", onclick: async () => { if (abierto) { d.close(); return; } if (await abrirTema(p)) d.close(); }}, [
        el("span", {style: "flex:1;min-width:0"}, [p.nombre, el("br"), el("span", {className: "mut", style: "font-size:12px",
          textContent: p.partes ? `${p.partes} parte${p.partes === 1 ? "" : "s"} · ${duracionTexto(p.compases, bpm)}` : "sin partes"})]),
        abierto ? el("span", {className: "pill ok", textContent: "abierto"}) : el("span", {className: "mut", textContent: "›"})]);
    })) : el("p", {className: "mut", textContent: "Todavía no hay temas guardados."}),
    el("p", {className: "ayuda", style: "margin:0 0 12px", textContent: "Cada tema se guarda solo mientras lo editas. Al abrir otro, lo último que cambiaste queda en el que cierras."}),
    el("div", {className: "acciones"}, [
      el("button", {type: "button", className: "prim", textContent: "+ Nuevo tema", onclick: () => { d.close(); bienvenida(false); }}),
      el("button", {type: "button", textContent: "Duplicar este", disabled: !actual, onclick: async () => {
        const nombre = prompt("Nombre de la copia", `Copia de ${actual}`); if (!nombre) return;
        d.close(); await guardarProyecto(nombre.trim(), true); }}),
    ]),
  ]);
}
async function nuevoTema(clave, nombreSugerido) {
  const nombre = prompt("Nombre del tema nuevo", nombreSugerido);
  if (!nombre || !nombre.trim()) return false;
  await enviarPendiente();
  // Primero el tema nuevo con su nombre (el de antes queda con su último cambio), después las partes.
  try {
    let r;
    try { r = await api("/api/proyecto/guardar", {nombre: nombre.trim(), nuevo: true}); }
    catch (e) {
      if (!/Ya hay un proyecto/.test(e.message)) throw e;
      if (!confirm(`Ya hay un tema «${nombre.trim()}». ¿Reemplazarlo?`)) return false;
      r = await api("/api/proyecto/guardar", {nombre: nombre.trim(), nuevo: true, sobrescribir: true});
    }
    await api("/api/cancion/plantilla", {clave, nuevo: true});
    await recargar(); escribirLocal("bienvenida", 1);
    mostrar("cancion"); aviso(`${nombre.trim()}: listo para armar`);
    return true;
  } catch (e) { aviso(e.message, true); return false; }
}
async function bienvenida(primeraVez) {
  let plantillas = [];
  try { plantillas = (await (await fetch("/api/plantillas")).json()).plantillas; } catch (e) {}
  const mini = (energias) => {
    const total = energias.reduce((n, x) => n + x[0], 0) || 1;
    return el("span", {className: "plantilla-mini", "aria-hidden": "true"}, energias.map(([c, e]) =>
      el("i", {style: `flex:${c} 1 0;height:${Math.round(15 + 85 * e)}%;opacity:${(0.35 + 0.65 * e).toFixed(2)}`})));
  };
  const opcion = (nombre, info, extra, fn) => el("button", {type: "button", onclick: fn}, [extra || el("span", {className: "plantilla-mini", style: "background:none;border:1px dashed var(--line2)"}),
    el("span", {style: "flex:1;min-width:0"}, [nombre, el("br"), el("span", {className: "mut", style: "font-size:12px", textContent: info})])]);
  let d;
  const limpio = (n) => n.split(" · slot")[0];
  d = hoja(primeraVez ? "Bienvenido a Yantra" : "Nuevo tema", null, [
    el("div", {className: "bienvenida"}, [el("p", {className: "lema", textContent: "Arma un tema por partes. Yantra lo toca con tus máquinas, siguiendo a la Circuit."})]),
    h3("Empezar desde"),
    el("div", {className: "motores-lista", style: "max-height:52vh;overflow:auto;margin-bottom:12px"}, [
      ...plantillas.map((p) => opcion(limpio(p.nombre), `${p.bpm} BPM · ${p.partes} partes · ${duracionTexto(p.compases, p.bpm)}`, mini(p.energias || []),
        async () => { if (await nuevoTema(p.clave, limpio(p.nombre))) d.close(); })),
      opcion("En blanco", "Una parte de 16 compases y lo que suena ahora", null, async () => { if (await nuevoTema("blanco", "Tema nuevo")) d.close(); }),
    ]),
    el("div", {className: "acciones"}, [
      el("button", {type: "button", textContent: "Abrir un tema guardado", onclick: () => { d.close(); escribirLocal("bienvenida", 1); hojaTemas(); }}),
      el("button", {type: "button", textContent: primeraVez ? "Ahora no" : "Cancelar", onclick: () => { escribirLocal("bienvenida", 1); d.close(); }}),
    ]),
  ]);
}
$("tema_cab").onclick = () => hojaTemas();

async function estado() {
  try {
    const d = await (await fetch("/api/estado")).json();
    ultimoEstado = d;
    const p = $("pill");
    if (!d.entrada) { p.textContent = "Sin Circuit"; p.className = "pill mal"; }
    else if (d.corriendo) { p.textContent = "Sonando"; p.className = "pill ok"; }
    else { p.textContent = "Detenido"; p.className = "pill"; }
    const ton = cfg ? `${cfg.musica.tonica} ${(ESCALAS.find((e) => e[0] === cfg.musica.escala) || ["", ""])[1].toLowerCase()}` : "";
    const partes = [d.bpm ? Math.round(d.bpm) + " BPM" : null, d.compas ? `compás ${d.compas}` : null, d.raiz ? `nota ${d.raiz}` : null, ton,
      d.cambios_en_cola ? "cambios al próximo compás" : null].filter(Boolean);
    $("sub").textContent = partes.join(" · ") || "Esperando la Circuit";
    $("ver").textContent = "Yantra v" + d.version;
    $("deshacer").disabled = !d.deshacer;
    pintarProyecto(d.proyecto_al_dia);
    pintarTemaCab();
    pintarEdicion(d.editando);
    marcarCambios();
    refrescarLinea();
    $("acorde").textContent = d.acorde ? "Acorde: " + d.acorde : "Sin acorde";
    const azar = document.getElementById("prog_azar");
    if (azar) azar.textContent = d.progresion || "";
    $("dialogo_linea").textContent = d.dialogo ? "Diálogo: " + (FASES[d.dialogo] || "en silencio") : "";
    const fase = $("dialogo_fase");
    if (fase) { fase.textContent = FASES[d.dialogo] || "En silencio"; fase.className = "pill" + (d.dialogo && d.dialogo !== "espacio" ? " ok" : ""); }
    pintarClips(); pintarMutes();
    if (typeof pintarTocar === "function") pintarTocar(d);
    pintarSubida(d);
    const fg = document.getElementById("fx_gesto");
    if (fg) { fg.textContent = d.fx_gesto ? "Último: " + (GESTO_TEXTO[d.fx_gesto] || d.fx_gesto) : "En silencio"; fg.className = "pill" + (d.fx_gesto ? " ok" : ""); }
    pintarCancion(d);
    // Modo canción: si el motor pasó a otra parte, la app muestra lo que suena ahora
    // (si estás escribiendo en un campo, espera a que termines).
    const escribiendo = document.activeElement && ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName) && document.activeElement.type !== "range";
    if (cfg && d.version_base !== undefined && d.version_base !== cfg.version_base && !escribiendo) { await recargar(); }
    // Algo cambió desde el nanoKONTROL2: la app muestra cómo quedó (salvo un cambio tuyo esperando).
    else if (cfg && d.version_externa !== undefined && d.version_externa !== cfg.version_externa && !escribiendo && !temporizador) { await recargar(); }
    pintarControl(d);
    pintarTeclado(d);
    pintarTocado(d);
    document.querySelectorAll("button.escena[data-escena]").forEach((b) => b.classList.toggle("elegida", !!d.control && d.control.escena === Number(b.dataset.escena)));
    const faltan = Object.entries(d.salidas).filter(([, ok]) => !ok).map(([k]) => k);
    $("puertos").textContent = faltan.length ? "Sin conexión: " + faltan.join(", ") : "Todas las salidas conectadas";
    document.querySelectorAll("[data-salida]").forEach((e) => {
      const usada = e.dataset.salida && e.dataset.salida in d.salidas;
      e.style.display = usada ? "" : "none";
      if (!usada) return;
      const ok = d.salidas[e.dataset.salida];
      e.textContent = ok ? "Conectada" : "Sin cable"; e.className = "pill" + (ok ? " ok" : " mal");
    });
    pintarPuertos();
  } catch (e) {
    $("pill").textContent = "Sin conexión"; $("pill").className = "pill mal";
  }
}

$("deshacer").onclick = deshacer;
$("panico").onclick = async () => {
  try { await fetch("/api/panico", {method: "POST"}); aviso("Notas apagadas"); } catch (e) { aviso("Sin conexión con la Pi", true); }
};

mostrar(["tocar", "cancion", "ajustes"].includes(vista) ? vista : "cancion");
(async () => {
  try { cfg = await (await fetch("/api/config")).json(); render(); pintarTemaCab();
    if (!cfg.app.proyecto && leerLocal("bienvenida", null) === null) bienvenida(true); }
  catch (e) { aviso("No pude cargar la configuración", true); }
  estado(); setInterval(estado, 1000);
})();

// relleno de los deslizadores: --p = porcentaje recorrido
function pintarRango(r) {
  const min = +r.min || 0, max = r.max === "" ? 100 : +r.max;
  r.style.setProperty("--p", ((+r.value - min) / ((max - min) || 1) * 100) + "%");
}
document.addEventListener("input", (e) => { if (e.target.type === "range") pintarRango(e.target); });
new MutationObserver(() => document.querySelectorAll('input[type=range]').forEach(pintarRango))
  .observe(document.body, {childList: true, subtree: true});
