"""Las piezas sueltas del board: iconos, chips, vacíos, el logo, avisos y deshacer."""

import math
import sys

from gi.repository import Adw, GLib, GObject, Gdk, Gtk, Pango

from .. import estado, marca, temas
from . import escala
from .comun import (
    DATOS, ESPACIADO_MD, ESPACIADO_SM, ESPACIADO_XS, LADO_ARRANQUE, REVELAR_MS, SALIDA_CARTA_MS,
    animaciones_activas,
)


def banda_de_avisos():
    """La banda que asoma cuando Cotejo no pudo leer algo.

    Un aviso en la interfaz no es adorno: una nota que no se lee deja de tener tareas, y eso
    en el board se ve exactamente igual que una nota que nunca las tuvo.
    """
    banda = Adw.Banner(revealed=False)
    banda.add_css_class("aviso-banda")
    return banda


def poner_avisos(banda, avisos):
    """El resumen en la banda y el detalle en su tooltip: enterarse cuesta un vistazo."""
    if not avisos:
        banda.set_revealed(False)
        return
    notas = [a for a in avisos if a.get("nota")]
    if notas:
        banda.set_title(f"No pude leer {len(notas)} nota{'s' if len(notas) > 1 else ''}: "
                        "sus tareas no salen aquí")
    else:
        banda.set_title(avisos[0]["motivo"])
    banda.set_tooltip_text("\n".join(
        f"{a['nota']}: {a['motivo']}" if a.get("nota") else a["motivo"] for a in avisos))
    banda.set_revealed(True)


def con_mano(widget):
    """El cursor de mano sobre lo que se pulsa: cartas, Comprobar, Revisar, Aprobar…"""
    widget.set_cursor_from_name("pointer")
    return widget


def etiquetar(widget, texto):
    """Nombre accesible para los botones que solo tienen ícono."""
    widget.update_property([Gtk.AccessibleProperty.LABEL], [texto])


def revelar_al_acercarse(fila, contenido):
    """Un Gtk.Revealer que abre `contenido` con el puntero o el foco sobre `fila`.

    Al salir cede 1,5 s después; volver (puntero o foco) cancela la espera, y destruir la
    carta al refrescar la cancela también. Sin animaciones (animaciones_activas) abre al
    instante, la misma señal que apaga --k-dur-hover.
    """
    revelador = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN,
                             reveal_child=False)
    revelador.set_child(contenido)
    estado = {"puntero": False, "foco": False, "espera": 0}

    def cancelar():
        if estado["espera"]:
            GLib.source_remove(estado["espera"])
            estado["espera"] = 0

    def cerrar():
        estado["espera"] = 0
        if not estado["puntero"] and not estado["foco"]:
            revelador.set_reveal_child(False)
        return GLib.SOURCE_REMOVE

    def cambio():
        if estado["puntero"] or estado["foco"]:
            cancelar()
            revelador.set_transition_duration(REVELAR_MS if animaciones_activas() else 0)
            revelador.set_reveal_child(True)
        elif revelador.get_reveal_child() and not estado["espera"]:
            revelador.set_transition_duration(REVELAR_MS if animaciones_activas() else 0)
            estado["espera"] = GLib.timeout_add(SALIDA_CARTA_MS, cerrar)

    movimiento = Gtk.EventControllerMotion()
    movimiento.connect("enter", lambda *_a: (estado.update(puntero=True), cambio()))
    movimiento.connect("leave", lambda *_a: (estado.update(puntero=False), cambio()))
    fila.add_controller(movimiento)
    foco = Gtk.EventControllerFocus()

    def foco_de_teclado():
        # Solo cuenta el foco que el teclado pidió. El que llega solo (el diálogo de detalle que
        # se cierra y devuelve el foco a la carta, la ventana que vuelve a activarse) no abre nada.
        raiz = fila.get_root()
        return bool(raiz and foco.contains_focus() and raiz.get_focus_visible())

    def refoco(*_a):
        estado["foco"] = foco_de_teclado()
        cambio()

    foco.connect("notify::contains-focus", refoco)
    fila.add_controller(foco)
    enganchada = []

    def a_la_ventana(*_a):
        # focus-visible se apaga al usar el ratón: una carta que seguía "con foco" tiene que ceder.
        raiz = fila.get_root()
        if raiz is None or raiz in enganchada:
            return
        enganchada.append(raiz)
        ids = [raiz.connect("notify::focus-visible", refoco)]
        fila.connect("destroy", lambda *_a: [raiz.disconnect(i) for i in ids
                                             if GObject.signal_handler_is_connected(raiz, i)])

    fila.connect("notify::root", a_la_ventana)
    a_la_ventana()
    fila.connect("destroy", lambda *_a: cancelar())
    revelador.estado_revelador = estado
    return revelador


