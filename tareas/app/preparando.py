"""La pantalla Preparando del board (v1.3.0, cotejo-hiifrz): qué hace el agente con el proyecto.

Los cinco pasos con su estado y su tiempo, el reloj, el registro desplegable, el error con
«Reintentar» y «Abrir en terminal», y «Revisar el plan» al terminar. Es una página más de la
pila (`"preparando"`, sin botón en el selector, como la entrevista). Aquí solo se pinta: lo que
se enseña lo decide `tareas/preparando.py` (sin GTK) con `tareas/progreso.py` y
`tareas/preparacion.py`; las acciones son de `enrutador/preparar.py`.

**El reloj** es un `GLib.timeout_add_seconds(1)` que existe solo mientras la pantalla se ve:
nace en `do_map` y se quita en `do_unmap` (como el reloj de la constelación). No hay hilos que
toquen GTK: el hilo que espera al agente solo avisa con `GLib.idle_add` (`preparacion_terminada`).

«Revisar el plan» llama a `revisar_plan(estado)` de `Board`, con el dict de `preparacion.estado`
(id, proyecto, carpeta, cliente…): la pantalla de `tareas/app/revisar_plan.py` (cotejo-m195bn).
"""

from gi.repository import GLib, Gtk

from .. import preparando
from .comun import ESPACIADO_LG, ESPACIADO_MD, ESPACIADO_SM, ESPACIADO_XL, ESPACIADO_XS
from .piezas import con_mano, etiquetar

PREPARANDO = "preparando"
SEGUNDOS = 1


class PantallaPreparando(Gtk.ScrolledWindow):
    """La página: se pinta con `pintar(vista)` y, mientras se ve, pide un refresco por segundo."""

    __gtype_name__ = "CotejoPantallaPreparando"

    def __init__(self, al_refrescar, **kwargs):
        super().__init__(hexpand=True, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER,
                         css_classes=["inicio"], **kwargs)
        self._al_refrescar = al_refrescar
        self.temporizador = 0
        self.refrescos = 0            # las pruebas lo miran
        self.filas = []
        self.vista = None

        cuerpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=ESPACIADO_LG,
                         margin_top=ESPACIADO_XL * 2, margin_bottom=ESPACIADO_XL * 2,
                         margin_start=ESPACIADO_XL * 2, margin_end=ESPACIADO_XL * 2)
        self.ruta = Gtk.Label(label="Inicio", xalign=0, css_classes=["dato"])
        self.eyebrow = Gtk.Label(xalign=0, css_classes=["dato"])
        self.titulo = Gtk.Label(xalign=0, wrap=True, css_classes=["inicio-titular"])
        self.reloj = Gtk.Label(xalign=0, css_classes=["dato"])
        for w in (self.ruta, self.eyebrow, self.titulo, self.reloj):
            cuerpo.append(w)

        self.lista = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=ESPACIADO_MD)
        cuerpo.append(self.lista)

        self.mensaje = Gtk.Label(xalign=0, wrap=True, visible=False, css_classes=["preparando-error"])
        cuerpo.append(self.mensaje)

        self.registro = Gtk.TextView(editable=False, cursor_visible=False, monospace=True,
                                     wrap_mode=Gtk.WrapMode.WORD_CHAR,
                                     css_classes=["entrevista-texto"])
        marco = Gtk.ScrolledWindow(child=self.registro, min_content_height=140,
                                   max_content_height=260,
                                   hscrollbar_policy=Gtk.PolicyType.NEVER,
                                   css_classes=["entrevista-marco"])
        self.ver_registro = Gtk.Expander(label="Ver lo que hace el agente", child=marco)
        cuerpo.append(self.ver_registro)

        pie = Gtk.Box(spacing=ESPACIADO_SM, halign=Gtk.Align.END)
        self.boton_inicio = con_mano(Gtk.Button(label="Volver al Inicio"))
        self.reintentar = con_mano(Gtk.Button(label="Reintentar", visible=False))
        self.en_terminal = con_mano(Gtk.Button(label="Abrir en terminal", visible=False))
        self.revisar = con_mano(Gtk.Button(label="Revisar el plan", visible=False,
                                           css_classes=["suggested-action"]))
        for b in (self.boton_inicio, self.reintentar, self.en_terminal, self.revisar):
            etiquetar(b, b.get_label())
            pie.append(b)
        cuerpo.append(pie)

        ancho = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, halign=Gtk.Align.CENTER)
        ancho.set_size_request(640, -1)
        ancho.append(cuerpo)
        self.set_child(ancho)

    # --- pintar ---------------------------------------------------------------------------------

    def pintar(self, v):
        """Pone una `preparando.Vista`. Las filas de pasos se crean una vez y se actualizan."""
        self.vista = v
        self.ruta.set_label(f"Inicio  ›  {v.proyecto}" if v.proyecto else "Inicio")
        self.eyebrow.set_label(v.eyebrow)
        self.titulo.set_label(v.titulo)
        self.reloj.set_label(v.reloj)
        while len(self.filas) < len(v.pasos):
            self.filas.append(self._fila())
        for fila, paso in zip(self.filas, v.pasos):
            simbolo, nombre, detalle, tiempo = fila
            simbolo.set_label(paso["simbolo"])
            nombre.set_label(paso["titulo"])
            detalle.set_label(paso["detalle"])
            tiempo.set_label(paso["tiempo"])
            for w in (simbolo, nombre):
                for clase in ("paso-pendiente", "paso-en-curso", "paso-hecho", "paso-fallo"):
                    w.remove_css_class(clase)
                w.add_css_class("paso-" + paso["estado"].replace(" ", "-"))
            etiquetar(nombre, f"{paso['titulo']}: {paso['estado']}")
        self.mensaje.set_label(v.mensaje)
        self.mensaje.set_visible(bool(v.mensaje))
        self.reintentar.set_visible("reintentar" in v.acciones)
        self.en_terminal.set_visible("abrir_en_terminal" in v.acciones)
        self.revisar.set_visible(v.puede_revisar)
        buffer = self.registro.get_buffer()
        if buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False) != v.registro:
            buffer.set_text(v.registro)

    def _fila(self):
        caja = Gtk.Box(spacing=ESPACIADO_MD)
        simbolo = Gtk.Label(width_chars=2, css_classes=["preparando-simbolo"])
        textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=ESPACIADO_XS, hexpand=True)
        nombre = Gtk.Label(xalign=0, wrap=True, css_classes=["carta-nombre"])
        detalle = Gtk.Label(xalign=0, wrap=True, css_classes=["carta-descripcion"])
        textos.append(nombre)
        textos.append(detalle)
        tiempo = Gtk.Label(xalign=1, css_classes=["dato"], valign=Gtk.Align.START)
        caja.append(simbolo)
        caja.append(textos)
        caja.append(tiempo)
        self.lista.append(caja)
        return simbolo, nombre, detalle, tiempo

    # --- el reloj: existe solo mientras la pantalla se ve ---------------------------------------

    def _tic(self):
        self.refrescos += 1
        self._al_refrescar()
        return GLib.SOURCE_CONTINUE

    def hay_reloj(self):
        return bool(self.temporizador)

    def do_map(self):
        Gtk.ScrolledWindow.do_map(self)
        if not self.temporizador:
            self.temporizador = GLib.timeout_add_seconds(SEGUNDOS, self._tic)
        self._al_refrescar()

    def do_unmap(self):
        if self.temporizador:
            GLib.source_remove(self.temporizador)
            self.temporizador = 0
        Gtk.ScrolledWindow.do_unmap(self)


