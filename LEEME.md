# Motor generativo Goa · etapa 1

La Raspberry Pi escucha el reloj y una nota larga de la Circuit Tracks por USB,
y toca secuencias Goa en la FM-1 (y opcionalmente en la MicroFreak) por USB.
Tus cables MIDI actuales no cambian.

## 1. Preparar la tarjeta SD (en tu computador)

1. Instala **Raspberry Pi Imager** desde raspberrypi.com/software.
2. Elige *Raspberry Pi 4* → *Raspberry Pi OS Lite (64-bit)* → tu tarjeta.
3. En la configuración (el engranaje o "Editar ajustes"):
   - Nombre del equipo: `goa`
   - Usuario y contraseña: los que quieras
   - Tu red Wi-Fi
   - Servicios: activar **SSH** con contraseña
4. Graba, pon la tarjeta en la Pi y enciéndela. Espera 2 minutos.

## 2. Copiar e instalar

Desde tu computador, conéctate a la Pi y descarga el motor desde GitHub:

```
ssh tu-usuario@goa.local
sudo apt install -y git
git clone https://github.com/metapsychedelic/Goa-engine.git goa-engine
cd goa-engine
./install.sh
sudo reboot
```

Para actualizar más adelante: `goa-update`. Para volver a la versión
anterior si algo suena peor: `goa-update --anterior`.

## 3. Configurar la Circuit Tracks

- En el **Setup** de la Circuit activa el envío de reloj (Clock Tx) y de notas
  MIDI (Note Tx) para las pistas.
- Usa la pista **Synth 2** para la nota larga (canal 2) y baja su volumen a cero.
  Las pistas MIDI 1 y 2 salen por los canales 3 (MicroFreak) y 4 (FM-1).

## Conexión recomendada: modo dongle

Conectar los sintes a la Pi por USB mete ruido (lazo de tierra) y la Circuit,
al cargar su batería, puede hacer caer la Pi. Con el dongle USB-MIDI no pasa
ninguna de las dos cosas, porque el MIDI de 5 pines y TRS es aislado:

1. Circuit MIDI Out → IN del dongle
2. OUT del dongle → MicroFreak MIDI In (MicroFreak con su Out en modo Thru)
3. MicroFreak Thru → FM-1
4. Dongle por USB a la Pi. Nada más va por USB.

En la app, sección Conexión MIDI: Entrada = nombre del dongle, activa
"Reenviar todo a la cadena MIDI" y en cada secuencia pon como destino el dongle.
La secuencia A con canal 4 suena en la FM-1; con canal 3, en la MicroFreak.

Si la Pi está apagada, la MicroFreak y la FM-1 no reciben a la Circuit:
para tocar sin la Pi, conecta la Circuit directo a la MicroFreak como antes.

## 4. Primera prueba

Conecta la Circuit y la FM-1 a la Pi por USB y entra por `ssh`:

```
goa-ports                         # ¿aparecen la Circuit y la FM-1?
goa-ports --probar FM-1 4         # ¿suena la FM-1? (modo dongle: CH345 4)
goa-ports --escuchar Circuit      # dale Play: ¿aparece "reloj OK" con el BPM?
goa-debug                         # mantén una nota en la pista Synth 2 y mira las notas
```

Los puertos se eligen en la app: cada motor tiene un menú **Destino** (en
Motores › Salida MIDI) y Ajustes › Conexión MIDI tiene la entrada y la salida
del reenvío. Los menús muestran lo que la Pi ve conectado en ese momento y se
actualizan solos al enchufar algo; un puerto elegido que no está enchufado
aparece como "(desconectado)". Para cambiar una máquina de lugar (por ejemplo,
la FM-1 por USB y la MC-101 por el cable MIDI), basta con elegir el puerto y el
canal nuevos en cada motor.

## 5. La app en el celular

Con el celular en la misma red Wi-Fi que la Pi, abre **http://goa.local:8080**.
Cada cambio se aplica en vivo, sin cortar el sonido, y queda guardado.
En el iPhone puedes agregarla a la pantalla de inicio desde Compartir.

Si `goa.local` no abre (pasa en algunos Android), usa la IP de la Pi:
corre `hostname -I` en la Pi y abre `http://LA-IP:8080`.

También puedes editar a mano `~/.config/goa/config.toml` y correr `goa-restart`;
las opciones están explicadas en `config.ejemplo.toml`.

## Pads y drones

