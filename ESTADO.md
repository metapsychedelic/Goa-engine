# Estado del proyecto (para retomar en un chat nuevo)

Versión actual: **0.79.0** (ver `goa/__init__.py`). En la Pi se actualiza con `goa-update`.

## Qué es
Motor generativo Goa/psytrance en Raspberry Pi. La Circuit Tracks es el reloj
maestro; el motor manda pads, bajo y secuencias por MIDI a FM-1 (firmware Shrub),
MC-101, MicroFreak. App web en el celular (pestañas Tocar, Motores, Armonía,
Canción, Ajustes).

## Archivos clave
- `goa/motor.py` (el motor: reloj, notas largas, tocar secuencias, bajo, diálogo, clips)
- `goa/motor_forma.py` (parte de Motor: escenas, modo canción, subidas, drops, efectos de cada parte)
- `goa/secuencia.py` (una secuencia: patrón, molde, evolución) · `goa/disparo.py` (nota larga por canal)
- `goa/azar.py` (azar determinista con caché: mismo resultado, más rápido)
- `goa/forma.py` (energía, conductor, modo canción, roll)
- `goa/pads.py` (progresiones, acorde de tensión), `goa/escalas.py` (ESCALAS, ESCALAS_COLOR)
- `goa/config.py` (esquemas), `goa/web.py` + `goa/web/index.html` (app: el HTML; estilos en `goa/web/estilo.css` y
  el código en `goa/web/js/1-base.js` … `5-app.js`, scripts clásicos que comparten el ámbito global y se cargan en orden; `web.py` los sirve en `/app/…`)
- `goa/fx.py` (motor de FX: gestos, riser, caída, curva del filtro); la subida y la
  intervención de las secuencias están en `motor.py` (`_compas_subida`, `_glitch`, `_filtro_secuencias`)
- `goa/plantillas.py` (templates de canción de la app)
- `herramientas/circuit_cancion.py` (genera los .ncs de la Circuit; `todas carpeta/`)
- Pruebas: `python3 -m pruebas.<nombre>` (cancion, director, dialogo, en_vivo,
  escenas, piloto, progresiones, bajo, generos, armonia, mutaciones, thru, simular, clasico, psytrance, carpeta, fabrica, looper, control, teclado, tocado).
  App simulada: `python3 -m pruebas.app` en localhost:8080.

## Hecho recientemente

