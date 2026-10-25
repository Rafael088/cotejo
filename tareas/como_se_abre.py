"""Cómo se abre la app de un proyecto (v1.3.0, cotejo-vn4qd2): lo que usa «Ver mi app».

La arquitectura de un proyecto (una entrada `arquitectura` del almacén, la misma que lleva
`## Piezas`) puede llevar una sección que dice cómo verla funcionando, en llano y estable:

    ## Cómo se abre

    - comando: npm run dev
    - url: http://localhost:5173
    - qué esperar: la página de reservas, con la lista vacía la primera vez

- **comando**: lo que arranca la app, en la carpeta del proyecto. Un solo programa con sus
  argumentos: sin `&&`, `|`, `;` ni redirecciones (se corre sin shell) y nunca con `sudo`.
- **url** (opcional): dónde se ve. Una dirección `http(s)://` o, sin comando, un archivo del
  proyecto (`index.html`): una página la sirve Cotejo con su propio servidor; otro archivo se
  abre con el programa que tenga la persona para él.
- **qué esperar**: una frase de lo que la persona tiene que ver al abrirla.
- **carpeta** (opcional): una subcarpeta del proyecto donde correr el comando.

La deja la preparación (`tareas/inicio.py`) y la mantiene al día cada agente que cambie cómo
se abre (`enrutador/encargo.py`). Sin ella, `plan_de` deduce con prudencia —un `package.json`
con script `dev` o `start`, o un `index.html` en la raíz— y si tampoco, lo dice en llano.

Todo aquí es puro salvo `plan_de` y `deducir`, que solo leen. Arrancar, esperar y parar el
proceso es de `tareas/servidor_app.py`; el board (`tareas/app/ver_app.py`) solo pinta.
"""

import json
import re
import shlex
import unicodedata
from dataclasses import dataclass
from pathlib import Path

TITULO_SECCION = "Cómo se abre"
CLAVES = {"comando": "comando", "url": "url", "que esperar": "que_esperar",
          "carpeta": "carpeta"}
PROHIBIDOS = ("sudo", "su", "doas", "pkexec", "runas")
OPERADORES = ("&&", "||", "|", ";", ">", ">>", "<", "&", "2>", "2>&1")
# El formato tal como se les pide a los agentes (preparar y cada encargo).
FORMATO = "\n".join([
    "    ## Cómo se abre",
    "",
    "    - comando: <un solo programa con sus argumentos, p. ej. `npm run dev`; sin `&&`, `|`, "
    "`;` ni `sudo`; vacío si basta con abrir un archivo>",
    "    - url: <dónde se ve, p. ej. `http://localhost:5173`, o un archivo del proyecto como "
    "`index.html`>",
    "    - qué esperar: <una frase con lo que la persona verá al abrirla>",
    "    - carpeta: <opcional: la subcarpeta del proyecto donde correr el comando>",
])
SIN_ANOTAR = ("No sé cómo abrir tu app todavía: pídeselo a un agente con una tarea como "
              "«Anota en la arquitectura cómo se abre la app».")

_SECCION_RE = re.compile(r"^#{2,3}\s+(.+?)\s*#*\s*$")
_LINEA_RE = re.compile(r"^\s*(?:[-*]\s+)?([^:]{1,30}?)\s*:\s*(.*?)\s*$")


@dataclass(frozen=True)
class ComoSeAbre:
    """Lo anotado (o deducido). `origen`: «arquitectura» o «deducido»."""

    comando: str = ""
    url: str = ""
    que_esperar: str = ""
    carpeta: str = ""
    origen: str = "arquitectura"

    @property
    def es_web(self):
        return self.url.startswith(("http://", "https://"))

    @property
    def tipo(self):
        """`servidor` (comando y dirección), `programa` (solo comando: se mira si dice una
        dirección), `pagina` (un .html del proyecto que sirve Cotejo), `enlace` (una dirección
        sin comando) o `archivo` (otro archivo del proyecto)."""
        if self.comando:
            return "servidor" if self.es_web else "programa"
        if self.es_web:
            return "enlace"
        return "pagina" if self.url.lower().endswith((".html", ".htm")) else "archivo"

    def argv(self):
        return shlex.split(self.comando) if self.comando else []


@dataclass(frozen=True)
class Plan:
    """Lo que hará «Ver mi app»: `como` y la carpeta donde, o `motivo` en llano si no se puede."""

    como: ComoSeAbre = None
    carpeta: str = ""
    motivo: str = ""

    @property
    def ok(self):
        return self.como is not None and not self.motivo


def _normal(texto):
    plano = unicodedata.normalize("NFKD", texto)
    plano = "".join(c for c in plano if not unicodedata.combining(c))
    return " ".join(plano.lower().replace("_", " ").split())


def _lineas_de_la_seccion(cuerpo):
    """Las líneas bajo `## Cómo se abre` (o `###`), o None si no hay tal sección."""
    lineas = (cuerpo or "").splitlines()
    for i, linea in enumerate(lineas):
        m = _SECCION_RE.match(linea.strip())
        if m and _normal(m.group(1)) == _normal(TITULO_SECCION):
            dentro = []
            for siguiente in lineas[i + 1:]:
                if _SECCION_RE.match(siguiente.strip()):
                    break
                dentro.append(siguiente)
            return dentro
    return None


