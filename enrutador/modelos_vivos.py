"""Qué agentes están listos (instalados **y con sesión**) y qué modelos ofrece hoy cada uno
(v1.3.0, cotejo-qixs4j).

Dos preguntas, las dos sin gastar un token ni abrir un navegador:

- **¿Tiene sesión?** (`sesion`, `listos`). Se mira solo lo que cada agente deja en disco al
  iniciar sesión, o la variable de entorno con su clave. Si la sesión vive en el llavero del
  sistema (Codex y Claude Code pueden guardarla ahí), se le pregunta al CLI su estado
  (`ESTADO_CLI`), con tope y caché corta, y nunca al pintar el board (cotejo-2j6un7). Claude Code,
  `~/.claude/.credentials.json` (o `oauthAccount` en `~/.claude.json`, que es lo que queda en
  macOS, donde la credencial va al llavero); Codex, `~/.codex/auth.json` (o `CODEX_HOME`);
  OpenCode, alguna credencial en su `auth.json` (`opencode auth list` lee ese mismo archivo);
  Gemini CLI, `~/.gemini/oauth_creds.json`. Antigravity CLI guarda su sesión en el llavero y no
  documenta cómo preguntarle si la tiene (`SESION_INVISIBLE`): solo se ve la que va por entorno
  (`AGY_ADC_AUTH=true`, o `GEMINI_API_KEY` con `modelProvider: "gemini"` en su settings.json,
  https://antigravity.google/docs/install), y si no, instalado cuenta como listo y un `agy -p`
  sin sesión sale con «authentication required» (…/docs/cli/headless). Instalado es lo de
  siempre, `clientes.instalados()`.
- **¿Qué modelos tiene?** (`listar`). Se le pregunta al CLI solo cuando sabe listarlos sin
  hablar con ningún modelo: `opencode models` (una línea `proveedor/modelo` por modelo) y
  `codex debug models` (el catálogo en JSON; cuentan los de `visibility: list`), que es el mismo
  JSON que Codex ya guardó en `~/.codex/models_cache.json` (o `$CODEX_HOME`), y `agy models`
  (una línea `slug  Nombre` por modelo, https://antigravity.google/docs/cli/headless). Con Codex
  se lee primero ese archivo —no hay que lanzar nada— y solo si no está se le pregunta al CLI.
  Claude Code y Gemini CLI no listan: aceptan alias que sobreviven a cada modelo nuevo
  (`claude --model opus`; `gemini -m pro|flash|flash-lite|auto`) y esos son su lista, `RESPALDO`.
  Lo que contesta el CLI se guarda en `<estado>/modelos/<cliente>.json` (`CADUCA` segundos) y la
  llamada tiene tope (`TOPE`); si el CLI falla, tarda o no está, se usa lo último guardado y, si
  nada, el respaldo, que es corto y conservador a propósito: nunca un id inventado.

El board pinta con `en_cache` (nunca lanza nada al pintar) y refresca con `listar` en un hilo
desde «Añadir modelo». Las pruebas ponen CLIs falsos en un PATH temporal y `HOME` en otra parte.
"""

import json
import os
import re
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from tareas import rutas

from . import clientes

TOPE = 15                  # segundos como mucho por CLI
CADUCA = 6 * 3600          # lo guardado vale seis horas

# Lo que se ofrece cuando el CLI no lista: alias que entiende el propio agente.
RESPALDO = {
    "claude": ("opus", "sonnet", "haiku"),
    "gemini": ("pro", "flash", "flash-lite", "auto"),
    "codex": (),
    "opencode": (),
    "antigravity": (),
}

# Cómo se le pregunta a cada CLI (sin modelo, sin prompt, sin red de pago).
PREGUNTA = {
    "opencode": ("models",),
    "codex": ("debug", "models"),
    "antigravity": ("models",),
}

