"""`App`: la aplicación GTK, el tema, la vigilancia de la fuente y `main`."""

import sys

from gi.repository import Adw, GLib, Gdk, Gio, Gtk

from .. import bitacora, configuracion, estado, fuente as f, rutas, temas, usuario
from .comun import APP_ID, DATOS, animaciones_activas, aplicar_clase_animaciones
from .piezas import pintar_logo
from .estilo import CSS
from .ventana import Board


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.add_main_option("fondo", 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Quedarse en segundo plano, sin abrir la ventana", None)
        # Sin opción el board se abre o se cierra; con --board solo se abre. Se queda por
        # quien ya lo llamaba así, de cuando la ventana por defecto era la lista.
        self.add_main_option("board", 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Abrir el board de tareas", None)
        # La config con la que se abrió la fuente: si cambia (`cotejo fuentes usar`), la app la
        # reabre sola en vez de exigir que alguien la reinicie. Ver `vigilar_config`.
        self.config_fuente = f.cargar_config()
        self.fuente = f.abrir(self.config_fuente)
        self.monitor_config = None
        self.cambio_config_pendiente = 0
        self.board = None
        self.proyectos = []
        self.avisos = []  # lo que no se pudo leer o escribir en el último escaneo
        self.bitacora = {}  # por id de tarea, lo último que se dijo de ella
        self.monitores = []
        self.recarga_pendiente = 0
        self.proveedor = None
        self.tema = None  # el id que pidió la config, aunque se esté viendo el de defecto
        self.colores = None  # los del tema que se está viendo: los usa el logo de la cabecera
        self.esquema = None  # claro u oscuro: el dot solo baja su brillo en uno claro
        self.problema_tema = None  # por qué no se pudo usar, si no se pudo
        # Si el board que se abra será el primero de un proceso que arrancó con la ventana: es
        # el único que lleva la animación de arranque. Con --fondo no hay arranque que enseñar.
        self.desde_cero = True

    def do_startup(self):
        Adw.Application.do_startup(self)
        self.proveedor = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self.proveedor, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.aplicar_tema(temas.elegido())
        # Los iconos propios. Van como simbólicos para que el color lo siga poniendo el CSS:
        # el mismo dibujo va en plata en un chip, en verde en la columna que te espera y en
        # ámbar en una devolución, y eso solo lo da la letra `color`.
        tema_iconos = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        tema_iconos.add_search_path(str(DATOS / "iconos"))
        # El ícono de la app (`data/<APP_ID>.svg`) para la ventana. En Linux ya lo da el
        # .desktop; en Windows es el que sale en Alt+Tab y en la barra de título.
        tema_iconos.add_search_path(str(DATOS))
        Gtk.Window.set_default_icon_name(APP_ID)
        # gtk-enable-animations puede cambiar con la app abierta (el panel de accesibilidad no
        # exige reiniciar nada), y las ventanas ya abiertas tienen que enterarse sin recargar.
        ajustes = Gtk.Settings.get_default()
        if ajustes is not None:
            ajustes.connect("notify::gtk-enable-animations", self.al_cambiar_animaciones)
        self.atajos()
        self.refrescar()
        self.vigilar()
        self.vigilar_config()
        self.poner_lo_del_usuario()
        # El proceso se queda vivo con la ventana cerrada: quien lo abre y lo cierra es el
        # widget de la barra, y así el resumen que ese widget lee sigue fresco todo el tiempo.
        self.hold()

    def poner_lo_del_usuario(self):
        """Con un paquete del sistema, lo que vive en el $HOME de esta persona (el widget de la
        barra, el protocolo de los agentes) lo pone `usuario.sh`, que el paquete no puede correr
        por ella. Se corre aquí, la primera vez que abre Cotejo y después de cada actualización,
        en segundo plano: no retrasa el arranque y, si falla, queda en `usuario.log` y `doctor`
        lo dice (cotejo-8ecldw).
        """
        orden = usuario.hace_falta()
        if orden is None:
            return
        registro = rutas.estado() / "usuario.log"
        try:
            registro.parent.mkdir(parents=True, exist_ok=True)
            lanzador = Gio.SubprocessLauncher.new(Gio.SubprocessFlags.STDERR_MERGE)
            lanzador.set_stdout_file_path(str(registro))
            lanzador.spawnv(orden)
        except (GLib.Error, OSError) as error:
            print(f"Cotejo: no pude poner lo de este usuario ({error})", file=sys.stderr)

    def do_command_line(self, linea):
        opciones = linea.get_options_dict()
        if opciones.contains("fondo"):
            self.desde_cero = False
            return 0
        if opciones.contains("board"):
            self.abrir_board()
            return 0
        self.alternar_board()
        return 0

    def aplicar_tema(self, ident):
        """Pinta la app con un tema. Si no se puede usar, con el de defecto, y lo dice.

        Todo el CSS se recarga de una vez —los colores del tema delante, el resto detrás— en
        el mismo proveedor: dos proveedores con el `:root` repartido dependen de en qué orden
        los resuelva GTK, y uno solo no. El esquema de Adwaita va con el tema porque lo que no
        pinta Cotejo (entradas, casillas, el diálogo) lo pinta Adwaita según sea claro u oscuro.
        """
        self.tema = ident
        try:
            datos = temas.cargar(ident)
            self.problema_tema = None
        except temas.TemaRoto as error:
            datos = temas.cargar(temas.DEFECTO)
            self.problema_tema = str(error)
        self.proveedor.load_from_string(temas.css(datos) + CSS)
        self.colores = datos["colores"]
        self.esquema = datos["esquema"]
        if self.board:
            pintar_logo(self.board.logo, self.colores)
            # El dot no cambia de color con el tema: en uno claro solo baja su brillo. Apagado
            # (lo normal desde la 1.2.4) no existe, y un error aquí dejaba a Adwaita en el
            # esquema anterior: diálogos y avisos oscuros sobre un board claro.
            if self.board.dot is not None:
                self.board.dot.set_property("claro", self.esquema == "claro")
        Adw.StyleManager.get_default().set_color_scheme(
            Adw.ColorScheme.FORCE_LIGHT if datos["esquema"] == "claro"
            else Adw.ColorScheme.FORCE_DARK)
        return self.problema_tema

    def elegir_tema(self, ident):
        """Lo que hace el selector: aplicarlo ya y apuntarlo en la config para la próxima vez.

        Si la config está rota no se escribe encima —se perdería lo que tiene—: el tema se ve
        igual hasta que se cierre la app, y se avisa.
        """
        problema = self.aplicar_tema(ident)
        if problema:
            return problema
        try:
            datos = configuracion.leer()
            if datos.get("tema") != ident:
                configuracion.guardar({**datos, "tema": ident})
        except (configuracion.ConfigRota, OSError) as error:
            return f"Se ve, pero no pude guardarlo: {error}"
        return None

    def al_cambiar_animaciones(self, *_args):
        """El ajuste cambió con la app abierta: cada ventana ya viva se pone al día."""
        if self.board is not None:
            aplicar_clase_animaciones(self.board)

    # --- datos ------------------------------------------------------------

    def refrescar(self):
        """Escanea el vault una sola vez y reparte: el board y el archivo que lee la barra."""
        avisos = []
        # Con las hechas: el board necesita las cuatro columnas.
        self.proyectos = ([] if self.fuente.problema
                          else self.fuente.escanear(incluir_hechas=True, avisos=avisos))
        fallo = estado.escribir(estado.resumir(self.proyectos, self.fuente.problema, avisos))
        if fallo:
            # Si esto falla, la barra se queda con el conteo de ayer para siempre. Se dice.
            avisos = avisos + [{"nota": "", "motivo": fallo}]
        self.avisos = avisos
        # Solo con el board abierto: el proceso de fondo mantiene el conteo de la barra, y
        # para eso no necesita saber qué entregó nadie.
        if self.board is not None:
            self.bitacora = bitacora.ultimas()
        if self.board is not None:
            self.board.pintar()

    def vigilar(self):
        for monitor in self.monitores:
            monitor.cancel()
        self.monitores = []
        # Una fuente que no vive en archivos no tiene nada que vigilar: se recarga a mano.
        for carpeta in self.fuente.vigilables():
            monitor = Gio.File.new_for_path(carpeta).monitor_directory(Gio.FileMonitorFlags.NONE, None)
            monitor.connect("changed", self.al_cambiar_archivo)
            self.monitores.append(monitor)

    def al_cambiar_archivo(self, _monitor, archivo, _otro, _evento):
        if archivo.get_basename().endswith(".tareas-tmp"):
            return
        if self.recarga_pendiente:
            GLib.source_remove(self.recarga_pendiente)
        self.recarga_pendiente = GLib.timeout_add(400, self.recarga_diferida)

    def recarga_diferida(self):
        self.recarga_pendiente = 0
        self.refrescar()
        self.vigilar()
        return GLib.SOURCE_REMOVE

    def vigilar_config(self):
        """Cambiar de fuente es un comando (`cotejo fuentes usar`), no un reinicio.

        Se vigila la carpeta y no el archivo porque la config se escribe con un reemplazo
        atómico, y un monitor sobre el archivo se queda mirando el que ya no está.
        """
        carpeta = configuracion.ruta().parent
        if not carpeta.is_dir():
            return
        self.monitor_config = Gio.File.new_for_path(str(carpeta)).monitor_directory(
            Gio.FileMonitorFlags.NONE, None)
        self.monitor_config.connect("changed", self.al_cambiar_config)

    def al_cambiar_config(self, _monitor, archivo, _otro, _evento):
        if archivo.get_basename() != configuracion.ruta().name:
            return
        if self.cambio_config_pendiente:
            GLib.source_remove(self.cambio_config_pendiente)
        self.cambio_config_pendiente = GLib.timeout_add(400, self.cambiar_de_fuente)

    def cambiar_de_fuente(self):
        """Reabre la fuente si la config dice otra cosa. Si la nueva no se puede abrir, se
        queda la de antes: mejor el board de ayer que un board vacío."""
        self.cambio_config_pendiente = 0
        # El tema también se sigue: `temas usar` desde la CLI cambia el board abierto. Si lo
        # escribió el propio selector, ya está aplicado y esto no hace nada.
        tema = temas.elegido()
        if tema != self.tema:
            self.aplicar_tema(tema)
        # Y el dot: `"dot": true|false` lo crea o lo destruye en el board abierto.
        if self.board is not None:
            self.board.sincronizar_dot()
        nueva = f.cargar_config()
        if nueva == self.config_fuente:
            return GLib.SOURCE_REMOVE
        try:
            fuente = f.abrir(nueva)
        except ValueError:
            return GLib.SOURCE_REMOVE
        self.config_fuente, self.fuente = nueva, fuente
        if self.board is not None:
            self.board.fuente = fuente
        self.refrescar()
        self.vigilar()
        return GLib.SOURCE_REMOVE

    # --- ventana ----------------------------------------------------------

    def abrir_board(self):
        if self.board is None:
            self.bitacora = bitacora.ultimas()  # el board la lee al pintarse por primera vez
            try:
                self.board = Board(self)
            except Exception:
                self.no_abrio()
                return
            # Cerrar solo lo oculta: el proceso sigue vivo para el widget de la barra.
            self.board.set_hide_on_close(True)
            if self.desde_cero and animaciones_activas():
                self.board.mostrar_arranque()  # el dot entra cuando acabe
            else:
                GLib.idle_add(lambda: self.board.entrar_dot() and False)
        self.desde_cero = False
        self.board.present()

    def no_abrio(self):
        """El board no se pudo crear: dejarlo escrito y decirlo, no quedarse vivo y callado.

        El proceso sigue (hizo `hold()`) y en Windows corre con pythonw, sin consola: sin esto,
        un error al crear la ventana no se veía en ninguna parte (cotejo-bezrqz).
        """
        import traceback
        registro = rutas.estado() / "cotejoboard.log"
        try:
            registro.parent.mkdir(parents=True, exist_ok=True)
            registro.write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            registro = None
        traceback.print_exc()
        aviso = Gtk.AlertDialog()
        aviso.set_message("Cotejo no pudo abrir el board")
        aviso.set_detail(f"Lo que pasó quedó en {registro}." if registro else
                         "Tampoco pude guardar el error: corre `cotejo --board` en una terminal.")
        aviso.show(None)

    def alternar_board(self):
        if self.board is not None and self.board.get_visible():
            self.board.close()
        else:
            self.abrir_board()

    def buscar(self):
        """Ctrl+F lleva a la búsqueda del board.

        Va como acelerador de la aplicación y no como tecla de la ventana porque esos se
        atienden antes: con la tecla en la ventana, el acelerador se la comía sin hacer nada.
        """
        if self.board is not None:
            self.board.ver_pestana("tablero")   # buscar es del tablero, no del Inicio
            self.board.busqueda.grab_focus()

    def atajos(self):
        for nombre, teclas, funcion in (
            ("buscar", ["<Ctrl>f"], self.buscar),
            ("recargar", ["<Ctrl>r", "F5"], lambda: self.refrescar()),
            ("cerrar", ["<Ctrl>w"], lambda: self.get_active_window() and self.get_active_window().close()),
            ("salir", ["<Ctrl>q"], self.quit),
        ):
            accion = Gio.SimpleAction.new(nombre, None)
            accion.connect("activate", lambda *_a, f=funcion: f())
            self.add_action(accion)
            self.set_accels_for_action(f"app.{nombre}", teclas)


SIN_PANTALLA = ("No hay pantalla gráfica: el board necesita una sesión de escritorio; "
                "la CLI funciona igual")


def main():
    # Sin display (ssh, TTY, un contenedor) GTK aborta con un traceback y un core dump al crear
    # la ventana. Al importar, PyGObject ya intentó inicializar GTK y, si falló, lo calla: por
    # eso se mira si hay display en vez de fiarse de init_check. Se sale con un mensaje y un
    # código distinto de 0.
    if not (Gtk.init_check() and Gdk.Display.get_default()):
        print(SIN_PANTALLA, file=sys.stderr)
        return 1
    if sys.platform == "win32":
        # Sin esto Windows agrupa la ventana con pythonw.exe y en la barra de tareas sale el
        # ícono de Python. Es el mismo id que lleva el acceso del menú Inicio (cotejo.iss), y
        # de ese acceso toma Windows el ícono y el nombre (cotejo-lwi9ft).
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    return App().run(sys.argv)
