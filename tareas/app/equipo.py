"""La pantalla «Revisar el equipo» del board (v1.3.0, cotejo-36mzm0): reemplaza el primer arranque.

Se ve la primera vez (la fuente de repos sin ningún repo, `equipo.es_primer_arranque`) en vez del
tablero, y dice qué agentes de terminal y qué git hay en esta máquina. Cada agente está **no
instalado**, **falta iniciar sesión**, **falta elegir modelo** o **listo** (cotejo-2j6un7):

- No instalado y con instalador oficial que Cotejo sabe correr (Claude Code, Codex, OpenCode):
  **Instalar** lo corre (`instalar_agentes.instalar`) en un hilo, con sus líneas en vivo debajo
  de la fila y **Cancelar**; además, el enlace a su página oficial. Sin instalador (Gemini CLI,
  git), solo el enlace (`Board.abrir_pagina`, el lanzador de enlaces del sistema).
- Falta iniciar sesión: **Iniciar sesión** abre el inicio de sesión oficial del agente
  (`instalar_agentes.iniciar_sesion`): en una terminal si lo pide, en segundo plano con su salida
  aquí si no (Codex), o el comando para copiar si no hay terminal.
- Falta elegir modelo: dice que se abra el agente, se configure un proveedor y un modelo y se
  vuelva a revisar. El maestro usa esta misma comprobación y no lo ofrece antes.
- Antigravity CLI (lo que reemplaza a Gemini CLI en cuentas personales) se instala igual y
  recibe tareas, pero Cotejo no puede ver su sesión (vive en el llavero): instalado dice
  «Instalado» y «Abrir» lo abre en una terminal para entrar con la cuenta. Gemini CLI queda
  como enlace, «solo con licencia de empresa».
- Mientras la pantalla se ve (o hay algo corriendo), cada `SONDEO` segundos se vuelve a detectar
  **en un hilo** (`equipo.revisar(preguntar_cli=True)`: la sesión de Codex o Claude Code en el
  llavero se le pregunta a su CLI) y, si algo cambió, se repinta: así se entera sola de que la
  persona terminó en el navegador. Al pintar nunca se lanza ningún CLI.

- git instalado pero sin con qué empujar (`equipo.puede_empujar`, cotejo-vz6v3c) dice «Falta
  conectar» y **Conectar** abre GitHub CLI en una terminal (`instalar_agentes.conectar_git`:
  `gh auth login`, o `gh auth setup-git` si gh ya tiene sesión); sin gh, su página oficial.
  El sondeo nota solo cuando queda. Cotejo nunca guarda la contraseña.

Se llega aquí el primer arranque y, después, con «Agentes» en el Inicio o con «¿Falta un
agente?» en el diálogo «Añadir modelo» (`ver_equipo`).

«Revisar otra vez» vuelve a detectar y «Empezar» pasa a Inicio solo en el primer arranque. Es una página
más de la pila (`"equipo"`, sin botón en el selector). Qué se detecta lo decide
`tareas/equipo.py`, y qué se corre `tareas/instalar_agentes.py`, los dos sin GTK; aquí solo se
pinta. Los hilos nunca tocan GTK: avisan con `GLib.idle_add`.
"""

import threading

from gi.repository import Adw, Gio, GLib, Gtk

from enrutador import modelos_vivos

from .. import equipo, instalar_agentes
from .comun import ESPACIADO_LG, ESPACIADO_MD, ESPACIADO_SM, ESPACIADO_XL, ESPACIADO_XS
from .escala import px
from .piezas import con_mano, etiquetar, vaciar

EQUIPO = "equipo"
SONDEO = 3            # segundos entre una detección y la siguiente
LINEAS_A_LA_VISTA = 6
ANCHO_EQUIPO = 760


def _foto(visto):
    return tuple((p.clave, p.estado) for p in visto.piezas)


