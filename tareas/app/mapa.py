"""El mapa del proyecto en el board (v1.3.0, cotejo-p86sa9).

Una página más de la pila (`"mapa"`, sin botón en el selector, como la entrevista y el plan):
las cuatro capas con sus piezas por estado y, debajo, la ficha de la pieza tocada (la frase en
llano, sus tareas y, para quien programa, la tecnología). Qué se enseña está en `tareas/mapa.py`,
sin GTK; aquí solo se pinta. El punto de cada pieza y la leyenda son los de la constelación
(`constelacion.dibujar_punto`, `leyenda`), para que el mapa no pueda decir otra cosa que ella.

Es lo que hace `abrir_proyecto(nombre, carpeta=None)`, el enganche que dejó el Inicio: tocar una
tarjeta, tocar un núcleo de la constelación y «Empezar la 0.1.0» / «Ver el mapa» del plan
llevan aquí. Del mapa se pasa al tablero de ese proyecto con «Ver el tablero»
(`abrir_tablero`, lo que antes hacía tocar una tarjeta) y se vuelve con «Inicio».

La carpeta sale de la fuente activa (`carpeta_de`); un proyecto recién preparado vive en la
fuente repo y no en la activa, y por eso el plan la pasa explícita.
"""

from gi.repository import Adw, Gtk, Pango

from .. import mapa as m
from .comun import ESPACIADO_LG, ESPACIADO_MD, ESPACIADO_SM, ESPACIADO_XL, ESPACIADO_XS
from .escala import px
from .constelacion import dibujar_punto, leyenda
from .piezas import chip, con_mano, etiquetar, vaciar

MAPA = "mapa"
LADO_PUNTO = 14
ANCHO_MAPA = 1080


def punto(estado, colores):
    """El punto de un estado, dibujado igual que en la constelación."""
    area = Gtk.DrawingArea(content_width=px(LADO_PUNTO), content_height=px(LADO_PUNTO),
                           valign=Gtk.Align.CENTER)
    area.set_draw_func(lambda _a, cr, w, h: dibujar_punto(cr, w, h, estado, colores))
    return area


