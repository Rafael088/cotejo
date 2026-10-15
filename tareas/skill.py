"""Cómo se entera un agente de que Cotejo existe, sea cual sea el agente.

Un agente solo sabe que hay que llamar a un comando si está escrito en el archivo que su
harness carga solo, y ese archivo es distinto en cada uno —Claude Code lee `~/.claude/skills/`,
Codex y opencode un `AGENTS.md`, Gemini un `GEMINI.md`, y mañana habrá otro—.

El protocolo se escribe una vez en `skills/cotejo/SKILL.md` y de ahí salen las dos formas de
entregarlo: donde el agente entiende de skills se copia el archivo tal cual, y donde solo hay
un archivo de instrucciones se le inyecta un bloque corto entre marcas. Corto a propósito: ese
archivo se carga en todas las sesiones de todos los proyectos, y meterle el protocolo entero
sería el desperdicio de contexto que Cotejo existe para evitar.

Solo se toca el archivo de un agente que ya esté instalado —que su carpeta de config exista o que
su comando esté en el PATH: quien lo acaba de instalar y nunca lo abrió aún no tiene carpeta—, el bloque se reemplaza entre sus
marcas y nunca se duplica, y antes de escribir en un archivo ajeno se deja una copia `.bak`.
"""

import os
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SKILL = RAIZ / "skills" / "cotejo" / "SKILL.md"
# El detalle que un agente no necesita siempre va en archivos al lado de SKILL.md, para que la
# skill que se carga en cada sesión sea corta; `SKILL.md` dice cuándo leer cada uno.
REFERENCIAS = SKILL.parent / "referencias"
# Las skills cortas que acompañan al protocolo, para tareas que no son trabajar las tareas
# (cambiar de fuente, registrar modelos). Van aparte para que un agente no cargue el protocolo
# entero —que es largo— para algo que se resuelve en un comando. Solo a los agentes que
# entienden de skills.
COMPANERAS = ("cotejo-fuentes", "cotejo-modelos")

# El comando de cada agente, para reconocerlo aunque nunca se haya abierto y no tenga carpeta de
# config todavía. `shutil.which` entiende PATHEXT, así que en Windows encuentra `claude.exe` y
# `claude.cmd` sin más (el instalador llama a este mismo código).
BINARIOS = {"Claude Code": "claude", "Codex": "codex", "Gemini CLI": "gemini",
            "opencode": "opencode"}

INICIO = "<!-- cotejo:inicio -->"
FIN = "<!-- cotejo:fin -->"

# Cómo se llamaba esto antes: cuando el enrutador era su propio programa (focorouter) y cuando el
# producto se llamaba Foco. Se limpia al instalar: dos protocolos instalados, uno con el nombre
# de antes, es peor que ninguno.
VIEJAS_MARCAS = (("<!-- focorouter:inicio -->", "<!-- focorouter:fin -->"),
                 ("<!-- foco:inicio -->", "<!-- foco:fin -->"))
VIEJAS_SKILLS = ("focorouter", "foco", "foco-fuentes", "foco-modelos")

BLOQUE = f"""{INICIO}
## Las tareas de los proyectos viven en Cotejo, y no toda tarea es para ti

Antes de ponerte con una tarea pendiente de un proyecto, mira qué hay y a quién le toca. Hay
modelos configurados y una persona, y una de cada tres tareas no es para ningún modelo —comprar algo,
firmar algo, abrir una cuenta—: intentarla produce una entrega falsa.

    cotejo plan --proyecto <nombre>    # qué modelo recibiría cada pendiente, en JSON
    cotejo decidir --tarea <id>        # a quién le toca esa, y por qué
    cotejo modelos                     # catálogo; también admite `modelos agregar`
    cotejo modelos agregar --clave <c> --modelo-id <id> --cliente <cliente> --nivel n2
    cotejo protocolo                   # el núcleo; --completo añade las referencias

Preguntar no escribe nada. Despachar toma la tarea; entregarla sigue siendo de quien la hace,
y comprobarla, de una persona.

Con `--motor headless|sesion`, el cliente hereda la carpeta de donde corrió `cotejo` si el
proyecto no tiene ruta en `enrutador.proyectos` (config.json). No asumas la ruta del autor:
pregúntala o compruébala con `despachar <id> --simular`, que no toma la tarea.
{FIN}"""

