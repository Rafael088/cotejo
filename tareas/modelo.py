"""Qué es una tarea y qué es un proyecto, sin que importe de dónde salieron.

Aquí no hay Markdown, ni `- [ ]`, ni tags, ni rutas de Obsidian: eso es de las fuentes
(`tareas/fuentes/`). Lo que vive aquí es lo único que el resto de Cotejo —el board, la CLI de
agentes, el resumen de la barra— necesita saber de una tarea: qué dice, en qué columna está,
quién la tiene y cómo se la nombra desde fuera.

La frontera importa porque el contrato con el agente cuelga de ella. Mientras «la tarea está en
curso» signifique «hay un `#en-curso` en su línea», Cotejo solo sirve para un vault de Obsidian
con `01-Proyectos/`, y cada segundo cerebro nuevo obliga a reprogramar al agente. Con el modelo
en medio, los tags pasan a ser un detalle de cómo la fuente Obsidian guarda las cosas, y Logseq,
una carpeta de Markdown pelada o Todoist son adaptadores en vez de reescrituras.
"""

import time
from dataclasses import dataclass, field
from datetime import date

from . import version as versiones

PENDIENTE = "pendiente"
HECHA = "hecha"

# Las cuatro columnas, en orden. La última la escribe solo una persona: si el agente pudiera
# marcar hecha la suya, «hecha» dejaría de significar «alguien la revisó».
COLUMNAS = (
    (PENDIENTE, "Pendiente"),
    ("en-curso", "Haciéndola"),
    ("por-validar", "Para comprobar"),
    (HECHA, "Finalizada"),
)
# Los modelos personalizados se añaden desde la configuración del enrutador. `persona` es el
# destino humano y no identifica al usuario que instaló Cotejo.
AGENTES = ("opus", "sonnet", "haiku", "persona")

ORDEN_ESTADO = {"activo": 0, "idea": 1, "pausado": 2}

# Las marcas nacían `foco-…` cuando el producto se llamaba Foco, y la migración del 2026-09-26
# las pasó a `cotejo-…`. Quien todavía nombre una tarea por el id de antes —una evidencia, un
# despacho viejo, una sesión que ya la tenía, la bitácora— tiene que seguir llegando a ella.
PREFIJO_VIEJO = "foco-"
PREFIJO = "cotejo-"


def id_actual(tarea_id):
    """El id con el prefijo de ahora: `foco-a1b2c3` → `cotejo-a1b2c3`. Los demás, tal cual."""
    tarea_id = str(tarea_id or "")
    if tarea_id.startswith(PREFIJO_VIEJO):
        return PREFIJO + tarea_id[len(PREFIJO_VIEJO):]
    return tarea_id
ORDEN_PRIORIDAD = {"alta": 0, "media": 1, "baja": 2}


class TareaCambiada(Exception):
    """La tarea ya no está como cuando se leyó: alguien la editó por fuera.

    La levanta la fuente antes de escribir. Es lo que evita pisar trabajo ajeno en silencio,
    así que ninguna fuente debería escribir sin poder levantarla.
    """


class NoSeCreaAqui(Exception):
    """La fuente no puede anotar una tarea nueva en ese proyecto, y el mensaje dice por qué.

    No es lo mismo que una fuente que no sabe crear (`NotImplementedError`): esta sí sabe,
    pero ese proyecto no tiene un sitio donde la tarea vaya sin que la fuente se lo invente
    —en Obsidian, una carpeta suelta como el Inbox, que no tiene nota principal—.
    """


class FuenteNoResponde(Exception):
    """La fuente no contestó, o contestó algo que no se entiende: la app de fuera no está, se
    cayó la red, el token caducó. No se escribió nada, y el mensaje dice qué mirar.

    Es distinto de `TareaCambiada`: ahí se leyó bien y alguien se adelantó; aquí no se pudo
    ni leer. `reintentable` dice si tiene sentido repetir sin cambiar nada (la red, un límite
    de peticiones) o si antes hay que arreglar algo (un token, una base que no existe).
    """

    def __init__(self, mensaje, salida="", reintentable=False):
        super().__init__(mensaje)
        self.salida = salida
        self.reintentable = reintentable


class IdAmbiguo(Exception):
    """Dos tareas responden al mismo id.

    Quedarse con la primera sería escribir en la tarea equivocada sin que nadie se entere, que
    es la peor forma de fallar. El mensaje lleva dónde están las candidatas.
    """


_MAX_ANTES = 80
_MAX_NOMBRE = 60


def _cortar(texto, tope=_MAX_NOMBRE):
    """Corta en palabra con «…» si pasa de `tope`."""
    texto = texto.strip()
    if len(texto) <= tope:
        return texto
    corte = texto[:tope].rsplit(" ", 1)[0].rstrip(" ,;:.") or texto[:tope]
    return corte + "\u2026"