En Motores › **Pads**: progresiones lentas de estilo Goa y
psytrance (i–♭II frigio, épica, andaluza, drone modal...), con voces que se
mueven lo mínimo entre acordes, drone opcional en la raíz, variación y rasgueo.
Con "Las secuencias siguen al acorde" (en Armonía, con armonía libre), las secuencias Goa cambian
de nota base junto con los pads. Pads en la MicroFreak (canal 3, hasta 4 voces)
y Goa en la FM-1 (canal 4), o al revés: cada máquina toca un solo sonido a la vez.

**Progresión al azar:** elige *Al azar · según la escala* y cada *Otra variante*
arma una progresión nueva de 2 a 4 acordes que parte en la i. Solo usa acordes
mayores y menores de la escala (deja fuera los disminuidos y aumentados), prefiere
los que le dan color a cada escala y termina en un acorde que vuelve bien a la i.
La app muestra la progresión en números romanos. Las escalas que mejor andan al
azar: **frigio** (lo más Goa: i–♭II, cortas), **menor natural** (la más variada,
♭VI y ♭VII épicos), **dórica** (luminosa, IV mayor) y **lidia** (flotante, II
mayor). Frigio dominante y húngara menor tienen pocos acordes limpios: dan
progresiones cortas. Una progresión nueva (al azar o elegida) entra en el próximo
cambio y parte en su i.


**Pulso:** con pulso, los acordes suenan en golpes euclidianos en corcheas.
*Largo del golpe* (aparece al subir el pulso) dice cuánto del hueco hasta el
golpe siguiente dura cada golpe: corto (35 %, por defecto) se oye como pulso;
al máximo, casi como un pad continuo. Si igual suena pegado, baja el release
del sinte.

## La app

Cinco pestañas abajo:

- **Tocar:** lo que usas en vivo, en este orden: **Escenas**; un botón por
  motor (Pads, Bajo, cada secuencia, Diálogo, FX) para prenderlo o apagarlo
  (entra o sale en el próximo compás y mientras espera dice "entra" o "sale");
  **Energía**; **Subida**; **Frases del diálogo** (si suena: Otra frase · Volver
  · Fijar de cada voz, sin ir a Motores); **Piloto automático** y **Variación
  larga**. Abajo, el acorde que suena. Arriba a la derecha, el botón de pánico.
- **Motores:** un motor a la vez, elegido arriba (el **+** añade una
  secuencia). Todos tienen la misma forma: activo, género, estilo (o textura en
  los pads), variante, los controles principales y grupos plegados con el resto:
  **Ritmo**, **Notas**, **Variación** y **Salida MIDI** (en las secuencias además
  **Filtro y orden** y **FX**; en el diálogo, **Voces** en vez de Notas, y las
  frases de cada voz junto a los principales). Cada grupo cerrado muestra un
  resumen de cómo está.
- **Armonía:** género para todo, tónica, escala (y qué poner en la Circuit),
  guiada o libre, tensión, anticipar y Pegado ↔ Desplazado.
- **Canción:** el modo canción y sus partes (ver más abajo).
- **Ajustes:** proyecto, conexión MIDI, canal general de la nota larga y qué
  pasa cuando cambia.

Para encontrar una buena variante, prueba con **Otra variante**; si saltaste
una que sonaba bien, **←** vuelve a ella (recuerda las últimas 20).

**Clips:** están dentro de cada secuencia y del diálogo, en el grupo
Variación. "Guardar como clip" guarda su carácter (estilo, variante, ajustes;
en el diálogo, la conversación completa con sus destinos). Al tocar un clip
entra en el próximo compás; mientras espera, titila.

**Proyectos** (en Ajustes): guardar, guardar como, abrir y borrar proyectos
completos. Se guardan en `~/.config/goa/proyectos/`.

## Escenas y energía

En **Tocar**:

- **Escenas** (hasta 8): "+ Guardar lo que suena" guarda una foto de todo lo
  musical: géneros, tónica y escala, progresión, estilos, variantes, ajustes de
  cada motor, cuáles suenan y la energía. No guarda destinos ni canales, así que
  sigue sirviendo si cambias cables. En **Editar** puedes guardar encima de una o
  borrarla.
- Al tocar una escena, el motor **llega a ella de a poco** en los compases de
  *Transición* (al compás, 4, 8 o 16), empezando en el próximo compás:
  - lo continuo (densidad, largo de notas, oscuridad, swing, tensión, fuerza…)
    se mueve un poco en cada compás;
  - lo que no se puede mover de a poco (estilo, variante, progresión, escala)
    cambia en el último compás de la transición;
  - los motores que se prenden **entran de a uno** (primero los pads, después
    las secuencias, el diálogo y al final el bajo) y los que se apagan salen de
    a uno;
  - si cambia la **tonalidad**, los dos compases antes del cambio suena un
    **acorde puente** que es de las dos escalas (de F frigio a C menor, por
    ejemplo, Fm: el iv de la nueva) y después la progresión nueva parte en su i.
    En Armonía › *Entre escenas* ves qué tan emparentada es cada escena con lo
    que suena.
  Mientras llega, la escena titila y dice cuántos compases faltan. Lo que
  cambies en la app durante la transición se suma al destino.
