---
id: apr-d34h
fecha: 2026-11-04
temas: [enrutador, arquitectura]
---
# Al mudar el enrutador dentro de Cotejo cayeron tres reglas del repo viejo

Movido del CLAUDE.md del repo el 2026-11-04 (cotejo-d9cbol), sin cambiar el texto. Es el detalle por módulo de arq-lfay (un proyecto tiene una sola arquitectura; volver a anotarla la reescribe).

Vivía en su propio repositorio (`../focorouter`, hoy archivado) y hablaba con Cotejo por su CLI,
en un subproceso. Al ser el mismo comando, eso dejó de tener sentido —un programa no se llama a
sí mismo para preguntarse algo que sabe— y con ello cayeron dos reglas que aquel repo defendía:

- **Ya no se le habla a Cotejo por subproceso**, sino importando `tareas.cli`. La costura sigue
  en `enrutador/cotejo.py`: decidir, planear y despachar hablan con ese objeto y no con la
  fuente. Lo que se ganó: `plan` escanea el vault una vez en vez de una por tarea.
- **La bitácora de despachos usa `ARCHIVO` de módulo**, como la de Cotejo, en vez de resolver la
  ruta en cada llamada. Es lo que deja que las pruebas la redirijan con el mismo `mock.patch`
  que todo lo demás, y no se pierde nada: XDG se lee igual al importar que al llamar.
- **La config es una clave (`enrutador`) del config de Cotejo**, no un archivo aparte.