def tiene_seccion(cuerpo):
    return _lineas_de_la_seccion(cuerpo) is not None


def seccion(cuerpo):
    """El texto de la sección entera (con su título), o "" si no la hay."""
    lineas = _lineas_de_la_seccion(cuerpo)
    if lineas is None:
        return ""
    return "\n".join([f"## {TITULO_SECCION}", *lineas]).rstrip()


def analizar(cuerpo):
    """(ComoSeAbre o None, [errores]). Sin la sección: (None, []), y no es un error."""
    lineas = _lineas_de_la_seccion(cuerpo)
    if lineas is None:
        return None, []
    campos, errores = {}, []
    for linea in lineas:
        if not linea.strip() or linea.strip().startswith("<!--"):
            continue
        m = _LINEA_RE.match(linea)
        clave = CLAVES.get(_normal(m.group(1))) if m else None
        if clave is None:
            errores.append(f"«{linea.strip()}» no es una línea de «{TITULO_SECCION}»: van "
                           "`comando:`, `url:`, `qué esperar:` y `carpeta:`")
            continue
        campos[clave] = m.group(2).strip().strip("`").strip()
    como = ComoSeAbre(**campos)
    errores += errores_de(como)
    return (None if errores else como), errores


def errores_de(como):
    """Lo que impide correr `como` sin riesgo, en frases para quien lo escribió."""
    errores = []
    if not como.comando and not como.url:
        errores.append(f"«{TITULO_SECCION}» necesita `comando:`, `url:` o los dos")
    if como.comando:
        try:
            argv = shlex.split(como.comando)
        except ValueError as error:
            return errores + [f"el comando no se entiende ({error})"]
        if argv and Path(argv[0]).name in PROHIBIDOS:
            errores.append(f"el comando no puede empezar por `{argv[0]}`")
        if any(a in OPERADORES or a.startswith(("$(", "`")) for a in argv):
            errores.append("el comando va sin shell: un solo programa con sus argumentos, sin "
                           "`&&`, `|`, `;` ni redirecciones (usa `carpeta:` para la subcarpeta)")
    for nombre, valor in (("carpeta", como.carpeta), ("url", "" if como.es_web else como.url)):
        if valor and (Path(valor).is_absolute() or ".." in Path(valor).parts):
            errores.append(f"`{nombre}:` va relativa a la carpeta del proyecto y sin `..`")
    return errores


def errores(cuerpo):
    """Solo los errores de la sección (para validar al anotar o editar la arquitectura)."""
    return analizar(cuerpo)[1]


def con_seccion_previa(texto, cuerpo_previo):
    """`texto` con la sección «Cómo se abre» de `cuerpo_previo` si el nuevo no trae una: anotar
    otra vez la arquitectura (un reintento, piezas nuevas) no borra cómo se abre la app."""
    anterior = seccion(cuerpo_previo)
    if not anterior or tiene_seccion(texto):
        return texto
    return f"{texto.rstrip()}\n\n{anterior}\n" if texto.strip() else f"{anterior}\n"


# --- con E/S (solo leer) ---------------------------------------------------------------------

def de_la_arquitectura(carpeta):
    """(ComoSeAbre o None, [errores]) de la arquitectura más reciente que lleva la sección."""
    from . import almacen, conocimiento
    alm = almacen.Almacen(carpeta)
    if not alm.existe():
        return None, []
    con = [e for e in alm.entradas("arquitectura") if tiene_seccion(e.cuerpo)]
    if not con:
        return None, []
    entrada = max(con, key=lambda e: conocimiento._marca_de(alm, e))
    return analizar(entrada.cuerpo)


def deducir(carpeta):
    """Sin anotación, lo que se puede suponer sin riesgo, o None."""
    carpeta = Path(carpeta)
    paquete = carpeta / "package.json"
    if paquete.is_file():
        try:
            scripts = json.loads(paquete.read_text(encoding="utf-8")).get("scripts") or {}
        except (OSError, ValueError, AttributeError):
            scripts = {}
        for script in ("dev", "start"):
            if isinstance(scripts, dict) and scripts.get(script):
                return ComoSeAbre(comando=f"npm run {script}", origen="deducido")
    if (carpeta / "index.html").is_file():
        return ComoSeAbre(url="index.html", origen="deducido")
    return None


def plan_de(carpeta):
    """El `Plan` de «Ver mi app» para la carpeta principal del proyecto (nunca un worktree)."""
    if not carpeta or not Path(carpeta).is_dir():
        return Plan(motivo="No encuentro la carpeta de este proyecto en tu equipo.")
    como, errores_ = de_la_arquitectura(carpeta)
    if errores_:
        return Plan(carpeta=str(carpeta), motivo=(
            "La forma de abrir tu app que dejó anotada el agente no se puede usar: "
            + "; ".join(errores_) + ". Pídele a un agente que la corrija."))
    como = como or deducir(carpeta)
    if como is None:
        return Plan(carpeta=str(carpeta), motivo=SIN_ANOTAR)
    return Plan(como=como, carpeta=str(carpeta))
