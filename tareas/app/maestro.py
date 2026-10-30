"""El maestro en el board: la barra del pie y la conversación que sube encima (cotejo-9ybn1a).

La persona le escribe en llano y ve la conversación en la app: añade tareas, contesta sobre el
proyecto y propone repartir lo asignado. Nunca se abre una terminal: cada mensaje es un turno
sin interfaz (`enrutador/conversacion.py`, por `verbos.hablar_maestro`) que el board sigue en
vivo. Repartir lo hace el board al pulsar el botón, por el mismo camino que mover la carta a
Haciendo (`Movimientos.mover`): su agente, su worktree, su ficha en vivo y la capacidad.
"""

from gi.repository import Adw, GLib, Gtk

from .. import modelo
from . import comun
from .comun import ESPACIADO_MD, ESPACIADO_SM, TODOS
from .conversacion import PanelMaestro
from .escala import px
from .piezas import con_mano, etiquetar, icono


# El aviso de «no hay agente» trae una instrucción: da tiempo de leerla.
SEGUNDOS_SIN_AGENTE = 15
# Cada cuánto se mira lo que va haciendo el maestro mientras contesta (solo entonces).
MS_EN_VIVO = 700


class Maestro:
    """La barra del maestro y su conversación."""

    def menu_maestro(self, boton):
        """El desplegable del botón: con qué agente habla el maestro.

        Elegir uno solo lo deja como el de siempre (el botón principal recuerda el último
        elegido); enviar es del botón o de Enter, nunca de elegir: un desplegable no debería
        lanzar un agente sin que se pulse «Enviar».
        """
        from enrutador import clientes
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                       margin_top=px(ESPACIADO_SM), margin_bottom=px(ESPACIADO_SM),
                       margin_start=px(ESPACIADO_SM), margin_end=px(ESPACIADO_SM))
        popover = boton.get_popover()
        caja.append(Gtk.Label(label="EL MAESTRO HABLA CON", xalign=0,
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
            opcion.connect("clicked",
                           lambda _b, n=nombre: self.elegir_cliente_maestro(n, popover))
            caja.append(opcion)
        if not instalados:
            caja.append(Gtk.Label(label=clientes.SIN_AGENTE_TEXTO, xalign=0, wrap=True,
                                  max_width_chars=36, css_classes=["menu-titulo"]))
        popover.set_child(caja)

    def elegir_cliente_maestro(self, cliente, popover):
        """Elegir solo elige: recuerda el agente para el botón y cierra el menú, sin enviar."""
        comun.guardar_board(cliente_maestro=cliente)
        popover.popdown()
        self.poner_maestro()            # la ayuda del botón dice con cuál va a hablar

    def cliente_del_maestro(self, instalados):
        """El último agente elegido para el maestro, si sigue instalado; si no, el primero."""
        recordado = comun.cargar_board().get("cliente_maestro")
        if recordado in instalados:
            return recordado
        return instalados[0] if instalados else None

    def barra_maestro(self):
        """El maestro en el pie: lo que se le dice y un solo botón para enviarlo.

        Enter y el botón hacen lo mismo; el desplegable del botón elige el agente. Con la caja
        vacía, el botón enseña (u oculta) la conversación sin enviar nada.
        """
        barra = Gtk.Box(spacing=px(ESPACIADO_SM), halign=Gtk.Align.CENTER,
                        valign=Gtk.Align.CENTER, css_classes=["maestro-barra"])
        barra.append(icono("agente", 14, "maestro-chispa"))
        self.entrada_maestro = Gtk.Entry(
            placeholder_text="Pídele algo al maestro: «apunta…», «¿qué falta?», «reparte»",
            width_chars=22, hexpand=True)
        etiquetar(self.entrada_maestro, "Lo que le dices al maestro, en llano")
        self.entrada_maestro.connect("activate", self.al_ejecutar_maestro)
        self.entrada_maestro.connect("changed", lambda *_: self.poner_maestro())
        barra.append(self.entrada_maestro)
        # Un botón dividido: la parte grande envía con el agente de siempre; la flecha, el
        # menú para elegir otro. El menú se arma al abrirlo, porque los agentes instalados
        # pueden cambiar con el board abierto.
        self.boton_maestro = Adw.SplitButton(label="Enviar", css_classes=["maestro-ejecutar"],
                                             dropdown_tooltip="Elegir con qué agente habla")
        self.boton_maestro.connect("clicked", self.al_ejecutar_maestro)
        # Adw.SplitButton no tiene create_popup_func: el menú se rehace cada vez que se abre.
        popover = Gtk.Popover()
        self.boton_maestro.set_popover(popover)
        popover.connect("show", lambda *_: self.menu_maestro(self.boton_maestro))
        barra.append(con_mano(self.boton_maestro))
        return barra

    def crear_conversacion(self):
        """El panel de la conversación, oculto hasta que se le habla al maestro."""
        self.panel_maestro = PanelMaestro(self.repartir_del_maestro, self.parar_maestro,
                                          self.olvidar_maestro, self.cerrar_conversacion)
        self.reloj_maestro = None
        return self.panel_maestro

    # --- hablar ---------------------------------------------------------------------------------

    def al_ejecutar_maestro(self, *_args):
        from enrutador import clientes
        instalados = clientes.instalados()
        if not instalados:
            self.aviso(clientes.SIN_AGENTE_TEXTO, segundos=SEGUNDOS_SIN_AGENTE)
            return
        texto = " ".join(self.entrada_maestro.get_text().split())
        if not texto:
            if self.panel_maestro.get_reveal_child():
                self.cerrar_conversacion()
            else:
                self.ver_conversacion()
            return
        self.hablar_al_maestro(self.cliente_del_maestro(instalados), texto)

    def hablar_al_maestro(self, cliente, texto):
        """Un mensaje al maestro del proyecto elegido. Lo escrito solo se borra si salió: si
        se niega (ya está contestando, el agente no está), se queda para no volver a teclearlo.
        """
        from enrutador import verbos
        from ..cli import ErrorCLI
        # El nombre exacto llega con la respuesta del verbo; la vuelta del turno la lee aquí,
        # y siempre después: `idle_add` corre en este mismo bucle, cuando esta función acabó.
        destino = [self.seleccion]
        try:
            hecho = verbos.hablar_maestro(
                self.seleccion, texto, cliente,
                al_terminar=lambda turno: GLib.idle_add(self.maestro_contesto, destino[0],
                                                        turno))
        except ErrorCLI as error:
            self.aviso(f"{error.mensaje}. {error.salida}")
            return
        destino[0] = hecho["proyecto"]
        comun.guardar_board(cliente_maestro=cliente)
        self.entrada_maestro.set_text("")
        self.titulo_maestro = hecho.get("titulo") or cliente
        self.ver_conversacion()

    def maestro_contesto(self, proyecto, _turno=None):
        """Vuelve el turno (desde el hilo que lo esperaba): lo apuntado sale en el tablero."""
        self.app.refrescar()
        if proyecto == self.proyecto_del_maestro():
            self.pintar_conversacion()
        return False

    # --- la conversación ----------------------------------------------------------------------

    def proyecto_del_maestro(self):
        return None if self.seleccion == TODOS or self.fuente.problema else self.seleccion

    def ver_conversacion(self):
        if self.proyecto_del_maestro() is None:
            return
        self.pintar_conversacion()
        self.panel_maestro.set_reveal_child(True)

    def cerrar_conversacion(self):
        self.panel_maestro.set_reveal_child(False)
        self.parar_reloj_maestro()

    def pintar_conversacion(self):
        """Repinta el panel y, mientras el maestro contesta, vuelve a mirar cada poco."""
        from enrutador import conversacion
        proyecto = self.proyecto_del_maestro()
        if proyecto is None:
            self.cerrar_conversacion()
            return False
        datos = conversacion.leer(proyecto)
        vivo = conversacion.en_vivo(proyecto) if datos.get("en_curso") else []
        self.panel_maestro.pintar(proyecto, getattr(self, "titulo_maestro", ""), datos, vivo)
        if datos.get("en_curso"):
            if self.reloj_maestro is None:
                self.reloj_maestro = GLib.timeout_add(MS_EN_VIVO, self.tic_maestro)
        else:
            self.parar_reloj_maestro()
        return False

    def tic_maestro(self):
        self.reloj_maestro = None
        if self.panel_maestro.get_reveal_child():
            self.pintar_conversacion()
        return False

    def parar_reloj_maestro(self):
        if getattr(self, "reloj_maestro", None) is not None:
            GLib.source_remove(self.reloj_maestro)
            self.reloj_maestro = None

    def parar_maestro(self):
        from enrutador import conversacion
        proyecto = self.proyecto_del_maestro()
        if proyecto is not None:
            conversacion.parar(proyecto)
        self.pintar_conversacion()

    def olvidar_maestro(self):
        from enrutador import conversacion
        proyecto = self.proyecto_del_maestro()
        if proyecto is not None:
            conversacion.olvidar(proyecto)
        self.pintar_conversacion()

    def repartir_del_maestro(self, indice, ids):
        """«Repartir» en una respuesta: cada una por el camino de pasarla a Haciendo a mano.

        Solo las que siguen en Pendiente; las demás se dicen. Cotejo ya filtró que una persona
        les asignó un modelo (`maestro.pedidas`), y `mover` vuelve a mirarlo al lanzar.
        """
        from enrutador import conversacion
        proyecto = self.proyecto_del_maestro()
        if proyecto is None:
            return
        conversacion.marcar_repartido(proyecto, indice)
        sueltas = []
        for ident in ids:
            # Se busca otra vez cada vez: lanzar una repinta y relee las tareas.
            dueno, tarea = next(((p, t) for p in self.app.proyectos if p.nombre == proyecto
                                 for t in p.tareas if t.id == ident), (None, None))
            if tarea is None or tarea.columna != modelo.PENDIENTE:
                sueltas.append(ident)
                continue
            self.mover(dueno, tarea, "en-curso")
        if sueltas:
            self.aviso(f"No lancé {', '.join(sueltas)}: ya no están en Pendiente.")
        self.pintar_conversacion()

    def poner_maestro(self):
        """El maestro es de un proyecto: con «Todos los proyectos» no hay a cuál hablarle.

        El botón dice qué va a pasar: «Enviar» con algo escrito, «Conversación» sin nada (la
        enseña u oculta). Al cambiar de proyecto, la conversación abierta es la del nuevo.
        """
        sin_fuente = bool(self.fuente.problema)
        de_uno = self.seleccion != TODOS and not sin_fuente
        for control in (self.boton_maestro, self.entrada_maestro):
            control.set_sensitive(de_uno)
        from enrutador import clientes
        sin_agente = not clientes.instalados()
        con_texto = bool(self.entrada_maestro.get_text().strip())
        self.boton_maestro.set_label("Enviar" if con_texto else "Conversación")
        if con_texto:
            self.boton_maestro.add_css_class("con-texto")
        else:
            self.boton_maestro.remove_css_class("con-texto")
        if sin_fuente:
            ayuda = "Aún no hay de dónde leer las tareas: configura una fuente primero"
        elif not de_uno:
            ayuda = "Elige un proyecto para hablar con su maestro"
        elif sin_agente:
            ayuda = clientes.SIN_AGENTE_TEXTO   # por qué el botón no hace nada
        else:
            titulo = clientes.de(self.cliente_del_maestro(clientes.instalados())).titulo
            ayuda = (f"Enviárselo al maestro, que habla con {titulo}" if con_texto else
                     "Ver la conversación con el maestro de este proyecto")
        self.boton_maestro.set_tooltip_text(ayuda)
        panel = getattr(self, "panel_maestro", None)
        if panel is not None and panel.get_reveal_child():
            if de_uno:
                self.pintar_conversacion()
            else:
                self.cerrar_conversacion()