- **0.87.0 · Rediseño, etapa 3: editor de secuencia por intención.** `panelSecuencia` (2-motores.js) = cabecera + franja + **Estilo** (`bloqueEstilo`: details abierto y plegable, ‹ › recorren `ORDEN_ESTILOS`, los 10 estilos en 4 familias `FAMILIAS`; las opciones de Goa clásico / Psytrance solo con ese estilo; `elegirEstilo` pone `posicion = todos` para los de `POSICION_NECESARIA`, igual que generos.py) + **Variante** (tarjeta siempre a la vista: `varianteAB`, seed a mano plegada, pestaña «Clip: X ▾» / «Sin clip») + grupos **Más o menos notas** (densidad, dónde caen, largo 2–64 con atajos, largo y variación, sostenidas, filtro y orden), **Que cambie solo** (mutación de notas y ritmo; «Cada 1–64» solo si mutación, ritmo o `molde_muta` > 0; congelar), **Groove** (swing, acentos, fuerzas, variación, redobles %, con la otra voz), **Altura** (octava, parte desde, saltos, slides, pedal, deslices, voz doble, techo 36–127, ♭2, color, raga y sus ornamentos/bend, armonía), **Sonido del sinte** (CC del filtro y reposo una sola vez, subidas, LFO 1 y 2 con duración libre `numeroDecimal` 0,25–32, FX), **Salida MIDI**. Sin selector de género (el motor no lo leía). Inventario completo en docs/rediseno-secuencia.md. **Clips:** lista con ⋯ (Renombrar, Guardar lo que suena aquí, Borrar con Deshacer), «Agrupar por estilo» (local), «+ Guardar lo que suena» con «Incluir la variante». Clave nueva de clip `con_variante` (False: al tocarlo la secuencia conserva su seed; `config.clip_aplicado`). Endpoints: `/api/clip/guardar {fila, nombre, variante, indice?}` (con indice guarda encima), `/api/clip/renombrar`, `/api/clip/restaurar`. Se quitaron `clipsSecuencia`, `guardarClip`, `grupoMolde`. **Rendimiento:** la app va comprimida con gzip (276 → 84 KB) y cada archivo con `?v=<fecha del archivo>` y caché inmutable (el teléfono no la vuelve a bajar hasta que cambie). Prueba nueva pruebas/clips.py.
- **0.86.0 · Rediseño, etapa 1: la app en varios archivos, sin cambios visibles.** `index.html` (147 líneas) + `estilo.css` + `js/1-base.js` (constantes, utilidades, puertos, navegación), `2-motores.js` (editores de motores, clips), `3-vivo.js` (tocar, armonía, ajustes, nano, escenas), `4-tema.js` (canción, loop, línea de tiempo, partes, energía, subida), `5-app.js` (actualización, temas, arranque). `web.py` sirve `/app/<archivo>` solo .js/.css dentro de goa/web (sin caché). Nuevas pruebas de resguardo para todo el rediseño: **`pruebas/huella_sonora.py`** (graba cada mensaje MIDI en 33 escenarios: el ejemplo, todos los motores, una canción entera, cada estilo y figura, cada género; compara con `pruebas/datos/huella_sonora.json.gz`; `--grabar` solo cuando el cambio de sonido es a propósito) y **`pruebas/rendimiento.py`** (µs por pulso del reloj). Base 0.86: todos los motores ~26 µs promedio, p99 ~0,23 ms; canción ~38 µs, p99 ~0,35 ms (el pulso llega cada 17,9 ms a 140 BPM).
- **0.85.0 · Loop de partes.** `cancion.loop_desde` / `loop_hasta` (índices, -1 = sin loop). `forma.rango_loop` / `partes_en_juego`; `Conductor.parte` ubica la posición solo dentro de las partes del loop (siempre repite) y suma el índice de la primera. El loop que vale se guarda en `Conductor.cancion["loop"]` al dar Play (o al saltar): cambiarlo sonando no corre la canción, vale desde el próximo Play. Saltar a una parte fuera del loop da error. `POST /api/cancion {loop: [d, h] | null}` (la app además prende el modo canción). `_cancion_estado` trae `loop`, y total/posición del loop. App: en la tarjeta del modo canción, «Loop de partes» con desde/hasta, «Hacer loop» / «Quitar»; en la línea de tiempo las partes del loop llevan ↻ y las de afuera quedan tenues; «Ir a otra parte…» en Vivo muestra solo las del loop. Prueba en cancion.py.
- **0.84.0 · LFO en los pads y destinos por sinte.** Los pads tienen los mismos dos LFO por CC que una secuencia (`lfo*`, `lfo2*` en [pads]; `Pads.lfos`, enviados en `Motor._lfo_secuencias` por la salida y el canal de los pads cuando suenan; al cambiar la config se conserva el último valor). En la app, grupo «Filtro y sonido del sinte» en los pads. El editor de LFO (también en secuencias y Tocado) muestra destinos por sinte, de sus tablas MIDI: MC-101/FM-1 = corte 74, resonancia 71, ataque 73, release 72, wavetable 20/21 (FM-1); MicroFreak = corte 23, resonancia 83, wave 10, timbre 12, shape 13; más «Otro CC». Prueba en pruebas/lfo.py. Pendiente aparte: «Movimiento» armónico de los pads (ejemplos de audio en /tmp/pads2: mediante cromática, frigio dominante con aumentado, cuartas, línea que baja, napolitano sobre pedal, remolino; al usuario le gustaron, falta que elija).
- **0.83.0 · Limpiar y menos preguntas.** (0.83.1: «Limpiar» arriba de todo en Tema, junto a «Lo que suena ›», y «Limpiar <parte>» en la pantalla de Parte, que entra a editarla si hace falta.) Tema: botón «Limpiar» (o «Limpiar «parte»» editando) → `POST /api/limpiar`: todos los motores (MOTORES_FABRICA) y cada secuencia a fábrica y callados (`activo`/`activa` = false), con sus salidas y canales; queda en la historia (origen «limpiar»), así que Deshacer lo revierte. En vez de confirm(), las acciones avisan con «Deshacer» por 6 s (`avisoDeshacer`): fábrica, eliminar secuencia y limpiar (usan /api/deshacer); borrar escena o parte, guardar lo que suena en una parte, cargar o actualizar plantilla y descartar la edición (usan `fotoPartes` + `POST /api/escena/restaurar {escena, parte}`). Sin pregunta: borrar clips (ya es un modo borrar), editar una parte con el modo canción prendido (pasa a libre solo) y abrir otro proyecto si hay uno abierto (con autoguardado no se pierde nada). Siguen preguntando solo: borrar lo grabado del Tocado, borrar un proyecto, reemplazar un proyecto con el mismo nombre, abrir otro sin tener tema guardado y actualizar la versión.
- **0.82.0 · App nueva, etapa 6: Scatter de la MC-101 en las subidas.** Sección global `[scatter]` (salida MC-101, canal 16 = canal de control, fuerza; no va en las escenas) y por parte `scatter`, `scatter_compases` (1-32, 4), `scatter_suave` / `scatter_intenso` / `scatter_extremo` (pad 1-16, 0 = esa etapa no suena; 1 / 8 / 16). `Motor._paso_scatter` en cada paso, antes del hueco: `_scatter_pedido` según los pasos que faltan para el final de la parte (con «quedarse» y saltos incluidos) → suave desde N compases antes, intenso en los 2 últimos, extremo en los 4 últimos pasos; nota = 59 + pad. Cambiar de etapa suelta el pad anterior y aprieta el nuevo en el mismo paso; en el uno de la parte siguiente se suelta; Stop lo suelta (`_soltar_scatter`). `salidas()` abre la salida si una parte lo usa con el modo canción. App: casilla y tarjeta en «Apoyo a la subida» (compases antes y un pad por etapa) y tarjeta en Ajustes. Pruebas en cancion.py (tiempos exactos, pad en 0, Stop, saltar, quedarse a mitad). **Probar en la MC-101 que el note off apaga el Scatter.**
- **0.81.1 · Saltar de parte desde el editor** (0.82.1: con el número de parte, «‹ 3 · Build», «5 · Groove B ›» y «‹ 4 · Groove A»): en el editor de un motor (y en la Armonía) mientras editas una parte, arriba a la derecha «‹ anterior» y «siguiente ›» (`pintarVolver`): pasan a editar la parte vecina y te dejan en el mismo motor (`editarMotorEnParte(j, motorSel)`), sin volver a Tema.
- **0.81.0 · App nueva, etapa 5: Vivo, temas en la cabecera y bienvenida.** Vivo con el modo canción (`bloqueAhora` / `pintarAhoraCaja`): «Ahora» con el mapa del tema, la parte, compás x/y, tiempo y «Sigue: X en N compases · de golpe»; «Después de X»: **Quedarse 16 más** (`POST /api/cancion {quedarse: 16}` → `Motor.quedarse_parte`: `Conductor.cancion["extra"] = {inicio, fin, n, i, vuelta}`; `Conductor.parte` devuelve la parte alargada dentro de [inicio, fin) y corre lo que viene n compases; `_avanzar_cancion` lo pliega en `origen` al pasar `fin`; si la siguiente ya entraba (`lanzada == fin`), `relanzar_parte` vuelve a lanzar la actual en el próximo compás; apretar dos veces suma; saltar lo borra), **X ya** (saltar) e **Ir a otra parte…** (hoja). «Subida hacia X»: últimos 4/8/16 (`/api/subida {compases, final: true}` → `pedir_subida_final`: espera hasta que falten N compases de la parte y termina justo en su final; estado `{"pedida": N, "final": true}`). En modo canción las escenas pasan a «Escenas sueltas» (cerrado) y el piloto se oculta. `_cancion_estado` trae `extra` y el total con lo alargado. Cabecera: el nombre del tema (▾) abre «Tus temas» (`hojaTemas`: abrir, + Nuevo tema, Duplicar este); `/api/proyectos` trae partes y compases. Bienvenida (`bienvenida`, la primera vez sin tema guardado, o desde «+ Nuevo tema»): plantillas con su curva de energía (`plantillas.lista()` trae `energias`), «En blanco» y abrir uno guardado; `nuevoTema` primero guarda como tema nuevo (el anterior queda con su último cambio) y después `POST /api/cancion/plantilla {clave, nuevo: true}` (sin escenas del anterior, modo canción prendido; clave `blanco` = una parte de 16). Pruebas: cancion.py (quedarse, quedarse en el último compás, total, subida al final) y edicion.py (tema nuevo, en blanco, lista de temas).
- **0.80.0 · App nueva, etapa 4: editor de secuencia.** Arriba, «Lo que toca ahora»: barras por paso (altura = nota, claras = fuertes, la blanca = el paso que suena), de lo que de verdad salió por MIDI. El motor la anota en `Secuencia.huella` (Motor._tocar_paso → `_anotar_huella`, por índice del patrón, se pisa en cada vuelta así se ve lo que mutó) y la app la pide a `GET /api/patron?sec=N` cada 250 ms solo mientras el editor está a la vista (`raiz` dice si espera su nota larga). Variante A/B (`varianteAB`, en el teléfono, clave «ab:sec-X»): A = la guardada, B = probando, «Otra», «Quedarme con…», favoritas ★ y «Sonaron:» con las últimas 8; si la seed cambió por fuera, la que suena pasa a ser A. Tres controles principales: Densidad, Largo de las notas, Brillo (octava; salió del grupo Notas). Mutación de notas y la seed escrita a mano pasan al grupo Variación; Género es un grupo cerrado. «Copiar a otras partes…» (`copiarMotorA`) usa /api/parte/copiar, que ahora acepta `desde: -1` = lo que suena ahora (forma.foto). pruebas/app.py vuelve a dar la nota larga si un cambio la soltó. Pruebas: pruebas/huella.py (la huella = las notas que salieron, paso por paso) y edicion.py.
- **0.54.0 · Estilo y género «Psytrance»:** salió del análisis de 25 loops MIDI del pack Zenhiser Analog Psytrance (140 BPM): el riff deja huecos fijos (sobre todo los pasos 5 y 9, donde cae el bombo), 60-90 % de raíz saltando de octava, color ♭7 > ♭3 > ♭2 > 4.ª en los pasos de cierre de cada medio compás (8, 11, 15, 16), notas muy cortas con alguna larga, frases A/B. Figuras en generador._psy_*: riff (MASCARAS_PSY del pack, de la más llena a la más vacía según `huecos`), ráfaga (bloque de notas iguales que cambia de altura por compás), octavas (rolling de octavas con color en el paso 15), arpegio (célula de 8 con huecos), pulsos (negras sostenidas; el patrón puede traer `sostener` = pasos que dura la nota). Comparte con el Goa clásico la frase 2/4, respuesta, respuestas distintas, mutación, raga y techo (generador.FRASEADOS; clasico(..., familia="psytrance")). Figuras místicas (de LD Magic, LD Mystic, LD Protest y SY Supernova): espacio (raíz y octava de 1½ tiempo + nota corta en el contratiempo), mantra (drone de 3 tiempos y canto lento en negras con anacrusa de ♭7), tresillo (tresillos de corchea y de negra: el patrón puede traer `retraso` = pulsos tarde dentro del paso, así el tresillo cae en 0, 8, 16) y descenso (raíz en cada tiempo y línea que baja ♭7 ♭6 5 4). `sostener` acepta fracciones (1.5 pasos). De la carpeta completa de MIDIs del usuario (413 loops de 7 packs, clasificados por familia): figuras puntillo (MASCARAS_PUNTILLO, grupos de 3 semicorcheas) y melodía (contornos por grados que suben en A, bajan desde el ♭6 en B y resuelven en la raíz); bajo «sincopado» (..xx..x...xx..x., lejos del bombo) y remate en fusas (`fusas` en [bajo]: las últimas notas del compás que cierra la frase se parten en dos fusas; Golpe.fusa); voz doble en las secuencias (`doble`: tercera/cuarta/quinta/sexta/octava paralela por grados, motor._por_grados); stabs de acordes en los pads (`ritmo` = "stabs", el pulso 1-4 elige la máscara de STABS); progresiones i_iv_bVI_bIII y i_v_bVI_iv. Prueba: pruebas/carpeta.py (incluye que todos los ajustes nuevos sobrevivan a guardar y volver a cargar). **Arreglo:** en 0.53.0 `variar` quedó declarado en la sección de texturas del esquema, así que la app no guardaba «Respuestas distintas» (las pruebas no pasaban por normalizar); ahora está en la secuencia, junto con `huecos`. escuchar_clasico.render(..., segunda={...}) toca una segunda secuencia en la salida SEC con otro timbre, para oír dos sintes juntos. Género Psytrance en generos.py (frigio, i–♭II cada 16, bajo rolling, FX zaps y glitches). App: tarjeta Psytrance con figura y Huecos. Prueba: pruebas/psytrance.py. escuchar_clasico.render(..., estilo="psytrance") suma palmas en 2 y 4 (BPM se cambia con escuchar_clasico.BPM).
- **0.53.0 · Estilo «Goa clásico»:** salió del análisis de 7 MIDIs de referencia (PT_01/02/05/43/45): grilla de semicorcheas, la raíz manda, ♭2 como firma y frases A B / A B A C con la variación en la segunda mitad del último compás. `generador.clasico` con figuras pedal / ciclo / acordes (+ auto por seed) y campos `figura`, `frase` (2/4), `remate`, `ciclo` (0 = seed, 3/5/6/7), `registro` (1-3). El patrón dura la frase (Secuencia.largo = 32/64); `Secuencia.firma()` reemplaza la tupla (seed, estilo, largo, pedal) en motor y director. Mutación propia (`mutar_clasico`): cambia una nota y todas sus repeticiones, nunca la raíz. `variar` (0-1): cada vuelta de la frase toca otra respuesta (B/C desde `clasico(..., vuelta=k)` + `con_respuesta`; el A no cambia) y regresa a la primera tras 1 + round(variar·3) vueltas; se aplica en Secuencia.evolucionar al inicio de cada frase (también sobre el patrón guardado del director). Director: con este estilo la «hermana» usa mutar_clasico y el «recuerdo» no usa espejo (se corre un compás). Todas las secuencias tienen `deslices` (0-1, opcional; 0 = idéntico a antes): respiraciones (la raíz débil no se ataca y la anterior se sostiene, Motor._respira), notas llenas que terminan justo al entrar la siguiente y aproximaciones por grado al adorno que viene; sin cambiar la escala. Y `raga` (goa/raga.py: bhairav, bhairavi, todi, marwa, hijaz) con `ornamentos` y `bend_rango`: la escala de la raga desde la tónica (Tonalidad «raga:x», manda sobre la escala de color). **Todo en la rejilla de semicorcheas** (la 1.ª versión partía pasos en fusas: sonaba a redoble, corría la nota del tiempo y los ligados se pisaban; medido y corregido): Motor._en_rejilla cambia la nota de los pasos de nota fija (Sa o Pa, nunca el uno del compás) que rodean a la nota adornada: kan = el paso anterior lleva la gracia de la raga; gamak = los dos pasos después de una nota que tiembla hacen el trino (vecina, nota). Motor._ornamento_raga deja solo lo de pitch bend, que no agrega notas: meend (si cabe en bend_rango) y andolan (¼ de tono en notas sostenidas que tiemblan). Los bends van en Secuencia.bends y vuelven al centro al callar o sacar la raga. Prueba: notas fuera de rejilla / de ≤2 pulsos / pisadas = 0 con todo al máximo. Con ornamentos ≥ 30 %, el Goa clásico cierra la frase con el pakad de la raga (generador._cerrar_con_pakad). Y `techo` (nota más alta, 127 = sin techo): lo que pasa baja de octava en Motor._tocar_paso, después de la armonía y del director. App: tarjeta «Goa clásico» en la secuencia; al elegirlo pone posición «todas». Prueba: pruebas/clasico.py. Escuchar: `python3 -m pruebas.escuchar_clasico carpeta/` (8 ejemplos a 145 BPM con bajo del motor, MP3).
- **0.52.0 · Texturas con ritmo y registro:** cortas sobre FIGURAS rítmicas (una cada 4 compases, motivo de 2 compases repetido, seeds tx:figura/tx:motivo); notas desde PISO C3 + octava (antes salían de la raíz del disparo +1/+2 octavas: muy agudas), repartidas en `registro` 1–3 octavas (largas prefieren abajo).
- **0.51.1 · Remates offbeat clásicos otra vez:** vuelven {13:7,14:4,15:0}/{14:7,15:6}; en offbeat, las notas del remate junto al bombo (l%4 1 o 3) con grado <3 suben una octava y van sin acento (sonaban a segundo bombo).
- **0.51.0 · Motor Texturas:** goa/texturas.py + sección [texturas] (config, motor, motor_forma._paso_texturas, forma: escenas/energía/transiciones, app: panel y botón). Largas de 1/2/4 compases con CC que respira (seno^1.5), notas comunes con el acorde siguiente, cortas fuera del bombo. Prueba: pruebas/texturas.py.