ENTRE_MARCAS = re.compile(re.escape(INICIO) + r".*?" + re.escape(FIN) + r"\n?", re.DOTALL)
ENTRE_MARCAS_VIEJAS = re.compile("|".join(
    re.escape(inicio) + r".*?" + re.escape(fin) + r"\n?" for inicio, fin in VIEJAS_MARCAS),
    re.DOTALL)


def cuerpo(ruta=None):
    """El protocolo sin el frontmatter, que es metadato de Claude Code y no del contenido."""
    texto = (ruta or SKILL).read_text(encoding="utf-8")
    if texto.startswith("---\n"):
        _, _, resto = texto[4:].partition("\n---\n")
        texto = resto
    return texto.lstrip("\n")


def referencias(carpeta=None):
    """Los archivos de referencia de la skill, ordenados: lo que se reparte al lado de SKILL.md."""
    carpeta = Path(carpeta) if carpeta else REFERENCIAS
    return sorted(carpeta.glob("*.md")) if carpeta.is_dir() else []


def copiar_referencias(destino):
    """Deja las referencias en `destino` (la carpeta de la skill) y quita las que ya no existen."""
    fuente = referencias()
    final = destino / "referencias"
    shutil.rmtree(final, ignore_errors=True)
    if fuente:
        final.mkdir(parents=True, exist_ok=True)
        for archivo in fuente:
            shutil.copy(archivo, final / archivo.name)
    return [final / a.name for a in fuente]


def inyectar(texto, bloque=BLOQUE):
    """El archivo con el bloque puesto, reemplazándolo si ya estaba.

    Pura y aparte porque lo que hay que poder probar no es que escriba, es que correrlo dos
    veces deje el archivo igual y que no se lleve por delante lo que el usuario tenga alrededor.
    """
    texto = ENTRE_MARCAS_VIEJAS.sub("", texto)
    if INICIO in texto:
        return ENTRE_MARCAS.sub(bloque + "\n", texto, count=1)
    if texto and not texto.endswith("\n"):
        texto += "\n"
    return texto + ("\n" if texto else "") + bloque + "\n"


def quitar(texto):
    """El archivo sin el bloque y sin el hueco donde estaba. Vacío si no quedaba nada más."""
    limpio = ENTRE_MARCAS_VIEJAS.sub("", ENTRE_MARCAS.sub("", texto))
    if not limpio.strip():
        return ""
    return re.sub(r"\n{3,}", "\n\n", limpio).rstrip("\n") + "\n"


def destinos(hogar=None):
    """Dónde escribir, por agente: `(nombre, de qué depende, cómo, dónde)`.

    Lo de lo que depende es la carpeta del agente: si no existe y su comando tampoco está en el
    PATH (`instalado`), ese agente no está instalado y no se le crea nada. Añadir uno nuevo es una línea más.
    """
    # XDG_CONFIG_HOME solo manda cuando el hogar es el de verdad: si alguien pasa un hogar de
    # mentira y la variable siguiera ganando, escribiríamos en la config real creyendo que
    # estamos en un temporal, y eso se descubre cuando ya tocaste el archivo del usuario.
    xdg = os.environ.get("XDG_CONFIG_HOME") if hogar is None else None
    hogar = Path(hogar or Path.home())
    config = Path(xdg) if xdg else hogar / ".config"
    return [
        ("Claude Code", hogar / ".claude", "skill", hogar / ".claude/skills/cotejo/SKILL.md"),
        ("Codex", hogar / ".codex", "skill", hogar / ".codex/skills/cotejo/SKILL.md"),
        ("Gemini CLI", hogar / ".gemini", "bloque", hogar / ".gemini/GEMINI.md"),
        ("opencode", config / "opencode", "bloque", config / "opencode/AGENTS.md"),
    ]


