"""El verbo `cotejo version [--proyecto] [--siguiente X.Y.Z]` (v1.2.4).

Sin `--siguiente` solo lee: la publicada (último tag), la en curso, las tareas de la en curso
por estado y lo aprobado desde el último tag. Con `--siguiente` escribe `version:` en el
`proyecto.md` del repo —por `tareas/version.py` y el almacén, con su `version`/hash— y nada
más. Es planear, no aprobar: por eso lo puede hacer un agente. Las reglas de las versiones
viven en `tareas/version.py`; aquí solo está cómo se llega al repo y cómo se cuenta.

Qué repo: con `--proyecto`, su carpeta (la de `enrutador.proyectos` en la config o, si no está,
`Fuente.carpeta_de`, que es como `despachar` sabe dónde crear el worktree); sin él, el repo
donde se está (`git rev-parse --show-toplevel`).

Lo aprobado desde el último tag: las tareas finalizadas de la versión en curso cuya fecha de
cierre (`— AAAA-MM-DD`) es **posterior** a la fecha del commit del último tag (las cerradas el
mismo día del tag se dan por incluidas en él). Sin tag, todas las finalizadas de esa versión.
Con tag, las finalizadas sin fecha no se pueden situar y se cuentan aparte (`sin_fecha`).
"""

import subprocess
from pathlib import Path

from . import almacen, version as versiones
from .cli import ESQUEMA, ErrorCLI, cargar, imprimir
from .modelo import HECHA

ESTADOS = ("pendiente", "en-curso", "por-validar", HECHA)