- **0.50.1 · Arreglos:** remates del bajo offbeat solo en contratiempos (antes 13/15, pegados al bombo). La mutación del filtro de notas parte siempre del molde original y no toca los pasos del bombo (antes se acumulaba y la secuencia perdía el tiempo). Con el filtro puesto, el cambio garantizado de la mutación de notas cae en un paso que se oye (generador.mutar(audibles)). Medido: la mutación de notas sin filtro es idéntica a la de la 0.40.

- **0.50.0 · Versión tablet automática:** desde 700 px de ancho, columna de 720 px y controles más grandes; desde 1000 px (iPad horizontal), Tocar fijo a la izquierda (sticky, con su propio scroll) y la pestaña elegida a la derecha; la pestaña Tocar se oculta. Solo CSS + mostrar()/tocarVisible(); el teléfono no cambia.

- **0.49.1 · Dos dongles iguales:** buscar_puerto acepta «Nombre #n»; la app y goa-ports muestran «CH345 #1/#2» (antes se fundían en uno). Prueba: pruebas/puertos.py.

- **0.49.0 · Filtro que se abre en las subidas:** `subida_filtro`, `subida_desde`, `subida_hasta`, `subida_despues` (vuelve/queda) por secuencia, sin necesitar el FX; el último paso de la subida llega a «hasta». Con FX, `curva_filtro(..., tope=subida_hasta)`. Grupo de la app renombrado «Filtro del sinte» (no confundir con el filtro de notas).

- **0.48.0 · Dos LFO por secuencia:** `lfo2*` además de `lfo*` (secuencia.Lfo, PREFIJOS_LFO); la app avisa si los dos mueven el mismo CC.

- **0.47.1 · El LFO también mueve el wavetable:** opciones CC 20 y 21 (posición de wavetable A y B de la FM-1 con Shrub).

- **0.47.0 · LFO de filtro en las secuencias:** `lfo*` por secuencia (CC 74/71, seno/triángulo/azar/sube/baja, 1 tiempo a 32 compases, rango). Motor._lfo_secuencias cada 3 pulsos, solo al cambiar; espera si el FX interviene ese CC. Mapa de CC de la FM-1 con Shrub en el LEEME. Prueba: pruebas/lfo.py.

- **0.46.0 · Se saca el estilo Deepnotic y la plantilla 10:** el intento de bajo estilo Dekel no funcionó (se dio por fallido). Configs guardadas con `deepnotic` pasan a `offbeat` (config.ESTILOS_BAJO_RETIRADOS, bajo.ALIAS). Se quedan el filtro automático por CC, el golpe de filtro por nota y el portamento, que sirven para cualquier estilo.

- **0.45.3 · Deepnotic corregido:** el análisis de la 0.45.0 había tomado la cola sub del bajo por el bombo. Bien medido (con el click del bombo): bombo en el tiempo, bajo a contratiempo (raíz en tiempos 2 y 4, sube en 1 y 3) y una corta suave en la 4.ª semicorchea. `atraso` ahora corre el contratiempo.

- **0.45.2 · Portamento por CC:** `porta` y `porta_tiempo` en el bajo (CC 65 y CC 5, se mandan solo al cambiar; apagado no toca el sinte).

- **0.45.1 · Filtro en el ataque y deepnotic recto:** `filtro_nota` (CC sube en cada ataque y vuelve; no en notas ligadas de un slide). `atraso` por defecto 0: el retraso medido en el tema era el sidechain del bombo, no la nota.

- **0.45.0 · Estilo Deepnotic (Dekel) + filtro automático por CC + Template 10:** analizado «Free Diving» (Dekel & Satcha, 136 BPM): dos notas de bajo por tiempo (alta atrasada ~1/3 de semicorchea, grave en la 4.ª), la alta fija en tiempos pares y variando en impares, y el filtro abriéndose 1,5-2 min y cerrándose en cada quiebre. bajo: estilo `deepnotic`, `atraso`, `filtro*` (CC por tiempo; motor_forma lo reinicia en quiebres). Plantilla template10 (136 BPM, Circuit proyecto 45) y su batería en herramientas/circuit_cancion.py.

- **0.44.8 · Remate con acento suave:** +6 sobre la fuerza del bajo (antes +12 que se sumaba a los acentos al azar y llegaba a 127).

- **0.44.7 · El bajo nunca pisa notas sin slide:** ninguna nota dura más allá del comienzo de la siguiente (antes se pisaban 1-3 ticks con swing, tresillos, golpes de 2 pasos en remates del offbeat/dub y largo alto). Prueba que recorre estilos × largo × swing × remate marcado.

- **0.44.6 · Nota larga del remate sin pisarse:** termina antes de la siguiente (antes se pisaban 2 ticks); `remate_largo` (30-100 %, 75 % por defecto) controla cuánto del hueco ocupa.

- **0.44.5 · Nota larga del remate con control propio:** `remate_largas` (0 por defecto) separado de la variación; a lo más una nota larga por remate.

- **0.44.3/0.44.4 · La variación del remate no quita notas:** cambia alturas y, desde 50 %, a veces alarga una nota hasta la siguiente (slide). Nunca quita ni agrega notas. (La 0.44.3 quedó subida con el código viejo; la 0.44.4 lo corrige.)

