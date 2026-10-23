"""«Revisar el plan» (v1.3.0, cotejo-m195bn): el final del inicio, sin GTK.

Cuando el agente termina de preparar un proyecto, la pantalla Preparando ofrece «Revisar el
plan». Esto es lo que esa pantalla enseña y lo que hacen sus botones; la pantalla
(`tareas/app/revisar_plan.py`) solo pinta y llama aquí. Junta lo que ya existe y no lo repite:

- **El objetivo y el siguiente paso** salen de la entrada `proyecto` del almacén, con el mismo
  partidor que usa `contexto` (`conocimiento._secciones_proyecto`).
- **Las decisiones** son las del almacén. Aceptar es `decision.aceptar`, lo mismo que el botón
  de la carta de *Para comprobar*; «Cambiar» es `decision.rechazar` con motivo (decidido en el
  planning de la fase 2: rechazarla con un motivo que vuelve al agente). Las dos son de la
  persona: no hay verbo de CLI ni tool de MCP para ninguna.
- **El motivo vuelve al agente** con `enrutador.preparar.rehacer`: la misma preparación (id,
  cliente, modelo, entorno) relanzada con el prompt de `inicio.armar_rehacer`, y la pantalla
  vuelve a Preparando.
- **Las tareas de la 0.1.0**, con quién las haría según el enrutador (`decision.de_tarea`, como
  `cotejo plan`): las del nivel humano (n0) salen marcadas «tú».
- **«Empezar la 0.1.0»** (`empezar`) reparte como `cotejo plan`: a cada tarea pendiente sin
  dueño le pone el modelo que propone el enrutador —o `persona` si es del nivel humano— con la
  misma escritura verificada que `asignar`. No despacha ni lanza nada: lo que se lance lo
  elige la persona después, con el maestro o a mano.

Las tareas se leen y escriben con la fuente repo apuntada **solo** a la carpeta del proyecto:
el agente las creó así (`inicio.ENTORNO`), y la fuente activa de la persona puede ser otra.
`tareas` no importa el enrutador al cargarse: se importa dentro de cada función.
"""

from dataclasses import dataclass, field
from pathlib import Path

from . import almacen, bitacora, conocimiento, decision
from .fuentes.repo import Repo

VERSION = "v0.1.0"
TU = "tú"


@dataclass
class Plan:
    """Todo lo que la pantalla pinta, ya en llano."""
    id: str = ""
    proyecto: str = ""
    carpeta: str = ""
    objetivo: str = ""
    siguiente_paso: str = ""
    decisiones: list = field(default_factory=list)   # {id, titulo, texto, estado, version}
    tareas: list = field(default_factory=list)       # {id, texto, quien, tuya, modelo, ...}
    avisos: list = field(default_factory=list)

    @property
    def por_aceptar(self):
        return sum(1 for d in self.decisiones if d["estado"] == "propuesta")

    @property
    def cabecera_decisiones(self):
        n = self.por_aceptar
        if not self.decisiones:
            return "Sin decisiones propuestas"
        if n == 0:
            return "Todas las decisiones revisadas"
        return ("1 decisión espera tu visto bueno" if n == 1
                else f"{n} decisiones esperan tu visto bueno")


def _almacen(carpeta):
    return almacen.Almacen(carpeta)


def fuente_del_proyecto(carpeta):
    """La fuente repo con solo esta carpeta, sin mirar la config ni `COTEJO_REPOS`."""
    fuente = Repo({"repos": [str(carpeta)]})
    fuente.repos = [Path(carpeta)]
    fuente.raiz = None
    return fuente


def _reglas():
    from enrutador import config as cfg, niveles, reglas
    config = cfg.cargar()
    humano, nivel = reglas.cargar(config.get("reglas_extra"), config.get("reglas_apagadas"))
    return {"reglas_humano": humano, "reglas_nivel": nivel,
            "niveles_extra": niveles.personalizados(config.get("modelos")),
            "alias_persona": config.get("alias_persona")}


def _decidir(tarea, reglas):
    from enrutador import decision as decidir
    return decidir.de_tarea({"texto": tarea.texto, "agente": tarea.agente,
                             "dificultad": tarea.dificultad}, **reglas)


def _de_la_version(tarea):
    """¿Es de la 0.1.0? Las que no dicen versión también cuentan: en un proyecto recién
    preparado no hay otra."""
    version = tarea.version_del_texto
    return not version or version == VERSION


def _tareas(carpeta, reglas, avisos):
    fuente = fuente_del_proyecto(carpeta)
    proyectos = fuente.escanear(incluir_hechas=False, avisos=avisos)
    salida = []
    for proyecto in proyectos:
        for tarea in proyecto.tareas:
            if _de_la_version(tarea):
                salida.append((fuente, proyecto, tarea, _decidir(tarea, reglas)))
    return salida


