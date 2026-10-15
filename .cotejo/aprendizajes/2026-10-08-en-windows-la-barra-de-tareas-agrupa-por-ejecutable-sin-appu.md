---
id: apr-l979
fecha: 2026-10-08
temas: [windows, empaquetado, ui]
---
# En Windows la barra de tareas agrupa por ejecutable: sin AppUserModelID el board sale con el ícono de Python

Una app Python lanzada con pythonw.exe aparece en la barra de tareas con el ícono de Python, porque Windows agrupa por ejecutable salvo que el proceso declare un AppUserModelID. Hacen falta las tres cosas: SetCurrentProcessExplicitAppUserModelID(APP_ID) en app.main, el mismo AppUserModelID en los accesos de [Icons] de cotejo.iss y el ícono de la ventana pedido por nombre (Gtk.Window.set_default_icon_name) con el SVG dentro del paquete. Se verificó con la captura board-menu-inicio.png del run 36772520040.
