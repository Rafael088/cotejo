"""La ficha de una tarea y el selector de agente."""

from gi.repository import Adw, Gtk, Pango

from .. import bitacora, modelo, revision, seguir_ficha
from .comun import (
    ESPACIADO_LG, ESPACIADO_SM, ESPACIADO_XL, ESPACIADO_XS, ICONOS_COLUMNA, ICONOS_DIFICULTAD,
    NOMBRES_DIFICULTAD, anotacion_visible, id_corto,
)
from .escala import px
from .piezas import con_mano, etiquetar, icono
from .vista_capturas import seccion_capturas


class Detalle:
    """La ficha de una tarea y el selector de agente."""

    def ver_detalle(self, proyecto, tarea):
        dialogo = self.dialogo_detalle(proyecto, tarea)
        self.registrar_ficha(dialogo, tarea, seguir_ficha.DETALLE)
        dialogo.present(self)

    # --- la ficha abierta sigue a la tarea (v1.3.0, cotejo-v66btg) -------------------------

    def registrar_ficha(self, dialogo, tarea, vista):
        """Anota qué ficha hay abierta para que `seguir_ficha` la ponga al día en cada repintado.
        Al cerrarse, deja de seguirla (solo si sigue siendo esa: una ficha nueva ya la reemplazó)."""
        if dialogo is None:
            return
        self.ficha_abierta = (dialogo, (tarea.id, vista, tarea.columna))

        def al_cerrar(*_):
            actual = getattr(self, "ficha_abierta", None)
            if actual is not None and actual[0] is dialogo:
                self.ficha_abierta = None
        dialogo.connect("closed", al_cerrar)

    def seguir_ficha(self):
        """Tras repintar: si la tarea de la ficha abierta cambió de columna, la ficha se muestra
        al estado nuevo (de Haciendo a la revisión de Para comprobar, etc.) en vez de quedarse con
        la cabecera vieja. Si la tarea ya no está en la fuente, se cierra y se avisa. Si la fuente
        no responde no se sabe nada de la tarea: la ficha se queda como está."""
        abierta = getattr(self, "ficha_abierta", None)
        if abierta is None or self.fuente.problema:
            return
        dialogo, datos = abierta
        decision = seguir_ficha.decidir(
            datos, self.app.proyectos, lambda t: self.entrega_de(t) is not None)
        if decision[0] == seguir_ficha.IGUAL:
            return
        self.ficha_abierta = None
        dialogo.close()
        if decision[0] == seguir_ficha.DESAPARECE:
            self.aviso("La tarea de la ficha ya no está en la fuente: se cerró.")
            return
        _, proyecto, tarea, vista = decision
        if vista == seguir_ficha.REVISION and self.ver_revision(proyecto, tarea) is not None:
            return
        self.ver_detalle(proyecto, tarea)

    def dialogo_detalle(self, proyecto, tarea):
        """La ficha de una tarea: lo que la carta no enseña y lo que se puede hacer con ella.

        Se lee de arriba abajo en el orden en que se decide: qué es (id, versión, nombre y
        descripción, cada cosa una sola vez), quién la tiene y cuánto cuesta, lo último que se
        dijo de ella y, abajo y fijas, las dos acciones de mover. El modelo se cambia aquí mismo
        en vez de cerrar y buscar el ⋮; en Finalizada ya no, porque lo hecho no se reasigna.
        Nada de abrir la nota: todo lo que hay que saber de la tarea está en la ficha.
        """
        version, nombre_corto, descripcion = tarea.partes
        nombres = dict(modelo.COLUMNAS)
        finalizada = tarea.columna == modelo.HECHA
        dialogo = Adw.Dialog(title=f"{id_corto(tarea.id)} · {nombres[tarea.columna]}",
                             content_width=px(560))
        vista = Adw.ToolbarView(css_classes=["detalle"])
        cabecera = Adw.HeaderBar(show_title=False)
        # La columna donde está, a la izquierda de la barra, como la miga de pan de la ficha:
        # el título del diálogo queda para el lector de pantalla y el selector de ventanas.
        donde_esta = Gtk.Box(spacing=px(ESPACIADO_SM), css_classes=["detalle-columna"])
        donde_esta.append(icono(ICONOS_COLUMNA[tarea.columna], 14))
        donde_esta.append(Gtk.Label(label=nombres[tarea.columna]))
        if proyecto is not None:
            donde_esta.append(Gtk.Label(label="·", css_classes=["detalle-tenue"]))
            donde_esta.append(Gtk.Label(label=proyecto.nombre, css_classes=["detalle-tenue"],
                                        ellipsize=Pango.EllipsizeMode.END, max_width_chars=24))
        cabecera.pack_start(donde_esta)
        vista.add_top_bar(cabecera)

        cuerpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_LG),
                         margin_top=px(ESPACIADO_LG), margin_bottom=px(ESPACIADO_XL),
                         margin_start=px(ESPACIADO_XL) + px(ESPACIADO_XS),
                         margin_end=px(ESPACIADO_XL) + px(ESPACIADO_XS))

        # Los textos se pueden seleccionar con el mouse para copiarlos, pero no toman el foco:
        # si no, la primera etiqueta se abría con todo el texto resaltado.
        # Qué es. Sin dos puntos en el texto, el «nombre» es solo su principio recortado y la
        # descripción el texto entero: enseñar los dos era leer la misma frase dos veces.
        que_es = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_SM))
        arriba = Gtk.Box(spacing=px(ESPACIADO_SM))
        arriba.append(Gtk.Label(label=id_corto(tarea.id), tooltip_text=tarea.id,
                                css_classes=["carta-codigo", "detalle-id"]))
        if version:
            arriba.append(Gtk.Label(label=version, css_classes=["carta-version"]))
        que_es.append(arriba)
        recortado = nombre_corto.rstrip("…").rstrip()
        solo_titulo = descripcion == nombre_corto or descripcion.startswith(recortado)
        titulo = descripcion if solo_titulo else nombre_corto
        que_es.append(Gtk.Label(label=titulo, xalign=0, wrap=True, selectable=True, focusable=False,
                                wrap_mode=Pango.WrapMode.WORD_CHAR,
                                css_classes=["detalle-nombre"]
                                + (["largo"] if len(titulo) > 90 else [])))
        if not solo_titulo:
            que_es.append(Gtk.Label(label=descripcion, xalign=0, wrap=True, selectable=True, focusable=False,
                                    wrap_mode=Pango.WrapMode.WORD_CHAR,
                                    css_classes=["detalle-descripcion"]))
        cuerpo.append(que_es)

        # Quién la tiene, cuánto cuesta y dónde vive: tres datos en una franja, cada uno con
        # su rótulo encima, en vez de una tabla de clave y valor que había que leer entera.
        datos = Gtk.Box(spacing=px(ESPACIADO_XL), css_classes=["detalle-datos"], homogeneous=False)
        datos.append(self.dato_de_detalle("Hecha por" if finalizada else "Modelo",
                                          self.selector_de_agente(proyecto, tarea, dialogo)))
        dificultad = Gtk.Box(spacing=px(ESPACIADO_XS))
        if tarea.dificultad:
            dificultad.append(icono(ICONOS_DIFICULTAD.get(tarea.dificultad, ""), 14))
        dificultad.append(Gtk.Label(
            label=NOMBRES_DIFICULTAD.get(tarea.dificultad, tarea.dificultad or "Sin calcular"),
            css_classes=["detalle-valor"] + ([] if tarea.dificultad else ["detalle-tenue"])))
        datos.append(self.dato_de_detalle("Dificultad", dificultad))
        vive = Gtk.Label(label=tarea.donde or "—", xalign=0, selectable=True, focusable=False,
                         ellipsize=Pango.EllipsizeMode.START, tooltip_text=tarea.donde or None,
                         css_classes=["detalle-ruta"])
        datos.append(self.dato_de_detalle("Dónde vive", vive, expandir=True))
        cuerpo.append(datos)

        # Lo último que se dijo de ella, entero y seleccionable: en la carta va recortado a
        # tres líneas, y aquí es donde se lee y se copia. La que terminó sin entregar tiene su
        # propia sección (`seccion_sin_entregar`, cotejo-granqk) en vez de esta «DEVUELTA», que
        # repetía lo que dijo el agente en crudo y con jerga.
        no_entrego = self.seccion_sin_entregar(proyecto, tarea, dialogo)
        visible = (None if finalizada else
                   anotacion_visible(tarea, self.app.bitacora.get(tarea.id)))
        if no_entrego is not None:
            cuerpo.append(no_entrego)
        elif visible is not None:
            clase, titulo_anotacion, texto = visible
            caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS),
                           css_classes=["anotacion", clase])
            cabeza = Gtk.Box(spacing=px(ESPACIADO_XS))
            cabeza.append(icono("devuelta" if clase == "detenida" else "evidencia", 12))
            cabeza.append(Gtk.Label(label=titulo_anotacion, xalign=0, hexpand=True,
                                    css_classes=["anotacion-titulo"]))
            caja.append(cabeza)
            caja.append(Gtk.Label(label=texto.strip(), xalign=0, wrap=True, selectable=True, focusable=False,
                                  wrap_mode=Pango.WrapMode.WORD_CHAR,
                                  css_classes=["anotacion-texto"]))
            cuerpo.append(caja)
        # Lo que se ve del trabajo entregado (`entregar --captura`): grande y sin abrir nada.
        entregada = (bitacora.ultima_entrega(tarea.id)
                     if finalizada else self.app.bitacora.get(tarea.id))
        entregada = (entregada if (entregada or {}).get("operacion") == "entregar"
                     else None)
        vistas = seccion_capturas(entregada, dialogo)
        if vistas is not None:
            cuerpo.append(vistas)

        if finalizada and entregada is not None:
            entrega = revision.resumen(entregada) or {}
            cuerpo.append(self.entrega_finalizada(entregada, entrega))

        # Lanzada desde el board (v1.3.0, `lanzar.py`): en Haciendo, lo que hace su agente en
        # vivo; en Pendiente, por qué quedó en espera o que está pausada (cotejo-z7ma7r).
        dialogo.en_vivo = self.seccion_en_vivo(tarea)
        if dialogo.en_vivo is not None:
            def retomar_caida(*_):
                dialogo.close()
                self.retomar_la_caida(proyecto, tarea)
            dialogo.en_vivo.al_retomar = retomar_caida
            dialogo.en_vivo.refrescar()      # ya con el botón a mano
            cuerpo.append(dialogo.en_vivo)
        espera = self.motivo_en_espera(tarea)
        if espera:
            def quitar(proyecto=proyecto, tarea=tarea):
                dialogo.close()
                self.al_quitar_de_espera(proyecto, tarea)

            def lanzar_igual(proyecto=proyecto, tarea=tarea):
                dialogo.close()
                self.al_lanzar_igual(proyecto, tarea)
            cuerpo.append(self.seccion_en_espera(espera, quitar, lanzar_igual))
        dialogo.pausada = (None if espera or no_entrego is not None
                           else self.seccion_pausada(tarea))
        if dialogo.pausada is not None:
            cuerpo.append(dialogo.pausada)

        vista.set_content(Gtk.ScrolledWindow(child=cuerpo, propagate_natural_height=True,
                                             max_content_height=px(520),
                                             hscrollbar_policy=Gtk.PolicyType.NEVER))

        if finalizada:
            dialogo.set_child(vista)
            return dialogo

        # Mover, abajo y fijo: atrás a la izquierda, adelante a la derecha y en verde, como
        # el orden de las columnas. Nunca a Finalizada desde aquí: eso es comprobar.
        orden = [c for c, _ in modelo.COLUMNAS]
        i = orden.index(tarea.columna)
        acciones = Gtk.Box(spacing=px(ESPACIADO_SM), css_classes=["detalle-acciones"])

        def accion(texto, destino, nombre_icono, clase, icono_al_final=False):
            fila = Gtk.Box(spacing=px(ESPACIADO_SM))
            partes = [Gtk.Label(label=texto), icono(nombre_icono, 14)]
            for parte in (partes if icono_al_final else reversed(partes)):
                fila.append(parte)
            boton = con_mano(Gtk.Button(child=fila, css_classes=[clase]))
            etiquetar(boton, texto)
            boton.texto = texto

            def al_pulsar(*_):
                dialogo.close()
                self.mover(proyecto, tarea, destino)
            boton.connect("clicked", al_pulsar)
            return boton

        if i > 0:
            acciones.append(accion(f"Devolver a {nombres[orden[i - 1]]}", orden[i - 1],
                                   "flecha-izquierda", "flat"))
        acciones.append(Gtk.Box(hexpand=True))
        if i + 1 < len(orden) - 1:
            acciones.append(accion(f"Pasar a {nombres[orden[i + 1]]}", orden[i + 1],
                                   "flecha-derecha", "suggested-action", icono_al_final=True))
        if acciones.get_first_child() is not acciones.get_last_child():
            vista.add_bottom_bar(acciones)
        dialogo.set_child(vista)
        return dialogo

    def entrega_finalizada(self, entregada, datos):
        """La entrega de una tarea aprobada, sin acciones que puedan modificarla."""
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_SM),
                       css_classes=["anotacion", "entregada"])
        caja.append(Gtk.Label(label="ENTREGA", xalign=0, css_classes=["detalle-clave"]))
        evidencia = (entregada.get("evidencia") or "").strip()
        if evidencia:
            caja.append(Gtk.Label(label=evidencia, xalign=0, wrap=True, selectable=True,
                                  focusable=False, css_classes=["anotacion-texto"]))
        git = " · ".join(parte for parte in (
            datos.get("rama") or "",
            f"commit {(datos.get('head') or '')[:12]}" if datos.get("head") else "",
        ) if parte)
        if git:
            caja.append(Gtk.Label(label=git, xalign=0, selectable=True, focusable=False,
                                  css_classes=["revision-dato"]))
        commits = datos.get("commits") or []
        for commit in commits:
            caja.append(Gtk.Label(label=f"{commit['corto']}  {commit['asunto']}", xalign=0,
                                  wrap=True, selectable=True, focusable=False,
                                  css_classes=["salida-prueba"]))
        return caja

    @staticmethod
    def dato_de_detalle(rotulo, valor, expandir=False):
        """Uno de los datos de la franja de la ficha: rótulo pequeño encima, valor debajo."""
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS),
                       hexpand=expandir)
        caja.append(Gtk.Label(label=rotulo.upper(), xalign=0, css_classes=["detalle-clave"]))
        valor.set_valign(Gtk.Align.CENTER)
        caja.append(valor)
        return caja

    def selector_de_agente(self, proyecto, tarea, dialogo):
        """El modelo de la ficha: un botón con el que tiene, que despliega a quién pasársela.

        En Finalizada es solo el nombre: lo hecho ya no cambia de manos.

        Asignar no cierra la ficha: el modelo nuevo se pinta en el mismo botón y la lista se
        rehace con la tarea al día, para poder seguir leyendo lo que se estaba leyendo
        (cotejo-uy34ma). Antes se cerraba, y en Pendiente parecía que la ventana se caía sola.
        """
        if tarea.columna == modelo.HECHA:
            return _fila_de_agente(tarea, self.alias_persona)
        boton = Gtk.MenuButton(child=_fila_de_agente(tarea, self.alias_persona),
                               always_show_arrow=True, css_classes=["flat", "detalle-agente"])
        etiquetar(boton, f"Cambiar el modelo, ahora {tarea.agente or 'sin asignar'}")
        boton.set_tooltip_text("Cambiar a quién está asignada")
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                       margin_top=px(ESPACIADO_SM), margin_bottom=px(ESPACIADO_SM),
                       margin_start=px(ESPACIADO_SM), margin_end=px(ESPACIADO_SM))
        popover = Gtk.Popover(child=caja)

        def poner_al_dia(actual):
            """La tarea ya escrita en la fuente: el botón y el menú, con lo nuevo."""
            boton.set_child(_fila_de_agente(actual, self.alias_persona))
            etiquetar(boton, f"Cambiar el modelo, ahora {actual.agente or 'sin asignar'}")
            while caja.get_first_child() is not None:
                caja.remove(caja.get_first_child())
            caja.append(Gtk.Label(label="ASIGNAR A", xalign=0, css_classes=["menu-titulo"]))
            caja.append(self.lista_de_agentes(proyecto, actual, popover, asignar, anadir_aqui))

        def asignar(p, t, agente, pop):
            pop.popdown()
            actual = self.al_asignar(p, t, agente, pop)
            if actual is not None:
                poner_al_dia(actual)

        def anadir(p, t, _cliente, pop):
            pop.popdown()

            def al_agregar(clave):
                actual = self.al_asignar(p, t, clave, pop)
                if actual is not None:
                    poner_al_dia(actual)
            self.abrir_anadir_modelo(self.agente_del_proyecto(p) or None, al_agregar)

        caja.append(Gtk.Label(label="ASIGNAR A", xalign=0, css_classes=["menu-titulo"]))
        # Un Board falso de las pruebas viejas no sabe abrir el diálogo de añadir (modelos.py).
        anadir_aqui = anadir if hasattr(self, "abrir_anadir_modelo") else None
        caja.append(self.lista_de_agentes(proyecto, tarea, popover, asignar, anadir_aqui))
        boton.set_popover(popover)
        return con_mano(boton)

    def lista_de_agentes(self, proyecto, tarea, popover, funcion=None, funcion_anadir=None):
        """Las opciones de «Asignar a», con scroll y agrupadas por cliente.

        Con los modelos que registran los clientes la lista pasa de treinta: sin scroll el
        popover no cabe en la ventana y GTK no lo abre, y sin un ancho mínimo las etiquetas
        recortadas lo dejaban en una columna ilegible. «Añadir modelo…» va una sola vez al
        pie, separado de los modelos, en vez de repetirse bajo cada grupo (cotejo-uy34ma).
        """
        agentes = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        # Por agente, con el del proyecto primero (cotejo-qixs4j, `modelos.py`). Un Board falso
        # de las pruebas viejas no trae `grupos_de`: ahí, la lista plana de siempre.
        grupos = (self.grupos_de(proyecto) if hasattr(self, "grupos_de")
                  else [(None, [a for a in self.agentes if a not in self.alias_persona])])
        for cliente, nombres in grupos:
            if cliente:
                from .modelos import titulo_de
                agentes.append(Gtk.Label(label=titulo_de(cliente), xalign=0,
                                         css_classes=["menu-titulo"]))
            for agente in nombres:
                if agente != tarea.agente:
                    agentes.append(self.opcion(agente, funcion or self.al_asignar, proyecto,
                                               tarea, agente, popover, "agente"))
        anadir = funcion_anadir or getattr(self, "al_anadir_y_asignar", None)
        if anadir is not None:
            agentes.append(Gtk.Separator(margin_top=px(ESPACIADO_SM),
                                         margin_bottom=px(ESPACIADO_XS)))
            agentes.append(self.opcion("Añadir modelo…", anadir, proyecto, tarea, None,
                                       popover, "mas"))
        personas = tuple(a for a in self.agentes if a in self.alias_persona) or \
            tuple(self.alias_persona[:1])
        if personas or tarea.agente:
            agentes.append(Gtk.Separator(margin_top=px(ESPACIADO_SM),
                                         margin_bottom=px(ESPACIADO_XS)))
        for agente in personas + ("",):
            if agente == tarea.agente:
                continue
            quien = "sin-agente" if not agente else "persona"
            agentes.append(self.opcion(agente or "Sin agente", funcion or self.al_asignar,
                                       proyecto, tarea, agente, popover, quien))
        return Gtk.ScrolledWindow(child=agentes, hscrollbar_policy=Gtk.PolicyType.NEVER,
                                  propagate_natural_height=True, max_content_height=px(320),
                                  width_request=px(300))


def _fila_de_agente(tarea, alias_persona):
    """El nombre del modelo con su icono, dentro del botón que abre «Asignar a»."""
    quien = ("sin-agente" if not tarea.agente else
             "persona" if tarea.agente in alias_persona else "agente")
    fila = Gtk.Box(spacing=px(ESPACIADO_XS))
    fila.append(icono(quien, 14))
    fila.append(Gtk.Label(label=tarea.agente or "Sin asignar",
                          css_classes=["detalle-valor"]
                          + ([] if tarea.agente else ["detalle-tenue"])))
    return fila
