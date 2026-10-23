# Inicio de un proyecto: de la idea al plan de la 0.1.0

Cuando la persona dice «empiezo un proyecto», «quiero montar X desde cero» o «prepara este
repo para trabajar con Cotejo». Quien entrevista eres tú; Cotejo solo pone los verbos. No hay
asistente gráfico ni verbo `nuevo`.

## 1. Preparar la carpeta

```sh
cotejo init --repo <carpeta>      # la crea si no existe, hace git init, deja .cotejo/ con version 0.1.0
cotejo fuentes usar repo          # solo si la persona no tiene otra fuente que quiera conservar
```

Es idempotente. Si la persona ya usa Obsidian o Notion, no cambies su fuente: dile que las
tareas de este proyecto se leerán del repo si lo activa. El nombre del proyecto es el de la
carpeta (`cotejo estado` lo lista).

## 2. Entrevistar, poco

Cinco preguntas, **todas en un solo mensaje**, cada una con un valor por defecto que la persona
solo confirma o corrige. Si ya dijo algo en la conversación, no lo preguntes: propónlo.

1. ¿Qué es, en una frase?
2. ¿Para quién? (defecto: para quien lo está pidiendo)
3. ¿Qué tiene que hacer la 0.1.0 para servir? (3 cosas como mucho)
4. ¿Qué queda fuera de la 0.1.0?
5. ¿Stack? (defecto: el que ya hay en la carpeta, o el que mejor conozca la persona)

No sigas preguntando: lo que falte se decide con el defecto y se dice. Lo dudoso va como
decisión propuesta, no como hecho.

## 3. Dejarlo escrito

Lee antes la `version` de `proyecto.md` y escríbelo con ella. `editar` **reemplaza todo el
cuerpo** bajo el título: pasa las tres secciones juntas. `contexto` las lee por esas cabeceras
y recorta cada una a 500 caracteres, así que una o dos frases por sección.

```sh
cotejo leer proyecto --repo <carpeta>        # trae `version`
cotejo editar proyecto --repo <carpeta> --version <hash> --texto "## Objetivo
...
## Stack
...
## Siguiente paso
..."
cotejo proponer decision --repo <carpeta> --titulo "..." --temas stack,datos --texto "qué y por qué"
cotejo anotar arquitectura --repo <carpeta> --titulo "Arquitectura" --temas arquitectura --texto "..." \
  --pieza "ve|Nombre|qué es, en llano|tecnología|<ids de tareas>"   # una por pieza
cotejo crear "Nombre corto: qué hay que hacer" --proyecto <nombre> --version 0.1.0
```

- **Decisiones**: solo las que condicionan lo demás (stack, dónde viven los datos, qué se deja
  fuera). Una por `proponer`. Quedan en `propuesta`; **aceptarlas es de la persona en CotejoBoard**.
  No las des por vigentes ni las simules editando el frontmatter.
- **Arquitectura**: una entrada con las piezas en cuatro capas (`ve`, `hace`, `guarda`,
  `conecta`), una frase en llano cada una y, cuando ya existan, los ids de sus tareas; en `--texto`,
  cómo se hablan. Es lo que el board dibuja. El formato, en `almacen.md`.
- **Tareas**: las de la 0.1.0 y no más (entre 3 y 8), cada una acotada a una sesión de trabajo.
  Todas con `--version 0.1.0`; sin él caerían igual en la en curso, pero así queda a la vista.
  La primera es el «Siguiente paso» que escribiste. Una de cada tres puede ser de la persona (n0):
  crear la cuenta, decidir un nombre. Escríbela igual.
- Lo que la persona dijo que queda fuera de la 0.1.0 no se crea como tarea: va en el texto de la
  decisión o en `anotar referencia`.

## 4. Comprobar y entregar el resultado a la persona

```sh
cotejo contexto --repo <carpeta>     # < 1k tokens: objetivo, stack, siguiente paso, version, decisiones (y cuáles están propuestas), tareas
cotejo version --proyecto <nombre>   # en curso 0.1.0, tareas pendientes
```

Enséñale el resultado en pocas líneas y di qué le toca: **aceptar las decisiones propuestas en
CotejoBoard** (salen en «Para comprobar»). Después, `cotejo plan --proyecto <nombre>` reparte la
0.1.0.

## Proyecto importado (desde Obsidian o Notion)

Después de traer un proyecto que ya existe de otra app, los mismos pasos de decidir, arquitectura y
tareas se aplican; lo que cambia es el arranque.

```sh
cotejo importar obsidian|notion <repo> <proyecto> --repo <carpeta>  # ensayo
cotejo importar obsidian|notion <repo> <proyecto> --repo <carpeta> --aplicar  # si le parece bien
cotejo leer proyecto --repo <carpeta>                              # trae el proyecto y su version
```

El importador fija una `version` en `proyecto.md`; si la persona quiere otra, `cotejo version
--proyecto <nombre> --siguiente X.Y.Z`. Comprobar con `cotejo version --proyecto <nombre>`.

**Editar `proyecto.md`**: `editar` lo reemplaza todo. Lee primero (`leer proyecto`), conserva
Objetivo y Siguiente paso, y pasa el hash:

```sh
cotejo editar proyecto --repo <carpeta> --version <hash> --texto "## Objetivo
...
## Stack
...
## Siguiente paso
..."
```

Las tareas importadas ya están en `.cotejo/tareas.md` sin versión o con la suya. Revisar con la
tarea «Revisar lo importado: resúmenes, temas y fichas» que el importador crea: hacerla con la
persona (entregar con evidencia, no marcarla hecha). Asignar versión a las tareas nuevas con
`crear --version` o dejar las importadas sin cambios.

Lo demás es igual: decisiones (`proponer`), arquitectura (`anotar`) y comprobar con `cotejo
contexto` y `cotejo version`.
