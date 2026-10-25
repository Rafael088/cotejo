"""Mover una tarea: arrastrar, el menú, el motivo y deshacer."""

import time

from gi.repository import Adw, GObject, Gdk, Gtk

from .. import bitacora, modelo, revision, worktrees
from .comun import texto_a_markup
from .escala import px
from .piezas import TareaArrastrada, icono


class Movimientos:
    """Mover una tarea: arrastrar, el menú, el motivo y deshacer."""

    # --- arrastre ------------------------------------------------------

    def arrastrable(self, fila):
        origen = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        origen.connect("prepare", self.al_preparar, fila)
        origen.connect("drag-begin", self.al_empezar, fila)
        origen.connect("drag-end", self.al_soltar_carta, fila)
        origen.connect("drag-cancel", self.al_cancelar, fila)
        fila.add_controller(origen)

    def al_preparar(self, _origen, _x, _y, fila):
        self.arrastre = fila
        return Gdk.ContentProvider.new_for_value(
            GObject.Value(TareaArrastrada, TareaArrastrada(fila.proyecto, fila.tarea)))

    def al_empezar(self, _origen, arrastre, fila):
        """La carta que se arrastra se marca como hueco y lo que sigue al cursor es su texto."""
        fila.add_css_class("arrastrada")
        icono = Gtk.Label(label=texto_a_markup(fila.tarea.texto), use_markup=True, xalign=0,
                          wrap=True, max_width_chars=24, css_classes=["carta", "carta-texto"])
        icono.set_size_request(max(fila.get_width() - 24, 180), -1)
        Gtk.DragIcon.get_for_drag(arrastre).set_child(icono)
        arrastre.set_hotspot(24, 18)

    def al_soltar_carta(self, _origen, _arrastre, _borrar, fila):
        fila.remove_css_class("arrastrada")
        self.arrastre = None

    def al_cancelar(self, _origen, _arrastre, _motivo, fila):
        fila.remove_css_class("arrastrada")
        self.arrastre = None
        return False

    def al_entrar_arrastre(self, _destino, _x, _y, clave, caja):
        # Una columna solo se ilumina si soltar ahí cambia algo: la propia columna no cuenta.
        if self.arrastre is None or self.arrastre.tarea.columna == clave:
            return Gdk.DragAction(0)
        caja.add_css_class("columna-destino")
        return Gdk.DragAction.MOVE

    def al_salir_arrastre(self, _destino, caja):
        caja.remove_css_class("columna-destino")

    def al_soltar(self, _destino, valor, _x, _y, clave, caja):
        caja.remove_css_class("columna-destino")
        if not isinstance(valor, TareaArrastrada) or valor.tarea.columna == clave:
            return False
        self.mover(valor.proyecto, valor.tarea, clave)
        return True

    # --- acciones ------------------------------------------------------

    def al_activar(self, _lista, fila):
        if getattr(fila, "decision", None) is not None:
            alm, entrada = fila.decision
            self.ver_revision_decision(fila.proyecto, alm, entrada)
        elif getattr(fila, "tarea", None) is not None:
            # Una entrega se abre en su revisión, que es donde se aprueba; todo lo demás, en
            # la ficha. Nada se abre ya en la app de la fuente.
            if fila.tarea.columna == "por-validar" and self.entrega_de(fila.tarea) is not None:
                self.ver_revision(fila.proyecto, fila.tarea)
            else:
                self.ver_detalle(fila.proyecto, fila.tarea)

    def mover(self, proyecto, tarea, destino):
        """Único camino de escritura: lo usan el menú, el teclado, la ficha y el arrastre.

        Sacar una tarea de *Para comprobar* sin marcarla es rechazarla, y eso pide
        motivo antes de escribir nada. La evidencia es obligatoria al entregar por la misma
        razón que el motivo lo es al devolver: si no, el agente vuelve a entregar lo mismo.
        """
        # A Para comprobar solo se llega entregando (cotejo-2sxw7p): una tarea de un agente no
        # se pasa a mano, y se le dice a la persona por qué en vez de no hacer nada.
        bloqueo = modelo.aviso_comprobar_a_mano(tarea, destino, self.alias_persona)
        if bloqueo:
            self.aviso(bloqueo, segundos=8, boton="La hago yo",
                       al_pulsar=lambda: self.hacerla_yo(proyecto, tarea, destino))
            self.app.refrescar()
            return
        if tarea.columna == "por-validar" and destino != modelo.HECHA:
            self.preguntar_motivo(proyecto, tarea, destino)
            return
        # Pendiente → Haciendo a mano lanza su agente (v1.3.0, `lanzar.py`): con modelo, se
        # lanza; sin él, se pregunta; sin hueco, queda en espera. Solo una tarea de persona
        # sigue de largo y se mueve como siempre.
        if (tarea.columna == modelo.PENDIENTE and destino == "en-curso"
                and self.lanzar_al_mover(proyecto, tarea)):
            return
        # Haciendo → Pendiente a mano la pausa (cotejo-z7ma7r, `lanzar.py`): su agente se para
        # y el worktree, la rama y el modelo se quedan para retomarla.
        if tarea.columna == "en-curso" and destino == modelo.PENDIENTE:
            self.pausar_al_mover(tarea)
        self.escribir_movimiento(proyecto, tarea, destino)

    def hacerla_yo(self, proyecto, tarea, destino):
        """«La hago yo» del aviso de arriba: la persona se la queda y la mueve a donde quería.

        Se asigna a la persona como en el diálogo de «¿Qué agente la hace?»; si su agente lo
        lanzó el board, se para antes (su worktree y su rama se quedan, como al pausar, pero sin
        el aviso de retomarla: ya no la hace un agente).
        """
        agente = self.alias_persona[0] if self.alias_persona else "persona"
        if tarea.columna == "en-curso" and self.es_pausable(tarea):
            from enrutador import despacho_board as db
            db.pausar(tarea.id)
        try:
            actual = self.fuente.poner_agente(tarea, agente)
            bitacora.anotar("asignar", proyecto, actual, de=tarea.agente, a=agente)
        except (modelo.TareaCambiada, OSError) as error:
            self.aviso(f"No pude asignarla: cambió en {error}")
            self.app.refrescar()
            return
        self.escribir_movimiento(proyecto, actual, destino)

    def escribir_movimiento(self, proyecto, tarea, destino, motivo=""):
        # Mientras se integra en segundo plano, esa tarea no se vuelve a aprobar.
        if destino == modelo.HECHA and tarea.id in getattr(self, "integrando", ()):
            self.aviso("Todavía la estoy metiendo en tu app")
            return False
        # Aprobar una entrega ofrece integrar su rama (B4), o la integra sola en un proyecto
        # del Inicio (`origen.py`). Se mira antes de escribir porque
        # dar la tarea por buena retira su worktree, y con él el registro de qué repo es.
        plan = None
        if destino == modelo.HECHA and tarea.columna == "por-validar":
            plan = revision.plan_integracion(tarea.id, bitacora.ultima_entrega(tarea.id))
        try:
            actual = tarea
            if actual.hecha and destino != modelo.HECHA:
                actual = self.fuente.marcar(actual, hecha=False)
            actual = (self.fuente.marcar(actual, hecha=True) if destino == modelo.HECHA
                      else self.fuente.poner_estado(actual, destino))
            self.foco_tras_pintar = actual.id
        except (modelo.TareaCambiada, OSError) as error:
            self.aviso(f"No pude moverla: cambió en {error}")
            self.app.refrescar()
            return False
        # Quién hizo qué se anota después de escribir en la nota: el estado no depende de que
        # la bitácora llegue al disco. Los nombres distinguen las dos transiciones que son de
        # una persona, comprobar y rechazar, del resto de los movimientos a mano.
        operacion = {modelo.HECHA: "comprobar"}.get(destino, "rechazar" if motivo else "mover")
        bitacora.anotar(operacion, proyecto, actual, de=tarea.columna, a=destino,
                        **({"motivo": motivo} if motivo else {}))
        # Dar por buena una tarea es lo único que no puede deshacer un agente, y hasta ahora
        # era también lo único que pasaba en silencio.
        if destino == modelo.HECHA:
            self.finalizadas.anotar(actual)
        # El dot reacciona a lo que hace una persona: celebra lo que se da por bueno y se
        # apena con lo que se devuelve. Se apunta antes de refrescar, que es quien lo pinta.
        presencia_dot = getattr(self, "presencia", None)
        if presencia_dot is not None:
            if destino == modelo.HECHA:
                presencia_dot.celebrar(time.monotonic())
            elif tarea.columna == "por-validar":
                presencia_dot.fallar(actual.id, destino, time.monotonic())
        self.retirar_worktree(actual, destino)
        self.comprobaciones.pop(tarea.id, None)
        self.app.refrescar()
        if plan is not None:
            # En un proyecto creado desde el Inicio aprobar ya integra, sin enseñar ramas
            # (cotejo-00fwc2); en los de quien programa, se ofrece como siempre.
            if plan.get("del_inicio"):
                self.integrar_sola(proyecto, actual, plan)
            else:
                self.ofrecer_integrar(actual, plan)
        return True

    def retirar_worktree(self, tarea, destino):
        """Aprobada o devuelta a Pendiente, su worktree de despacho sobra (B3), salvo si la
        lanzó el board: devuelta a Pendiente está pausada y se retoma ahí (cotejo-z7ma7r).

        La rama se queda —es lo que se integra, o sobre lo que trabaja quien la retome— y lo
        que tenga sin commitear también: `retirar` se niega, y aquí solo se avisa.
        """
        if destino not in (modelo.HECHA, modelo.PENDIENTE):
            return
        # Pausada (la lanzó el board y volvió a Pendiente): su worktree es de donde retoma el
        # agente siguiente, y se queda.
        if destino == modelo.PENDIENTE and self.es_pausable(tarea):
            return
        resultado = worktrees.retirar(tarea.id)
        if resultado.get("registrado") and not resultado.get("retirado"):
            self.aviso(f"Su worktree se queda: {resultado.get('motivo', 'no pude retirarlo')}")

    def desmarcar(self, tarea):
        try:
            self.fuente.marcar(tarea, hecha=False)
        except (modelo.TareaCambiada, OSError):
            self.aviso("No pude deshacer: la tarea cambió mientras tanto")

    def preguntar_motivo(self, proyecto, tarea, destino):
        """Devolver una tarea sin decir por qué deja al agente donde estaba."""
        dialogo = Adw.AlertDialog(heading="¿Por qué la devuelves?", body=tarea.texto)
        entrada = Gtk.Entry(placeholder_text="Qué falta o qué está mal", activates_default=True)
        dialogo.set_extra_child(entrada)
        dialogo.add_response("cancelar", "Cancelar")
        dialogo.add_response("devolver", f"Devolver a {dict(modelo.COLUMNAS)[destino]}")
        dialogo.set_response_appearance("devolver", Adw.ResponseAppearance.DESTRUCTIVE)
        dialogo.set_default_response("devolver")
        dialogo.set_close_response("cancelar")
        # Sin motivo no hay devolución: el botón no se enciende hasta que haya algo escrito.
        dialogo.set_response_enabled("devolver", False)
        entrada.connect("changed", lambda e: dialogo.set_response_enabled(
            "devolver", bool(e.get_text().strip())))
        dialogo.connect("response", self.al_responder_motivo, entrada, proyecto, tarea, destino)
        dialogo.present(self)
        entrada.grab_focus()

    def al_responder_motivo(self, _dialogo, respuesta, entrada, proyecto, tarea, destino):
        motivo = entrada.get_text().strip()
        if respuesta != "devolver" or not motivo:
            return
        # De Para comprobar a Haciendo, si la lanzó el board, va otro agente con lo que se
        # pidió cambiar (cotejo-o253bs, `lanzar.py`); si no, se mueve como siempre.
        if destino == "en-curso" and self.relanzar_al_rechazar(proyecto, tarea, motivo):
            return
        self.escribir_movimiento(proyecto, tarea, destino, motivo)

    def al_mover(self, proyecto, tarea, destino, popover):
        popover.popdown()
        self.mover(proyecto, tarea, destino)

    def al_asignar(self, proyecto, tarea, agente, popover):
        popover.popdown()
        try:
            actual = self.fuente.poner_agente(tarea, agente)
            self.foco_tras_pintar = actual.id
            bitacora.anotar("asignar", proyecto, actual, de=tarea.agente, a=agente)
        except (modelo.TareaCambiada, OSError) as error:
            self.aviso(f"No pude asignarla: cambió en {error}")
        self.app.refrescar()

    def al_ver(self, _proyecto, _tarea, datos, popover):
        """La anotación entera, seleccionable: de una evidencia se copia el commit o el comando."""
        popover.popdown()
        titulo, texto = datos
        dialogo = Adw.AlertDialog(heading=titulo)
        etiqueta = Gtk.Label(label=texto, xalign=0, yalign=0, wrap=True, selectable=True,
                             css_classes=["anotacion-texto"])
        dialogo.set_extra_child(Gtk.ScrolledWindow(
            child=etiqueta, propagate_natural_height=True, max_content_height=px(420),
            hscrollbar_policy=Gtk.PolicyType.NEVER))
        dialogo.add_response("cerrar", "Cerrar")
        dialogo.present(self)
        # Una etiqueta seleccionable se abre con todo el texto resaltado, como si ya lo
        # hubieras marcado tú. Se puede copiar igual, pero no empieza gritando.
        etiqueta.select_region(0, 0)