class PestanaEquipo:
    def crear_equipo(self):
        self.equipo_trabajos = {}      # clave → Trabajo (instalar o `codex login`)
        self.equipo_notas = {}         # clave → lo último que se le dijo a la persona
        self.equipo_sondeo = 0
        self.equipo_sondeando = False   # hay un hilo detectando
        self.equipo_visto = None
        cuerpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XL),
                         margin_top=px(ESPACIADO_XL) * 2, margin_bottom=px(ESPACIADO_XL) * 2,
                         margin_start=px(ESPACIADO_XL) * 2, margin_end=px(ESPACIADO_XL) * 2)
        cabeza = Gtk.Box(spacing=px(ESPACIADO_MD))
        textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS),
                         hexpand=True)
        self.equipo_titular = Gtk.Label(xalign=0, wrap=True, css_classes=["inicio-titular"])
        self.equipo_mensaje = Gtk.Label(xalign=0, wrap=True, css_classes=["vacio-pista"])
        textos.append(self.equipo_titular)
        textos.append(self.equipo_mensaje)
        cabeza.append(textos)
        contenido_revisar = Gtk.Box(spacing=px(ESPACIADO_XS))
        contenido_revisar.append(Gtk.Image(icon_name="view-refresh-symbolic"))
        contenido_revisar.append(Gtk.Label(label="Revisar otra vez"))
        self.equipo_revisar = con_mano(Gtk.Button(child=contenido_revisar, valign=Gtk.Align.START,
                                                  css_classes=["flat", "equipo-revisar"]))
        self.equipo_revisar.connect("clicked", lambda *_: self.revisar_equipo())
        cabeza.append(self.equipo_revisar)
        cuerpo.append(cabeza)
        self.equipo_filas = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_LG))
        cuerpo.append(self.equipo_filas)
        self.equipo_seguir = con_mano(Gtk.Button(label="Empezar", halign=Gtk.Align.START,
                                                 css_classes=["principal"]))
        self.equipo_seguir.connect("clicked", lambda *_: self.seguir_al_inicio())
        cuerpo.append(self.equipo_seguir)
        ancho = Adw.Clamp(child=cuerpo, maximum_size=px(ANCHO_EQUIPO),
                          tightening_threshold=px(ANCHO_EQUIPO))
        return Gtk.ScrolledWindow(child=ancho, hexpand=True, vexpand=True,
                                  hscrollbar_policy=Gtk.PolicyType.NEVER, css_classes=["inicio"])

    # --- pintar -----------------------------------------------------------------------------

    def revisar_equipo(self, visto=None):
        """Vuelve a detectar (o usa `visto`) y repinta. Devuelve el `Equipo` que vio."""
        visto = visto if visto is not None else equipo.revisar()
        self.equipo_visto = visto
        primer_arranque = equipo.es_primer_arranque(self.fuente)
        self.equipo_seguir.set_visible(primer_arranque)
        vaciar(self.equipo_filas)
        self.equipo_enlaces = {}
        self.equipo_instalar = {}
        self.equipo_sesion = {}
        self.equipo_cancelar = {}
        self.equipo_progreso = {}
        ocupado = any(t.corriendo for t in self.equipo_trabajos.values())
        self._grupo_equipo("Listos", visto.agentes_listos, ocupado)
        pendientes = visto.agentes_pendientes
        self._grupo_equipo("Para instalar" if pendientes and all(not p.instalado for p in pendientes)
                           else "Les falta algo", pendientes, ocupado)
        self._grupo_equipo("Herramientas", (visto.git,), ocupado)
        if primer_arranque:
            self.equipo_titular.set_label("Antes de empezar, Cotejo revisa tu equipo")
            self.equipo_mensaje.set_label(
                "Para preparar proyectos hace falta un agente de IA. Esto es lo que encontré:")
        else:
            self.equipo_titular.set_label("Tus agentes")
            self.equipo_mensaje.set_label(
                f"{visto.resumen_agentes} Cotejo los vuelve a revisar solo cada pocos segundos.")
        self._sondear_equipo_si_hace_falta()
        return visto

    def _grupo_equipo(self, titulo, piezas, ocupado):
        if not piezas:
            return
        grupo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_SM))
        grupo.append(Gtk.Label(label=titulo, xalign=0, css_classes=["equipo-grupo-titulo"]))
        lista = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["equipo-lista"])
        for pieza in piezas:
            lista.append(self._fila_equipo(pieza, ocupado))
        grupo.append(lista)
        self.equipo_filas.append(grupo)

    def _fila_equipo(self, pieza, ocupado):
        fila = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS),
                       css_classes=["equipo-fila"], valign=Gtk.Align.FILL)
        fila.pieza = pieza
        linea = Gtk.Box(spacing=px(ESPACIADO_MD), valign=Gtk.Align.CENTER, vexpand=True)
        identidad = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS),
                            hexpand=True, valign=Gtk.Align.CENTER)
        identidad.append(Gtk.Label(label=pieza.titulo, xalign=0,
                                   css_classes=["equipo-nombre"]))
        detalle = self._detalle_pieza(pieza)
        if detalle:
            identidad.append(Gtk.Label(label=detalle, xalign=0, wrap=True,
                                       css_classes=["equipo-nota"]))
        linea.append(identidad)
        trabajo = self.equipo_trabajos.get(pieza.clave)
        if trabajo is not None and trabajo.corriendo:
            cancelar = con_mano(Gtk.Button(label="Cancelar", valign=Gtk.Align.CENTER))
            cancelar.connect("clicked", lambda _b, t=trabajo: t.cancelar())
            self.equipo_cancelar[pieza.clave] = cancelar
            linea.append(cancelar)
        elif pieza.clave == equipo.GIT and pieza.pide_sesion:
            boton = con_mano(Gtk.Button(label="Conectar", valign=Gtk.Align.CENTER,
                                        css_classes=["principal"]))
            etiquetar(boton, "Conectar git con tu cuenta de GitHub (abre una terminal)")
            boton.connect("clicked", lambda *_: self.conectar_git())
            self.equipo_sesion[pieza.clave] = boton
            linea.append(boton)
        elif pieza.pide_sesion and pieza.clave in instalar_agentes.SESIONES:
            boton = con_mano(Gtk.Button(label="Iniciar sesión", valign=Gtk.Align.CENTER,
                                        css_classes=["principal"]))
            etiquetar(boton, f"Iniciar sesión en {pieza.titulo} (abre tu navegador)")
            boton.connect("clicked", lambda _b, p=pieza: self.iniciar_sesion_agente(p.clave))
            self.equipo_sesion[pieza.clave] = boton
            linea.append(boton)
        elif pieza.sesion_desconocida and pieza.clave in instalar_agentes.SESIONES:
            linea.append(self._estado_listo())
            abrir = con_mano(Gtk.Button(label="Abrir", valign=Gtk.Align.CENTER,
                                        css_classes=["flat"]))
            etiquetar(abrir, f"Abrir {pieza.titulo} en una terminal para entrar con tu cuenta")
            abrir.connect("clicked", lambda _b, p=pieza: self.iniciar_sesion_agente(p.clave))
            self.equipo_sesion[pieza.clave] = abrir
            linea.append(abrir)
        elif not pieza.instalado:
            solo_enlace = not pieza.instalable
            if solo_enlace:
                enlace = con_mano(Gtk.Button(label="Cómo instalarlo", valign=Gtk.Align.CENTER,
                                              css_classes=["flat", "equipo-enlace"]))
            else:
                enlace = con_mano(Gtk.Button(child=Gtk.Image(icon_name="web-browser-symbolic"),
                                              valign=Gtk.Align.CENTER,
                                              css_classes=["flat", "equipo-enlace"]))
            etiquetar(enlace, f"Cómo instalar {pieza.titulo}")
            enlace.connect("clicked", lambda _b, p=pieza: self.abrir_pagina(p.pagina))
            self.equipo_enlaces[pieza.clave] = enlace
            linea.append(enlace)
            if pieza.instalable:
                instalar = con_mano(Gtk.Button(label="Instalar", valign=Gtk.Align.CENTER,
                                               css_classes=["principal"]))
                etiquetar(instalar, f"Instalar {pieza.titulo} con su instalador oficial")
                instalar.set_sensitive(not ocupado)
                instalar.connect("clicked", lambda _b, p=pieza: self.instalar_agente(p.clave))
                self.equipo_instalar[pieza.clave] = instalar
                linea.append(instalar)
        elif pieza.listo:
            linea.append(self._estado_listo())
        fila.append(linea)
        progreso = Gtk.Label(xalign=0, wrap=True, selectable=True, css_classes=["dato"])
        self.equipo_progreso[pieza.clave] = progreso
        fila.append(progreso)
        self._pintar_progreso(pieza.clave)
        return fila

    @staticmethod
    def _detalle_pieza(pieza):
        if pieza.listo and pieza.modelos:
            nombres = [str(modelo) for modelo in pieza.modelos[:3]]
            return ", ".join(nombres) + ("…" if len(pieza.modelos) > 3 else "")
        return pieza.nota

    @staticmethod
    def _estado_listo():
        estado = Gtk.Box(spacing=px(ESPACIADO_XS), css_classes=["equipo-estado"])
        estado.append(Gtk.Label(label="•", css_classes=["equipo-punto"]))
        estado.append(Gtk.Label(label="Listo"))
        return estado

    def _pintar_progreso(self, clave):
        etiqueta = getattr(self, "equipo_progreso", {}).get(clave)
        if etiqueta is None:
            return
        trabajo = self.equipo_trabajos.get(clave)
        partes = list(trabajo.lineas[-LINEAS_A_LA_VISTA:]) if trabajo is not None else []
        nota = self.equipo_notas.get(clave)
        if nota:
            partes.append(nota)
        etiqueta.set_label("\n".join(partes))
        etiqueta.set_visible(bool(partes))

    # --- instalar e iniciar sesión ----------------------------------------------------------------

    def instalar_agente(self, clave):
        """Corre el instalador oficial en un hilo. Uno a la vez."""
        if any(t.corriendo for t in self.equipo_trabajos.values()):
            return None
        self.equipo_notas.pop(clave, None)
        trabajo = instalar_agentes.instalar(
            clave, al_linea=self._linea_en_hilo, al_terminar=self._fin_en_hilo)
        self.equipo_trabajos[clave] = trabajo
        self.revisar_equipo(self.equipo_visto)
        return trabajo

    def iniciar_sesion_agente(self, clave):
        """Abre el inicio de sesión oficial y deja que el sondeo note cuando quede."""
        self.equipo_notas.pop(clave, None)
        apertura = instalar_agentes.iniciar_sesion(
            clave, al_linea=self._linea_en_hilo, al_terminar=self._fin_en_hilo)
        if apertura.como == "fondo":
            self.equipo_trabajos[clave] = apertura.trabajo
            self.equipo_notas[clave] = ("Se abre tu navegador para que entres con tu cuenta. "
                                        "Si no se abre, usa el enlace de arriba.")
        elif apertura.como == "terminal" and not modelos_vivos.sesion_visible(clave):
            self.equipo_notas[clave] = (
                f"Abrí una terminal con «{apertura.comando}»: entra con tu cuenta en el navegador.")
        elif apertura.como == "terminal":
            self.equipo_notas[clave] = (
                f"Abrí una terminal con «{apertura.comando}»: sigue los pasos ahí y en tu "
                f"navegador. Cotejo lo nota solo cuando termines.")
        else:
            self.equipo_notas[clave] = (
                f"No encontré una terminal que abrir. Abre una tú y escribe: {apertura.comando}"
                f" (Cotejo lo nota solo cuando termines).")
        self.revisar_equipo(self.equipo_visto)
        return apertura

    def conectar_git(self):
        """GitHub CLI en una terminal para que git empuje sin pedir contraseña; sin gh, su
        página. El sondeo nota solo cuando queda."""
        apertura = instalar_agentes.conectar_git()
        if apertura.como == "sin_gh":
            self.abrir_pagina(equipo.PAGINAS["gh"])
            self.equipo_notas[equipo.GIT] = (
                "Para conectar git hace falta GitHub CLI: te abrí su página. Instálalo y vuelve "
                "a tocar «Conectar».")
        elif apertura.como == "terminal":
            self.equipo_notas[equipo.GIT] = (
                f"Abrí una terminal con «{apertura.comando}»: sigue los pasos ahí y en tu "
                f"navegador (elige HTTPS y di que sí a autenticar git). Cotejo lo nota solo "
                f"cuando termines.")
        else:
            self.equipo_notas[equipo.GIT] = (
                f"No encontré una terminal que abrir. Abre una tú y escribe: {apertura.comando}"
                f" (Cotejo lo nota solo cuando termines).")
        self.revisar_equipo(self.equipo_visto)
        return apertura

    def _linea_en_hilo(self, trabajo, _linea):
        GLib.idle_add(lambda: self._pintar_progreso(trabajo.clave) and False)

    def _fin_en_hilo(self, trabajo):
        GLib.idle_add(lambda: self.trabajo_terminado(trabajo) and False)

    def trabajo_terminado(self, trabajo):
        """Ya en el hilo de GTK: dice cómo acabó y repinta con lo que hay ahora."""
        visto = equipo.revisar()
        pieza = next((p for p in visto.piezas if p.clave == trabajo.clave), None)
        instalado = pieza.instalado if pieza is not None else None
        self.equipo_notas[trabajo.clave] = instalar_agentes.resultado(trabajo, instalado)
        if trabajo.que == "instalar" and trabajo.estado == "hecho" and instalado:
            # Lo que dijo el instalador ya no hace falta en pantalla: queda en el registro.
            trabajo.lineas.clear()
        self.revisar_equipo(visto)
        return visto

    # --- el sondeo: existe mientras la pantalla se ve o algo corre -----------------------------

    def _sondear_equipo_si_hace_falta(self):
        if not self.equipo_sondeo and self._equipo_a_la_vista():
            self.equipo_sondeo = GLib.timeout_add_seconds(SONDEO, self.sondear_equipo)

    def _equipo_a_la_vista(self):
        return ((self.pestana_actual() == EQUIPO and self.equipo_filas.get_root() is not None)
                or any(t.corriendo for t in self.equipo_trabajos.values()))

    def sondear_equipo(self):
        """Lanza una detección en un hilo (`detectar_en_fondo`) si no hay otra en marcha. Se
        apaga sola cuando la pantalla deja de verse y no corre nada."""
        if not self._equipo_a_la_vista():
            self.equipo_sondeo = 0
            return GLib.SOURCE_REMOVE
        if not self.equipo_sondeando:
            self.equipo_sondeando = True
            self.detectar_en_fondo(self.equipo_detectado)
        return GLib.SOURCE_CONTINUE

    def detectar_en_fondo(self, al_terminar):
        """`equipo.revisar(preguntar_cli=True)` en un hilo; vuelve por `GLib.idle_add`."""
        def correr():
            try:
                visto = equipo.revisar(preguntar_cli=True)
            except Exception:  # noqa: BLE001  (un fallo al detectar no tumba el board)
                visto = None
            GLib.idle_add(lambda: al_terminar(visto) and False)
        threading.Thread(target=correr, daemon=True).start()

    def equipo_detectado(self, visto):
        """Ya en el hilo de GTK: repinta solo si cambió algún estado."""
        self.equipo_sondeando = False
        if visto is None or self.equipo_filas.get_root() is None:
            return
        if self.equipo_visto is None or _foto(visto) != _foto(self.equipo_visto):
            for p in visto.piezas:
                if p.listo and p.clave in self.equipo_notas:
                    self.equipo_notas[p.clave] = f"{p.titulo} está listo."
            self.revisar_equipo(visto)

    def ver_equipo(self, *_):
        """Lleva a «Revisar el equipo» desde el Inicio o desde «Añadir modelo»."""
        dialogo = getattr(self, "dialogo_modelo", None)
        if dialogo is not None:
            dialogo.force_close()
            self.dialogo_modelo = None
        self.ver_pestana(EQUIPO)

    def abrir_pagina(self, url):
        """Abre una página oficial con el lanzador del sistema (las pruebas lo sustituyen)."""
        Gio.AppInfo.launch_default_for_uri(url, None)

    def seguir_al_inicio(self):
        self.ver_pestana("inicio")
