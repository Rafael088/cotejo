"""Los modelos de todos los agentes en el board (v1.3.0, cotejo-qixs4j).

«Asignar a» (el menú de la carta y el de la ficha) y «¿Qué agente la hace?» ofrecen los modelos
de los agentes **instalados y con sesión** (`enrutador.modelos_vivos.listos`), agrupados por
agente y con **el agente del proyecto primero** (`origen.agente_de`: el que se eligió al crearlo;
si no lo dice, Claude). Cada grupo trae sus modelos de fábrica y los registrados
(`enrutador.niveles.grupos`).

«Añadir modelo…» abre un diálogo sencillo: agente, modelo (de su lista en vivo o escrito), nombre
y nivel. Registra con `modelos_vivos.agregar`, lo mismo que `cotejo modelos agregar`. La lista en
vivo se pide al CLI en un hilo (`modelos_vivos.listar`, con caché y tope); mientras tanto se ve lo
guardado. Al pintar nunca se lanza ningún CLI: solo se miran archivos.
"""

import threading

from gi.repository import Adw, GLib, Gtk

from enrutador import clientes, config as enrutador_config, modelos_vivos, niveles

from .. import bitacora, modelo, origen
from .comun import ESPACIADO_SM, ESPACIADO_XS
from .escala import px
from .piezas import con_mano

ESCRIBIR = "Otro (escríbelo abajo)"


def titulo_de(cliente):
    if cliente in clientes.CLIENTES:
        return clientes.CLIENTES[cliente].titulo or cliente
    return "Otros"


