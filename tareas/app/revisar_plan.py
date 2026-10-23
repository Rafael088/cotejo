"""La pantalla «Revisar el plan» del board (v1.3.0, cotejo-m195bn): el final del inicio.

Objetivo y siguiente paso, las decisiones propuestas con **Aceptar** y **Cambiar**, las tareas de
la 0.1.0 con las de la persona marcadas «tú», y **Empezar la 0.1.0**. Es una página más de la
pila (`"plan"`, sin botón en el selector, como la entrevista y Preparando). Aquí solo se pinta:
qué se enseña y qué hace cada botón está en `tareas/revisar_plan.py`, sin GTK.

- **Aceptar** es `decision.aceptar`, el mismo de la carta de *Para comprobar*: solo lo pide la
  persona, desde un botón; no hay verbo para ello.
- **Cambiar** abre un campo para el motivo, que es obligatorio (el botón no se activa vacío):
  la decisión queda `rechazada` y el agente se relanza con ese motivo
  (`enrutador.preparar.rehacer`); la pantalla vuelve a Preparando.
- **Empezar la 0.1.0** reparte como `cotejo plan` (asigna, no lanza) y abre el mapa del
  proyecto (`abrir_proyecto`, cotejo-p86sa9); **Ver el mapa del proyecto** lo abre sin repartir.
  Las dos pasan la carpeta: un proyecto recién preparado vive en la fuente repo, no en la activa.
"""

from gi.repository import GLib, Gtk

from .. import almacen, decision, revisar_plan
from .comun import ESPACIADO_LG, ESPACIADO_MD, ESPACIADO_SM, ESPACIADO_XL, ESPACIADO_XS
from .piezas import chip, con_mano, etiquetar, vaciar

PLAN = "plan"


def _bloque(*hijos):
    caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=ESPACIADO_SM,
                   css_classes=["carta", "plan-bloque"])
    for hijo in hijos:
        caja.append(hijo)
    return caja


class FilaDecision(Gtk.Box):
    """Una decisión: título, texto y, si sigue propuesta, Aceptar y Cambiar (con su motivo)."""

    __gtype_name__ = "CotejoFilaDecision"

    def __init__(self, datos, al_aceptar, al_rechazar):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=ESPACIADO_XS,
                         css_classes=["plan-decision"])
        self.datos = datos
        fila = Gtk.Box(spacing=ESPACIADO_MD)
        textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=ESPACIADO_XS,
                         hexpand=True)
        self.titulo = Gtk.Label(label=datos["titulo"], xalign=0, wrap=True,
                                css_classes=["carta-nombre"])
        textos.append(self.titulo)
        resumen = revisar_plan.resumen_decision(datos)
        if resumen:
            textos.append(Gtk.Label(label=resumen, xalign=0, wrap=True,
                                    css_classes=["carta-descripcion"]))
        fila.append(textos)
        self.aceptar = self.cambiar = None
        self.motivo = self.enviar = None
        estado = datos["estado"]
        if estado == "propuesta":
            acciones = Gtk.Box(spacing=ESPACIADO_XS, valign=Gtk.Align.START)
            self.cambiar = con_mano(Gtk.Button(label="Cambiar"))
            self.aceptar = con_mano(Gtk.Button(label="Aceptar", css_classes=["suggested-action"]))
            etiquetar(self.cambiar, f"Cambiar la decisión «{datos['titulo']}»")
            etiquetar(self.aceptar, f"Aceptar la decisión «{datos['titulo']}»")
            acciones.append(self.cambiar)
            acciones.append(self.aceptar)
            fila.append(acciones)
            self.aceptar.connect("clicked", lambda *_: al_aceptar(datos))
            self.cambiar.connect("clicked", lambda *_: self.pedir_motivo())
        else:
            texto = "Aceptada" if estado == "aceptada" else "Rechazada"
            fila.append(chip(texto, "", tooltip=datos.get("motivo") or ""))
        self.append(fila)

        if estado == "propuesta":
            self.caja_motivo = Gtk.Box(spacing=ESPACIADO_XS, visible=False)
            self.motivo = Gtk.Entry(
                hexpand=True, placeholder_text="Por qué no: tu agente lo leerá para proponer otra")
            etiquetar(self.motivo, "Motivo para cambiar la decisión")
            self.enviar = con_mano(Gtk.Button(label="Pedir otra", sensitive=False))
            self.motivo.connect("changed", self._al_escribir)
            self.motivo.connect("activate", lambda *_: self._enviar(al_rechazar))
            self.enviar.connect("clicked", lambda *_: self._enviar(al_rechazar))
            self.caja_motivo.append(self.motivo)
            self.caja_motivo.append(self.enviar)
            self.append(self.caja_motivo)

    def pedir_motivo(self):
        self.caja_motivo.set_visible(True)
        self.motivo.grab_focus()

    def _al_escribir(self, *_):
        self.enviar.set_sensitive(bool(self.motivo.get_text().strip()))

    def _enviar(self, al_rechazar):
        motivo = self.motivo.get_text().strip()
        if motivo:      # devolver exige motivo: vacío, ni se intenta
            al_rechazar(self.datos, motivo)


