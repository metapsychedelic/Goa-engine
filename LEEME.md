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

Desde tu computador, en la carpeta donde descomprimiste este zip:

```
scp -r goa-engine tu-usuario@goa.local:~/
ssh tu-usuario@goa.local
cd goa-engine
./install.sh
sudo reboot
```

## 3. Configurar la Circuit Tracks

- En el **Setup** de la Circuit activa el envío de reloj (Clock Tx) y de notas
  MIDI (Note Tx) para las pistas.
- Elige una pista para la nota larga y ponle el **canal 4** (o cambia
  `canal_disparo` en la configuración). Baja su volumen si es un sinte interno.

## 4. Primera prueba

Conecta la Circuit y la FM-1 a la Pi por USB y entra por `ssh`:

```
goa-ports                         # ¿aparecen la Circuit y la FM-1?
goa-ports --probar FM-1 2         # ¿suena la FM-1?
goa-ports --escuchar Circuit      # dale Play: ¿aparece "reloj OK" con el BPM?
goa-debug                         # mantén una nota en el canal 4 y mira las notas
```

Si los nombres de los puertos no contienen "Circuit" o "FM-1", edita
`~/.config/goa/config.toml` con la parte del nombre que muestra `goa-ports`.

## 5. Ajustar

```
nano ~/.config/goa/config.toml
goa-restart
```

Cada opción está explicada dentro del archivo: tonalidad, escala, estilo,
posición rítmica, largo, gate, seed, mutación y más.

## Si algo falla

- `goa-log` muestra lo que está haciendo el motor.
- Copia lo que sale y cuéntame qué escuchaste: con eso corregimos.

## Probar sin hardware

```
python3 -m pruebas.simular
```

Simula la Circuit y muestra las notas generadas en una grilla por compás.