class PantallaMapa(Gtk.ScrolledWindow):
    """La página: `pintar(mapa)`; `al_tocar_pieza(id)` enseña su ficha."""

    __gtype_name__ = "CotejoPantallaMapa"

    def __init__(self, colores, **kwargs):
        super().__init__(hexpand=True, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER,
                         css_classes=["inicio"], **kwargs)
        self._colores = colores
        self.mapa = None
        self.botones_pieza = {}          # id → botón, para las pruebas y el foco
        self.ficha_actual = None
        cuerpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_LG),
                         margin_top=px(ESPACIADO_XL) * 2, margin_bottom=px(ESPACIADO_XL) * 2,
                         margin_start=px(ESPACIADO_XL) * 2, margin_end=px(ESPACIADO_XL) * 2)

        barra = Gtk.Box(spacing=px(ESPACIADO_SM))
        self.ruta = Gtk.Label(xalign=0, hexpand=True, css_classes=["dato"])
        barra.append(self.ruta)
        self.boton_inicio = con_mano(Gtk.Button(label="Inicio"))
        self.boton_carpeta = con_mano(Gtk.Button(label="Abrir la carpeta"))
        self.boton_parar = con_mano(Gtk.Button(label="Parar", visible=False))
        self.boton_ver_app = con_mano(Gtk.Button(label="Ver mi app"))
        self.boton_tablero = con_mano(Gtk.Button(label="Ver el tablero"))
        for b in (self.boton_inicio, self.boton_carpeta, self.boton_parar, self.boton_ver_app,
                  self.boton_tablero):
            barra.append(b)
        cuerpo.append(barra)

        cabeza = Gtk.Box(spacing=px(ESPACIADO_LG))
        textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS),
                         hexpand=True)
        self.eyebrow = Gtk.Label(xalign=0, css_classes=["dato"])
        self.titulo = Gtk.Label(xalign=0, wrap=True, css_classes=["inicio-titular"])
        textos.append(self.eyebrow)
        textos.append(self.titulo)
        cabeza.append(textos)
        self.avance = Gtk.Label(valign=Gtk.Align.END, css_classes=["dato"])
        cabeza.append(self.avance)
        cuerpo.append(cabeza)

        # Las cuatro capas: en fila con ancho, una debajo de otra en una ventana estrecha.
        self.capas = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                                 min_children_per_line=1, max_children_per_line=4,
                                 row_spacing=px(ESPACIADO_SM), column_spacing=px(ESPACIADO_SM),
                                 valign=Gtk.Align.START)
        cuerpo.append(self.capas)

        self.vacio = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS),
                             visible=False, css_classes=["carta", "plan-bloque"])
        self.vacio.append(Gtk.Label(label="Este proyecto todavía no tiene arquitectura",
                                    xalign=0, css_classes=["carta-nombre"]))
        self.vacio.append(Gtk.Label(
            label="Cuando tu agente la escriba con sus piezas, aquí verás qué ve la gente, qué "
                  "hace, qué guarda y con qué se conecta. Sus tareas siguen en el tablero.",
            xalign=0, wrap=True, css_classes=["carta-descripcion"]))
        cuerpo.append(self.vacio)

        self.ficha = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_SM),
                             css_classes=["carta", "plan-bloque", "mapa-ficha"])
        self.ficha_capa = Gtk.Label(xalign=0, css_classes=["dato"])
        self.ficha_nombre = Gtk.Label(xalign=0, wrap=True, css_classes=["carta-nombre"])
        self.ficha_frase = Gtk.Label(xalign=0, wrap=True)
        self.ficha_chips = Gtk.Box(spacing=px(ESPACIADO_XS))
        self.ficha_tareas = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS))
        self.ficha_tecnologia = Gtk.Label(xalign=0, wrap=True, css_classes=["dato"])
        for w in (self.ficha_capa, self.ficha_nombre, self.ficha_frase, self.ficha_chips,
                  self.ficha_tareas, self.ficha_tecnologia):
            self.ficha.append(w)
        cuerpo.append(self.ficha)

        # Los avisos son para quien programa: plegados, sin color de error en el mapa.
        self.avisos = Gtk.Label(xalign=0, wrap=True, selectable=True, css_classes=["dato"])
        self.avisos_plegable = Gtk.Expander(label="Si programas", visible=False,
                                            child=self.avisos)
        cuerpo.append(self.avisos_plegable)
        cuerpo.append(leyenda(colores))

        self.set_child(Adw.Clamp(child=cuerpo, maximum_size=px(ANCHO_MAPA),
                                 tightening_threshold=px(ANCHO_MAPA)))

    # --- pintar ---------------------------------------------------------------------------------

    def pintar(self, mapa):
        self.mapa = mapa
        self.ruta.set_label(mapa.ruta)
        self.eyebrow.set_label(mapa.eyebrow)
        self.titulo.set_label(mapa.titulo)
        self.avance.set_label(mapa.texto_avance)
        etiquetar(self.boton_tablero, f"Ver el tablero de {mapa.proyecto}")
        etiquetar(self.boton_ver_app, f"Ver mi app: abrir {mapa.proyecto}")
        vaciar(self.capas)
        self.botones_pieza = {}
        self.capas.set_visible(mapa.con_arquitectura)
        self.vacio.set_visible(not mapa.con_arquitectura)
        for capa in mapa.capas:
            self.capas.append(self._capa(capa))
        self.avisos.set_label("\n".join(a if isinstance(a, str) else
                                        f"{a.get('nota', '')}: {a.get('motivo', '')}"
                                        for a in mapa.avisos))
        self.avisos_plegable.set_visible(bool(mapa.avisos))
        self.avisos_plegable.set_expanded(False)
        anterior = self.ficha_actual.id if self.ficha_actual else None
        elegida = mapa.pieza(anterior) if anterior else None
        elegida = elegida or mapa.primera()
        if elegida is None:
            self.ficha_actual = None
            self.ficha.set_visible(False)
        else:
            self.al_tocar_pieza(elegida["id"])

    def _capa(self, capa):
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_SM),
                       valign=Gtk.Align.START, css_classes=["mapa-capa"])
        caja.append(Gtk.Label(label=capa.titulo, xalign=0, css_classes=["carta-nombre"]))
        caja.append(Gtk.Label(label=capa.subtitulo, xalign=0, css_classes=["carta-descripcion"]))
        if not capa.piezas:
            caja.append(Gtk.Label(label="Nada todavía", xalign=0, css_classes=["dato"]))
        for pieza in capa.piezas:
            fila = Gtk.Box(spacing=px(ESPACIADO_SM))
            fila.append(punto(pieza["estado"], self._colores))
            fila.append(Gtk.Label(label=pieza["nombre"], xalign=0, hexpand=True, wrap=True,
                                  wrap_mode=Pango.WrapMode.WORD_CHAR))
            boton = con_mano(Gtk.ToggleButton(child=fila, css_classes=["mapa-pieza"]))
            etiquetar(boton, f"{pieza['nombre']}, {m.nombre_estado(pieza['estado']).lower()}")
            boton.connect("clicked", lambda _b, i=pieza["id"]: self.al_tocar_pieza(i))
            self.botones_pieza[pieza["id"]] = boton
            caja.append(boton)
        return caja

    def al_tocar_pieza(self, pieza_id):
        pieza = self.mapa.pieza(pieza_id) if self.mapa else None
        if pieza is None:
            return
        f = m.ficha(self.mapa, pieza)
        self.ficha_actual = f
        for ident, boton in self.botones_pieza.items():
            activo = ident == pieza_id
            if boton.get_active() != activo:
                boton.set_active(activo)   # «toggled», no «clicked»: no vuelve a entrar aquí
        self.ficha.set_visible(True)
        self.ficha_capa.set_label(f.capa.upper())
        self.ficha_nombre.set_label(f.nombre)
        self.ficha_frase.set_label(f.frase)
        vaciar(self.ficha_chips)
        self.ficha_chips.append(chip(f.texto_estado, "", *(["verde"] if f.verde else [])))
        vaciar(self.ficha_tareas)
        for t in f.tareas:
            fila = Gtk.Box(spacing=px(ESPACIADO_MD), css_classes=["plan-tarea"])
            fila.append(Gtk.Label(label=t["texto"], xalign=0, wrap=True, hexpand=True))
            fila.append(chip(t["texto_columna"], "",
                             *(["verde"] if t["columna"] == "por-validar" else [])))
            etiquetar(fila, f"{t['texto']}: {t['texto_columna']}")
            self.ficha_tareas.append(fila)
        if not f.tareas:
            self.ficha_tareas.append(Gtk.Label(label=m.SIN_TAREAS, xalign=0,
                                               css_classes=["carta-descripcion"]))
        self.ficha_tecnologia.set_label(f.texto_tecnologia)


