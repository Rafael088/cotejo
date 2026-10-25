"""`Board`: la ventana, y lo que junta las mezclas de cada parte."""

from gi.repository import Adw, GLib, Gdk, Gtk
from enrutador import config as enrutador_config

from .. import almacen, decision, estado, fuente as f, marca, modelo, temas
from . import comun, escala
from .comun import (
    ATAJOS, ENTRADA_MS, ESPACIADO_MD, ESPACIADO_SM, ESPACIADO_XL, MARGEN_TABLERO_LADOS,
    MARGEN_TABLERO_VERTICAL, agentes_disponibles, animaciones_activas, aplicar_clase_animaciones,
)
from .escala import px
from .piezas import (
    Finalizadas, banda_de_avisos, cabecera_de_marca, dibujar_arranque, etiquetar, icono,
    muestra_de_tema, pintar_logo, poner_avisos,
)
from .banda import Banda
from .capa_dot import CapaDot
from .cartas import Cartas
from .columnas import Columnas
from .decisiones import Decisiones
from .detalle import Detalle
from .maestro import Maestro
from .movimientos import Movimientos
from .pie import Pie
from .teclado import Teclado
from .vista_resumen import Resumen
from .vista_revision import Revision


class Board(Maestro, Columnas, Banda, Pie, Cartas, Detalle, Decisiones, Revision, Resumen, Teclado,
            Movimientos, CapaDot, Adw.ApplicationWindow):
    """Las tareas en sus cuatro estados, un proyecto a la vez.

    Es el lado humano del flujo de agentes: el agente mueve de Pendiente a Haciéndola y de ahí
    a Para comprobar; finalizar sigue siendo la única transición que hace una persona.
    Por eso esta ventana sí se diseña para gente, aunque el resto de la app se diseñe para agentes:
    el contrato con el agente son los tags del Markdown, y nada de lo de aquí lo toca.

    Mover una tarea se hace de tres maneras que terminan en la misma escritura del Markdown:
    arrastrando la carta, con `Ctrl+←` / `Ctrl+→`, o desde el menú `⋮`.
    """

    def __init__(self, app):
        super().__init__(application=app, title="CotejoBoard")
        self.app = app
        self.fuente = app.fuente
        self.set_default_size(*self.tamano_inicial())
        self.columnas = {}
        self.agentes = agentes_disponibles()
        self.orden = [clave for clave, _ in modelo.COLUMNAS]
        estado_board = comun.cargar_board()
        self.seleccion = estado_board.get("proyecto")
        # El filtro de fechas de Finalizada (v1.2.2): por defecto, los últimos 7 días. Vive en
        # `board.json`, fuera del vault, como el proyecto elegido: es de la interfaz, no de la
        # tarea. Se lee antes de montar las columnas porque el botón del filtro nace marcando
        # la opción que ya estaba elegida.
        claves_filtro = {clave for clave, _nombre, _dias in modelo.FILTROS_FINALIZADA}
        guardado = estado_board.get("filtro_finalizada")
        self.filtro_finalizada = guardado if guardado in claves_filtro else modelo.FILTRO_FINALIZADA_DEFECTO
        self.ventana_finalizada = None  # la ventana de Finalizadas, si está abierta
        for propiedad in ("maximized", "fullscreened"):
            self.connect(f"notify::{propiedad}", lambda *_a: self.al_cambiar_de_tamano())
        self.animacion = None
        self.arrastre = None  # la carta que se está arrastrando ahora mismo
        self.filtro = ""  # lo escrito en la búsqueda, ya en minúsculas
        self.foco_tras_pintar = None  # id al que llevar el foco en el próximo repintado
        # Lo que dio «Volver a comprobar» por id de tarea (B4). Vive en memoria y no en la
        # bitácora: comprobar es leer, y no deja rastro en el historial de la tarea.
        self.comprobaciones = {}

        # Alias de personas (nombres adicionales que cuentan como humanos)
        config_enrutador = enrutador_config.cargar()
        self.alias_persona = tuple(config_enrutador.get("alias_persona") or ("persona",))

        self.toasts = Adw.ToastOverlay()
        self.finalizadas = Finalizadas(self.toasts, self.desmarcar, self.app.refrescar)
        vista = Adw.ToolbarView()
        self.toasts.set_child(vista)
        # El board va dentro de una pila para que la animación de arranque pueda ir delante y
        # fundirse en él (`mostrar_arranque`). Sin animación, la pila solo tiene el board.
        self.pila = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE,
                              transition_duration=marca.FUNDIDO_MS)
        self.pila.add_named(self.toasts, "board")
        self.animacion_arranque = None
        self.set_content(self.pila)

        cabecera, caja_titulo, self.subtitulo, self.logo = cabecera_de_marca(
            "Board", con_botones_de_ventana=True)
        pintar_logo(self.logo, app.colores)
        cabecera.pack_start(caja_titulo)

        # De derecha a izquierda: lo que se usa a diario queda suelto y lo demás se guarda.
        cabecera.pack_end(self.menu_cabecera())
        self.boton_recargar = Gtk.Button(icon_name="cotejo-recargar-symbolic", css_classes=["flat"],
                                         tooltip_text="Recargar (Ctrl+R)")
        etiquetar(self.boton_recargar, "Recargar")
        self.boton_recargar.connect("clicked", lambda *_: self.app.refrescar())
        cabecera.pack_end(self.boton_recargar)
        boton_tema = Gtk.Button(icon_name="cotejo-tema-symbolic", css_classes=["flat"],
                                tooltip_text="Tema")
        etiquetar(boton_tema, "Elegir el tema")
        boton_tema.connect("clicked", lambda *_: self.ver_temas())
        cabecera.pack_end(boton_tema)
        cabecera.pack_end(self.caja_busqueda())
        vista.add_top_bar(cabecera)
        self.banda = banda_de_avisos()
        vista.add_top_bar(self.banda)

        # Banda de proyectos + columnas. Elegir proyecto es lo que hace humano el board.
        vista.add_top_bar(self.crear_banda_proyectos())

        # homogeneous=False: las columnas ya no miden lo mismo (ver ANCHO_COLUMNAS).
        self.tablero = Gtk.Box(spacing=px(ESPACIADO_SM), vexpand=True, halign=Gtk.Align.CENTER,
                               margin_top=px(MARGEN_TABLERO_VERTICAL),
                               margin_bottom=px(MARGEN_TABLERO_VERTICAL),
                               margin_start=px(MARGEN_TABLERO_LADOS),
                               margin_end=px(MARGEN_TABLERO_LADOS))
        self.altura_encabezados = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.VERTICAL)
        for indice, (clave, nombre) in enumerate(modelo.COLUMNAS):
            self.tablero.append(self.columna(indice, clave, nombre))

        cuerpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        # Con las columnas ya no midiendo lo mismo, una ventana estrecha dejaba la última
        # fuera de la pantalla y sin forma de llegar a ella. Antes no pasaba porque todas
        # encogían a la vez. Así que el tablero se desplaza: el mínimo de cada columna se
        # respeta y lo que no cabe se alcanza, en vez de dejar de existir.
        self.scroll_tablero = Gtk.ScrolledWindow(child=self.tablero, hexpand=True, vexpand=True,
                                                 vscrollbar_policy=Gtk.PolicyType.NEVER,
                                                 hscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
        cuerpo.append(self.scroll_tablero)
        # Las columnas ceden ancho (hasta su piso) cuando la ventana es estrecha.
        self.scroll_tablero.get_hadjustment().connect(
            "notify::page-size", lambda *_a: self.ajustar_columnas())

        self.pie = self.crear_pie()
        cuerpo.append(self.pie)
        # El dot (D5) va en un overlay sobre el tablero y el pie: no empuja ni tapa nada.
        self.encima = Gtk.Overlay(child=cuerpo)
        self.montar_dot()
        vista.set_content(self.encima)

        teclas = Gtk.EventControllerKey()
        teclas.connect("key-pressed", self.al_tecla)
        self.add_controller(teclas)
        # Alt+← → es del dot, y se oye antes que las columnas: ellas ya usan ← → y Ctrl+← →, y
        # sin la fase de captura tomarían Alt+← como un ← suelto.
        teclas_dot = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        teclas_dot.connect("key-pressed", self.al_tecla_dot)
        self.add_controller(teclas_dot)
        aplicar_clase_animaciones(self)
        self.pintar()

    @staticmethod
    def tamano_inicial():
        """1280 × 820 a la escala de ahora. Lo que la escala añade no pasa del 90 % de la
        pantalla (a 150 % serían 1920 × 1230, más alto que un portátil de 1080), pero nunca
        queda por debajo de los 1280 × 820 de siempre: con escala 1, lo de antes."""
        ancho, alto = px(1280), px(820)
        monitores = Gdk.Display.get_default().get_monitors()
        if monitores.get_n_items():
            zona = monitores.get_item(0).get_geometry()
            ancho = min(ancho, max(1280, int(zona.width * 0.9)))
            alto = min(alto, max(820, int(zona.height * 0.9)))
        return ancho, alto

    def ajustar_columnas(self):
        anchos = comun.anchos_columnas(int(self.scroll_tablero.get_hadjustment().get_page_size()))
        caja = self.tablero.get_first_child()
        for clave, _nombre in modelo.COLUMNAS:
            if caja is None:
                break
            if clave in comun.ANCHO_MINIMO_COLUMNAS:
                caja.set_size_request(anchos[clave], -1)
            caja = caja.get_next_sibling()

    def al_tecla(self, _control, tecla, _codigo, estado):
        control = bool(estado & Gdk.ModifierType.CONTROL_MASK)
        if tecla == Gdk.KEY_Escape:
            # Con algo buscado, Escape borra la búsqueda antes de cerrar nada: cerrar la
            # ventana entera por querer ver otra vez todas las tareas es perder el sitio.
            if self.filtro:
                self.busqueda.set_text("")
                return True
            self.close()
            return True
        if control and tecla in (Gdk.KEY_question, Gdk.KEY_interrogdown):
            self.ver_atajos()
            return True
        if control and tecla in (Gdk.KEY_z, Gdk.KEY_Z):
            self.finalizadas.deshacer()
            return True
        return False

    # --- cabecera ------------------------------------------------------

    def caja_busqueda(self):
        """Buscar deja de estar detrás de un botón y dice con qué tecla se llama.

        Era la única acción del board que había que adivinar. La tecla se enseña hasta que
        se usa: una vez que hay algo escrito, el hueco lo ocupa lo que estás buscando.
        """
        caja = Gtk.Box(spacing=px(ESPACIADO_SM), css_classes=["buscador"], valign=Gtk.Align.CENTER)
        caja.append(icono("buscar", 16))
        self.busqueda = Gtk.Entry(placeholder_text="Buscar tareas", has_frame=False,
                                  width_chars=14)
        etiquetar(self.busqueda, "Buscar tareas")
        self.busqueda.connect("changed", self.al_buscar)
        caja.append(self.busqueda)
        self.atajo_busqueda = Gtk.Label(label="Ctrl F", css_classes=["atajo"])
        caja.append(self.atajo_busqueda)
        return caja

    def al_buscar(self, entrada):
        self.filtro = entrada.get_text().strip().lower()
        self.atajo_busqueda.set_visible(not self.filtro)
        self.pintar_columnas()

    def menu_cabecera(self):
        boton = Gtk.MenuButton(icon_name="cotejo-mas-symbolic", css_classes=["flat"],
                               tooltip_text="Más opciones")
        etiquetar(boton, "Más opciones")
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                       margin_top=px(ESPACIADO_SM), margin_bottom=px(ESPACIADO_SM),
                       margin_start=px(ESPACIADO_SM), margin_end=px(ESPACIADO_SM))
        popover = Gtk.Popover(child=caja, position=Gtk.PositionType.BOTTOM, halign=Gtk.Align.END)
        boton.set_popover(popover)
        for texto, nombre_icono, atajo, funcion in (
                ("Atajos de teclado", "teclado", "Ctrl ?", self.ver_atajos),):
            fila = Gtk.Box(spacing=px(ESPACIADO_MD))
            fila.append(icono(nombre_icono, 15))
            rotulo = Gtk.Label(label=texto, xalign=0, hexpand=True)
            fila.append(rotulo)
            fila.append(Gtk.Label(label=atajo, css_classes=["menu-atajo"]))
            opcion = Gtk.Button(css_classes=["flat", "menu-item"], child=fila)
            opcion.connect("clicked", lambda _b, f=funcion, p=popover: (p.popdown(), f()))
            caja.append(opcion)
        caja.append(self.fila_tamano(popover))
        return boton

    def fila_tamano(self, popover):
        """Tamaño: 100, 125 o 150 % de todo el board, sobre la escala que ya pone la pantalla.

        Los tres a la vista y no en un diálogo: es un ajuste de un clic y se ve al momento.
        """
        fila = Gtk.Box(spacing=px(ESPACIADO_MD), css_classes=["menu-item", "menu-tamano"])
        fila.append(icono("tamano", 15))
        fila.append(Gtk.Label(label="Tamaño", xalign=0, hexpand=True))
        grupo = Gtk.Box(css_classes=["linked"])
        primero = None
        for tamano in escala.TAMANOS:
            opcion = Gtk.ToggleButton(label=f"{tamano} %", active=tamano == self.app.tamano,
                                      group=primero, css_classes=["tamano"])
            etiquetar(opcion, f"Tamaño al {tamano} %")
            opcion.connect("toggled", self.al_elegir_tamano, tamano, popover)
            primero = primero or opcion
            grupo.append(opcion)
        fila.append(grupo)
        return fila

    def al_elegir_tamano(self, opcion, tamano, popover):
        if not opcion.get_active() or tamano == self.app.tamano:
            return
        popover.popdown()
        problema = self.app.elegir_tamano(tamano)
        if problema:
            self.aviso(problema)

    def al_cambiar_de_tamano(self):
        """Maximizada o a pantalla completa, sin esquinas ni sombra (ver `.a-pantalla`)."""
        if self.is_maximized() or self.is_fullscreen():
            self.add_css_class("a-pantalla")
        else:
            self.remove_css_class("a-pantalla")

    def ver_atajos(self):
        """Lo que el board ya sabía hacer sin mouse, escrito en un sitio.

        Todo esto funcionaba desde antes; lo que faltaba era dónde enterarse.
        """
        dialogo = Adw.AlertDialog(heading="Atajos de teclado")
        rejilla = Gtk.Grid(row_spacing=px(ESPACIADO_SM), column_spacing=px(ESPACIADO_XL))
        for fila, (atajo, que) in enumerate(ATAJOS):
            rejilla.attach(Gtk.Label(label=atajo, xalign=1, css_classes=["menu-atajo"]), 0, fila, 1, 1)
            rejilla.attach(Gtk.Label(label=que, xalign=0), 1, fila, 1, 1)
        dialogo.set_extra_child(rejilla)
        dialogo.add_response("cerrar", "Cerrar")
        dialogo.present(self)

    def ver_temas(self):
        """El selector de temas: se elige y se ve al momento. Aquí no se edita ni se crea nada.

        Crear un tema es escribir un archivo de tokens y comprobar que se lee (`cotejo temas
        nuevo`, `cotejo temas comprobar`), y eso lo hace un agente por la CLI. Un tema que no
        pasa la comprobación sale en la lista, pero apagado y diciendo por qué: esconderlo
        dejaría a quien lo creó preguntándose dónde está.
        """
        dialogo = Adw.AlertDialog(heading="Tema",
                                  body="Aquí solo se elige. Un tema nuevo lo crea y lo "
                                       "comprueba un agente con «cotejo temas».")
        lista = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        orden = []  # el id de cada fila, por su posición
        marcas = {}

        def marcar():
            for ident, marca in marcas.items():
                marca.set_visible(ident == self.app.tema)

        def al_activar(_lista, fila):
            problema = self.app.elegir_tema(orden[fila.get_index()])
            marcar()
            if problema:
                self.aviso(problema)

        lista.connect("row-activated", al_activar)
        for uno in (temas.resumen(i, r, de_fabrica, self.app.tema)
                    for i, (r, de_fabrica) in sorted(temas.disponibles().items())):
            fila = Adw.ActionRow(title=GLib.markup_escape_text(uno.get("nombre") or uno["id"]),
                                 activatable=uno["ok"], sensitive=uno["ok"])
            orden.append(uno["id"])
            if uno["ok"]:
                datos = temas.cargar(uno["id"])
                if datos.get("descripcion"):
                    fila.set_subtitle(GLib.markup_escape_text(datos["descripcion"]))
                fila.add_prefix(muestra_de_tema(datos["colores"]))
            else:
                fila.set_subtitle(GLib.markup_escape_text(
                    "No se puede usar: " + uno["problemas"][0]))
            marca = icono("estado-hecha", 16, "en-cotejo")
            etiquetar(marca, "En uso")
            marcas[uno["id"]] = marca
            fila.add_suffix(marca)
            lista.append(fila)
        marcar()
        dialogo.set_extra_child(lista)
        dialogo.add_response("cerrar", "Listo")
        dialogo.present(self)

    def vigilar_teclas(self, widget, funcion, *datos):
        """Las teclas se miran en captura: antes de que el ListBox use Tab o las flechas."""
        control = Gtk.EventControllerKey()
        control.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        control.connect("key-pressed", funcion, *datos)
        widget.add_controller(control)

    def proyectos_con_tareas(self):
        return [p for p in self.app.proyectos if p.tareas or p.hechas]

    def decisiones_de(self, proyecto):
        """Las decisiones `propuesta` del almacén `.cotejo/` de este proyecto (C5, v1.2).

        Solo los proyectos que son, o migraron a, un repo de git tienen almacén:
        `fuente.carpeta_de` es `None` para los demás (hoy, cualquiera que siga solo en
        Obsidian) y no hay nada que pintar. Un repo sin `.cotejo/` tampoco es un error aquí,
        es que ese proyecto no se migró todavía. Devuelve `[(Almacen, Entrada)]`.
        """
        carpeta = self.fuente.carpeta_de(proyecto.nombre)
        if not carpeta:
            return []
        alm = almacen.Almacen(carpeta)
        if not alm.existe():
            return []
        return [(alm, entrada) for entrada in decision.propuestas(alm)]

    def pintar(self):
        # Los menús de asignar se construyen al pintar: si un modelo se registra con el board
        # abierto, tiene que salir en el menú sin reiniciar la app.
        self.agentes = agentes_disponibles()
        poner_avisos(self.banda, self.app.avisos)
        self.pintar_banda()
        self.pintar_columnas()
        # El medidor cambia cuando un agente llama a la CLI, no cuando cambia el vault, así
        # que se refresca con lo demás —al recargar y en cada cambio— y no se vigila aparte:
        # es un número para consultar, no un aviso que tenga que llegar al instante.
        self.pintar_ahorro()

    def poner_subtitulo(self, proyectos, todos):
        esperando = sum(1 for p in proyectos for t in p.tareas if t.estado == "por-validar")
        donde = "en todos los proyectos" if todos else (proyectos[0].nombre if proyectos else "")
        if esperando:
            texto = f"{esperando} esperando que las compruebes · {donde}"
            self.subtitulo.add_css_class("en-cotejo")
        else:
            faltan = sum(len(p.tareas) for p in proyectos)
            texto = f"{faltan} sin terminar · {donde}"
            self.subtitulo.remove_css_class("en-cotejo")
        self.subtitulo.set_label(texto)

    def mostrar_arranque(self):
        """La marca cargando antes que el board: la C se dibuja y el check entra a cerrarla.

        Solo la pide `App.abrir_board` cuando el proceso arrancó con la ventana (no venía de
        segundo plano) y con gtk-enable-animations encendido. El board ya está construido
        debajo; esto le añade ARRANQUE_MS + FUNDIDO_MS y no espera a nada más.
        """
        area = Gtk.DrawingArea(hexpand=True, vexpand=True)
        area.instante = 0.0
        colores = self.app.colores
        area.set_draw_func(lambda _a, cr, ancho, alto: dibujar_arranque(
            cr, ancho, alto, area.instante, colores))
        area.update_property([Gtk.AccessibleProperty.LABEL], ["Cotejo"])
        self.pila.add_named(area, "arranque")
        self.pila.set_visible_child_full("arranque", Gtk.StackTransitionType.NONE)

        def avanzar(valor):
            area.instante = valor
            area.queue_draw()

        def terminar(*_args):
            self.pila.set_visible_child_name("board")
            # El dot entra cuando el board ya se ve: después del fundido del logo.
            GLib.timeout_add(marca.FUNDIDO_MS, lambda: self.entrar_dot() and False)
            # Fuera de la pila cuando acabe el fundido: no tiene por qué seguir viva.
            GLib.timeout_add(marca.FUNDIDO_MS + 50, lambda: (self.pila.remove(area), False)[1])
            self.animacion_arranque = None

        objetivo = Adw.CallbackAnimationTarget.new(avanzar)
        self.animacion_arranque = Adw.TimedAnimation.new(area, 0, 1, marca.ARRANQUE_MS, objetivo)
        self.animacion_arranque.set_easing(Adw.Easing.LINEAR)
        self.animacion_arranque.connect("done", terminar)
        self.animacion_arranque.play()

    def aparecer(self):
        """Lo único que se anima al cambiar de proyecto: el tablero entra, nada más."""
        if not animaciones_activas():
            self.tablero.set_opacity(1)
            return
        objetivo = Adw.PropertyAnimationTarget.new(self.tablero, "opacity")
        self.animacion = Adw.TimedAnimation.new(self.tablero, 0.4, 1, ENTRADA_MS, objetivo)
        self.animacion.set_easing(Adw.Easing.EASE_OUT_CUBIC)
        self.animacion.play()

    def aviso(self, texto, segundos=4):
        """Un aviso que no se sale de la ventana: el texto largo se parte en líneas."""
        etiqueta = Gtk.Label(label=texto, wrap=True, max_width_chars=48, xalign=0,
                             natural_wrap_mode=Gtk.NaturalWrapMode.WORD)
        self.toasts.add_toast(Adw.Toast(custom_title=etiqueta, timeout=segundos))
