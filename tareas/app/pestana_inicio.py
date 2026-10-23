"""La pestaña Inicio (v1.3.0): lo primero que se ve al abrir el board, antes que el tablero.

Saludo, una frase con cuántos proyectos hay y cuántas entregas esperan, una tarjeta por
proyecto (versión, avance en piezas de su arquitectura) y «Nuevo proyecto». Qué se enseña lo
decide `tareas/resumen_inicio.py`, sin GTK; aquí solo se pinta.

Es el contenedor de lo que viene en la 1.3.0, y deja los enganches a la vista:

- `area_constelacion`: la caja entre el saludo y las tarjetas. `pintar_inicio` pone ahí la
  constelación de proyectos (cotejo-7wc9hb, `tareas/app/constelacion.py`) con
  `poner_constelacion(widget)`, y la quita si no hay proyectos. Tocar un núcleo es lo mismo
  que tocar su tarjeta: `abrir_proyecto(nombre)`.
- `nuevo_proyecto()`: lo que hace «Nuevo proyecto»: abre la entrevista (cotejo-kf94so,
  `tareas/app/entrevista.py`), una tercera página de la pila sin botón en el selector.
- `abrir_proyecto(nombre)`: lo que hace tocar una tarjeta. De momento, el tablero con ese
  proyecto elegido; el mapa del proyecto (cotejo-p86sa9) lo reemplaza.

Las dos pestañas viven en una `Gtk.Stack` (`self.pestanas`); el selector va en la cabecera.
Con la fuente sin configurar (primer arranque) o rota, se abre en el tablero: ahí está la
tarjeta que explica qué hacer, y un Inicio vacío no diría nada.
"""

import datetime

from gi.repository import Adw, Gtk, Pango

from .. import resumen_inicio
from .comun import ESPACIADO_LG, ESPACIADO_MD, ESPACIADO_SM, ESPACIADO_XL, ESPACIADO_XS
from .comun import animaciones_activas
from .constelacion import caja_constelacion
from .piezas import chip, con_mano, etiquetar, vaciar

INICIO, TABLERO = "inicio", "tablero"
PESTANAS = ((INICIO, "Inicio"), (TABLERO, "Tablero"))
ANCHO_INICIO = 1080      # el contenido no se estira más que esto en una ventana ancha
CAMBIO_PESTANA_MS = 160


