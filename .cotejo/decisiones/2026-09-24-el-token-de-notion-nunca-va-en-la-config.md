---
id: dec-yrvu
fecha: 2026-09-24
temas: []
estado: aceptada
autor: importado
---
# El token de Notion nunca va en la config

El token de Notion nunca va en la config: se lee de NOTION_TOKEN o de ~/.config/cotejo/notion.token (permisos 600)

**Por qué:** El board y la barra los arrancan Hyprland y Quickshell, no una shell, así que no ven las variables de fish; el archivo llega a todos por igual y la config se puede enseñar o versionar sin filtrar nada

**Descartado:** Token en config.json; solo la variable de fish; env en la config de Hyprland
