"""Mover a Haciendo lanza el agente (v1.3.0, cotejo-7xsjb8), y lo que hace se ve en vivo.

Pasar a mano una tarea de Pendiente a Haciendo (arrastrando, con el menú, con Ctrl+→ o desde la
ficha: todo pasa por `mover`) la despacha en segundo plano con su modelo asignado. Quien
decide y lanza es `enrutador/despacho_board.py`; aquí solo se le contesta a la persona:

- **Con modelo**: se lanza, la carta pasa a Haciendo y un aviso dice quién empezó.
- **Sin modelo**: se pregunta qué agente la hace, con la propuesta del enrutador y su porqué;
  al elegir se guarda con «asignar» y se lanza. «La hago yo» la asigna a la persona y la mueve
  sin lanzar nada.
- **n0** (de una persona): se mueve como siempre y no se lanza nada.
- **Sin hueco** (`cotejo capacidad` dice 0): no se lanza; la tarea queda en Pendiente **en
  espera** —un chip «En espera» en su carta y el motivo en su ficha— y un aviso lo dice en
  llano. Nada la lanza sola después: se vuelve a mover cuando haya hueco.

**En vivo.** La ficha de una tarea en Haciendo que lanzó el board lleva «Lo que hace el agente»:
una frase de cómo va y sus mensajes (`lanzados.Seguimiento`, en llano). El temporizador que trae
las líneas nuevas (`GLib.timeout_add_seconds(1)`) existe solo mientras la ficha se ve: nace en
`do_map` y se quita en `do_unmap`, como el reloj de Preparando. El hilo que espera al agente no
toca GTK: avisa con `GLib.idle_add` (`agente_terminado`).
"""

from gi.repository import Adw, GLib, Gtk, Pango

from .. import bitacora, lanzados, modelo
from .comun import ESPACIADO_SM, ESPACIADO_XS, id_corto
from .piezas import icono

SEGUNDOS = 1
EN_CURSO = "en-curso"


class EnVivo(Gtk.Box):
    """«Lo que hace el agente» en la ficha: la situación y los mensajes, al día cada segundo
    mientras se ve."""

    __gtype_name__ = "CotejoAgenteEnVivo"

    def __init__(self, tarea_id):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=ESPACIADO_XS)
        self.id = tarea_id
        self.seguimiento = lanzados.Seguimiento(tarea_id)
        self.temporizador = 0
        self.refrescos = 0            # las pruebas lo miran
        self.vacio = True
        cabeza = Gtk.Box(spacing=ESPACIADO_XS)
        cabeza.append(icono("agente", 12))
        cabeza.append(Gtk.Label(label="LO QUE HACE EL AGENTE", xalign=0,
                                css_classes=["detalle-clave"]))
        self.append(cabeza)
        self.situacion = Gtk.Label(xalign=0, wrap=True, css_classes=["detalle-valor"],
                                   wrap_mode=Pango.WrapMode.WORD_CHAR)
        self.append(self.situacion)
        self.registro = Gtk.TextView(editable=False, cursor_visible=False, monospace=True,
                                     wrap_mode=Gtk.WrapMode.WORD_CHAR,
                                     css_classes=["entrevista-texto"])
        self.marco = Gtk.ScrolledWindow(child=self.registro, min_content_height=140,
                                        max_content_height=260,
                                        hscrollbar_policy=Gtk.PolicyType.NEVER,
                                        css_classes=["entrevista-marco"])
        self.append(self.marco)
        self.refrescar()

    def texto(self):
        buffer = self.registro.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

    def refrescar(self):
        """Pone la situación y añade al final lo que el agente escribió desde la última vez."""
        registro = lanzados.leer(self.id)
        self.situacion.set_label(lanzados.situacion(lanzados.estado(registro)))
        nuevas = self.seguimiento.nuevas(registro) if registro else []
        buffer = self.registro.get_buffer()
        if nuevas:
            if self.vacio:
                buffer.set_text("")
                self.vacio = False
            delante = "\n" if buffer.get_char_count() else ""
            buffer.insert(buffer.get_end_iter(), delante + "\n".join(nuevas))
            ajuste = self.marco.get_vadjustment()
            GLib.idle_add(lambda: ajuste.set_value(ajuste.get_upper()) and False)
        elif self.vacio and not buffer.get_char_count():
            buffer.set_text("Todavía no ha dicho nada.")
        return nuevas

    def _tic(self):
        self.refrescos += 1
        self.refrescar()
        return GLib.SOURCE_CONTINUE

    def hay_reloj(self):
        return bool(self.temporizador)

    def do_map(self):
        Gtk.Box.do_map(self)
        if not self.temporizador:
            self.temporizador = GLib.timeout_add_seconds(SEGUNDOS, self._tic)

    def do_unmap(self):
        if self.temporizador:
            GLib.source_remove(self.temporizador)
            self.temporizador = 0
        Gtk.Box.do_unmap(self)


