# Estado del proyecto (para retomar en un chat nuevo)

Versión actual: **0.54.0** (ver `goa/__init__.py`). En la Pi se actualiza con `goa-update`.

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
- `goa/config.py` (esquemas), `goa/web.py` + `goa/web/index.html` (app)
- `goa/fx.py` (motor de FX: gestos, riser, caída, curva del filtro); la subida y la
  intervención de las secuencias están en `motor.py` (`_compas_subida`, `_glitch`, `_filtro_secuencias`)
- `goa/plantillas.py` (templates de canción de la app)
- `herramientas/circuit_cancion.py` (genera los .ncs de la Circuit; `todas carpeta/`)
- Pruebas: `python3 -m pruebas.<nombre>` (cancion, director, dialogo, en_vivo,
  escenas, piloto, progresiones, bajo, generos, armonia, mutaciones, thru, simular, clasico, psytrance, carpeta).
  App simulada: `python3 -m pruebas.app` en localhost:8080.

## Hecho recientemente

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
