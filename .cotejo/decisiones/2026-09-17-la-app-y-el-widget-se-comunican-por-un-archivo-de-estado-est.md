---
id: dec-rogf
fecha: 2026-09-17
temas: []
estado: aceptada
autor: importado
---
# La app y el widget se comunican por un archivo de estado (estado.json), con…

La app y el widget se comunican por un archivo de estado (estado.json), con tareas-obsidian --estado como red de seguridad

**Por qué:** QML no puede leer el vault, y que el widget escaneara solo cada N segundos sería lento y quedaría desfasado. Con la app viva el conteo cambia al instante; --estado no carga GTK y responde en 34 ms cuando la app no está corriendo

**Descartado:** Que el widget escanee el vault por su cuenta; hablar por D-Bus con la app
