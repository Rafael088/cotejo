---
name: cotejo-modelos
description: >-
  Gestionar el catálogo de modelos que Cotejo puede asignar a sus tareas. Úsala cuando el usuario
  quiera añadir un modelo de Claude, OpenCode Go, Codex u otro cliente, consultar los modelos
  disponibles, seleccionar uno para una tarea o preparar Cotejo para un cliente de IA nuevo.
---

# Modelos de Cotejo

Cotejo separa la tarea de quién puede hacerla del cliente que ejecuta ese modelo. Antes de asignar
un modelo, consulta el catálogo:

```sh
cotejo modelos
```

## Registrar un modelo

Si el modelo no aparece, registra una clave corta y estable. La clave se guarda en la tarea como
`#agente/<clave>`; `modelo-id` conserva el identificador real del cliente. No guardes API keys,
tokens ni credenciales en la configuración.

```sh
cotejo modelos agregar \
  --clave luna \
  --nombre "GPT 5.6 Luna" \
  --modelo-id opencode-go/gpt-5.6-luna \
  --cliente opencode \
  --nivel n2
```

`--nivel` describe el tamaño de trabajo que representa: `n1` es acotado, `n2` es normal y `n3`
cruza arquitectura o varios archivos. El cliente puede actualizar el registro repitiendo el mismo
comando con la misma clave.

## Asignar una tarea

No edites el Markdown del vault a mano. Usa el id que devuelve `tareas`:

```sh
cotejo tareas --proyecto <nombre> --estado pendiente
cotejo asignar <id> luna
```

Comprueba la asignación con `tareas` o `decidir --tarea <id>`. Una asignación explícita tiene
preferencia sobre las reglas automáticas. Si el modelo solo es una propuesta de las reglas,
pregunta antes de despachar o usa `--modelo <clave>` para una decisión puntual.

Con el motor por defecto (`agente`) Cotejo no lanza nada: devuelve el encargo al cliente que está
trabajando. Con `despachar <id> --motor headless` sí lanza **el cliente del modelo** —`opencode run
-m <modelo-id>`, `codex exec -m`, `gemini -p`, `agy -p --model`, `claude -p`—, así que `cliente`
tiene que ser uno de los que sabe abrir (`cotejo maestro --clientes`). Es lo que usa el maestro de
un proyecto (`cotejo maestro --proyecto X`) para repartir las tareas asignadas.

## Quitar un modelo

Solo quita modelos personalizados y verifica antes qué tareas siguen usando su clave:

```sh
cotejo tareas --agente luna
cotejo modelos quitar luna
```

Los modelos integrados y el destino `persona` no se eliminan desde este comando.
