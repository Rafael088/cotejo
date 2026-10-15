---
id: apr-2bnz
fecha: 2026-10-05
temas: []
---
# Para probar una app GTK/Adwaita sin tocar la instancia que ya corre (mismo APP_ID)

Para probar una app GTK/Adwaita sin tocar la instancia que ya corre (mismo APP_ID): lanzarla con dbus-run-session y config y estado temporales (COTEJO_CONFIG, XDG_STATE_HOME). Para capturarla sin depender del compositor (ventana en otro workspace), renderizarla desde dentro: Gtk.WidgetPaintable + Gtk.Snapshot + renderer.render_texture(...).save_to_png().