def _git(carpeta, *args):
    try:
        hecho = subprocess.run(versiones.comando_git(carpeta, *args), stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    texto = hecho.stdout.strip()
    return texto if hecho.returncode == 0 and texto else None


def _raiz_de(carpeta):
    """La raíz del repo que contiene `carpeta`, o None si no está en uno."""
    if not Path(carpeta).is_dir():
        return None
    raiz = _git(carpeta, "rev-parse", "--show-toplevel")
    return Path(raiz) if raiz else None


def _mismo(a, b):
    try:
        return Path(a).expanduser().resolve() == Path(b).expanduser().resolve()
    except OSError:
        return False


def _carpeta_del_proyecto(proyecto):
    """Dónde vive el repo de `proyecto`: la config del enrutador y, si no, la fuente."""
    from enrutador import config as cfg
    try:
        propia = cfg.directorio_de(cfg.cargar(), proyecto)
    except cfg.ConfigInvalida:
        propia = None
    return propia


def _resolver(args):
    """`(raiz, proyecto o None, proyectos, avisos)` según `--proyecto` o el repo actual."""
    fuente, proyectos, avisos = cargar()
    if args.proyecto:
        pedido = args.proyecto.strip().lower()
        proyecto = next((p for p in proyectos if p.nombre.lower() == pedido), None) or \
            next((p for p in proyectos if pedido in p.nombre.lower()), None)
        if proyecto is None:
            raise ErrorCLI(f"No hay ningún proyecto «{args.proyecto}»",
                           "`cotejo estado` lista los proyectos; usa el nombre tal cual.")
        carpeta = _carpeta_del_proyecto(proyecto.nombre) or fuente.carpeta_de(proyecto.nombre)
        if not carpeta:
            raise ErrorCLI(f"«{proyecto.nombre}» no tiene carpeta de repo",
                           "Dile dónde está en la config (enrutador.proyectos) o usa la fuente "
                           "`repo`; sin carpeta no hay tags de donde sacar la versión.")
        raiz = _raiz_de(carpeta)
        if raiz is None:
            raise ErrorCLI(f"«{carpeta}» no es un repo de git",
                           f"Revisa la carpeta de «{proyecto.nombre}» en la config.")
        return raiz, proyecto, proyectos, avisos
    raiz = _raiz_de(Path.cwd())
    if raiz is None:
        raise ErrorCLI("No estás dentro de un repo git",
                       "Corre `cotejo version` dentro de un repo, o pasa --proyecto.")
    # El proyecto del repo donde se está: el que apunta a esta carpeta (o al repo principal,
    # si se está en un worktree). Sin él se da la versión igual, sin tareas.
    comun = _git(raiz, "rev-parse", "--path-format=absolute", "--git-common-dir")
    candidatos = [raiz] + ([Path(comun).parent] if comun else [])
    for proyecto in proyectos:
        carpeta = _carpeta_del_proyecto(proyecto.nombre) or fuente.carpeta_de(proyecto.nombre)
        if carpeta and any(_mismo(carpeta, c) for c in candidatos):
            return raiz, proyecto, proyectos, avisos
    return raiz, None, proyectos, avisos


def _fecha_del_tag(raiz, tag):
    return _git(raiz, "log", "-1", "--format=%cs", tag) if tag else None


def contar(proyecto, en_curso, fecha_tag, hay_tag):
    """Las tareas de `en_curso` por estado y las aprobadas desde el último tag."""
    por_estado = dict.fromkeys(ESTADOS, 0)
    aprobadas, sin_fecha, sin_version = [], 0, 0
    if proyecto is None:
        return None, {"desde": fecha_tag, "total": 0, "tareas": [], "sin_fecha": 0}
    for tarea in [*proyecto.tareas, *proyecto.hechas]:
        propia = tarea.version_del_texto
        if not propia:
            sin_version += 1
        if not en_curso or not versiones.pertenece(propia, en_curso):
            continue
        por_estado[tarea.columna] = por_estado.get(tarea.columna, 0) + 1
        if tarea.columna != HECHA:
            continue
        if not hay_tag or (tarea.cerrada and fecha_tag and tarea.cerrada > fecha_tag):
            aprobadas.append({"id": tarea.id, "tarea": tarea.nombre_corto,
                              "cerrada": tarea.cerrada})
        elif hay_tag and not tarea.cerrada:
            sin_fecha += 1
    tareas = {**por_estado, "total": sum(por_estado.values()), "sin_version": sin_version}
    return tareas, {"desde": fecha_tag, "total": len(aprobadas), "tareas": aprobadas,
                    "sin_fecha": sin_fecha}


def validar_siguiente(texto, en_curso, declarada=None):
    """La `Semver` que se puede escribir como siguiente, o ErrorCLI con el porqué.

    Solo una menor o una mayor por encima de la en curso: el parche lo calcula Cotejo solo
    cuando el tag alcanza la declarada, y bajar la versión no es planear. Pedir la que ya está
    escrita y en curso no es un error: repetir el comando no hace nada.
    """
    nueva = versiones.parsear(texto)
    if nueva is None:
        raise ErrorCLI(f"«{texto}» no es una versión", "Usa X.Y.Z, por ejemplo 1.3.0 o 2.0.0.")
    if en_curso is None:
        raise ErrorCLI("El proyecto no tiene versión en curso",
                       "`cotejo init` le pone `version:` en proyecto.md; después, --siguiente.")
    base = versiones.parsear(en_curso)
    if nueva.parche != 0:
        raise ErrorCLI(f"{nueva} es un parche",
                       "--siguiente solo sube la menor (X.Y.0) o la mayor (X.0.0); el parche "
                       "lo calcula Cotejo cuando el último tag alcanza la versión.")
    if nueva == base and versiones.parsear(declarada) == nueva:
        return nueva
    if nueva <= base:
        raise ErrorCLI(f"{nueva} no sube la versión en curso ({base})",
                       "Tiene que ser mayor: la siguiente menor o la siguiente mayor.")
    return nueva


def escribir_siguiente(raiz, nueva):
    """Escribe `version:` en proyecto.md por el almacén. Devuelve lo que hizo."""
    alm = almacen.Almacen(raiz)
    declarada, _ = versiones.declarada(raiz)
    if declarada == nueva:
        return "ya-estaba"
    try:
        try:
            entrada = alm.leer(almacen.ID_PROYECTO)
        except almacen.EntradaNoExiste:
            entrada = alm.crear("proyecto", raiz.name)
        alm.reescribir(almacen.ID_PROYECTO, entrada.version, campos={versiones.CLAVE: str(nueva)})
    except almacen.EntradaCambiada as error:
        raise ErrorCLI("proyecto.md cambió mientras se escribía",
                       "Nada se escribió; vuelve a correr el comando.", reintentable=True) \
            from error
    except (almacen.NoSeEdita, almacen.IdRepetido, almacen.FrontmatterRoto) as error:
        raise ErrorCLI(f"No se pudo escribir proyecto.md: {error}",
                       "Míralo con `cotejo doctor`.") from error
    return "escrita"


def cmd_version(args):
    raiz, proyecto, proyectos, avisos = _resolver(args)
    hecho = None
    if args.siguiente:
        antes = versiones.estado(raiz)
        hecho = escribir_siguiente(
            raiz, validar_siguiente(args.siguiente, antes["en_curso"], antes["declarada"]))
    datos = versiones.estado(raiz)
    fecha = _fecha_del_tag(raiz, datos["tag"])
    tareas, aprobadas = contar(proyecto, datos["en_curso"], fecha, bool(datos["tag"]))
    salida = {"esquema": ESQUEMA, "repo": str(raiz),
              "proyecto": proyecto.nombre if proyecto else None, **datos,
              "fecha_tag": fecha, "tareas": tareas, "aprobadas": aprobadas}
    if hecho:
        salida["hecho"] = hecho
    if proyecto is None:
        salida["avisos"] = [*avisos, "No se encontró el proyecto de este repo: sin tareas. "
                                     "Pasa --proyecto para contarlas."]
    elif avisos:
        salida["avisos"] = avisos
    imprimir(salida)
    return 0


def anadir(sub):
    verbo = sub.add_parser(
        "version", help="Versión publicada y en curso del proyecto, sus tareas y lo aprobado "
                        "desde el último tag. No escribe nada (salvo con --siguiente)")
    verbo.add_argument("--proyecto", help="El proyecto. Por defecto, el repo donde estás")
    verbo.add_argument("--siguiente", metavar="X.Y.Z",
                       help="Planear la siguiente menor o mayor: la escribe en proyecto.md")
    verbo.set_defaults(funcion=cmd_version)