def partes_de_tarea(texto, version=""):
    """(version, nombre, descripcion) derivados del texto de una tarea; no se guardan.

    «v1.2.4 · CotejoBoard 7.3.2 · Nombre: descripción». La versión es `version` —la del campo
    de la tarea, que la fuente sacó de su tag (`#v1.2.4` en Obsidian)— o, si no trae, la del
    prefijo `vX.Y.Z ·` del texto; las dos pasan por `version.de_tarea`, el único parser. El
    prefijo se quita del nombre aunque gane el campo. El nombre es el último segmento antes de
    los primeros «: » (los de «https://» no cuentan); sin dos puntos, las primeras palabras
    (~60 caracteres) y la descripción es el texto entero.
    """
    texto = " ".join((texto or "").split())
    prefijo = ""
    resto = texto
    primero, sep, despues = texto.partition(" \u00b7 ")
    if sep and primero.startswith("v") and versiones.de_tarea(primero):
        prefijo, resto = primero, despues
    version = versiones.de_tarea(version) or versiones.de_tarea(prefijo) or ""
    i = resto.find(": ")
    if 0 < i <= _MAX_ANTES:
        nombre = resto[:i].split(" \u00b7 ")[-1].strip()
        descripcion = resto[i + 2:].strip()
        if nombre:
            return version, _cortar(nombre), descripcion
    # Sin dos puntos, el contexto que sigue a la versión («CotejoBoard 7.3.2 · Probar…») tampoco
    # es el nombre. Solo tras una versión: en un texto suelto, un « · » puede ser parte de la frase.
    nombre = resto.split(" \u00b7 ")[-1].strip() if prefijo else ""
    return version, _cortar(nombre or resto), resto


@dataclass
class Tarea:
    """Una tarea, como la ve todo el mundo menos su fuente.

    `sitio` es lo único que no se mira desde fuera: es lo que la fuente necesita para volver a
    encontrar esta tarea y comprobar que sigue igual (para Obsidian, la nota, la línea y su
    texto exacto). Es opaco a propósito — quien lo inspeccione está haciendo suposiciones sobre
    una fuente concreta, que es justo lo que esta capa existe para impedir.
    """

    texto: str
    id: str = ""  # cómo se nombra desde fuera; lo pone la fuente y no se construye a mano
    donde: str = ""  # dónde vive, en los términos de su fuente ("01-Proyectos/Cotejo.md")
    sub: str = ""  # etiqueta corta si no vive en el sitio principal del proyecto
    estado: str = PENDIENTE  # pendiente | en-curso | por-validar
    agente: str = ""  # quién la tiene asignada
    dificultad: str = ""  # facil | medio | dificil
    # La versión a la que pertenece ("v1.2.4" o "v1.2", normalizada por `version.de_tarea`), o
    # "" si su fuente no le da ninguna: en Obsidian, el tag `#v1.2.4`, que se lee como
    # `#agente/…`. Clave que se agrega (v1.2.4). Para saber de qué versión es una tarea se mira
    # `version_del_texto`, que además cuenta el prefijo `v1.2.4 ·` de antes.
    version: str = ""
    hecha: bool = False
    # Fecha de cierre ("AAAA-MM-DD"), o None si la línea no trae una. Solo Obsidian (y repo.py,
    # que hereda su parser) la rellena hoy, leyendo el "— AAAA-MM-DD" que `marcar` escribe; una
    # fuente externa la deja en None si su adaptador no la da. Es una clave que se agrega al
    # modelo, no una que lo cambia: nadie más la miraba antes de v1.2.2.
    cerrada: str = None
    sitio: object = None

    @property
    def columna(self):
        return HECHA if self.hecha else self.estado

    @property
    def version_del_texto(self):
        """La versión a la que pertenece: la del campo o, sin él, la del prefijo del texto. Es
        la que filtra `tareas --version`, la que agrupa el board y la que sale en el JSON."""
        return self.partes[0]

    @property
    def nombre_corto(self):
        return self.partes[1]

    @property
    def descripcion(self):
        return self.partes[2]

    @property
    def partes(self):
        return partes_de_tarea(self.texto, self.version)


@dataclass
class Proyecto:
    nombre: str
    donde: str = ""  # dónde vive el proyecto en su fuente
    estado: str = ""
    prioridad: str = ""
    tareas: list = field(default_factory=list)  # las que faltan
    hechas: list = field(default_factory=list)  # solo se llenan si se piden

    @property
    def orden(self):
        return (
            ORDEN_ESTADO.get(self.estado, 3),
            ORDEN_PRIORIDAD.get(self.prioridad, 3),
            self.nombre.lower(),
        )


