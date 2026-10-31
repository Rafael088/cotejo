"""Revisar el equipo (v1.3.0, cotejo-36mzm0), sin GTK: qué agentes de terminal y qué git hay.

Es lo que enseña la pantalla del primer arranque (`tareas/app/equipo.py`): para cada agente
(los de `enrutador.clientes`) y para git, si está en el PATH y, si no, la página oficial a la
que llevar a la persona. Las direcciones están aquí, en un solo sitio.

Cada agente está en uno de cuatro estados (cotejo-2j6un7): **no instalado**, **falta iniciar
sesión**, **falta elegir modelo** o **listo** (lo decide `enrutador.modelos_vivos.estado`, igual
que para el maestro). Los que tienen
instalador oficial que Cotejo sabe correr (`instalar_agentes.INSTALADORES`) se instalan desde
la pantalla; los demás (Gemini CLI, git) siguen enlazando a su página. A quien no tiene ninguno
se le recomienda uno (`instalar_agentes.RECOMENDADO`).

Antigravity CLI (cotejo-r4yg0n) guarda la sesión en el llavero y no tiene cómo preguntársela
(`modelos_vivos.SESION_INVISIBLE`): instalado dice «Instalado», cuenta como listo y su «Abrir»
lo abre en una terminal para entrar con la cuenta.

Ni la detección ni el git se reinventan: los agentes son `clientes.instalados()` (después de
`instalar_agentes.sumar_al_path`, para ver lo recién instalado) y git es `shutil.which("git")`,
lo mismo que mira `cotejo init`.
"""

import shutil
from dataclasses import dataclass

# La página oficial donde cada herramienta explica cómo instalarse.
PAGINAS = {
    "claude": "https://docs.claude.com/en/docs/claude-code/setup",
    "codex": "https://developers.openai.com/codex/cli",
    "gemini": "https://github.com/google-gemini/gemini-cli",
    "opencode": "https://opencode.ai/docs/",
    "antigravity": "https://antigravity.google/docs/getting-started/",
    "git": "https://git-scm.com/downloads",
}
GIT = "git"
TITULO_GIT = "git (para guardar versiones)"


NO_INSTALADO = "No instalado"
SIN_SESION = "Falta iniciar sesión"
SIN_MODELO = "Falta elegir modelo"
LISTO = "Listo"
INSTALADO = "Instalado"     # instalado, y Cotejo no puede ver si tiene sesión (Antigravity CLI)

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
    modelos: tuple = ()           # lo que el maestro puede lanzar con este agente
    requiere_modelo: bool = False # git no usa modelos

    @property
    def sesion_desconocida(self):
        """Instalado, sin una sesión que Cotejo vea, y sin forma de preguntarla."""
        return self.instalado and not self.con_sesion and not self.sesion_visible

    @property
    def listo(self):
        return (self.instalado and (self.con_sesion or not self.sesion_visible)
                and (not self.requiere_modelo or bool(self.modelos)))

    @property
    def estado(self):
        if not self.instalado:
            return NO_INSTALADO
        if (self.requiere_modelo and not self.modelos
                and (self.con_sesion or not self.sesion_visible)):
            return SIN_MODELO
        if self.sesion_desconocida:
            return INSTALADO
        if not self.con_sesion:
            return SIN_SESION
        return SIN_MODELO if self.requiere_modelo and not self.modelos else LISTO

    @property
    def pide_sesion(self):
        return self.instalado and not self.con_sesion and self.sesion_visible

    @property
    def pide_modelo(self):
        return (self.instalado and (self.con_sesion or not self.sesion_visible)
                and self.requiere_modelo and not self.modelos)

    @property
    def nota(self):
        """Una línea en llano bajo el nombre, o ""."""
        if self.pide_modelo:
            return (f"Abre {self.titulo}, configura un proveedor y un modelo, y pulsa "
                    "«Revisar otra vez».")
        if self.sesion_desconocida:
            return ("Cotejo no puede ver si ya entraste con tu cuenta. Si no, ábrelo con "
                    "«Abrir» y entra; sin sesión, la tarea que le toque se para y lo dice.")
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
            sin_modelo = [a.titulo for a in self.agentes if a.pide_modelo]
            if sin_modelo:
                return f"Te falta elegir un modelo en {sin_modelo[0]}" if len(sin_modelo) == 1 \
                    else "Te falta elegir un modelo en un agente"
            sin = [a.titulo for a in self.agentes if a.pide_sesion]
            return f"Te falta iniciar sesión en {sin[0]}" if len(sin) == 1 else \
                "Te falta iniciar sesión en un agente"
        if not listos:
            return "Te falta un agente de IA"
        if len(listos) == 1:
            return f"Todo listo para empezar con {listos[0]}"
        return f"Todo listo: tienes {len(listos)} agentes"

    @property
    def mensaje(self):
        if not self.hay_agente and self.hay_instalado:
            con_cuenta = next((a for a in self.agentes if a.pide_modelo), None)
            if con_cuenta:
                return con_cuenta.nota
            return ("Toca «Iniciar sesión»: se abre la página del agente en tu navegador para "
                    "que entres con tu cuenta. Cotejo lo nota solo cuando termines.")
        if not self.hay_agente:
            return ("Para preparar proyectos hace falta un agente de IA. Toca «Instalar» en uno "
                    "(si dudas, Claude Code): Cotejo corre su instalador oficial, sin terminal y "
                    "sin pedirte la contraseña del equipo. Después, «Iniciar sesión».")
        if not self.git.listo:
            return ("Falta git, que guarda las versiones de tu proyecto. Instálalo desde su "
                    "página oficial y vuelve a revisar.")
        return "Tienes lo necesario. Los agentes que no uses puedes dejarlos sin instalar."


def hay_git():
    return shutil.which(GIT) is not None


def revisar(preguntar_cli=False):
    """Mira esta máquina ahora mismo (cada llamada vuelve a detectar). `preguntar_cli` deja
    preguntar a los CLIs si tienen sesión en el llavero (`modelos_vivos.sesion`): solo desde un
    hilo, nunca al pintar."""
    from enrutador import clientes, modelos_vivos
    from . import instalar_agentes as inst
    inst.sumar_al_path()
    estados = modelos_vivos.estados(preguntar_cli=preguntar_cli,
                                     refrescar=preguntar_cli)
    ninguno = not any(e.instalado for e in estados)
    agentes = tuple(
        Pieza(actual.cliente, actual.titulo, actual.instalado,
              PAGINAS.get(actual.cliente, ""), con_sesion=actual.sesion,
              instalable=inst.puede_instalar(actual.cliente),
              recomendado=ninguno and actual.cliente == inst.RECOMENDADO,
              sesion_visible=actual.sesion_visible, modelos=actual.modelos,
              requiere_modelo=True)
        for actual in estados)
    return Equipo(agentes, Pieza(GIT, TITULO_GIT, hay_git(), PAGINAS[GIT]))


def es_primer_arranque(fuente):
    """Una fuente de repos sin ningún repo ni carpeta: no está rota, nadie la ha configurado.

    Un repo que no existe o una carpeta mal escrita siguen siendo un problema (ámbar): ahí
    sí hay algo que corregir y se abre el tablero, no esta pantalla.
    """
    return (fuente.problema is not None and hasattr(fuente, "repos")
            and not fuente.repos and not fuente.raiz)
