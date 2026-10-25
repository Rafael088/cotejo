"""Lo de arriba de la revisión para quien no programa: el resumen, las pruebas y qué hacer."""

from gi.repository import Gtk

from .. import modelo, revision
from .comun import ESPACIADO_MD, ESPACIADO_SM, ESPACIADO_XS
from .escala import px
from .piezas import con_mano


class Resumen:
    """Se pinta solo si la entrega trae `--resumen`; sin él la revisión queda como estaba."""

    def bloque_resumen(self, proyecto, tarea, entrega, texto, dialogo):
        """Resumen tal cual lo escribió el agente, una frase de pruebas y los dos caminos."""
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_MD),
                       css_classes=["revision-resumen"])
        caja.append(self.titulo_seccion("QUÉ CAMBIÓ Y CÓMO PROBARLO"))
        caja.append(Gtk.Label(label=texto, xalign=0, wrap=True, selectable=False,
                              css_classes=["revision-explicacion"]))
        caja.append(self.titulo_seccion("LAS PRUEBAS"))
        caja.append(Gtk.Label(label=revision.frase_pruebas(entrega), xalign=0, wrap=True,
                              css_classes=["revision-explicacion"]))
        caja.append(self.titulo_seccion("QUÉ HACER"))
        caja.append(Gtk.Label(
            label="Pruébalo como dice arriba. Si está bien, apruébalo; si no, devuélvelo "
                  "y cuéntale al agente qué falta.",
            xalign=0, wrap=True, css_classes=["revision-dato"]))
        botones = Gtk.Box(spacing=px(ESPACIADO_SM), margin_top=px(ESPACIADO_XS))

        def aprobar(*_):
            dialogo.close()
            self.mover(proyecto, tarea, modelo.HECHA)

        def devolver(*_):
            dialogo.close()
            self.mover(proyecto, tarea, "en-curso")   # pregunta el motivo antes de escribir

        for texto_boton, clase, accion in (("Aprobar", "suggested-action", aprobar),
                                           ("Devolver y decir por qué", "flat", devolver)):
            boton = Gtk.Button(child=self.con_icono(
                "estado-hecha" if clase != "flat" else "flecha-izquierda", texto_boton),
                css_classes=[clase])
            boton.connect("clicked", accion)
            botones.append(con_mano(boton))
        caja.append(botones)
        return caja
