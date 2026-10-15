---
id: apr-38jf
fecha: 2026-10-05
temas: []
---
# Dos agentes en el mismo directorio de trabajo no se pisan por editar el mismo archivo…

Dos agentes en el mismo directorio de trabajo no se pisan por editar el mismo archivo, sino por git: un `git add -A` se lleva lo que el otro tiene sin commitear, y lo deja firmado con el nombre equivocado y en la rama equivocada. Antes de commitear en un árbol compartido hay que mirar `git status` y `git branch`, o directamente trabajar en worktrees separados.
