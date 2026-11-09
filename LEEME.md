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
- **Proyectos:** guardar, guardar como, abrir y borrar proyectos completos.
  Se guardan en `~/.config/goa/proyectos/`.

## Llamada y respuesta

Dos voces que conversan dejando espacio, sin repetir frases.

- **Quién llama:** *el motor* (con su nota larga, como las secuencias) o
  *yo, en vivo*: tocas tu frase en el canal de escucha y, cuando dejas de
  tocar, el motor espera el silencio que elijas y responde en el próximo tiempo.
- **Quién responde:** cualquier destino y canal. El botón "Responder en el
  mismo sinte" manda la respuesta al sinte que llamó (o al canal donde tocas).
- **Cada voz tiene su carácter:** escala propia (o la de Música), relación con
  la nota larga (unísono a octava), octava, ámbito, contorno (sube, baja, arco,
  valle, libre), ritmo, densidad, gate, saltos, matices y cómo **termina**:
  en tensión (♭2, quinta, ♭7: suena a pregunta) o en reposo (la raíz: resuelve).
- **Cómo responde:** *variación* (mismo ritmo y dirección, otras notas),
  *espejo* (la frase invertida), *eco* (tu frase con el carácter de la
  respuesta) o *nueva* (una frase propia).
- **Espacio y tiempo:** compases de cada voz, pausa entre ambas y descanso
  después. **Evolución** cambia un poco la frase en cada vuelta; en 0 se repite igual.

Para tocar la llamada en vivo, tus notas tienen que llegar a la Pi: por ejemplo
tocando en vivo una pista de la Circuit (Note Tx activo). En modo dongle esas
notas se reenvían a la cadena, así que escuchas tu llamada y el motor responde.

## Si algo falla

- `goa-log` muestra lo que está haciendo el motor.
- Copia lo que sale y cuéntame qué escuchaste: con eso corregimos.

## Probar sin hardware

```
python3 -m pruebas.simular
```

Simula la Circuit y muestra las notas generadas en una grilla por compás.
`python3 -m pruebas.dialogo` prueba la llamada y respuesta en los dos modos.
`python3 -m pruebas.app` levanta la app con una Circuit simulada en http://localhost:8080.