class Modelos:
    """Los métodos de `Board` que saben de los modelos de cada agente."""

    def leer_modelos(self):
        """Al pintar: la config, quién está listo y, por proyecto, su agente (se olvida aquí)."""
        try:
            self.definiciones = enrutador_config.cargar().get("modelos") or []
        except enrutador_config.ConfigInvalida:
            self.definiciones = []
        self.listos = modelos_vivos.listos()
        self.agentes_de_proyecto = {}

    def agente_del_proyecto(self, proyecto):
        nombre = getattr(proyecto, "nombre", "") or ""
        cache = self.__dict__.setdefault("agentes_de_proyecto", {})
        if nombre not in cache:
            try:
                carpeta = self.fuente.carpeta_de(nombre) if nombre else None
            except Exception:  # noqa: BLE001 - sin carpeta, Claude
                carpeta = None
            cache[nombre] = origen.agente_de(carpeta) if carpeta else ""
        return cache[nombre]

    def grupos_de(self, proyecto):
        """`[(cliente, [nombres])]` para el menú, con el agente del proyecto primero."""
        if not hasattr(self, "listos"):
            self.leer_modelos()
        return niveles.grupos(self.definiciones, self.listos, self.agente_del_proyecto(proyecto))

    # --- «Añadir modelo» ----------------------------------------------------------------------

    def abrir_anadir_modelo(self, cliente=None, al_agregar=None):
        """El diálogo. `al_agregar(clave)` se llama al registrar (p. ej. para asignarla)."""
        listos = list(getattr(self, "listos", None) or modelos_vivos.listos()) or \
            list(clientes.CLIENTES)
        cliente = cliente if cliente in listos else listos[0]
        dialogo = Adw.AlertDialog(
            heading="Añadir modelo",
            body="Elige el agente y uno de sus modelos (o escríbelo). Queda en el catálogo de "
                 "Cotejo, como con «cotejo modelos agregar».")
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_SM))

        def fila(texto, widget):
            caja.append(Gtk.Label(label=texto, xalign=0, css_classes=["detalle-clave"]))
            caja.append(widget)

        dialogo.clientes = listos
        dialogo.agente = Gtk.DropDown.new_from_strings([titulo_de(c) for c in listos])
        dialogo.agente.set_selected(listos.index(cliente))
        fila("AGENTE", dialogo.agente)
        dialogo.lista = Gtk.StringList()
        dialogo.modelo = Gtk.DropDown(model=dialogo.lista, enable_search=True,
                                      expression=Gtk.PropertyExpression.new(
                                          Gtk.StringObject, None, "string"))
        fila("MODELO", dialogo.modelo)
        dialogo.estado = Gtk.Label(xalign=0, css_classes=["detalle-tenue"], wrap=True)
        caja.append(dialogo.estado)
        dialogo.escrito = Gtk.Entry(placeholder_text="o escribe su id, p. ej. proveedor/modelo")
        caja.append(dialogo.escrito)
        dialogo.nombre = Gtk.Entry(placeholder_text="Nombre (opcional)")
        fila("NOMBRE", dialogo.nombre)
        dialogo.nivel = Gtk.DropDown.new_from_strings([t for _, t in modelos_vivos.NIVELES_TEXTO])
        dialogo.nivel.set_selected(1)
        fila("NIVEL", dialogo.nivel)
        # Solo salen los agentes listos; el que falta se instala o se conecta en «Revisar el
        # equipo» (cotejo-2j6un7).
        dialogo.ir_al_equipo = con_mano(Gtk.Button(
            label="¿Falta un agente? Instálalo o conéctalo", css_classes=["flat"],
            halign=Gtk.Align.START))
        dialogo.ir_al_equipo.connect("clicked", lambda *_: self.ver_equipo())
        caja.append(dialogo.ir_al_equipo)
        caja.set_margin_top(px(ESPACIADO_XS))
        dialogo.set_extra_child(caja)
        dialogo.add_response("cancelar", "Cancelar")
        dialogo.add_response("agregar", "Añadir")
        dialogo.set_response_appearance("agregar", Adw.ResponseAppearance.SUGGESTED)
        dialogo.set_default_response("agregar")
        dialogo.set_close_response("cancelar")
        dialogo.set_response_enabled("agregar", True)
        dialogo.agente.connect("notify::selected",
                               lambda *_: self.cargar_modelos_del_dialogo(dialogo))
        dialogo.connect("response", self.al_responder_anadir, al_agregar)
        self.dialogo_modelo = dialogo
        self.cargar_modelos_del_dialogo(dialogo)
        dialogo.present(self)
        return dialogo

    def cliente_del_dialogo(self, dialogo):
        return dialogo.clientes[dialogo.agente.get_selected()]

    def poner_modelos(self, dialogo, cliente, nombres, vivos):
        if self.cliente_del_dialogo(dialogo) != cliente:
            return False                      # cambiaron de agente mientras tanto
        dialogo.lista.splice(0, dialogo.lista.get_n_items(), list(nombres) + [ESCRIBIR])
        dialogo.modelo.set_selected(0)
        dialogo.estado.set_label(
            f"{len(nombres)} modelos de {titulo_de(cliente)}" + ("" if vivos else
                                                                   " (buscando más…)"))
        return False

    def cargar_modelos_del_dialogo(self, dialogo):
        """Pone lo guardado ya y pide la lista en vivo en un hilo (`listar_en_fondo`)."""
        cliente = self.cliente_del_dialogo(dialogo)
        self.poner_modelos(dialogo, cliente, modelos_vivos.en_cache(cliente),
                           cliente not in modelos_vivos.PREGUNTA)
        if cliente in modelos_vivos.PREGUNTA:
            self.listar_en_fondo(
                cliente, lambda nombres: self.poner_modelos(dialogo, cliente, nombres, True))

    def listar_en_fondo(self, cliente, al_terminar):
        """`modelos_vivos.listar` en un hilo; vuelve por `GLib.idle_add`. Las pruebas lo
        reemplazan por uno que corre seguido."""
        def correr():
            nombres = modelos_vivos.listar(cliente)
            GLib.idle_add(lambda: al_terminar(nombres) and False)
        threading.Thread(target=correr, daemon=True).start()

    def modelo_del_dialogo(self, dialogo):
        escrito = dialogo.escrito.get_text().strip()
        if escrito:
            return escrito
        elegido = dialogo.modelo.get_selected_item()
        texto = elegido.get_string() if elegido is not None else ""
        return "" if texto == ESCRIBIR else texto

    def al_responder_anadir(self, dialogo, respuesta, al_agregar=None):
        self.dialogo_modelo = None
        if respuesta != "agregar":
            return None
        nivel = modelos_vivos.NIVELES_TEXTO[dialogo.nivel.get_selected()][0]
        try:
            guardado, _ = modelos_vivos.agregar(
                self.cliente_del_dialogo(dialogo), self.modelo_del_dialogo(dialogo),
                dialogo.nombre.get_text(), nivel)
        except (ValueError, enrutador_config.ConfigInvalida) as error:
            self.aviso(f"No añadí el modelo: {error}")
            return None
        self.aviso(f"Añadido {guardado['nombre']} como #agente/{guardado['clave']}")
        self.leer_modelos()
        if al_agregar is not None:
            al_agregar(guardado["clave"])
        else:
            self.app.refrescar()
        return guardado

    def al_anadir_y_asignar(self, proyecto, tarea, cliente, popover):
        """«Añadir modelo…» desde «Asignar a»: al registrarlo, se le asigna a la tarea."""
        if popover is not None:
            popover.popdown()

        def asignar(clave):
            try:
                actual = self.fuente.poner_agente(tarea, clave)
                bitacora.anotar("asignar", proyecto, actual, de=tarea.agente, a=clave)
            except (modelo.TareaCambiada, OSError) as error:
                self.aviso(f"No pude asignarla: cambió en {error}")
            self.app.refrescar()
        return self.abrir_anadir_modelo(cliente or self.agente_del_proyecto(proyecto) or None,
                                        asignar)
