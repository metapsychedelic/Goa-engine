# Molde de la escena «orquesta» en la MC-101

La obertura de Yantra (motor **Obertura**) manda cuatro capas, cada una por un canal MIDI.
En la MC-101 se arma **una escena** con estos sonidos y Yantra cambia a ella al empezar la
obertura, y de vuelta a tu escena psy justo antes del drop. La MC-101 no cambia de sonido por
Program Change en la pista: cambia de **escena** con un Program Change en su **canal de
control**.

## Antes de empezar (una sola vez)

- **Canal de control** de la MC-101: el mismo que pongas en Yantra (por defecto 16).
  Es el que ya usa el Scatter.
- **Canales de las pistas**: uno por pista, como en la tabla de abajo (1 a 4 por defecto;
  se cambian en Yantra, en Obertura › Capas y canales).
- **Master Step Length en 16**: así la MC cambia de escena justo en el uno del compás.
  Yantra manda el cambio en la mitad del compás anterior (el compás de preparación).

## Las cuatro pistas de la escena

| Pista | Canal (Yantra) | Capa | Qué sonido buscar | Ajustes |
|---|---|---|---|---|
| 1 | 1 | **Cuerdas graves** | Chelos / contrabajos / «Low Strings» o un ensemble de cuerdas con ataque rápido (marcato, staccato). Evita los de ataque lento: el galope son semicorcheas. | Polifónico. Release corto. Reverb media. |
| 2 | 2 | **Cuernos / metales** | Cuernos (horns), trombones, «Brass» grave o un ensemble de metales. Mejor oscuro que brillante. | Polifónico (acordes de 3-4 notas y el tema en octavas). Release medio. Reverb alta. |
| 3 | 3 | **Coro** | Coro de voces «aah» u «ooh» (Choir / Vox). Si no hay, un pad de cuerdas lento y oscuro. | Polifónico (raíz y quinta). Ataque lento. Reverb alta. |
| 4 | 4 | **Percusión de guerra** | Un kit de batería con toms graves o taikos, un tambor seco y un golpe grande (crash, orchestra hit o un timbal). | Ver el mapa de notas. |

### Mapa de notas de la percusión (pista 4)

| Golpe | Nota (Yantra) | Qué poner en ese pad |
|---|---|---|
| Taiko | 36 (C1) | El tom o bombo más grave y grande (taiko, «big drum», floor tom). |
| Tambor de guerra | 38 (D1) | Un tambor seco y más agudo (snare sin bordonas, tom alto, frame drum). |
| Golpe de orquesta | 49 (C#2) | Un crash largo, un orchestra hit o un timbal con mucha cola. |

Si tu kit tiene esos sonidos en otros pads, cambia las notas en Yantra (Obertura › Capas y
canales) en vez de mover los sonidos.

## La escena psy (la de vuelta)

Es la escena que usas normalmente para el tema (bajo, FX, loops). Pon su número en Yantra en
**«Escena a la que vuelve para el drop»**. El cambio sale en el silencio de un tiempo y medio
del final de la obertura, así la escena psy entra justo con el primer bombo del drop.

## En Yantra

1. Motores › **Obertura**: carácter (batalla, frigia o trágica), largo (frases de 8
   compases), la escena «orquesta» y la escena de vuelta.
2. En el modo canción, una parte para la obertura (con sus otros motores callados) que dure
   **8 × frases + 1** compases (el +1 es el compás de preparación para cambiar de escena),
   y después la parte del drop.
3. «Otra» en la Variante cambia la obertura (progresión, galope, llamada de cuerno, tema y
   taikos) sin cambiar el carácter.

## Rango de las capas

Todo sale en la tonalidad del tema, con la tónica entre E2 y D#3:

- Cuerdas graves: una octava bajo la tónica (y la tónica misma desde la etapa 3).
- Cuernos: desde la tónica + 12 (acordes) hasta + 36 (el tema en octavas).
- Coro: tónica + 12 y su quinta.

Si un sonido queda muy grave o agudo, súbele o bájale la octava en la MC-101 (Tone › Octave).
