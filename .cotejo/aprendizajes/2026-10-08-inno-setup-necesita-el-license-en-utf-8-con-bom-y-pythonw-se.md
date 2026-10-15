---
id: apr-eu9n
fecha: 2026-10-08
temas: [windows, empaquetado]
---
# Inno Setup necesita el LICENSE en UTF-8 con BOM; y pythonw se traga los errores en silencio

Dos trampas del empaquetado de Windows de la 1.0. (1) La página de licencia de Inno Setup muestra mal las tildes si el LICENSE no lleva BOM: construir.py (copiar_app) escribe app\LICENSE con utf-8-sig y deja intacto el del repo, y probar_instalado.py comprueba el BOM. (2) bin\cotejoboard.exe arranca con pythonw.exe, que no tiene consola: cualquier excepción mata el board sin decir nada (pasó en un PC limpio). Para diagnosticar hay que correr bin\cotejo.exe --board en cmd, y el board tiene que capturar sus excepciones y guardarlas en un archivo de estado.
