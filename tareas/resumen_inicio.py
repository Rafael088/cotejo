"""Lo que enseña la pestaña Inicio del board (v1.3.0), sin GTK: el saludo, el resumen y una
tarjeta por proyecto.

El board (`tareas/app/pestana_inicio.py`) solo pinta lo que sale de aquí. Las funciones puras
(`saludo`, `titular`, `tarjeta`, `ordenar`) no tocan archivos; `tarjetas` es la única que lee,
y lo hace por la fuente (`carpeta_de`) y por el almacén `.cotejo/` del repo de cada proyecto:
la versión en curso (`version.estado`), el objetivo de `proyecto.md` y las piezas de la
arquitectura dibujable (`conocimiento.piezas_del_repo`).

El avance se cuenta en **piezas hechas** de la arquitectura, no en tareas: es lo que la
persona entiende como «cuánto de mi proyecto ya está». Un proyecto sin piezas no tiene avance
que enseñar y lo dice («sin arquitectura todavía»); no se inventa uno a partir de las tareas.
"""

from dataclasses import dataclass, field

from . import almacen, como_se_abre, conocimiento, modelo
from . import version as versiones

SIN_ARQUITECTURA = "sin arquitectura todavía"
AL_DIA = "al día"
POR_HACER = "por hacer"


@dataclass
class Tarjeta:
    """Una tarjeta de proyecto, ya lista para pintar."""

    nombre: str
    version: str = ""          # la versión en curso («0.1.0»), o "" si no se sabe
    objetivo: str = ""         # la primera línea del objetivo de `proyecto.md`, o ""
    por_comprobar: int = 0     # entregas que esperan a la persona
    sin_terminar: int = 0      # tareas que no están hechas (las de por comprobar incluidas)
    piezas: int = 0            # piezas de la arquitectura
    piezas_hechas: int = 0
    estados: list = field(default_factory=list)   # el estado de cada pieza, en orden
    carpeta: str = ""          # la carpeta principal del proyecto («Ver mi app»), o ""
    sin_app: bool = False      # todavía no hay código: «Ver mi app» se apaga hasta que lo haya

    @property
    def con_arquitectura(self):
        return self.piezas > 0

    @property
    def avance(self):
        """La fracción de piezas hechas (0 a 1), o None si no hay arquitectura."""
        return self.piezas_hechas / self.piezas if self.piezas else None

    @property
    def texto_avance(self):
        """«0.1.0 · 6 de 11 piezas», o «0.1.0 · sin arquitectura todavía»."""
        if self.piezas:
            unidad = "pieza" if self.piezas == 1 else "piezas"
            avance = f"{self.piezas_hechas} de {self.piezas} {unidad}"
        else:
            avance = SIN_ARQUITECTURA
        return f"{self.version} · {avance}" if self.version else avance

    @property
    def texto_estado(self):
        """El chip de la tarjeta: «2 por comprobar», «4 por hacer» o «al día».

        «Al día» es solo cuando no queda nada: ni entregas que comprobar ni tareas sin
        terminar. Antes lo decía un proyecto con cuatro tareas pendientes, al lado de
        «0 de 4 piezas» (v1.3.1).
        """
        if self.por_comprobar:
            return f"{self.por_comprobar} por comprobar"
        if self.sin_terminar:
            return f"{self.sin_terminar} {POR_HACER}"
        return AL_DIA


def saludo(hora):
    """«Buenos días», «Buenas tardes» o «Buenas noches» según la hora local (0–23)."""
    if 5 <= hora < 12:
        return "Buenos días"
    if 12 <= hora < 20:
        return "Buenas tardes"
    return "Buenas noches"


def _contar(n, singular, plural):
    return f"{n} {singular if n == 1 else plural}"


def titular(tarjetas):
    """La frase grande del Inicio: cuántos proyectos y cuántas entregas esperan.

    «Tienes 3 proyectos y 2 entregas por comprobar», «Tienes 1 proyecto y 4 tareas por hacer»,
    «Tienes 1 proyecto, todo al día» o, sin ninguno, «Todavía no tienes proyectos». «Todo al
    día» queda para cuando no hay ni entregas ni trabajo pendiente (v1.3.1): decirlo con
    tareas por hacer era lo que chocaba con «0 de 4 piezas».
    """
    if not tarjetas:
        return "Todavía no tienes proyectos"
    proyectos = _contar(len(tarjetas), "proyecto", "proyectos")
    esperan = sum(t.por_comprobar for t in tarjetas)
    if esperan:
        return f"Tienes {proyectos} y {_contar(esperan, 'entrega', 'entregas')} por comprobar"
    quedan = sum(t.sin_terminar for t in tarjetas)
    if quedan:
        return f"Tienes {proyectos} y {_contar(quedan, 'tarea', 'tareas')} {POR_HACER}"
    return f"Tienes {proyectos}, todo al día"


