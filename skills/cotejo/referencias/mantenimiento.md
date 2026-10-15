# Mantenimiento: limpiar, fuentes, temas y errores

## Limpiar las finalizadas de un proyecto

Si `entregar` trae en `avisos` que el proyecto acumula muchas finalizadas (pasa del umbral
`limpiar.umbral` de la config, 50 por defecto), **pregúntale a la persona** si quiere limpiarlas;
no lo hagas por tu cuenta. También vale cuando te lo pidan directamente.

```sh
cotejo limpiar <proyecto>             # ensayo: no toca nada
cotejo limpiar <proyecto> --aplicar   # las borra, después de que la persona diga que sí
```

El ensayo lista las finalizadas de hace más de 7 días o sin fecha, y dice de cada una si ya tiene
su `comprobar` en la bitácora (`comprobada`). Antes de `--aplicar`:

1. Guarda en `.cotejo/` lo que valga la pena: decisiones con `cotejo proponer decision`;
   resultados, problemas o aprendizajes con `cotejo anotar`.
2. Enséñale el ensayo a la persona y pídele confirmación.

Con `--aplicar`, a las que no tienen `comprobar` se les escribe antes una anotación `limpiar` y
luego se borra su línea, verificando que no cambió; los ids siguen resolviendo en la bitácora. Las
que cambiaron salen en `saltadas` con su motivo. `limpiar` no finaliza nada y no tiene botón en el
board.

## Si no aparecen las tareas, o la fuente falla

```sh
cotejo doctor
```

Dice si la config está bien, de qué fuente se lee y si contesta, con `salida` diciendo qué hacer.
Conectar Cotejo a otra app (`cotejo fuentes agregar`, `cotejo fuentes usar`) es configurar la
máquina de una persona: hazlo solo si te lo piden, y nunca pongas un token en la config —se guarda
el **nombre** de la variable de entorno (`token_env`)—. Sin vault y con las tareas en este repo
de git, la skill `cotejo-fuentes` cubre `cotejo init` y `fuentes usar repo`.

## Si te piden un tema de colores para CotejoBoard

```sh
cotejo temas nuevo <id> --desde oscuro --nombre "Cómo se verá"   # --desde claro si es claro
```

Devuelve la ruta del JSON y para qué es cada color. Edita `colores` y `descripcion`, y luego
`cotejo temas comprobar <id>` hasta que salga `ok: true` (mide el contraste y dice qué par no
llega). No lo actives (`temas usar`) salvo que te lo pidan: el tema lo elige una persona.

## Cuando algo sale mal

Los errores vienen en JSON con `salida` (el siguiente paso) y `reintentable`. Códigos: `3` error,
`4` la tarea cambió y conviene reintentar, `5` es de una persona, `6` falta decidir el modelo. Si
la respuesta trae `avisos`, hay notas que no se pudieron leer y sus tareas **no están** en la
lista, que no es lo mismo que no haya nada.
