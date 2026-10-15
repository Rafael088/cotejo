---
id: pro-guxv
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: "Se borraron todos los artefactos por API y se puso retention-days: 3 en los upload-artifact (PR #34); GitHub tarda 6-12 h en recalcular"
---
# En Actions fallaban construir e instalador en todos los PR (las pruebas en verde)

En Actions fallaban construir e instalador en todos los PR (las pruebas en verde)

**Causa:** Cuota de almacenamiento de artefactos llena: ~13 GB acumulados, cada run de Windows subía ~360 MB sin caducidad

**Solución:** Se borraron todos los artefactos por API y se puso retention-days: 3 en los upload-artifact (PR #34); GitHub tarda 6-12 h en recalcular
