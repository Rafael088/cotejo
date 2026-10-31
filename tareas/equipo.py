"""Revisar el equipo (v1.3.0, cotejo-36mzm0), sin GTK: qué agentes de terminal y qué git hay.

Es lo que enseña la pantalla del primer arranque (`tareas/app/equipo.py`): para cada agente
(los de `enrutador.clientes`) y para git, si está en el PATH y, si no, la página oficial a la
que llevar a la persona. Las direcciones están aquí, en un solo sitio.

Cada agente está en uno de tres estados (cotejo-2j6un7): **no instalado**, **falta iniciar
sesión** o **listo** (instalado y con sesión, `enrutador.modelos_vivos.sesion`). Los que tienen
instalador oficial que Cotejo sabe correr (`instalar_agentes.INSTALADORES`) se instalan desde
la pantalla; los demás (Gemini CLI, git) siguen enlazando a su página. A quien no tiene ninguno
se le recomienda uno (`instalar_agentes.RECOMENDADO`).

Antigravity CLI (cotejo-r4yg0n) guarda la sesión en el llavero y no tiene cómo preguntársela
(`modelos_vivos.SESION_INVISIBLE`): instalado dice «Instalado», cuenta como listo y su «Abrir»
lo abre en una terminal para entrar con la cuenta.

Ni la detección ni el git se reinventan: los agentes son `clientes.instalados()` (después de
`instalar_agentes.sumar_al_path`, para ver lo recién instalado) y git es `shutil.which("git")`,
lo mismo que mira `cotejo init`.

Instalado no basta para que git esté listo (cotejo-vz6v3c): al guardar un cambio Cotejo empuja
la rama, y sin credenciales git se para a pedir usuario y contraseña. `puede_empujar` mira, sin
lanzar nada y sin red, si hay con qué: un `credential.helper` en la config de git (el de
`gh auth login`/`gh auth setup-git`, el llavero del sistema, el de Git for Windows…) o una
llave SSH en `~/.ssh`. El helper de GitHub CLI solo cuenta si gh tiene sesión (`hosts.yml`).
Sin nada de eso, git queda en «Falta conectar» y la pantalla ofrece conectarlo con GitHub CLI
(`instalar_agentes.conectar_git`). Cotejo nunca guarda contraseñas ni tokens: ni en su config
ni en la de git (nada de `credential.helper store`); de eso se encarga gh o el llavero.
La identidad (nombre y correo) no se mira: si falta, Cotejo commitea como «Cotejo»
(`conexion.IDENTIDAD_COTEJO`).
"""

import os
import re
import shutil
from pathlib import Path

from . import rutas
from dataclasses import dataclass

# La página oficial donde cada herramienta explica cómo instalarse.
PAGINAS = {
    "claude": "https://docs.claude.com/en/docs/claude-code/setup",
    "codex": "https://developers.openai.com/codex/cli",
    "gemini": "https://github.com/google-gemini/gemini-cli",
    "opencode": "https://opencode.ai/docs/",
    "antigravity": "https://antigravity.google/docs/getting-started/",
    "git": "https://git-scm.com/downloads",
    "gh": "https://cli.github.com/",
}
GIT = "git"
TITULO_GIT = "git (para guardar versiones)"


NO_INSTALADO = "No instalado"
SIN_SESION = "Falta iniciar sesión"
LISTO = "Listo"
INSTALADO = "Instalado"     # instalado, y Cotejo no puede ver si tiene sesión (Antigravity CLI)
SIN_CONEXION = "Falta conectar"   # git instalado, sin credenciales para empujar

# Una línea en llano bajo el nombre, por agente, mientras no esté instalado.
NOTAS = {
    "gemini": "Solo con licencia de empresa. Con el plan gratuito, Pro o Ultra de Google, "
              "usa Antigravity CLI.",
    "antigravity": "Lo que reemplaza a Gemini CLI para cuentas personales de Google.",
}