- **0.44.2 · Remates sin cortes:** las notas del remate ya no se acortan (largo normal, solo sin slide y acentuadas), y la variación nunca calla la última nota del remate (antes podía, y la frase quedaba cortada).

- **0.44.1 · Remates: vuelven los dos clásicos + variación:** se sacan los 5 remates por estilo (no gustaron); vuelven los dos de la 0.43.2 que se alternan, con `remate_var` (azar por frase, notas y a veces ritmo), `remate_rango` (quinta/octava) y `remate_marca` (0 = como el resto, 1 = corto y acentuado).

- **0.44.0 · Bajo: 5 remates por estilo y «Notas que suben»:** la seed elige el remate de cada frase (sin repetir seguido; cambia el sonido de bajos guardados en el compás del remate). Nuevo control `sube` (0-1): caminos ascendentes desde la raíz (bajo.CAMINOS) en la última nota de 1-3 tiempos, dos por tiempo desde 55 %; topes 2/4/7 grados; camino distinto en compases pares e impares; nunca en el bombo.

- **0.43.2 · Remates del bajo marcados:** las notas del remate van cortas, acentuadas (+12), sin slide y siempre se vuelven a atacar (antes una nota igual a la anterior se ligaba y el remate sonaba a desliz). El rolling remata en los tiempos 3 y 4: rebote de octava o corrida que baja.

- **0.43.1 · Más contraste:** bordes de tarjetas, botones, segmentados y pasos del filtro más claros; tarjetas y textos secundarios un poco más luminosos.

- **0.43.0 · El molde es un filtro de notas:** interruptor propio (filtro, en secuencias y voces); prendido y vacío no suena nada, se abren pasos (x pasa, ? a veces, - bloquea). La seed arma las notas y el filtro solo deja pasar (antes el molde forzaba notas y tapaba la seed). En el diálogo las notas bloqueadas se corren al paso abierto más cercano, y la seed también gira el ritmo de las voces (cambia el sonido de diálogos guardados). Marca de bombo en los pasos 1-2-3-4. Moldes viejos: filtro prendido y . → x (config._migrar_moldes).

- **0.42.0 · Diseño «Yantra · Polvo estelar»:** la app se llama Yantra (logo en Megrim con contorno). Fondo casi negro con estrellas y un Sri Yantra tenue en la esquina; acento lavanda; cabecera y barra translúcidas; iconos de pestañas con geometría de yantra (el bindu aparece en la pestaña activa); deslizadores con degradé lavanda; casillas oscuras. Fuentes IBM Plex Sans/Mono y Megrim.
- **0.42.1 · Fuentes en la Pi:** al arrancar, si tiene internet, la Pi baja las fuentes (solo latín, unos 150 KB) a goa/web/fuentes/ (fuera de git) y la app las sirve desde /fuentes/; el teléfono las guarda en caché un año. Sin internet nunca se rompe: usa Google o la letra del sistema hasta poder bajarlas. Prueba: pruebas/fuentes.py. Propuestas en el lienzo de diseño.
- v0.36.0 Pads: «Al azar» salió del menú de progresiones y es una casilla (azar,
  azar_cada): parte de la progresión elegida, la primera variación suena tal cual y cada
  N vueltas cambia 1 o 2 acordes por otros limpios de la escala (i – X se dobla a
  i – X – i – Y). Configs con "aleatoria" pasan a i_bII + azar. Las sorpresas
  (variación) ya no repiten el acorde de al lado: antes a veces un cambio no se oía
  (posible causa de "no cambia cada 4").
- v0.35.2 Progresiones frigias nuevas: i–♭II–♭III–♭II, i–♭III–♭II–i, i–♭VI–♭II. El menú
  de progresiones dice en qué escalas suena mejor cada una (frigias primero).
- v0.35.1 Pads: el frigio al azar ya no es casi siempre de dos acordes (deja de ser
  escala "quieta": 3 y 4 acordes en ~78 %). Otra variante al azar se oye en el compás
  siguiente (entra en su 2.º acorde si sonaba la i). Cambiar "cambia cada" en vivo
  mantiene el acorde y sigue al ritmo nuevo (antes volvía a la i).
- v0.35.0 Motor de FX (pestaña Motores › FX, por defecto MC-101 canal 1): zaps,
  burbujas, ácido, glitch con pitch bend y CC del filtro; "Locura" (la energía la mueve).
  Subidas: botón en Tocar (8/16/32, ✕ cancela), casilla "Riser" por parte de la canción,
  build y break del piloto. Riser: golpes que se densifican, pitch que sube, filtro que
  baja el primer cuarto y se abre hasta el drop; caída de 2 compases en el drop.
  Secuencias con casilla FX: su filtro (CC configurable + reposo) hace la misma curva,
  redobles en la 2.ª mitad de la subida y stutter en el último tiempo de cada frase de 4.
- Modo canción (partes = escena + compases + curva de energía + entrada suave/golpe),
  modo libre intacto. Program Change por motor (FM-1 Shrub: sin confirmar que funcione).
- Apoyos opcionales a la subida por parte: pads acompañan, roll de secuencias,
  corte de bajo, acorde de tensión, hueco.
- Templates (app + Circuit). Synth 1 = pista regla del largo de escena;
  MIDI 1 nota larga F2 canal 3 (pads), MIDI 2 canal 4 (secuencias). Crash con
  reverb Hall + algo de delay.
  - T1 Psytrance (proyecto 32), T2 Dark minimal 142 (33, glitch solo agudo), T3 Goa clásico (34),
    T4 Goa tribal (35), T5 Goa épico (40), T6 Psy chill 104 (41),
    T7 Chillgressive 120 (42), T8 Chillout 92 (43), T9 Ambient 76 (44).
  - T1–T9: 16 escenas; las subidas (Rise, Fuego, Vuelta, Ascenso) de 8 compases y el resto de 16.
- Escalas: doble armónica en Música; escala de color por secuencia (doble armónica,
  persa, enigmática); control ♭2; progresiones i–♭VII–♭VI–♭VII e i–♭II–♭VII–i.

- Control de frases (opcional): molde de 16 pasos (siempre, a veces con probabilidad, nunca) y orden (adelante, atrás, péndulo, azar) en secuencias y voces del diálogo, 🎲 Goa/Psy y mutación opcional del molde;
  Otra frase / Volver / Fijar por voz; la respuesta contesta con lo suyo, eco, espejo o cerrando.

## Pendiente / a revisar
- Goa clásico (0.53.0) por afinar después de probarlo en el hardware: rango de pitch bend real de la FM-1 con Shrub (bend_rango, 2 por defecto); si se extrañan los ligados con glide (ahora no se pisan), opción que solo los pise con el sinte en legato; más vocabulario para que las seeds se distancien más (celdas de octava del pedal, celdas de acordes, arpegios que suben y bajan). Seeds de referencia que suenan distintas: pedal S-017 S-025 S-040 S-100 · ciclo S-006 S-059 S-001 S-028 · acordes S-007 S-003 S-079 S-012.
- Numeración de proyectos: la herramienta usa slot 0–63 y la Circuit muestra 1–64.
  El envío a "slot 40" cayó en el proyecto 41 (T5–T9 quedaron en 41–45; el 45 fue
  sobrescrito). Hay que cargar los archivos corregidos `p40_goa_epico.ncs` …
  `p44_ambient.ncs` en los proyectos 40–44 (con Components, o por el conector
  usando slot = proyecto − 1).
- El usuario vio 140 BPM en todos los templates nuevos, pero los .ncs traen su
  tempo (104/120/92/76). Comprobar al cargarlos bien; si sigue en 140, la Circuit
  está siguiendo un reloj MIDI externo.
- Program Change en FM-1 Shrub sin confirmar.
- FX: falta probar con el hardware. CC del cutoff de la FM-1 con Shrub sin confirmar
  (por defecto 74); MicroFreak = 23. Rango de pitch bend de la MC-101 (12 para una
  octava en el riser). Los gestos aún no esquivan los huecos del diálogo.
- Banco de samples de la Circuit: "FROM GOA TO PSYT" (nombres con
  `list_drum_samples` del conector circuit-tracks).


## Con la otra voz (0.54)

Tres controles opcionales por secuencia (grupo «Con la otra voz», desde la segunda secuencia) para que dos sintes no se pisen. Miran a la primera secuencia activa de la lista. En cero, todo suena como antes.
- `corrimiento` (0-15): el patrón entra N semicorcheas tarde (motor._indice).
- `complementar` (0-1): calla donde la referencia ataca; hasta 50 % cede en sus tiempos y acentos, al 100 % es hocket (nunca ataca junto al lead). Con un lead que toca todas las semicorcheas se queda casi muda.
- `separar`: si choca de cerca con lo que suena en la referencia (segunda, séptima o tritono a menos de una octava, o la misma nota; la ♭9 lejana del frigio se respeta). Además, una nota corrida dentro del paso (tresillo) que caería a 1-3 ticks de un ataque de la referencia se alinea con él, y si la referencia va corrida (tresillo en el lead) la sigue; una nota pegada al golpe tardío de la referencia en el paso anterior se calla. Así no hay flams en ninguna dirección, va a la nota consonante de la escala más cercana (hasta una quinta); si la referencia ataca encima de una nota larga que choca, la corta.
Prueba: pruebas/voces.py.

