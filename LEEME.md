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

Si los nombres de los puertos no contienen "Circuit" o "FM-1", edita
`~/.config/goa/config.toml` con la parte del nombre que muestra `goa-ports`.

## 5. La app en el celular

Con el celular en la misma red Wi-Fi que la Pi, abre **http://goa.local:8080**.
Cada cambio se aplica en vivo, sin cortar el sonido, y queda guardado.
En el iPhone puedes agregarla a la pantalla de inicio desde Compartir.

Si `goa.local` no abre (pasa en algunos Android), usa la IP de la Pi:
corre `hostname -I` en la Pi y abre `http://LA-IP:8080`.

También puedes editar a mano `~/.config/goa/config.toml` y correr `goa-restart`;
las opciones están explicadas en `config.ejemplo.toml`.

## Pads y drones

Sección **Pads y drones** de la app: progresiones lentas de estilo Goa y
psytrance (i–♭II frigio, épica, andaluza, drone modal...), con voces que se
mueven lo mínimo entre acordes, drone opcional en la raíz, variación y rasgueo.
Con "Las secuencias siguen al acorde" (en Música), las secuencias Goa cambian
de nota base junto con los pads. Pads en la MicroFreak (canal 3, hasta 4 voces)
y Goa en la FM-1 (canal 4), o al revés: cada máquina toca un solo sonido a la vez.

## Disparador y proyectos

- **Guardar como clip** (en cada secuencia) guarda su carácter: estilo, seed,
  afinación y mutación.
- **Disparador:** una fila por secuencia. Toca un clip y entra en el próximo
  compás de la Circuit; mientras espera, titila. Los clips siguen mutando.
- **Clips de diálogo:** en Llamada y respuesta, "Guardar como clip" guarda la
  conversación completa: quién llama (motor o en vivo), destinos y canales,
  tiempos, cómo responde y el carácter de cada voz. En el disparador aparecen en
  la fila *Llamada y respuesta*; al lanzar uno entra en el próximo compás con
  todo ese seteo, y la sección queda mostrando lo que suena.
- **Proyectos:** guardar, guardar como, abrir y borrar proyectos completos.
  Se guardan en `~/.config/goa/proyectos/`.

## La app

Cada módulo (Proyecto, Disparador, Música, Pads, Llamada y respuesta, Conexión
y cada secuencia) se abre y cierra tocando su título; la app recuerda cómo los
dejaste. El interruptor del título prende o apaga el módulo sin abrirlo.
Arriba quedan los controles para tocar en vivo; lo demás está en "Más ajustes".
Para encontrar una buena secuencia, prueba variantes con **Otra**; si saltaste
una que sonaba bien, **Anterior** vuelve a ella (recuerda las últimas 20).

## Géneros y Pegado ↔ Desplazado

Cada motor tiene su propio selector de género, independiente: los pads, la
llamada y respuesta y cada secuencia. Por ejemplo, pads ambient, un diálogo
chillgressive y un bajo psy chill. Elegir un género escribe sus valores en ese
motor y después puedes ajustar todo a mano; nunca toca destinos, canales,
fuerza ni variantes. La escala es común a todos (en Música), para que nada
choque.

En **Música**, *Género para todo* es un atajo: pone la escala de ese género y
el mismo género en todos los motores, también en las secuencias.

En cada secuencia, el género filtra sus estilos: Goa (rolling, galope, arpegio
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
ajuste (en sus "Más ajustes").

## Armonía guiada

Los pads son la guía armónica: saben qué acorde suena, cuál viene y en cuántos
pasos llega. En **Música → Armonía**:

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
"Más ajustes"). Todo queda siempre dentro de la escala.

En los pads, **Suenan** apagado los deja callados pero guiando: útil para
escenas minimal donde el bajo y las secuencias caminan antes de que entren los
acordes. **Suspensiones** (en "Más ajustes", con ataque ligado): al cambiar de
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
como eran. *Transponer* corre el bajo en grados de escala (4 = la quinta). En
"Más ajustes": densidad, swing, slide (para un sinte en legato con glide),
acentos y notas fantasma.

En los estilos psy nunca cae en el tiempo del bombo. Los compases de una frase
se repiten igual y, con **remates**, el último cierra con un remate que alterna
entre dos variantes. Es monofónico: nunca suenan dos notas juntas.

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

## Si algo falla

- `goa-log` muestra lo que está haciendo el motor.
- Copia lo que sale y cuéntame qué escuchaste: con eso corregimos.

## Probar sin hardware

```
python3 -m pruebas.simular
```

Simula la Circuit y muestra las notas generadas en una grilla por compás.
`python3 -m pruebas.dialogo` prueba la llamada y respuesta en los dos modos.
`python3 -m pruebas.bajo` prueba el generador de bajo en todos los géneros.
`python3 -m pruebas.armonia` prueba la armonía guiada, el modo libre, los pads
que solo guían y las suspensiones.
`python3 -m pruebas.generos` prueba los perfiles de género, el pulso de los pads
y el control Pegado ↔ Desplazado.
`python3 -m pruebas.mutaciones` prueba que las mutaciones avancen y que mover
un control en la app no las borre.
`python3 -m pruebas.app` levanta la app con una Circuit simulada en http://localhost:8080.
