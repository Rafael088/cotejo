"""La barra del maestro: elegir cliente y abrirlo con la indicación."""

from gi.repository import Adw, Gtk

from . import comun
from .comun import ESPACIADO_MD, ESPACIADO_SM, TODOS
from .escala import px
from .piezas import con_mano, etiquetar, icono


class Maestro:
    """La barra del maestro: elegir cliente y abrirlo con la indicación."""

    def menu_maestro(self, boton):
        """El desplegable del botón del maestro: con qué cliente abrirlo.

        Elegir uno lo abre ya, con lo que haya escrito, y lo deja como el de siempre: el botón
        principal recuerda el último que se usó en vez de volver cada vez al primero instalado.
        """
        from enrutador import clientes
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                       margin_top=px(ESPACIADO_SM), margin_bottom=px(ESPACIADO_SM),
                       margin_start=px(ESPACIADO_SM), margin_end=px(ESPACIADO_SM))
        popover = boton.get_popover()
        caja.append(Gtk.Label(label="ABRIR EL MAESTRO CON", xalign=0,
                              css_classes=["menu-titulo"]))
        instalados = clientes.instalados()
        actual = self.cliente_del_maestro(instalados)
        for nombre in instalados:
            fila = Gtk.Box(spacing=px(ESPACIADO_MD))
            fila.append(icono("agente", 15))
            fila.append(Gtk.Label(label=clientes.CLIENTES[nombre].titulo or nombre, xalign=0,
                                  hexpand=True))
            if nombre == actual:
                fila.append(Gtk.Label(label="Enter", css_classes=["menu-atajo"]))
            opcion = Gtk.Button(css_classes=["flat", "menu-item"]
                                + (["sugerida"] if nombre == actual else []), child=fila)
            opcion.connect("clicked", lambda _b, n=nombre: (popover.popdown(),
                                                            self.abrir_maestro(n)))
            caja.append(opcion)
        if not instalados:
            caja.append(Gtk.Label(label="No encontré ningún cliente de IA instalado\n"
                                        f"({', '.join(clientes.CLIENTES)}).",
                                  xalign=0, css_classes=["menu-titulo"]))
        popover.set_child(caja)

    def cliente_del_maestro(self, instalados):
        """El último cliente con el que se abrió el maestro, si sigue instalado; si no, el primero."""
        recordado = comun.cargar_board().get("cliente_maestro")
        if recordado in instalados:
            return recordado
        return instalados[0] if instalados else None

    def barra_maestro(self):
        """El maestro en el pie: una indicación opcional y un solo botón para abrirlo.

        Lo que se escribe no es una tarea: es lo que el maestro lee al abrirse («solo las de la
        v1.2.4», «primero las de la web»), y se le pasa en su instrucción. Enter y el botón
        hacen lo mismo; el desplegable del botón elige el cliente. Antes había dos botones que
        abrían el maestro y Enter anotaba la frase como carta en Pendiente, que el maestro
        nunca leía.
        """
        barra = Gtk.Box(spacing=px(ESPACIADO_SM), halign=Gtk.Align.CENTER,
                        valign=Gtk.Align.CENTER, css_classes=["maestro-barra"])
        barra.append(icono("agente", 14, "maestro-chispa"))
        self.entrada_maestro = Gtk.Entry(placeholder_text="Indicación para el maestro (opcional)",
                                         width_chars=22, hexpand=True)
        etiquetar(self.entrada_maestro, "Indicación para el maestro: la lee al abrirse")
        self.entrada_maestro.connect("activate", self.al_ejecutar_maestro)
        self.entrada_maestro.connect("changed", lambda *_: self.poner_maestro())
        barra.append(self.entrada_maestro)
        # Un botón dividido: la parte grande abre el maestro con el cliente de siempre; la
        # flecha, el menú para elegir otro. El menú se arma al abrirlo, porque los clientes
        # instalados pueden cambiar con el board abierto.
        self.boton_maestro = Adw.SplitButton(label="Abrir maestro",
                                             css_classes=["maestro-ejecutar"],
                                             dropdown_tooltip="Elegir con qué cliente abrirlo")
        self.boton_maestro.connect("clicked", self.al_ejecutar_maestro)
        # Adw.SplitButton no tiene create_popup_func: el menú se rehace cada vez que se abre.
        popover = Gtk.Popover()
        self.boton_maestro.set_popover(popover)
        popover.connect("show", lambda *_: self.menu_maestro(self.boton_maestro))
        barra.append(con_mano(self.boton_maestro))
        return barra

    def al_ejecutar_maestro(self, *_args):
        from enrutador import clientes
        instalados = clientes.instalados()
        if not instalados:
            self.aviso("No encontré ningún cliente de IA instalado "
                       f"({', '.join(clientes.CLIENTES)})")
            return
        self.abrir_maestro(self.cliente_del_maestro(instalados))

    def abrir_maestro(self, cliente):
        """Abre el maestro del proyecto elegido —lo mismo que `cotejo maestro --indicacion`—.

        La indicación solo se borra si el maestro se abrió: si se niega (sin tareas asignadas,
        sin terminal), lo escrito se queda para no tener que volver a teclearlo.
        """
        from enrutador import clientes, verbos
        from ..cli import ErrorCLI
        indicacion = " ".join(self.entrada_maestro.get_text().split())
        try:
            hecho = verbos.abrir_maestro(self.seleccion, cliente, indicacion=indicacion)
        except ErrorCLI as error:
            self.aviso(f"{error.mensaje}. {error.salida}")
            return
        comun.guardar_board(cliente_maestro=cliente)
        self.entrada_maestro.set_text("")
        titulo = clientes.CLIENTES[cliente].titulo or cliente
        cuantas = len(hecho["asignadas"])
        self.aviso(f"{titulo} abierto como maestro de {hecho['proyecto']}: "
                   f"{cuantas} tarea{'s' if cuantas != 1 else ''} para repartir"
                   + (", con tu indicación" if indicacion else ""))

    def poner_maestro(self):
        """El maestro es de un proyecto: con «Todos los proyectos» no hay a cuál abrírselo.

        El botón dice qué va a pasar: «Abrir maestro» sin nada escrito, «Enviar al maestro»
        cuando lo escrito viaja con él.
        """
        sin_fuente = bool(self.fuente.problema)
        de_uno = self.seleccion != TODOS and not sin_fuente
        for control in (self.boton_maestro, self.entrada_maestro):
            control.set_sensitive(de_uno)
        con_texto = bool(self.entrada_maestro.get_text().strip())
        self.boton_maestro.set_label("Enviar al maestro" if con_texto else "Abrir maestro")
        self.boton_maestro.set_tooltip_text(
            ("Abrir el maestro con tu indicación" if con_texto
             else "Abrir un agente que reparta las tareas asignadas de este proyecto")
            if de_uno else "Aún no hay de dónde leer las tareas: configura una fuente primero"
            if sin_fuente else "Elige un proyecto para abrir su maestro")