@dataclass(frozen=True)
class Pieza:
    clave: str        # "claude", "codex", … o "git"
    titulo: str       # cómo se llama en pantalla
    instalado: bool
    pagina: str       # dónde se instala (oficial)
    con_sesion: bool = True       # git no tiene sesión: cuenta como con sesión
    instalable: bool = False      # Cotejo sabe correr su instalador oficial aquí
    recomendado: bool = False     # el que se sugiere a quien no tiene ninguno
    sesion_visible: bool = True   # Cotejo sabe si tiene sesión (Antigravity CLI no)

    @property
    def sesion_desconocida(self):
        """Instalado, sin una sesión que Cotejo vea, y sin forma de preguntarla."""
        return self.instalado and not self.con_sesion and not self.sesion_visible

    @property
    def listo(self):
        return self.instalado and (self.con_sesion or not self.sesion_visible)

    @property
    def estado(self):
        if not self.instalado:
            return NO_INSTALADO
        if self.sesion_desconocida:
            return INSTALADO
        if self.con_sesion:
            return LISTO
        return SIN_CONEXION if self.clave == GIT else SIN_SESION

    @property
    def pide_sesion(self):
        return self.instalado and not self.con_sesion and self.sesion_visible

    @property
    def nota(self):
        """Una línea en llano bajo el nombre, o ""."""
        if self.sesion_desconocida:
            return ("Cotejo no puede ver si ya entraste con tu cuenta. Si no, ábrelo con "
                    "«Abrir» y entra; sin sesión, la tarea que le toque se para y lo dice.")
        if self.clave == GIT and self.pide_sesion:
            return ("Está instalado, pero al guardar un cambio te pediría usuario y contraseña. "
                    "Conéctalo una vez con tu cuenta de GitHub y no te lo volverá a pedir. "
                    "Cotejo nunca guarda tu contraseña.")
        if self.instalado:
            return ""
        if self.recomendado:
            return "Si no sabes cuál elegir, empieza por este."
        return NOTAS.get(self.clave, "")

    @property
    def texto_enlace(self):
        return f"Cómo instalar {self.titulo.split(' (')[0]}"


@dataclass(frozen=True)
class Equipo:
    agentes: tuple
    git: Pieza

    @property
    def piezas(self):
        return (*self.agentes, self.git)

    @property
    def hay_agente(self):
        """Algún agente listo: instalado y con sesión."""
        return any(a.listo for a in self.agentes)

    @property
    def hay_instalado(self):
        return any(a.instalado for a in self.agentes)

    @property
    def faltan(self):
        return tuple(p for p in self.piezas if not p.listo)

    @property
    def titular(self):
        listos = [a.titulo for a in self.agentes if a.listo]
        if not listos and self.hay_instalado:
            sin = [a.titulo for a in self.agentes if a.pide_sesion]
            return f"Te falta iniciar sesión en {sin[0]}" if len(sin) == 1 else \
                "Te falta iniciar sesión en un agente"
        if not listos:
            return "Te falta un agente de IA"
        if self.git.pide_sesion:
            return "Casi listo: falta conectar git para guardar tus cambios"
        if not self.git.instalado:
            return "Casi listo: falta git"
        if len(listos) == 1:
            return f"Todo listo para empezar con {listos[0]}"
        return f"Todo listo: tienes {len(listos)} agentes"

    @property
    def mensaje(self):
        if not self.hay_agente and self.hay_instalado:
            return ("Toca «Iniciar sesión»: se abre la página del agente en tu navegador para "
                    "que entres con tu cuenta. Cotejo lo nota solo cuando termines.")
        if not self.hay_agente:
            return ("Para preparar proyectos hace falta un agente de IA. Toca «Instalar» en uno "
                    "(si dudas, Claude Code): Cotejo corre su instalador oficial, sin terminal y "
                    "sin pedirte la contraseña del equipo. Después, «Iniciar sesión».")
        if self.git.pide_sesion:
            return ("Toca «Conectar» en git: se abre una terminal con «gh auth login» para que "
                    "entres con tu cuenta de GitHub en el navegador. Cotejo lo nota solo cuando "
                    "termines y nunca guarda tu contraseña.")
        if not self.git.listo:
            return ("Falta git, que guarda las versiones de tu proyecto. Instálalo desde su "
                    "página oficial y vuelve a revisar.")
        return "Tienes lo necesario. Los agentes que no uses puedes dejarlos sin instalar."


def hay_git():
    return shutil.which(GIT) is not None


# --- ¿puede empujar? ----------------------------------------------------------------------------

_SECCION = re.compile(r'^\s*\[\s*([A-Za-z0-9.-]+)(?:\s+"[^"]*")?\s*\]')
_CLAVE = re.compile(r'^\s*([A-Za-z0-9-]+)\s*(?:=\s*(.*?))?\s*$')
_GH_HELPER = re.compile(r"\bgh(\.exe)?['\"]?\s+auth\s+git-credential\b")
LLAVES_SSH = ("id_ed25519", "id_ecdsa", "id_rsa", "id_ed25519_sk", "id_ecdsa_sk", "id_dsa")


def _casa(casa=None):
    return Path(casa) if casa is not None else Path(os.environ.get("HOME") or Path.home())


