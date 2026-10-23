"""El progreso del inicio (v1.3.0): de la bitácora a los cinco pasos de la pantalla Preparando.

El agente que prepara un proyecto nuevo (`tareas/inicio.py`) hace cinco cosas con `cotejo`, y
cada verbo deja una línea en la bitácora (`tareas/bitacora.py`): `init`, `editar`, `proponer` y
`anotar` con `anotar_verbo` (llevan `carpeta`), `crear` con la de siempre (lleva `proyecto` y
`nota`). Aquí esas líneas se traducen a lo que la persona entiende: los `PASOS` de `inicio.py`,
cada uno pendiente, en curso, hecho o con fallo, con su hora y un detalle corto en llano.
Sin GTK, sin red y sin escribir nada.

Tres piezas:

- `pasos(eventos, estado, ...)`: función pura. Recibe los eventos ya leídos (`eventos_de`) y,
  si se tiene, el estado de la preparación (`tareas.preparacion.estado`: el dict o solo su
  `estado`), y devuelve los cinco pasos en el orden de `PASOS`.
- `Seguimiento`: seguir la bitácora sin releerla. Cada `avanzar()` lee solo lo que se añadió
  desde la última vez (por offset) y se queda únicamente con las líneas de este proyecto; está
  hecha para llamarse cada segundo.
- `crudo(...)`: el registro en crudo para quien quiera verlo: las líneas de la bitácora tal cual
  y el final del `.log` del agente.

Qué cuenta para cada paso: `init`; `editar` solo si lo editado es el proyecto (`tipo:
proyecto`); `proponer` (cada decisión distinta); `anotar` solo de `arquitectura`; `crear` (cada
tarea distinta). Un verbo repetido no suma dos veces lo mismo (el agente reintenta). Los pasos
pueden llegar desordenados: el que sigue al más avanzado es el que está en curso, los que
tienen líneas están hechos y los demás, pendientes. Si la preparación terminó bien, nada queda en
curso; si se colgó o falló, el paso en curso pasa a fallo.
"""

import json
import os

from . import bitacora
from .inicio import PASOS

PENDIENTE, EN_CURSO, HECHO, FALLO = "pendiente", "en curso", "hecho", "fallo"
ESTADOS_CON_FALLO = ("colgado", "fallo")
LINEAS_CRUDAS = 200


def _mismo_sitio(a, b):
    try:
        return os.path.realpath(a) == os.path.realpath(b)
    except (OSError, ValueError):
        return False


def _paso_de(linea, carpeta):
    """El índice del paso al que cuenta esta línea (ya parseada) del proyecto `carpeta`, o None."""
    operacion = linea.get("operacion")
    verbos = [p.verbo for p in PASOS]
    if operacion not in verbos:
        return None
    if operacion == "crear":
        # La línea de `crear` no lleva carpeta: sí el nombre del proyecto y el archivo de
        # sus tareas en la fuente repo (`<nombre>/.cotejo/tareas.md`).
        nombre = os.path.basename(os.path.normpath(carpeta))
        if linea.get("proyecto") != nombre or not str(linea.get("nota", "")).startswith(
                nombre + "/.cotejo/"):
            return None
    elif not _mismo_sitio(linea.get("carpeta", ""), carpeta):
        return None
    if operacion == "editar" and linea.get("tipo") != "proyecto":
        return None
    if operacion == "anotar" and linea.get("tipo") != "arquitectura":
        return None
    return verbos.index(operacion)


def _evento(texto, carpeta, desde):
    try:
        linea = json.loads(texto)
    except ValueError:
        return None
    if not isinstance(linea, dict) or not isinstance(linea.get("cuando"), int):
        return None
    if linea["cuando"] < desde:
        return None
    indice = _paso_de(linea, carpeta)
    return None if indice is None else {**linea, "paso": indice}


def eventos_de(lineas, carpeta, desde=0):
    """De las líneas de la bitácora (texto), los eventos del proyecto de `carpeta` desde `desde`
    (segundos; el momento en que se lanzó el agente). Las rotas o ajenas se saltan."""
    hechos = (_evento(texto, carpeta, desde) for texto in lineas)
    return [e for e in hechos if e is not None]


def _identidad(evento):
    return evento.get("id") or evento.get("entrada") or evento["cuando"]


def _plural(n, uno, varios):
    return f"{n} {uno if n == 1 else varios}"


def _detalle(verbo, eventos):
    n = len({_identidad(e) for e in eventos})
    if verbo == "init":
        return ("Carpeta creada y preparada" if any(e.get("git_init") for e in eventos)
                else "Carpeta preparada")
    if verbo == "editar":
        return "Proyecto escrito" + (f" ({n} versiones)" if n > 1 else "")
    if verbo == "proponer":
        return _plural(n, "decisión propuesta", "decisiones propuestas")
    if verbo == "anotar":
        piezas = max((e.get("piezas") or 0 for e in eventos), default=0)
        return "Arquitectura anotada" + (f": {_plural(piezas, 'pieza', 'piezas')}"
                                         if piezas else "")
    return _plural(n, "tarea creada", "tareas creadas")


def _estado_de(estado):
    return estado.get("estado") if isinstance(estado, dict) else estado


