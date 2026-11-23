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

1. Motores › **Obertura**: modo (Épico, Chill o Cine), carácter (batalla, frigia o trágica
   en el épico; etéreo, lamento o ritual en el chill; neón, títulos o cosmos en el cine),
   forma, «Tema del track», «En loop» si quieres que no termine, largo (frases de 8
   compases), la escena «orquesta» y la escena de vuelta.
2. En el modo canción, una parte para la obertura (con sus otros motores callados) que dure
   **8 × frases + 1** compases (el +1 es el compás de preparación para cambiar de escena),
   y después la parte del drop.
3. «Otra» en la Variante cambia la obertura (progresión, galope, llamada de cuerno, tema y
   taikos) sin cambiar el carácter.

## Escena chill (modo Chill)

Para el modo **Chill** arma otra escena con la misma disposición de pistas y canales,
pero con sonidos tranquilos. Pon su número en «Escena «orquesta»» cuando uses el chill.

| Pista | Canal | Capa en el chill | Qué sonido buscar |
|---|---|---|---|
| 1 | 1 | **Colchón** | Cuerdas lentas o un string pad (ataque y release largos). Acordes de 3 a 5 notas. |
| 2 | 2 | **Melodía** | Una voz sola: flauta, chelo, piano o un lead suave. Etéreo pide algo alto (flauta, violín), lamento algo grave (chelo), ritual algo percutido (piano, kalimba, marimba). Monofónico sirve. |
| 3 | 3 | **Coro** | El mismo coro «aah/ooh» o un pad de voces aireado. |
| 4 | 4 | **Percusión suave** | Taiko o tom grave suave (36), un shaker, rim o tambor de mano para el fantasma (38) y un platillo en swell o un reverse cymbal (49). |

La melodía va por la pista de los cuernos: en una escena épica suena con metales, en la
chill con lo que pongas ahí.

## Escena cine (modo Cine, sintes a lo Vangelis)

Otra escena con la misma disposición. Las melodías las inventa el motor (no copia ningún
tema); el carácter viene de los sonidos y de cómo se tocan.

| Pista | Canal | Capa en el cine | Qué sonido buscar | Ajustes |
|---|---|---|---|---|
| 1 | 1 | **Brass de sinte** | Un brass analógico polifónico (estilo CS-80 / «Synth Brass», «Poly Brass»). | Ataque lento (0,3-0,5 s) y filtro que se abre con la envolvente. Release largo. Reverb larga. |
| 2 | 2 | **Lead** | Un lead de sierra con vibrato que entra solo (delayed vibrato), o un brass solo. | **Rango de bend igual al de Yantra** (por defecto 2 semitonos): el motor hace entradas deslizadas y caídas con el bend. Delay y reverb largas. |
| 3 | 3 | **Arpegio / pulso** | Neón: un pluck o arpeggio synth suave. Títulos: un bajo o sinte de pulso seco (las octavas en semicorcheas). Cosmos: campanas (bell, FM). | Release corto en el pulso, más largo en el arpegio. |
| 4 | 4 | **Timbal, caja y gong** | Timbal o tom grande (36), una caja con mucha reverb (38) y un gong o crash enorme (49). | Reverb larga en la caja. |

## Formas y tema del track

- **Forma**: Crece (de a poco), Golpe (entra con todo, baja y vuelve), Ola (crece, falso
  final a la mitad con golpe y silencio en el épico, y vuelve más fuerte) o Respiro (se
  vacía antes del remate).
- **Tema del track**: la llamada, el tema y la melodía usan las primeras notas de la 1.ª
  secuencia, así la intro anuncia lo que viene en el drop.

## Rango de las capas

Todo sale en la tonalidad del tema, con la tónica entre E2 y D#3:

- Cuerdas graves: una octava bajo la tónica (y la tónica misma desde la etapa 3).
- Cuernos: desde la tónica + 12 (acordes) hasta + 36 (el tema en octavas).
- Coro: tónica + 12 y su quinta.

Si un sonido queda muy grave o agudo, súbele o bájale la octava en la MC-101 (Tone › Octave).
