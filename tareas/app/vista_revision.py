"""La revisión en Para comprobar: evidencia, diff, integrar."""

import threading

from gi.repository import Adw, GLib, Gtk, Pango

from .. import bitacora, modelo, revision, worktrees
from .comun import ESPACIADO_LG, ESPACIADO_MD, ESPACIADO_SM, ESPACIADO_XS
from .escala import px
from .piezas import chip, con_mano, icono


class Revision:
    """La revisión en Para comprobar: evidencia, diff, integrar."""

    def revision_en_carta(self, proyecto, tarea):
        """Lo que la carta de *Para comprobar* dice de la entrega y lo que se puede hacer con ella.

        Pruebas en verde o en rojo, el diff en una línea con su barra y los commits: lo justo
        para decidir si abrir la revisión entera. Debajo, volver a comprobar, revisar y aprobar.
        Todo sale de `revision.resumen`, que no sabe de GTK y se prueba sin pantalla.
        """
        datos = revision.resumen(self.entrega_de(tarea))
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS))
        if datos:
            fila = Gtk.Box(spacing=px(ESPACIADO_XS))
            pruebas = datos["pruebas"]
            if pruebas:
                fila.append(chip(pruebas["texto"],
                                 "estado-hecha" if pruebas["estado"] == "verde" else "aviso",
                                 pruebas["estado"],
                                 tooltip="Las pruebas que corrió Cotejo al entregarla"))
            if datos["commits_texto"]:
                fila.append(Gtk.Label(label=datos["commits_texto"], css_classes=["revision-dato"],
                                      tooltip_text=datos.get("rama") or ""))
            if fila.get_first_child() is not None:
                caja.append(fila)
            if datos["diff"]:
                linea = Gtk.Box(spacing=px(ESPACIADO_SM))
                linea.append(Gtk.Label(label=datos["diff"]["texto"], xalign=0,
                                       css_classes=["revision-dato"]))
                linea.append(self.barra_diff(datos["diff"]["proporcion_mas"], 1.0, 56))
                caja.append(linea)
        comprobacion = revision.texto_comprobacion(self.comprobaciones.get(tarea.id))
        if comprobacion:
            caja.append(Gtk.Label(label=comprobacion, xalign=0, wrap=True,
                                  css_classes=["revision-dato"]))

        botones = Gtk.Box(spacing=px(ESPACIADO_XS), css_classes=["revision-botones"])
        comprobar = Gtk.Button(child=self.con_icono("recargar", "Comprobar"),
                               css_classes=["flat"],
                               tooltip_text="Vuelve a correr las pruebas de la entrega")
        comprobar.set_sensitive(not (self.comprobaciones.get(tarea.id) or {}).get("corriendo"))
        comprobar.connect("clicked", lambda *_: self.volver_a_comprobar(tarea))
        botones.append(con_mano(comprobar))
        if datos or (self.entrega_de(tarea) or {}).get("resumen"):
            ver = Gtk.Button(child=self.con_icono("evidencia", "Revisar"), css_classes=["flat"],
                             tooltip_text="El diff, las pruebas y los commits de la entrega")
            ver.connect("clicked", lambda *_: self.ver_revision(proyecto, tarea))
            botones.append(con_mano(ver))
        aprobar = Gtk.Button(child=self.con_icono("estado-hecha", "Aprobar"), hexpand=True,
                             halign=Gtk.Align.END, css_classes=["suggested-action"],
                             tooltip_text="La das por buena; si tiene rama, te ofrece integrarla")
        aprobar.connect("clicked", lambda *_: self.mover(proyecto, tarea, modelo.HECHA))
        botones.append(con_mano(aprobar))
        caja.append(botones)
        return caja

    @staticmethod
    def con_icono(nombre, texto):
        caja = Gtk.Box(spacing=px(ESPACIADO_XS))
        caja.append(icono(nombre, 12))
        caja.append(Gtk.Label(label=texto))
        return caja

    @staticmethod
    def barra_diff(proporcion_mas, proporcion, ancho):
        """Una barra de `ancho` px: lo añadido en verde y lo quitado en ámbar, a escala."""
        barra = Gtk.Box(css_classes=["barra-diff"], valign=Gtk.Align.CENTER)
        barra.set_size_request(ancho, 4)
        lleno = round(ancho * max(0.0, min(1.0, proporcion)))
        mas = round(lleno * proporcion_mas)
        if mas:
            parte = Gtk.Box(css_classes=["barra-mas"])
            parte.set_size_request(mas, 4)
            barra.append(parte)
        if lleno - mas:
            parte = Gtk.Box(css_classes=["barra-menos"])
            parte.set_size_request(lleno - mas, 4)
            barra.append(parte)
        return barra

    def volver_a_comprobar(self, tarea):
        """Vuelve a correr las pruebas en un hilo: pueden tardar minutos y el board no se congela."""
        if (self.comprobaciones.get(tarea.id) or {}).get("corriendo"):
            return
        self.comprobaciones[tarea.id] = {"corriendo": True}
        self.pintar()
        entrega = bitacora.ultima_entrega(tarea.id)
        propio = worktrees.carpeta_de(tarea.id)

        def correr():
            try:
                resultado = revision.recomprobar(entrega, propio)
            except Exception as error:  # noqa: BLE001 — un fallo aquí no puede tumbar el board
                resultado = {"sigue_igual": None, "pruebas": [], "salida": f"No pude: {error}"}
            GLib.idle_add(self.al_comprobar, tarea.id, resultado)

        threading.Thread(target=correr, daemon=True).start()

    def al_comprobar(self, tarea_id, resultado):
        self.comprobaciones[tarea_id] = resultado
        self.aviso(revision.texto_comprobacion(resultado))
        self.pintar()
        return GLib.SOURCE_REMOVE

    def ver_revision(self, proyecto, tarea):
        """La entrega entera: pruebas con su salida, commits, archivos con su barra y el diff.

        El diff va por archivo, plegado, y cada archivo se pinta al desplegarlo: una entrega
        con cuarenta archivos no tiene que crear miles de etiquetas para enseñar la lista. Para
        lo que no cabe está «Abrir en herramienta», que lanza el `git difftool` de la persona.
        """
        entrega = self.entrega_de(tarea)
        datos = revision.resumen(entrega)
        texto_resumen = ((entrega or {}).get("resumen") or "").strip()
        if datos is None and not texto_resumen:
            return
        datos = datos or {"rama": None, "head": None, "desde": None, "sin_commitear": False,
                          "pruebas": None, "diff": None, "commits": [], "commits_texto": ""}
        carpeta = revision.carpeta_git(tarea.id, entrega)
        dialogo = Adw.Dialog(title="Revisar la entrega", content_width=px(880), content_height=px(760))
        vista = Adw.ToolbarView()
        cabecera = Adw.HeaderBar()
        vista.add_top_bar(cabecera)

        comprobar = Gtk.Button(child=self.con_icono("recargar", "Volver a comprobar"),
                               css_classes=["flat"])
        comprobar.connect("clicked", lambda *_: self.volver_a_comprobar(tarea))
        cabecera.pack_start(comprobar)
        aprobar = Gtk.Button(child=self.con_icono("estado-hecha", "Aprobar"),
                             css_classes=["suggested-action"])

        def al_aprobar(*_):
            dialogo.close()
            self.mover(proyecto, tarea, modelo.HECHA)

        aprobar.connect("clicked", al_aprobar)
        cabecera.pack_end(con_mano(aprobar))
        herramienta = Gtk.Button(child=self.con_icono("abrir", "Abrir en herramienta"),
                                 css_classes=["flat"],
                                 tooltip_text="git difftool, con la herramienta que tengas en git")
        herramienta.connect("clicked", lambda *_: self.abrir_en_herramienta(
            carpeta, datos.get("desde"), datos.get("head")))
        herramienta.set_sensitive(bool(carpeta and datos.get("desde") and datos.get("head")))
        cabecera.pack_end(herramienta)

        cuerpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_MD),
                         margin_top=px(ESPACIADO_MD), margin_bottom=px(ESPACIADO_LG),
                         margin_start=px(ESPACIADO_LG), margin_end=px(ESPACIADO_LG))
        cuerpo.append(Gtk.Label(label=tarea.texto, xalign=0, wrap=True,
                                css_classes=["revision-texto"]))
        if texto_resumen:
            cuerpo.append(self.bloque_resumen(proyecto, tarea, entrega, texto_resumen, dialogo))
        # Lo que dijo el agente que la lanzó el board, guardado (cotejo-o253bs).
        dialogo.en_vivo = self.seccion_en_vivo(tarea)
        if dialogo.en_vivo is not None:
            cuerpo.append(dialogo.en_vivo)
        if texto_resumen:
            cuerpo.append(self.titulo_seccion("EL DETALLE PARA QUIEN QUIERA VERLO"))
        donde = " · ".join(parte for parte in (
            datos.get("rama") or "", f"{(datos.get('desde') or '')[:7]}..{(datos.get('head') or '')[:7]}"
            if datos.get("desde") else "",
            "con cambios sin commitear" if datos["sin_commitear"] else "") if parte)
        if donde:
            cuerpo.append(Gtk.Label(label=donde, xalign=0, selectable=True,
                                    css_classes=["revision-dato"]))

        entregadas = (entrega or {}).get("pruebas") or []
        if entregadas:
            cuerpo.append(self.titulo_seccion("PRUEBAS"))
            for prueba in entregadas:
                cuerpo.append(self.fila_prueba(prueba))
        if datos["commits"]:
            cuerpo.append(self.titulo_seccion(datos["commits_texto"].upper()))
            for commit in datos["commits"]:
                cuerpo.append(Gtk.Label(label=f"{commit['corto']}  {commit['asunto']}", xalign=0,
                                        selectable=True, wrap=True, css_classes=["salida-prueba"]))
        if datos["diff"]:
            cuerpo.append(self.titulo_seccion(datos["diff"]["texto"].upper()))
            partes = {a["ruta"]: a for a in (revision.diff(carpeta, datos.get("desde"),
                                                           datos.get("head")) or [])}
            if not partes:
                cuerpo.append(Gtk.Label(
                    label="Git no me da el diff de esta entrega (¿se borró la rama o el repo?)",
                    xalign=0, wrap=True, css_classes=["revision-dato"]))
            for archivo in datos["diff"]["archivos"]:
                cuerpo.append(self.archivo_del_diff(archivo, partes.get(archivo["ruta"])))

        vista.set_content(Gtk.ScrolledWindow(child=cuerpo, vexpand=True,
                                             hscrollbar_policy=Gtk.PolicyType.NEVER))
        dialogo.set_child(vista)
        self.registrar_ficha(dialogo, tarea, "revision")
        dialogo.present(self)
        # Sin esto el foco cae en la primera etiqueta seleccionable y se abre con todo su texto
        # resaltado, como si ya lo hubieras marcado tú (lo mismo que en `al_ver`).
        dialogo.set_focus(comprobar)
        return dialogo

    @staticmethod
    def titulo_seccion(texto):
        return Gtk.Label(label=texto, xalign=0, margin_top=px(ESPACIADO_SM),
                         css_classes=["revision-titulo"])

    @staticmethod
    def fila_prueba(prueba):
        estado_ = revision.estado_prueba(prueba.get("codigo"))
        codigo = prueba.get("codigo")
        texto = {"verde": "verde", "rojo": f"rojo · código {codigo}",
                 "sin-terminar": prueba.get("error") or "no terminó"}[estado_]
        cabeza = Gtk.Box(spacing=px(ESPACIADO_SM))
        cabeza.append(chip(texto, "estado-hecha" if estado_ == "verde" else "aviso", estado_))
        cabeza.append(Gtk.Label(label=prueba.get("comando", ""), xalign=0, hexpand=True,
                                selectable=True, wrap=True, css_classes=["salida-prueba"]))
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS))
        caja.append(cabeza)
        salida = (prueba.get("salida") or "").strip()
        if salida:
            # Lo último de la salida, que es donde las herramientas ponen el resumen y el fallo.
            plegable = Gtk.Expander(label="Salida", expanded=estado_ != "verde")
            plegable.set_child(Gtk.Label(label=salida, xalign=0, selectable=True, wrap=True,
                                         wrap_mode=Pango.WrapMode.WORD_CHAR,
                                         css_classes=["salida-prueba"]))
            caja.append(plegable)
        return caja

    def archivo_del_diff(self, archivo, parte):
        """Una fila del diff: ruta, +/−, barra; y el diff del archivo plegado debajo."""
        cabeza = Gtk.Box(spacing=px(ESPACIADO_SM))
        cabeza.append(Gtk.Label(label=archivo["ruta"], xalign=0, hexpand=True,
                                ellipsize=Pango.EllipsizeMode.START, css_classes=["salida-prueba"]))
        cifras = ("binario" if archivo["binario"] else
                  f"+{archivo['mas'] or 0} −{archivo['menos'] or 0}")
        cabeza.append(Gtk.Label(label=cifras, css_classes=["revision-dato"]))
        cabeza.append(self.barra_diff(archivo["proporcion_mas"], archivo["proporcion"], 80))
        plegable = Gtk.Expander(label_widget=cabeza)
        if parte is None or (not parte["lineas"] and not parte["binario"]):
            plegable.set_sensitive(parte is not None)
            return plegable

        def al_desplegar(expander, _propiedad):
            if not expander.get_expanded() or expander.get_child() is not None:
                return
            expander.set_child(self.lineas_del_diff(parte))

        plegable.connect("notify::expanded", al_desplegar)
        return plegable

    @staticmethod
    def lineas_del_diff(parte):
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["diff"],
                       margin_top=px(ESPACIADO_XS))
        if parte["binario"]:
            caja.append(Gtk.Label(label="Archivo binario: ábrelo en la herramienta", xalign=0,
                                  css_classes=["diff-linea", "hunk"]))
            return caja
        lineas, fuera = revision.recortar(parte["lineas"])
        signos = {"mas": "+", "menos": "−", "contexto": " ", "hunk": ""}
        for tipo, texto in lineas:
            fila = Gtk.Box(spacing=px(ESPACIADO_XS), css_classes=["diff-linea", tipo])
            if tipo != "hunk":
                fila.append(Gtk.Label(label=signos[tipo], css_classes=["diff-signo"]))
            fila.append(Gtk.Label(label=texto, xalign=0, hexpand=True, selectable=True,
                                  wrap=True, wrap_mode=Pango.WrapMode.CHAR))
            caja.append(fila)
        if fuera:
            caja.append(Gtk.Label(label=f"… {fuera} líneas más: ábrelo en la herramienta",
                                  xalign=0, css_classes=["diff-linea", "hunk"]))
        return caja

    def abrir_en_herramienta(self, carpeta, desde, hasta):
        resultado = revision.abrir_en_herramienta(carpeta, desde, hasta)
        self.aviso(f"Abriendo en {resultado['herramienta']}" if resultado["abierto"]
                   else resultado["motivo"])

    def ofrecer_integrar(self, tarea, plan):
        """Aprobada la tarea, **ofrece** integrar su rama. Nunca la integra sin preguntar."""
        if not plan.get("ofrecer"):
            # Sin repo no hay nada de código que decir; con repo, por qué no se ofrece.
            if plan.get("repo"):
                self.aviso(f"No te ofrezco integrarla: {plan.get('motivo')}")
            return
        cuerpo = f"¿Integro {plan['rama']} en {plan['destino']}?\n{plan['repo']}"
        if plan.get("aviso"):
            cuerpo += f"\n\n{plan['aviso']}"
        dialogo = Adw.AlertDialog(heading="Aprobada. ¿Integras su rama?", body=cuerpo)
        dialogo.add_response("ahora-no", "Ahora no")
        dialogo.add_response("integrar", f"Integrar en {plan['destino']}")
        dialogo.set_response_appearance("integrar", Adw.ResponseAppearance.SUGGESTED)
        # Por defecto, no: integrar toca el repo de la persona y tiene que ser un clic a propósito.
        dialogo.set_default_response("ahora-no")
        dialogo.set_close_response("ahora-no")
        dialogo.connect("response", self.al_responder_integrar, plan)
        dialogo.present(self)

    def al_responder_integrar(self, _dialogo, respuesta, plan):
        if respuesta != "integrar":
            return
        resultado = revision.integrar(plan)
        self.aviso(f"{plan['rama']} integrada en {plan['destino']}" if resultado["integrada"]
                   else resultado["motivo"])