class PantallaRevisarPlan(Gtk.ScrolledWindow):
    """La página: se pinta con `pintar(plan)`."""

    __gtype_name__ = "CotejoPantallaRevisarPlan"

    def __init__(self, **kwargs):
        super().__init__(hexpand=True, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER,
                         css_classes=["inicio"], **kwargs)
        self.plan = None
        self.filas_decision = []
        self.filas_tarea = []
        cuerpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=ESPACIADO_LG,
                         margin_top=ESPACIADO_XL * 2, margin_bottom=ESPACIADO_XL * 2,
                         margin_start=ESPACIADO_XL * 2, margin_end=ESPACIADO_XL * 2)
        self.ruta = Gtk.Label(xalign=0, css_classes=["dato"])
        cuerpo.append(self.ruta)

        self.objetivo = Gtk.Label(xalign=0, wrap=True, css_classes=["inicio-titular"])
        self.siguiente = Gtk.Label(xalign=0, wrap=True, css_classes=["carta-descripcion"])
        cuerpo.append(_bloque(Gtk.Label(label="EL OBJETIVO", xalign=0, css_classes=["dato"]),
                              self.objetivo, self.siguiente))

        cabeza = Gtk.Box(spacing=ESPACIADO_SM)
        self.cabecera_decisiones = Gtk.Label(xalign=0, hexpand=True, wrap=True,
                                             css_classes=["carta-nombre"])
        cabeza.append(self.cabecera_decisiones)
        self.cuenta = Gtk.Box()
        cabeza.append(self.cuenta)
        self.lista_decisiones = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                        spacing=ESPACIADO_MD)
        cuerpo.append(_bloque(cabeza, self.lista_decisiones))

        self.lista_tareas = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=ESPACIADO_SM)
        cuerpo.append(_bloque(Gtk.Label(label="Tareas de la 0.1.0", xalign=0,
                                        css_classes=["carta-nombre"]), self.lista_tareas))

        self.avisos = Gtk.Label(xalign=0, wrap=True, visible=False,
                                css_classes=["preparando-error"])
        cuerpo.append(self.avisos)

        pie = Gtk.Box(spacing=ESPACIADO_SM, halign=Gtk.Align.END)
        self.boton_inicio = con_mano(Gtk.Button(label="Volver al Inicio"))
        self.ver_mapa = con_mano(Gtk.Button(label="Ver el mapa del proyecto"))
        self.empezar = con_mano(Gtk.Button(label="Empezar la 0.1.0",
                                           css_classes=["suggested-action"]))
        for b in (self.boton_inicio, self.ver_mapa, self.empezar):
            etiquetar(b, b.get_label())
            pie.append(b)
        cuerpo.append(pie)

        ancho = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, halign=Gtk.Align.CENTER)
        ancho.set_size_request(720, -1)
        ancho.append(cuerpo)
        self.set_child(ancho)

    def pintar(self, plan, al_aceptar, al_rechazar):
        self.plan = plan
        self.ruta.set_label(f"{plan.proyecto}  ›  Plan de la 0.1.0")
        self.objetivo.set_label(plan.objetivo or "El agente no dejó escrito el objetivo.")
        self.siguiente.set_label(f"Siguiente paso: {plan.siguiente_paso}"
                                 if plan.siguiente_paso else "")
        self.siguiente.set_visible(bool(plan.siguiente_paso))
        self.cabecera_decisiones.set_label(plan.cabecera_decisiones)
        vaciar(self.cuenta)
        if plan.por_aceptar:
            self.cuenta.append(chip(f"{plan.por_aceptar} por aceptar", "", "verde"))
        vaciar(self.lista_decisiones)
        self.filas_decision = [FilaDecision(d, al_aceptar, al_rechazar)
                               for d in plan.decisiones]
        for fila in self.filas_decision:
            self.lista_decisiones.append(fila)
        vaciar(self.lista_tareas)
        self.filas_tarea = []
        for t in plan.tareas:
            fila = Gtk.Box(spacing=ESPACIADO_MD, css_classes=["plan-tarea"])
            quien = chip(t["quien"], "", *(["chip-tu"] if t["tuya"] else []),
                         tooltip=("Es tuya: ningún modelo la hace" if t["tuya"] else
                                  f"La haría {t['modelo'] or 'un agente'}"))
            fila.append(quien)
            fila.append(Gtk.Label(label=t["texto"], xalign=0, wrap=True, hexpand=True))
            if t["dificultad"]:
                fila.append(Gtk.Label(label=t["dificultad"], css_classes=["dato"]))
            etiquetar(fila, f"{t['texto']}: {'tuya' if t['tuya'] else t['quien']}")
            self.filas_tarea.append((fila, quien, t))
            self.lista_tareas.append(fila)
        if not plan.tareas:
            self.lista_tareas.append(Gtk.Label(label="Todavía no hay tareas de la 0.1.0.",
                                               xalign=0, css_classes=["carta-descripcion"]))
        self.avisos.set_label("\n".join(a if isinstance(a, str) else
                                        f"{a.get('nota', '')}: {a.get('motivo', '')}"
                                        for a in plan.avisos))
        self.avisos.set_visible(bool(plan.avisos))
        self.empezar.set_sensitive(bool(plan.tareas))