- **Energía** (0 a 100; 50 = cada motor tal como lo dejaste): mueve juntas la
  densidad y los acentos de las secuencias y el bajo, las notas fantasma, la
  evolución, la fuerza, el pulso de los pads (y sus suspensiones, más en la
  calma), el espacio y los golpes del diálogo y la tensión armónica. Nunca
  salta: llega como mucho 10 por compás (arriba dice, por ejemplo, 40 → 80).
  La densidad y las notas fantasma se multiplican (del 40 % en calma al 160 %
  en clímax): una densidad baja sigue siendo baja con la energía arriba, y lo
  que tienes en 0 queda en 0. Cada escena guarda su energía.

## Piloto automático

En Tocar, **Piloto automático** arma la forma del tema solo, por frases:

| Sección | Compases (normal) | Qué pasa |
|---|---|---|
| Intro | 16 | pads y secuencias, sin bajo ni diálogo; energía baja |
| Build | 16 | entra el bajo, el diálogo a la mitad; la energía sube de a poco |
| Clímax | 32 | todo, con energía alta |
| Break | 8 | se van el bajo y las secuencias; los pads quedan sostenidos, con más suspensiones y entrada escalonada |
| Drop | 32 | todo vuelve junto, en el uno, con energía arriba |

Después del drop vuelve al build. *Secciones* corta, normal o larga cambia los
largos (la mitad o el doble). Arranca en el próximo borde de frase: en la
intro si la energía está baja, en el build si ya está arriba.

**Tomar el control:** toca una sección para saltar a ella (entra en el próximo
compás). Si mueves la energía, el piloto se apaga y la energía queda donde la
pusiste. Los motores que calla el piloto dicen "piloto" en sus botones; al
apagarlo vuelve todo lo que dejaste prendido. El piloto no cambia tu
configuración ni tus escenas: puedes lanzar escenas mientras anda.

## Variación larga (el director)

Para que nada suene igual durante mucho rato sin perder la identidad, en Tocar
está **Variación larga**. Cada 16 o 32 compases (en el borde de la frase), el
director deshace lo que hizo en el período anterior y, según cuánta variación
pediste, elige uno o dos cambios para el período que empieza:

- **variante hermana:** una secuencia cambia un 20 % de sus notas, con el mismo ritmo;
- **vuelve un motivo:** una secuencia retoma un patrón de hace uno o más
  períodos, transformado (corrido, una tercera arriba o en espejo);
- **una octava arriba** en una secuencia;
- **cambio de roles:** la llamada pasa al sinte de la respuesta y al revés;
- **pads que solo guían:** se callan un período y siguen guiando la armonía;
- **protagonista:** un motor queda adelante y los demás tocan menos notas.

No cambia tu configuración: todo vuelve solo al terminar el período. Una
secuencia **congelada** queda fuera. Debajo dice qué está haciendo en este
período. Es determinista: la misma configuración hace el mismo viaje.

## Modo canción

Pestaña **Canción**. Apagado (lo normal), el motor funciona en **modo libre**,
igual que siempre.

**Armar la canción:** en modo libre, deja sonando lo que quieres para una parte
(secuencias, pads, bajo…) y toca **+ Parte con lo que suena**: le pones nombre
(Intro, Build…) y cuántos compases dura, y guarda lo que suena como su escena.
Cada parte tiene:

- **Escena:** lo que suena en esa parte. Varias partes pueden usar la misma.
- **Energía al empezar y al terminar:** la curva de la parte (por ejemplo, un
  build que sube de 35 a 70).
- **Entrada:** *suave* (llega de a poco en los compases antes, como mucho la
  mitad de la parte anterior) o *de golpe* (entra de una en su primer compás,
  como un drop). En los dos casos, los motores entran y salen justo en el
  primer compás de la parte.
- **Los pads acompañan la subida** (opcional, apagado por defecto): a lo largo de
  la parte el pulso de los pads acelera (2, 4, 6 y 8 golpes por compás), los
  golpes se acortan, suben de fuerza y suman una voz al final. Ideal para los
  rises. En la parte siguiente vuelven a lo de su escena.
