"""La pantalla «Revisar el equipo» del board (v1.3.0, cotejo-36mzm0): reemplaza el primer arranque.

Se ve la primera vez (la fuente de repos sin ningún repo, `equipo.es_primer_arranque`) en vez del
tablero, y dice qué agentes de terminal y qué git hay en esta máquina. Cada agente está **no
instalado**, **falta iniciar sesión** o **listo** (cotejo-2j6un7):

- No instalado y con instalador oficial que Cotejo sabe correr (Claude Code, Codex, OpenCode):
  **Instalar** lo corre (`instalar_agentes.instalar`) en un hilo, con sus líneas en vivo debajo
  de la fila y **Cancelar**; además, el enlace a su página oficial. Sin instalador (Gemini CLI,
  git), solo el enlace (`Board.abrir_pagina`, el lanzador de enlaces del sistema).
- Falta iniciar sesión: **Iniciar sesión** abre el inicio de sesión oficial del agente
  (`instalar_agentes.iniciar_sesion`): en una terminal si lo pide, en segundo plano con su salida
  aquí si no (Codex), o el comando para copiar si no hay terminal.
- Mientras la pantalla se ve (o hay algo corriendo), cada `SONDEO` segundos se vuelve a detectar
  (`equipo.revisar`, que mira la sesión con `modelos_vivos.sesion`) y, si algo cambió, se repinta:
  así se entera sola de que la persona terminó en el navegador.

«Revisar otra vez» vuelve a detectar y «Seguir al Inicio» pasa a la pestaña Inicio. Es una página
más de la pila (`"equipo"`, sin botón en el selector). Qué se detecta lo decide
`tareas/equipo.py`, y qué se corre `tareas/instalar_agentes.py`, los dos sin GTK; aquí solo se
pinta. Los hilos nunca tocan GTK: avisan con `GLib.idle_add`.
"""

from gi.repository import Gio, GLib, Gtk

from .. import equipo, instalar_agentes
from .comun import ESPACIADO_LG, ESPACIADO_MD, ESPACIADO_SM, ESPACIADO_XL, ESPACIADO_XS
from .escala import px
from .piezas import chip, con_mano, etiquetar, vaciar

EQUIPO = "equipo"
SONDEO = 3            # segundos entre una detección y la siguiente
LINEAS_A_LA_VISTA = 6


def _foto(visto):
    return tuple((p.clave, p.estado) for p in visto.piezas)


