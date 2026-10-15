# Dot D3 · Rendimiento de un widget GTK en Python

Prueba de viabilidad de la fase D3 del planning del dot: un `Gtk.Widget` escrito en Python con
`do_snapshot`, `push_shadow`, `push_color_matrix` y `append_cairo`, a 60 fps con
`add_tick_callback`. El experimento está en `herramientas/dot_rendimiento.py`; no es el widget
final (ese es D4).

**Veredicto: camino A (`do_snapshot`). No hace falta el plan B.** Funciona desde PyGObject,
no pierde memoria y no gasta más del 2 % de la máquina. Medida en un solo núcleo sí pasa de
ese 2 %: ver «Qué significa el 2 %».

## Cómo se midió

- Máquina: CPU de 8 hilos, Wayland (Hyprland), GTK 4.22, Python 3.14, PyGObject.
- Ventana real a la vista con el widget (dibujo de prueba: una docena de formas, degradado
  radial, sombra grande y matriz `saturate(0.4) brightness(0.82)`), reloj de fotogramas a 60 Hz.
- CPU: `time.process_time()` del proceso entero (todos los hilos) entre tiempo transcurrido,
  tras 2 s de asentarse la ventana. **Se expresa como % de un solo núcleo** (100 % = un núcleo
  ocupado); entre paréntesis, el % de la máquina entera (÷ 8).
- Línea base: la misma ventana con el widget dibujado una vez y sin tick (`--sin-animar`).
- RSS: `/proc/self/statm` al principio, cada pocos segundos y al final, tras `gc.collect()`.

Para repetirlo:

```sh
python3 herramientas/dot_rendimiento.py --talla 56  --duracion 20 --sin-animar   # línea base
python3 herramientas/dot_rendimiento.py --talla 56  --duracion 90
python3 herramientas/dot_rendimiento.py --talla 250 --duracion 90 --salida r250.json
python3 herramientas/dot_rendimiento.py --comprobar    # firmas y que el tick se pare
```

## Números (2026-10-10)

| Talla | Modo | Duración | CPU (un núcleo) | Fotogramas | RSS inicial → final |
|---|---|---|---|---|---|
| 56 px | línea base, sin animar | 20 s | 0,03 % | 0 | 126 436 → 126 012 KiB |
| 56 px | animado | 20 s | 5,38 % (0,67 % de la máquina) | 1 200 | 126 572 → 126 796 KiB |
| 56 px | animado, larga | 90 s | 5,30 % | 5 401 | 126 188 → 126 588 KiB |
| 250 px | línea base, sin animar | 20 s | 0,03 % | 0 | 126 248 → 126 376 KiB |
| 250 px | animado | 20 s | 8,85 % (1,1 % de la máquina) | 1 200 | 126 472 → 126 820 KiB |
| 250 px | animado, larga | 90 s | 8,80 % | 5 401 | 126 520 → 126 808 KiB |

Restada la línea base (0,03 %), el coste del widget es el mismo número: 5,3 % a 56 px y 8,8 %
a 250 px. Salen 60,0 fps exactos en todas las pruebas.

Dentro de `do_snapshot`, el código Python (dibujar con cairo y apilar los nodos) tarda unos
135 µs por fotograma tanto a 56 como a 250 px, es decir, ~0,8 % de un núcleo. El resto del
coste lo pone GTK al rasterizar el nodo de cairo, difuminar la sombra y subir la textura, y
crece con la talla.

## Fugas

La RSS sube unos 300–400 KiB en los primeros ~35 s (cachés de GTK, de Pango y del
rasterizador) y se queda plana: en los últimos ~50 s, de 5 400 fotogramas, no se mueve más de
4 KiB. Los objetos vivos de Python (`gc.get_objects`) pasan de 24 190 a 24 200 en las
ejecuciones largas, sin crecimiento por fotograma. El `cairo.Context` que devuelve
`append_cairo` en cada fotograma no se acumula: lo recoge el recolector de PyGObject al
soltarse la referencia, siempre que no se guarde.

## Comportamiento del tick (`--comprobar`, y `pruebas/test_dot_rendimiento.py`)

- Widget sin mostrar: 0 ticks, sin callback registrado.
- A la vista: ~36 ticks en 0,6 s (60 fps).
- Ventana oculta (`set_visible(False)`): el widget se desmapea, se retira el callback con
  `remove_tick_callback` y no entra ningún tick más; al volver a mostrarla se reanuda.
- `gtk-enable-animations` en falso con el widget a la vista: se retira el callback (se escucha
  `notify::gtk-enable-animations`) y no hay ticks; al encenderlo se reanuda.

La pauta que lo consigue: registrar el tick en `do_map` y retirarlo en `do_unmap`, y
reevaluar si `get_mapped()` y la propiedad lo permiten. Mejor que dejar el tick vivo y no
hacer nada dentro, porque así el reloj de fotogramas se queda dormido.

## Firmas reales en PyGObject (GTK 4.22) para D4

```python
snapshot.push_color_matrix(color_matrix: Graphene.Matrix, color_offset: Graphene.Vec4)
snapshot.push_shadow(shadow: list[Gsk.Shadow])        # lista, aunque sea de una sombra
cr = snapshot.append_cairo(bounds: Graphene.Rect)     # -> cairo.Context
snapshot.pop()                                        # uno por cada push, en orden inverso
```

- `Gsk.Shadow()` se construye vacío y se rellenan `color` (`Gdk.RGBA`), `dx`, `dy` y `radius`.
- La matriz: `m = Graphene.Matrix(); m.init_from_float([16 floats])` y
  `v = Graphene.Vec4(); v.init(0, 0, 0, 0)`. Graphene guarda por columnas y GSK aplica el
  color como vector fila, así que la matriz de la especificación de filtros de CSS va
  **transpuesta** (`matriz_saturar_oscurecer` de la herramienta ya lo hace).
- `Graphene.Rect().init(x, y, ancho, alto)`.
- Orden: lo que se apila primero afecta a lo de dentro. Con `push_color_matrix` fuera y
  `push_shadow` dentro, la sombra también se desatura y oscurece.
- El `Gsk.Shadow.radius` de GSK no es el `blur` de CSS: se calibra en D4 con el PNG de oro.

## Qué significa el 2 %

El planning dice «< 2 % de CPU con la ventana a la vista» sin decir de qué. Como porcentaje de
la máquina (8 hilos) pasa de sobra, 0,7 % a 56 px y 1,1 % a 250 px. Como porcentaje de un
núcleo no pasa: 5,3 % y 8,8 %. Aun así no justifica el plan B: casi todo ese coste es de GTK
rasterizando el fotograma (no se midió un `DrawingArea`, pero el cairo y la sombra los
seguiría pagando), y el Python propio es menos de 1 % de un núcleo. Además el dot solo anima cuando hay un estado
con movimiento, y con el widget fuera de pantalla o con las animaciones apagadas cuesta 0.

Si en D5 se quiere bajar más: limitar el tick a 30 fps en los estados lentos, o dibujar con
la talla de 56 px aunque el overlay se vea más grande.