- **Más apoyos a la subida** (cada uno opcional, apagados por defecto; actúan
  en el final de la parte: los 2 últimos compases, o el último si la parte
  tiene menos de 8):
  - **Roll de las secuencias:** repiten un tiempo, después medio tiempo y al
    final una semicorchea, como un loop que se encoge antes del cambio.
  - **Corte de bajo:** el bajo se calla para que la parte siguiente pegue más.
  - **Acorde de tensión:** el último compás va a un acorde que pide resolver
    (♭II en frigio, V en menor armónica, ♭VII en menor) y la parte siguiente
    parte en la i. Lo siguen los pads, el bajo y las secuencias guiadas.
  - **Hueco:** el último tiempo de la parte, el motor queda en silencio.
- **Escuchar** pone la escena de la parte para seguir armándola, y **Guardar lo
  que suena** la actualiza.

**Tocarla con la Circuit:** prende el modo canción y arma en la Circuit su
cadena de escenas con los **mismos largos**. Al dar Play en la Circuit los dos
parten desde el principio y cambian de parte en el mismo compás. La Circuit no
avisa por MIDI cuando cambia de escena, así que el motor cuenta compases desde
el Play: si saltas una escena a mano en la Circuit, usa **Saltar aquí** en la
parte que corresponde. Al terminar, la canción **repite** (como la cadena de la
Circuit) o **se queda en la última** parte. La app muestra en qué parte va, el
tiempo y cuántas escenas de la Circuit necesita (tiene 16, de hasta 16 compases
cada una con patrones de 32 pasos).

En modo canción la energía la maneja cada parte y el piloto automático queda
apagado.

**Plantillas:** *Cargar plantilla…* pone una estructura lista. Cada una tiene su
proyecto gemelo en la Circuit (percusión con el banco FROM GOA TO PSYT):

**Por qué las subidas duran 8 compases:** en la Circuit una escena repite su cadena
de patrones, y una cadena de 4 patrones dura 8 compases. Una subida de 16 sonaba
como dos subidas seguidas; con 8 hay un solo redoble, un riser y un swell que llega
a la parte siguiente. Las demás partes son de 16.

**Actualizar una canción ya armada:** si el template cambió (por ejemplo, partes
que pasaron de 8 a 16 compases), en Canción usa **Actualizar con la plantilla…**.
Pone los largos de la plantilla y suma las partes que falten (sin escena), y deja
tus escenas, energías, entradas y apoyos a la subida. Tus partes que la plantilla
no tiene quedan al final. «Cargar plantilla…», en cambio, reemplaza todo.

**Samples de los templates:** se eligieron midiendo el audio del banco FROM GOA
TO PSYT (energía por bandas, fundamental y caída de cada muestra). Bombos cortos
con poco sub (1, 3, 4, 5, 6, 7) y nivel 105; nada con energía fuerte bajo 150 Hz
en las demás pistas, para no chocar con el bajo del motor; el crash solo en el uno
de las partes (de ride hace un hat abierto); sin la atmósfera de 3 s ni los booms
y blips sub en los loops. En los géneros chill (6 a 9) la pista 4 es percusión
orgánica suave: el crash (suave) solo al empezar las partes principales, un swell
suave que llega a la parte siguiente y el riser solo en las subidas; en el ambient,
como mucho un swell cada 16 compases. La tabla completa está en `herramientas/circuit_cancion.py`.

- **Template 1 · Psytrance** (proyecto 32): 140 BPM, 16 escenas,
  240 compases (6:51; las subidas de 8).
- **Template 2 · Dark minimal** (proyecto 33): 142 BPM, 16 escenas, 240 compases
  (6:46; las subidas de 8). Misma forma que los demás (intro, grooves, break,
  rise, clímax, outro); estilo Zenonesque: pocos elementos, glitch solo agudo.
- **Template 3 · Goa clásico** (proyecto 34): 140 BPM, 16 escenas,
  240 compases (6:51; las subidas de 8). Bombo tipo 909, snare, toms que rematan, breakdown largo, ride.
- **Template 4 · Goa tribal** (proyecto 35): 140 BPM, 16 escenas,
  240 compases (6:51; las subidas de 8). Toms afinados en llamada y respuesta sobre el clap, congas, ceremonia a medio tiempo.
- **Template 5 · Goa épico** (proyecto 40): 140 BPM, 16 partes, 224 compases (6:24). Arcos
  largos, redobles en dos olas, crash cada 8 compases.
