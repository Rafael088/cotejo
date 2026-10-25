"""Los ajustes del enrutador, que son una clave más de la config de Cotejo.

Antes vivían en su propio archivo (`~/.config/focorouter/config.json`) porque el enrutador era
su propio programa. Al mudarse aquí dentro dejó de tener sentido: quien instala una cosa
instala las dos, y tener dos archivos de config para un solo comando es la clase de detalle
que se descubre el día que uno de los dos está desactualizado.

Todo lo que apunta fuera del proceso se puede mover sin tocar código:

    COTEJO_CONFIG    el archivo de config      (por defecto el de Cotejo, ~/.config/cotejo/)
    COTEJO_MOTOR     con qué se despacha       (por defecto el de la config: agente)

Ninguna ruta se calcula al importar este módulo: `ruta_config()` resuelve al llamarla. Un
`HOME` distinto o un binario congelado rompen cualquier constante de módulo, y ahí es donde va
Cotejo el día que se empaquete para otros dispositivos.
"""

import copy
import json
import os
import re
from pathlib import Path

from tareas import configuracion, rutas

ESQUEMA = 1

# La clave donde viven estos ajustes dentro del config de Cotejo. Lo de fuera de esta clave es
# de Cotejo (qué fuente, qué vault) y no se toca desde aquí.
CLAVE = "enrutador"

# Con qué se abre el maestro (`enrutador.maestro.terminal`) si la config no dice otra, según el
# sistema. `xdg-terminal-exec` pide al escritorio la terminal preferida del usuario por el portal
# XDG; no existe en Windows, que no tiene un equivalente estándar, pero sí tiene `start`: abre una
# consola nueva y visible sin que Cotejo tenga que adivinar qué terminal hay instalada. El `""`
# es el título vacío que `start` espera para no confundir el título con el programa a ejecutar.
TERMINAL_XDG = ["xdg-terminal-exec"]
TERMINAL_POR_SISTEMA = {
    "windows": ["cmd", "/c", "start", ""],
}


def _terminal_por_defecto():
    """La terminal del maestro para este sistema.

    Se calcula al llamar `cargar()`, nunca al importar: es lo que deja que una prueba finja otra
    plataforma (`mock.patch.object(rutas.sys, "platform", ...)`) y vea el defecto que le tocaría,
    sin depender de en qué máquina corren las pruebas.
    """
    return list(TERMINAL_POR_SISTEMA.get(rutas.sistema(), TERMINAL_XDG))