def configs_de_git(casa=None, entorno=None):
    """Los archivos de config de git que mira git: sistema, global y el de XDG."""
    entorno = os.environ if entorno is None else entorno
    casa = _casa(casa)
    xdg = rutas.config_xdg(casa, entorno)
    return [Path(entorno.get("GIT_CONFIG_SYSTEM") or "/etc/gitconfig"),
            xdg / "git" / "config",
            Path(entorno.get("GIT_CONFIG_GLOBAL") or casa / ".gitconfig")]


def helpers_de_credenciales(archivos):
    """Los `helper` de las secciones `[credential]` (y `[credential "<url>"]`), en orden. Uno
    vacío (`helper =`) borra los de antes, como hace git."""
    helpers = []
    for archivo in archivos:
        try:
            lineas = Path(archivo).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        seccion = ""
        for linea in lineas:
            if linea.lstrip().startswith(("#", ";")):
                continue
            m = _SECCION.match(linea)
            if m:
                seccion = m.group(1).lower()
                continue
            m = _CLAVE.match(linea)
            if seccion == "credential" and m and m.group(1).lower() == "helper":
                valor = (m.group(2) or "").strip().strip('"')
                if valor:
                    helpers.append(valor)
                else:
                    helpers.clear()
    return helpers


def gh_con_sesion(casa=None, entorno=None):
    """¿GitHub CLI tiene alguna cuenta? Lo dice su `hosts.yml` (el token puede estar en el
    llavero, pero el host queda apuntado ahí)."""
    entorno = os.environ if entorno is None else entorno
    if entorno.get("GH_TOKEN") or entorno.get("GITHUB_TOKEN"):
        return True
    casa = _casa(casa)
    carpeta = entorno.get("GH_CONFIG_DIR") or rutas.config_xdg(casa, entorno) / "gh"
    try:
        texto = (Path(carpeta) / "hosts.yml").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return any(re.match(r"^[^\s#][^:]*:\s*$", linea) for linea in texto.splitlines())


def llave_ssh(casa=None):
    """¿Hay una llave SSH con su nombre de siempre en `~/.ssh`?"""
    ssh = _casa(casa) / ".ssh"
    return any((ssh / nombre).is_file() for nombre in LLAVES_SSH)


def puede_empujar(casa=None, entorno=None):
    """Con qué empujaría git sin pedir usuario y contraseña: "helper", "ssh" o None.

    Sin lanzar nada y sin red: lee la config de git, la de gh y `~/.ssh`. El helper de GitHub
    CLI (`gh auth git-credential`) solo cuenta si gh tiene sesión."""
    helpers = helpers_de_credenciales(configs_de_git(casa, entorno))
    if any(not _GH_HELPER.search(h) or gh_con_sesion(casa, entorno) for h in helpers):
        return "helper"
    if llave_ssh(casa):
        return "ssh"
    return None


def revisar(preguntar_cli=False):
    """Mira esta máquina ahora mismo (cada llamada vuelve a detectar). `preguntar_cli` deja
    preguntar a los CLIs si tienen sesión en el llavero (`modelos_vivos.sesion`): solo desde un
    hilo, nunca al pintar."""
    from enrutador import clientes, modelos_vivos
    from . import instalar_agentes as inst
    inst.sumar_al_path()
    puestos = set(clientes.instalados())
    ninguno = not puestos
    agentes = tuple(
        Pieza(nombre, cliente.titulo or nombre, nombre in puestos, PAGINAS.get(nombre, ""),
              con_sesion=nombre in puestos and modelos_vivos.sesion(
                  nombre, preguntar_cli=preguntar_cli),
              instalable=inst.puede_instalar(nombre),
              recomendado=ninguno and nombre == inst.RECOMENDADO,
              sesion_visible=modelos_vivos.sesion_visible(nombre))
        for nombre, cliente in clientes.CLIENTES.items())
    instalado = hay_git()
    git = Pieza(GIT, TITULO_GIT, instalado, PAGINAS[GIT],
                con_sesion=instalado and puede_empujar() is not None)
    return Equipo(agentes, git)


def es_primer_arranque(fuente):
    """Una fuente de repos sin ningún repo ni carpeta: no está rota, nadie la ha configurado.

    Un repo que no existe o una carpeta mal escrita siguen siendo un problema (ámbar): ahí
    sí hay algo que corregir y se abre el tablero, no esta pantalla.
    """
    return (fuente.problema is not None and hasattr(fuente, "repos")
            and not fuente.repos and not fuente.raiz)