class PestanaMapa:
    """Los métodos de `Board` que llevan el mapa: `abrir_proyecto` y `abrir_tablero`."""

    def crear_mapa(self):
        self.mapa_proyecto = None        # (nombre, carpeta) del que se ve
        self.pantalla_mapa = PantallaMapa(lambda: self.app.colores)
        p = self.pantalla_mapa
        p.boton_inicio.connect("clicked", lambda *_: self.ver_pestana("inicio"))
        p.boton_tablero.connect("clicked", lambda *_: self.abrir_tablero(
            self.mapa_proyecto[0] if self.mapa_proyecto else ""))
        # cotejo-vn4qd2: siempre la carpeta principal del proyecto, nunca un worktree.
        for boton, accion in ((p.boton_ver_app, self.ver_mi_app),
                              (p.boton_carpeta, self.abrir_carpeta),
                              (p.boton_parar, lambda nombre, _c: self.parar_app(nombre))):
            boton.connect("clicked", lambda _b, a=accion: self.mapa_proyecto and a(
                self.mapa_proyecto[0], self.mapa_proyecto[1] or None))
        return p

    def abrir_proyecto(self, nombre, carpeta=None):
        """Tocar una tarjeta o un núcleo, o empezar desde el plan: el mapa de ese proyecto."""
        if not nombre:
            return
        if carpeta is None and not self.fuente.problema:
            carpeta = self.fuente.carpeta_de(nombre)
        self.mapa_proyecto = (nombre, str(carpeta) if carpeta else "")
        self.repintar_mapa()
        self.ver_pestana(MAPA)

    def repintar_mapa(self):
        if not getattr(self, "mapa_proyecto", None):
            return
        nombre, carpeta = self.mapa_proyecto
        proyecto = next((p for p in self.app.proyectos if p.nombre == nombre), None)
        # Lo del board solo vale si es de esa misma carpeta: uno recién preparado se lee de ella.
        if proyecto is not None and carpeta and not self.fuente.problema:
            activa = self.fuente.carpeta_de(nombre)
            if not activa or str(activa) != carpeta:
                proyecto = None
        self.pantalla_mapa.pintar(m.leer(nombre, carpeta, proyecto))
        self.pintar_botones_app()

    def repintar_mapa_si_se_ve(self):
        if getattr(self, "pestanas", None) is not None and self.pestana_actual() == MAPA:
            self.repintar_mapa()

    def abrir_tablero(self, nombre):
        """«Ver el tablero»: el tablero con ese proyecto elegido (lo que antes hacía la tarjeta)."""
        chip_proyecto = getattr(self, "botones_chip", {}).get(nombre)
        if chip_proyecto is None:
            self.aviso(f"{nombre} no tiene tareas en la fuente que usas"
                       if nombre else "No sé qué proyecto abrir")
            return
        self.al_elegir_chip(chip_proyecto)
        self.ver_pestana("tablero")