El corrimiento es una herramienta creativa en crudo: no corrige nada y algunos valores pueden sonar mal. Separar es la red opcional; probado en 7.744 combinaciones (22 estilos/figuras × 22 × 16 corrimientos) sin flams ni choques cercanos. escuchar_clasico.render(..., cambios={compás: {...}}) mueve controles de la segunda secuencia en vivo.
Con armonía guiada, Separar busca primero entre las notas del acorde si la nota que mueve era del acorde (antes bajaba de 92 a 86-88 % las notas del acorde en los tiempos fuertes; ahora queda igual que sin separar).

Revisión antes de subir (0.54): Separar también alinea el swing (antes solo los tresillos); tope MIDI 0-127 en todas las notas de las secuencias (la voz doble en octava podía mandar 132 con la nota arriba de todo); el momento armónico se calcula una vez por paso (≈10 % menos CPU, picos de 1,9 a 1,5 ms). Verificado: 22 suites, 7.744 pares de estilos sin flams ni choques, 1.000 configs al azar sin fallas ni notas colgadas, 26 casos idénticos a la 0.53 con lo nuevo apagado, una config guardada por la 0.53 carga bien.


## Actualizar desde la app (0.55)

Ajustes › Actualización: «Buscar actualización» hace `git fetch` y muestra la versión nueva y los mensajes de los commits; «Actualizar y reiniciar» hace `git checkout main && git pull --ff-only`, comprueba en un proceso aparte que el código nuevo compila, que el motor arranca y que carga la config del usuario (4 compases), y si falla vuelve al commit anterior (`reset --hard`). Luego el proceso se manda SIGTERM (apaga notas y guarda, como `systemctl restart`) y systemd (Restart=always) lo levanta; la app espera un proceso nuevo (campo `inicio` de /api/estado) y se recarga. Sin systemd (INVOCATION_ID ausente) no se apaga: avisa que hay que reiniciar. «Volver a la versión anterior» = goa-update --anterior. Git corre con SCHED_OTHER y nice 10 (el servicio es tiempo real). Si cambió install.sh, la app avisa que hay que correrlo. Código: goa/actualizar.py; prueba: pruebas/actualizar.py (GitHub falso en carpetas temporales).

## Restaurar ajustes de fábrica (0.56)

Botón pequeño con ícono de espiral en la cabecera de cada secuencia (junto a «Activo»), con confirmación. POST /api/secuencia/fabrica {fila}: config.fabrica_secuencia pone los valores por defecto de ESQUEMA_SECUENCIA y conserva CONSERVAR_EN_FABRICA (nombre, nota larga, activa, salida, canal, programa, género, seed y los CC del sinte). Después Motor.reiniciar_secuencia(fila) regenera el patrón desde la seed: si lo único distinto era la mutación, la firma no cambia y el motor habría seguido con el patrón mutado. Prueba en pruebas/carpeta.py.

## Fábrica en todos los motores y Deshacer general (0.58)

**Restaurar ajustes de fábrica** (botón de espiral en la cabecera, con confirmación) en todos los motores: secuencias, pads, bajo, llamada y respuesta (las dos voces), FX y texturas. POST /api/fabrica {motor, fila}; /api/secuencia/fabrica sigue andando. config.fabrica_motor: las secuencias conservan CONSERVAR_EN_FABRICA; los demás CONSERVAR_EN_FABRICA_MOTOR (activo, suenan, salida, canal, programa, nota larga, escucha, género, seed y los CC de su sinte: filtro_cc, cc_corte, cc). Motor.reiniciar_motor deshace lo mutado aunque la firma no cambie (secuencia, bajo, frases del diálogo). Si ya estaba de fábrica no suma un paso.

**Deshacer general** (botón ↶ en la cabecera, junto a «Sonando»; gris si no hay nada): un paso atrás por toque, hasta 50 (goa/historia.py). Son pasos los cambios de controles (/api/config; mover un deslizador seguido, < 1,5 s, es un solo paso), el género por motor o de Música y la fábrica (deshacer la fábrica devuelve también el patrón mutado que sonaba: Motor.estado_* / volver_estado_*). No son pasos y no se pierden al deshacer: energía, piloto, escena que suena, subidas, clips lanzados, escenas, partes, canción, clips guardados y proyecto. **Fuera del candado:** cada paso guarda las referencias a la config de antes y la de después (sin copiar; anotar es O(1)); comparar, armar la config deshecha, normalizar y validar se hace sin el candado, y adentro solo se toma el paso y se aplica (si la config cambió entretanto, el paso vuelve a la historia y pide tocar de nuevo). Para que la foto siga fiel, lanzar/detener clips y diálogo reemplazan el objeto en vez de modificarlo (web._cambiar_fila). Deshacer devuelve solo lo que el paso cambió (sección o secuencia) y solo si sigue como ese paso la dejó; si después la cambió un clip, una escena o la canción, avisa y no la pisa. Abrir un proyecto vacía la historia. La app manda el cambio pendiente (los 350 ms de guardar) antes de deshacer o restaurar. /api/estado trae `deshacer` (pasos disponibles). Prueba: pruebas/fabrica.py (por HTTP con la app de verdad).

## Menos tiempo con el candado tomado (0.59)

Para que mover controles, deshacer o la energía no le quiten tiempo al reloj:
- **Guardar en la tarjeta en un hilo aparte** (Contexto._guardador): `_guardar_activa` solo lo pide (no espera) y devuelve el último error; junta cambios seguidos (GUARDAR_JUNTA = 0,3 s) y escribe sin el candado. `guardar_ya()` guarda esperando (antes de actualizar y al apagar, en main.py). `esperar_guardado()` para las pruebas. Guardar un proyecto también escribe el archivo fuera del candado.
- **goa/copia.py** reemplaza los copy.deepcopy de configuraciones enteras en motor, forma, motor_forma y generos: comparte la biblioteca (escenas, partes, clips: solo se leen) y copia cada sección con dict(). Era ~80 % de aplicar_config, también en el camino del reloj (energizar, transiciones, piloto).
- Medido en x86 con 16 escenas: aplicar_config 0,92 → 0,22 ms (máx 2,1 → 0,7); toma más larga del candado al mover un control 1,56 → 0,33 ms (máx 2,1 → 0,5), energía 1,9 → 0,5 ms, deshacer 0,23 ms; pulso del reloj p99 0,63 → 0,31 ms. En la Pi 4 calcular ~3-4×. Salida MIDI idéntica a la 0.58 (mismo hash, modo libre con escena/energía/subida y modo canción).

## Looper de la MC-101 (0.60)

Sección [looper] (activo, salida MC-101, canal 4, clip 0-16, parar 0-16) y pestaña Motores › Looper (16 slots + Callado, aviso si otro motor va al mismo sinte y canal, fábrica). Según la tabla MIDI de la MC-101 (MC-101_MIDIImpleChart_eng03): Program Change 0-15 en el canal de la pista = clip 1-16 (en el canal de control, 0-127 = escenas). Motor._looper manda el PC solo al cambiar, solo andando, y otra vez en cada Start. Callar: no hay mensaje de parar clip en la tabla, así que se lanza un slot vacío (`parar`; 0 = no calla). Escenas: «looper» está en forma.SECCIONES (la escena guarda activo y clip; `parar` va en ENRUTAMIENTO, es de la máquina). Anticipo: con una escena en camino, en el compás antes de que llegue (tr.fin − 1) ya pide el loop de destino; en modo canción también para partes que entran de golpe (MotorForma._looper_parte_siguiente lee la escena de la parte siguiente). Con Master Step Length en 16 pasos la MC-101 lo cambia justo en el uno. Escenas guardadas antes de la 0.60 no traen looper: no lo tocan. Prueba: pruebas/looper.py.
Por confirmar en el hardware: que la MC-101 reciba los PC del canal de la pista sin activar nada en System › MIDI, y que lanzar un slot vacío calle la pista Looper.

## nanoKONTROL2 (0.61)