def buscar(proyectos, tarea_id):
    """La tarea con ese id y su proyecto, o (None, None). Toda escritura entra por aquí.

    El id llega ya normalizado por la fuente: cómo se escribe una referencia a una tarea
    (con `^` delante, con prefijo, en mayúsculas) es cosa suya.
    """
    encontradas = [(proyecto, tarea) for proyecto in proyectos
                   for tarea in list(proyecto.tareas) + list(proyecto.hechas)
                   if tarea.id == tarea_id]
    if not encontradas and tarea_id:
        # Por el id de antes de migrar, o por el de después en un vault sin migrar.
        actual = id_actual(tarea_id)
        encontradas = [(proyecto, tarea) for proyecto in proyectos
                       for tarea in list(proyecto.tareas) + list(proyecto.hechas)
                       if tarea.id != tarea_id and id_actual(tarea.id) == actual]
    if len(encontradas) > 1:
        raise IdAmbiguo(", ".join(sorted({t.donde for _, t in encontradas})))
    return encontradas[0] if encontradas else (None, None)


def resumen(proyectos):
    """Conteo para la barra. `pendientes` es todo lo no marcado; los otros son subconjuntos."""
    datos = {"pendientes": 0, "en_curso": 0, "por_validar": 0, "hechas": 0, "proyectos": 0,
             "top": []}
    for proyecto in proyectos:
        datos["hechas"] += len(proyecto.hechas)
        if not proyecto.tareas:
            continue
        datos["proyectos"] += 1
        datos["pendientes"] += len(proyecto.tareas)
        datos["en_curso"] += sum(1 for t in proyecto.tareas if t.estado == "en-curso")
        datos["por_validar"] += sum(1 for t in proyecto.tareas if t.estado == "por-validar")
        datos["top"].append({"nombre": proyecto.nombre, "pendientes": len(proyecto.tareas)})
    # Los proyectos ya vienen ordenados por estado y prioridad: los primeros son los que importan.
    datos["top"] = datos["top"][:4]
    return datos


# El filtro de fechas de la columna Finalizada (CotejoBoard, v1.2.2): `clave` es lo que se
# guarda en `board.json` y `dias` la ventana que se le abre a `en_filtro_finalizada` — None en
# "todas" quiere decir que no hay ventana, no que sean "muchos días". Es una tupla y no un
# dict porque el board también necesita el orden en que se enseñan las opciones.
FILTROS_FINALIZADA = (
    ("hoy", "Hoy", 1),
    ("7-dias", "7 días", 7),
    ("30-dias", "30 días", 30),
    ("todas", "Todas", None),
)
FILTRO_FINALIZADA_DEFECTO = "7-dias"
_DIAS_FILTRO_FINALIZADA = {clave: dias for clave, _nombre, dias in FILTROS_FINALIZADA}


def hoy_local():
    """La fecha de hoy, en el mismo formato que escribe `marcar` ("AAAA-MM-DD")."""
    return time.strftime("%Y-%m-%d")


def en_filtro_finalizada(cerrada, filtro, hoy=None):
    """Si una tarea finalizada con fecha de cierre `cerrada` entra en `filtro`.

    La ventana son los últimos N días contando con hoy, no la semana o el mes de calendario:
    "7 días" es hoy y los 6 anteriores. "Todas" no filtra nada, ni siquiera las que no traen
    fecha —son justo las únicas que solo aparecen ahí, porque no hay ventana donde ponerlas—.
    `hoy` se inyecta para las pruebas; sin él, la fecha local de hoy (`hoy_local`).
    """
    dias = _DIAS_FILTRO_FINALIZADA.get(filtro, _DIAS_FILTRO_FINALIZADA[FILTRO_FINALIZADA_DEFECTO])
    if dias is None:
        return True
    if not cerrada:
        return False
    try:
        fecha = date.fromisoformat(cerrada)
        referencia = date.fromisoformat(hoy) if hoy else date.fromisoformat(hoy_local())
    except ValueError:
        return False
    return 0 <= (referencia - fecha).days < dias


def aviso_comprobar_a_mano(tarea, destino, alias_persona=("persona",)):
    """Por qué una persona no puede pasar esta tarea a Para comprobar con la mano (cotejo-2sxw7p),
    en llano; "" si puede.

    A *Para comprobar* solo se llega cuando el agente asignado entrega. Pasar a mano una tarea
    de un agente desde Pendiente o Haciendo dejaría esa columna diciendo «entregada» sobre algo
    que nadie entregó, sin evidencia que revisar. Una tarea de una persona o sin asignar sí se
    mueve: quien la hace es quien la mueve.
    """
    if destino != "por-validar" or tarea.columna not in (PENDIENTE, "en-curso"):
        return ""
    if not tarea.agente or tarea.agente in alias_persona:
        return ""
    quien = alias_persona[0] if alias_persona else "persona"
    return (f"No se puede pasar a Para comprobar a mano: está asignada a {tarea.agente} y solo "
            f"llega ahí cuando {tarea.agente} la entrega. Si la vas a hacer tú, asígnala a "
            f"«{quien}» y luego muévela.")
