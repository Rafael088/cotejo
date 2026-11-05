---
id: dec-vps5
fecha: 2026-11-04
temas: [rutas, windows]
estado: propuesta
autor: agente
---
# Ninguna ruta de config o de estado se escribe a mano: salen de tareas/rutas.py

Toda ruta de config o estado sale de tareas/rutas.py, que sabe dónde van en Linux, macOS y Windows.

**Por qué:** una ruta literal funciona en la máquina del autor y rompe en otro sistema; en Linux no cambió ninguna porque el widget lee de ahí.

**Lo vigila:** pruebas/test_rutas.py, roja con un ".config" o ".local" literal fuera de su sitio.

Sale de «Lo que no se cambia sin decisión consciente» del CLAUDE.md (texto completo en ref-62y4); se propone al acortarlo en cotejo-d9cbol porque no había decisión vigente que la recogiera.