class PestanaEquipo:
    def crear_equipo(self):
        self.equipo_trabajos = {}      # clave → Trabajo (instalar o `codex login`)
        self.equipo_notas = {}         # clave → lo último que se le dijo a la persona
        self.equipo_sondeo = 0
        self.equipo_visto = None
        cuerpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_LG),
                         margin_top=px(ESPACIADO_XL) * 2, margin_bottom=px(ESPACIADO_XL) * 2,
                         margin_start=px(ESPACIADO_XL) * 2, margin_end=px(ESPACIADO_XL) * 2)
        cuerpo.append(Gtk.Label(label="Primer arranque", xalign=0, css_classes=["dato"]))
        cuerpo.append(Gtk.Label(label="Antes de empezar, Cotejo revisa tu equipo", xalign=0,
                                wrap=True, css_classes=["inicio-titular"]))
        cuerpo.append(Gtk.Label(
            label="Para preparar proyectos hace falta un agente de IA. Esto es lo que encontré:",
            xalign=0, wrap=True, css_classes=["vacio-pista"]))
        self.equipo_filas = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_SM))
        cuerpo.append(self.equipo_filas)
        self.equipo_titular = Gtk.Label(xalign=0, wrap=True, css_classes=["vacio-titulo"])
        self.equipo_mensaje = Gtk.Label(xalign=0, wrap=True, css_classes=["vacio-pista"])
        cuerpo.append(self.equipo_titular)
        cuerpo.append(self.equipo_mensaje)
        botones = Gtk.Box(spacing=px(ESPACIADO_MD))
        self.equipo_revisar = con_mano(Gtk.Button(label="Revisar otra vez"))
        self.equipo_revisar.connect("clicked", lambda *_: self.revisar_equipo())
        self.equipo_seguir = con_mano(Gtk.Button(label="Seguir al Inicio"))
        self.equipo_seguir.connect("clicked", lambda *_: self.seguir_al_inicio())
        botones.append(self.equipo_revisar)
        botones.append(self.equipo_seguir)
        cuerpo.append(botones)
        return Gtk.ScrolledWindow(child=cuerpo, hexpand=True, vexpand=True,
                                  hscrollbar_policy=Gtk.PolicyType.NEVER, css_classes=["inicio"])

    # --- pintar -----------------------------------------------------------------------------

    def revisar_equipo(self, visto=None):
        """Vuelve a detectar (o usa `visto`) y repinta. Devuelve el `Equipo` que vio."""
        visto = visto if visto is not None else equipo.revisar()
        self.equipo_visto = visto
        vaciar(self.equipo_filas)
        self.equipo_enlaces = {}
        self.equipo_instalar = {}
        self.equipo_sesion = {}
        self.equipo_cancelar = {}
        self.equipo_progreso = {}
        ocupado = any(t.corriendo for t in self.equipo_trabajos.values())
        for pieza in visto.piezas:
            self.equipo_filas.append(self._fila_equipo(pieza, ocupado))
        self.equipo_titular.set_label(visto.titular)
        self.equipo_mensaje.set_label(visto.mensaje)
        self._sondear_equipo_si_hace_falta()
        return visto

    def _fila_equipo(self, pieza, ocupado):
        fila = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS),
                       css_classes=["carta"])
        linea = Gtk.Box(spacing=px(ESPACIADO_MD))
        linea.append(Gtk.Label(label=pieza.titulo, xalign=0, hexpand=True))
        linea.append(chip(pieza.estado, "", *(["verde"] if pieza.listo else [])))
        trabajo = self.equipo_trabajos.get(pieza.clave)
        if trabajo is not None and trabajo.corriendo:
            cancelar = con_mano(Gtk.Button(label="Cancelar", valign=Gtk.Align.CENTER))
            cancelar.connect("clicked", lambda _b, t=trabajo: t.cancelar())
            self.equipo_cancelar[pieza.clave] = cancelar
            linea.append(cancelar)
        elif pieza.pide_sesion and pieza.clave in instalar_agentes.SESIONES:
            boton = con_mano(Gtk.Button(label="Iniciar sesión", valign=Gtk.Align.CENTER,
                                        css_classes=["suggested-action"]))
            etiquetar(boton, f"Iniciar sesión en {pieza.titulo} (abre tu navegador)")
            boton.connect("clicked", lambda _b, p=pieza: self.iniciar_sesion_agente(p.clave))
            self.equipo_sesion[pieza.clave] = boton
            linea.append(boton)
        elif not pieza.instalado:
            enlace = con_mano(Gtk.Button(label=pieza.texto_enlace, valign=Gtk.Align.CENTER,
                                         css_classes=["flat"]))
            etiquetar(enlace, f"{pieza.texto_enlace} (abre su página oficial)")
            enlace.connect("clicked", lambda _b, p=pieza: self.abrir_pagina(p.pagina))
            self.equipo_enlaces[pieza.clave] = enlace
            linea.append(enlace)
            if pieza.instalable:
                instalar = con_mano(Gtk.Button(label="Instalar", valign=Gtk.Align.CENTER,
                                               css_classes=["suggested-action"]))
                etiquetar(instalar, f"Instalar {pieza.titulo} con su instalador oficial")
                instalar.set_sensitive(not ocupado)
                instalar.connect("clicked", lambda _b, p=pieza: self.instalar_agente(p.clave))
                self.equipo_instalar[pieza.clave] = instalar
                linea.append(instalar)
        fila.append(linea)
        if pieza.nota:
            fila.append(Gtk.Label(label=pieza.nota, xalign=0, wrap=True,
                                  css_classes=["vacio-pista"]))
        progreso = Gtk.Label(xalign=0, wrap=True, selectable=True, css_classes=["dato"])
        self.equipo_progreso[pieza.clave] = progreso
        fila.append(progreso)
        self._pintar_progreso(pieza.clave)
        return fila

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
        """Vuelve a detectar; repinta solo si cambió algún estado. Se apaga sola cuando la
        pantalla deja de verse y no corre nada."""
        if not self._equipo_a_la_vista():
            self.equipo_sondeo = 0
            return GLib.SOURCE_REMOVE
        visto = equipo.revisar()
        if self.equipo_visto is None or _foto(visto) != _foto(self.equipo_visto):
            for p in visto.agentes:
                if p.listo and p.clave in self.equipo_notas:
                    self.equipo_notas[p.clave] = f"{p.titulo} está listo."
            self.revisar_equipo(visto)
        return GLib.SOURCE_CONTINUE

    def abrir_pagina(self, url):
        """Abre una página oficial con el lanzador del sistema (las pruebas lo sustituyen)."""
        Gio.AppInfo.launch_default_for_uri(url, None)

    def seguir_al_inicio(self):
        self.ver_pestana("inicio")