class Lanzar:
    """Los métodos de `Board` que lanzan una tarea al moverla y la siguen en su ficha."""

    def lanzar_al_mover(self, proyecto, tarea):
        """Pendiente → Haciendo, a mano. True si ya se encargó (lanzó, preguntó o quedó en
        espera); False si toca moverla como siempre (una tarea de persona)."""
        from enrutador import despacho_board as db
        try:
            estado = db.lanzar(
                tarea.id, al_terminar=lambda e: GLib.idle_add(self.agente_terminado, e))
        except db.EsDeUnaPersona:
            self.aviso("Es una tarea para una persona: la paso a Haciendo sin lanzar ningún "
                       "agente.")
            return False
        except db.FaltaModelo as falta:
            self.preguntar_modelo(proyecto, tarea, falta.propuesta, falta.razon)
            return True
        except db.SinHueco as sin_hueco:
            self.aviso(str(sin_hueco))
            self.app.refrescar()
            return True
        except db.NoSePuede as error:
            self.aviso(f"No la lancé: {error}")
            self.app.refrescar()
            return True
        self.foco_tras_pintar = estado.get("id") or tarea.id
        self.aviso(f"{estado.get('modelo') or 'El agente'} empezó a trabajar en "
                   f"{id_corto(estado.get('id') or tarea.id)}")
        self.app.refrescar()
        return True

    def agente_terminado(self, estado):
        """El agente volvió (ya en el hilo de la interfaz): se avisa y se repinta."""
        if estado:
            self.aviso(f"{id_corto(estado.get('id'))}: {lanzados.situacion(estado)}")
        self.app.refrescar()
        return GLib.SOURCE_REMOVE

    # --- sin modelo: se pregunta ------------------------------------------------------------

    def modelos_para_preguntar(self, propuesta):
        """Los modelos que se ofrecen (sin las personas), con la propuesta primero."""
        modelos = [a for a in self.agentes if a and a not in self.alias_persona]
        if propuesta in modelos:
            modelos.remove(propuesta)
        return ([propuesta] if propuesta else []) + modelos

    def preguntar_modelo(self, proyecto, tarea, propuesta, razon):
        """¿Qué agente la hace? Con la propuesta del enrutador y su porqué."""
        modelos = self.modelos_para_preguntar(propuesta)
        dialogo = Adw.AlertDialog(
            heading="¿Qué agente la hace?",
            body=(f"Nadie le ha asignado modelo. Propongo {propuesta} porque {razon}.\n\n"
                  f"{tarea.texto}"))
        desplegable = Gtk.DropDown.new_from_strings(modelos)
        desplegable.set_selected(0)
        dialogo.set_extra_child(desplegable)
        dialogo.add_response("cancelar", "Cancelar")
        dialogo.add_response("yo", "La hago yo")
        dialogo.add_response("lanzar", "Asignar y lanzar")
        dialogo.set_response_appearance("lanzar", Adw.ResponseAppearance.SUGGESTED)
        dialogo.set_default_response("lanzar")
        dialogo.set_close_response("cancelar")
        dialogo.modelos = modelos
        dialogo.desplegable = desplegable
        dialogo.connect("response", self.al_responder_modelo, proyecto, tarea)
        self.pregunta_modelo = dialogo
        dialogo.present(self)
        return dialogo

    def al_responder_modelo(self, dialogo, respuesta, proyecto, tarea):
        self.pregunta_modelo = None
        if respuesta not in ("lanzar", "yo"):
            return
        if respuesta == "yo":
            agente = self.alias_persona[0] if self.alias_persona else "persona"
        else:
            agente = dialogo.modelos[dialogo.desplegable.get_selected()]
        try:
            actual = self.fuente.poner_agente(tarea, agente)
            bitacora.anotar("asignar", proyecto, actual, de=tarea.agente, a=agente)
        except (modelo.TareaCambiada, OSError) as error:
            self.aviso(f"No pude asignarla: cambió en {error}")
            self.app.refrescar()
            return
        if respuesta == "yo" or not self.lanzar_al_mover(proyecto, actual):
            self.escribir_movimiento(proyecto, actual, EN_CURSO)

    # --- lo que se ve -----------------------------------------------------------------------

    def leer_en_espera(self):
        """{id: motivo} de las que esperan hueco, una vez por repintado."""
        try:
            self.en_espera = lanzados.en_espera()
        except OSError:
            self.en_espera = {}
        return self.en_espera

    def motivo_en_espera(self, tarea):
        if tarea.columna != modelo.PENDIENTE:
            return ""
        return (getattr(self, "en_espera", None) or {}).get(tarea.id, "")

    def seccion_en_espera(self, motivo):
        """En la ficha de una tarea en espera: por qué no se lanzó."""
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=ESPACIADO_XS,
                       css_classes=["anotacion", "detenida"])
        cabeza = Gtk.Box(spacing=ESPACIADO_XS)
        cabeza.append(icono("aviso", 12))
        cabeza.append(Gtk.Label(label="EN ESPERA", xalign=0, css_classes=["anotacion-titulo"]))
        caja.append(cabeza)
        caja.append(Gtk.Label(label=motivo, xalign=0, wrap=True, selectable=True,
                              focusable=False, wrap_mode=Pango.WrapMode.WORD_CHAR,
                              css_classes=["anotacion-texto"]))
        caja.set_margin_top(ESPACIADO_SM)
        return caja

    def seccion_en_vivo(self, tarea):
        """«Lo que hace el agente», si la lanzó el board y está en Haciendo; si no, None."""
        if tarea.columna != EN_CURSO or lanzados.leer(tarea.id) is None:
            return None
        return EnVivo(tarea.id)
