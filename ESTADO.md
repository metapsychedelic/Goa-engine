# Estado del proyecto (para retomar en un chat nuevo)

Versión actual: **0.36.0** (ver `goa/__init__.py`). En la Pi se actualiza con `goa-update`.

## Qué es
Motor generativo Goa/psytrance en Raspberry Pi. La Circuit Tracks es el reloj
maestro; el motor manda pads, bajo y secuencias por MIDI a FM-1 (firmware Shrub),
MC-101, MicroFreak. App web en el celular (pestañas Tocar, Motores, Armonía,
Canción, Ajustes).

## Archivos clave
- `goa/motor.py` (motor, secuencias, subidas, escala de color, ♭2)
- `goa/forma.py` (energía, conductor, modo canción, roll)
- `goa/pads.py` (progresiones, acorde de tensión), `goa/escalas.py` (ESCALAS, ESCALAS_COLOR)
- `goa/config.py` (esquemas), `goa/web.py` + `goa/web/index.html` (app)
- `goa/fx.py` (motor de FX: gestos, riser, caída, curva del filtro); la subida y la
  intervención de las secuencias están en `motor.py` (`_compas_subida`, `_glitch`, `_filtro_secuencias`)
- `goa/plantillas.py` (templates de canción de la app)
- `herramientas/circuit_cancion.py` (genera los .ncs de la Circuit; `todas carpeta/`)
- Pruebas: `python3 -m pruebas.<nombre>` (cancion, director, dialogo, en_vivo,
  escenas, piloto, progresiones, bajo, generos, armonia, mutaciones, thru, simular).
  App simulada: `python3 -m pruebas.app` en localhost:8080.

## Hecho recientemente
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
  - T1–T4 y T6–T9: 16 escenas × 16 compases = 256 compases (máximo de la Circuit). T5 sigue con escenas de 8.
- Escalas: doble armónica en Música; escala de color por secuencia (doble armónica,
  persa, enigmática); control ♭2; progresiones i–♭VII–♭VI–♭VII e i–♭II–♭VII–i.

## Pendiente / a revisar
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