- **Template 6 · Psy chill** (proyecto 41): 104 BPM con shuffle, 16 escenas,
  240 compases (9:14; las subidas de 8). Bombo redondo, clap largo, congas y blips. Escala dórica.
- **Template 7 · Chillgressive** (proyecto 42): 120 BPM, 16 escenas,
  240 compases (8:00; las subidas de 8). Hats rodando en semicorcheas, clap en 2 y 4, breaks largos. Escala menor.
- **Template 8 · Chillout** (proyecto 43): 92 BPM con swing, 16 escenas,
  240 compases (10:26; las subidas de 8). Beat quebrado, snare con cuerpo, shaker y congas. Escala menor.
- **Template 9 · Ambient** (proyecto 44): 76 BPM, 16 escenas, 240 compases
  (12:38). Misma forma que los demás, con subidas de 8 muy suaves (toms y shaker
  que crecen, un swell). Sin bombo fijo: latidos suaves, casi nada de FX.

Los templates 6 a 9 están pensados para su género del motor: elige el mismo
género en Música para que escalas, pads, bajo y secuencias calcen con el estilo.

Las partes vienen sin escena: elige qué suena en cada una con *Guardar lo que
suena*. En todos, el crash lleva reverb Hall y un poco de delay.

El proyecto de la Circuit se arma con `herramientas/circuit_cancion.py` (necesita
`pip install circuit-tracks-tools`), que toma los nombres y compases de la misma
plantilla (`goa/plantillas.py`). En la Circuit, Synth 1 es la «regla»: sus
patrones van vacíos y marcan el largo de cada escena; la percusión va en las
cuatro baterías.

## Parche por escena (Program Change)

Cada motor tiene en Salida MIDI el campo **Parche (Program Change)**: 0 no
cambia nada; de 1 a 128 le pide ese parche a su sinte. Se manda al dar Play y
cada vez que una escena o una parte de la canción lo cambia, justo en su primer
compás. Se guarda en las escenas, así cada parte puede tener su sonido. Si dos
motores van al mismo sinte y canal, manda el que está sonando. Funciona con
sintes que reciben Program Change (revisa que tu firmware lo tenga activo).

## Mutación de las secuencias

Cada secuencia evoluciona cada *Mutar cada* compases (en Motores › Variación):

- **Mutación de notas** cambia la altura de algunas notas. Cada mutación cambia
  al menos una, así el patrón nunca se queda pegado en la nota larga.
- **Mutación de ritmo** (opcional, apagada por defecto) cambia el ritmo de a
  poco: mueve una nota a un lugar vecino, agrega o quita una, o devuelve un
  lugar a como estaba. Respeta dónde caen las notas (el offbeat no pasa al
  bombo) y la cantidad se queda entre la mitad y una vez y media de la original.
- Con la **Variación larga**, tu patrón sigue mutando por debajo mientras suena
  una variante del director, y vuelve evolucionado.
- No muta si está **congelado**, si las dos mutaciones están en 0 o si el pedal
  está en 100 % (solo la nota larga). Otra variante, otro estilo u otro largo, o
  Stop y Play, parten de nuevo desde el patrón original.

## Cambios en vivo

Con el motor andando, nada se dispara de golpe al tocar la app:

- **Las secuencias** cambian al tiempo: una variante o un estilo nuevo se
  escucha de inmediato.
- **Todo lo demás** (pads, bajo, llamada y respuesta, tónica, escala, armonía,
  géneros) entra en el primer paso del **próximo compás**. Mientras espera, el
  compás en la app dice "entra al compás".
- En ese cambio nada se corta: las notas que suenan terminan solas, el sub del
  bajo sigue ligado y los pads pasan al acorde nuevo en ligado (las notas
  comunes siguen sonando, solo se mueven las otras).

## Géneros y Pegado ↔ Desplazado

Cada motor tiene su propio selector de género, independiente: los pads, la
llamada y respuesta y cada secuencia. Por ejemplo, pads ambient, un diálogo
chillgressive y un bajo psy chill. Elegir un género escribe sus valores en ese
motor y después puedes ajustar todo a mano; nunca toca destinos, canales,
fuerza ni variantes. La escala es común a todos (en Armonía, con armonía libre), para que nada
choque.

En **Armonía**, *Género para todo* es un atajo: pone la escala de ese género y
el mismo género en todos los motores, también en las secuencias.

En cada secuencia y en el bajo, el género solo cambia el estilo (y muestra los
suyos): tu swing, largo y demás ajustes se quedan como los dejaste. El
*Género para todo* (en Armonía) sí pone el perfil completo. En cada secuencia, el
género filtra sus estilos: Goa (rolling, galope, arpegio
de 3, ácido), psy chill (bombo, silencio, bajo, bajo), chillgressive (rolling,
euclidiano 7 de 16), chillout (notas largas en 3 de 16, casi solo raíz y quinta)
y ambient (notas muy largas en un patrón de 13 pasos que se desfasa).