def repos_que_faltan(avisos):
    """Los avisos de repos de la lista que ya no existen, en llano, para el Inicio.

    Devuelve `(titulo, [detalle, ...])` o None si no falta ninguno. Cada detalle dice qué repo
    es y cómo arreglarlo; no hay verbo para quitarlo de la lista, y se dice así.
    """
    faltan = [a for a in (avisos or []) if isinstance(a, dict) and a.get("repo_falta")]
    if not faltan:
        return None
    titulo = (f"{_contar(len(faltan), 'repo de tu lista ya no existe', 'repos de tu lista ya no existen')}"
              ": se salta y el resto sigue funcionando")
    return titulo, [a["motivo"] for a in faltan]


def columnas_de(proyecto):
    """{id de tarea: columna} con las tareas que ya leyó la fuente (también las hechas).

    Es lo que `piezas_del_repo` necesita para dar estado a cada pieza; se arma con lo que el
    board ya tiene en memoria en vez de volver a leer `tareas.md`.
    """
    columnas = {}
    for numero, tarea in enumerate([*proyecto.tareas, *proyecto.hechas]):
        columnas[modelo.id_actual(tarea.id) or f"#{numero}"] = tarea.columna
    return columnas


def tarjeta(proyecto, version="", objetivo="", piezas=(), carpeta="", sin_app=False):
    """La tarjeta de un proyecto a partir de lo leído. `piezas` son los dicts de
    `conocimiento.piezas_del_repo` (con `estado`)."""
    estados = [p.get("estado", "falta") for p in piezas]
    return Tarjeta(
        nombre=proyecto.nombre,
        version=version or "",
        objetivo=(objetivo or "").strip().splitlines()[0] if (objetivo or "").strip() else "",
        por_comprobar=sum(1 for t in proyecto.tareas if t.estado == "por-validar"),
        sin_terminar=sum(1 for t in proyecto.tareas if t.estado != "hecha"),
        piezas=len(estados),
        piezas_hechas=sum(1 for e in estados if e == "hecho"),
        estados=estados,
        carpeta=str(carpeta or ""),
        sin_app=sin_app,
    )


def ordenar(tarjetas_):
    """Primero lo que espera a la persona; después, por nombre. El orden de la fuente
    (estado y prioridad del proyecto) se respeta dentro de cada grupo porque `sorted` es
    estable."""
    return sorted(tarjetas_, key=lambda t: 0 if t.por_comprobar else 1)


# --- con E/S (solo leer) ---------------------------------------------------------------------

def _del_almacen(carpeta, proyecto, avisos=None):
    """(versión, objetivo, piezas) del repo de `carpeta`. Lo que no esté, vacío: un repo sin
    `.cotejo/` o con un `proyecto.md` roto no es un error del Inicio."""
    alm = almacen.Almacen(carpeta)
    if not alm.existe():
        return "", "", []
    version = versiones.estado(carpeta).get("en_curso") or ""
    objetivo = ""
    try:
        entrada = alm.leer(almacen.ID_PROYECTO)
        objetivo = conocimiento._secciones_proyecto(entrada.cuerpo).get("objetivo", "")
    except (almacen.EntradaNoExiste, almacen.IdRepetido):
        pass
    textos = {modelo.id_actual(t.id): getattr(t, "nombre_corto", "") or getattr(t, "texto", "")
              for t in [*proyecto.tareas, *proyecto.hechas] if modelo.id_actual(t.id)}
    piezas = conocimiento.piezas_del_repo(alm, columnas=columnas_de(proyecto), avisos=avisos,
                                          textos=textos)
    return version, objetivo, piezas


def tarjetas(proyectos, fuente, avisos=None):
    """Una `Tarjeta` por proyecto, en el orden del Inicio.

    Entran los proyectos con tareas (como en la banda del board) y los que son un repo con
    `.cotejo/` aunque todavía no tengan ninguna: uno recién creado tiene que salir. Un error
    al leer el almacén de uno no tumba el Inicio: ese proyecto sale sin versión ni piezas.
    """
    resultado = []
    for proyecto in proyectos:
        carpeta = fuente.carpeta_de(proyecto.nombre)
        datos = ("", "", [])
        if carpeta:
            try:
                datos = _del_almacen(carpeta, proyecto, avisos)
            except Exception as error:   # noqa: BLE001 — el Inicio enseña lo que pueda
                if avisos is not None:
                    avisos.append({"nota": str(carpeta), "motivo": f"Inicio: {error}"})
        if not (proyecto.tareas or proyecto.hechas or datos != ("", "", [])):
            continue
        sin_app = False
        if carpeta:
            try:
                sin_app = como_se_abre.plan_de(carpeta).sin_app
            except Exception:   # noqa: BLE001 — un error aquí no debe tumbar el Inicio
                sin_app = False
        resultado.append(tarjeta(proyecto, *datos, carpeta=carpeta or "", sin_app=sin_app))
    return ordenar(resultado)