# Los que guardan la sesión donde Cotejo no la ve ni sabe preguntarla: instalados, cuentan como
# listos (`listos`) y la pantalla del equipo dice que no puede saberlo (`tareas/equipo.py`).
SESION_INVISIBLE = ("antigravity",)


# --- sesión -------------------------------------------------------------------------------------

def _casa():
    return Path(os.environ.get("HOME") or Path.home())


def _con_credenciales(ruta):
    """El `auth.json` de OpenCode tiene al menos una credencial."""
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(datos, dict) and bool(datos)


def _claude_con_cuenta(ruta):
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(datos, dict) and bool(datos.get("oauthAccount"))


# La sesión guardada en el llavero del sistema no deja archivo (cotejo-2j6un7): ahí se le
# pregunta al propio CLI, que contesta al instante y sin gastar tokens. `codex login status`
# sale con 0 y dice «Logged in»; `claude auth status` imprime JSON con `"loggedIn": true`
# (https://code.claude.com/docs/en/cli-reference). Solo se guarda el sí/no: la salida de Claude
# lleva el correo de la cuenta y no se registra en ninguna parte.
ESTADO_CLI = {
    "codex": ("login", "status"),
    "claude": ("auth", "status"),
}
TOPE_ESTADO = 5            # segundos como mucho por pregunta
CADUCA_ESTADO = 30         # lo que vale el sí/no del CLI
_estado_cli = {}           # nombre → (cuándo, sí/no)


def _leer_estado(nombre, salida, codigo):
    if nombre == "codex":
        return codigo == 0 and "logged in" in salida.lower() and \
            "not logged in" not in salida.lower()
    if nombre == "claude":
        try:
            datos = json.loads(salida)
        except ValueError:
            return False
        return isinstance(datos, dict) and datos.get("loggedIn") is True
    return False


def estado_del_cli(nombre, tope=TOPE_ESTADO):
    """Le pregunta al CLI si tiene sesión (sí/no) y lo guarda `CADUCA_ESTADO` segundos. Sin
    CLI, si falla o si tarda más de `tope`: no."""
    if os.environ.get("COTEJO_NO_PREGUNTAR_CLI"):
        # Las pruebas lo ponen: ninguna llama al claude/codex de verdad de quien las corre.
        return False
    argumentos = ESTADO_CLI.get(nombre)
    ejecutable = shutil.which(clientes.de(nombre).ejecutable) if argumentos else None
    if ejecutable is None:
        return False
    si = False
    try:
        # Sesión propia: si tarda, se mata con todo lo que haya lanzado (si no, un hijo que se
        # quede con la salida abierta haría esperar más que el tope).
        proceso = subprocess.Popen([ejecutable, *argumentos], stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                                   text=True, env={**os.environ, "NO_COLOR": "1"},
                                   start_new_session=True)
    except OSError:
        proceso = None
    if proceso is not None:
        try:
            salida, _ = proceso.communicate(timeout=tope)
            si = _leer_estado(nombre, salida or "", proceso.returncode)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proceso.pid, signal.SIGKILL)
            except OSError:
                proceso.kill()
            proceso.communicate()
    _estado_cli[nombre] = (time.monotonic(), si)
    return si


def _estado_guardado(nombre):
    guardado = _estado_cli.get(nombre)
    if guardado and time.monotonic() - guardado[0] < CADUCA_ESTADO:
        return guardado[1]
    return None


def olvidar_estados():
    """Vacía lo que contestaron los CLIs (las pruebas, y quien quiera preguntar de nuevo ya)."""
    _estado_cli.clear()


def sesion(nombre, entorno=None, preguntar_cli=False):
    """¿Inició sesión este agente? Mira archivos y variables. Si no hay nada y la sesión puede
    vivir en el llavero (`ESTADO_CLI`), usa lo que contestó el CLI hace poco y, solo con
    `preguntar_cli`, le pregunta (con tope). Al pintar el board nunca se pregunta."""
    entorno = os.environ if entorno is None else entorno
    if _en_disco(nombre, entorno):
        return True
    if nombre not in ESTADO_CLI:
        return False
    guardado = _estado_guardado(nombre)
    if guardado is not None:
        return guardado
    return estado_del_cli(nombre) if preguntar_cli else False


