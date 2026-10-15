---
id: pro-mdl9
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: "Anotar fase=lanzado con pid, programa y máquina al lanzar; revisar mira si el proceso vive y es el mismo programa. Con systemd-run --scope el pid sigue siendo el del cliente porque hace exec (PR #9 y #13)"
---
# Un headless que moría por OOM dejaba la tarea en curso días, hasta que revisar la daba…

Un headless que moría por OOM dejaba la tarea en curso días, hasta que revisar la daba por colgada

**Causa:** El despacho solo se anotaba al terminar, y si el proceso moría no terminaba nunca

**Solución:** Anotar fase=lanzado con pid, programa y máquina al lanzar; revisar mira si el proceso vive y es el mismo programa. Con systemd-run --scope el pid sigue siendo el del cliente porque hace exec (PR #9 y #13)
