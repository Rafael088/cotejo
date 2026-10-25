"""Las capturas de una entrega, grandes, para comprobar un trabajo que se ve sin abrir nada.

Son funciones sueltas y no métodos del `Board`: las pintan la ficha y la revisión, y lo único
que necesitan es la anotación de `entregar`. Sin capturas devuelven None y quien llama no añade
nada, así que una entrega de siempre se ve igual que antes. Lo que hay en disco y cómo se
rotula sale de `tareas/capturas.py`, que no sabe de GTK.
"""

from gi.repository import Adw, Gtk

from .. import capturas
from .comun import ESPACIADO_SM, ESPACIADO_XS
from .escala import px
from .piezas import con_mano

# Lo más grande que sale una captura en la ficha (560 px de ancho) y en la revisión (880).
EN_FICHA = (480, 520)
EN_REVISION = (800, 560)


def _imagen(ruta, ancho, alto, maximo):
    """Una Gtk.Picture a la escala que cabe en `maximo`, sin agrandar lo que ya es pequeño."""
    escala = min(1.0, maximo[0] / max(ancho, 1), maximo[1] / max(alto, 1))
    imagen = Gtk.Picture.new_for_filename(ruta)
    imagen.set_can_shrink(True)
    imagen.set_content_fit(Gtk.ContentFit.CONTAIN)
    imagen.set_halign(Gtk.Align.START)
    imagen.set_size_request(px(round(ancho * escala)), px(round(alto * escala)))
    return imagen


def ver_entera(padre, una):
    """La captura a tamaño completo, en su propio diálogo y con barras si no cabe."""
    ancho, alto = una.get("ancho") or 800, una.get("alto") or 600
    dialogo = Adw.Dialog(title=f"{capturas.rotulo(una)} · {ancho}×{alto}",
                         content_width=px(min(ancho + 40, 1400)),
                         content_height=px(min(alto + 80, 900)))
    imagen = Gtk.Picture.new_for_filename(una["ruta"])
    imagen.set_can_shrink(False)
    vista = Adw.ToolbarView()
    vista.add_top_bar(Adw.HeaderBar())
    vista.set_content(Gtk.ScrolledWindow(child=imagen, vexpand=True))
    dialogo.set_child(vista)
    dialogo.present(padre)
    return dialogo


def seccion_capturas(entrega, padre, maximo=EN_FICHA, titulo=None):
    """La caja con las capturas de la entrega (cada una con su rótulo, clic para verla entera),
    o None si la entrega no trae ninguna. `titulo` es un Widget de cabecera opcional."""
    encontradas = capturas.de_la_entrega(entrega)
    if not encontradas:
        return None
    caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_SM),
                   css_classes=["capturas"])
    if titulo is not None:
        caja.append(titulo)
    fila = Gtk.Box(spacing=px(ESPACIADO_SM), halign=Gtk.Align.START)
    for una in encontradas:
        ancho, alto = una.get("ancho") or maximo[0], una.get("alto") or maximo[1]
        pieza = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS))
        pieza.append(Gtk.Label(label=f"{capturas.rotulo(una)} · {ancho}×{alto}", xalign=0,
                               css_classes=["revision-dato"]))
        boton = Gtk.Button(child=_imagen(una["ruta"], ancho, alto, maximo), css_classes=["flat"],
                           tooltip_text="Verla a tamaño completo")
        boton.connect("clicked", lambda _b, u=una: ver_entera(padre, u))
        boton.capturas_ruta = una["ruta"]
        pieza.append(con_mano(boton))
        fila.append(pieza)
    caja.append(Gtk.ScrolledWindow(child=fila, hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                                   vscrollbar_policy=Gtk.PolicyType.NEVER,
                                   propagate_natural_height=True))
    return caja
