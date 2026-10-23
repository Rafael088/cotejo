---
id: dec-hgq7
fecha: 2026-10-22
temas: [fase-2, inicio, producto]
estado: propuesta
autor: agente
reemplaza: dec-22dl
---
# El inicio en la app crea proyectos de punta a punta

Reemplaza la decisión del 2026-10-10 (dec-22dl, y su «Camino sin terminal: No»). El board tiene una pestaña Inicio que se abre primero, antes que el board, y crea proyectos de punta a punta sin que la persona toque la terminal. Un formulario guiado sin IA recoge las respuestas, Cotejo arma el prompt, lanza el agente por detrás y la app muestra el progreso en vivo hasta que el proyecto queda inicializado. Por qué: la persona que no programa no debe depender de la CLI de un agente para empezar. Se toca la regla del maestro: headless (claude -p) se permite solo para preparar un proyecto desde el inicio y siempre con progreso visible en la app; para todo lo demás el motor sigue siendo agente y el maestro se abre en una terminal que se ve. Crear un proyecto sigue sin ser un verbo nuevo de la CLI: el inicio llama a init. En Linux se distribuye como AppImage, y Cotejo solo enlaza a la página oficial de cada agente, sin instalarlo. Descartado: reemplazar el board por el inicio, y headless como defecto o en segundo plano sin progreso.
