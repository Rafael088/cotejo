---
id: pro-iq8c
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: "Matar el proceso antes de instalar: `pkill -f '^python3 -m tareas'` y después `./install.sh`. Sin el pkill, install.sh copia bien los archivos pero no cambia nada de lo que ves"
---
# Instalar los cambios y seguir viendo el board viejo, aunque el archivo en disco ya…

Instalar los cambios y seguir viendo el board viejo, aunque el archivo en disco ya estuviera actualizado

**Causa:** La app es de instancia única (mismo APP_ID). El proceso de fondo que alimenta el widget de la barra intercepta cualquier `tareas-obsidian --board` y abre su propia ventana, que es la del código con el que arrancó

**Solución:** Matar el proceso antes de instalar: `pkill -f '^python3 -m tareas'` y después `./install.sh`. Sin el pkill, install.sh copia bien los archivos pero no cambia nada de lo que ves