- **Goa:** frigio, i–♭II, diálogo en corcheas pegado al beat.
- **Psy chill:** dórica, i–IV–i–♭VII con un pulso euclidiano suave en los pads.
- **Chillgressive:** menor, i–♭VI–♭VII–v cada 8 compases, diálogo en semicorcheas.
- **Chillout:** menor, acordes de séptima y novena juntos, notas largas.
- **Ambient:** lidia, drone, acordes de 16 compases con voces que entran de a una.

**Pegado ↔ Desplazado:** en 0 todo cae justo en la rejilla. Al subirlo, algunas
notas se corren una semicorchea (nunca el uno de la llamada) y las semicorcheas
débiles se atrasan un poco, como swing. Mueve la llamada, la respuesta y el
pulso de los pads; las secuencias no se corren. Cada voz puede tener su propio
ajuste (en su grupo Variación).

## Armonía guiada

Los pads son la guía armónica: saben qué acorde suena, cuál viene y en cuántos
pasos llega. En la pestaña **Armonía**:

- **Guiada** (por defecto): las secuencias y la llamada y respuesta siguen cada
  acorde. Los motivos conservan su ritmo y su forma; solo se ajustan las alturas.
  En las secuencias, los tiempos fuertes caen en notas del acorde y la **tensión**
  decide cuántas notas de paso quedan en los débiles. En el diálogo, las notas
  salen de su color (Luminoso ↔ Oscuro) y cada voz cierra su motivo en el acorde;
  ultra oscuro queda colgado a propósito.
- **Anticipar los cambios:** la última nota antes de un cambio de acorde lleva
  al que viene (una nota común se queda; si no, un paso de escala junto a él).
- **Libre:** cada motor cuenta sus notas desde su raíz, como antes.

Cada secuencia y la llamada y respuesta pueden tener su propia armonía (en sus
grupo Variación). Todo queda siempre dentro de la escala.

**Textura de los pads:** *Acordes* (como siempre), *Nota sola* (solo la raíz
de cada acorde, grave, moviéndose como un bajo: una guía clara para programar
tus secuencias encima) o *Raíz + acorde* (el acorde con su raíz una octava
abajo; ocupa una voz del sinte).

**Escala en la Circuit:** bajo la tónica y la escala, la app dice qué poner en
el botón Scales de la Circuit para que todo lo que toques quede dentro de la
escala del motor. Frigio dominante y lidia no existen en la Circuit: se usan la
menor armónica una quinta abajo y la mayor una quinta arriba (mismas notas).
La doble armónica tampoco: se usa la húngara menor una quinta abajo.

**Escalas misteriosas:** en Música está la **doble armónica** (bizantina,
1 ♭2 3 4 5 ♭6 7), que es el frigio dominante con séptima mayor. Con progresión
al azar usa I, ♭II, iii e iv.

**Escala de color** (en cada secuencia, grupo Notas): la secuencia toca en otra
escala mientras pads, bajo y diálogo siguen en la de Música. Opciones: doble
armónica, **persa** (1 ♭2 3 4 ♭5 ♭6 7) y **enigmática** (1 ♭2 3 ♯4 ♯5 ♭7 7).
Las dos últimas no tienen quinta justa, por eso solo existen como color: sobre
una base firme suenan misteriosas; como escala de todo se desarmarían. En
armonía guiada los tiempos fuertes igual caen en el acorde y el color aparece
en los débiles.

**♭2** (en cada secuencia, grupo Notas): cambia notas de los pasos débiles por
el medio tono sobre la raíz que suena, la tensión típica de las melodías de
psytrance. Los tiempos fuertes no se tocan. En 0 la secuencia queda como era.

Progresiones nuevas de los pads: **i – ♭VII – ♭VI – ♭VII** (va y vuelve sin
cerrar) e **i – ♭II – ♭VII – i**.

En los pads, **Suenan** apagado los deja callados pero guiando: útil para
escenas minimal donde el bajo y las secuencias caminan antes de que entren los
acordes. **Suspensiones** (en el grupo Ritmo, con ataque ligado): al cambiar de
acorde, una voz se queda colgada y resuelve un tiempo después.

Sin pads activos, la armonía es el acorde de la escala sobre tu nota larga: se
sigue, pero no se puede anticipar. Tus cambios de nota larga en vivo tampoco se
anticipan; el motor los sigue.