goa/control.py (detalle en su docstring). Sección [control] (activo, puerto "nanoKONTROL2", canal 1, luces, subida 8) y tarjeta en Ajustes con el mapa. main.py abre su entrada aparte de la de la Circuit (revisar_control, cada 2 s, con reconexión); el callback solo encola. Un hilo junta lo último de cada fader/perilla y aplica cada 60 ms. Todo va por la API local (como otro teléfono) con la cabecera X-Goa-Control: mismas validaciones, deshacer y guardado; sube ctx.version_externa y la app se recarga (y rechaza un /api/config viejo: «Cambió desde el nanoKONTROL2»). Nuevos: POST /api/ajuste {cambios: [[sección, fila, clave, valor]], juntar} (unos pocos valores, armar y normalizar fuera del candado; `juntar` = un paso de deshacer como un deslizador) y POST /api/cc (CC directo al sinte de un motor).
Canales: Pads, Bajo, Secuencia A, B, Diálogo, FX, Texturas, Looper. Fader/perilla: pads voces/variación, bajo densidad/filtro_max, secuencias densidad/mutación, diálogo densidad (dialogo.densidad, desde 0.62)/oscuridad (las dos voces), FX filtro_reposo/locura, texturas densidad/profundidad, looper CC 74/CC 71 a la MC-101. **Sin volumen** (lo pidió así). Recogen el valor (RECOGER = 3 pasos o cruzarlo); si cambió por otro lado (escena, app) se sueltan y vuelven a recoger. S solo (otra vez restaura), M encendido, R seed nueva / loop siguiente. Transporte: TRACK elige escena (punteada en Tocar), PLAY lanza, STOP vuelve a la anterior, SET guarda escena, MARKER energía ±0,1, CYCLE piloto, REW deshacer, REC subida (otra vez cancela). FF libre. Luces (LED Mode External): M, S, CYCLE, REC, PLAY. Números CC de fábrica en modo CC (SET + CYCLE al prenderlo). Prueba: pruebas/control.py.
Por confirmar en el hardware: números CC de fábrica y LEDs en modo External.

## Densidad del diálogo (0.62)

dialogo.densidad (0-1, por defecto 1): Dialogo._ralear saca notas del plan del compás después de asignar las alturas; cada lugar de cada voz tiene su número fijo (seed:papel:densidad:lugar), así bajarla saca notas sin cambiar la frase y subirla las devuelve en el mismo lugar. La primera nota de cada voz siempre suena. Con armonía guiada, la última nota de cada voz en el compás cierra en el acorde: con menos notas esa puede cambiar de altura (a propósito). Deslizador «Densidad» en Motores › Diálogo y es el fader 5 del nanoKONTROL2 (antes golpes, que cambiaba la frase).

## Teclado de la MicroFreak, primera parte (0.63)

Para tocar en vivo a través del motor. La MicroFreak va por USB a la Pi con Local Off (confirmado por el usuario: con Local Off sus perillas quedan bloqueadas). Sección [teclado] (activo, puerto "MicroFreak", canal 10 = su Output chan, perillas, canal_sinte 3 = el del pad) y tarjeta en Ajustes. goa/teclado.py: en el callback de mido, los CC y el pitch bend que llegan por el canal del teclado se devuelven por USB al canal en que suena (los canales distintos evitan el bucle); las notas quedan registradas para el motor (todavía no suenan: falta elegir sinte de salida y modo «una tecla» / «contorno»). main.revisar_entrada generaliza la entrada aparte (nano y teclado). Prueba: pruebas/teclado.py.

## Tocado: tocar con estilo desde la MicroFreak (0.64)

goa/tocado.py (detalle en su docstring) y pestaña Motores › Tocado. Sección [tocado]: activo, salida/canal/programa (elegible; por defecto FM-1 canal 4), modo una_tecla | contorno, estilo goa | acido | mantra | raga | bajo, octava, compases 8-32 (largo de la grabación), seed. Teclado.recibir → Motor.tocado_on/off con el candado, al instante (sin cuantizar). La altura sale de Tocado.elegir con el acorde de Motor._momento_tocado (pads o nota larga): siempre en la escala (_en_escala) y en el tiempo en una nota del acorde. Raga: apoyatura desde arriba (2 pulsos) en el tiempo, solo con el reloj andando. Una nota sostenida que choca con un acorde nuevo se vuelve a atacar suave en la nota del acorde (_cambio_de_acorde). Grabar: armado → graba desde el próximo uno los compases elegidos → loop cuantizado a semicorcheas; el loop guarda ritmo, largo, fuerza y tecla, no la altura (cada vuelta elige con la armonía del momento; seed nueva = otras notas, mismo ritmo). POST /api/tocado {accion: grabar|parar|seguir|borrar}; /api/estado trae `tocado`. Fábrica no borra lo grabado. Lo grabado no se guarda en escenas ni en la tarjeta todavía. Prueba: pruebas/tocado.py.

## Tocado guardado y diagnóstico del teclado (0.65)

- tocado.loop (texto JSON [compases, [[inicio, largo, fuerza, tecla]…]], hasta 60000 caracteres: un número como 4.º elemento del esquema de un str es su largo máximo, el resto se corta a 40). Al terminar de grabar o borrar, Tocado.cambio_loop; Contexto.sincronizar_tocado (desde /api/estado, /api/tocado y el bucle de main cada 2 s) lo pasa a ctx.config y motor.base y pide guardar. «tocado» está en forma.SECCIONES: las escenas guardan el loop (y si está prendido); lanzar una escena con loop lo carga desde el uno del compás, una sin loop lo saca, una de antes no lo toca. Fábrica conserva el loop.
- El usuario probó la 0.64 y el teclado (teclas y perillas) no hacía nada: sin acceso a la Pi, se agregó diagnóstico. Teclado cuenta lo recibido, avisa si las teclas o perillas llegan por otro canal (otro_canal) y la tarjeta de Ajustes ofrece «Usar el canal N», dice qué entradas ve la Pi si no encuentra la MicroFreak, y avisa si el Tocado está apagado. Pendiente: lo que muestre en la Pi.

## Arranque seguro (0.65.1)

El usuario reportó cuelgues y que la Pi dejó de arrancar (sin acceso remoto para ver la causa; sospecha principal: la MicroFreak alimentada por el USB de la Pi, o la SD dañada por cortes). config.guardar hace fsync del archivo y de la carpeta y deja la versión anterior como `config.toml.respaldo`. main.cargar_seguro: si la config está vacía o dañada arranca con el respaldo y si no con config.ejemplo.toml (la dañada queda como `.dañada`), en vez de salir y reiniciarse cada 2 s. Prueba de humo de main con un mido falso: arranca, abre Circuit, nano y MicroFreak, CPU en reposo ~0 %.

## Causa del cuelgue: el motor escuchándose a sí mismo (0.65.2)

Con el log de la Pi: «Teclado conectado: RtMidiOut Client:RtMidi output 128:0». La config tenía teclado.puerto = "RtMidiOut Client #1": cada salida que abre el motor con rtmidi aparece en ALSA como un puerto «RtMidiOut Client» que también se puede escuchar, así que el teclado recibía todo lo que mandaba el motor (y lo devolvía): realimentación a toda velocidad en un proceso de tiempo real → Pi colgada. Arreglo: main.es_propio / sin_propios (RtMidi y Midi Through) quedan fuera de las entradas y salidas disponibles y buscar_puerto nunca los elige; la app no los lista. Teclado: freno de más de 400 mensajes por segundo (deja de escuchar 5 s y avisa). Pendiente en la Pi: corregir teclado.puerto en su config.toml.

## Tocado: estilos de las secuencias, pasos y cuantización (0.66)

Ya funciona en la Pi (la MicroFreak no mandaba teclas por USB: era su ajuste Output/Merge). Pedidos del usuario tras probarlo:
- Estilos: los mismos de las secuencias (generador.ESTILOS). Tocado._patron arma una Secuencia con ese estilo y la seed; en «una tecla» cada nota toma la altura del paso del patrón en que cae (o del último paso que suena antes), contado desde el compás (paso absoluto), con la nota del acorde en los tiempos. Se sacaron los estilos propios (goa, mantra, raga, bajo); config.normalizar los migra (TOCADO_ESTILOS_0_64) para no romper configs ni escenas viejas.
- Largo de la grabación en pasos (1-32, deslizador; tocado.pasos reemplaza compases). Empieza en el próximo uno; termina a los N pasos (no tiene que ser un compás: un loop de 3 pasos es polirritmo). Loop guardado como {"pulsos", "notas"} (lee el formato viejo).
- Cuantización tocado.cuantizar: estricta (inicio y largo a la semicorchea), suave (a mitad de camino), swing (contratiempo +2 pulsos), libre. Misma posición: queda la más fuerte. Una nota tocada hasta 4 pulsos antes del uno cuenta desde el uno (aunque ya se haya soltado).
- El indicador de grabación (Grabando 3/16, Loop 5/16) quedó al lado del botón Grabar.

## Tocado: ajustes del estilo, melodía por orden de notas y cuantización estricta (0.67)

