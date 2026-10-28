"""El archivo de config de Cotejo: dónde está, qué dice de cada fuente y cómo se escribe.

Un solo archivo para todo —qué fuente se usa, los parámetros de cada una y los ajustes del
enrutador—, porque dos archivos para un solo comando se descubren el día que uno de los dos
está desactualizado. Vive en `~/.config/cotejo/config.json` en Linux; en macOS y Windows, en
la carpeta de config de cada sistema (`rutas.config_base()`).

Antes vivía en `~/.config/tareas-obsidian/config.json`, con los parámetros de Obsidian sueltos
en la raíz. Las dos cosas se siguen leyendo: la ruta vieja mientras no exista la nueva, y las
claves sueltas como parámetros de `obsidian`. `config init` migra, y al migrar renombra el viejo
a `config.json.migrado` en vez de borrarlo: lo que no puede pasar es que haya dos archivos
vivos y cada skill escriba en uno.

La forma nueva:

    {
      "fuente": "notion",
      "fuentes": {
        "obsidian": {"vault": "/ruta", "carpeta_proyectos": "01-Proyectos"},
        "notion": {"tipo": "externa", "comando": "cotejo-notion",
                   "token_env": "NOTION_TOKEN", "database_id": "..."}
      },
      "enrutador": {...}
    }

Los tokens no se guardan aquí: se guarda el **nombre** de la variable de entorno que los tiene
(`token_env`). `validar` se queja de cualquier clave que parezca un secreto en claro.

Ninguna ruta se calcula al importar: `ruta()` resuelve al llamarla, igual que el enrutador.

**El agente de una tarea no escribe la config** (v1.3.0, cotejo-dgb7l2). Ahí viven
`lanzar.sandbox` y `lanzar.argumentos_extra`: el agente que pudiera cambiarlos le quitaría el
sandbox y los prohibidos a los lanzamientos siguientes. El armado del agente lleva
`COTEJO_CONFIG_VEDADA=1` en su entorno y entonces `guardar` se niega (`ConfigVedada`) antes de
tocar nada; debajo, su sandbox no le deja escribir los `archivos()` ni su carpeta.
"""

import json
import os
from pathlib import Path

from . import rutas

# Lo que va en la raíz del archivo y no es un parámetro de ninguna fuente.
# `tema` va aquí aunque sea de la ventana: sin ella, el formato viejo la leería como un
# parámetro más de Obsidian. `limpiar` (v1.2.2) por lo mismo.
PROPIAS = ("fuente", "fuentes", "enrutador", "tema", "limpiar", "dot")
# La fuente a la que pertenecen las claves sueltas de la raíz, que es como era el archivo viejo.
LEGADO_DE = "obsidian"
DEFECTO = "obsidian"
# La fuente de una instalación sin nada configurado (v1.2.4): no hay vault que leer.
DEFECTO_NUEVO = "repo"
# Cuántas finalizadas puede acumular un proyecto antes de que `entregar` avise de que convendría
# `limpiar` (`{"limpiar": {"umbral": 50}}`). 0 apaga el aviso.
UMBRAL_LIMPIAR = 50


# La marca que lleva en su entorno el agente de una tarea (`enrutador/armado.py`).
VEDADA = "COTEJO_CONFIG_VEDADA"


class ConfigRota(Exception):
    """El archivo existe y no se puede usar. Escribir encima perdería lo que el usuario puso."""


class ConfigVedada(Exception):
    """La pide escribir el agente de una tarea. Lleva lo mismo que un `ErrorCLI` (`cli.main` la
    imprime igual) sin que este módulo tenga que importar la CLI."""

    def __init__(self):
        self.mensaje = ("La config de Cotejo no se cambia desde una tarea: la escribe solo una "
                        "persona.")
        self.salida = ("Sigue con la tarea sin cambiarla. Si de verdad hace falta un cambio de "
                       "config, dilo en la entrega o bloquea la tarea con el motivo.")
        self.reintentable = False
        self.codigo = 3
        self.avisos = []
        super().__init__(self.mensaje)


def vedada(entorno=None):
    """¿Corre esto dentro del agente de una tarea, que no puede escribir la config?"""
    return bool((os.environ if entorno is None else entorno).get(VEDADA))


def sin_vedar():
    """Levanta `ConfigVedada` si quien llama es el agente de una tarea. Va antes de escribir."""
    if vedada():
        raise ConfigVedada()


