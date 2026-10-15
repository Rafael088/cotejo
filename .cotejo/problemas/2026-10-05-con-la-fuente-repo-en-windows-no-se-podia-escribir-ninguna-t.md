---
id: pro-t6yr
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: "Normalizar con PurePath(...).as_posix() en _archivo() y probarlo en el runner de Windows (PR #32)"
---
# Con la fuente repo, en Windows no se podía escribir ninguna tarea

Con la fuente repo, en Windows no se podía escribir ninguna tarea

**Causa:** repo.py guardaba las claves con '/' y las buscaba con str(Path), que en Windows usa '\'

**Solución:** Normalizar con PurePath(...).as_posix() en _archivo() y probarlo en el runner de Windows (PR #32)
