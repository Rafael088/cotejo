"""El mapa de un proyecto (v1.3.0, cotejo-p86sa9), sin GTK: qué se enseña y en qué orden.

Las piezas de la arquitectura dibujable (`tareas/arquitectura.py`, leídas por
`conocimiento.piezas_del_repo`) repartidas en las cuatro capas que decidió el dueño en el
planning de la fase 2 —qué ve la gente, qué hace, qué guarda, con qué se conecta—, cada una con
su estado. Tocar una pieza abre su **ficha**: la frase en llano, sus tareas con la columna en la
que está cada una y, para quien programa, la tecnología.

La pantalla (`tareas/app/mapa.py`) solo pinta lo que sale de aquí. Los estados, sus nombres y
la leyenda son los de la constelación (`constelacion.NOMBRES`, `ESTADOS_LEYENDA`): el mapa es la
constelación de un proyecto en grande, y el verde sigue siendo solo de lo que espera
comprobación.

`armar` es puro. `leer` es lo único que toca disco, y solo lee: el almacén `.cotejo/` de la
carpeta del proyecto y, si el board no las tiene ya en memoria, sus tareas con la fuente repo
apuntada a esa carpeta (`revisar_plan.fuente_del_proyecto`), que es donde vive un proyecto
recién preparado aunque la persona use Obsidian.
"""

from dataclasses import dataclass, field

from . import almacen, conocimiento, modelo
from . import version as versiones
from .arquitectura import CAPAS
from .constelacion import ESTADOS_LEYENDA, NOMBRES

# El orden y las palabras del prototipo: la pregunta que cualquiera entiende y, debajo, qué es.
TEXTOS_CAPA = {
    "ve": ("Qué ve la gente", "Pantallas"),
    "hace": ("Qué hace", "Lo que pasa al tocar algo"),
    "guarda": ("Qué guarda", "Datos"),
    "conecta": ("Con qué se conecta", "Servicios de afuera"),
}
NOMBRES_COLUMNA = dict(modelo.COLUMNAS)
SIN_TECNOLOGIA = "todavía sin elegir"
SIN_TAREAS = "Ninguna tarea la cubre todavía."

assert tuple(TEXTOS_CAPA) == CAPAS


@dataclass
class Capa:
    clave: str
    titulo: str
    subtitulo: str
    piezas: list = field(default_factory=list)   # dicts de `piezas_del_repo`, en su orden


@dataclass
class Mapa:
    """Todo lo que pinta la pantalla del mapa."""

    proyecto: str
    carpeta: str = ""
    version: str = ""
    capas: list = field(default_factory=list)    # las cuatro `Capa`, siempre, en orden
    tareas: dict = field(default_factory=dict)   # id → {texto, columna}
    avisos: list = field(default_factory=list)

    @property
    def piezas(self):
        return [p for capa in self.capas for p in capa.piezas]

    @property
    def con_arquitectura(self):
        return bool(self.piezas)

    @property
    def hechas(self):
        return sum(1 for p in self.piezas if p["estado"] == "hecho")

    @property
    def texto_avance(self):
        """«6 de 11 piezas», o «sin arquitectura todavía» (lo mismo que la tarjeta)."""
        total = len(self.piezas)
        if not total:
            return "sin arquitectura todavía"
        return f"{self.hechas} de {total} {'pieza' if total == 1 else 'piezas'}"

    @property
    def ruta(self):
        return f"{self.proyecto}  ›  Mapa"

    @property
    def eyebrow(self):
        return f"MAPA DEL PROYECTO · {self.version}" if self.version else "MAPA DEL PROYECTO"

    @property
    def titulo(self):
        return f"Cómo está hecho {self.proyecto}"

    def pieza(self, pieza_id):
        return next((p for p in self.piezas if p["id"] == pieza_id), None)

    def primera(self):
        """La pieza que se enseña al abrir: la primera que espera comprobación, si hay; si no,
        la primera del mapa. None sin arquitectura."""
        piezas = self.piezas
        return next((p for p in piezas if p["estado"] == "por-comprobar"),
                    piezas[0] if piezas else None)


@dataclass
class Ficha:
    """Lo que se ve al tocar una pieza."""

    id: str
    nombre: str
    capa: str               # el título de la capa («Qué ve la gente»)
    frase: str
    estado: str
    texto_estado: str
    tareas: list            # [{id, texto, columna, texto_columna}]
    desconocidas: list      # ids que la arquitectura nombra y no son de ninguna tarea
    tecnologia: str

    @property
    def verde(self):
        return self.estado == "por-comprobar"

    @property
    def texto_tecnologia(self):
        return f"Si programas: {self.tecnologia or SIN_TECNOLOGIA}"

    @property
    def descripcion(self):
        """Lo que dice el lector de pantalla del botón de la pieza."""
        return f"{self.nombre}, {self.texto_estado.lower()}"