def _base():
    return rutas.config_base()


def carpeta():
    """`~/.config/cotejo/`, o `~/.config/foco/` si es la única que hay.

    El producto se llamó Foco y su carpeta era esa. No se copia a la nueva por su cuenta: dos
    carpetas vivas son dos configs, y cada skill acabaría escribiendo en una. `install.sh` la
    mueve y deja `foco` como enlace a `cotejo`.
    """
    base = _base()
    if not (base / "cotejo").exists() and (base / "foco").is_dir():
        return base / "foco"
    return base / "cotejo"


def nueva():
    return carpeta() / "config.json"


def legado():
    return _base() / "tareas-obsidian" / "config.json"


def archivos():
    """Todos los archivos por los que Cotejo podría leer su config: el que manda hoy y los que
    mandarían si ese faltara (el nuevo, el viejo, el de `~/.config/foco`). Sin repetir."""
    candidatos = [ruta(), nueva(), legado(), _base() / "foco" / "config.json"]
    return list(dict.fromkeys(os.path.abspath(Path(c).expanduser()) for c in candidatos))


def ruta():
    """El archivo que manda. `COTEJO_CONFIG` gana a todo; luego el nuevo; luego el viejo.

    Si no existe ninguno, el nuevo: es donde escribirá `config init` o `fuentes usar`.
    """
    desde_entorno = os.environ.get("COTEJO_CONFIG")
    if desde_entorno:
        return Path(desde_entorno).expanduser()
    if nueva().exists() or not legado().exists():
        return nueva()
    return legado()