DEFECTOS = {
    # `agente` no lanza nada: devuelve el encargo para que lo haga el agente que preguntó. Es
    # el defecto porque es el caso normal; los que arrancan procesos se piden por su nombre.
    "motor": "agente",
    "motores": {
        "sesion": {"comando": ["claude"], "argumentos_extra": [], "timeout_seg": 120},
        # `aislar` y `memoria_max` son del scope de systemd en que corre cada headless
        # (`enrutador/aislamiento.py`): un `MemoryMax` por porcentaje no asume cuánta RAM tiene
        # la máquina de quien instale Cotejo, y `aislar: false` apaga el aislamiento sin tocar
        # nada más. Solo aplica en Linux con systemd de usuario; en otro lado se ignora solo.
        "headless": {"comando": ["claude"], "argumentos_extra": [], "timeout_seg": 1800,
                     "aislar": True, "memoria_max": "50%"},
    },
    # El agente que reparte las tareas asignadas de un proyecto (`cotejo maestro`, y el botón
    # del board). Se abre siempre en una terminal que se ve: `terminal` es con qué (sin entrada,
    # `_terminal_por_defecto()` según la plataforma; `cargar()` la rellena), y `modelos` el
    # modelo con que se abre cada cliente (sin entrada, el que ese cliente tenga por defecto).
    "maestro": {"terminal": None, "modelos": {"claude": "opus"}},
    # Preparar un proyecto nuevo en segundo plano (`enrutador/preparar.py`, v1.3.0). Corre con
    # los ajustes de `motores.headless` y además con estos argumentos por cliente: Claude sin
    # interfaz no puede pedir permiso, así que se le da solo el de correr `cotejo` (y lo mismo a
    # Gemini, que sin interfaz niega todo comando que pediría confirmación). Pasados
    # `minutos_sin_actividad` sin que nada se mueva en `.cotejo/` del proyecto, cuenta como
    # colgado y la pantalla ofrece reintentar o abrirlo en una terminal.
    "preparar": {"minutos_sin_actividad": 10,
                 "argumentos_extra": {"claude": ["--allowedTools", "Bash(cotejo:*)"],
                                      "gemini": ["--allowed-tools", "run_shell_command(cotejo)"]}},
    # Lanzar desde el board (`enrutador/despacho_board.py`, v1.3.0): pasar a mano una tarea de
    # Pendiente a Haciendo la despacha sin interfaz, con los ajustes de `motores.headless` y
    # además estos argumentos por cliente. Los permisos no están aquí (cotejo-7yfw1e,
    # dec-kiik): terminal libre en su worktree con los prohibidos de fábrica, que pone
    # `clientes.Cliente.terminal_libre` siempre, para que una config propia no se los lleve.
    # `stream-json` es lo que deja ver en el detalle de la tarea qué está haciendo mientras
    # trabaja. `timeout_seg` es cuánto se le deja antes de pararlo.
    "lanzar": {"timeout_seg": 3600,
               "argumentos_extra": {
                   "claude": ["--output-format", "stream-json", "--verbose"]}},
    # Dónde corre el agente para cada proyecto de Cotejo. Sin entrada, corre donde estés.
    "proyectos": {},
    # Un worktree por despacho (`tareas/worktrees.py`): si la tarea es de un repo de git,
    # `despachar` le crea una carpeta y una rama `cotejo/<id>` propias. `carpeta` es dónde (sin
    # entrada, la carpeta de estado de Cotejo: fuera del repo y del vault); `aislar: false`
    # vuelve al comportamiento de antes para todos los despachos, como `--sin-aislar` para uno.
    "worktrees": {"carpeta": None, "aislar": True},
    # Modelos añadidos por un cliente de IA. La clave es el nombre que se guarda en
    # #agente/<clave>; el id es el que entiende el cliente que lo ejecuta.
    "modelos": [],
    # Reglas propias, que ganan a las de fábrica; y las de fábrica que quieras apagar por nombre.
    "reglas_extra": [],
    "reglas_apagadas": [],
    # Alias de persona: nombres adicionales que se tratan como #agente/persona en el vault.
    # Por defecto solo "persona", pero el usuario puede añadir otros (p. ej. ["persona", "<tu-nombre>"]).
    # Cada alias en esta lista hará que una nota con #agente/<alias> sea tratada como asignada
    # a un humano, no a un modelo. Los aliases se leen en el board para determinar quién es persona
    # al mostrar el icono en CotejoBoard, y en niveles.py para resolver #agente/<alias>.
    "alias_persona": ["persona"],
    # Cuántos despachos caben a la vez en esta máquina (`cotejo capacidad`). Vacío = medirlo:
    # `mb_por_agente`, `reserva_mb`, `fraccion_swap`, `cpu_por_agente` y `maximo` pisan los
    # supuestos de `enrutador/capacidad.py`.
    "capacidad": {},
}


def ruta_config():
    # Una sola forma de encontrar el archivo para Cotejo y para el enrutador: si discreparan, uno
    # de los dos leería una config que el otro no escribe.
    return configuracion.ruta()


def _fundir(base, encima):
    """Mezcla recursiva: lo que el usuario no escribió conserva el defecto.

    Sin esto, poner `{"motores": {"sesion": {"timeout_seg": 60}}}` en la config borraría el
    comando del motor y el enrutador dejaría de funcionar por un cambio que parecía inocente.
    """
    salida = dict(base)
    for clave, valor in (encima or {}).items():
        if isinstance(valor, dict) and isinstance(salida.get(clave), dict):
            salida[clave] = _fundir(salida[clave], valor)
        else:
            salida[clave] = valor
    return salida


class ConfigInvalida(Exception):
    """La config existe pero no se puede leer. Se dice y no se sigue con los defectos.

    Seguir en silencio sería peor que fallar: quien escribió una config espera que se use, y un
    enrutador que la ignora manda su trabajo a un modelo que no eligió.
    """


CLAVE_MODELO_RE = re.compile(r"^[\w.-]+$")
CLIENTE_RE = re.compile(r"^[\w.-]+$")
NIVELES_MODELO = {"n1", "n2", "n3"}
RESERVADOS = {"humano", "persona", "n0", "n1", "n2", "n3",
              "haiku", "sonnet", "opus"}


