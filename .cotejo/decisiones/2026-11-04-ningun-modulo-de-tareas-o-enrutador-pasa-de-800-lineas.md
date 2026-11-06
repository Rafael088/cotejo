---
id: dec-owvb
fecha: 2026-11-04
temas: [arquitectura]
estado: aceptada
autor: agente
aceptada_el: 2026-11-05
---
# Ningún módulo de tareas/ o enrutador/ pasa de 800 líneas

Tope de 800 líneas por módulo; lo nuevo del board va en la mezcla de Board a la que pertenece o en una nueva, nunca en ventana.py por comodidad. Los que ya lo pasaban (verbos.py, dot.py, importar_obsidian.py) están congelados: pueden bajar, no subir.

**Por qué:** tareas/app.py llegó a 3.721 líneas en tres semanas porque todo caía en Board.

**Lo vigila:** pruebas/test_tamano_de_modulos.py; si se pone roja, se parte el módulo.

Sale de «Lo que no se cambia sin decisión consciente» del CLAUDE.md (texto completo en ref-62y4); se propone al acortarlo en cotejo-d9cbol porque no había decisión vigente que la recogiera.