def _en_disco(nombre, entorno):
    casa = _casa()
    if nombre == "claude":
        return bool(entorno.get("ANTHROPIC_API_KEY") or entorno.get("CLAUDE_CODE_OAUTH_TOKEN")
                    or (casa / ".claude" / ".credentials.json").is_file()
                    or _claude_con_cuenta(casa / ".claude.json"))
    if nombre == "codex":
        carpeta = Path(entorno.get("CODEX_HOME") or casa / ".codex")
        return bool(entorno.get("OPENAI_API_KEY") or (carpeta / "auth.json").is_file())
    if nombre == "opencode":
        datos = Path(entorno["XDG_DATA_HOME"]) if entorno.get("XDG_DATA_HOME") else \
            rutas.datos_xdg()
        return _con_credenciales(datos / "opencode" / "auth.json")
    if nombre == "gemini":
        return bool(entorno.get("GEMINI_API_KEY") or entorno.get("GOOGLE_API_KEY")
                    or entorno.get("GOOGLE_GENAI_USE_VERTEXAI")
                    or (casa / ".gemini" / "oauth_creds.json").is_file())
    if nombre == "antigravity":
        # Solo lo que documenta https://antigravity.google/docs/install: la clave de Gemini
        # vale únicamente con `modelProvider: "gemini"` en su settings.json.
        return bool(str(entorno.get("AGY_ADC_AUTH", "")).lower() == "true"
                    or (entorno.get("GEMINI_API_KEY") and _proveedor_agy(casa) == "gemini"))
    return False