Tras probarlo el usuario pidió: cuantización más estricta, los sub-parámetros de los estilos y que cambiar el estilo después de grabar se note, y grabaciones más largas.
- config.TOCADO_PATRON: el Tocado lleva los ajustes de patrón de una secuencia (género, figura, frase, remate, variar, ciclo, registro, huecos, pedal, saltos, raga, ornamentos, escala_color, semitono, relación, acentos, acento, largo). tocado._secuencia arma una Secuencia con ellos (y su escala de raga o color). La UI reusa panelClasico/panelPsy y un grupo «Notas del estilo».
- Alturas por orden de notas: la nota N que tocas toma la nota N que suena en esa secuencia (antes: el paso en que caía, que con pocas notas casi siempre era la raíz). En el loop la cuenta sigue entre vueltas (vuelta × notas + i), así la melodía avanza y un cambio de estilo se oye en la vuelta siguiente. Acentos del estilo: fuerza mínima `acento`. Saltos de octava y ♭2 como en las secuencias.
- Cuantización: rejilla de semicorcheas o corcheas (tocado.grilla); descuenta LATENCIA = 1 pulso y redondea hacia adelante en la mitad; en estricta ninguna nota se monta sobre la siguiente. Las notas del loop ya no se vuelven a atacar en un cambio de acorde (eso agregaba golpes fuera del ritmo grabado).
- Grabación de 1 a 128 pasos (8 compases).

## Tocado: los ajustes de las secuencias que no tocan el ritmo, y largo del loop (0.68)

- Arreglo: Grabar seguía topado en 32 pasos (tocado.accion tenía min(32)); ahora 1 a 128.
- config.TOCADO_EXTRA: armonía (general/guiada/libre), techo, voz doble, slide, mutación (mutar_cada, bloqueada), recorrido, variación de fuerza, gate/gate_random con `largo_nota` (tuyo | estilo), densidad, repetición, FX y filtro en la subida, LFO 1 y 2. No van los que deciden el ritmo (posición, corrimiento, molde, mutación de ritmo, swing, complementar/separar, deslices).
- Densidad/repetición/slide/gate solo en el loop; techo, doble, recorrido, fuerza y armonía también en vivo. La mutación cambia el patrón del estilo en el compás (Tocado._mutar). LFO en motor._lfo_secuencias; filtro de subida/FX con un SimpleNamespace (tocado.filtro) que motor_forma._con_filtro suma a las secuencias.
- Largo del loop después de grabar: accion("largo", pasos) — no destructivo. `grabado` = largo de la grabación; si el loop es más largo, la repite (tramos); el JSON guarda "grabado" si difiere.

### 0.68.1 — Program Change solo de lo que suena
Un motor apagado (secuencia no activa, pads/bajo/tocado apagados) ya no manda su parche a su sinte (antes lo mandaba si ningún motor activo pedía ese sinte y canal). Al prenderse lo manda; motor._programas olvida los canales que nadie pide, así lo vuelve a mandar al prenderse otra vez.

## Proyectos: guardar robusto y autoguardado (0.69)

- Bug: desde 0.65.1 config.guardar hacía `ruta + ".respaldo"`; con la Path de un proyecto fallaba al sobrescribir uno existente («Guardar» solo funcionaba con un nombre nuevo). Ahora `os.fspath(ruta)`. Después de guardar, se relee el archivo para confirmar.
- app.autoguardar (por defecto sí): con un proyecto abierto, el hilo de guardado escribe también el archivo del proyecto (Contexto._autoguardar).
- ctx.proyecto_al_dia → /api/estado; la app muestra «guardado» / «cambios sin guardar» y solo pregunta al abrir otro si hay cambios sin guardar. Al arrancar se compara la config con el archivo del proyecto.
- Abrir otro proyecto o «Guardar como» primero escriben lo pendiente (guardar_ya), así el último cambio queda en el proyecto que se cierra (antes el guardado que juntaba cambios 0,3 s podía perderlo).
- «Guardar como» con un nombre que ya existe pregunta antes de reemplazar (409 + sobrescribir).
- api() en la app manda antes el cambio que esperaba sus 350 ms (antes Guardar justo después de mover algo lo perdía al recargar).
- La lista de proyectos ignora temporales `.config-*.toml`.
- Prueba nueva: pruebas/proyectos.py.

## FX: gestos cuantizados que se repiten, fondo de notas largas con filtro en ritmo (0.70)

El usuario: los gestos sonaban muy al azar y fuera de cuantización; quiere notas largas y locuras de filtro de fondo, en la MC-101, con más control.
- Gestos: empiezan en un tiempo, duran tiempos enteros (fx.TIEMPOS) y todo cae en la rejilla de fusas (antes las burbujas iban cada 4 pulsos y el zap/eco cruzaban tiempos). `donde` (frase | compas | tiempo): al final de la frase/compás terminan justo en el uno. Qué gesto va en cada lugar se repite cada `repetir` compases; `caos` cambia algunos por vuelta. El glitch ya no usa pitch bend (los saltos de bend con un rango de 2 semitonos desafinaban): salta entre notas del acorde. Solo el zap usa bend.
- Gestos nuevos: barrido (1 compás, filtro abre/cierra), gate (2 tiempos, filtro euclidiano), eco (1 compás, corchea con puntillo), escalera (1 tiempo de fusas por el acorde).
- Fondo (fx.fondo): notas largas (raíz, del acorde, raíz+quinta, octavas) que se atacan cada `fondo_largo` compases y cambian en el tiempo siguiente si cambia el acorde. Filtro en ritmo (filtro_modo pluck|pasos|sh|wobble|rampa|quieto, filtro_division, golpes/rotar euclidianos, caída, min/max, movimiento) y resonancia (cc2) en un ciclo propio de `reso_ciclo` semicorcheas. El caos mete por tiempo: doble velocidad, saltos de fusas o congelar. Mientras un gesto con filtro (fx.CON_FILTRO), el riser o la caída manejan el filtro, el fondo lo suelta (filtro_hasta). Los "off" de un gesto no apagan una nota larga que sea la misma.

### 0.70.1 — El reloj no espera a la app
Síntoma: al mover algo en la app, el loop del Looper de la MC-101 se desincronizaba un rato. Causas que tironeaban el reloj reenviado (y los pulsos del motor):
- Python cambia de hilo cada 5 ms: mientras la app armaba/validaba/guardaba (y desde 0.69, además el proyecto), el pulso del reloj podía esperar. main: `sys.setswitchinterval(0.0005)`.
- El thru (reloj incluido) se reenvía antes y sin el candado del motor; Puertos.envio (candado chico) cubre cada send porque ahora se manda desde dos hilos.
- Puertos.cambiar_salidas (en cada cambio de la app, con el candado) pedía la lista de puertos al sistema: ahora no hace nada si las salidas son las mismas y usa la última lista; la revisión cada 2 s pide la lista fuera del candado.
- Lanzar escena arma y valida fuera del candado (como /api/ajuste).
- Los hilos de la app y del guardado dejan la prioridad de tiempo real (web.hilo_secundario). La configuración se convierte a TOML una vez para el archivo y el proyecto.

## Looper: entra siempre cuadrado (0.71)

El usuario: a veces el loop de la MC-101 entraba descuadrado y otras no.
- El Program Change del loop se pedía justo en el uno del compás anterior: con un pelo de atraso, la MC-101 a veces lo tomaba en ese mismo uno (un compás antes). Ahora queda pendiente (Motor.looper_pendiente) y se manda en el pulso 48 (MITAD_COMPAS) del compás antes de donde debe entrar (Motor._looper_pulso, desde reloj).
- looper.cada (1/2/4/8): en modo libre entra en el próximo múltiplo de `cada` compases desde el Start (loops de 4 compases siempre con la frase). Con escena/parte, entra con ella. Ir y volver al loop que suena antes de que entre no manda nada.
- looper.transporte: main reenvía clock/start/stop/continue/songpos a la salida del looper (sin candado, como el thru; no duplica si el thru ya va a esa salida). Para que la MC-101 arranque con la Circuit y su compás no quede corrido.

## Looper: apagarlo lo calla (0.72)

El usuario no quería depender de un slot vacío. La tabla MIDI de la MC-101 no tiene CC para parar un clip ni mutear una pista, pero sí CC 7 (volumen) por canal de pista.
- Interruptor apagado o «Callado» sin slot vacío: CC 7 = 0 en el canal del looper justo en el uno (en el próximo múltiplo de `cada`, o cuando entra la escena); al volver a sonar, CC 7 = looper.nivel (100) en el uno en que entra (el Program Change, si cambia el loop, sigue yendo en la mitad del compás anterior). Con slot vacío elegido, igual que antes.
- Solo calla lo que el motor hizo sonar (Motor.looper_enviado); Motor.looper_mudo recuerda que bajó el volumen. looper_pendiente = (clave, pc|None, nivel|None, compás).
- config.salidas deja abierta la salida del looper apagado si tiene un loop elegido (para poder callarlo). `nivel` es de la máquina: las escenas no lo guardan.

## Looper: re-encuadre de la MC-101 (0.73)