def nombre_estado(estado):
    """«Hecho», «En curso»… Uno que no se conoce se dice como `falta`, igual que se pinta."""
    return NOMBRES.get(estado, NOMBRES["falta"])


def tareas_de(proyecto):
    """{id: {texto, columna}} de un `modelo.Proyecto` ya leído (las que faltan y las hechas)."""
    salida = {}
    for tarea in [*proyecto.tareas, *proyecto.hechas]:
        ident = modelo.id_actual(tarea.id)
        if ident:
            salida[ident] = {"texto": tarea.nombre_corto or tarea.texto, "columna": tarea.columna}
    return salida


def columnas_de(tareas):
    """{id: columna}, lo que `piezas_del_repo` necesita para dar estado a cada pieza."""
    return {ident: t["columna"] for ident, t in tareas.items()}


def armar(proyecto, piezas, tareas=None, version="", carpeta="", avisos=None):
    """El `Mapa` de `proyecto` con sus piezas (dicts de `piezas_del_repo`) por capa."""
    capas = [Capa(clave, *TEXTOS_CAPA[clave]) for clave in CAPAS]
    por_clave = {c.clave: c for c in capas}
    for pieza in piezas:
        capa = por_clave.get(pieza.get("capa"))
        if capa is not None:
            capa.piezas.append(pieza)
    return Mapa(proyecto=proyecto, carpeta=str(carpeta or ""), version=version or "",
                capas=capas, tareas=dict(tareas or {}), avisos=list(avisos or []))


def ficha(mapa, pieza):
    """La `Ficha` de una pieza del mapa (su dict), con el texto y la columna de cada tarea."""
    tareas = []
    for ident in pieza.get("tareas", []):
        t = mapa.tareas.get(ident)
        if t is None:
            continue
        tareas.append({"id": ident, "texto": t["texto"], "columna": t["columna"],
                       "texto_columna": NOMBRES_COLUMNA.get(t["columna"], t["columna"])})
    estado = pieza.get("estado", "falta")
    return Ficha(id=pieza["id"], nombre=pieza["nombre"],
                 capa=TEXTOS_CAPA.get(pieza.get("capa"), ("", ""))[0],
                 frase=pieza.get("frase", ""), estado=estado,
                 texto_estado=nombre_estado(estado), tareas=tareas,
                 desconocidas=list(pieza.get("desconocidas", [])),
                 tecnologia=pieza.get("tecnologia", ""))


def leyenda():
    """[(estado, nombre)] en el orden de la constelación."""
    return [(e, NOMBRES[e]) for e in ESTADOS_LEYENDA]


# --- con E/S (solo leer) ---------------------------------------------------------------------


def _tareas_de_la_carpeta(carpeta, avisos):
    from .revisar_plan import fuente_del_proyecto
    tareas = {}
    for proyecto in fuente_del_proyecto(carpeta).escanear(incluir_hechas=True, avisos=avisos):
        tareas.update(tareas_de(proyecto))
    return tareas


def leer(nombre, carpeta, proyecto=None):
    """El `Mapa` del proyecto `nombre`, cuyo repo está en `carpeta`.

    `proyecto` es el `modelo.Proyecto` que el board ya leyó (con sus hechas), si lo tiene: así
    no se vuelve a leer `tareas.md`. Sin él —un proyecto que vive en la fuente repo y no en la
    activa— se leen de la carpeta. Sin carpeta o sin `.cotejo/`, un mapa vacío con el porqué.
    """
    avisos = []
    if not carpeta:
        avisos.append("Este proyecto no vive en un repo con .cotejo/: no tiene mapa.")
        tareas = tareas_de(proyecto) if proyecto is not None else {}
        return armar(nombre, [], tareas, avisos=avisos)
    alm = almacen.Almacen(carpeta)
    tareas = tareas_de(proyecto) if proyecto is not None else _tareas_de_la_carpeta(carpeta,
                                                                                    avisos)
    if not alm.existe():
        avisos.append("Este repo todavía no tiene .cotejo/: no hay arquitectura que dibujar.")
        return armar(nombre, [], tareas, carpeta=carpeta, avisos=avisos)
    version = versiones.estado(carpeta).get("en_curso") or ""
    piezas = conocimiento.piezas_del_repo(alm, columnas=columnas_de(tareas), avisos=avisos,
                                          textos={i: t["texto"] for i, t in tareas.items()})
    return armar(nombre, piezas, tareas, version=version, carpeta=carpeta, avisos=avisos)