class PestanaRevisarPlan:
    """Los métodos de `Board` que llevan la pantalla. `revisar_plan(estado)` es el enganche que
    llama «Revisar el plan» de Preparando."""

    def crear_revisar_plan(self):
        self.plan_estado = None
        self.pantalla_plan = PantallaRevisarPlan()
        p = self.pantalla_plan
        p.boton_inicio.connect("clicked", lambda *_: self.ver_pestana("inicio"))
        p.empezar.connect("clicked", lambda *_: self.empezar_version())
        p.ver_mapa.connect("clicked", lambda *_: self.mapa_del_plan())
        return p

    def mapa_del_plan(self):
        """El mapa del proyecto del plan, con su carpeta (vive en la fuente repo)."""
        estado = self.plan_estado or {}
        self.abrir_proyecto(estado.get("proyecto", ""), estado.get("carpeta") or None)

    def revisar_plan(self, estado):
        """«Revisar el plan» (desde Preparando): la pantalla con el plan de ese proyecto."""
        self.plan_estado = dict(estado or {})
        if not self.plan_estado.get("carpeta"):
            self.aviso("No sé dónde está este proyecto.")
            self.abrir_proyecto(self.plan_estado.get("proyecto", ""))
            return
        self.repintar_plan()
        self.ver_pestana(PLAN)

    def repintar_plan(self):
        self.pantalla_plan.pintar(revisar_plan.leer(self.plan_estado),
                                  self.aceptar_del_plan, self.rechazar_del_plan)

    def aceptar_del_plan(self, datos):
        """Botón de la persona, como el de la vista de revisión de una decisión."""
        try:
            revisar_plan.aceptar(self.plan_estado["carpeta"], datos["id"], datos["version"])
        except (almacen.EntradaNoExiste, almacen.IdRepetido, almacen.EntradaCambiada,
                almacen.NoSeEdita, decision.NoEsDecision, decision.AceptacionParcial) as error:
            self.aviso(str(error))
        else:
            self.aviso(f"«{datos['titulo']}» aceptada")
        self.repintar_plan()

    def rechazar_del_plan(self, datos, motivo):
        """«Cambiar»: rechazada con motivo y el agente, otra vez a trabajar; vuelve Preparando."""
        from enrutador import preparar
        try:
            estado = revisar_plan.rechazar(
                self.plan_estado, datos["id"], datos["version"], motivo,
                al_terminar=lambda e: GLib.idle_add(self.preparacion_terminada, e))
        except (almacen.EntradaNoExiste, almacen.IdRepetido, almacen.EntradaCambiada,
                almacen.NoSeEdita, decision.NoEsDecision, ValueError) as error:
            self.aviso(str(error))
            self.repintar_plan()
            return
        except preparar.NoSePuede as error:
            # La decisión ya quedó rechazada (lo dijo la persona); lo que falló es relanzar.
            self.aviso(f"Quedó rechazada, pero no pude relanzar al agente: {error}")
            self.repintar_plan()
            return
        self.mostrar_preparando(estado)

    def empezar_version(self):
        """«Empezar la 0.1.0»: reparte como `cotejo plan` y abre el mapa del proyecto."""
        from .. import cli
        try:
            asignadas = revisar_plan.empezar(self.plan_estado)
        except cli.ErrorCLI as error:
            self.aviso(str(error))
            return
        if asignadas:
            self.aviso(f"{len(asignadas)} tareas repartidas; nada se lanzó todavía"
                       if len(asignadas) != 1 else "1 tarea repartida; nada se lanzó todavía")
        self.app.refrescar()
        self.mapa_del_plan()