class PestanaPreparando:
    """Los métodos de `Board` que llevan la pantalla (y los enganches de la entrevista)."""

    def crear_preparando(self):
        self.preparando_seguimiento = None
        self.pantalla_preparando = PantallaPreparando(self.refrescar_preparando)
        p = self.pantalla_preparando
        p.boton_inicio.connect("clicked", lambda *_: self.ver_pestana("inicio"))
        p.reintentar.connect("clicked", lambda *_: self.reintentar_preparacion())
        p.en_terminal.connect("clicked", lambda *_: self.abrir_preparacion_en_terminal())
        p.revisar.connect("clicked", lambda *_: self.revisar_plan(self.estado_preparando()))
        return p

    # --- enganches con la entrevista ------------------------------------------------------------

    def mostrar_preparando(self, estado):
        """Recibe lo que devolvió `preparar.lanzar` y enseña la pantalla."""
        self.preparando_seguimiento = preparando.Preparando(estado["id"])
        self.refrescar_preparando()
        self.ver_pestana(PREPARANDO)

    def preparacion_terminada(self, estado):
        """El agente volvió (ya en el hilo de la interfaz). Refresca si es la que se ve; si no,
        avisa."""
        mia = self.preparando_seguimiento is not None and \
            self.preparando_seguimiento.id == (estado or {}).get("id")
        if mia:
            self.refrescar_preparando()
        if not (mia and self.pestana_actual() == PREPARANDO) and estado:
            self.aviso(f"{estado.get('proyecto', 'El proyecto')}: el agente terminó")
        return GLib.SOURCE_REMOVE

    # --- por dentro -----------------------------------------------------------------------------

    def refrescar_preparando(self):
        if self.preparando_seguimiento is not None:
            self.pantalla_preparando.pintar(self.preparando_seguimiento.refrescar())

    def estado_preparando(self):
        """El `preparacion.estado` de la que se ve, para los enganches."""
        from enrutador import preparar
        try:
            return preparar.estado(self.preparando_seguimiento.id)
        except preparar.NoSePuede:
            return {"id": self.preparando_seguimiento.id,
                    "proyecto": (self.pantalla_preparando.vista or preparando.Vista()).proyecto}

    def reintentar_preparacion(self):
        from enrutador import preparar
        try:
            preparar.reintentar(self.preparando_seguimiento.id,
                                al_terminar=lambda e: GLib.idle_add(self.preparacion_terminada, e))
        except preparar.NoSePuede as error:
            self.aviso(str(error))
            return
        self.refrescar_preparando()

    def abrir_preparacion_en_terminal(self):
        from enrutador import preparar
        try:
            preparar.abrir_en_terminal(self.preparando_seguimiento.id)
        except preparar.NoSePuede as error:
            self.aviso(str(error))
            return
        self.refrescar_preparando()
