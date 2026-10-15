---
id: apr-058i
fecha: 2026-10-08
temas: [windows, git-bash, rutas]
---
# El Python de MSYS2 dentro de Git Bash ve MSYSTEM y mezcla separadores de ruta

Desde Git Bash, que es donde corren los agentes en Windows, el Python de MSYS2 que trae el runtime de Cotejo ve la variable MSYSTEM y usa / como separador, mientras rglob devuelve rutas con barras invertidas. relative_to lanzaba ValueError en fuentes/obsidian.py (_oculta) y cotejo no podía leer el vault. El arreglo es que lanzador.c borre MSYSTEM antes de arrancar Python. Se comprobó en el runner de windows.yml (run 36774689722) creando, tomando y entregando 3 tareas desde Git Bash.
