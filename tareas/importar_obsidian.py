"""Traer un proyecto de Obsidian a su `.cotejo/` (v1.2): el ensayo (D1) y `--aplicar` (D2).

`cotejo importar obsidian <proyecto>` lee la nota del proyecto, sus subnotas y sus adjuntos,
decide en qué repo va a vivir y reparte cada sección de la nota al tipo del almacén que le toca
(`tareas/almacen.py`). **No escribe nada**: devuelve un `Plan` —qué entradas se crearían, con su
título, texto, campos y `origen`— y el resumen de cuántas van a cada tipo y qué no encajó. El
plan es el contrato con `--aplicar` (D2), que solo tiene que escribirlo: decidir y escribir van
separados para que lo que se enseña en el ensayo sea exactamente lo que luego se escribe.

Lo que se da por supuesto es la plantilla del vault (`_Plantillas/Proyecto.md`): secciones `##`
con un emoji delante, decisiones y problemas en tabla, aprendizajes en viñetas, la bitácora en
`### AAAA-MM-DD`. Lo que se sale de ella no se pierde ni se adivina: va a `referencias/` con el
tema `sin-clasificar`, y el ensayo lo lista con su motivo. Es mecánico a propósito —se puede
probar y no gasta tokens—; lo que no encaje lo resuelve después la tarea de revisión.

Cada entrada lleva un `origen` estable (la nota, la sección y un hash corto de lo que dice), que
es lo que hace idempotente el importador: el ensayo ya dice cuántas estaban importadas.

`aplicar` (D2) escribe ese mismo plan en el repo —sin commit: el diff lo revisa la persona—,
reescribe los enlaces internos, crea la tarea de revisión y marca el proyecto como migrado en
la config (la fuente compuesta deja de leerlo del vault). Lo que ya estaba importado, por su
`origen`, no se vuelve a escribir.

No importa GTK, como el resto del núcleo. Nunca escribe en el vault.
"""

import hashlib
import os
import re
import shutil
import subprocess
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from . import almacen, configuracion, rutas, version

SIN_CLASIFICAR = "sin-clasificar"

# Cómo se llaman, sin emoji ni tildes y en minúsculas, las secciones que entiende el reparto.
# Las de `proyecto.md` se copian tal cual a ese archivo; las demás se parten en entradas.
SECCIONES_PROYECTO = ("objetivo", "stack", "stack y arquitectura", "arquitectura",
                      "hoja de ruta", "mapa del proyecto", "enlaces", "siguiente paso")
SECCIONES = {
    "tareas": "tareas",
    "decisiones tecnicas": "decision", "decisiones": "decision",
    "bitacora": "bitacora",
    "problemas y soluciones": "problema", "problemas": "problema",
    "aprendizajes": "aprendizaje",
    **{nombre: "proyecto" for nombre in SECCIONES_PROYECTO},
}

FENCE_RE = re.compile(r"^\s*(```|~~~)")
SECCION_RE = re.compile(r"^##\s+(.+?)\s*$")
SUBSECCION_RE = re.compile(r"^###\s+(.+?)\s*$")
FECHA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TAREA_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[.\]\s+\S")
VINETA_RE = re.compile(r"^[-*+]\s+(.*)$")
FILA_RE = re.compile(r"^\s*\|(.*)\|\s*$")
SEPARADOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}")
# `![[logo.png]]`, `[[diagrama.excalidraw|alias]]` y `![](img/logo.png)`: los enlaces a algo que
# no es una nota son adjuntos. Los que van a notas son subnotas o enlaces a otros proyectos.
WIKI_RE = re.compile(r"!?\[\[([^\]|#^]+)(?:[#^][^\]|]*)?(?:\|[^\]]*)?\]\]")
MD_IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
PROYECTO_FM_RE = re.compile(r"^proyecto:\s*['\"]?\[\[([^\]|]+)(?:\|[^\]]*)?\]\]['\"]?\s*$",
                            re.MULTILINE)
# Carpetas que nunca son del proyecto aunque estén dentro de su carpeta.
NUNCA = {"node_modules", ".git", ".obsidian", ".trash", "__pycache__", ".venv", "venv"}


class NoSeImporta(Exception):
    """El ensayo no puede seguir. `salida` dice qué hacer, como los errores de la CLI."""

    def __init__(self, mensaje, salida=""):
        super().__init__(mensaje)
        self.salida = salida


# En Windows, git no puede tener la raíz de un repo por encima de MAX_PATH − 12 caracteres (el
# límite de `CreateDirectory` y de `chdir`), ni con `LongPathsEnabled=1` ni con
# `core.longpaths=true`: sin esto no crea la carpeta, y con esto la crea pero no entra en ella.
# Archivos largos *dentro* de un repo de raíz corta sí funcionan (`probar_despachar.py`).
RAIZ_GIT_MAXIMA_WINDOWS = 247


