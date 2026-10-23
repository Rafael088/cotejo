"""Revisar el equipo (v1.3.0, cotejo-36mzm0), sin GTK: qué agentes de terminal y qué git hay.

Es lo que enseña la pantalla del primer arranque (`tareas/app/equipo.py`): para cada agente
(los de `enrutador.clientes`) y para git, si está en el PATH y, si no, la página oficial a la
que llevar a la persona. Cotejo **nunca instala nada**: solo enlaza. Las direcciones están
aquí, en un solo sitio.

Ni la detección ni el git se reinventan: los agentes son `clientes.instalados()` y git es
`shutil.which("git")`, lo mismo que mira `cotejo init`.
"""

import shutil
from dataclasses import dataclass

# La página oficial donde cada herramienta explica cómo instalarse.
PAGINAS = {
    "claude": "https://docs.claude.com/en/docs/claude-code/setup",
    "codex": "https://developers.openai.com/codex/cli",
    "gemini": "https://github.com/google-gemini/gemini-cli",
    "opencode": "https://opencode.ai/docs/",
    "git": "https://git-scm.com/downloads",
}
GIT = "git"
TITULO_GIT = "git (para guardar versiones)"


@dataclass(frozen=True)
class Pieza:
    clave: str        # "claude", "codex", … o "git"
    titulo: str       # cómo se llama en pantalla
    listo: bool
    pagina: str       # dónde se instala (oficial)

    @property
    def estado(self):
        return "Listo" if self.listo else "No instalado"

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
        return any(a.listo for a in self.agentes)

    @property
    def faltan(self):
        return tuple(p for p in self.piezas if not p.listo)

    @property
    def titular(self):
        listos = [a.titulo for a in self.agentes if a.listo]
        if not listos:
            return "Te falta un agente de IA"
        if len(listos) == 1:
            return f"Todo listo para empezar con {listos[0]}"
        return f"Todo listo: tienes {len(listos)} agentes"

    @property
    def mensaje(self):
        if not self.hay_agente:
            return ("Para preparar proyectos hace falta un agente de IA. Elige uno, instálalo "
                    "desde su página oficial y vuelve a revisar. Cotejo no instala nada por ti.")
        if not self.git.listo:
            return ("Falta git, que guarda las versiones de tu proyecto. Instálalo desde su "
                    "página oficial y vuelve a revisar.")
        return "Tienes lo necesario. Los agentes que no uses puedes dejarlos sin instalar."


def hay_git():
    return shutil.which(GIT) is not None


def revisar():
    """Mira esta máquina ahora mismo (cada llamada vuelve a detectar)."""
    from enrutador import clientes
    puestos = set(clientes.instalados())
    agentes = tuple(
        Pieza(nombre, cliente.titulo or nombre, nombre in puestos, PAGINAS.get(nombre, ""))
        for nombre, cliente in clientes.CLIENTES.items())
    return Equipo(agentes, Pieza(GIT, TITULO_GIT, hay_git(), PAGINAS[GIT]))


def es_primer_arranque(fuente):
    """Una fuente de repos sin ningún repo ni carpeta: no está rota, nadie la ha configurado.

    Un repo que no existe o una carpeta mal escrita siguen siendo un problema (ámbar): ahí
    sí hay algo que corregir y se abre el tablero, no esta pantalla.
    """
    return (fuente.problema is not None and hasattr(fuente, "repos")
            and not fuente.repos and not fuente.raiz)