## Bajo

La tarjeta **Bajo** es un generador de líneas de bajo que sabe hacia dónde va
la armonía: toca la raíz del acorde de los pads y, según el **movimiento**,
salta a la octava, la quinta o una nota de paso. Con armonía guiada y
"anticipar", la última nota antes de un cambio de acorde lleva a la raíz que
viene. Sin pads, o en armonía libre, sigue su nota larga.

Estilos (el género muestra los suyos, y puedes cambiarlos al vuelo):

- **Rolling:** K B B B, el clásico del Goa y el full-on.
- **Full-on:** rolling con una celda melódica por tiempo (raíz, quinta, octava, ♭2).
- **Tresillo:** bombo y dos notas en tresillo.
- **Galope:** K · B B.
- **Saltado:** K B · B.
- **Offbeat:** una corchea a contratiempo (progressive, psy chill).
- **Chillgressive:** rolling oscuro, notas cortas y un acento que se mueve.
- **Dub** (chillout): en el uno, antes del tres y en el tres; notas largas.
- **Sub** (ambient): una nota grave por acorde, ligada.

Con el motor andando, cualquier cambio del bajo (el estilo, por ejemplo) entra
justo en el próximo compás. Si el patrón de base es el mismo, sigue con lo que
ya había mutado.

**Variación:** *Evolución* cambia un golpe cada *mutar cada* compases (otra
nota, un silencio, uno nuevo o corrido) y se acumula, con algunos que vuelven a
como eran. *Transponer* corre el bajo en grados de escala (4 = la quinta). En los
grupos Ritmo y Notas: densidad, swing, slide (para un sinte en legato con glide),
acentos y notas fantasma.

En los estilos psy nunca cae en el tiempo del bombo. Los compases de una frase
se repiten igual y, con **remates**, el último cierra con un remate. Cada estilo
tiene dos remates clásicos que se alternan (en el rolling: rebote de octava y una
corrida que baja). Controles (grupo Ritmo):
- **Variación del remate** (0 = siempre los dos clásicos): en cada frase cambian
  al azar las alturas de algunas notas. Nunca se quitan ni se agregan notas.
  Repetible con la variante.
- **Nota larga en el remate** (0 = nunca): en esa proporción de frases, una nota
  del remate (nunca la última) se alarga hacia la siguiente y termina antes de que
  empiece: nunca se pisan. **Largo de la nota larga**: cuánto del espacio hasta la
  siguiente ocupa (75 % por defecto). A lo más una por remate.
- **Rango de las notas que cambian**: hasta la quinta o hasta la octava.
- **Remate marcado**: 0 = el remate suena como el resto (puede llevar slide);
  arriba, sus notas van sin slide, se vuelven a atacar y con un acento suave (con su
  largo normal, para que no suene a corte).

**Notas que suben** (0 = siempre en la raíz): en vez de quedarse en la raíz, la
última nota de algunos tiempos sigue un camino que sube, como los bajos full-on.
Bajo hasta un paso de escala, al medio hasta la quinta (y suben dos notas por
tiempo), alto hasta la octava en los tres tiempos. Hay un camino para los compases
pares y otro para los impares, así la línea va variando. Nunca cae en el bombo.
No aplica al dub ni al sub. Es monofónico: nunca suenan dos notas juntas.

## Llamada y respuesta

Dos voces que conversan con **ritmos euclidianos**: cada una reparte sus golpes
de la forma más pareja posible en el compás. Todo cae en la rejilla y la
llamada siempre tiene un golpe en el uno, así nada se arrastra contra el bombo.

- **Quién llama:** *el motor* (con su nota larga) o *yo, en vivo*: el motor
  escucha dónde tocas en cada compás y en el siguiente responde en tus huecos.
- **Cómo conversan:** *entrelazado* (la respuesta toca solo en los huecos de la
  llamada, en el mismo compás) o *por turnos* (alternan por compases).
- **Rejilla:** corcheas (siempre con el bombo) o semicorcheas (más sincopado).
- **Golpes** de cada voz y **Espacio:** cuántos lugares espera la respuesta
  después de cada nota de la llamada. Si no caben todos sus golpes, la app
  muestra cuántos caben.
- **Luminoso ↔ Oscuro:** elige las notas. Luminoso: raíz, ♭3, quinta, ♭7.
  Oscuro: con ♭2 y ♭6. Ultra oscuro: medio tono contra la raíz.
- **Variante y mutación:** cada cierto número de compases cambia una nota o
  gira el patrón (la llamada sigue cayendo en el uno).