def leer(donde=None):
    """El contenido del archivo, `{}` si no existe. Levanta `ConfigRota` si no se puede leer."""
    donde = Path(donde) if donde else ruta()
    if not donde.exists():
        return {}
    try:
        datos = json.loads(donde.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ConfigRota(f"No pude leer {donde}: {error}") from error
    if not isinstance(datos, dict):
        raise ConfigRota(f"{donde} no tiene un objeto JSON dentro")
    return datos


def cargar():
    """La config para usarla, sin quejarse: un archivo roto se lee como vacío.

    Es lo que quiere la barra y el board, que no pueden caerse por una coma. Quien necesite
    saber que está roto lo pregunta con `validar` o `cotejo doctor`.
    """
    try:
        return leer()
    except ConfigRota:
        return {}


def fuente_activa(datos):
    """Qué fuente manda: `COTEJO_FUENTE`, luego «fuente» de la config, y si no hay ninguna, el repo.

    Sin config, o con una que no nombra fuente, la entrada es el repo (v1.2.4): una instalación
    nueva no tiene vault. Quien ya usaba Obsidian sin escribir «fuente» (claves sueltas del
    formato viejo o `fuentes.obsidian`, o `COTEJO_VAULT`) sigue en Obsidian: no se le cambia la fuente al actualizar.
    """
    return os.environ.get("COTEJO_FUENTE") or fuente_de_config(datos)


def fuente_de_config(datos):
    """Lo mismo sin mirar el entorno: la que dice el archivo, o la de defecto si no dice."""
    if datos.get("fuente"):
        return datos["fuente"]
    fuentes = datos.get("fuentes")
    if (os.environ.get("COTEJO_VAULT")
            or any(k not in PROPIAS + ("contexto",) for k in datos)
            or (isinstance(fuentes, dict) and LEGADO_DE in fuentes)):
        return LEGADO_DE
    return DEFECTO_NUEVO


def parametros(datos, nombre):
    """Lo que la config dice de una fuente: su entrada en `fuentes`, y por debajo, para
    `obsidian`, las claves sueltas del formato viejo."""
    base = {}
    if nombre == LEGADO_DE:
        base = {k: v for k, v in datos.items() if k not in PROPIAS}
    propia = (datos.get("fuentes") or {}).get(nombre)
    return {**base, **(propia if isinstance(propia, dict) else {})}


def registradas(datos):
    """Las fuentes que la config nombra en `fuentes`, con sus parámetros."""
    fuentes = datos.get("fuentes") or {}
    return {nombre: parametros(datos, nombre) for nombre, valor in fuentes.items()
            if isinstance(valor, dict)}


def guardar(datos, donde=None):
    """Escribe el archivo entero de forma atómica: o queda el nuevo, o sigue el de antes."""
    import tempfile  # aquí y no arriba: `--estado` importa este módulo y nunca escribe

    sin_vedar()
    donde = Path(donde) if donde else ruta()
    donde.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(datos, indent=2, ensure_ascii=False) + "\n"
    descriptor, temporal = tempfile.mkstemp(dir=donde.parent, prefix=".config-", suffix=".json")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
            archivo.write(texto)
        os.replace(temporal, donde)
    except BaseException:
        Path(temporal).unlink(missing_ok=True)
        raise
    return donde


def migrar(viejo):
    """El formato viejo al nuevo: las claves sueltas pasan a `fuentes.obsidian`."""
    sueltas = {k: v for k, v in viejo.items() if k not in PROPIAS}
    nuevo = {"fuente": viejo.get("fuente") or DEFECTO}
    fuentes = dict(viejo.get("fuentes") or {})
    if sueltas:
        fuentes[LEGADO_DE] = {**sueltas, **(fuentes.get(LEGADO_DE) or {})}
    if fuentes:
        nuevo["fuentes"] = fuentes
    for clave in ("enrutador", "tema", "limpiar", "contexto", "dot"):
        if clave in viejo:
            nuevo[clave] = viejo[clave]
    return nuevo


def umbral_limpiar(datos=None):
    """El umbral de finalizadas para el aviso de `entregar`, o el de defecto si no se entiende.

    Un valor roto no apaga el aviso ni tumba `entregar`: se usa el de defecto, y `config
    validar` dice qué tiene mal.
    """
    datos = cargar() if datos is None else datos
    seccion = datos.get("limpiar")
    umbral = seccion.get("umbral") if isinstance(seccion, dict) else None
    if isinstance(umbral, int) and not isinstance(umbral, bool) and umbral >= 0:
        return umbral
    return UMBRAL_LIMPIAR


def dot_activo(datos=None):
    """Si el board lleva el dot (`"dot": true`). Apagado por defecto: sin la clave, o con un
    valor que no es booleano, no se crea (`config validar` avisa del segundo caso)."""
    datos = cargar() if datos is None else datos
    return datos.get("dot") is True


def _validar_limpiar(datos, errores, avisos):
    if "limpiar" not in datos:
        return
    seccion = datos["limpiar"]
    if not isinstance(seccion, dict):
        errores.append("«limpiar» tiene que ser un objeto: {\"umbral\": 50}")
        return
    if "umbral" in seccion:
        umbral = seccion["umbral"]
        if isinstance(umbral, bool) or not isinstance(umbral, int) or umbral < 0:
            errores.append(f"«limpiar.umbral» es {umbral!r}: tiene que ser un entero ≥ 0 "
                           f"(0 apaga el aviso de `entregar`). Mientras, se usa "
                           f"{UMBRAL_LIMPIAR}.")
    sobran = sorted(set(seccion) - {"umbral"})
    if sobran:
        avisos.append(f"«limpiar» no conoce {', '.join(sobran)}: se ignora. Solo tiene "
                      f"«umbral».")


def _validar_contexto(datos, errores, avisos):
    if "contexto" not in datos:
        return
    seccion = datos["contexto"]
    if not isinstance(seccion, dict):
        errores.append("«contexto» tiene que ser un objeto: {\"dias_viejo\": 14}")
        return
    if "dias_viejo" in seccion:
        dias = seccion["dias_viejo"]
        if isinstance(dias, bool) or not isinstance(dias, int) or dias < 0:
            errores.append(f"«contexto.dias_viejo» es {dias!r}: tiene que ser un entero ≥ 0. "
                           f"Mientras, se usa 14.")
    sobran = sorted(set(seccion) - {"dias_viejo"})
    if sobran:
        avisos.append(f"«contexto» no conoce {', '.join(sobran)}: se ignora. Solo tiene "
                      f"«dias_viejo».")


def parece_secreto(clave):
    """Una clave que por el nombre guarda un secreto en claro. `token_env` y `token_archivo`
    no: son el nombre de una variable y una ruta, no el secreto."""
    clave = clave.lower()
    return (any(p in clave for p in ("token", "secret", "password", "clave_api", "api_key"))
            and not clave.endswith(("_env", "_archivo")))


def _secretos_en(valor, ruta, errores):
    """Busca claves que parecen secretos en todo `valor`, recorriendo dicts y listas.

    No se detiene en `fuentes.<nombre>`: un token en la raíz de la config (`api_key` suelta) o
    dentro de `enrutador` (una regla, un modelo personalizado) pasaba antes sin que nadie lo
    viera. Nunca mete el valor en el mensaje de error, solo dónde está —`ruta` es de claves, no
    de contenido—, así que un secreto real no queda en claro en la salida de `validar`.
    """
    if isinstance(valor, dict):
        for clave, hijo in valor.items():
            sub = f"{ruta}.{clave}" if ruta else str(clave)
            if parece_secreto(str(clave)):
                errores.append(f"«{sub}» parece un secreto en claro. Guárdalo en una variable "
                               f"de entorno y pon aquí su nombre en «token_env».")
            else:
                _secretos_en(hijo, sub, errores)
    elif isinstance(valor, list):
        for indice, hijo in enumerate(valor):
            _secretos_en(hijo, f"{ruta}[{indice}]", errores)


def validar(conocidas):
    """Qué está mal en la config, sin tocar nada. `conocidas` son las fuentes de fábrica.

    Devuelve `(errores, avisos)`. Un error hace que algo no funcione; un aviso, que algo
    funciona distinto de lo que quien lo escribió seguramente cree.
    """
    errores, avisos = [], []
    donde = ruta()
    try:
        datos = leer(donde)
    except ConfigRota as error:
        return [str(error)], avisos
    if not donde.exists():
        avisos.append(f"No hay archivo de config ({donde}): se usan los valores por defecto. "
                      f"`config init` lo crea.")
    if not os.environ.get("COTEJO_CONFIG") and nueva().exists() and legado().exists():
        avisos.append(f"Hay dos archivos: se usa {nueva()} y se ignora {legado()}. Bórralo "
                      f"o renómbralo para que nadie lo edite creyendo que sirve.")
    fuentes = datos.get("fuentes", {})
    if not isinstance(fuentes, dict):
        errores.append("«fuentes» tiene que ser un objeto: {\"nombre\": {parámetros}}")
        fuentes = {}
    for nombre, valor in fuentes.items():
        if not isinstance(valor, dict):
            errores.append(f"La fuente «{nombre}» tiene que ser un objeto con sus parámetros")
            continue
        tipo = valor.get("tipo", "built-in" if nombre in conocidas else "externa")
        if tipo == "externa" and not valor.get("comando"):
            errores.append(f"La fuente externa «{nombre}» no dice qué «comando» lanzar")
        if tipo not in ("built-in", "externa"):
            errores.append(f"La fuente «{nombre}» tiene «tipo» {tipo!r}: vale built-in o externa")
        if tipo == "built-in" and nombre not in conocidas:
            errores.append(f"«{nombre}» dice ser built-in, pero las de fábrica son "
                           f"{', '.join(sorted(conocidas))}")
    # No solo `fuentes.<nombre>`: un token suelto en la raíz o dentro de `enrutador` tiene que
    # saltar igual.
    _secretos_en(datos, "", errores)
    activa = fuente_activa(datos)
    if activa not in conocidas and activa not in fuentes:
        errores.append(f"La fuente activa es «{activa}», y no es de fábrica ni está en "
                       f"«fuentes». `fuentes` lista las que hay.")
    enrutador = datos.get("enrutador")
    if enrutador is not None and not isinstance(enrutador, dict):
        errores.append("«enrutador» tiene que ser un objeto")
    if "dot" in datos and not isinstance(datos["dot"], bool):
        errores.append(f"«dot» es {datos['dot']!r}: tiene que ser true o false. Mientras, el "
                       f"dot queda apagado.")
    _validar_limpiar(datos, errores, avisos)
    _validar_contexto(datos, errores, avisos)
    if "tema" in datos:
        # Aviso y no error: con un tema que no sirve, el board se ve con el de defecto y todo
        # lo demás funciona. Aquí dentro el import, porque `temas` importa este módulo.
        from . import temas
        try:
            temas.cargar(temas.elegido(datos))
        except temas.TemaRoto as error:
            avisos.append(f"{error}: el board usa «{temas.DEFECTO}». `temas comprobar "
                          f"{temas.elegido(datos)}` dice qué tiene.")
    return errores, avisos