def pasos(eventos, estado=None, desde=0, ahora=None):
    """Los cinco pasos con su estado, hora y detalle. Pura: no lee ni escribe nada.

    `estado` es el de la preparación (`tareas.preparacion.estado`, o solo su `estado`:
    «preparando», «colgado», «listo», «fallo»); sin él, se asume que el agente sigue. `desde`
    es la hora en que se lanzó (el inicio del primer paso) y `ahora`, con la que se mide la
    duración de lo que sigue en curso.

    Cada paso es un dict: `verbo`, `titulo`, `estado` (pendiente | en curso | hecho | fallo),
    `inicio` y `fin` (segundos, o None), `duracion` (segundos, o None), `detalle` (en llano) y
    `n` (cuántos hechos distintos lleva). El inicio de un paso es cuando acabó lo anterior
    (la bitácora anota al terminar cada verbo), así que la duración es lo que tardó el agente
    en hacerlo.
    """
    por_paso = [[e for e in eventos if e["paso"] == i] for i in range(len(PASOS))]
    avanzado = max((i for i, es in enumerate(por_paso) if es), default=-1)
    nivel = _estado_de(estado)
    # El paso que el agente tiene entre manos: el que sigue al más avanzado (o el último, si
    # ya hay tareas). Al terminar bien no queda ninguno.
    en_curso = None if nivel == "listo" else min(avanzado + 1, len(PASOS) - 1)
    por_que = (estado.get("por_que") or "") if isinstance(estado, dict) else ""
    salida = []
    for i, (paso, es) in enumerate(zip(PASOS, por_paso)):
        if i == en_curso:
            situacion = FALLO if nivel in ESTADOS_CON_FALLO else EN_CURSO
        else:
            situacion = HECHO if es else PENDIENTE
        primero = min((e["cuando"] for e in es), default=None)
        previas = [e["cuando"] for e in eventos if e["paso"] != i and
                   (primero is None or e["cuando"] <= primero)]
        inicio = max(previas, default=desde or None)
        if situacion == PENDIENTE:
            inicio = None
        fin = max(e["cuando"] for e in es) if situacion == HECHO else None
        duracion = None
        if situacion == HECHO and inicio is not None:
            duracion = max(0, fin - inicio)
        elif situacion == EN_CURSO and inicio is not None and ahora is not None:
            duracion = max(0, int(ahora) - inicio)
        detalle = _detalle(paso.verbo, es) if es else ""
        if situacion == EN_CURSO and not es:
            detalle = "En marcha"
        elif situacion == FALLO:
            detalle = por_que or detalle or "Se detuvo en este paso"
        salida.append({"verbo": paso.verbo, "titulo": paso.titulo, "estado": situacion,
                       "inicio": inicio, "fin": fin, "duracion": duracion, "detalle": detalle,
                       "n": len({_identidad(e) for e in es})})
    return salida


class Seguimiento:
    """Sigue la bitácora de un proyecto leyendo solo lo nuevo (por offset).

    `Seguimiento(carpeta, desde)`; luego `avanzar()` cada segundo (devuelve True si llegó algo
    de este proyecto) y `pasos(estado, ahora)` / `crudo(registro)` para pintar. La primera
    lectura mira la cola del archivo (`bitacora.COLA_BYTES`), no todo; las siguientes, solo lo
    que creció. Una línea a medio escribir se deja para la próxima vez. Si el archivo se vació
    o se rotó, empieza de nuevo.
    """

    def __init__(self, carpeta, desde=0, archivo=None):
        self.carpeta = os.path.normpath(str(carpeta))
        self.desde = int(desde or 0)
        self.archivo = archivo
        self.offset = None
        self.crudas = []     # las líneas de este proyecto, tal cual
        self.eventos = []

    def _ruta(self):
        return self.archivo or bitacora.ARCHIVO

    def avanzar(self):
        try:
            with open(self._ruta(), "rb") as f:
                tamano = f.seek(0, os.SEEK_END)
                if self.offset is None:
                    self.offset = max(0, tamano - bitacora.COLA_BYTES)
                    if self.offset:
                        f.seek(self.offset - 1)
                        previo = f.read(1)
                        if previo != b"\n":  # cayó a mitad de línea: esa se descarta entera
                            f.readline()
                            self.offset = f.tell()
                elif tamano < self.offset:
                    self.offset = 0
                    self.crudas, self.eventos = [], []
                f.seek(self.offset)
                datos = f.read()
        except OSError:
            return False
        completo = datos.rfind(b"\n") + 1  # solo hasta la última línea terminada
        self.offset += completo
        cambio = False
        for linea in datos[:completo].decode("utf-8", "replace").splitlines():
            evento = _evento(linea, self.carpeta, self.desde)
            if evento is not None:
                self.crudas.append(linea)
                self.eventos.append(evento)
                cambio = True
        return cambio

    def pasos(self, estado=None, ahora=None):
        return pasos(self.eventos, estado, self.desde, ahora)

    def crudo(self, registro=None, lineas=LINEAS_CRUDAS):
        return crudo(self.crudas, registro, lineas)


def de_preparacion(registro, archivo=None):
    """Un `Seguimiento` para el registro de una preparación (`tareas.preparacion.leer`)."""
    return Seguimiento(registro.get("carpeta", ""), registro.get("ts", 0), archivo)


def crudo(crudas, registro=None, lineas=LINEAS_CRUDAS):
    """El registro en crudo: `{"bitacora": [líneas tal cual], "log": final del .log}`.

    `log` es el texto de `preparacion.cola_del_log(registro)`; sin registro, vacío.
    """
    log = ""
    if registro:
        from . import preparacion
        log = preparacion.cola_del_log(registro)
    return {"bitacora": list(crudas[-lineas:]), "log": log}
