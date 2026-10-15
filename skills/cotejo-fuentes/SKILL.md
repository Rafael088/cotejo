---
name: cotejo-fuentes
description: >-
  Cambiar de dónde lee Cotejo las tareas —un repo de git, Obsidian, Notion u otra app— o
  conectarlo a una app nueva. Úsala cuando digan «que Cotejo lea de este repo», «no tengo vault,
  ¿cómo uso Cotejo aquí?», «importa mi proyecto de Obsidian», «cambia Cotejo a Notion»,
  «conecta Cotejo a Trello/Linear/Todoist», «qué fuente está usando Cotejo» o «Cotejo no
  encuentra las tareas». No sirve para trabajar las tareas: para eso está la skill cotejo.
---

# Fuentes de Cotejo: de dónde lee las tareas

Cotejo lee de **una fuente a la vez**. Todo se hace con `cotejo`. Nunca edites
`~/.config/cotejo/config.json` a mano ni pongas un token en él.

## Registrar y usar un repo: cotejo init

Un repo de git es un proyecto: sus tareas viven en `<repo>/.cotejo/tareas.md`, con la misma línea
que en una nota de Obsidian. Viene sin adaptador ni token.

```sh
cd /ruta/al/repo
cotejo init               # crea .cotejo/tareas.md si no existe y registra el repo en «repos»
cotejo fuentes usar repo  # registra como fuente activa
```

`init` es idempotente: repetirlo sin haber tocado nada no escribe de nuevo ni duplica el repo en
la config. Funciona igual en Linux y en Windows. `cotejo doctor` avisa si el repo ya está
registrado pero falta `fuentes usar repo`.

## Importar un proyecto existente: importar obsidian | importar notion

Traen un proyecto a su `.cotejo/` de una vez —no son una fuente ni se usan con `fuentes usar`—:
después, el proyecto sigue viéndose igual en `tareas`, `plan` o el board, solo que ya no depende
de la app de origen.

```sh
cotejo importar obsidian <proyecto> [--destino <carpeta>] [--detalle]   # ensayo: no toca nada
cotejo importar notion <proyecto> [--destino <carpeta>] [--detalle]
cotejo importar obsidian <proyecto> --aplicar    # lo escribe de verdad (sin commit)
```

Son **ensayo por defecto**: enséñale el ensayo a quien lo pidió antes de `--aplicar`. `--destino`
es obligatorio si el proyecto no tiene repo (Obsidian lo deduce de `repo:` o de un `.git`;
Notion lo pide siempre la primera vez). Repetirlo no duplica: cada entrada guarda su `origen`.

**Obsidian** reparte Objetivo/Stack/Enlaces/Siguiente paso, decisiones, bitácora, problemas,
aprendizajes, subnotas y adjuntos según la plantilla, y **marca el proyecto como migrado**: desde
entonces se lee del repo y la nota original deja de contar para el board, aunque sigue ahí sin
tocar —quitar de `migrados` en la config de la fuente `obsidian` lo deshace—. Los proyectos no
migrados se leen del vault simultáneamente. **Notion** trae solo tareas y sus páginas con resumen
pendiente; no deja de leerse de Notion, así que puede haber el mismo proyecto en los dos sitios
mientras no migres.

Ambas crean la tarea «Revisar lo importado: resúmenes, temas y fichas» porque la clasificación
necesita revisión.

## Cambiar de fuente: fuentes usar

Para cambiar a una fuente ya registrada (repo, obsidian, notion o cualquier otra):

```sh
cotejo fuentes                    # cuáles hay y cuál está activa (no se conecta a nada)
cotejo fuentes usar <fuente>      # obsidian, notion, repo, o el nombre de otra registrada
```

`usar` prueba la fuente antes de activarla y se niega si no responde, así que no puede dejar el
board vacío. Si ya estaba activa, contesta `"cambio": false`. El board y la barra se enteran
solos: no hay que reiniciar nada. Para comprobar: `cotejo doctor`.

## Conectar una app que todavía no está

1. `cotejo fuentes info <app>`: si hay un adaptador `cotejo-<app>` instalado, dice qué parámetros
   pide. **Notion** ya lo trae (`cotejo-notion`: `database_id` y el token).
2. El token **no** va en la config: va en `~/.config/cotejo/<app>.token` (permisos 600) o en la
   variable que diga `token_env`. Pídeselo a la persona; no lo inventes ni lo imprimas.
3. `cotejo fuentes agregar <app> --comando cotejo-<app> --param clave=valor` (registra, no activa).
4. `cotejo fuentes probar <app>`: lee sin escribir nada. Si falla, su `salida` dice qué arreglar.
5. `cotejo fuentes usar <app>`.

Si la app no tiene adaptador, hay que escribirlo: se copia `extras/plantilla/cotejo_plantilla.py`
del repo de Cotejo y se cambian sus lecturas y escrituras por la API de la app. El contrato está
en la sección «Conectar Cotejo a otra app» del README. Eso es trabajo de código, no de config:
dilo y pregunta antes de empezar.

## Si algo falla

`cotejo doctor` contesta en una llamada si la config está bien, qué fuente está activa y si
conecta, con `salida` diciendo el siguiente paso. `cotejo fuentes quitar <app>` desregistra una
fuente sin borrar nada en su app (no deja quitar la activa).
