"""Moverse por el board con el teclado: foco entre columnas y cartas."""

from gi.repository import Gdk, Gtk

from .. import estado
from .piezas import chip


class Teclado:
    """Moverse por el board con el teclado: foco entre columnas y cartas."""

    # --- teclado -------------------------------------------------------

    @staticmethod
    def _es_carta(fila):
        """Una tarea o una decisión propuesta (C5, v1.2): lo que el teclado recorre como
        carta. Un encabezado de grupo, o una columna vacía, no lo es."""
        return (getattr(fila, "tarea", None) is not None
                or getattr(fila, "decision", None) is not None)

    def cartas(self, lista):
        """Solo las filas que son carta: los encabezados de grupo no se recorren."""
        filas, fila = [], lista.get_first_child()
        while fila is not None:
            if self._es_carta(fila):
                filas.append(fila)
            fila = fila.get_next_sibling()
        return filas

    def fila_enfocada(self):
        widget = self.get_focus()
        while widget is not None:
            if isinstance(widget, Gtk.ListBoxRow):
                return widget if self._es_carta(widget) else None
            widget = widget.get_parent()
        return None

    def clave_enfocada(self):
        fila = self.fila_enfocada()
        return fila.clave if fila is not None else None

    def enfocar_columna(self, indice, paso):
        """Foco a la primera carta de esa columna, saltando las que estén vacías."""
        while 0 <= indice < len(self.orden):
            cartas = self.cartas(self.columnas[self.orden[indice]][0])
            if cartas:
                cartas[0].grab_focus()
                return True
            indice += paso
        return False

    def enfocar_lateral(self):
        """Foco al chip del proyecto elegido (o al primero)."""
        chip = self.botones_chip.get(self.seleccion) or self.chips.get_first_child()
        (chip or self.chips).grab_focus()
        return True

    def al_tecla_columna(self, control, tecla, _codigo, estado, indice):
        atras = tecla == Gdk.KEY_ISO_Left_Tab or bool(estado & Gdk.ModifierType.SHIFT_MASK)
        if tecla in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
            # Tab recorre columnas, no cartas: con 60 tareas, tabular una a una no lleva a nada.
            paso = -1 if atras else 1
            if self.enfocar_columna(indice + paso, paso):
                return True
            if atras:
                return self.enfocar_lateral()
            self.busqueda.grab_focus()
            return True

        fila = self.fila_enfocada()
        if tecla in (Gdk.KEY_Left, Gdk.KEY_Right):
            paso = -1 if tecla == Gdk.KEY_Left else 1
            if estado & Gdk.ModifierType.CONTROL_MASK:
                return self.mover_con_teclado(fila, paso)
            if indice + paso < 0:
                return self.enfocar_lateral()
            self.enfocar_columna(indice + paso, paso)
            return True
        if tecla in (Gdk.KEY_Up, Gdk.KEY_Down):
            return self.mover_foco(control.get_widget(), fila, -1 if tecla == Gdk.KEY_Up else 1)
        if fila is None:
            return False
        if tecla in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.al_activar(None, fila)
            return True
        if (tecla == Gdk.KEY_Menu or (tecla == Gdk.KEY_F10 and atras)) and getattr(
                fila, "boton_menu", None) is not None:
            fila.boton_menu.popup()
            return True
        return False

    def mover_foco(self, lista, fila, paso):
        """Arriba y abajo entre cartas, saltando encabezados y sin salirse por los extremos."""
        cartas = self.cartas(lista)
        if not cartas:
            return True
        indice = cartas.index(fila) + paso if fila in cartas else (0 if paso > 0 else len(cartas) - 1)
        if 0 <= indice < len(cartas):
            cartas[indice].grab_focus()
        return True

    def al_tecla_banda(self, _control, tecla, _codigo, estado):
        """Tab sale de la banda hacia las columnas (Mayús+Tab, hacia atrás); → baja a la
        primera columna. Las flechas ← y ↑ / ↓ entre chips las resuelve el foco de GTK."""
        atras = tecla == Gdk.KEY_ISO_Left_Tab or bool(estado & Gdk.ModifierType.SHIFT_MASK)
        if tecla in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
            if atras:
                self.boton_recargar.grab_focus()
            elif not self.enfocar_columna(0, 1):
                self.busqueda.grab_focus()
            return True
        if tecla == Gdk.KEY_Down:
            self.enfocar_columna(0, 1)
            return True
        return False

    def mover_con_teclado(self, fila, paso):
        # Una decisión no tiene columna: Ctrl+← / Ctrl+→ sobre su carta no hace nada, en vez
        # de intentar moverla como si fuera una tarea.
        if fila is None or getattr(fila, "tarea", None) is None:
            return True
        indice = self.orden.index(fila.tarea.columna) + paso
        if 0 <= indice < len(self.orden):
            self.mover(fila.proyecto, fila.tarea, self.orden[indice])
        return True
