---
id: dec-k9sg
fecha: 2026-09-24
temas: []
estado: aceptada
autor: importado
---
# Un solo archivo de config, ~/.config/cotejo/config.json, con fuente activa y parámetros…

Un solo archivo de config, ~/.config/cotejo/config.json, con fuente activa y parámetros por fuente; config init migra el viejo y lo renombra a config.json.migrado

**Por qué:** Dos archivos vivos es el fallo que se descubre tarde: cada skill escribe en uno y la app lee el otro. Renombrar en vez de borrar deja volver atrás

**Descartado:** Mantener ~/.config/tareas-obsidian como segundo archivo; borrar el viejo al migrar