class Logo(GObject.Object, Gdk.Paintable):
    """Una textura servida a un alto fijo, con el ancho que le toca por su proporción.

    Un `Gtk.Picture` pide el tamaño natural de lo que pinta, y un SVG rasterizado lo tiene en
    píxeles del archivo: la cabecera crecía hasta el alto del logo. Este pintable dice cuánto
    mide (`alto`) y dibuja la textura escalada, que sigue viéndose nítida en una pantalla de
    escala 2 porque el archivo es cuatro veces más ancho de lo que se muestra.
    """

    def __init__(self, textura, alto):
        super().__init__()
        self.textura, self.alto = textura, alto

    def do_get_intrinsic_height(self):
        return self.alto

    def do_get_intrinsic_width(self):
        return round(self.alto * self.textura.get_width() / self.textura.get_height())

    def do_snapshot(self, snapshot, ancho, alto):
        self.textura.snapshot(snapshot, ancho, alto)


def pintar_logo(logo, colores, alto=22):
    """El logo de Cotejo con los colores del tema: la palabra en el texto y el check en la señal.

    El archivo viene en blanco y Verde Hecho, que son el texto y la señal del tema oscuro. Con
    los colores fijos, en el tema claro la palabra blanca desaparecería sobre el papel y el
    verde no llegaría a 3:1; así sirve también en los temas que haga cada uno. Lo genera
    `docs/marca/generar.py`.
    """
    svg = (DATOS / "marca" / "cotejo-logo.svg").read_text()
    svg = svg.replace("#FFFFFF", colores["texto"]).replace("#16C98D", colores["senal"])
    try:
        textura = Gdk.Texture.new_from_bytes(GLib.Bytes.new(svg.encode()))
    except GLib.Error as error:
        # Sin cargador de SVG (pasó en Windows sin loaders.cache) el board abre sin logo: el
        # nombre del producto sigue en la cabecera, y una ventana sin logo es mejor que ninguna.
        print(f"Cotejo: no pude dibujar el logo ({error.message})", file=sys.stderr)
        logo.set_paintable(None)
        return
    logo.set_paintable(Logo(textura, alto))


def cabecera_de_marca(producto, con_botones_de_ventana):
    """La cabecera de marca del board: el logo de Cotejo, el nombre del producto y el subtítulo.

    El rediseño del board (07ab95a y siguientes) le agregó volver, su propia caja de
    búsqueda y un menú de más opciones, y cada ventana terminó armando la marca por su
    cuenta; aquí volvieron a divergir cosas que no tenían por qué —el subtítulo se llamaba
    igual pero se construía dos veces—. Lo que sigue siendo de cada ventana —buscar, el
    menú— no está aquí: por eso esta función no llama a `pack_start`, para que quien la
    use decida en qué orden empaca lo suyo alrededor de la marca.

    La política de botones de ventana (minimizar/maximizar/cerrar) también se decide una
    sola vez, no dos veces por casualidad: van donde la ventana no tiene su propia forma de
    cerrarse. CotejoBoard es la ventana grande y redimensionable y no tiene botón de cerrar
    propio, así que necesita los del sistema para minimizarse, maximizarse o cerrarse.

    El logo es la palabra «Cotejo» con la C del check; al lado va el producto («Board») en
    tenue, para que la marca sea una sola y el board, una parte de ella.

    Devuelve (cabecera, caja_titulo, subtitulo, logo); el logo sale vacío y lo pinta
    `pintar_logo`, que necesita los colores del tema.
    """
    cabecera = Adw.HeaderBar(show_start_title_buttons=con_botones_de_ventana,
                             show_end_title_buttons=con_botones_de_ventana)
    caja_titulo = Gtk.Box(spacing=ESPACIADO_MD, halign=Gtk.Align.START)
    textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
    nombre = Gtk.Box(spacing=ESPACIADO_SM, halign=Gtk.Align.START)
    logo = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, can_shrink=False,
                       alternative_text="Cotejo", valign=Gtk.Align.END)
    nombre.append(logo)
    nombre.append(Gtk.Label(label=producto, valign=Gtk.Align.END,
                            css_classes=["marca-titulo", "marca-producto"]))
    textos.append(nombre)
    subtitulo = Gtk.Label(xalign=0, css_classes=["marca-subtitulo"])
    textos.append(subtitulo)
    caja_titulo.append(textos)
    cabecera.set_title_widget(Gtk.Box())
    return cabecera, caja_titulo, subtitulo, logo