def _proveedor_agy(casa):
    try:
        datos = json.loads((casa / ".gemini" / "antigravity-cli" / "settings.json")
                           .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return datos.get("modelProvider", "") if isinstance(datos, dict) else ""


def sesion_visible(nombre):
    """¿Puede Cotejo saber si este agente tiene sesión? (No, con `SESION_INVISIBLE`.)"""
    return nombre not in SESION_INVISIBLE


def listos(preguntar_cli=False):
    """Los agentes instalados y con sesión, en el orden de `clientes.CLIENTES`. Los de sesión
    invisible cuentan con estar instalados."""
    return [nombre for nombre in clientes.instalados()
            if not sesion_visible(nombre) or sesion(nombre, preguntar_cli=preguntar_cli)]


# --- modelos ------------------------------------------------------------------------------------

def _archivo(nombre):
    return rutas.estado() / "modelos" / f"{nombre}.json"


def _leer_guardado(nombre):
    try:
        datos = json.loads(_archivo(nombre).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(datos, dict) or not isinstance(datos.get("modelos"), list):
        return None
    return datos


def _guardar(nombre, modelos):
    archivo = _archivo(nombre)
    try:
        archivo.parent.mkdir(parents=True, exist_ok=True)
        temporal = archivo.with_suffix(".tmp")
        temporal.write_text(json.dumps({"en": time.time(), "modelos": modelos},
                                       ensure_ascii=False), encoding="utf-8")
        temporal.replace(archivo)
    except OSError:
        pass   # sin caché se vuelve a preguntar la próxima vez; no es un error


def leer_opencode(salida):
    """`opencode models`: una línea `proveedor/modelo` por modelo; lo demás se ignora."""
    vistos = []
    for linea in salida.splitlines():
        linea = linea.strip()
        if linea and "/" in linea and " " not in linea and linea not in vistos:
            vistos.append(linea)
    return vistos


def leer_codex(salida):
    """`codex debug models`: los de `visibility: list`, por su `priority`.

    `None` si la salida no se entiende: no es lo mismo «no tiene ningún modelo» que «no pude
    preguntar», y solo lo primero debe dejar al agente fuera del maestro."""
    try:
        datos = json.loads(salida)
    except ValueError:
        return None
    lista = datos.get("models") if isinstance(datos, dict) else datos
    if not isinstance(lista, list):
        return None
    visibles = [m for m in lista if isinstance(m, dict) and m.get("slug")
                and m.get("visibility", "list") == "list"]
    visibles.sort(key=lambda m: m.get("priority") if isinstance(m.get("priority"), int) else 999)
    return [m["slug"] for m in visibles]


def leer_cache_codex(entorno=None):
    """Los modelos que Codex ya se guardó en `~/.codex/models_cache.json` (mismo JSON que
    `codex debug models`): ahorra lanzar el CLI y funciona sin red. Vacío si no está o está roto."""
    entorno = os.environ if entorno is None else entorno
    carpeta = Path(entorno.get("CODEX_HOME") or _casa() / ".codex")
    try:
        return leer_codex((carpeta / "models_cache.json").read_text(encoding="utf-8"))
    except OSError:
        return []


def leer_agy(salida):
    """`agy models`: una línea por modelo, el slug y su nombre (`gemini-3.8-flash-medium
    Gemini 3.8 Flash (Medium)`); cuenta la primera palabra si parece un slug."""
    vistos = []
    for linea in salida.splitlines():
        partes = linea.split()
        slug = partes[0] if partes else ""
        if SLUG.fullmatch(slug) and slug not in vistos:
            vistos.append(slug)
    return vistos


SLUG = re.compile(r"[a-z0-9][a-z0-9._-]*[a-z0-9]")

LECTORES = {"opencode": leer_opencode, "codex": leer_codex, "antigravity": leer_agy}


def preguntar(nombre, tope=TOPE):
    """Le pide la lista al CLI. None si no sabe listar, no está, falla o tarda más de `tope`.

    Con Codex se lee antes su `models_cache.json`: es el mismo catálogo que contesta
    `codex debug models`, sin lanzar ni gastar. El CLI es el respaldo de ese archivo.
    """
    if nombre not in PREGUNTA:
        return None
    if nombre == "codex":
        guardados = leer_cache_codex()
        if guardados:
            return guardados
    ejecutable = shutil.which(clientes.de(nombre).ejecutable)
    if ejecutable is None:
        return None
    try:
        hecho = subprocess.run([ejecutable, *PREGUNTA[nombre]], capture_output=True, text=True,
                               timeout=tope, stdin=subprocess.DEVNULL,
                               env={**os.environ, "NO_COLOR": "1"})
    except (OSError, subprocess.SubprocessError):
        return None
    if hecho.returncode != 0:
        return None
    return LECTORES[nombre](hecho.stdout)


def en_cache(nombre):
    """Lo que hay sin preguntar a nadie: lo último guardado o, si nada, el respaldo."""
    guardado = _leer_guardado(nombre)
    if guardado and guardado["modelos"]:
        return list(guardado["modelos"])
    return list(RESPALDO.get(nombre, ()))


def _modelos(nombre, preguntar_cli=False, refrescar=False, tope=TOPE):
    """`(modelos, conocido)`: lo que ofrece este agente y si Cotejo lo sabe de verdad.

    «No lo sé» (el CLI falló, tardó o contestó algo que no se entiende) no es «no tiene
    ninguno»: solo lo segundo impide ofrecerlo, porque un fallo pasajero no debe dejar sin
    maestro a quien sí puede trabajar (`estado`)."""
    guardado = _leer_guardado(nombre)
    fresco = bool(guardado and guardado["modelos"]
                  and time.time() - float(guardado.get("en") or 0) < CADUCA)
    if fresco and not refrescar:
        return list(guardado["modelos"]), True
    if not preguntar_cli:
        return en_cache(nombre), fresco
    if nombre not in PREGUNTA:
        return list(RESPALDO.get(nombre, ())), True
    vivos = preguntar(nombre, tope)
    if vivos is not None:
        if vivos:
            _guardar(nombre, vivos)
        return list(vivos), True
    return en_cache(nombre), fresco


def listar(nombre, refrescar=False, tope=TOPE):
    """Los modelos de este agente: lo guardado si es reciente, si no se le pregunta al CLI (y
    se guarda), y si no contesta, `en_cache`. `refrescar` salta lo guardado."""
    return _modelos(nombre, preguntar_cli=True, refrescar=refrescar, tope=tope)[0]


@dataclass(frozen=True)
class EstadoAgente:
    """Una sola respuesta para Inicio/Ajustes y para el maestro."""

    cliente: str
    titulo: str
    instalado: bool
    sesion: bool
    sesion_visible: bool
    modelos: tuple
    modelos_conocidos: bool = False

    @property
    def listo(self):
        """Instalado, con sesión (o sin forma de verla) y con modelos cuando se sabe que no
        tiene ninguno. Un «no pude preguntar» no lo deja fuera."""
        con_sesion = self.sesion or not self.sesion_visible
        tiene_modelos = bool(self.modelos) or not self.modelos_conocidos
        return self.instalado and con_sesion and tiene_modelos

    @property
    def paso(self):
        """Qué tiene que hacer la persona para que el agente llegue a estar listo."""
        if not self.instalado:
            return f"Instala {self.titulo} desde Ajustes y pulsa «Revisar otra vez»"
        if self.sesion_visible and not self.sesion:
            return (f"Abre {self.titulo}, inicia sesión con tu cuenta y pulsa "
                    "«Revisar otra vez»")
        if not self.modelos:
            return (f"Abre {self.titulo}, configura un proveedor y un modelo, y pulsa "
                    "«Revisar otra vez»")
        return ""

    @property
    def problema(self):
        if self.listo:
            return ""
        if not self.instalado:
            falta = "no está instalado"
        elif self.sesion_visible and not self.sesion:
            falta = "está instalado, pero falta iniciar sesión"
        else:
            falta = "tiene sesión, pero no encontré ningún modelo disponible"
        return f"{self.titulo} {falta}. {self.paso}."


def estado(nombre, preguntar_cli=False, refrescar=False):
    """Estado utilizable de un agente; nunca ofrece al maestro algo que no puede lanzar."""
    cliente = clientes.de(nombre)
    instalado = nombre in clientes.instalados()
    visible = sesion_visible(nombre)
    con_sesion = instalado and sesion(nombre, preguntar_cli=preguntar_cli)
    puede_mirar_modelos = instalado and (con_sesion or not visible)
    modelos, conocidos = (_modelos(nombre, preguntar_cli=preguntar_cli, refrescar=refrescar)
                          if puede_mirar_modelos else ([], False))
    return EstadoAgente(nombre, cliente.titulo or nombre, instalado, con_sesion, visible,
                        tuple(modelos), bool(conocidos))


def estados(preguntar_cli=False, refrescar=False):
    """Estado de todos los agentes conocidos, en el orden estable de la interfaz."""
    return [estado(nombre, preguntar_cli=preguntar_cli, refrescar=refrescar)
            for nombre in clientes.CLIENTES]


def utilizables(preguntar_cli=False, refrescar=False):
    """Los que Inicio/Ajustes y el maestro consideran listos, con la misma comprobación."""
    return [actual.cliente for actual in estados(preguntar_cli, refrescar) if actual.listo]


def aviso_sin_listos(preguntar_cli=False):
    """Por qué no hay maestro, priorizando lo que ya está instalado sobre instalar otro."""
    vistos = estados(preguntar_cli=preguntar_cli)
    pendiente = next((e for e in vistos if e.instalado and not e.listo), None)
    if pendiente:
        return pendiente.problema
    return clientes.SIN_AGENTE_TEXTO


def resumen(refrescar=False, preguntar_cli=True):
    """Para la CLI (`cotejo modelos vivos`): por cada agente conocido, si está instalado, si
    tiene sesión y sus modelos (en vivo o, con `preguntar_cli=False`, lo guardado)."""
    salida = []
    for actual in estados(preguntar_cli=preguntar_cli, refrescar=refrescar):
        salida.append({"cliente": actual.cliente, "titulo": actual.titulo,
                       "instalado": actual.instalado, "sesion": actual.sesion,
                       "sesion_visible": actual.sesion_visible, "listo": actual.listo,
                       "problema": actual.problema,
                       "lista_el_cli": actual.cliente in PREGUNTA,
                       "modelos_conocidos": actual.modelos_conocidos,
                       "modelos": list(actual.modelos)})
    return salida


# --- «Añadir modelo» (el diálogo del board) ----------------------------------------------------

NIVELES_TEXTO = (("n1", "n1 · lo mecánico y acotado"), ("n2", "n2 · el trabajo normal"),
                 ("n3", "n3 · lo difícil"))


def nueva_clave(modelo_id, existentes=()):
    """Una clave para `#agente/<clave>` a partir del id (`opencode-go/kimi-k2.7-code` →
    `kimi-k2.7-code`): solo letras, números, punto, guion y guion bajo; sin pisar una clave
    reservada ni una de `existentes` (se le añade `-2`, `-3`…)."""
    from . import config as cfg, niveles
    base = (modelo_id or "").strip().rstrip("/").rsplit("/", 1)[-1].lower()
    base = "".join(c if c.isalnum() or c in "._-" else "-" for c in base).strip("-.") or "modelo"
    ocupadas = (set(cfg.RESERVADOS) | {n.clave for n in niveles.DE_FABRICA}
                | {str(c).lower() for c in existentes})
    clave, n = base, 2
    while clave in ocupadas:
        clave, n = f"{base}-{n}", n + 1
    return clave


def definicion(cliente, modelo_id, nombre="", nivel="n2", registrados=()):
    """Lo que el diálogo registra con `config.registrar_modelo`, lo mismo que guarda
    `cotejo modelos agregar`. Si ese cliente ya tiene registrado ese mismo id, se actualiza
    con su clave; si no, clave nueva (`nueva_clave`). Levanta ValueError con lo que falta."""
    cliente = (cliente or "").strip().lower()
    modelo_id = (modelo_id or "").strip()
    if not cliente:
        raise ValueError("Elige el agente.")
    if not modelo_id or any(c in modelo_id for c in "\r\n "):
        raise ValueError("Escribe o elige el modelo (sin espacios).")
    if nivel not in {n for n, _ in NIVELES_TEXTO}:
        raise ValueError("El nivel es n1, n2 o n3.")
    mismo = [m for m in registrados or () if m.get("cliente") == cliente
             and m.get("modelo_id") == modelo_id]
    clave = (mismo[0]["clave"] if mismo else
             nueva_clave(modelo_id, [m.get("clave", "") for m in registrados or ()]))
    return {"clave": clave, "nombre": (nombre or "").strip() or modelo_id,
            "modelo_id": modelo_id, "cliente": cliente, "nivel": nivel,
            "entrada_mtok": 0.0, "salida_mtok": 0.0}


def agregar(cliente, modelo_id, nombre="", nivel="n2", ruta=None):
    """Registra el modelo como `cotejo modelos agregar` (`config.registrar_modelo`). Devuelve
    `(guardado, reemplazado)`. Levanta ValueError o `config.ConfigInvalida`."""
    from . import config as cfg
    registrados = (cfg.cargar(ruta) or {}).get("modelos") or []
    return cfg.registrar_modelo(definicion(cliente, modelo_id, nombre, nivel, registrados), ruta)
