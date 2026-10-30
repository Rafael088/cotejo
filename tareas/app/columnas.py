"""Las cuatro columnas, Finalizada plegada y su filtro de fechas."""

import types

from gi.repository import Adw, GLib, Gdk, Gtk

from .. import equipo, fuente as f, marca, modelo
from . import comun
from .comun import (
    ANCHO_COLUMNAS, ANCHO_RIEL, ESPACIADO_LG, ESPACIADO_MD, ESPACIADO_SM, ESPACIADO_XL,
    ESPACIADO_XS, ICONOS_COLUMNA, TODOS, VACIOS, VACIO_BUSQUEDA, id_corto, ordenar_por_version,
)
from .escala import px
from .piezas import TareaArrastrada, con_mano, etiquetar, icono, vaciar, vacio


class Columnas:
    """Las cuatro columnas, Finalizada plegada y su filtro de fechas."""

    # --- vista ---------------------------------------------------------

    def columna(self, indice, clave, nombre):
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_SM),
                       css_classes=["columna-caja"], hexpand=False)
        caja.set_size_request(px(ANCHO_COLUMNAS[clave]), -1)
        encabezado = Gtk.Box(spacing=px(ESPACIADO_SM), margin_start=px(ESPACIADO_XS),
                             margin_end=px(ESPACIADO_XS), margin_top=px(ESPACIADO_XS))
        marca = icono(ICONOS_COLUMNA[clave], 15, "columna-icono")
        etiqueta = Gtk.Label(label=nombre, xalign=0, hexpand=True, wrap=True,
                             css_classes=["columna-titulo"])
        cuenta = Gtk.Label(label="0", css_classes=["cuenta-columna"], valign=Gtk.Align.CENTER)
        # El único acento va donde hay algo esperándote, igual que en el botón de la barra.
        if clave == "por-validar":
            # El número se enciende al pintar, solo si hay algo: un 0 en verde no espera nada.
            for parte in (marca, etiqueta):
                parte.add_css_class("en-cotejo")
        elif clave == modelo.HECHA:
            # Lo terminado no reclama nada: se consulta, no se atiende.
            marca.add_css_class("terminada")
            etiqueta.add_css_class("terminada")
        encabezado.append(marca)
        encabezado.append(etiqueta)
        if clave == modelo.HECHA:
            # A la izquierda del contador: se lee "filtro, cuántas" en ese orden, como se
            # lee "Hoy: 12" (cotejo-r3cs5t). El menú se arma de nuevo en cada apertura para
            # que la marca de la opción elegida nunca quede vieja.
            boton_filtro = Gtk.MenuButton(icon_name="cotejo-filtro-symbolic",
                                          css_classes=["flat"], valign=Gtk.Align.CENTER,
                                          tooltip_text="Filtrar por fecha de cierre")
            etiquetar(boton_filtro, "Filtrar Finalizada por fecha de cierre")
            boton_filtro.set_create_popup_func(self.menu_filtro_finalizada)
            encabezado.append(boton_filtro)
        encabezado.append(cuenta)
        # Un nombre de dos líneas no debe bajar las cartas de su columna con respecto a las
        # otras tres: las cabeceras se miden juntas y todas valen lo que la más alta.
        self.altura_encabezados.add_widget(encabezado)
        caja.append(encabezado)

        # Un ListBox y no un Box: las flechas recorren sus filas solas y cada carta puede
        # recibir el foco, que es lo que hace el board manejable sin tocar el mouse.
        lista = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["columna"])
        lista.connect("row-activated", self.al_activar)
        self.vigilar_teclas(lista, self.al_tecla_columna, indice)
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER, child=lista)
        caja.append(scroll)

        # Soltar sobre cualquier parte de la columna, no solo sobre las cartas que ya tiene:
        # una columna vacía es justo a donde más se arrastra.
        destino = Gtk.DropTarget.new(TareaArrastrada, Gdk.DragAction.MOVE)
        destino.connect("enter", self.al_entrar_arrastre, clave, caja)
        destino.connect("leave", self.al_salir_arrastre, caja)
        destino.connect("drop", self.al_soltar, clave, caja)
        caja.add_controller(destino)

        self.columnas[clave] = (lista, cuenta, scroll)
        if clave == modelo.HECHA:
            # El riel (v1.2.4): Finalizada va siempre plegada, solo con su ícono. La lista y el
            # contador siguen vivos aunque no se vean: `pintar_columnas` los llena y una carta
            # que llega con Ctrl+→ se cuenta. El clic abre la ventana con las finalizadas.
            marca_riel = icono(ICONOS_COLUMNA[clave], 22, "terminada")
            marca_riel.set_halign(Gtk.Align.CENTER)
            marca_riel.set_valign(Gtk.Align.CENTER)
            # El conteo va debajo del check: el riel ya no es solo un ícono, también dice
            # cuántas finalizadas hay con el filtro de fechas actual.
            cuenta_riel = Gtk.Label(label=cuenta.get_label(), css_classes=["riel-cuenta"],
                                    halign=Gtk.Align.CENTER)
            contenido_riel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                                     valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
            contenido_riel.append(marca_riel)
            contenido_riel.append(cuenta_riel)
            boton_riel = Gtk.Button(child=contenido_riel, css_classes=["flat", "riel-finalizada"],
                                    vexpand=True, valign=Gtk.Align.FILL, halign=Gtk.Align.FILL)
            boton_riel.connect("clicked", lambda _b: self.presentar_finalizada())
            con_mano(boton_riel)
            cuenta.connect("notify::label", lambda *_a: self.poner_nombre_riel())
            caja.append(boton_riel)
            self.finalizada = types.SimpleNamespace(
                caja=caja, encabezado=encabezado, scroll=scroll, riel=boton_riel,
                cuenta_riel=cuenta_riel)
            self.poner_nombre_riel()
            encabezado.set_visible(False)
            scroll.set_visible(False)
            caja.set_size_request(px(ANCHO_RIEL), -1)
        return caja

    def menu_filtro_finalizada(self, boton):
        """El menú del botón de filtro de Finalizada: Hoy / 7 días / 30 días / Todas.

        Un solo clic, sin confirmar: no escribe nada (es un filtro de vista, no un cambio de
        la tarea), así que no hay por qué pedir un segundo paso.
        """
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                       margin_top=px(ESPACIADO_SM), margin_bottom=px(ESPACIADO_SM),
                       margin_start=px(ESPACIADO_SM), margin_end=px(ESPACIADO_SM))
        popover = Gtk.Popover(child=caja)
        caja.append(Gtk.Label(label="FINALIZADA DESDE", xalign=0, css_classes=["menu-titulo"]))
        for clave_filtro, nombre, _dias in modelo.FILTROS_FINALIZADA:
            fila = Gtk.Box(spacing=px(ESPACIADO_MD))
            fila.append(Gtk.Label(label=nombre, xalign=0, hexpand=True))
            if clave_filtro == self.filtro_finalizada:
                fila.append(icono("estado-hecha", 14, "en-cotejo"))
            opcion = Gtk.Button(css_classes=["flat", "menu-item"], child=fila)
            opcion.connect("clicked", lambda _b, c=clave_filtro: (popover.popdown(),
                                                                  self.elegir_filtro_finalizada(c)))
            caja.append(opcion)
        boton.set_popover(popover)

    def elegir_filtro_finalizada(self, clave):
        if clave == self.filtro_finalizada:
            return
        self.filtro_finalizada = clave
        comun.guardar_board(filtro_finalizada=clave)
        self.pintar_columnas()

    def poner_nombre_riel(self):
        """Nombre accesible y tooltip del riel: «Finalizada · N», con N lo del filtro actual."""
        _lista, cuenta, _scroll = self.columnas[modelo.HECHA]
        texto = f"{dict(modelo.COLUMNAS)[modelo.HECHA]} · {cuenta.get_label()}"
        self.finalizada.cuenta_riel.set_label(cuenta.get_label())
        self.finalizada.riel.set_tooltip_text(texto)
        etiquetar(self.finalizada.riel, texto)

    def finalizadas_del_filtro(self):
        """[(proyecto, tarea)] de Finalizada con el filtro de fechas y la búsqueda actuales."""
        todos = self.seleccion == TODOS
        hoy = modelo.hoy_local()
        salida = []
        for proyecto in self.proyectos_con_tareas():
            if not todos and proyecto.nombre != self.seleccion:
                continue
            for t in list(proyecto.tareas) + list(proyecto.hechas):
                if t.columna != modelo.HECHA:
                    continue
                if not modelo.en_filtro_finalizada(t.cerrada, self.filtro_finalizada, hoy):
                    continue
                if self.filtro and self.filtro not in t.texto.lower():
                    continue
                salida.append((proyecto, t))
        return salida

    def presentar_finalizada(self):
        if self.ventana_finalizada is not None:
            return
        dialogo = self.dialogo_finalizada()
        self.ventana_finalizada = dialogo
        dialogo.connect("closed", lambda _d: setattr(self, "ventana_finalizada", None))
        dialogo.present(self)

    def dialogo_finalizada(self):
        """La ventana de las finalizadas: el filtro de fechas y una fila por tarea.

        Se arma aparte de presentarla para poder probarla sin pantalla. `repintar` rehace la
        lista y las marcas del filtro; el board la llama cada vez que repinta sus columnas.
        """
        dialogo = Adw.Dialog(title=dict(modelo.COLUMNAS)[modelo.HECHA],
                             content_width=px(520), content_height=px(560))
        vista = Adw.ToolbarView()
        vista.add_top_bar(Adw.HeaderBar())
        cuerpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_MD),
                         margin_top=px(ESPACIADO_SM), margin_bottom=px(ESPACIADO_MD),
                         margin_start=px(ESPACIADO_XL), margin_end=px(ESPACIADO_XL))
        filtro = Gtk.Box(css_classes=["linked"], halign=Gtk.Align.START)
        botones, primero = {}, None
        for clave_filtro, nombre, _dias in modelo.FILTROS_FINALIZADA:
            b = Gtk.ToggleButton(label=nombre, group=primero)
            primero = primero or b
            b.connect("toggled", lambda boton, c=clave_filtro: boton.get_active()
                      and self.elegir_filtro_finalizada(c))
            botones[clave_filtro] = b
            filtro.append(b)
        cuerpo.append(filtro)
        lista = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["columna"])
        cuerpo.append(Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER,
                                         child=lista))
        vista.set_content(cuerpo)
        dialogo.set_child(vista)

        def repintar():
            botones[self.filtro_finalizada].set_active(True)
            vaciar(lista)
            filas = self.finalizadas_del_filtro()
            todos = self.seleccion == TODOS
            for proyecto, tarea in filas:
                fila = Gtk.Box(spacing=px(ESPACIADO_MD), margin_top=px(ESPACIADO_XS),
                               margin_bottom=px(ESPACIADO_XS))
                fila.append(Gtk.Label(label=id_corto(tarea.id), xalign=0,
                                      css_classes=["carta-codigo"]))
                texto = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
                texto.append(Gtk.Label(label=tarea.nombre_corto, xalign=0, wrap=True))
                detalle = " · ".join(x for x in (tarea.cerrada, proyecto.nombre if todos else None) if x)
                if detalle:
                    texto.append(Gtk.Label(label=detalle, xalign=0, css_classes=["dim-label"]))
                fila.append(texto)
                fila.append(self.menu(proyecto, tarea))
                lista.append(self.fila_quieta(fila))
            if not filas:
                lista.append(self.fila_quieta(self.vacio(modelo.HECHA)))

        dialogo.repintar = repintar
        repintar()
        return dialogo

    def pintar_columnas(self, entrando=False):
        if self.fuente.problema:
            self.pintar_problema()
            self.actualizar_dot()
            return

        todos = self.seleccion == TODOS
        proyectos = [p for p in self.proyectos_con_tareas() if todos or p.nombre == self.seleccion]
        self.leer_en_espera()
        # Mover una tarea la borra y la vuelve a crear en otra columna: sin esto el foco se
        # perdería justo al moverla con el teclado, que es cuando más falta hace. Quien acaba
        # de escribir manda, porque al escribir la tarea puede haber ganado su marca y con
        # ella un id distinto del que tenía cuando se leyó.
        enfocada = self.foco_tras_pintar or self.clave_enfocada()
        self.foco_tras_pintar, devolver = None, None

        for clave, _ in modelo.COLUMNAS:
            lista, cuenta, scroll = self.columnas[clave]
            # Repintar en cada cambio del vault no debe mover la columna que estás leyendo.
            posicion = 0 if entrando else scroll.get_vadjustment().get_value()
            vaciar(lista)

            total = 0
            # Una sola "hoy" para toda la columna Finalizada, para que todas sus tareas de
            # este repintado se midan contra el mismo día aunque el reloj cambie de fecha a
            # medio pintar.
            hoy = modelo.hoy_local() if clave == modelo.HECHA else None
            for proyecto in proyectos:
                tareas = [t for t in list(proyecto.tareas) + list(proyecto.hechas)
                          if t.columna == clave]
                if clave == modelo.HECHA:
                    # El filtro de fechas de Finalizada (v1.2.2): una hecha sin fecha de
                    # cierre solo cuenta en "Todas" (ver `en_filtro_finalizada`).
                    tareas = [t for t in tareas
                             if modelo.en_filtro_finalizada(t.cerrada, self.filtro_finalizada, hoy)]
                if self.filtro:
                    tareas = [t for t in tareas if self.filtro in t.texto.lower()]
                # Las decisiones propuestas (C5, v1.2) son de *Para comprobar* y nada más:
                # no tienen columna propia, así que no se miran para las demás.
                decisiones = self.decisiones_de(proyecto) if clave == "por-validar" else []
                if self.filtro:
                    decisiones = [(alm, e) for alm, e in decisiones
                                  if self.filtro in e.titulo.lower()]
                if not tareas and not decisiones:
                    continue
                total += len(tareas) + len(decisiones)
                # Con "Todos" cada grupo lleva su encabezado: categorizadas, no amontonadas.
                if todos:
                    lista.append(self.fila_quieta(
                        Gtk.Label(label=proyecto.nombre.upper(), xalign=0, wrap=True,
                                  css_classes=["grupo-titulo"], margin_top=px(ESPACIADO_SM))))
                if clave == modelo.PENDIENTE:
                    tareas = ordenar_por_version(tareas)
                version_anterior = None
                for tarea in tareas:
                    if clave == modelo.PENDIENTE:
                        version = tarea.version_del_texto or "sin versión"
                        if version != version_anterior:
                            lista.append(self.fila_quieta(Gtk.Label(
                                label=version, xalign=0, css_classes=["grupo-version"],
                                margin_top=px(ESPACIADO_XS), margin_start=px(ESPACIADO_XS))))
                            version_anterior = version
                    fila = self.carta(proyecto, tarea)
                    lista.append(fila)
                    if fila.clave == enfocada:
                        devolver = fila
                for alm, entrada in decisiones:
                    fila = self.carta_decision(proyecto, alm, entrada)
                    lista.append(fila)
                    if fila.clave == enfocada:
                        devolver = fila
            cuenta.set_label(str(total))
            if clave == "por-validar":
                (cuenta.add_css_class if total else cuenta.remove_css_class)("en-cotejo")
            if total == 0:
                lista.append(self.fila_quieta(self.vacio(clave)))
            GLib.idle_add(lambda a=scroll.get_vadjustment(), p=posicion: a.set_value(p) and False)

        if devolver is not None:
            # Después de las posiciones de scroll: al enfocar, la columna se desplaza sola a la carta.
            GLib.idle_add(lambda f=devolver: f.grab_focus() and False)
        self.poner_subtitulo(proyectos, todos)
        if self.ventana_finalizada is not None:
            self.ventana_finalizada.repintar()
        self.actualizar_dot()
        if entrando:
            self.aparecer()

    def pintar_problema(self):
        """Sin de dónde leer: el vacío en ámbar, en la primera columna.

        Antes el problema entero iba al subtítulo, en mayúsculas: con una ruta larga la
        cabecera pedía más ancho que la pantalla (Adwaita avisaba de 1630 px), y las
        columnas se quedaban con lo último que se pintó, como si siguiera valiendo.
        """
        self.subtitulo.set_label("")
        self.subtitulo.set_tooltip_text(None)
        self.subtitulo.remove_css_class("en-cotejo")
        for i, (clave, _) in enumerate(modelo.COLUMNAS):
            lista, cuenta, _scroll = self.columnas[clave]
            vaciar(lista)
            cuenta.set_label("0")
            if i == 0:
                if equipo.es_primer_arranque(self.fuente):
                    caja = vacio("vacio", "Todavía no hay proyectos",
                                 "Empieza uno desde Inicio, con «Nuevo proyecto».")
                else:
                    caja = vacio("aviso", "No hay de dónde leer las tareas",
                                 self.fuente.problema, roto=True)
                caja.set_margin_top(px(ESPACIADO_SM))
                lista.append(self.fila_quieta(caja))

    def fila_quieta(self, hijo):
        """Encabezado o columna vacía: se ve, pero el teclado pasa de largo."""
        return Gtk.ListBoxRow(child=hijo, activatable=False, selectable=False, focusable=False)

    def vacio(self, clave):
        # Buscando, la columna no está vacía: es la búsqueda la que no encontró. Por eso lupa
        # y no bandeja.
        if self.filtro:
            caja = vacio("buscar", *VACIO_BUSQUEDA)
        else:
            caja = vacio("vacio", *VACIOS[clave])
        caja.set_margin_top(px(ESPACIADO_LG))
        caja.set_margin_start(px(ESPACIADO_SM))
        caja.set_margin_end(px(ESPACIADO_SM))
        return caja