def chip(texto, nombre_icono="", *clases, tooltip="", maximo=0):
    """Una de las pastillas de una carta: el agente, la dificultad, dónde vive.

    Lleva icono además del texto porque en una carta hay tres seguidas y todas son texto
    mono del mismo tamaño: sin forma que las separe hay que leerlas para saber cuál es cuál.
    """
    caja = Gtk.Box(spacing=ESPACIADO_XS, css_classes=["chip", *clases],
                   valign=Gtk.Align.CENTER)
    if nombre_icono:
        caja.append(icono(nombre_icono, 12))
    etiqueta = Gtk.Label(label=texto)
    if maximo:
        etiqueta.set_max_width_chars(maximo)
        etiqueta.set_ellipsize(Pango.EllipsizeMode.END)
    caja.append(etiqueta)
    if tooltip:
        caja.set_tooltip_text(tooltip)
    return caja


def vacio(nombre_icono, titulo, pista, roto=False):
    """El estado vacío de Cotejo: icono propio, título y pista, alineados a la izquierda.

    Habla con los tokens del tema y con los iconos de `data/iconos`, no con el
    `Adw.StatusPage` de Adwaita, que traía su tipografía y su gris.
    `roto` es para cuando no es que no haya nada, sino que no se puede leer: va en ámbar.
    Los márgenes los pone quien lo coloca, que es quien sabe dónde cae.
    """
    clases = ["vacio"] + (["roto"] if roto else [])
    caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=clases,
                   spacing=ESPACIADO_XS)
    # A la izquierda como el texto que lleva debajo: una imagen se centra sola si no se
    # le dice, y quedaba fuera del eje de su propio título.
    marca = icono(nombre_icono, 20, "vacio-icono")
    marca.set_halign(Gtk.Align.START)
    caja.append(marca)
    caja.append(Gtk.Label(label=titulo, xalign=0, wrap=True, css_classes=["vacio-titulo"]))
    caja.append(Gtk.Label(label=pista, xalign=0, wrap=True, css_classes=["vacio-pista"]))
    return caja


def muestra_de_tema(colores):
    """Un board en miniatura pintado con los colores de un tema: ventana, carta, texto y acento.

    Se dibuja y no se arma con widgets porque sus colores no pueden salir del CSS: el CSS
    lleva los del tema en uso, y la muestra enseña los de otro.
    """
    rgba = {token: temas.color(colores[token]) for token in ("fondo", "borde", "superficie",
                                                           "texto", "tenue", "senal")}

    def rectangulo(cr, x, y, ancho, alto, radio):
        cr.new_sub_path()
        cr.arc(x + ancho - radio, y + radio, radio, -math.pi / 2, 0)
        cr.arc(x + ancho - radio, y + alto - radio, radio, 0, math.pi / 2)
        cr.arc(x + radio, y + alto - radio, radio, math.pi / 2, math.pi)
        cr.arc(x + radio, y + radio, radio, math.pi, 3 * math.pi / 2)
        cr.close_path()

    def poner(cr, token):
        r, g, b, a = rgba[token]
        cr.set_source_rgba(r / 255, g / 255, b / 255, a)

    def dibujar(_area, cr, ancho, alto):
        rectangulo(cr, 0.5, 0.5, ancho - 1, alto - 1, 6)
        poner(cr, "fondo")
        cr.fill_preserve()
        poner(cr, "borde")
        cr.set_line_width(1)
        cr.stroke()
        rectangulo(cr, 7, 7, ancho - 14, alto - 14, 4)
        poner(cr, "superficie")
        cr.fill()
        for token, y, largo in (("texto", 12, 0.6), ("tenue", 18, 0.4)):
            rectangulo(cr, 11, y, (ancho - 22) * largo, 3, 1.5)
            poner(cr, token)
            cr.fill()
        rectangulo(cr, ancho - 24, alto - 15, 13, 5, 2.5)
        poner(cr, "senal")
        cr.fill()

    area = Gtk.DrawingArea(content_width=56, content_height=38, valign=Gtk.Align.CENTER)
    area.set_draw_func(dibujar)
    return area


def vaciar(caja):
    """Quita todos los hijos de una lista o una caja de GTK 4, que no trae cómo."""
    hijo = caja.get_first_child()
    while hijo is not None:
        siguiente = hijo.get_next_sibling()
        caja.remove(hijo)
        hijo = siguiente


def icono(nombre, tamano=16, *clases):
    """Uno de los iconos de `data/iconos`, del tamaño y con las clases que se le pidan.

    Se piden por nombre y no por archivo a propósito: así GTK los trata como simbólicos y
    les aplica el `color` del CSS, que es lo que deja al mismo dibujo cambiar de color
    según dónde esté. `data/iconos/generar.py` explica por qué están dibujados como están.
    El tamaño se pide sin escalar: en Windows lo escala `escala` y lo vuelve a escalar si la
    ventana pasa a otro monitor, para lo que apunta el de partida en `cotejo_tamano`.
    """
    imagen = Gtk.Image(icon_name=f"cotejo-{nombre}-symbolic", pixel_size=escala.tamano(tamano),
                       css_classes=list(clases))
    imagen.cotejo_tamano = tamano
    return imagen


