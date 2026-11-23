# Rediseño del editor de secuencia · etapa 2: inventario

Las 74 claves de `ESQUEMA_SECUENCIA`, dónde están hoy y dónde van. Regla: **mismo tipo de
control y rango completo del motor**. Ninguna opción se recorta. Un control que depende de otro
solo se oculta cuando no tiene ningún efecto.

Leyenda: % = deslizador 0–100 %, n = número con − / +, seg = botones segmentados, sw = interruptor.

## Cabecera
- `activa` sw · franja «Lo que toca ahora» · ⟲ fábrica

## 1. Estilo (sección abierta, plegable, con ‹ ›)
- `estilo` seg 10, por familia: **Rodantes** rolling, galope, arpegio3, acido · **Con frase** clasico, psytrance ·
  **Con aire** psy_chill, euclidiano · **Lentos** largas, ambient. (Hoy se ven solo los del género de la secuencia.)
  Al elegir largas/ambient/clasico/psytrance se pone `posicion = todos`, como hoy.
- Solo con **Goa clásico**: `figura` seg 4 (auto, pedal, ciclo, acordes) · `frase` seg 2/4 · `remate` % ·
  `variar` % (1–4 respuestas) · con ciclo o auto: `ciclo` seg (seed, 3, 5, 6, 7 = todos los que usa el
  generador, `CICLOS`) y `registro` seg 1–3.
- Solo con **Psytrance**: `figura` seg 12 · `huecos` % · `frase` seg 2/4 · `remate` % · `variar` %.

## 2. Variante (siempre a la vista)
- `seed`: Otra · ‹ · ★ (A/B, `varianteAB`) · escrita a mano (texto).
- Clips: pestaña chica «Clip: X ▾» / «Sin clip» (etapa 3).

## 3. Más o menos notas
- `densidad` % · `posicion` seg 4 + texto · `largo` **n 2–64** + atajos 16/13/11/7 (no en estilos con frase) ·
  `gate` 5–100 % · `gate_random` % · `largas` %.
- Filtro y orden: `filtro` sw → molde (pincel, pasos, presets, 🎲 goa/psy = `molde_estilo`), `molde_prob` % (si hay ?),
  `molde_muta` % · `recorrido` seg 4 (siempre).

## 4. Que cambie solo
- `mutacion` % · `mutacion_ritmo` % · `mutar_cada` **n 1–64**, visible si mutación de notas, de ritmo o
  `molde_muta` > 0 (los tres lo usan) · `bloqueada` sw.

## 5. Groove
- `swing` 0–100 % (motor 0–0,5) · `acentos` % · `velocidad` n 1–127 · `acento` n 1–127 · `vel_random` % ·
  `repeticion` (Redobles) %.
- Con la otra voz (no en la primera): `corrimiento` 0–15 · `complementar` % · `separar` sw.

## 6. Altura
- `octava` −3…+3 · `relacion` seg 4 · `saltos` % · `slide` % · `pedal` % · `deslices` % · `doble` seg 6 ·
  `techo` **36–127** · `semitono` % · `escala_color` seg 4 · `raga` seg 6 → `ornamentos` %, `bend_rango` n 0–24 ·
  `armonia` seg 3 (general/guiada/libre).

## 7. Sonido del sinte
- `cc_filtro` n 0–127 y `filtro_reposo` n 0–127 (una sola vez; hoy salen en dos grupos).
- `subida_filtro` sw → `subida_desde`, `subida_hasta`, `subida_despues`.
- `lfo`, `lfo2` sw → `_cc` (por sinte + otro CC 0–127), `_forma` seg 5, `_compases` (atajos de 1 tiempo a 32
  compases **+ número libre 0,25–32**), `_min`, `_max`.
- `fx` sw (la interviene el FX) → `subida_hasta` si no hay subida propia.

## 8. Salida MIDI
- `nombre` (12) · `salida` · `canal` 1–16 · `disparo` 0–16 · `programa` · Eliminar · Copiar a otras partes.

## Sale
- `genero` de la secuencia: el motor no lo lee (solo filtraba la lista de estilos). La clave queda en el
  esquema por compatibilidad. «Cambiar género» de todo el tema sigue en Ajustes.

## Hoy ya recortados (se abren en la etapa 3)
- `largo`: el motor acepta 2–64 (probado en los 8 estilos sin frase); la app solo da 16/13/11/7.
- `techo`: el motor acepta 36–127; la app parte en 60.
- `lfo_compases` / `lfo2_compases`: el motor acepta cualquier valor 0,25–32; la app da 8 fijos.