class PestanaInicio:
    """Las pestañas Inicio y Tablero, y lo que se pinta en Inicio."""

    def crear_pestanas(self, tablero):
        """La pila con las dos pestañas; `tablero` es lo que antes era todo el contenido."""
        self.pestanas = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE,
                                  transition_duration=CAMBIO_PESTANA_MS, vexpand=True)
        self.pestanas.add_named(self.crear_inicio(), INICIO)
        self.pestanas.add_named(tablero, TABLERO)
        self.pestanas.add_named(self.crear_entrevista(), "entrevista")
        self.inicio_al_dia = False   # se repinta al verse: fuera de vista no se lee nada
        return self.pestanas

    def selector_de_pestanas(self):
        """Inicio | Tablero, en la cabecera. Dos botones de alternar enlazados."""
        caja = Gtk.Box(css_classes=["linked", "pestanas"], valign=Gtk.Align.CENTER)
        self.botones_pestana = {}
        primero = None
        for clave, texto in PESTANAS:
            boton = con_mano(Gtk.ToggleButton(label=texto, css_classes=["pestana"]))
            if primero is None:
                primero = boton
            else:
                boton.set_group(primero)
            boton.connect("toggled", self.al_alternar_pestana, clave)
            # Con la entrevista a la vista «Inicio» sigue activo y no emite `toggled`.
            boton.connect("clicked", self.al_alternar_pestana, clave)
            self.botones_pestana[clave] = boton
            caja.append(boton)
        return caja

    def al_alternar_pestana(self, boton, clave):
        if boton.get_active() and self.pestana_actual() != clave:
            self.ver_pestana(clave)

    def pestana_actual(self):
        return self.pestanas.get_visible_child_name()

    def pestana_inicial(self):
        """Inicio, salvo que no haya de dónde leer: entonces el tablero, con su explicación."""
        return TABLERO if self.fuente.problema else INICIO

    def ver_pestana(self, clave, al_abrir=False):
        """Enseña una pestaña. Lo que solo es del tablero (la banda de proyectos, buscar) se
        esconde en Inicio; el dot entra la primera vez que se ve el tablero. `al_abrir` es la
        primera vez, al crear la ventana: ahí el dot lo hace entrar la app, después del logo."""
        self.pestanas.set_transition_duration(CAMBIO_PESTANA_MS if animaciones_activas() else 0)
        self.pestanas.set_visible_child_name(clave)
        boton = self.botones_pestana.get(clave)
        if boton is not None and not boton.get_active():
            boton.set_active(True)
        en_tablero = clave == TABLERO
        for widget in (self.banda_proyectos, self.buscador):
            widget.set_visible(en_tablero)
        if en_tablero and not al_abrir:
            self.entrar_dot()
        elif not self.inicio_al_dia:
            self.pintar_inicio()

    def tablero_a_la_vista(self):
        return getattr(self, "pestanas", None) is None or self.pestana_actual() == TABLERO

    # --- lo que se pinta ----------------------------------------------------------------------

    def crear_inicio(self):
        cuerpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=ESPACIADO_XL,
                         margin_top=ESPACIADO_XL * 2, margin_bottom=ESPACIADO_XL * 2,
                         margin_start=ESPACIADO_XL * 2, margin_end=ESPACIADO_XL * 2)

        cabeza = Gtk.Box(spacing=ESPACIADO_LG)
        textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=ESPACIADO_XS,
                         hexpand=True, valign=Gtk.Align.END)
        self.inicio_saludo = Gtk.Label(xalign=0, css_classes=["inicio-saludo"])
        self.inicio_titular = Gtk.Label(xalign=0, wrap=True, css_classes=["inicio-titular"])
        textos.append(self.inicio_saludo)
        textos.append(self.inicio_titular)
        cabeza.append(textos)
        nuevo = con_mano(Gtk.Button(label="+  Nuevo proyecto",
                                    valign=Gtk.Align.END, css_classes=["suggested-action"]))
        etiquetar(nuevo, "Nuevo proyecto")
        nuevo.connect("clicked", lambda *_: self.nuevo_proyecto())
        cabeza.append(nuevo)
        cuerpo.append(cabeza)

        # La constelación (cotejo-7wc9hb): oculta mientras no haya proyectos que dibujar.
        self.constelacion = None
        self.area_constelacion = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                         css_classes=["inicio-constelacion"], visible=False)
        cuerpo.append(self.area_constelacion)

        self.inicio_tarjetas = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,
                                           homogeneous=True, min_children_per_line=1,
                                           max_children_per_line=4,
                                           row_spacing=ESPACIADO_MD, column_spacing=ESPACIADO_MD,
                                           valign=Gtk.Align.START)
        cuerpo.append(self.inicio_tarjetas)

        ancho = Adw.Clamp(child=cuerpo, maximum_size=ANCHO_INICIO, tightening_threshold=ANCHO_INICIO)
        return Gtk.ScrolledWindow(child=ancho, hexpand=True, vexpand=True,
                                  hscrollbar_policy=Gtk.PolicyType.NEVER,
                                  css_classes=["inicio"])

    def poner_constelacion(self, widget):
        """Pone `widget` en el hueco de la constelación (o lo vacía y oculta con None)."""
        vaciar(self.area_constelacion)
        if widget is not None:
            self.area_constelacion.append(widget)
        self.area_constelacion.set_visible(widget is not None)

    def pintar_inicio(self, ahora=None):
        """Saludo, titular y tarjetas, con lo que ya leyó la app (no vuelve a escanear)."""
        if self.pestana_actual() != INICIO:
            self.inicio_al_dia = False
            return
        self.inicio_al_dia = True
        hora = (ahora or datetime.datetime.now()).hour
        tarjetas = ([] if self.fuente.problema
                    else resumen_inicio.tarjetas(self.app.proyectos, self.fuente))
        self.inicio_saludo.set_label(resumen_inicio.saludo(hora))
        self.inicio_titular.set_label(resumen_inicio.titular(tarjetas))
        self.pintar_constelacion(tarjetas)
        vaciar(self.inicio_tarjetas)
        for uno in tarjetas:
            self.inicio_tarjetas.append(self.tarjeta_de_proyecto(uno))
        self.inicio_tarjetas.append(self.tarjeta_nuevo())

    def pintar_constelacion(self, tarjetas):
        """La constelación con las mismas tarjetas que se pintan debajo; sin ninguna, nada."""
        if not tarjetas:
            self.constelacion = None
            self.poner_constelacion(None)
            return
        if self.constelacion is None:
            caja, self.constelacion = caja_constelacion(lambda: self.app.colores,
                                                        self.abrir_proyecto)
            self.poner_constelacion(caja)
        self.constelacion.poner(tarjetas)

    def tarjeta_de_proyecto(self, t):
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=ESPACIADO_SM)
        fila = Gtk.Box(spacing=ESPACIADO_SM)
        nombre = Gtk.Label(label=t.nombre, xalign=0, hexpand=True,
                           ellipsize=Pango.EllipsizeMode.END, css_classes=["carta-nombre"])
        fila.append(nombre)
        fila.append(chip(t.texto_estado, "", *(["verde"] if t.por_comprobar else [])))
        caja.append(fila)
        if t.objetivo:
            caja.append(Gtk.Label(label=t.objetivo, xalign=0, wrap=True, lines=2,
                                  ellipsize=Pango.EllipsizeMode.END,
                                  css_classes=["carta-descripcion"]))
        avance = Gtk.ProgressBar(fraction=t.avance or 0, css_classes=["inicio-avance"])
        avance.set_visible(t.con_arquitectura)
        caja.append(avance)
        caja.append(Gtk.Label(label=t.texto_avance, xalign=0, css_classes=["dato"]))
        boton = con_mano(Gtk.Button(child=caja, css_classes=["carta", "inicio-tarjeta"]))
        etiquetar(boton, f"Proyecto {t.nombre}, {t.texto_estado}, {t.texto_avance}")
        boton.connect("clicked", lambda *_: self.abrir_proyecto(t.nombre))
        return boton

    def tarjeta_nuevo(self):
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=ESPACIADO_XS,
                       valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
        caja.append(Gtk.Label(label="+", css_classes=["inicio-mas"]))
        caja.append(Gtk.Label(label="Empezar un proyecto", css_classes=["vacio-titulo"]))
        caja.append(Gtk.Label(label="Contestas unas preguntas y tu agente lo prepara",
                              wrap=True, justify=Gtk.Justification.CENTER,
                              css_classes=["vacio-pista"]))
        boton = con_mano(Gtk.Button(child=caja, css_classes=["carta", "inicio-nuevo"]))
        etiquetar(boton, "Empezar un proyecto")
        boton.connect("clicked", lambda *_: self.nuevo_proyecto())
        return boton

    # --- enganches para las tareas que siguen ---------------------------------------------------

    def abrir_proyecto(self, nombre):
        """Tocar una tarjeta. El mapa del proyecto (cotejo-p86sa9) reemplaza esto; mientras,
        lleva al tablero con ese proyecto elegido."""
        chip_proyecto = getattr(self, "botones_chip", {}).get(nombre)
        if chip_proyecto is not None:
            self.al_elegir_chip(chip_proyecto)
        else:
            self.aviso(f"{nombre} todavía no tiene tareas")
            return
        self.ver_pestana(TABLERO)
