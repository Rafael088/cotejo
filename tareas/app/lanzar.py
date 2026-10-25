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

**Pausar y retomar** (cotejo-z7ma7r). Devolver a mano a Pendiente una tarea que lanzó el board la
pausa (`pausar_al_mover`): su agente se para y el worktree, la rama y el modelo se quedan (no se
retira el worktree). Su ficha en Pendiente lo dice («Pausada»). Pasarla otra vez a Haciendo
vuelve por `lanzar_al_mover`, que lanza un agente nuevo con la nota de retomar
(`tareas/retomar.py`), y su «Lo que hace el agente» dice que es una reanudación.

**El fin y el rechazo** (cotejo-o253bs). Cuando el agente vuelve, `despacho_board` le hace el
fin y aquí solo se avisa (`agente_terminado`): entregó y está en Para comprobar, donde su ficha
y su revisión guardan sus mensajes; o terminó sin entregar y volvió a Pendiente, pausada, con el
motivo. Devolver de Para comprobar a Haciendo con motivo (`relanzar_al_rechazar`) lanza un
agente nuevo en el mismo worktree con lo que se pidió cambiar.
"""

from gi.repository import Adw, GLib, Gtk, Pango

from .. import bitacora, lanzados, modelo, retomar, senal_vida
from .comun import ESPACIADO_SM, ESPACIADO_XS, animaciones_activas, id_corto
from .escala import px
from .piezas import icono

SEGUNDOS = 1
EN_CURSO = "en-curso"
POR_COMPROBAR = "por-validar"


class EnVivo(Gtk.Box):
    """«Lo que hace el agente» en la ficha: la situación y los mensajes, al día cada segundo
    mientras se ve."""

    __gtype_name__ = "CotejoAgenteEnVivo"

    def __init__(self, tarea_id):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS))
        self.id = tarea_id
        self.seguimiento = lanzados.Seguimiento(tarea_id)
        self.temporizador = 0
        self.refrescos = 0            # las pruebas lo miran
        self.vacio = True
        cabeza = Gtk.Box(spacing=px(ESPACIADO_XS))
        cabeza.append(icono("agente", 12))
        cabeza.append(Gtk.Label(label="LO QUE HACE EL AGENTE", xalign=0,
                                css_classes=["detalle-clave"]))
        self.append(cabeza)
        # La señal de vida (cotejo-21y2ah): un punto que late, cuánto lleva y cuánto hace que
        # se movió y qué está haciendo; si el proceso murió, «Retomar». Ver `senal_vida.py`.
        self.vida_punto = Gtk.Label(label="●", css_classes=["vida-punto"], valign=Gtk.Align.START)
        self.vida_titulo = Gtk.Label(xalign=0, hexpand=True, css_classes=["detalle-valor"])
        self.vida_detalle = Gtk.Label(xalign=0, css_classes=["detalle-tenue"])
        self.vida_ayuda = Gtk.Label(xalign=0, wrap=True, visible=False,
                                    wrap_mode=Pango.WrapMode.WORD_CHAR,
                                    ellipsize=Pango.EllipsizeMode.END, lines=2,
                                    css_classes=["vida-ayuda"])
        self.al_retomar = None        # lo pone la ficha: lanza un agente nuevo que retoma
        self.vida_retomar = Gtk.Button(label="Retomar", visible=False, halign=Gtk.Align.START,
                                       css_classes=["suggested-action", "pill"])
        self.vida_retomar.connect("clicked", self.al_pulsar_retomar)
        textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS),
                         hexpand=True)
        textos.append(self.vida_titulo)
        textos.append(self.vida_detalle)
        textos.append(self.vida_ayuda)
        textos.append(self.vida_retomar)
        self.vida = Gtk.Box(spacing=px(ESPACIADO_SM), visible=False, css_classes=["vida"])
        self.vida.append(self.vida_punto)
        self.vida.append(textos)
        self.append(self.vida)
        self.nivel_vida = None
        self.situacion = Gtk.Label(xalign=0, wrap=True, css_classes=["detalle-valor"],
                                   wrap_mode=Pango.WrapMode.WORD_CHAR)
        self.append(self.situacion)
        # Una reanudación (cotejo-z7ma7r) lo dice debajo: de quién retoma y con qué.
        self.reanudacion = Gtk.Label(xalign=0, wrap=True, visible=False,
                                     css_classes=["detalle-tenue"],
                                     wrap_mode=Pango.WrapMode.WORD_CHAR)
        self.append(self.reanudacion)
        self.registro = Gtk.TextView(editable=False, cursor_visible=False, monospace=True,
                                     wrap_mode=Gtk.WrapMode.WORD_CHAR,
                                     css_classes=["entrevista-texto"])
        self.marco = Gtk.ScrolledWindow(child=self.registro, min_content_height=px(140),
                                        max_content_height=px(260),
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
        dice = retomar.resumen((registro or {}).get("reanudacion"))
        self.reanudacion.set_label(dice)
        self.reanudacion.set_visible(bool(dice))
        self.pintar_vida(registro)
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

    def al_pulsar_retomar(self, *_):
        if self.al_retomar is not None:
            self.al_retomar()

    def pintar_vida(self, registro):
        """Pone la señal de vida. El latido es una clase que alterna en cada tic y solo si las
        animaciones del sistema están activas; si no, el punto se queda fijo."""
        senal = senal_vida.evaluar(registro) if registro else None
        self.vida.set_visible(senal is not None)
        if senal is None:
            self.nivel_vida = None
            return
        if senal["nivel"] != self.nivel_vida:
            if self.nivel_vida:
                self.vida.remove_css_class(self.nivel_vida)
            self.vida.add_css_class(senal["nivel"])
            self.nivel_vida = senal["nivel"]
        self.vida_titulo.set_label(senal["titulo"])
        self.vida_detalle.set_label(senal["detalle"])
        self.vida_ayuda.set_label(senal["hace"])
        self.vida_ayuda.set_visible(bool(senal["hace"]))
        self.vida_retomar.set_visible(senal["retomar"] and self.al_retomar is not None)
        if senal["animar"] and animaciones_activas():
            if self.vida_punto.has_css_class("late"):
                self.vida_punto.remove_css_class("late")
            else:
                self.vida_punto.add_css_class("late")
        else:
            self.vida_punto.remove_css_class("late")

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

    # --- pausar: Haciendo → Pendiente a mano (cotejo-z7ma7r) --------------------------------

    @staticmethod
    def es_pausable(tarea):
        """¿La lanzó el board alguna vez? Entonces devolverla a Pendiente la pausa."""
        return retomar.es_retomable(lanzados.leer(tarea.id))

    def pausar_al_mover(self, tarea):
        """Para su agente y deja el worktree, la rama y el modelo para retomarla. Devuelve el
        estado, o None si no la lanzó el board (y se mueve como siempre)."""
        if not self.es_pausable(tarea):
            return None
        from enrutador import despacho_board as db
        estado = db.pausar(tarea.id)
        if estado:
            self.aviso(f"Pausé a {estado.get('modelo') or 'su agente'}: su worktree y su rama "
                       f"se quedan. Pásala a Haciendo y otro agente la retoma donde quedó.")
        return estado

    def retomar_la_caida(self, proyecto, tarea):
        """«Retomar» de un agente que se cerró sin entregar: la tarea sigue en Haciendo a su
        nombre, así que primero se anota parada y vuelve a Pendiente (como hace el fin, o
        `recoger` al refrescar) y de ahí se lanza otro agente nuevo con la nota de retomar,
        el camino de siempre (`lanzar_al_mover`). Si no hay hueco, queda en Pendiente, pausada,
        y se vuelve a pasar a Haciendo cuando lo haya."""
        from enrutador import despacho_board as db
        try:
            db.pausar(tarea.id, "se cerró sin entregar")
            actual = self.fuente.poner_estado(tarea, modelo.PENDIENTE)
        except (modelo.TareaCambiada, OSError) as error:
            self.aviso(f"No pude retomarla: cambió en {error}")
            self.app.refrescar()
            return
        bitacora.anotar("mover", proyecto, actual, de=tarea.columna, a=modelo.PENDIENTE)
        if not self.lanzar_al_mover(proyecto, actual):
            self.app.refrescar()

    def seccion_pausada(self, tarea):
        """En la ficha de una tarea pausada (en Pendiente, con un agente anterior): qué queda y
        qué pasa al moverla. None si no lo está."""
        if tarea.columna != modelo.PENDIENTE:
            return None
        registro = lanzados.leer(tarea.id)
        if not retomar.es_retomable(registro) or registro.get("fase") == lanzados.EN_ESPERA:
            return None
        quien = registro.get("modelo") or "su agente"
        rama = (registro.get("worktree") or {}).get("rama")
        texto = (f"Se paró a {quien}" + (f" ({retomar.motivo_de(registro)})"
                                          if retomar.motivo_de(registro) else "") + ". "
                 + (f"Su worktree y la rama {rama} siguen ahí. " if rama else "")
                 + "Al pasarla a Haciendo se lanza un agente nuevo que retoma donde quedó, con "
                   "una nota de sus commits, lo que dejó sin commitear y lo último que dijo.")
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=ESPACIADO_XS,
                       css_classes=["anotacion", "detenida"])
        cabeza = Gtk.Box(spacing=ESPACIADO_XS)
        cabeza.append(icono("aviso", 12))
        cabeza.append(Gtk.Label(label="PAUSADA", xalign=0, css_classes=["anotacion-titulo"]))
        caja.append(cabeza)
        caja.append(Gtk.Label(label=texto, xalign=0, wrap=True, selectable=True,
                              focusable=False, wrap_mode=Pango.WrapMode.WORD_CHAR,
                              css_classes=["anotacion-texto"]))
        caja.set_margin_top(ESPACIADO_SM)
        return caja

    # --- el rechazo: Para comprobar → Haciendo con motivo (cotejo-o253bs) ---------------------

    def relanzar_al_rechazar(self, proyecto, tarea, motivo):
        """Devuelta a Haciendo con motivo: se mueve (con el «rechazar» de siempre) y se lanza
        un agente nuevo en su worktree con el encargo, la entrega anterior y lo que se pidió
        cambiar. Vale también si la entregó otro camino (`despachar`, un agente a mano) con tal
        de que esté asignada a un agente (cotejo-2sxw7p). False si es de una persona o no tiene
        agente (y se mueve como siempre)."""
        from enrutador import despacho_board as db
        try:
            estado = db.rechazar(
                tarea.id, motivo,
                lambda: self.escribir_movimiento(proyecto, tarea, EN_CURSO, motivo),
                al_terminar=lambda e: GLib.idle_add(self.agente_terminado, e))
        except db.NoSePuede as error:
            self.aviso(f"No lancé otro agente: {error}")
            self.app.refrescar()
            return True
        if estado is None:
            return False
        self.foco_tras_pintar = tarea.id
        self.aviso(f"{estado.get('modelo') or 'Otro agente'} la retoma con lo que pediste "
                   f"cambiar, en el mismo worktree")
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
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS),
                       css_classes=["anotacion", "detenida"])
        cabeza = Gtk.Box(spacing=px(ESPACIADO_XS))
        cabeza.append(icono("aviso", 12))
        cabeza.append(Gtk.Label(label="EN ESPERA", xalign=0, css_classes=["anotacion-titulo"]))
        caja.append(cabeza)
        caja.append(Gtk.Label(label=motivo, xalign=0, wrap=True, selectable=True,
                              focusable=False, wrap_mode=Pango.WrapMode.WORD_CHAR,
                              css_classes=["anotacion-texto"]))
        caja.set_margin_top(px(ESPACIADO_SM))
        return caja

    def seccion_en_vivo(self, tarea):
        """«Lo que hace el agente», si la lanzó el board y está en Haciendo o, ya entregada, en
        Para comprobar (sus mensajes se guardan, cotejo-o253bs); si no, None."""
        if (tarea.columna not in (EN_CURSO, POR_COMPROBAR)
                or not retomar.es_retomable(lanzados.leer(tarea.id))):
            return None
        return EnVivo(tarea.id)
