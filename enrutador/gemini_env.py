"""El `.env` del proyecto en el entorno de Gemini CLI (v1.3.0, cotejo-4gvdy5).

Lo usa `clientes.Cliente.terminal_libre` para el agente que lanza el board. Sin GTK ni red: solo
lee archivos y devuelve variables.
"""

import os
import re


# Gemini CLI carga un `.env` al arrancar (https://geminicli.com/docs/reference/configuration/,
# «Environment variables and `.env` files»): el primero que encuentra subiendo desde donde
# arranca —en cada carpeta, primero `.gemini/.env` (solo con confianza) y luego `.env`; al
# llegar a la raíz, los de la casa— y **solo añade las variables que no existan**. Con la
# confianza que le da Cotejo, un `.env` del worktree (commiteado, o escrito por el agente
# anterior de la tarea) le metía al proceso de Gemini, a su shell y a sus servidores MCP una
# `BASH_ENV` (cada `bash -c` corre ese archivo antes del comando), un `NODE_OPTIONS`, un
# `LD_PRELOAD`, un `GIT_CONFIG_*`…: código que corre sin que nadie lo pida y por debajo de la
# política de prohibidos y de las guardas del PATH (cotejo-4gvdy5). El `PATH` no, porque siempre
# existe. Probado con Gemini CLI 0.61 (`loadEnvironment`/`findEnvFile` de su bundle y
# `pruebas/test_env_del_proyecto.py`).
#
# Cotejo no le quita el `.env` —una `GEMINI_API_KEY`, un `DATABASE_URL` o un `VITE_…` siguen
# llegando—: le define antes, **vacías**, las de esta lista que ese `.env` traiga y la persona no
# tenga, y como ya existen Gemini no las pisa. Es una lista de nombres que hacen que un programa
# corra código, cambie qué programa corre o adónde va la red; para cambiarla, aquí.
VEDADAS = frozenset({
    "PATH", "PATHEXT", "COMSPEC", "HOME", "SHELL",
    # Los arranques de los shells y lo que ejecuta un shell al expandir o al pintar.
    "BASH_ENV", "ENV", "ZDOTDIR", "SHELLOPTS", "BASHOPTS", "PS4", "PROMPT_COMMAND", "IFS",
    "CDPATH", "GLOBIGNORE",
    # Programas que otros programas abren solos.
    "EDITOR", "VISUAL", "PAGER", "MANPAGER", "LESSOPEN", "LESSCLOSE", "BROWSER",
    "SSH_ASKPASS", "SUDO_ASKPASS", "GCONV_PATH",
    # Opciones que inyectan código en un runtime o en un build.
    "JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS", "JDK_JAVA_OPTIONS", "GOFLAGS", "RUSTC_WRAPPER",
    "RUSTC", "MAKEFLAGS",
    # La red y sus certificados: un proxy y una CA propia leen lo que Gemini manda.
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE",
})
VEDADAS_PREFIJOS = (
    "LD_", "DYLD_", "BASH_", "GIT_", "GH_", "XDG_", "NODE_", "NPM_CONFIG_", "YARN_", "BUN_",
    "DENO_", "PYTHON", "PERL", "RUBY", "GEM_", "BUNDLE_", "LUA_", "CARGO_",
    # Los de Cotejo y los de los otros agentes, y los de Gemini que no son la clave ni el modelo.
    "COTEJO_", "FOCO_", "GEMINI_CLI_", "OPENCODE_", "CODEX_", "CLAUDE_",
)
# Lo normal en un `.env` aunque empiece como uno vedado.
SIEMPRE = frozenset({"NODE_ENV"})
# El dotenv de Gemini: `export ` opcional, `CLAVE=valor` o `CLAVE: valor`. Se lee cada línea, no
# el valor entre comillas que cruza varias: sobran nombres, no falta ninguno. Es JavaScript: su
# `\s` cuenta la marca de orden de bytes y su `^` empieza también tras U+2028 y U+2029.
_CLAVE_DOTENV = re.compile(r"^[\s\ufeff]*(?:export\s+)?([A-Za-z0-9_.-]+)\s*[=:]", re.M)


