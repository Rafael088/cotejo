"""«Ver mi app» y «Abrir la carpeta» en el board (v1.3.0, cotejo-vn4qd2).

Una mezcla de `Board`. Quien no programa tiene que poder ver su app sin abrir una terminal ni
saber qué es una rama: los dos botones viven en cada tarjeta del Inicio y en el mapa del
proyecto, y siempre usan la carpeta principal del proyecto (`fuente.carpeta_de`), nunca un
worktree: desde cotejo-00fwc2 lo aprobado ya está ahí.

Qué abrir lo decide `tareas/como_se_abre.py` (lo anotado en la arquitectura o, si no, una
deducción prudente) y arrancarlo, esperar y pararlo, `tareas/servidor_app.py`, en un hilo para
no congelar la ventana. El navegador y la carpeta se abren con el lanzador del sistema (Gio),
fuera de cualquier sandbox: es la persona quien mira. Cerrar el board para las apps que arrancó.
"""

import threading

from gi.repository import Gio, GLib, Gtk

from .. import como_se_abre, servidor_app
from .comun import ESPACIADO_SM, MARGEN_TABLERO_LADOS, MARGEN_TABLERO_VERTICAL, TODOS
from .escala import px
from .piezas import con_mano


def correr_aparte(funcion):
    """Corre `funcion` en un hilo (las pruebas lo cambian por una llamada directa)."""
    threading.Thread(target=funcion, daemon=True).start()


class VerApp:
    """Los métodos de `Board` que abren la app y la carpeta de un proyecto."""

    def crear_ver_app(self):
        self.servidores = servidor_app.Servidores()
        self.abriendo_app = set()
        self.connect("close-request", self._parar_apps_al_cerrar)
        self.crear_botones_flotantes()

    def crear_botones_flotantes(self):
        """«Ver mi app» y «Abrir la carpeta» flotando en el tablero (v1.3.0, cotejo-rcohjm).

        Viven en un overlay del tablero (`encima_tablero`), fuera de las columnas: salen con un
        proyecto elegido (nunca con «Todos los proyectos») y abren lo mismo que sus iguales
        del Inicio y del mapa, siempre sobre la carpeta principal del proyecto.
        """
        caja = Gtk.Box(spacing=px(ESPACIADO_SM), halign=Gtk.Align.END, valign=Gtk.Align.START,
                       margin_top=px(MARGEN_TABLERO_VERTICAL),
                       margin_end=px(MARGEN_TABLERO_LADOS))
        self.boton_flotante_ver_app = con_mano(Gtk.Button(label="Ver mi app"))
        self.boton_flotante_carpeta = con_mano(Gtk.Button(label="Abrir la carpeta"))
        for boton, accion in ((self.boton_flotante_ver_app, self.al_ver_app_flotante),
                              (self.boton_flotante_carpeta, self.al_abrir_carpeta_flotante)):
            boton.connect("clicked", lambda _b, a=accion: a())
            caja.append(boton)
        self.flotantes_app = caja
        self.encima_tablero.add_overlay(caja)
        self.poner_botones_flotantes()

    def al_ver_app_flotante(self):
        self.ver_mi_app(self.seleccion)

    def al_abrir_carpeta_flotante(self):
        self.abrir_carpeta(self.seleccion)

    def poner_botones_flotantes(self):
        """Los botones solo con un proyecto elegido, no con «Todos los proyectos» ni sin fuente."""
        caja = getattr(self, "flotantes_app", None)
        if caja is None:
            return
        caja.set_visible(self.seleccion != TODOS and not self.fuente.problema)

    def _parar_apps_al_cerrar(self, *_):
        self.servidores.parar_todos()
        self.pintar_botones_app()
        return False          # el cierre sigue como siempre (ocultar la ventana)

    def _carpeta(self, nombre, carpeta=None):
        if carpeta:
            return str(carpeta)
        if self.fuente.problema:
            return ""
        encontrada = self.fuente.carpeta_de(nombre)
        return str(encontrada) if encontrada else ""

    def ver_mi_app(self, nombre, carpeta=None):
        """Lo que hace «Ver mi app»: arranca o reutiliza su app y abre el navegador."""
        if nombre in self.abriendo_app:
            return
        plan = como_se_abre.plan_de(self._carpeta(nombre, carpeta))
        if not plan.ok:
            self.aviso(plan.motivo, segundos=10)
            return
        self.abriendo_app.add(nombre)
        self.aviso("Abriendo tu app…", segundos=3)

        def abrir():
            try:
                resultado = self.servidores.abrir(nombre, plan)
            except Exception as error:   # noqa: BLE001 — se dice, no se queda «abriendo»
                resultado = servidor_app.Resultado(False, f"Tu app no arrancó: {error}")
            GLib.idle_add(self._app_abierta, nombre, resultado)
        correr_aparte(abrir)

    def _app_abierta(self, nombre, resultado):
        self.abriendo_app.discard(nombre)
        if resultado.abrir:
            self.lanzar(resultado.abrir)
        if resultado.corriendo:
            self.aviso(resultado.texto, segundos=8, boton="Parar",
                       al_pulsar=lambda: self.parar_app(nombre))
        elif not resultado.ok and resultado.log:
            self.aviso(resultado.texto, segundos=12, boton="Ver lo que dijo",
                       al_pulsar=lambda: self.lanzar(resultado.log))
        else:
            self.aviso(resultado.texto, segundos=8 if resultado.ok else 12)
        self.pintar_botones_app()
        return GLib.SOURCE_REMOVE

    def parar_app(self, nombre):
        if self.servidores.parar(nombre):
            self.aviso("Paré tu app.", segundos=3)
        self.pintar_botones_app()

    def abrir_carpeta(self, nombre, carpeta=None):
        """Lo que hace «Abrir la carpeta»: la carpeta principal, en el gestor de archivos."""
        carpeta = self._carpeta(nombre, carpeta)
        if not carpeta:
            self.aviso("No encuentro la carpeta de este proyecto en tu equipo.")
            return
        self.lanzar(carpeta)

    def lanzar(self, destino):
        """Abre una dirección o una ruta con el programa de la persona (las pruebas lo cambian)."""
        uri = destino if "://" in destino else Gio.File.new_for_path(destino).get_uri()
        try:
            Gio.AppInfo.launch_default_for_uri(uri, None)
        except GLib.Error as error:
            self.aviso(f"No pude abrirlo: {error.message}", segundos=8)

    def pintar_botones_app(self):
        """«Parar» solo si la app está en marcha; «Ver mi app» se apaga mientras no haya código."""
        pantalla = getattr(self, "pantalla_mapa", None)
        proyecto = getattr(self, "mapa_proyecto", None)
        if pantalla is None:
            return
        pantalla.boton_parar.set_visible(bool(proyecto) and self.servidores.vivo(proyecto[0]))
        if not proyecto:
            pantalla.boton_ver_app.set_sensitive(False)
            pantalla.boton_ver_app.set_tooltip_text("")
            return
        nombre, carpeta = proyecto
        plan = como_se_abre.plan_de(self._carpeta(nombre, carpeta or None))
        pantalla.boton_ver_app.set_sensitive(not plan.sin_app)
        pantalla.boton_ver_app.set_tooltip_text(plan.motivo if plan.sin_app else "")
