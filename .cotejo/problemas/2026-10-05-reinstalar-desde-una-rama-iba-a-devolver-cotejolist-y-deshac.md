---
id: pro-fzzs
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: Comparar lo instalado con cada árbol antes de reinstalar; commitear la eliminación (3fc52a2), rebasar fuentes-externas encima y recién entonces merge a master e instalar
---
# Reinstalar desde una rama iba a devolver CotejoList y deshacer cambios de app.py que ya…

Reinstalar desde una rama iba a devolver CotejoList y deshacer cambios de app.py que ya se estaban usando

**Causa:** install.sh copia el árbol de trabajo tal cual: la eliminación de CotejoList (decisión del 2026-09-21) estaba instalada desde cambios sin commitear y no existía en ninguna rama

**Solución:** Comparar lo instalado con cada árbol antes de reinstalar; commitear la eliminación (3fc52a2), rebasar fuentes-externas encima y recién entonces merge a master e instalar
