---
name: cotejo
description: >-
  Trabajar las tareas de un proyecto en Cotejo: ver qué hay pendiente, qué modelo le toca a cada
  una, tomarla, hacerla y entregarla con evidencia. Úsala con «ponte con las tareas del proyecto
  X», «hazme dos tareas de X», «reparte lo pendiente», «qué tengo pendiente», «qué modelo debería
  hacer esto», «entrega esta tarea», «empiezo un proyecto»; y antes de cualquier tarea de un
  proyecto con tareas en Cotejo. También para un tema de CotejoBoard. Aplica desde cualquier repo.
---

# Cotejo, para quien va a repartir o a hacer tareas

Cotejo es el tablero donde tus agentes entregan y la persona comprueba. Las tareas viven en
`.cotejo/` del repo (o Obsidian, Notion…); `cotejo` las maneja y decide **quién atiende cada una**.

## Antes de tocar nada

```sh
cotejo doctor
```

Si no está, prueba `tareas-obsidian` o `foco` (instalación anterior). Si ninguno, no está
instalado: dilo, sin inventar rutas.

## Los destinos

| Nivel | Quién | Para qué |
| --- | --- | --- |
| n0 | **una persona** (no se despacha) | Comprar, firmar, llamar, abrir una cuenta, tocar algo físico |
| n1 | modelo acotado | Trabajo mecánico |
| n2 | modelo normal | El trabajo normal de código |
| n3 | modelo capaz | Arquitectura, contratos, lo que cruza archivos |

Una de cada tres es n0: dársela a un modelo produce una entrega falsa.

## El ciclo

1. **Contexto**: `cotejo contexto` (objetivo, tareas, decisiones vigentes; < 1k tokens).
   **Versión**: `cotejo version` antes de planear; tareas nuevas con `crear --version`.
2. **Mirar el reparto**: `cotejo plan --proyecto <nombre> --solo-despachables` da por tarea
   `id`, `texto`, `modelo`, `por`, `asignado` (si lo puso una persona o lo propone una regla); `sin_asignar` cuenta las
   que esperan. No escribe nada. Sin reparto:
   `cotejo tareas --proyecto <nombre> --estado pendiente` (`--todas`: con las hechas).
3. **Modelo**: si `asignado` es `false`, **pregunta cuál** enseñando la propuesta y su porqué, y
   guarda la respuesta: `cotejo asignar <id> <haiku|sonnet|opus|clave-registrada>`.
4. **Tomar**: si ese modelo eres tú, `cotejo despachar <id>` la toma y devuelve el encargo en
   `salida`; haz el trabajo. Si no, **no puedes cambiarte de modelo**: delega el `salida` a un
   subagente con ese modelo, o devuélvela («esta es de <modelo>, cámbiate y vuelve a pedirla»).
   Si la tarea es de un repo de git, `despachar` crea un worktree con rama `cotejo/<id>`: trabaja
   y commitea **ahí** (`--sin-aislar` para no aislar).
5. **Entregar** desde la carpeta del trabajo (o con `--repo`), con evidencia repetible
   (archivos, pruebas con su salida, commit). Cada `--prueba` la corre Cotejo
   sin shell (nada de `|` ni `&&`: una por comando). **Siempre `--resumen`** (`entrega.md`): qué
   cambió visto desde fuera y cómo probarlo uno mismo, sin jerga, para quien no programa:

   ```sh
   cotejo entregar <id> --evidencia "..." --resumen "..." --prueba "python3 -m unittest discover pruebas"
   cotejo bloquear <id> --motivo "qué lo impide"   # si te atascas, esto, no dejarla a medias
   cotejo comprobar <id>                           # repite las pruebas; no escribe nada
   ```
6. **Anotar**: trabajo nuevo que encuentres, `cotejo crear "qué hay que hacer" --proyecto <nombre>`
   (no se duplica; nada en Inbox/Diario ni proyectos nuevos). Texto como
   «vX.Y.Z · Nombre corto: descripción» (de ahí salen `version` y `nombre`). Para recordar:
   `cotejo anotar`, `cotejo proponer decision`, `cotejo bitacora "texto"` (detalle en almacen).

## Reglas duras

- **No marques nada como hecho ni entregues lo que no hiciste tú.** `[x]` lo pone una persona en
  CotejoBoard tras comprobar; no hay verbo para finalizar, a propósito.
- **No aceptes una decisión propuesta**: `proponer decision` es lo único tuyo; aceptarla es de la
  persona. No lo simules editando el frontmatter.
- **n0 no se despacha** y no hay bandera para forzarlo (código `5`).
- **Sin modelo asignado se pregunta** (`despachar` sale con `6`). `--auto` solo si te dijeron
  explícitamente que no pares a preguntar.
- **No edites tareas por fuera de Cotejo** (ni el Markdown ni la API de Notion): pisarías en
  silencio el trabajo de otro.
- **El `id` sale de `plan` o `tareas`**, no se construye. `decidir` y `despachar --simular` solo
  miran.
- **No asumas la máquina del autor**: ni rutas, ni cliente instalado, ni modelos registrados.
  Pregunta o comprueba con `cotejo modelos`, `cotejo doctor`, `despachar --simular`.

## Referencias (junto a este archivo; léelas solo cuando toque)

- `referencias/repartir.md`: «hazme N tareas» (eres el maestro), `capacidad`, `--motor`, `--nota`,
  `importar plan`, `revisar`, modelos configurables y carpeta del proyecto.
- `referencias/almacen.md`: el conocimiento del repo en `.cotejo/` (contexto, buscar, leer,
  proponer, anotar, bitacora, editar, resolver, init).
- `referencias/entrega.md`: cómo escribir el `--resumen` de `entregar`.
- `referencias/inicio.md`: proyecto nuevo: `init`, entrevista corta y plan de la 0.1.0.
- `referencias/versiones.md`: `version` (`--siguiente`), `crear --version` y `release` (solo en
  ensayo; etiquetar y publicar es de la persona).
- `referencias/mantenimiento.md`: `limpiar`, cambiar de fuente, temas del board, códigos de error.

`cotejo protocolo --completo` imprime este archivo y todas las referencias. Flags exactos:
`cotejo <verbo> --help`.
