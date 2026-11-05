---
id: ref-tvaz
temas: [arquitectura, fuentes]
resumen: pendiente
---
# Arquitectura · Fuentes, config e init

Movido del CLAUDE.md del repo el 2026-11-04 (cotejo-d9cbol), sin cambiar el texto. Es el detalle por módulo de arq-lfay (un proyecto tiene una sola arquitectura; volver a anotarla la reescribe).

`modelo.py` dice qué es una tarea; `fuente.py` es la interfaz con el segundo cerebro y decide
cuál se usa; `fuentes/obsidian.py` es la única que sabe de notas, tags y marcas de bloque;
`cli.py` (verbos para agentes), `app/` (el board) y `estado.py` (el resumen de la
barra) hablan con la interfaz y con el modelo, nunca con Obsidian. Si escribes `#en-curso` o
`.md` fuera de `fuentes/`, es que algo se salió de su sitio.

`fuentes/repo.py` es la fuente para quien no tiene vault: un repo de git es un proyecto y sus
tareas van en `<repo>/.cotejo/tareas.md`, con la misma línea que en Obsidian. Hereda de
`Obsidian` el parser y la escritura verificada, y solo cambia dónde cae cada archivo
(`_archivo`); los repos salen de `repos` (lista) y/o `raiz` (carpeta) en su config.

`fuentes/compuesta.py` es la migración gradual de la 1.2 (A3, decisión E1): Obsidian con
`migrados` (`{"Cotejo": "/ruta/al/repo"}`) en su config. `fuente.abrir` la devuelve en vez de
`Obsidian` solo si hay marca; cada proyecto marcado se lee de su repo con el nombre del vault y
**deja de leerse del vault** (gana el repo, la nota no se toca) y cada escritura va a la fuente
dueña según `donde`. Solo Obsidian + repo: nada de N fuentes ni externas. Quitar la marca la
deshace sin escribir nada.

`fuentes/externa.py` es la fuente que vive en otro programa: le habla por subproceso y en JSON
a un **adaptador** (`extras/notion/cotejo_notion.py`, `extras/plantilla/cotejo_plantilla.py`), y no
sabe nada de ninguna app. `configuracion.py` es el único que sabe dónde está el archivo de
config y cómo era el formato viejo; `conexion.py` tiene los verbos de la instalación (`init`,
`doctor`, `fuentes`, `config init|validar`).

`cotejo init` es el arranque para quien no tiene vault (y deja un commit inicial con `.cotejo/` si el repo no tenía ninguno, porque `despachar` rechaza antes de tomar un repo sin commits): dentro de un repo git (o con `--repo`),
crea `<repo>/.cotejo/tareas.md` si no existe y añade el repo a `repos` en la config de la
fuente `repo` —sin activarla, eso es de `fuentes usar repo`—. Es idempotente: ni duplica el
repo en `repos` si ya estaba (a mano o porque ya lo cubre `raiz`), ni rehace el archivo si ya
existe. Como lo normal después de `init` es seguir con otra fuente activa, `doctor` mira el
repo donde se para (`_pista_repo_actual`) y, sin tocar `ok`, avisa en «avisos» y en «salida»
si ya está registrado pero toca `fuentes usar repo`, o si tiene `.cotejo/tareas.md` sin
registrar y toca `cotejo init`.
