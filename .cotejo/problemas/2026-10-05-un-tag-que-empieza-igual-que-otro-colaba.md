---
id: pro-mdjj
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: "Límite propio (?![\\w/-]) en los tres regex de tags, que es donde de verdad termina un tag de Obsidian. No afectaba a ninguna tarea del vault de hoy: era una trampa esperando"
---
# Un tag que empieza igual que otro colaba

Un tag que empieza igual que otro colaba: una tarea con #en-curso-de-verdad aparecía sola en la columna Haciéndola, y su texto perdía el trozo que seguía al tag

**Causa:** El límite de la expresión regular era \b, y un guion no es carácter de palabra, así que \b casaba justo entre 'curso' y '-de-verdad'. Los tags de Obsidian admiten guiones, o sea que cualquier tag propio que empezara por #en-curso- o #por-validar- movía la tarea de columna

**Solución:** Límite propio (?![\w/-]) en los tres regex de tags, que es donde de verdad termina un tag de Obsidian. No afectaba a ninguna tarea del vault de hoy: era una trampa esperando
