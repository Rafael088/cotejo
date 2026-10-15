# Logo de Cotejo

**El logo es la palabra: «Cotejo», con una C que se cierra con un check como primera letra.**
La C, en el color del texto, es el trabajo que trae el agente; el check, en Verde Hecho, es lo
que pone la persona. El brazo largo del check sale por la boca de la C y flota sobre la «o»:
sin él, la C queda a medias y la palabra también. Esa misma C, sola, es el ícono de la app, el
favicon y el botón de la barra.

Abre `brand-showcase.html` para verlo todo junto, con los detalles señalados.

## Los detalles

- **La C tiene el trazo de las letras de Sora** (140 unidades, como la «o»), y mide lo que una
  mayúscula: se lee como letra, no como un ícono pegado delante de la palabra.
- **La C va cortada a escuadra y el check lleva puntas redondas**: la máquina y la mano.
- **La punta de arriba de la C la corta una recta paralela al brazo del check**, con el aire
  justo: la boca queda como una ranura hecha a la medida del check.
- **La punta de abajo va cortada en horizontal**, igual que las puntas de la «c» de Sora.
- **Lo único verde es el check.**

## Cómo se regenera

Todo sale de `generar.py`: el kit de esta carpeta, el símbolo de la app, el ícono del menú y el
de la barra. Se edita la geometría ahí y se vuelve a correr; nada se toca a mano:

```sh
python3 docs/marca/generar.py        # SVG y, si hay rsvg-convert, los PNG
python3 empaquetado/windows/icono.py # el .ico de Windows
```

`brand-showcase.html` lleva el logo en línea en el héroe y en el esquema anotado: si la
geometría cambia, hay que volver a pegarlos (salen de `palabra_logo()` y `c_cortada()`).

## Archivos

| Archivo | Para qué |
| --- | --- |
| `logo-full.svg` / `.png` | El logo, «Cotejo», sobre fondo claro |
| `logo-full-oscuro.svg` / `.png` | El mismo sobre fondo oscuro |
| `logo-mark.svg`, `logo-mark-oscuro.svg` | La C sola, sobre claro y sobre oscuro |
| `logo-wordmark.svg` | El logo a 180 de ancho, para cabeceras y pies |
| `logo-white.svg`, `logo-black.svg` | Una tinta: grabado, sello, fondos de color |
| `logo-icon.svg`, `logo-icon-512.png`, `-192.png`, `apple-touch-icon.png` | Ícono de app y de la web |
| `favicon.svg` | Favicon: placa negra y trazo engrosado para 16–32 px |
| `../../data/marca/cotejo-logo.svg` | Cabecera de CotejoBoard («Cotejo» + «Board»); `tareas/app/piezas.py` lo pinta con el texto y la señal del tema |
| `../../data/io.github.cotejoapp.Cotejo.svg` | Ícono del menú (Linux) y fuente del `.ico` (Windows) |
| `../../barra/cotejo.barra/cotejo-simbolo.svg` | Barra de Omarchy: blanco, engrosado, lo tiñe el widget |

Para la web:

```html
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<picture>
  <source srcset="/logo-full-oscuro.svg" media="(prefers-color-scheme: dark)">
  <img src="/logo-full.svg" alt="Cotejo" height="40">
</picture>
```

## Color

| Pieza | Sobre oscuro (`#101114`) | Sobre claro (`#FFFFFF` / `#FAFAFA`) |
| --- | --- | --- |
| C y palabra | `#FFFFFF` (18,9:1) | `#101114` (18,9:1) |
| Check | `#16C98D` Verde Hecho (8,8:1) | `#0E9F6E` (3,4:1 sobre blanco) |

El Verde Hecho sobre blanco da 2,15:1 y un gráfico necesita 3:1: por eso el check cambia de
tono sobre claro. `#0E9F6E` es solo para el logo; el texto verde sobre claro sigue siendo
`#08734F`.

## Tamaños

- El símbolo normal, de 32 px para arriba. De 24 px para abajo, la versión engrosada
  (`favicon.svg`, la de la barra).
- El logo, de 90 px de ancho para arriba. Por debajo, la C sola.
- Aire alrededor: como mínimo el alto de la «o» por cada lado.

## Lo que no se hace

- **Cambiar el check a otro color que el verde, o la C al verde.** Los dos colores cuentan
  quién hace qué. La excepción son las versiones de una tinta.
- **Poner `#16C98D` sobre blanco.** No llega al contraste de un gráfico.
- **Cerrar la C o meter el check entero dentro.** Es el «check en un círculo» de cualquier lista
  de tareas; lo propio de Cotejo es que el check sale de la C.
- **Redondear las puntas de la C o cortar las del check.** Se pierde la diferencia entre la
  máquina y la mano.
- **Separar la C de «otejo», o poner la C con check delante de otra palabra.** La C es la
  primera letra: va a su distancia de la «o» y no se repite con una «c» normal.
- **Escribir «otejo» con otra fuente o con texto vivo.** Va en curvas desde Sora SemiBold.
- **Pintar de verde otra cosa que el check.**
- **Rotar, deformar, sombrear o poner degradados.**
- **Poner el logo sobre fotos o fondos con ruido.** Ahí va el ícono con su placa
  (`logo-icon-512.png`) o una versión de una tinta.
