---
id: pro-c9ha
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: "longpaths=True por defecto en _git() de worktrees.py (PR #31)"
---
# En Windows, quitar un worktree fallaba con rutas de más de 260 caracteres

En Windows, quitar un worktree fallaba con rutas de más de 260 caracteres

**Causa:** Solo git worktree add/remove llevaban core.longpaths=true; el git status previo no

**Solución:** longpaths=True por defecto en _git() de worktrees.py (PR #31)
