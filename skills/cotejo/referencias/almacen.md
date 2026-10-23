# El conocimiento del repo: `.cotejo/`

Un repo puede llevar su conocimiento —decisiones, arquitectura, problemas, aprendizajes,
bitácora y referencias— en `.cotejo/`, un archivo por entrada con `id` estable (`dec-x7k2`,
`pro-9f3a`...). Conviene leerlo antes que las notas del segundo cerebro: más barato y más
preciso. Si el repo no lo tiene, `cotejo init` lo crea entero (`tareas.md`, `proyecto.md` y una
carpeta por tipo), sin activar ninguna fuente.

**Para enterarte, de menos a más:**

```sh
cotejo contexto [--tope N]      # objetivo, tareas por estado, decisiones y problemas
                                # vigentes (las --tope más recientes) y los temas; < 1k tokens
cotejo buscar [--tipo] [--temas] [--estado] [--desde] [--texto] [--limite]
                                # una línea por entrada: id, tipo, título y resumen
cotejo leer <id>                # la entrada completa, con su `version` (hash)
```

Los tres aceptan `--repo <carpeta>` si no estás dentro del repo que te interesa.

**Para dejar constancia:**

```sh
cotejo proponer decision --titulo --temas --texto [--reemplaza <dec-id>]
cotejo anotar <problema|aprendizaje|referencia|arquitectura> --titulo --temas --texto
cotejo anotar arquitectura --titulo --pieza "capa|nombre|frase|tecnología|tareas" ...
cotejo bitacora "texto"                       # se añade al final del archivo de hoy
cotejo editar <id> --version <hash> --texto   # arquitectura, referencia o proyecto.md
cotejo resolver <pro-id> --solucion "..."
```

Toda escritura devuelve la entrada que dejó (`id`, `ruta`, `version`). `editar` y `resolver` se
niegan, sin tocar nada, si la entrada cambió desde que la leíste con `leer`. Las decisiones no se
editan nunca: una que ya no aplica se reemplaza con `proponer decision --reemplaza <dec-id>`.

**Lo que no puedes hacer: aceptar una decisión.** `proponer decision` la deja en `propuesta`;
pasarla a `aceptada` es de la persona, desde CotejoBoard (sale como carta propia en «Para
comprobar»). No hay verbo de CLI ni tool de MCP para eso, a propósito, así que no lo pidas ni lo
simules editando el frontmatter a mano.

## La arquitectura dibujable (1.3.0)

Una entrada `arquitectura` puede ser texto libre (como siempre) o llevar una sección
`## Piezas` con una tabla, una fila por pieza, que es lo que CotejoBoard dibuja en el mapa del
proyecto y en la constelación:

```md
## Piezas

| Capa | Pieza | Qué es | Tecnología | Tareas |
| --- | --- | --- | --- | --- |
| ve | Pantalla de pedidos | Donde el cliente elige y paga | React | cotejo-ab12cd, cotejo-ef34gh |
| guarda | Pedidos | La lista de pedidos de cada día | SQLite | |
```

- **Capa**: `ve` (qué ve la gente), `hace` (qué hace), `guarda` (qué guarda) o `conecta` (con
  qué se conecta). Ninguna otra.
- **Pieza**: nombre corto (≤ 40 caracteres), único en el proyecto; es la etiqueta del mapa.
- **Qué es**: una frase en llano (≤ 140), para alguien que no programa.
- **Tecnología** y **Tareas** (ids separados por comas) pueden ir vacías. Un `|` dentro de una
  celda se escribe `\|`.

Lo más cómodo es no escribir la tabla: `anotar arquitectura` la arma con un `--pieza` por pieza
(`--texto` es opcional si hay piezas). `anotar` y `editar` se niegan sin escribir nada si una fila
está mal; `leer` devuelve `formato` (`piezas` o `libre`) y, si hay piezas, cada una con su
`estado`, y las filas rotas escritas a mano salen en `avisos`. `contexto` añade `arquitectura`:
una línea por capa (`"ve": "2 piezas: 1 hecho, 1 falta"`); el detalle, con `leer`.

El estado de una pieza sale de sus tareas: `por-comprobar` si alguna está para comprobar,
`hecho` si todas están hechas, `en-curso` si alguna está en curso y `falta` en cualquier otro
caso. **Una pieza sin tareas (o con ids que no existen) está en `falta`**: nada la cubre todavía.
Para añadir o mover piezas, edita la entrada que ya hay (`leer`, `editar`) en vez de anotar otra:
una pieza repetida en dos entradas se queda con la primera y la otra sale como aviso.
