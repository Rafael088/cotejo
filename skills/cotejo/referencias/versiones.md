# Versiones: planear y preparar el release

Un proyecto tiene una versión en curso y las tareas se agrupan por versión (el tag `#vX.Y.Z`
de la línea). Estos tres verbos la manejan; ninguno etiqueta ni publica.

## `cotejo version` antes de planear

```sh
cotejo version --proyecto <nombre>
```

Dice la versión en curso, la última etiquetada y cuántas tareas de la en curso están
aprobadas y cuántas faltan. Mírala **antes de planear o repartir**, para saber a qué versión
pertenece el trabajo y no mezclar versiones.

## Planear la siguiente versión

```sh
cotejo version --proyecto <nombre> --siguiente 1.3.0
```

Escribe la siguiente menor o mayor en `proyecto.md`. Puede hacerlo un agente: es planear, no
publicar. Debe subir la en curso (X.Y.0); un parche no se planea así.

## Crear tareas con versión

```sh
cotejo crear "Nombre corto: qué hay que hacer" --proyecto <nombre> --version 1.2.4
```

`--version` pone el tag `#v1.2.4` en la línea. Sin él, la tarea cae en la versión en curso.
Una tarea que dejas sin versión no entra en las notas de ninguna.

## `cotejo release` solo en ensayo, y la persona etiqueta

```sh
cotejo release --proyecto <nombre> --version 1.2.4            # ensayo: no escribe nada
cotejo release --proyecto <nombre> --version 1.2.4 --aplicar  # escribe .cotejo/releases/v1.2.4.md
```

- El ensayo enseña qué notas saldrían: tareas aprobadas, decisiones aceptadas, problemas
  resueltos. **Es lo que corre un agente.** Se niega, nombrando las tareas, si queda alguna de
  esa versión sin aprobar: no las apruebes tú, es de la persona.
- `--aplicar` escribe las notas; repetirlo con lo mismo no cambia nada. Si el archivo ya existe
  con otro contenido se niega y da su hash; `--reemplazar <hash>` lo reescribe. Hazlo solo si te
  lo piden.
- `salida` trae el comando `git tag` para **la persona**. El agente no etiqueta, no hace push de
  tags ni publica el release: como finalizar una tarea, es de una persona. Dale el comando y
  para.
