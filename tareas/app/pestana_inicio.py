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
- `abrir_proyecto(nombre)`: lo que hace tocar una tarjeta: el mapa del proyecto
  (cotejo-p86sa9, `tareas/app/mapa.py`), desde el que «Ver el tablero» lleva al tablero.

Las pantallas viven en una `Gtk.Stack` (`self.pestanas`); la cabecera refleja la visible.
Sin fuente configurada (primer arranque) se abre en «Revisar el equipo» (`tareas/app/equipo.py`,
cotejo-36mzm0), que pasa al Inicio; con la fuente rota, en el tablero, donde está la explicación.
"""

import datetime
from pathlib import Path

from gi.repository import Adw, Gtk, Pango

from .. import como_se_abre, equipo, resumen_inicio
from .comun import ESPACIADO_LG, ESPACIADO_MD, ESPACIADO_SM, ESPACIADO_XL, ESPACIADO_XS
from .escala import px
from .comun import animaciones_activas
from .constelacion import caja_constelacion
from .piezas import chip, con_mano, etiquetar, icono, vaciar

INICIO, TABLERO = "inicio", "tablero"
ANCHO_INICIO = 1080      # el contenido no se estira más que esto en una ventana ancha
CAMBIO_PESTANA_MS = 160
ANCHO_CHIP_ESTADO = 120   # la columna del chip de cada fila de proyecto


class PestanaInicio:
    """Las pestañas Inicio y Tablero, y lo que se pinta en Inicio."""

    def crear_pestanas(self, tablero):
        """La pila con las dos pestañas; `tablero` es lo que antes era todo el contenido."""
        self.crear_ver_app()
        self.pestanas = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE,
                                  transition_duration=CAMBIO_PESTANA_MS, vexpand=True)
        self.pestanas.add_named(self.crear_inicio(), INICIO)
        self.pestanas.add_named(tablero, TABLERO)
        self.pestanas.add_named(self.crear_equipo(), "equipo")
        self.pestanas.add_named(self.crear_entrevista(), "entrevista")
        self.pestanas.add_named(self.crear_preparando(), "preparando")
        self.pestanas.add_named(self.crear_revisar_plan(), "plan")
        self.pestanas.add_named(self.crear_mapa(), "mapa")
        self.inicio_al_dia = False   # se repinta al verse: fuera de vista no se lee nada
        return self.pestanas

    def pestana_actual(self):
        return self.pestanas.get_visible_child_name()

    def pestana_inicial(self):
        """Inicio. Sin nada configurado (primer arranque), «revisar el equipo»; con la fuente
        rota, el tablero, con su explicación."""
        if equipo.es_primer_arranque(self.fuente):
            return "equipo"
        return TABLERO if self.fuente.problema else INICIO

    def ver_pestana(self, clave, al_abrir=False):
        """Enseña una pestaña. Lo que solo es del tablero (la banda de proyectos, buscar) se
        esconde en Inicio; el dot entra la primera vez que se ve el tablero. `al_abrir` es la
        primera vez, al crear la ventana: ahí el dot lo hace entrar la app, después del logo."""
        if clave not in (TABLERO, "mapa"):
            self.tablero_desde_mapa = False
        self.pestanas.set_transition_duration(CAMBIO_PESTANA_MS if animaciones_activas() else 0)
        self.pestanas.set_visible_child_name(clave)
        en_tablero = clave == TABLERO
        self.boton_volver.set_visible(clave != INICIO)
        self.subtitulo.set_visible(en_tablero)
        self.titulo_pantalla.set_label(self.titulo_de_pantalla(clave))
        for widget in (self.banda_proyectos, self.buscador):
            widget.set_visible(en_tablero)
        if clave == "equipo":
            self.revisar_equipo()
        if en_tablero and not al_abrir:
            self.entrar_dot()
        elif not self.inicio_al_dia:
            self.pintar_inicio()

    def titulo_de_pantalla(self, clave):
        if clave == TABLERO:
            return "Tablero"
        if clave == "equipo":
            return "Primer arranque" if equipo.es_primer_arranque(self.fuente) else "Tus agentes"
        if clave == "entrevista":
            return "Nuevo proyecto"
        if clave == "mapa":
            return (self.mapa_proyecto or ("",))[0]
        if clave == "plan":
            return (self.plan_estado or {}).get("proyecto", "")
        if clave == "preparando":
            vista = getattr(self.pantalla_preparando, "vista", None)
            return getattr(vista, "proyecto", "") if vista else ""
        return ""

    def volver(self):
        """Vuelve a la pantalla lógica anterior, sin apropiarse de Alt+← del dot."""
        destino = "mapa" if self.pestana_actual() == TABLERO and \
            getattr(self, "tablero_desde_mapa", False) else INICIO
        self.tablero_desde_mapa = False
        self.ver_pestana(destino)

    def ver_tablero(self):
        """Entrada pública al tablero para las acciones del Inicio."""
        self.tablero_desde_mapa = False
        self.ver_pestana(TABLERO)

    def tablero_a_la_vista(self):
        return getattr(self, "pestanas", None) is None or self.pestana_actual() == TABLERO

    # --- lo que se pinta ----------------------------------------------------------------------

    def crear_inicio(self):
        cuerpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XL),
                         margin_top=px(ESPACIADO_XL) * 2, margin_bottom=px(ESPACIADO_XL) * 2,
                         margin_start=px(ESPACIADO_XL) * 2, margin_end=px(ESPACIADO_XL) * 2)

        cabeza = Gtk.Box(spacing=px(ESPACIADO_LG))
        textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS),
                         hexpand=True, valign=Gtk.Align.END)
        self.inicio_saludo = Gtk.Label(xalign=0, css_classes=["inicio-saludo"])
        self.inicio_titular = Gtk.Label(xalign=0, wrap=True, css_classes=["inicio-titular"])
        textos.append(self.inicio_saludo)
        textos.append(self.inicio_titular)
        cabeza.append(textos)
        contenido_nuevo = Gtk.Box(spacing=px(ESPACIADO_SM))
        contenido_nuevo.append(Gtk.Image(icon_name="list-add-symbolic"))
        contenido_nuevo.append(Gtk.Label(label="Nuevo proyecto"))
        nuevo = con_mano(Gtk.Button(child=contenido_nuevo, valign=Gtk.Align.END,
                                    css_classes=["principal"]))
        etiquetar(nuevo, "Nuevo proyecto")
        nuevo.connect("clicked", lambda *_: self.nuevo_proyecto())
        cabeza.append(nuevo)
        cuerpo.append(cabeza)

        self.inicio_entregas = Gtk.Box(spacing=px(ESPACIADO_SM),
                                       css_classes=["inicio-entregas"], visible=False)
        self.inicio_entregas.append(Gtk.Label(label="•", css_classes=["inicio-punto"]))
        self.inicio_entregas_texto = Gtk.Label(xalign=0, hexpand=True)
        self.inicio_entregas.append(self.inicio_entregas_texto)
        comprobar = con_mano(Gtk.Button(label="Comprobar", css_classes=["flat"]))
        comprobar.connect("clicked", lambda *_: self.ver_tablero())
        self.inicio_entregas.append(comprobar)
        cuerpo.append(self.inicio_entregas)

        # Un repo de la lista que ya no existe (v1.3.0): se salta, y aquí se dice en llano.
        self.inicio_aviso = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS),
                                    css_classes=["vacio", "roto"], visible=False)
        self.inicio_aviso_titulo = Gtk.Label(xalign=0, wrap=True, css_classes=["vacio-titulo"])
        self.inicio_aviso_detalle = Gtk.Label(xalign=0, wrap=True, selectable=True,
                                              css_classes=["vacio-pista"])
        self.inicio_aviso.append(self.inicio_aviso_titulo)
        self.inicio_aviso.append(self.inicio_aviso_detalle)
        self.inicio_aviso_acciones = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                              spacing=px(ESPACIADO_XS))
        self.inicio_aviso.append(self.inicio_aviso_acciones)
        cuerpo.append(self.inicio_aviso)

        # La constelación (cotejo-7wc9hb): oculta mientras no haya proyectos que dibujar.
        self.constelacion = None
        self.area_constelacion = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                         css_classes=["inicio-constelacion"], visible=False)
        cuerpo.append(self.area_constelacion)

        self.inicio_proyectos_titulo = Gtk.Label(label="Proyectos", xalign=0,
                                                  css_classes=["inicio-seccion"], visible=False)
        cuerpo.append(self.inicio_proyectos_titulo)
        self.inicio_tarjetas = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE,
                                           css_classes=["inicio-proyectos"], visible=False)
        self.inicio_tarjetas.connect("row-activated", self._abrir_fila_proyecto)
        cuerpo.append(self.inicio_tarjetas)

        self.inicio_vacio = self.tarjeta_nuevo()
        cuerpo.append(self.inicio_vacio)

        self.inicio_equipo = Gtk.Box(spacing=px(ESPACIADO_XS), css_classes=["inicio-equipo"])
        self.inicio_equipo_texto = Gtk.Label(css_classes=["dato-sin-mono"])
        self.inicio_equipo.append(self.inicio_equipo_texto)
        self.inicio_equipo_enlace = con_mano(Gtk.Button(css_classes=["flat", "inicio-enlace"]))
        self.inicio_equipo_enlace.connect("clicked", self.ver_equipo)
        self.inicio_equipo.append(self.inicio_equipo_enlace)
        cuerpo.append(self.inicio_equipo)

        ancho = Adw.Clamp(child=cuerpo, maximum_size=px(ANCHO_INICIO), tightening_threshold=px(ANCHO_INICIO))
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
        faltan = resumen_inicio.repos_que_faltan(getattr(self.app, "avisos", None))
        if faltan:
            self.inicio_aviso_titulo.set_label(faltan[0])
            self.inicio_aviso_detalle.set_label("\n\n".join(faltan[1]))
            vaciar(self.inicio_aviso_acciones)
            for aviso in faltan[2]:
                ruta = aviso["repo_falta"]
                nombre = Path(ruta).name or ruta
                boton = con_mano(Gtk.Button(label=f"Quitar {nombre} de Cotejo",
                                             halign=Gtk.Align.START,
                                             tooltip_text=ruta, css_classes=["flat"]))
                etiquetar(boton, f"Quitar {ruta} de Cotejo")
                boton.connect("clicked", lambda _b, r=ruta:
                              self.confirmar_quitar_proyecto("", r, ausente=True))
                self.inicio_aviso_acciones.append(boton)
        self.inicio_aviso.set_visible(bool(faltan))
        entregas = sum(t.por_comprobar for t in tarjetas)
        self.inicio_entregas_texto.set_label(
            f"{entregas} {'entrega espera' if entregas == 1 else 'entregas esperan'} que las compruebes")
        self.inicio_entregas.set_visible(entregas > 0)
        self.pintar_constelacion(tarjetas)
        vaciar(self.inicio_tarjetas)
        for uno in tarjetas:
            self.inicio_tarjetas.append(self.tarjeta_de_proyecto(uno))
        hay = bool(tarjetas)
        self.inicio_proyectos_titulo.set_visible(hay)
        self.inicio_tarjetas.set_visible(hay)
        self.inicio_vacio.set_visible(not hay)
        self.pintar_estado_equipo()

    def pintar_estado_equipo(self):
        """Una foto barata del equipo: nunca pregunta a los CLIs mientras pinta."""
        visto = getattr(self, "equipo_visto", None) or equipo.revisar(preguntar_cli=False)
        listos = sum(1 for agente in visto.agentes if agente.listo)
        if listos:
            self.inicio_equipo_texto.set_label(
                f"{listos} {'agente listo' if listos == 1 else 'agentes listos'} ·")
            self.inicio_equipo_enlace.set_label("Ver tus agentes")
            self.inicio_equipo.remove_css_class("sin-agentes")
        else:
            self.inicio_equipo_texto.set_label("Ningún agente listo ·")
            self.inicio_equipo_enlace.set_label("Instalar uno")
            self.inicio_equipo.add_css_class("sin-agentes")

    def _abrir_fila_proyecto(self, _lista, fila):
        self.abrir_proyecto(fila.nombre_proyecto)

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
        contenido = Gtk.Box(spacing=px(ESPACIADO_LG), css_classes=["inicio-proyecto-fila"])
        identidad = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS),
                            hexpand=True, valign=Gtk.Align.CENTER)
        identidad.append(Gtk.Label(label=t.nombre, xalign=0,
                                    ellipsize=Pango.EllipsizeMode.END,
                                    css_classes=["inicio-proyecto-nombre"]))
        identidad.append(Gtk.Label(label=t.objetivo, xalign=0,
                                    ellipsize=Pango.EllipsizeMode.END,
                                    css_classes=["inicio-descripcion"]))
        contenido.append(identidad)
        datos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS),
                        valign=Gtk.Align.CENTER, css_classes=["inicio-proyecto-datos"])
        datos.append(Gtk.Label(label=t.texto_avance, xalign=0, css_classes=["dato"]))
        avance = Gtk.ProgressBar(fraction=t.avance or 0, css_classes=["inicio-avance"])
        avance.set_visible(t.con_arquitectura)
        datos.append(avance)
        contenido.append(datos)
        # El chip va en una columna de ancho fijo: si no, «1 por hacer» empuja la cifra y la
        # barra de su fila y dejan de alinearse con las de «al día».
        estado = Gtk.Box(width_request=px(ANCHO_CHIP_ESTADO), valign=Gtk.Align.CENTER)
        estado.append(chip(t.texto_estado, "", *(["verde"] if t.por_comprobar else [])))
        contenido.append(estado)
        acciones = Gtk.Box(spacing=px(ESPACIADO_XS), halign=Gtk.Align.START)
        for texto, nombre_icono, accion in (
                ("Ver mi app", "web-browser-symbolic", self.ver_mi_app),
                ("Abrir la carpeta", "folder-open-symbolic", self.abrir_carpeta)):
            b = con_mano(Gtk.Button(icon_name=nombre_icono, css_classes=["flat", "inicio-accion"],
                                    tooltip_text=texto))
            etiquetar(b, f"{texto} de {t.nombre}")
            b.connect("clicked", lambda _b, a=accion: a(t.nombre, t.carpeta or None))
            acciones.append(b)
        parar = con_mano(Gtk.Button(icon_name="media-playback-stop-symbolic",
                                    css_classes=["flat", "inicio-accion"],
                                    tooltip_text="Parar la app"))
        etiquetar(parar, f"Parar la app de {t.nombre}")
        parar.connect("clicked", lambda *_: self.parar_app(t.nombre))
        parar.set_visible(self.servidores.vivo(t.nombre))
        acciones.append(parar)
        # Sin código todavía, «Ver mi app» no se puede pulsar y dice por qué en el tooltip.
        if t.sin_app:
            ver_app = acciones.get_first_child()
            ver_app.set_sensitive(False)
            ver_app.set_tooltip_text(como_se_abre.SIN_APP)
        tablero = con_mano(Gtk.Button(child=icono("tablero"),
                                      css_classes=["flat", "inicio-accion"],
                                      tooltip_text="Ver el tablero"))
        etiquetar(tablero, f"Ver el tablero de {t.nombre}")
        tablero.connect("clicked", lambda *_: self.abrir_tablero(t.nombre))
        acciones.append(tablero)
        contenido.append(acciones)
        tarjeta = Gtk.ListBoxRow(child=contenido, activatable=True, selectable=False)
        for widget in (tarjeta, contenido):
            widget.botones_app = acciones
            widget.boton_parar_app = parar
            widget.nombre_proyecto = t.nombre
        return tarjeta

    def tarjeta_nuevo(self):
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS),
                       valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
        caja.append(Gtk.Label(label="Empezar un proyecto", css_classes=["vacio-titulo"]))
        caja.append(Gtk.Label(label="Contestas unas preguntas y tu agente lo prepara",
                              wrap=True, justify=Gtk.Justification.CENTER,
                              css_classes=["vacio-pista"]))
        boton = con_mano(Gtk.Button(label="Empezar un proyecto", css_classes=["principal"]))
        etiquetar(boton, "Empezar un proyecto")
        boton.connect("clicked", lambda *_: self.nuevo_proyecto())
        caja.append(boton)
        marco = Gtk.Box(css_classes=["inicio-nuevo"])
        marco.append(caja)
        return marco

    # `abrir_proyecto(nombre)` (tocar una tarjeta o un núcleo) vive en `mapa.py` (cotejo-p86sa9):
    # abre el mapa del proyecto, y de ahí «Ver el tablero» (`abrir_tablero`) lleva al tablero.