La MC-101 cuenta los compases desde su propio arranque; si se corre, el loop entra corrido. (Causa probable encontrada con el usuario: la MicroFreak, en la cadena antes de la MC-101, tenía MIDI Output en Both y mezclaba su propio reloj con el de la Pi → dos relojes. Recomendado: Sync Source MIDI, Thru On, Output USB.)
- looper.reencuadrar (no | escena | loop) y looper.parar_antes: la Pi manda (Stop y) Start por la salida del looper un pulso antes del uno (tras un Start, el pulso siguiente es el uno de la máquina). «escena»: cuando entra una escena o parte (aunque el loop sea el mismo); «loop»: cuando cambia el loop (no en el Start). Motor.reencuadre = (compás, salida, con Stop); Motor._reencuadre_pulso desde reloj. /api/looper/reencuadrar («Re-encuadrar ahora»: próximo múltiplo de «entra cada»).
- Ojo: el Start reinicia toda la MC-101 y llega a todo lo que vaya por ese cable. Puertos.enviar acepta "start"/"stop".

### 0.73.1 — El loop de una escena también espera la frase
El usuario tiene loops de 64 pasos y MSTRSTEPLEN 16: la MC-101 los cambia en cualquier compás y un loop que parte en el compás 2 de la frase queda corrido. Con `cada` > 1, el compás en que entra el loop de una escena o parte se redondea hacia arriba al múltiplo de `cada` (Motor._looper).

## 0.74 — Fuera el re-encuadre y el reloj al looper
Resultó que bastaba «entra cada 4» (loops de 64 pasos con MSTRSTEPLEN 16). Se quitaron looper.reencuadrar/parar_antes (Start a la MC-101) y looper.transporte (reenviar reloj a la salida del looper), con su API y su UI; las claves viejas se descartan al cargar. Queda: «entra cada», el pedido en la mitad del compás anterior, el loop de una escena que espera la frase, callar con CC 7, y las mejoras de reloj de 0.70.1.

### 0.74.1 — El eco de las perillas no frena el reloj
El usuario notó que el desync de la MC-101 venía con el eco de perillas / la entrada del teclado. Teclado._devolver tomaba el candado del motor por cada CC, y Puertos tenía un solo candado de envío compartido con el reenvío del reloj: si el USB de la MicroFreak tardaba, el reloj de la cadena esperaba. Ahora _devolver va sin el candado del motor y Puertos tiene un candado por puerto (Puertos.envio(clave)).

### 0.74.2 — Las entradas del teclado y del controlador descartan el reloj en el driver
El desync aparece con la entrada del teclado abierta aunque no se toque nada. Lo único que llega por ahí en reposo es el reloj que la MicroFreak reenvía por USB (24 por negra): main._sin_reloj le pide a rtmidi ignorar sysex, reloj y active sensing en esas entradas, así ni llegan a Python. Pendiente: confirmar con el usuario si con esto se va (y si probó con la MicroFreak ya en Output USB / Sync MIDI).

## 0.75 — La MC-101 como reloj maestro
Causa real del Looper descuadrado: el reloj que reenvía la Pi llega con jitter (Python + dongle barato) y el Looper de la MC-101 mide el tempo al arrancar cada loop (la primera vuelta salía mal, la segunda bien; con cable directo del dongle, peor). Solución: la MC-101 es la maestra (Sync INT) → Circuit (sigue reloj externo) → Pi; la Pi sigue igual. thru.reloj (por defecto sí): apagado, el thru no reenvía clock/start/stop/continue/songpos, así el reloj no vuelve a la MC-101 por la cadena (MicroFreak → MC-101).

## 0.76 — Modo edición de escenas
El usuario armaba escenas con «Escuchar» y después «Guardar lo que suena» (incómodo). Ahora:
- «Editar» en una escena (Tocar › Escenas › Editar) o en una parte (Canción, modo libre): /api/editar lanza la escena en 1 compás y deja ctx.editando = {escena, original}. Cada cambio (web._guardar_activa → Contexto.sincronizar_edicion) copia lo que suena en esa escena (forma.escena_de). Al entrar se limpia la historia de deshacer y se apaga el piloto. Una parte sin escena recibe una nueva.
- Franja arriba (sticky): «Editando «X»», con «Descartar» (/api/editar/descartar: vuelve la escena a `original` y la lanza) y «Listo». Lanzar otra escena termina la edición; borrar escenas corre el índice. En modo canción no se edita.
- Puntos de cambios: en las pestañas de motores (y en Motores/Armonía de la barra) cuando lo que suena difiere de la referencia: editando, la escena como estaba al entrar (/api/editar/original); si no, la última escena lanzada. Se ignoran las claves de enrutamiento.
- Prueba nueva: pruebas/edicion.py.

## Pendiente: app nueva (rediseño)
Propuesta de pantallas: https://claude.ai/artifact/QgXAzQJS2tbR9DQXztgZP8 (lienzo de diseño). Ideas acordadas con el usuario (compone temas completos que luego suenan casi solos; lo que más usa es editar secuencias; le faltaba una vista general):
- Inicio = Tema: línea de tiempo del proyecto (partes × motores, energía, apoyos, dónde va sonando). Escritorio: horizontal tipo DAW con inspector de la parte; celular: vertical (partes = filas, motores = columnas). Tocar un casillero abre ese motor en esa parte, ya editando; mantener apretado: Editar / Copiar / Pegar (solo ese motor) / Igual en la siguiente / Que no suene aquí, y para la parte entera Copiar / Duplicar / Mover (al pegar una parte, elegir qué motores).
- Parte (entra en modo edición), Motor (editor de secuencia: patrón visible, estilo, variante A/B + historial, 3 controles principales, «Copiar a…», biblioteca), Vivo separado («Quedarse 16 más», «<parte siguiente> ya», «Ir a otra parte…», subida «últimos 4/8/16»), barra con Tema · Vivo · Ajustes. Cabecera: nombre del proyecto abre la lista de temas; primera vez: plantillas.
- Scatter de la MC-101: hecho en 0.82.0; falta confirmar en la máquina que el note off lo apaga y qué pads gustan para cada etapa.

## 0.77 — App nueva, etapa 1: Tema (línea de tiempo) como inicio
- La pestaña «Canción» pasa a ser «Tema», primera de la barra y vista de inicio (localStorage vista_v2 la fija una vez). Arriba, renderLinea(): partes × motores (motores()), cada casillero según la escena de la parte: suena / cambia de estilo o variante (◆, difiere() contra la parte anterior) / no suena / parte sin escena. Pantalla ≥ 700 px: horizontal (columnas proporcionales a los compases, curva de energía, fila de apoyos); celular: vertical (partes = filas con alto según compases, motores = columnas, barra de energía).
- Tocar un casillero: editarMotorEnParte (si el modo canción está prendido pide pasar a modo libre) → /api/editar {parte}, elige ese motor y abre Motores. Tocar el nombre: elige la parte y abre su tarjeta.
- Cabezal: en modo canción, la posición de /api/estado.cancion (moverCabezal en cada estado); la parte que suena brilla y la que editas lleva borde. refrescarLinea redibuja si cambian (no mientras escribes en una tarjeta).

## 0.78 — App nueva, etapa 2: copiar y pegar desde la línea de tiempo
- Mantener apretado un casillero (0,45 s) o clic derecho: hoja con Editar, Copiar, Pegar, Igual en la siguiente, Que no suene aquí; y para la parte entera Copiar la parte / Pegar una parte aquí. Copiar entra al modo pegar (franja #pegar_caja): cada toque en la misma columna pega ahí; con una parte copiada, tocar el nombre de otra abre la elección de motores.
- Backend: /api/parte/copiar {desde, hacia: [partes], motores: ["bajo", "sec0", "dialogo" (con llamada y respuesta), …]} copia solo esas secciones de la escena de origen a la de cada destino (si no tiene, se le crea con lo que suena); responde `compartidas` si la escena de destino la usa otra parte. /api/parte/apagar {parte, motor}. Si la escena cambiada es la que suena o la que editas (modo libre), se vuelve a lanzar en 1 compás (la edición sigue). La lista de escenas se copia antes de cambiarla (la historia de deshacer guarda la anterior).
- Pruebas: pruebas/edicion.py (copiar y pegar).

## 0.79 — App nueva, etapa 3: pantalla de Parte y barra Tema · Vivo · Ajustes
- La barra queda en Tema · Vivo (la antigua Tocar) · Ajustes. Motores y Armonía ya no son pestañas: se llega desde una Parte (con «‹ <parte>» para volver; pintarVolver). En pantalla ancha, una sola columna (Tema usa todo el ancho; dosColumnas() = false).
- Vista v-parte (renderParte, parteVista en localStorage; -1 = «lo que suena ahora»): anterior/siguiente, compases y chips (entrada, energía, apoyos), «Editar esta parte» / «Escuchar» (o «Saltar aquí»), la lista de motores con Armonía primero (resumen de la escena de la parte, o de lo que suena si la editas o no tiene escena; punto de cambio si la editas) y la tarjeta de la parte (bloqueParte) abierta como «Entrada, apoyos y ajustes de la parte». Tocar un motor entra a editar la parte y abre ese motor (abrirMotor).
- En Tema: tocar el nombre de una parte abre su Parte; las tarjetas de partes salen de la lista (quedan en cada Parte); «Lo que suena ahora ›». «Editar» de una escena (Vivo) abre «Lo que suena».