def vedada(nombre):
    """¿Es una variable que un `.env` ajeno no le añade a Gemini (`VEDADAS`)?"""
    nombre = nombre.upper()
    if nombre in SIEMPRE:
        return False
    return nombre in VEDADAS or nombre.startswith(VEDADAS_PREFIJOS)


def _mismo_sitio(a, b):
    def normal(ruta):
        return os.path.normcase(os.path.normpath(os.path.abspath(ruta)))
    return normal(a) == normal(b)


def _que_carga(desde, casa, ignorar_local):
    """`(archivo, carpeta)`: el `.env` que Gemini CLI cargaría arrancando en `desde`, con
    confianza, como su `findEnvFile` (la doc dice que para en la raíz del proyecto; el código
    sube hasta la del disco), y la carpeta donde lo encontró (`None` para los de la casa del
    final). `ignorar_local` es su `advanced.ignoreLocalEnv`, que solo salta los `.env` (no los
    `.gemini/.env`) fuera de la casa. `(None, None)` si no hay ninguno."""
    carpeta = os.path.abspath(desde)
    while True:
        gemini = os.path.join(carpeta, ".gemini", ".env")
        if os.path.exists(gemini):
            return gemini, carpeta
        local = os.path.join(carpeta, ".env")
        if os.path.exists(local) and (not ignorar_local or _mismo_sitio(carpeta, casa)):
            return local, carpeta
        arriba = os.path.dirname(carpeta)
        if not arriba or arriba == carpeta:
            for archivo in (os.path.join(casa, ".gemini", ".env"), os.path.join(casa, ".env")):
                if os.path.exists(archivo):
                    return archivo, None
            return None, None
        carpeta = arriba


def ajenos(trabajo, entorno=None):
    """Los `.env` que Gemini CLI cargaría arrancando en `trabajo` y que no son de la persona (los
    de su casa: `~/.env` y `~/.gemini/.env`, o los de `GEMINI_CLI_HOME`). Se miran los dos
    caminos, con y sin `advanced.ignoreLocalEnv`, que el `.gemini/settings.json` del proyecto
    también puede poner."""
    entorno = os.environ if entorno is None else entorno
    casa = entorno.get("GEMINI_CLI_HOME") or os.path.expanduser("~")
    lista = []
    for ignorar in (False, True):
        archivo, carpeta = _que_carga(trabajo, casa, ignorar)
        if archivo and carpeta is not None and not _mismo_sitio(carpeta, casa) \
                and archivo not in lista:
            lista.append(archivo)
    return lista


def _claves_dotenv(archivo):
    """Los nombres que define un `.env` (de más, nunca de menos). Uno que no se lee no define
    nada: Gemini tampoco carga nada de él."""
    try:
        with open(archivo, encoding="utf-8", errors="replace") as f:
            texto = f.read()
    except OSError:
        return []
    return _CLAVE_DOTENV.findall(re.sub(r"\r\n?|[\u2028\u2029]", "\n", texto))


def sin_env_del_proyecto(trabajo, env, entorno=None):
    """`env` con las variables vedadas (`vedada`) que traiga un `.env` ajeno (`ajenos`)
    definidas vacías, si no las tiene ya la persona ni `env`: Gemini solo añade las que no
    existen, y así no las pone él. Sin `.env` ajeno, `env` tal cual."""
    if not trabajo:
        return env
    entorno = os.environ if entorno is None else entorno

    def clave(nombre):
        return nombre.upper() if os.name == "nt" else nombre
    existen = {clave(n) for n in (*entorno, *env)}
    vacias = {nombre: "" for archivo in ajenos(trabajo, entorno)
              for nombre in _claves_dotenv(archivo)
              if clave(nombre) not in existen and vedada(nombre)}
    return {**env, **vacias} if vacias else env