def _fila(tarea, elegida):
    tuya = not elegida.despachable
    return {"id": tarea.id, "texto": tarea.texto, "estado": tarea.estado,
            "agente": tarea.agente, "dificultad": tarea.dificultad, "tuya": tuya,
            "quien": TU if tuya else (tarea.agente or "agente"),
            "modelo": "" if tuya else elegida.nivel.modelo,
            "asignada": bool(tarea.agente)}


def leer(estado, reglas=None):
    """El `Plan` del proyecto de una preparación (`preparacion.estado`: id, proyecto, carpeta)."""
    carpeta = estado.get("carpeta") or ""
    plan = Plan(id=estado.get("id") or "", proyecto=estado.get("proyecto") or "",
                carpeta=carpeta)
    alm = _almacen(carpeta)
    try:
        cuerpo = alm.leer(almacen.ID_PROYECTO).cuerpo
    except (almacen.EntradaNoExiste, almacen.IdRepetido):
        cuerpo = ""
        plan.avisos.append("El agente no dejó el objetivo del proyecto.")
    campos = conocimiento._secciones_proyecto(cuerpo)
    plan.objetivo = campos["objetivo"]
    plan.siguiente_paso = campos["siguiente_paso"]
    for e in alm.entradas("decision", plan.avisos):
        if e.estado in ("propuesta", "aceptada", "rechazada"):
            plan.decisiones.append({"id": e.id, "titulo": e.titulo,
                                    "texto": e.cuerpo.strip(), "estado": e.estado,
                                    "version": e.version,
                                    "motivo": e.datos.get("motivo", "")})
    reglas = reglas if reglas is not None else _reglas()
    plan.tareas = [_fila(t, d) for _f, _p, t, d in _tareas(carpeta, reglas, plan.avisos)]
    return plan


def _sin_titulo(texto, titulo):
    """El cuerpo de una entrada empieza por su `# título`; en la pantalla sobra."""
    lineas = texto.splitlines()
    if lineas and lineas[0].lstrip("# ").strip() == titulo.strip():
        lineas = lineas[1:]
    return "\n".join(lineas).strip()


def resumen_decision(d):
    """El texto de una decisión para la pantalla, sin repetir su título."""
    return _sin_titulo(d.get("texto", ""), d.get("titulo", ""))


def aceptar(carpeta, decision_id, version):
    """Acepta una decisión propuesta (botón de la persona). Devuelve `(aceptada, reemplazada)`."""
    return decision.aceptar(_almacen(carpeta), decision_id, version)


def rechazar(estado, decision_id, version, motivo, al_terminar=None):
    """«Cambiar»: la deja `rechazada` con el motivo y relanza al agente con ese motivo para que
    proponga otra. Devuelve el `preparacion.estado` de la preparación relanzada.

    Si el agente no se puede relanzar (no está el cliente), la decisión queda rechazada igual
    —eso ya lo dijo la persona— y sale `NoSePuede` con el porqué, para enseñarlo.
    """
    from enrutador import preparar
    from . import inicio
    carpeta = estado.get("carpeta") or ""
    rechazada = decision.rechazar(_almacen(carpeta), decision_id, version, motivo)
    prompt = inicio.armar_rehacer(carpeta, rechazada.id, rechazada.titulo,
                                  rechazada.datos.get("motivo", ""))
    return preparar.rehacer(estado["id"], prompt, al_terminar=al_terminar,
                            motivo=rechazada.datos.get("motivo", ""))


def empezar(estado, reglas=None):
    """«Empezar la 0.1.0»: reparte como `cotejo plan`, sin lanzar nada.

    A cada tarea pendiente de la 0.1.0 **sin dueño** le pone quién la haría: el modelo que
    propone el enrutador, o `persona` si es del nivel humano. Lo que ya tiene dueño no se toca
    (lo eligió alguien). Escribe con la fuente, verificado, y deja la línea de `asignar` en la
    bitácora. Devuelve `[{id, agente}]` de lo asignado. Después la preparación se da por vista.
    """
    from enrutador import preparar
    from . import cli
    reglas = reglas if reglas is not None else _reglas()
    asignadas = []
    for fuente, proyecto, tarea, elegida in _tareas(estado.get("carpeta") or "", reglas, []):
        if tarea.agente or tarea.estado != "pendiente":
            continue
        quien = elegida.nivel.modelo if elegida.despachable else "persona"
        actual = cli.escribir(fuente.poner_agente, tarea, quien)
        bitacora.anotar("asignar", proyecto, actual, de="", a=quien)
        asignadas.append({"id": actual.id, "agente": quien})
    try:
        preparar.descartar(estado["id"])
    except (KeyError, ValueError):
        pass
    return asignadas