def _validar_modelos(modelos):
    if not isinstance(modelos, list):
        raise ConfigInvalida("enrutador.modelos debe ser una lista")
    vistos = set()
    for modelo in modelos:
        if not isinstance(modelo, dict):
            raise ConfigInvalida("cada modelo registrado debe ser un objeto JSON")
        clave = str(modelo.get("clave", "")).strip().lower()
        modelo_id = str(modelo.get("modelo_id", "")).strip()
        cliente = str(modelo.get("cliente", "")).strip().lower()
        nivel = str(modelo.get("nivel", "n2")).strip().lower()
        if not CLAVE_MODELO_RE.fullmatch(clave) or clave in RESERVADOS:
            raise ConfigInvalida(
                f"clave de modelo inválida: {clave or '<vacía>'}; usa una clave nueva "
                "con letras, números, punto, guion o guion bajo")
        if clave in vistos:
            raise ConfigInvalida(f"modelo repetido en enrutador.modelos: {clave}")
        if not modelo_id or "\n" in modelo_id or "\r" in modelo_id:
            raise ConfigInvalida(f"modelo_id inválido para {clave}")
        if not CLIENTE_RE.fullmatch(cliente):
            raise ConfigInvalida(f"cliente inválido para {clave}")
        if nivel not in NIVELES_MODELO:
            raise ConfigInvalida(f"nivel inválido para {clave}: {nivel}")
        vistos.add(clave)


def _leer_entero(ruta):
    if not ruta.exists():
        return {}
    try:
        entero = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ConfigInvalida(f"No pude leer {ruta}: {error}") from error
    if not isinstance(entero, dict):
        raise ConfigInvalida(f"{ruta} no tiene un objeto JSON dentro")
    return entero


def cargar(ruta=None):
    """La config efectiva del enrutador, más de dónde salió cada cosa."""
    ruta = Path(ruta) if ruta else ruta_config()
    datos, origen = {}, "defectos"
    if ruta.exists():
        entero = _leer_entero(ruta)
        datos = entero.get(CLAVE) or {}
        origen = str(ruta)
    # `copy.deepcopy`: sin él, `_fundir` devuelve el propio diccionario `maestro` de DEFECTOS
    # cuando nadie lo pisa en la config, y rellenar `terminal` ahí abajo mutaría el defecto de
    # módulo para todas las llamadas siguientes (y para otras pruebas).
    config = _fundir(copy.deepcopy(DEFECTOS), datos)
    if isinstance(config.get("maestro"), dict) and config["maestro"].get("terminal") is None:
        config["maestro"]["terminal"] = _terminal_por_defecto()
    _validar_modelos(config.get("modelos", []))

    # Fijar el motor por entorno es lo que deja correr la batería de pruebas sin que pueda
    # llamar a un modelo por descuido: una prueba que gasta dinero se acaba desactivando.
    motor_entorno = os.environ.get("COTEJO_MOTOR")
    if motor_entorno:
        config["motor"] = motor_entorno
    config["_origen"] = {"config": origen, "clave": CLAVE,
                         "motor": "COTEJO_MOTOR" if motor_entorno else origen}
    return config


def directorio_de(config, proyecto):
    """Dónde debería trabajar el agente para ese proyecto, o None si no está dicho."""
    ruta = (config.get("proyectos") or {}).get(proyecto)
    return Path(ruta).expanduser() if ruta else None


def guardar_modelos(modelos, ruta=None):
    """Guarda el catálogo sin tocar el resto de la configuración de Cotejo."""
    _validar_modelos(modelos)
    ruta = Path(ruta) if ruta else ruta_config()
    entero = _leer_entero(ruta)
    enrutador = dict(entero.get(CLAVE) or {})
    enrutador["modelos"] = modelos
    entero[CLAVE] = enrutador
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(json.dumps(entero, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    os.replace(temporal, ruta)


def registrar_modelo(modelo, ruta=None):
    """Añade o actualiza un modelo por su clave, operación idempotente para skills."""
    clave = str(modelo.get("clave", "")).strip().lower()
    config = cargar(ruta)
    modelos = list(config.get("modelos", []))
    reemplazado = False
    for indice, actual in enumerate(modelos):
        if actual.get("clave") == clave:
            modelos[indice] = dict(modelo, clave=clave)
            reemplazado = True
            break
    if not reemplazado:
        modelos.append(dict(modelo, clave=clave))
    guardar_modelos(modelos, ruta)
    return dict(modelo, clave=clave), reemplazado


def quitar_modelo(clave, ruta=None):
    """Quita un modelo personalizado y devuelve si existía."""
    clave = str(clave or "").strip().lower()
    if clave in RESERVADOS:
        raise ConfigInvalida(f"No se puede quitar el modelo integrado «{clave}»")
    config = cargar(ruta)
    modelos = list(config.get("modelos", []))
    restantes = [modelo for modelo in modelos if modelo.get("clave") != clave]
    if len(restantes) == len(modelos):
        return False
    guardar_modelos(restantes, ruta)
    return True
