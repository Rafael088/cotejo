# Oro del dot

Los números y los fotogramas que da el laboratorio (`docs/dot/avatar.html`) en instantes
fijos. Lo consumen D2 (`tareas/dot.py`: `pose(estado, t)` contra `oro.json`, tolerancia 0,001)
y D4 (`dibujar_dot` contra los PNG).

- `oro.json`: una muestra por línea. Estados `idle`, `trabaja`, `comprobar`, `celebra`, `falla`
  y `entrada`, en 0, 0,3, 0,9, 1,6 y 2,4 s (`entrada` añade 0,38 s), y la mitad de cada
  transición de `idle` a cada estado y de vuelta (`tipo: "transicion"`).
- `<id>_<talla>.png`: la misma muestra a 250, 56 y 24 px, con fondo transparente. `<id>` es
  `<estado>_t<ms>` (`falla_t0900`) o `<origen>-a-<destino>_t<ms>` en las transiciones.
- El formato completo, y lo que D2 debe respetar de CSS, está en el docstring de
  `herramientas/dot_oro.py`.

Regenerar (hace falta Chromium; las pruebas normales no lo necesitan):

    python3 herramientas/dot_oro.py              # reescribe esta carpeta
    python3 herramientas/dot_oro.py --comprobar  # dice si regenerar da lo mismo

`piensa` no está: queda fuera del port.