class Finalizadas:
    """Lo que se acaba de dar por terminado, para poder echarlo atrás.

    Marcar tres tareas seguidas dejaba un solo aviso en pie —cada uno tapaba al anterior— y
    con él un solo «Deshacer»: las dos primeras se volvían irreversibles sin que nadie lo
    dijera, que es la peor forma de quitarle a alguien la posibilidad de arrepentirse.
    Ahora se cuentan y se deshacen de una en una, la última primero, que es el orden en que
    uno se arrepiente.

    El aviso se sustituye en vez de acumularse, así que hay que distinguir el aviso que se
    va porque lo reemplazamos del que se va porque se acabó su tiempo: solo el segundo
    significa «ya no vas a deshacer nada» y vacía la pila. Por eso `olvidar` compara con el
    aviso que está puesto ahora mismo en vez de fiarse de que la señal llegue en orden.
    """

    def __init__(self, toasts, deshacer_una, al_terminar):
        self.toasts = toasts
        self.deshacer_una = deshacer_una  # (tarea) -> None; escribe en la fuente
        self.al_terminar = al_terminar    # repintar, después de deshacer
        self.pila = []
        self.toast = None

    def anotar(self, tarea):
        self.pila.append(tarea)
        self.mostrar()

    def mostrar(self):
        anterior, self.toast = self.toast, None
        if anterior is not None:
            anterior.dismiss()
        cuantas = len(self.pila)
        titulo = ("Tarea finalizada" if cuantas == 1
                  else f"{cuantas} tareas finalizadas · se deshace la última")
        self.toast = Adw.Toast(title=titulo, button_label="Deshacer", timeout=6)
        self.toast.connect("button-clicked", lambda *_: self.deshacer())
        self.toast.connect("dismissed", self.olvidar)
        self.toasts.add_toast(self.toast)

    def olvidar(self, toast):
        if toast is self.toast:
            self.pila.clear()
            self.toast = None

    def deshacer(self):
        if not self.pila:
            return
        self.deshacer_una(self.pila.pop())
        if self.pila:
            self.mostrar()
        else:
            self.toast = None
        self.al_terminar()


class TareaArrastrada(GObject.Object):
    """Lo que viaja dentro de un arrastre: la tarea y su proyecto.

    Es un tipo propio, y no texto, para que el board acepte solo sus propias cartas y no
    cualquier cosa que se suelte encima desde otra ventana.
    """

    def __init__(self, proyecto, tarea):
        super().__init__()
        self.proyecto = proyecto
        self.tarea = tarea


def dibujar_arranque(cr, ancho, alto, t, colores):
    """Un fotograma de la animación de arranque: la C a medio dibujar y el check entrando.

    La C se dibuja recortándola con un sector que crece desde su punta de abajo, así sus dos
    cortes a escuadra son los del logo en el último fotograma y no unos redondeados; el check,
    con un trazo discontinuo que se alarga, con sus puntas redondas. La geometría es la del logo
    (`tareas/marca.py`), en sus unidades, escalada al centro del área.
    """
    geo = marca.LETRA
    x0, y0, x1, y1 = marca.caja(geo)
    escala = LADO_ARRANQUE / max(x1 - x0, y1 - y0)
    cr.translate(ancho / 2, alto / 2)
    cr.scale(escala, escala)
    cr.translate(-(x0 + x1) / 2, -(y0 + y1) / 2)
    parte_c, parte_check = marca.trazos(t)

    def poner(token):
        r, g, b, a = temas.color(colores[token]) or (128, 128, 128, 1.0)
        cr.set_source_rgba(r / 255, g / 255, b / 255, a)

    (cx, cy) = geo["centro"]
    if parte_c > 0:
        fuera, dentro, f0, d0, f1, d1 = marca.puntas(geo)
        desde, recorre = marca.barrido(geo)
        cr.save()
        cr.move_to(cx, cy)
        cr.arc(cx, cy, fuera * 2, desde, desde + recorre * parte_c)
        cr.close_path()
        cr.clip()
        cr.move_to(*f0)
        cr.arc(cx, cy, fuera, desde, desde + recorre)
        cr.line_to(*d1)
        cr.arc_negative(cx, cy, dentro, marca.angulo(geo, d1), marca.angulo(geo, d0))
        cr.close_path()
        poner("texto")
        cr.fill()
        cr.restore()
    if parte_check > 0:
        largo = marca.largo_del_check(geo)
        cr.move_to(*geo["check"][0])
        for punto in geo["check"][1:]:
            cr.line_to(*punto)
        cr.set_line_width(geo["grosor"])
        cr.set_line_cap(1)    # cairo.LINE_CAP_ROUND
        cr.set_line_join(1)   # cairo.LINE_JOIN_ROUND
        cr.set_dash([largo * parte_check, largo * 2])
        poner("senal")
        cr.stroke()
