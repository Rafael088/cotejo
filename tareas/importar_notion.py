"""Traer un proyecto de Notion a su `.cotejo/` (v1.2 · D3): el ensayo y `--aplicar`.

Mucho más modesto que `importar_obsidian` (D1/D2), por decisión de [[Cotejo - Planning v1.2]]
(sección «3. Importador», párrafo de Notion): «importa las tareas por el adaptador que ya
existe y las páginas como referencias; el resto pasa por la tarea de revisión». No hay
plantilla de proyecto que repartir en decisiones, problemas o aprendizajes, porque el
adaptador (`extras/notion/cotejo_notion.py`, hablado por `tareas/fuentes/externa.py`) solo
sabe leer páginas de una base como tareas —título, estado, agente, dificultad—, no su
contenido.

Lo que se trae:

- **Las tareas** del proyecto, tal como las lee `escanear()`, a `tareas.md` con la misma línea
  que escribe Obsidian (`- [ ] texto #dificultad #agente/x ^cotejo-id`).
- **Cada página** (cada tarea es una página de Notion) como una `referencia` con
  `resumen: pendiente` y su URL: lo que hay detrás —notas, subtareas, contenido— no lo trae el
  adaptador, así que se deja para que lo abra quien haga la tarea de revisión.

Reutiliza de `importar_obsidian` (D1/D2) sin tocarlo: `EntradaPlan`, `NoSeImporta`, cómo se
decide qué hacer con `tareas.md` (todo o nada: si el repo ya tiene esas mismas tareas no se
reescribe nada; si tiene otras, se niega), la tarea «Revisar lo importado» y el reemplazo
atómico. Lo que cambia es de dónde sale el reparto: en vez de las secciones de una nota, las
tareas y páginas que devuelve la fuente externa.

La marca de bloque (`^cotejo-xxxxxx`) de cada tarea es **determinista**: un hash de la
referencia de su página en Notion, no un sorteo. Así `planear` da siempre la misma marca para
la misma página, y repetir la importación no la ve como una tarea distinta de la que ya
escribió `--aplicar`.
"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from . import almacen, configuracion, version
from . import importar_obsidian as _io
from .fuentes.externa import Externa
from .fuentes.obsidian import ALFABETO_MARCA, PREFIJO_MARCA
from .importar_obsidian import EntradaPlan, NoSeImporta

FUENTE = "notion"  # la clave en `fuentes` de la config; es fija, como `obsidian` en el otro lado.


@dataclass
class Plan:
    proyecto: str
    repo: dict  # {"ruta", "como", "git_init"}
    url: str = ""
    tareas_md: str = ""
    tareas: int = 0
    entradas: list = field(default_factory=list)  # EntradaPlan("referencia", ...), una por página
    ya_importadas: list = field(default_factory=list)
    avisos: list = field(default_factory=list)

    def resumen(self, detalle=False):
        """Lo que enseña el ensayo: cuántas páginas van a referencias y qué pasa con el repo."""
        conteo = {}
        for entrada in self.entradas:
            conteo[entrada.tipo] = conteo.get(entrada.tipo, 0) + 1
        ya = set(self.ya_importadas)
        datos = {
            "proyecto": self.proyecto, "fuente": FUENTE, "url": self.url, "repo": self.repo,
            "conteo": {"tareas": self.tareas, **dict(sorted(conteo.items()))},
            "ya_importadas": len([e for e in self.entradas if e.origen in ya]),
            "nuevas": len([e for e in self.entradas if e.origen not in ya]),
        }
        if detalle:
            datos["entradas"] = [{**e.fila(), "ya": e.origen in ya} for e in self.entradas]
        if self.avisos:
            datos["avisos"] = self.avisos
        return datos


# --- el ensayo -------------------------------------------------------------------------------

def planear(nombre, destino=None):
    """El `Plan` de importar el proyecto `nombre` de Notion. No escribe nada, en ningún sitio."""
    externa = _externa()
    if externa.problema:
        raise NoSeImporta(
            externa.problema,
            f"`cotejo fuentes info {FUENTE}` dice qué parámetros pide; "
            f"`cotejo fuentes agregar {FUENTE} --comando cotejo-notion` la registra.")
    avisos = []
    proyectos = externa.escanear(incluir_hechas=True, avisos=avisos)
    if externa.problema:  # `escanear` no levanta: deja el fallo en `_fallo` y devuelve []
        raise NoSeImporta(externa.problema, f"`cotejo fuentes probar {FUENTE}` dice qué falla.")
    proyecto = _localizar(proyectos, nombre)
    repo = resolver_repo(proyecto.nombre, destino)
    plan = Plan(proyecto=proyecto.nombre, repo=repo, url=externa.uri(proyecto), avisos=avisos)
    _reparto(plan, [*proyecto.tareas, *proyecto.hechas])
    plan.ya_importadas = _ya_importadas(Path(repo["ruta"]), plan)
    return plan


def _externa():
    """La fuente `notion` de la config, aunque la fuente activa de Cotejo sea otra: se importa
    *desde* Notion, no se lee el proyecto *por* Notion."""
    config = configuracion.parametros(configuracion.cargar(), FUENTE)
    return Externa(FUENTE, config)


def _localizar(proyectos, nombre):
    """El `Proyecto` que se llama `nombre`, sin mayúsculas. Si no hay, sugiere el parecido."""
    buscado = str(nombre).strip().lower()
    for candidato in proyectos:
        if candidato.nombre.lower() == buscado:
            return candidato
    import difflib
    parecidos = difflib.get_close_matches(str(nombre), [p.nombre for p in proyectos], n=3)
    raise NoSeImporta(
        f"No hay ningún proyecto «{nombre}» en Notion."
        + (f" ¿Buscabas {', '.join(parecidos)}?" if parecidos else ""),
        f"`COTEJO_FUENTE={FUENTE} cotejo tareas` enseña qué proyectos ve Cotejo ahí.")


def resolver_repo(nombre, destino):
    """Dónde va a vivir `.cotejo/`: `{"ruta", "como", "git_init"}`.

    Notion no tiene un `repo:` del que adivinarlo, así que `--destino` es obligatorio la
    primera vez. Las siguientes, si ya se marcó como migrado, se reutiliza ese repo sin volver
    a pedirlo: es lo que hace que correrlo otra vez sin `--destino` siga siendo idempotente.
    """
    if destino:
        ruta = Path(destino).expanduser().resolve()
        if ruta.exists() and not ruta.is_dir():
            raise NoSeImporta(f"«{destino}» existe y no es una carpeta",
                              "Pasa en `--destino` una carpeta (puede no existir todavía).")
        return {"ruta": str(ruta), "como": "destino", "git_init": not (ruta / ".git").exists()}

    migrados = configuracion.parametros(configuracion.cargar(), FUENTE).get("migrados") or {}
    conocido = migrados.get(nombre)
    if conocido:
        ruta = Path(conocido)
        return {"ruta": str(ruta), "como": "migrado", "git_init": not (ruta / ".git").exists()}

    raise NoSeImporta(
        f"«{nombre}» no tiene repo: no se importó antes desde Notion y no diste --destino",
        "Pasa `--destino <carpeta>` y se le hará `git init` al aplicar.")


def _reparto(plan, tareas):
    """Llena `plan.tareas_md` (una línea por tarea) y `plan.entradas` (una referencia por página)."""
    lineas = []
    for tarea in tareas:
        ref = (tarea.sitio or {}).get("ref") or tarea.id
        marca = _marca_de(ref)
        lineas.append(_linea(tarea, marca))
        url = (tarea.sitio or {}).get("url") or ""
        texto = f"Página de Notion: {url}" if url else ""
        campos = {"resumen": almacen.PENDIENTE}
        if url:
            campos["url"] = url
        plan.entradas.append(EntradaPlan("referencia", tarea.texto, texto, temas=["notion"],
                                         campos=campos, origen=f"notion:{ref}"))
    plan.tareas = len(lineas)
    plan.tareas_md = (f"# Tareas\n\n" + "\n".join(lineas) + "\n") if lineas else ""


def _marca_de(ref):
    """Una marca de bloque estable para una página de Notion: un hash de su `ref`, no un sorteo.

    Determinista a propósito: `planear` tiene que dar siempre la misma marca para la misma
    página, o `--aplicar` dos veces vería tareas «nuevas» que en realidad ya se escribieron.
    """
    digerido = hashlib.sha256(f"{FUENTE}:{ref}".encode()).hexdigest()
    numero = int(digerido[:12], 16)
    base = len(ALFABETO_MARCA)
    letras = []
    for _ in range(6):
        numero, resto = divmod(numero, base)
        letras.append(ALFABETO_MARCA[resto])
    return PREFIJO_MARCA + "".join(letras)


def _linea(tarea, marca):
    cuerpo = f"- [{'x' if tarea.hecha else ' '}] {' '.join(tarea.texto.split())}"
    if tarea.dificultad:
        cuerpo += f" #{tarea.dificultad}"
    if not tarea.hecha and tarea.estado in ("en-curso", "por-validar"):
        cuerpo += f" #{tarea.estado}"
    if tarea.agente:
        cuerpo += f" #agente/{tarea.agente}"
    return f"{cuerpo} ^{marca}"


def _ya_importadas(repo, plan):
    if not (repo / almacen.CARPETA).is_dir():
        return []
    origenes = {str(e.datos.get("origen")) for e in almacen.Almacen(repo).entradas()
                if e.datos.get("origen")}
    return [e.origen for e in plan.entradas if e.origen in origenes]


# --- aplicar -----------------------------------------------------------------------------------

def aplicar(plan):
    """Escribe `plan` en su repo. Devuelve lo que hizo, para la respuesta de la CLI.

    Mismo orden que `importar_obsidian.aplicar`: lo que puede negarse (unas `tareas.md` que no
    son estas, un repo que no se puede crear) se comprueba antes de escribir la primera
    entrada. Nada se commitea.
    """
    repo = Path(plan.repo["ruta"])
    cotejo = repo / almacen.CARPETA
    tareas_md = cotejo / "tareas.md"
    que_tareas = _io._que_hacer_con_las_tareas(plan, tareas_md)

    hecho = {"git_init": False, "escritas": {}, "ya_estaban": 0, "avisos": list(plan.avisos)}
    if plan.repo["git_init"] and not (repo / ".git").exists():
        _io.git_init(repo)
        hecho["git_init"] = True

    alm = almacen.Almacen(repo)
    cotejo.mkdir(exist_ok=True)
    for tipo in almacen.TIPOS.values():  # el mismo esqueleto que deja `cotejo init`
        if tipo.carpeta and not (cotejo / tipo.carpeta).is_dir():
            (cotejo / tipo.carpeta).mkdir(parents=True)
            (cotejo / tipo.carpeta / ".gitkeep").touch()

    hecho["tareas_md"] = que_tareas
    if que_tareas == "escribir":
        _io._reemplazar(tareas_md, plan.tareas_md)
    elif not tareas_md.is_file():
        _io._reemplazar(tareas_md, "# Tareas\n")

    nombres = _nombres(plan, cotejo)
    ya = set(plan.ya_importadas)
    for entrada in plan.entradas:
        if entrada.origen in ya:
            hecho["ya_estaban"] += 1
            continue
        alm.crear(entrada.tipo, entrada.titulo, entrada.texto, entrada.temas,
                  nombre=nombres.get(entrada.origen),
                  **{**entrada.campos, "origen": entrada.origen})
        hecho["escritas"][entrada.tipo] = hecho["escritas"].get(entrada.tipo, 0) + 1

    hecho["version"] = version.asegurar(repo)
    hecho["tarea_revision"] = _io._tarea_de_revision(repo, plan.proyecto)
    hecho["migrado"] = _marcar_migrado(plan.proyecto, repo)
    if not hecho["avisos"]:
        del hecho["avisos"]
    return hecho


def _nombres(plan, cotejo):
    """El nombre de archivo de cada referencia nueva, reservado contra lo que ya hay."""
    nombres, usados = {}, {}
    for entrada in plan.entradas:
        if entrada.origen in plan.ya_importadas:
            continue
        base = almacen._slug(entrada.titulo, largo=120) or "referencia"
        nombres[entrada.origen] = _io._reservar(cotejo / "referencias", base, ".md", usados)
    return nombres


def _marcar_migrado(nombre, repo):
    """Apunta el proyecto en `migrados` de la fuente notion, igual que hace Obsidian."""
    datos = configuracion.cargar()
    fuentes = dict(datos.get("fuentes") or {})
    notion = dict(fuentes.get(FUENTE) or {})
    migrados = dict(notion.get("migrados") or {})
    if migrados.get(nombre) != str(repo):
        migrados[nombre] = str(repo)
        notion["migrados"] = migrados
        fuentes[FUENTE] = notion
        configuracion.guardar({**datos, "fuentes": fuentes})
    return {nombre: str(repo)}