def instalado(nombre, carpeta):
    """Si el agente está: su carpeta de config existe o su comando responde en el PATH."""
    binario = BINARIOS.get(nombre)
    return carpeta.is_dir() or bool(binario and shutil.which(binario))


def limpiar_viejas(hogar=None):
    """Quita las skills que instalaba el enrutador cuando era un programa aparte."""
    quitadas = []
    for _, carpeta, modo, ruta in destinos(hogar):
        if modo != "skill":
            continue
        for vieja in VIEJAS_SKILLS:
            antigua = ruta.parent.parent / vieja
            if antigua.is_dir():
                shutil.rmtree(antigua, ignore_errors=True)
                quitadas.append(str(antigua))
    return quitadas


def poner_bloque(ruta):
    antes = ruta.read_text(encoding="utf-8") if ruta.exists() else ""
    despues = inyectar(antes)
    if despues == antes:
        return False
    if antes:
        shutil.copy(ruta, ruta.with_suffix(ruta.suffix + ".bak"))
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(despues, encoding="utf-8")
    return True


def instalar(hogar=None, extra=()):
    hecho = [f"quitada la skill vieja en {ruta}" for ruta in limpiar_viejas(hogar)]
    for nombre, carpeta, modo, ruta in destinos(hogar):
        if not instalado(nombre, carpeta):
            continue
        if modo == "skill":
            ruta.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(SKILL, ruta)
            hecho.append(f"{nombre}: skill en {ruta}")
            if copiar_referencias(ruta.parent):
                hecho.append(f"{nombre}: referencias en {ruta.parent / 'referencias'}")
            for companera in COMPANERAS:
                destino = ruta.parent.parent / companera / "SKILL.md"
                destino.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(RAIZ / "skills" / companera / "SKILL.md", destino)
                hecho.append(f"{nombre}: skill en {destino}")
        elif poner_bloque(ruta):
            hecho.append(f"{nombre}: aviso en {ruta}")
        else:
            hecho.append(f"{nombre}: ya estaba al día")
    for ruta in extra:
        ruta = Path(ruta).expanduser()
        poner_bloque(ruta)
        hecho.append(f"a mano: aviso en {ruta}")
    return hecho


def desinstalar(hogar=None, extra=()):
    hecho = [f"quitada la skill vieja en {ruta}" for ruta in limpiar_viejas(hogar)]
    for nombre, _, modo, ruta in destinos(hogar):
        if modo == "skill":
            if ruta.exists():
                shutil.rmtree(ruta.parent, ignore_errors=True)
                hecho.append(f"{nombre}: skill quitada")
            for companera in COMPANERAS:
                shutil.rmtree(ruta.parent.parent / companera, ignore_errors=True)
        elif ruta.exists():
            antes = ruta.read_text(encoding="utf-8")
            if INICIO in antes or any(inicio in antes for inicio, _ in VIEJAS_MARCAS):
                despues = quitar(antes)
                if despues:
                    ruta.write_text(despues, encoding="utf-8")
                else:
                    ruta.unlink()
                hecho.append(f"{nombre}: aviso quitado de {ruta}")
    for ruta in extra:
        ruta = Path(ruta).expanduser()
        if ruta.exists():
            ruta.write_text(quitar(ruta.read_text(encoding="utf-8")), encoding="utf-8")
            hecho.append(f"a mano: aviso quitado de {ruta}")
    return hecho


def main(argumentos=None):
    argumentos = list(sys.argv[1:] if argumentos is None else argumentos)
    quitando = "--desinstalar" in argumentos
    extra = [a for a in argumentos if not a.startswith("--")]
    hecho = (desinstalar if quitando else instalar)(extra=extra)
    for linea in hecho:
        print(linea)
    if not hecho:
        print("Ningún agente conocido en este usuario; nada que hacer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
