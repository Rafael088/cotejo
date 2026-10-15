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
