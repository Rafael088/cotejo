"""Una carta de tarea: chips, anotación y su menú de tres puntos."""

from gi.repository import Gtk, Pango

from .. import fuente as f, modelo
from .comun import (
    ESPACIADO_MD, ESPACIADO_SM, ESPACIADO_XS, ICONOS_COLUMNA, ICONOS_DIFICULTAD,
    MAX_CARACTERES_CARTA, anotacion_visible, id_corto, texto_a_markup,
)
from .escala import px
from .piezas import chip, con_mano, etiquetar, icono, revelar_al_acercarse


class Cartas:
    """Una carta de tarea: chips, anotación y su menú de tres puntos."""

    def carta(self, proyecto, tarea, con_proyecto=False):
        fila = con_mano(Gtk.ListBoxRow(css_classes=["carta"], activatable=True))
        fila.proyecto = proyecto
        fila.tarea = tarea
        # El id identifica la tarea aunque la carta se destruya al repintar, y aunque la
        # tarea se haya movido de línea entre un repintado y el siguiente.
        fila.clave = tarea.id

        # Qué enseña cada columna (7.3.3): Pendiente solo el id (el nombre corto sale al
        # acercarse); Haciéndola, id y nombre; Para comprobar, todo, con su entrega.
        columna = tarea.columna
        compacta = columna == "pendiente"
        completa = columna not in ("pendiente", "en-curso")
        version, nombre_corto, descripcion = tarea.partes
        # La compacta sin separación: el revelador cerrado no debe dejar un hueco debajo del id.
        carta = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                        spacing=0 if compacta else px(ESPACIADO_SM))
        fila.set_child(carta)
        arriba = Gtk.Box(spacing=px(ESPACIADO_SM))
        if compacta:
            fila.add_css_class("carta-compacta")
        arriba.append(Gtk.Label(label=id_corto(tarea.id), xalign=0, valign=Gtk.Align.CENTER,
                                ellipsize=Pango.EllipsizeMode.MIDDLE, max_width_chars=14,
                                tooltip_text=tarea.id, css_classes=["carta-codigo"]))
        if completa and version:
            arriba.append(Gtk.Label(label=version, valign=Gtk.Align.CENTER,
                                    css_classes=["carta-version"]))
        espera = self.motivo_en_espera(tarea)
        if espera:
            # Se pidió lanzarla y no había hueco (`lanzar.py`): sigue aquí hasta que se mueva otra vez.
            arriba.append(chip("En espera", "aviso", "chip-espera", tooltip=espera))
        arriba.append(Gtk.Box(hexpand=True))
        etiqueta = Gtk.Label(label=texto_a_markup(nombre_corto), use_markup=True, xalign=0,
                             yalign=0, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                             hexpand=True, max_width_chars=MAX_CARACTERES_CARTA,
                             css_classes=["carta-texto", "carta-nombre"])
        fila.boton_menu = self.menu(proyecto, tarea)
        # Al cerrar el menú el foco vuelve a la carta: si no, se queda en el aire y hay que
        # empezar a tabular de nuevo desde el principio.
        fila.boton_menu.get_popover().connect(
            "closed", lambda _p, f=fila: f.get_root() and f.grab_focus())
        arriba.append(fila.boton_menu)
        carta.append(arriba)

        if compacta:
            # Lo único que Pendiente esconde: el nombre corto, hasta el puntero o el foco.
            etiqueta.set_margin_bottom(px(ESPACIADO_SM))
            etiqueta.set_margin_end(px(ESPACIADO_SM))
            fila.revelador = revelar_al_acercarse(fila, etiqueta)
            carta.append(fila.revelador)
        else:
            carta.append(etiqueta)
        if columna == "en-curso" and tarea.agente:
            # Haciéndola enseña el modelo asignado y nada más (sin dificultad ni anotación).
            quien = Gtk.Box(spacing=px(ESPACIADO_XS))
            quien.append(self.chip_agente(tarea))
            carta.append(quien)
        if completa and descripcion != nombre_corto:
            carta.append(Gtk.Label(label=texto_a_markup(descripcion), use_markup=True, xalign=0,
                                   wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                                   max_width_chars=MAX_CARACTERES_CARTA,
                                   css_classes=["carta-texto", "carta-descripcion"]))
        if completa:
            self.detalles_de_carta(carta, proyecto, tarea, con_proyecto)

        self.arrastrable(fila)
        nombre = f"{tarea.texto}. Columna: {dict(modelo.COLUMNAS)[tarea.columna]}"
        if tarea.agente:
            nombre += f". Agente: {tarea.agente}"
        if tarea.dificultad:
            nombre += f". Dificultad: {tarea.dificultad}"
        if espera:
            nombre += ". En espera de hueco para su agente"
        etiquetar(fila, nombre)
        accion = "abre la revisión" if columna == "por-validar" else "abre la ficha"
        fila.set_tooltip_text("Arrástrala a otra columna (o Ctrl+← / Ctrl+→). "
                              f"Clic o Enter: {accion}; Menú abre las acciones")
        return fila

    def chip_agente(self, tarea):
        """El chip de quién tiene la tarea: persona o modelo, según `alias_persona`."""
        quien = "persona" if tarea.agente in self.alias_persona else "agente"
        return chip(tarea.agente, quien, "chip-agente", tooltip=f"Asignada a {tarea.agente}")

    def detalles_de_carta(self, detalle, proyecto, tarea, con_proyecto=False):
        """Chips, anotación y, en *Para comprobar*, la entrega con su diff y sus botones."""
        chips = Gtk.Box(spacing=px(ESPACIADO_XS))
        if con_proyecto:
            chips.append(chip(proyecto.nombre, "tablero", tooltip=proyecto.nombre, maximo=18))
        if tarea.agente:
            chips.append(self.chip_agente(tarea))
        if tarea.dificultad:
            chips.append(chip(tarea.dificultad, ICONOS_DIFICULTAD.get(tarea.dificultad, ""),
                              tooltip="Dificultad, para saber a qué modelo encargarla"))
        if tarea.sub:
            chips.append(chip(tarea.sub, "", tooltip=tarea.donde, maximo=16))
        if chips.get_first_child() is not None:
            detalle.append(chips)
        anotacion = self.anotacion(tarea)
        if anotacion is not None:
            detalle.append(anotacion)
        if tarea.columna == "por-validar":
            detalle.append(self.revision_en_carta(proyecto, tarea))

    def anotacion(self, tarea):
        """La evidencia con la que entregaron la tarea, o el motivo por el que se devolvió.

        Es la mitad que le faltaba a la columna: sin ella, las cartas de *Para
        comprobar* no dicen qué se hizo, así que revisar una entrega cuesta lo mismo que
        haberla hecho y la columna no sirve para nada. Se recorta a tres líneas porque la
        carta mide 250 px; el resto está a un menú de distancia y en el tooltip.
        """
        visible = anotacion_visible(tarea, self.app.bitacora.get(tarea.id))
        if visible is None:
            return None
        clase, titulo, texto = visible
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                       css_classes=["anotacion", clase])
        cabeza = Gtk.Box(spacing=px(ESPACIADO_XS))
        cabeza.append(icono("devuelta" if clase == "detenida" else "evidencia", 12))
        cabeza.append(Gtk.Label(label=titulo, xalign=0, hexpand=True,
                                ellipsize=Pango.EllipsizeMode.END,
                                css_classes=["anotacion-titulo"]))
        caja.append(cabeza)
        # Los saltos de línea se aplastan a espacios: Pango recorta cada párrafo por su
        # cuenta, así que una evidencia de tres párrafos daba nueve líneas con tres «…»
        # dentro de una carta que solo puede dar tres.
        caja.append(Gtk.Label(label=" ".join(texto.split()), xalign=0, wrap=True, lines=3,
                              ellipsize=Pango.EllipsizeMode.END, css_classes=["anotacion-texto"]))
        caja.set_tooltip_text(texto)
        return caja

    # --- revisión de una entrega (B4) ------------------------------------------------------

    def entrega_de(self, tarea):
        """La anotación de `entregar` de la tarea, si es lo último que se dijo de ella."""
        anotacion = self.app.bitacora.get(tarea.id)
        if anotacion and anotacion.get("operacion") == "entregar":
            return anotacion
        return None

    def menu(self, proyecto, tarea):
        # Sin cotejo propio: el Tab salta de columna en columna y a este menú se llega con la
        # tecla Menú desde la carta, que es donde ya está el foco.
        boton = Gtk.MenuButton(icon_name="cotejo-mas-symbolic", valign=Gtk.Align.START,
                               css_classes=["flat"], focusable=False,
                               tooltip_text=("Mover (tecla Menú)" if tarea.hecha
                                             else "Mover o asignar (tecla Menú)"))
        etiquetar(boton, f"Acciones de la tarea: {tarea.texto[:60]}")
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_top=px(ESPACIADO_SM), margin_bottom=px(ESPACIADO_SM),
                       margin_start=px(ESPACIADO_SM), margin_end=px(ESPACIADO_SM))
        popover = Gtk.Popover(child=caja)
        boton.set_popover(popover)

        caja.append(Gtk.Label(label="MOVER A", xalign=0, css_classes=["menu-titulo"]))
        aqui = self.orden.index(tarea.columna)
        for clave, nombre in modelo.COLUMNAS:
            if clave == tarea.columna:
                continue
            # Las dos columnas de al lado se nombran por su dirección y llevan su atajo a la
            # vista: mover es lo que más se hace aquí y tiene tecla desde hace tiempo, pero
            # había que saberlo de antes. La de la derecha va resaltada porque es a donde va
            # la tarea si nada se tuerce.
            paso = self.orden.index(clave) - aqui
            simbolo_paso = {-1: "flecha-izquierda", 1: "flecha-derecha"}.get(paso)
            atajo = {-1: "Ctrl ←", 1: "Ctrl →"}.get(paso, "")
            caja.append(self.opcion(nombre, self.al_mover, proyecto, tarea, clave, popover,
                                    simbolo_paso or ICONOS_COLUMNA[clave], atajo, paso == 1))

        # Lo finalizado ya no cambia de manos: sin «Asignar a», que en Finalizada solo servía
        # para equivocarse.
        if not tarea.hecha:
            caja.append(Gtk.Separator(margin_top=px(ESPACIADO_SM), margin_bottom=px(ESPACIADO_XS)))
            caja.append(Gtk.Label(label="ASIGNAR A", xalign=0, css_classes=["menu-titulo"]))
            caja.append(self.lista_de_agentes(proyecto, tarea, popover))

        if self.motivo_en_espera(tarea):
            caja.append(Gtk.Separator(margin_top=px(ESPACIADO_SM), margin_bottom=px(ESPACIADO_XS)))
            caja.append(self.opcion("Lanzar de todos modos", self.al_lanzar_igual, proyecto,
                                    tarea, None, popover, "aviso"))
            caja.append(self.opcion("Quitar de la espera", self.al_quitar_de_espera, proyecto,
                                    tarea, None, popover, "aviso"))

        visible = anotacion_visible(tarea, self.app.bitacora.get(tarea.id))
        if visible is not None:
            clase, titulo, texto = visible
            # La carta recorta a tres líneas; una evidencia de verdad trae comandos y salidas
            # de pruebas, y lo que hay que copiar de ahí no cabe en un tooltip.
            detenida = clase == "detenida"
            caja.append(Gtk.Separator(margin_top=px(ESPACIADO_SM), margin_bottom=px(ESPACIADO_XS)))
            caja.append(self.opcion("Ver el motivo" if detenida else "Ver la evidencia",
                                    self.al_ver, proyecto, tarea, (titulo, texto), popover,
                                    "devuelta" if detenida else "evidencia"))
        return boton

    def opcion(self, texto, funcion, proyecto, tarea, dato, popover,
               nombre_icono="", atajo="", sugerida=False):
        fila = Gtk.Box(spacing=px(ESPACIADO_MD))
        if nombre_icono:
            fila.append(icono(nombre_icono, 15))
        fila.append(Gtk.Label(label=texto, xalign=0, hexpand=True,
                              ellipsize=Pango.EllipsizeMode.END))
        if atajo:
            fila.append(Gtk.Label(label=atajo, css_classes=["menu-atajo"]))
        clases = ["flat", "menu-item"] + (["sugerida"] if sugerida else [])
        boton = Gtk.Button(css_classes=clases, child=fila)
        boton.connect("clicked", lambda *_: funcion(proyecto, tarea, dato, popover))
        return boton