- **Sigue a los pads** (por defecto): usa su escala y la raíz de cada acorde.
- Ninguna nota pisa a la siguiente, aunque las dos voces vayan al mismo sinte.

## Control de las frases (todo opcional)

**Filtro de notas** (grupo «Filtro y orden» en cada secuencia y en cada voz del
diálogo): la seed arma las notas y el filtro decide cuáles pasan. Se prende y se
apaga con su interruptor; apagado suena todo y el filtro queda guardado.
- Al prenderlo parte **cerrado: no suena nada**. Vas tocando los pasos que quieres
  oír (● pasa) y se van escuchando; tocar de nuevo un paso lo cierra.
- Los pasos del bombo (1, 2, 3, 4) llevan siempre una marca rosada abajo, aunque
  estén abiertos.
- El filtro no inventa notas: si la seed no tiene nota en un paso abierto, ahí no
  suena nada. Por eso **cambiar la seed cambia lo que pasa** (en las secuencias,
  subir la densidad también agrega notas).
- En el diálogo, una nota que cae en un paso cerrado se corre al abierto más
  cercano (la frase conserva sus notas; si dos caen en el mismo, suena una). En
  corcheas cada lugar ocupa 2 pasos. La seed también cambia el ritmo de las voces.
- Atajos: Abrir todo, Tiempos, Contras, Sin bombo, Inicio, Final, Cerrar todo.
- **🎲 Goa / 🎲 Psy**: un filtro al azar pero con sentido. Goa deja pasar casi todo
  (rolling); Psy cierra los tiempos al bombo y al bajo y abre contratiempos y
  síncopas. Siempre queda al menos un paso abierto.
- **A veces (?)**: con el pincel «? A veces», en cada compás ese paso deja pasar
  la nota con la probabilidad que pongas (50 % por defecto). Repetible con la seed.
- **El filtro muta solo** (0 = no): cada «mutar cada» compases abre o cierra uno o
  dos pasos, al estilo del último 🎲. «Fijar» o «Congelar» lo detienen.
- **Orden**: adelante, atrás, péndulo o al azar. En las secuencias ordena los pasos
  del patrón; en el diálogo, las notas del motivo. El filtro no se mueve.
- Los moldes de antes (versiones hasta la 0.42) quedan con el filtro prendido y sus
  pasos libres abiertos.

**Otra frase · Volver · Fijar** (en cada voz del diálogo): «Otra frase» cambia
las notas y el ritmo de esa voz sin tocar la seed ni la otra voz; «Volver» trae
la anterior (se guardan todas: frase 1, 2, 3…); «Fijar» congela la frase para que
la mutación no la cambie.

**La respuesta contesta** (Voces del diálogo): con lo suyo (como siempre), en
**eco** (repite las notas de la llamada), en **espejo** (la llamada dada vuelta:
si sube, la respuesta baja) o **cerrando** (con sus notas, pero termina en la raíz).

## Si algo falla

- `goa-log` muestra lo que está haciendo el motor.
- Copia lo que sale y cuéntame qué escuchaste: con eso corregimos.

## Probar sin hardware

```
python3 -m pruebas.simular
```

Simula la Circuit y muestra las notas generadas en una grilla por compás.
`python3 -m pruebas.dialogo` prueba la llamada y respuesta en los dos modos.
`python3 -m pruebas.en_vivo` prueba que mover algo en la app no vuelva a atacar los pads
y que el género de una secuencia o del bajo no mueva tus ajustes.
`python3 -m pruebas.bajo` prueba el generador de bajo en todos los géneros.
`python3 -m pruebas.armonia` prueba la armonía guiada, el modo libre, los pads
que solo guían y las suspensiones.
`python3 -m pruebas.generos` prueba los perfiles de género, el pulso de los pads
y el control Pegado ↔ Desplazado.
`python3 -m pruebas.mutaciones` prueba que las mutaciones avancen y que mover
un control en la app no las borre.
`python3 -m pruebas.escenas` prueba las escenas: la transición gradual, que los motores
entren de a uno, el acorde puente al cambiar de tonalidad y que la energía llegue de a poco.
`python3 -m pruebas.director` prueba la variación larga: que entre solo en el borde de cada
período, que todo vuelva al terminar y que respete las secuencias congeladas.
`python3 -m pruebas.piloto` prueba el piloto: el orden y largo de las secciones, quién suena en
cada una, la energía (que el drop entre de golpe) y que al apagarlo vuelva todo.
`python3 -m pruebas.app` levanta la app con una Circuit simulada en http://localhost:8080.