def git_init(repo):
    """`git init` en `repo`, creándola si hace falta. Lo usan los dos importadores.

    En Windows se niega antes de tocar nada si la ruta es demasiado larga para git, en vez de
    devolver el `CalledProcessError` crudo de git (visto en la prueba a mano de F1).
    """
    if rutas.sistema() == "windows" and len(str(repo)) > RAIZ_GIT_MAXIMA_WINDOWS:
        raise NoSeImporta(
            f"La carpeta del repo es demasiado larga para git en Windows ({len(str(repo))} "
            f"caracteres; el máximo es {RAIZ_GIT_MAXIMA_WINDOWS}): {repo}",
            "Elige un --destino más corto: los archivos largos dentro del repo sí funcionan, "
            "la raíz no.")
    repo.mkdir(parents=True, exist_ok=True)
    # Como en `worktrees._git`: con la raíz cerca del límite, los archivos de `.git/` ya lo pasan.
    previo = ["-c", "core.longpaths=true"] if rutas.sistema() == "windows" else []
    try:
        subprocess.run(["git", *previo, "init", "-q", str(repo)], check=True,
                       capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        raise NoSeImporta(f"No pude hacer `git init` en {repo}: {error}",
                          "Créalo a mano con `git init` y vuelve a aplicar.") from None


@dataclass
class EntradaPlan:
    """Una entrada que `--aplicar` crearía con `Almacen.crear(tipo, titulo, texto, ...)`."""

    tipo: str
    titulo: str
    texto: str = ""
    temas: list = field(default_factory=list)
    campos: dict = field(default_factory=dict)  # estado, autor, fecha, resumen, archivo...
    origen: str = ""
    motivo: str = ""  # por qué cayó en sin-clasificar, si cayó

    def fila(self):
        datos = {"tipo": self.tipo, "titulo": self.titulo, "origen": self.origen}
        if self.motivo:
            datos["motivo"] = self.motivo
        return datos


@dataclass
class Plan:
    proyecto: str
    nota: str  # relativa al vault
    repo: dict  # {"ruta", "como", "git_init"}
    proyecto_md: str = ""  # el cuerpo de `.cotejo/proyecto.md`
    tareas_md: str = ""  # el cuerpo de `.cotejo/tareas.md`, con sus `^cotejo-id`
    tareas: int = 0
    entradas: list = field(default_factory=list)
    subnotas: list = field(default_factory=list)  # relativas al vault
    adjuntos: list = field(default_factory=list)  # {"origen", "ruta"} (ruta absoluta)
    no_enlazados: dict = field(default_factory=dict)  # {carpeta: cuántos} que no se importan
    ya_importadas: list = field(default_factory=list)  # orígenes que el repo ya tiene
    avisos: list = field(default_factory=list)

    def sin_clasificar(self):
        return [e for e in self.entradas if SIN_CLASIFICAR in e.temas]

    def resumen(self, detalle=False):
        """Lo que enseña el ensayo: cuántas van a cada tipo, qué no encajó y qué pasa con el repo."""
        conteo = {}
        for entrada in self.entradas:
            conteo[entrada.tipo] = conteo.get(entrada.tipo, 0) + 1
        ya = set(self.ya_importadas)
        datos = {
            "proyecto": self.proyecto, "nota": self.nota, "repo": self.repo,
            "conteo": {"tareas": self.tareas, "proyecto_md": bool(self.proyecto_md.strip()),
                       **dict(sorted(conteo.items()))},
            "subnotas": len(self.subnotas), "adjuntos": len(self.adjuntos),
            "no_enlazados": self.no_enlazados,
            "sin_clasificar": [e.fila() for e in self.sin_clasificar()],
            "ya_importadas": len([e for e in self.entradas if e.origen in ya]),
            "nuevas": len([e for e in self.entradas if e.origen not in ya]),
        }
        if detalle:
            datos["entradas"] = [{**e.fila(), "ya": e.origen in ya} for e in self.entradas]
        if self.avisos:
            datos["avisos"] = self.avisos
        return datos


# --- el ensayo -------------------------------------------------------------------------------

def planear(vault, carpeta_proyectos, nombre, destino=None):
    """El `Plan` de importar el proyecto `nombre` del vault. No escribe nada, en ningún sitio."""
    vault = Path(vault)
    principal, carpeta = localizar(vault, carpeta_proyectos, nombre)
    texto = _leer(principal)
    datos, cuerpo = _frontmatter(texto)
    repo = resolver_repo(datos, carpeta, destino, nombre)
    plan = Plan(proyecto=principal.stem, nota=_rel(principal, vault), repo=repo)

    repartir(plan, cuerpo, plan.nota)

    for nota in subnotas(vault, principal, carpeta):
        relativa = _rel(nota, vault)
        plan.subnotas.append(relativa)
        datos_sub, cuerpo_sub = _frontmatter(_leer(nota))
        plan.entradas.append(EntradaPlan(
            "referencia", nota.stem, _sin_titulo(cuerpo_sub, nota.stem),
            temas=_temas_de(datos_sub), campos={"resumen": almacen.PENDIENTE},
            origen=relativa))

    plan.adjuntos = adjuntos(vault, [principal, *(vault / s for s in plan.subnotas)],
                             plan.avisos)
    plan.no_enlazados = no_enlazados(carpeta, plan.adjuntos)
    for adjunto in plan.adjuntos:
        ruta = Path(adjunto["ruta"])
        plan.entradas.append(EntradaPlan(
            "recurso", ruta.stem, campos={"archivo": ruta.name, "resumen": almacen.PENDIENTE},
            origen=adjunto["origen"]))

    plan.ya_importadas = _ya_importadas(Path(repo["ruta"]), plan)
    return plan


def localizar(vault, carpeta_proyectos, nombre):
    """(nota principal, carpeta del proyecto o None). Sin mayúsculas: «cotejo» es «Cotejo»."""
    base = vault / carpeta_proyectos
    if not base.is_dir():
        raise NoSeImporta(f"No encuentro la carpeta de proyectos {base}",
                          "Revisa `vault` y `carpeta_proyectos` en la config de la fuente "
                          "obsidian (`cotejo fuentes info obsidian`).")
    buscado = str(nombre).strip().lower()
    candidatos = []
    for entrada in sorted(base.iterdir()):
        if entrada.name.startswith((".", "_")):
            continue
        if entrada.is_dir() and (entrada / f"{entrada.name}.md").is_file():
            candidatos.append((entrada.name, entrada / f"{entrada.name}.md", entrada))
        elif entrada.suffix == ".md":
            candidatos.append((entrada.stem, entrada, None))
    for nombre_proyecto, principal, carpeta in candidatos:
        if nombre_proyecto.lower() == buscado:
            return principal, carpeta
    import difflib
    parecidos = difflib.get_close_matches(str(nombre), [c[0] for c in candidatos], n=3)
    raise NoSeImporta(f"No hay ningún proyecto «{nombre}» en {carpeta_proyectos}."
                      + (f" ¿Buscabas {', '.join(parecidos)}?" if parecidos else ""),
                      "`cotejo tareas` lista los proyectos que ve Cotejo.")


def resolver_repo(datos, carpeta, destino, nombre):
    """Dónde va a vivir `.cotejo/`: `{"ruta", "como", "git_init"}`.

    Por orden: `--destino` si se pasa (y si no es un repo todavía, `--aplicar` le hará `git
    init`); `repo:` del frontmatter si es una carpeta local con git; un `.git` en una subcarpeta
    del proyecto (el caso de Cotejo, que tiene su repo dentro de su carpeta del vault). Si nada
    de eso, no se inventa: se pide `--destino`.
    """
    if destino:
        ruta = Path(destino).expanduser().resolve()
        if ruta.exists() and not ruta.is_dir():
            raise NoSeImporta(f"«{destino}» existe y no es una carpeta",
                              "Pasa en `--destino` una carpeta (puede no existir todavía).")
        return {"ruta": str(ruta), "como": "destino", "git_init": not (ruta / ".git").exists()}

    declarado = str(datos.get("repo") or "").strip()
    if declarado and "://" not in declarado and not declarado.startswith("git@"):
        ruta = Path(declarado).expanduser()
        if ruta.is_dir() and (ruta / ".git").exists():
            return {"ruta": str(ruta.resolve()), "como": "repo", "git_init": False}

    if carpeta is not None:
        repos = sorted(h for h in carpeta.iterdir()
                       if h.is_dir() and not h.name.startswith(".") and (h / ".git").exists())
        if len(repos) == 1:
            return {"ruta": str(repos[0].resolve()), "como": "subcarpeta", "git_init": False}
        if len(repos) > 1:
            raise NoSeImporta(f"«{nombre}» tiene varios repos dentro: "
                              f"{', '.join(r.name for r in repos)}",
                              "Elige uno con `--destino <carpeta>`.")

    por_que = (f"su `repo:` es «{declarado}», que no es una carpeta local con git"
               if declarado else "no tiene `repo:` ni un repo dentro de su carpeta")
    raise NoSeImporta(f"«{nombre}» no tiene repo: {por_que}",
                      f"Pasa `--destino <carpeta>` y se le hará `git init` al aplicar.")


def subnotas(vault, principal, carpeta):
    """Las notas del proyecto que no son la principal, ordenadas.

    Las de su carpeta (sin entrar en repos anidados, que tienen sus propios `.md` y no son notas
    del vault) y, en todo el vault, las que dicen `proyecto: "[[X]]"` en su frontmatter.
    """
    encontradas = set()
    if carpeta is not None:
        encontradas.update(n for n in _notas_de(carpeta) if n != principal)
    nombre = principal.stem.lower()
    for nota in _notas_de(vault):
        if nota == principal or nota in encontradas:
            continue
        try:
            cabeza = nota.read_text(encoding="utf-8")[:2000]
        except (OSError, UnicodeDecodeError):
            continue
        m = PROYECTO_FM_RE.search(cabeza.split("\n---", 1)[0]) if cabeza.startswith("---") else None
        if m and m.group(1).strip().lower() == nombre:
            encontradas.add(nota)
    return sorted(encontradas, key=lambda p: str(p).lower())


def adjuntos(vault, notas, avisos):
    """Los archivos que no son notas y que las notas enlazan (`![[logo.png]]`, `![](img.png)`).

    Un enlace se resuelve como lo hace Obsidian, por el nombre del archivo en cualquier parte
    del vault (o por la ruta, si la trae). Uno que no se encuentra es un aviso, no un error.
    """
    indice, notas_vault = {}, set()
    for ruta in _archivos_de(vault):
        if ruta.suffix == ".md":
            notas_vault.add(ruta.stem.lower())
        else:
            indice.setdefault(ruta.name.lower(), ruta)
    vistos = {}
    for nota in notas:
        try:
            texto = nota.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        destinos = [m.group(1).strip() for m in WIKI_RE.finditer(texto)]
        destinos += [m.group(1).strip() for m in MD_IMG_RE.finditer(texto)
                     if "://" not in m.group(1)]
        for destino in destinos:
            # «Cotejo - Planning v1.2» parece tener extensión y es una nota: si hay una nota
            # con ese nombre, es eso.
            if Path(destino).suffix in ("", ".md") or Path(destino).name.lower() in notas_vault:
                continue
            ruta = (vault / destino) if (vault / destino).is_file() else \
                (nota.parent / destino) if (nota.parent / destino).is_file() else \
                indice.get(Path(destino).name.lower())
            if ruta is None:
                aviso = {"nota": _rel(nota, vault),
                         "motivo": f"enlaza «{destino}», que no está en el vault"}
                if aviso not in avisos:
                    avisos.append(aviso)
                continue
            vistos.setdefault(ruta.resolve(), ruta)
    return [{"origen": _rel(r, vault), "ruta": str(r)}
            for r in sorted(vistos.values(), key=lambda p: str(p).lower())]


def no_enlazados(carpeta, adjuntos_):
    """Los archivos de la carpeta del proyecto que no son notas ni adjuntos enlazados, por carpeta.

    No se importan: casi siempre son código (un tema, un proyecto de vídeo) que va al repo como
    código y no como recurso con ficha. Se cuentan para que la persona decida qué hacer con
    ellos en vez de enterarse después de que no viajaron.
    """
    if carpeta is None:
        return {}
    enlazados = {Path(a["ruta"]).resolve() for a in adjuntos_}
    conteo = {}
    for ruta in _archivos_de(carpeta):
        if ruta.suffix == ".md" or ruta.resolve() in enlazados:
            continue
        relativa = ruta.relative_to(carpeta)
        grupo = relativa.parts[0] if len(relativa.parts) > 1 else "."
        conteo[grupo] = conteo.get(grupo, 0) + 1
    return dict(sorted(conteo.items(), key=lambda par: (-par[1], par[0])))


# --- el reparto ------------------------------------------------------------------------------

def repartir(plan, cuerpo, nota):
    """Llena `plan` con lo que dice el cuerpo de la nota principal, sección por sección."""
    intro, secciones = _secciones(cuerpo)
    partes_proyecto = [intro.strip()] if intro.strip() else []
    for titulo, texto in secciones:
        clave = _clave(titulo)
        tipo = SECCIONES.get(clave)
        if tipo is None and clave.startswith("stack"):
            tipo = "proyecto"
        origen = f"{nota}#{titulo}"
        if tipo == "proyecto":
            partes_proyecto.append(f"## {titulo}\n{texto.strip()}".rstrip())
        elif tipo == "tareas":
            plan.tareas_md = f"# Tareas\n\n{texto.strip()}\n" if texto.strip() else ""
            plan.tareas = sum(1 for l in texto.splitlines() if TAREA_RE.match(l))
        elif tipo == "decision":
            plan.entradas += _decisiones(texto, origen, titulo)
        elif tipo == "problema":
            plan.entradas += _problemas(texto, origen, titulo)
        elif tipo == "aprendizaje":
            plan.entradas += _aprendizajes(texto, origen, titulo)
        elif tipo == "bitacora":
            plan.entradas += _bitacora(texto, origen, titulo)
        elif texto.strip():
            plan.entradas.append(_sin_clasificar(titulo, texto, origen,
                                                 "sección que la plantilla no tiene"))
    plan.proyecto_md = "\n\n".join(partes_proyecto) + "\n" if partes_proyecto else ""


def _decisiones(texto, origen, seccion):
    """Una decisión por fila de la tabla (Fecha | Decisión | Motivo | Alternativas), o por viñeta."""
    filas, resto = _tabla(texto)
    entradas = []
    for celdas in filas:
        celdas += [""] * (4 - len(celdas))
        fecha, decision, motivo, alternativas = celdas[:4]
        if not decision:
            continue
        partes = [decision]
        if motivo:
            partes.append(f"**Por qué:** {motivo}")
        if alternativas:
            partes.append(f"**Descartado:** {alternativas}")
        campos = {"estado": "aceptada", "autor": "importado"}
        if FECHA_RE.match(fecha):
            campos["fecha"] = fecha
        entradas.append(EntradaPlan("decision", _titulo_corto(decision), "\n\n".join(partes),
                                    campos=campos, origen=_origen(origen, decision)))
    entradas += _vinetas_como("decision", resto, origen,
                              {"estado": "aceptada", "autor": "importado"})
    return entradas + _sobras(resto, origen, seccion)


def _problemas(texto, origen, seccion):
    """Uno por fila (Problema | Causa | Solución): `resuelto` si trae solución."""
    filas, resto = _tabla(texto)
    entradas = []
    for celdas in filas:
        celdas += [""] * (3 - len(celdas))
        problema, causa, solucion = celdas[:3]
        if not problema:
            continue
        partes = [problema]
        if causa:
            partes.append(f"**Causa:** {causa}")
        if solucion:
            partes.append(f"**Solución:** {solucion}")
        campos = {"estado": "resuelto" if solucion else "abierto"}
        if solucion:
            campos["solucion"] = solucion
        entradas.append(EntradaPlan("problema", _titulo_corto(problema), "\n\n".join(partes),
                                    campos=campos, origen=_origen(origen, problema)))
    entradas += _vinetas_como("problema", resto, origen, {"estado": "abierto"})
    return entradas + _sobras(resto, origen, seccion)


def _aprendizajes(texto, origen, seccion):
    return _vinetas_como("aprendizaje", texto, origen, {}) + _sobras(texto, origen, seccion)


def _bitacora(texto, origen, seccion):
    """Un día por `### AAAA-MM-DD`. Lo que no cuelga de una fecha va a sin-clasificar."""
    entradas = []
    antes, dias = _subsecciones(texto)
    for titulo, cuerpo in dias:
        if not _contenido(cuerpo):
            continue
        if FECHA_RE.match(titulo):
            entradas.append(EntradaPlan("bitacora", titulo, cuerpo.strip(),
                                        campos={"fecha": titulo}, origen=f"{origen}/{titulo}"))
        else:
            entradas.append(_sin_clasificar(f"{seccion}: {titulo}", cuerpo,
                                            f"{origen}/{titulo}", "día de bitácora sin fecha"))
    if _contenido(antes):
        entradas.append(_sin_clasificar(seccion, antes, origen,
                                        "texto de la bitácora fuera de un día"))
    return entradas


def _vinetas_como(tipo, texto, origen, campos):
    entradas = []
    for vineta in _vinetas(texto):
        entradas.append(EntradaPlan(tipo, _titulo_corto(vineta), vineta, campos=dict(campos),
                                    origen=_origen(origen, vineta)))
    return entradas


def _sobras(texto, origen, seccion):
    """Lo de una sección tipada que no es tabla ni viñeta (párrafos, subsecciones): sin-clasificar.

    Las citas (`> …`) son la instrucción de la plantilla y no cuentan.
    """
    sobra = []
    for linea in texto.splitlines():
        if (FILA_RE.match(linea) or SEPARADOR_RE.match(linea) or VINETA_RE.match(linea)
                or linea.startswith(("  ", "\t")) or linea.lstrip().startswith(">")):
            continue
        sobra.append(linea)
    if not _contenido("\n".join(sobra)):
        return []
    return [_sin_clasificar(seccion, "\n".join(sobra).strip(), f"{origen}/resto",
                            "texto que no es tabla ni viñeta")]


def _sin_clasificar(titulo, texto, origen, motivo):
    return EntradaPlan("referencia", titulo, texto.strip(), temas=[SIN_CLASIFICAR],
                       campos={"resumen": almacen.PENDIENTE}, origen=origen, motivo=motivo)


# --- Markdown, lo justo ----------------------------------------------------------------------

def _secciones(cuerpo):
    """(lo de antes del primer `##`, [(título, texto)]) sin contar los `##` de un bloque de código."""
    return _partir_por(cuerpo, SECCION_RE)


def _subsecciones(texto):
    return _partir_por(texto, SUBSECCION_RE)


def _partir_por(texto, patron):
    antes, partes, actual = [], [], None
    en_codigo = False
    for linea in texto.splitlines():
        if FENCE_RE.match(linea):
            en_codigo = not en_codigo
        m = None if en_codigo else patron.match(linea)
        if m:
            actual = [m.group(1).strip(), []]
            partes.append(actual)
        elif actual is None:
            antes.append(linea)
        else:
            actual[1].append(linea)
    return "\n".join(antes), [(t, "\n".join(l)) for t, l in partes]


def _tabla(texto):
    """(filas de datos como listas de celdas, el texto sin la tabla). Sin cabecera ni filas vacías."""
    filas, resto, cabecera = [], [], True
    for linea in texto.splitlines():
        m = FILA_RE.match(linea)
        if not m:
            resto.append(linea)
            cabecera = True
            continue
        if SEPARADOR_RE.match(linea):
            continue
        if cabecera:  # la primera fila de cada tabla son los títulos de columna
            cabecera = False
            continue
        celdas = [c.strip() for c in re.split(r"(?<!\\)\|", m.group(1))]
        if any(celdas):
            filas.append(celdas)
    return filas, "\n".join(resto)


def _vinetas(texto):
    """Las viñetas de primer nivel, con sus líneas de continuación. Las vacías no cuentan."""
    vinetas, actual = [], None
    for linea in texto.splitlines():
        m = VINETA_RE.match(linea)
        if m and not TAREA_RE.match(linea):
            actual = [m.group(1).strip()]
            vinetas.append(actual)
        elif actual is not None and linea.startswith(("  ", "\t")) and linea.strip():
            actual.append(linea.strip())
        else:
            actual = None
    return [" ".join(v).strip() for v in vinetas if " ".join(v).strip()]


def _contenido(texto):
    """Si hay algo escrito: ni líneas vacías, ni citas (la instrucción de la plantilla), ni una
    viñeta sin texto (`- `, que es como la plantilla deja el hueco)."""
    return any(l.strip() and not l.lstrip().startswith(">") and l.strip() not in "-*+"
               for l in texto.splitlines())


def _clave(titulo):
    """«🧠 Decisiones técnicas» → «decisiones tecnicas»."""
    plano = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode("ascii")
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", plano.lower()).split())


def _titulo_corto(texto, largo=90):
    """Un título de una línea: sin Markdown y cortado por la primera frase o por `largo`."""
    plano = re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", r"\2", texto)
    plano = re.sub(r"\*\*|__|`|(?<!\w)[*_]|[*_](?!\w)", "", plano)
    plano = " ".join(plano.split())
    # `:` no cierra frase: «v1.1: diff de…» se quedaría en «v1.1» (cotejo-1j0w3y).
    frase = re.split(r"(?<=[.!?])\s", plano, maxsplit=1)[0].rstrip(".:")
    if len(frase) <= largo:
        return frase
    return frase[:largo - 1].rsplit(" ", 1)[0].rstrip(",;") + "…"


def _origen(seccion, texto):
    """`nota#sección:hash`: estable mientras no cambie lo que dice, que es lo que se importó."""
    return f"{seccion}:{hashlib.sha256(' '.join(texto.split()).encode()).hexdigest()[:8]}"


def _frontmatter(texto):
    try:
        return almacen.partir(texto)
    except almacen.FrontmatterRoto:
        # Obsidian acepta YAML que el almacén no entiende; para importar basta con el cuerpo.
        fin = texto.find("\n---", 3)
        return {}, texto[fin + 4:] if texto.startswith("---") and fin != -1 else texto


def _temas_de(datos):
    tags = datos.get("tags") or []
    tags = [tags] if isinstance(tags, str) else tags
    return [t for t in (str(x).strip().lstrip("#").lower() for x in tags)
            if t and t != "proyecto"]


def _sin_titulo(cuerpo, nombre):
    lineas = cuerpo.strip().splitlines()
    if lineas and lineas[0].lstrip("# ").strip() == nombre:
        lineas = lineas[1:]
    return "\n".join(lineas).strip()


def _leer(ruta):
    try:
        return ruta.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise NoSeImporta(f"No pude leer {ruta}: {error}",
                          "Revisa que la nota exista y esté en UTF-8.") from None


def _rel(ruta, base):
    try:
        return ruta.relative_to(base).as_posix()
    except ValueError:
        return ruta.as_posix()


def _es_repo(carpeta):
    return (carpeta / ".git").exists()


def _recorrer(base):
    """Los archivos bajo `base`, sin ocultos, sin `NUNCA` y sin entrar en repos anidados."""
    pendientes = [base]
    while pendientes:
        carpeta = pendientes.pop()
        try:
            hijos = sorted(carpeta.iterdir())
        except OSError:
            continue
        for hijo in hijos:
            if hijo.name.startswith(".") or hijo.name in NUNCA:
                continue
            if hijo.is_dir():
                if not _es_repo(hijo):
                    pendientes.append(hijo)
            elif hijo.is_file():
                yield hijo


def _notas_de(base):
    return [r for r in _recorrer(base) if r.suffix == ".md"]


def _archivos_de(base):
    return list(_recorrer(base))


def _ya_importadas(repo, plan):
    if not (repo / almacen.CARPETA).is_dir():
        return []
    origenes = {str(e.datos.get("origen")) for e in almacen.Almacen(repo).entradas()
                if e.datos.get("origen")}
    # La bitácora no lleva `origen` (es un archivo por día): cuenta como importada si el día
    # ya existe en el repo.
    dias = {e.id for e in almacen.Almacen(repo).entradas("bitacora")}
    return [e.origen for e in plan.entradas
            if e.origen in origenes or (e.tipo == "bitacora" and e.titulo in dias)]


# --- aplicar (D2) ----------------------------------------------------------------------------

TAREA_REVISION = "Revisar lo importado: resúmenes, temas y fichas"
ENLACE_RE = re.compile(r"(!?)\[\[([^\]|#^]+)([#^][^\]|]*)?(?:\|([^\]]*))?\]\]")
MARCA_RE = re.compile(r"\^(cotejo-[a-z0-9]+)\s*$")


def aplicar(plan, vault):
    """Escribe `plan` en su repo. Devuelve lo que hizo, para la respuesta de la CLI.

    El orden importa: todo lo que puede negarse (unas `tareas.md` que no son estas, un repo que
    no se puede crear) se comprueba antes de escribir la primera entrada, para que un error
    deje el repo como estaba. Nada se commitea.
    """
    repo = Path(plan.repo["ruta"])
    cotejo = repo / almacen.CARPETA
    tareas_md = cotejo / "tareas.md"
    que_tareas = _que_hacer_con_las_tareas(plan, tareas_md)

    hecho = {"git_init": False, "escritas": {}, "ya_estaban": 0, "recursos_copiados": 0,
             "avisos": list(plan.avisos)}
    if plan.repo["git_init"] and not (repo / ".git").exists():
        git_init(repo)
        hecho["git_init"] = True

    alm = almacen.Almacen(repo)
    cotejo.mkdir(exist_ok=True)
    for tipo in almacen.TIPOS.values():  # el mismo esqueleto que deja `cotejo init`
        if tipo.carpeta and not (cotejo / tipo.carpeta).is_dir():
            (cotejo / tipo.carpeta).mkdir(parents=True)
            (cotejo / tipo.carpeta / ".gitkeep").touch()

    nombres = _nombres(plan, cotejo)
    enlazar = _reescritor(plan, vault, nombres)

    hecho["tareas_md"] = que_tareas
    if que_tareas == "escribir":
        _reemplazar(tareas_md, enlazar(plan.tareas_md))
    elif not tareas_md.is_file():
        _reemplazar(tareas_md, "# Tareas\n")
    hecho["proyecto_md"], hecho["version"] = _escribir_proyecto(alm, enlazar(plan.proyecto_md)), version.asegurar(repo)

    ya = set(plan.ya_importadas)
    archivos = {a["origen"]: Path(a["ruta"]) for a in plan.adjuntos}
    for entrada in plan.entradas:
        if entrada.origen in ya:
            hecho["ya_estaban"] += 1
            continue
        try:
            escrita = _escribir(alm, entrada, enlazar, nombres, archivos, hecho)
        except (ValueError, OSError) as error:
            hecho["avisos"].append({"nota": entrada.origen, "motivo": f"no se importó: {error}"})
            continue
        if escrita:
            hecho["escritas"][entrada.tipo] = hecho["escritas"].get(entrada.tipo, 0) + 1
        else:
            hecho["ya_estaban"] += 1

    hecho["tarea_revision"] = _tarea_de_revision(repo, plan.proyecto)
    hecho["migrado"] = _marcar_migrado(plan.proyecto, repo)
    if not hecho["avisos"]:
        del hecho["avisos"]
    return hecho


def _que_hacer_con_las_tareas(plan, tareas_md):
    """«escribir», «ya-estaban» o «sin-tareas». Se niega si el repo tiene otras tareas.

    Las tareas del vault van con sus `^cotejo-id`: si el repo ya las tiene todas, es que ya se
    importaron (y quizá alguien las movió después, que no hay que pisar). Si tiene tareas que
    no son estas, escribir encima borraría trabajo de otro; mezclarlas, adivinar el orden.
    """
    if not plan.tareas_md.strip():
        return "sin-tareas"
    try:
        actual = tareas_md.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "escribir"
    except (OSError, UnicodeDecodeError) as error:
        raise NoSeImporta(f"No pude leer {tareas_md}: {error}", "Revísalo y vuelve a aplicar.")
    lineas_actuales = [l for l in actual.splitlines() if TAREA_RE.match(l)]
    if not lineas_actuales:
        return "escribir"
    del_plan = {m.group(1) for m in (MARCA_RE.search(l) for l in plan.tareas_md.splitlines()) if m}
    del_repo = {m.group(1) for m in (MARCA_RE.search(l) for l in lineas_actuales) if m}
    if del_plan and del_plan <= del_repo:
        return "ya-estaban"
    raise NoSeImporta(f"{tareas_md} ya tiene tareas que no son las de «{plan.proyecto}»",
                      "No se escribió nada. Importa a un repo sin tareas o junta las listas a "
                      "mano antes de aplicar.")


def _nombres(plan, cotejo):
    """El nombre de archivo de cada subnota y cada recurso, decidido antes de escribir.

    Hace falta saberlo antes porque los enlaces se reescriben al escribir cada entrada, y una
    decisión (que no se edita) que enlaza una subnota tiene que salir ya con el nombre nuevo.
    Se reservan contra lo que ya hay en la carpeta y contra lo de esta misma importación.
    """
    nombres = {}
    usados = {}
    for entrada in plan.entradas:
        if entrada.origen in plan.ya_importadas:
            continue
        if entrada.tipo == "referencia" and entrada.origen.endswith(".md"):
            carpeta, base = "referencias", almacen._slug(Path(entrada.origen).stem, largo=120)
            nombres[entrada.origen] = _reservar(cotejo / carpeta, base or "referencia", ".md",
                                                usados)
        elif entrada.tipo == "recurso":
            original = Path(entrada.origen)
            base = almacen._slug(original.stem, largo=120) or "recurso"
            archivo = _reservar(cotejo / "recursos", base, original.suffix.lower(), usados)
            ficha = _reservar(cotejo / "recursos", Path(archivo).stem, ".md", usados)
            nombres[entrada.origen] = archivo
            nombres[entrada.origen + "#ficha"] = ficha
    return nombres


def _reservar(carpeta, base, sufijo, usados):
    ocupados = usados.setdefault(str(carpeta), set())
    nombre, numero = base, 2
    while (f"{nombre}{sufijo}" in ocupados) or (carpeta / f"{nombre}{sufijo}").exists():
        nombre = f"{base}-{numero}"
        numero += 1
    ocupados.add(f"{nombre}{sufijo}")
    return nombre if sufijo == ".md" else f"{nombre}{sufijo}"


def _reescritor(plan, vault, nombres):
    """La función que reescribe los `[[enlaces]]` de un texto importado.

    A la nota del proyecto → `[[proyecto]]`; a una subnota → a su referencia; a un adjunto → a
    su archivo en `recursos/`; a otra nota del vault (otro proyecto, un recurso suelto) → texto
    con su origen, porque ese enlace ya no lleva a ningún sitio desde el repo. Lo demás, igual.
    """
    destinos = {plan.proyecto.lower(): "proyecto"}
    for entrada in plan.entradas:
        nuevo = nombres.get(entrada.origen)
        if nuevo is None:
            continue
        if entrada.tipo == "referencia":
            destinos[Path(entrada.origen).stem.lower()] = nuevo
        else:
            destinos[Path(entrada.origen).name.lower()] = nuevo
    del_vault = {n.stem.lower() for n in _notas_de(vault)}

    def cambiar(m):
        embebido, destino, fragmento, alias = m.group(1), m.group(2).strip(), m.group(3) or "", m.group(4)
        clave = destino.lower()
        nuevo = destinos.get(clave) or destinos.get(Path(destino).name.lower())
        if nuevo:
            return f"{embebido}[[{nuevo}{fragmento}|{alias or destino}]]" if not embebido \
                else f"{embebido}[[{nuevo}{fragmento}]]"
        if clave in del_vault or Path(destino).name.lower() in del_vault:
            return f"{alias or destino} (vault: {destino})"
        return m.group(0)

    return lambda texto: ENLACE_RE.sub(cambiar, texto or "")


def _escribir(alm, entrada, enlazar, nombres, archivos, hecho):
    """Escribe una entrada del plan. `False` si ya estaba (un día de bitácora que existe)."""
    texto = enlazar(entrada.texto)
    campos = {**entrada.campos, "origen": entrada.origen}
    if entrada.tipo == "bitacora":
        _, creada = alm.importar_dia(entrada.campos["fecha"], texto)
        return creada
    if entrada.tipo == "recurso":
        archivo = nombres[entrada.origen]
        destino = alm.base / "recursos" / archivo
        if not destino.exists():
            shutil.copy2(archivos[entrada.origen], destino)
            hecho["recursos_copiados"] += 1
        campos["archivo"] = archivo
        alm.crear("recurso", entrada.titulo, texto, entrada.temas,
                  nombre=nombres[entrada.origen + "#ficha"], **campos)
        return True
    alm.crear(entrada.tipo, entrada.titulo, texto, entrada.temas,
              nombre=nombres.get(entrada.origen), **campos)
    return True


def _escribir_proyecto(alm, texto):
    """«creado», «actualizado» (el de `init`, que solo tiene el título) o «ya-estaba»."""
    if not texto.strip():
        return "sin-contenido"
    lineas = texto.strip().splitlines()
    titulo = lineas[0][2:].strip() if lineas[0].startswith("# ") else alm.raiz.name
    cuerpo = "\n".join(lineas[1:] if lineas[0].startswith("# ") else lineas).strip()
    try:
        actual = alm.leer(almacen.ID_PROYECTO)
    except almacen.EntradaNoExiste:
        alm.crear("proyecto", titulo, cuerpo)
        return "creado"
    if actual.cuerpo.strip() == f"# {actual.titulo}":
        alm.reescribir(almacen.ID_PROYECTO, actual.version, texto=cuerpo, titulo=titulo)
        return "actualizado"
    return "ya-estaba"


def _tarea_de_revision(repo, nombre):
    """La tarea «Revisar lo importado», en el `tareas.md` del repo y por su fuente. Su id.

    Va por `fuentes/repo.py`, que es quien escribe en ese archivo con la marca y la escritura
    atómica de siempre. Si ya está (pendiente o hecha), no se crea otra.
    """
    from .fuentes.repo import Repo
    fuente = Repo({"repos": [str(repo)]})
    fuente.repos, fuente.raiz = [repo], None
    proyectos = fuente.escanear(incluir_hechas=True)
    if not proyectos:
        return None
    proyecto = proyectos[0]
    for tarea in [*proyecto.tareas, *proyecto.hechas]:
        if tarea.texto == TAREA_REVISION:
            return tarea.id
    return fuente.crear(proyecto, TAREA_REVISION, "medio").id


def _marcar_migrado(nombre, repo):
    """Apunta el proyecto en `migrados` de la fuente obsidian. La nota del vault no se toca."""
    datos = configuracion.cargar()
    fuentes = dict(datos.get("fuentes") or {})
    obsidian = dict(fuentes.get("obsidian") or {})
    migrados = dict(obsidian.get("migrados") or {})
    if migrados.get(nombre) != str(repo):
        migrados[nombre] = str(repo)
        obsidian["migrados"] = migrados
        fuentes["obsidian"] = obsidian
        configuracion.guardar({**datos, "fuentes": fuentes})
    return {nombre: str(repo)}


def _reemplazar(ruta, texto):
    temporal = ruta.with_name(f".{ruta.name}.cotejo-tmp")
    with temporal.open("w", encoding="utf-8", newline="") as archivo:
        archivo.write(texto)
    os.replace(temporal, ruta)
