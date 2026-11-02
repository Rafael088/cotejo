"""Una fuente que vive en otro programa: Notion, Linear, lo que venga, hablado por subproceso.

Cotejo no sabe nada de la app de detrás. Lanza un comando —el **adaptador**— con un subcomando,
lee JSON de su salida estándar y lo convierte al modelo. Por qué un proceso aparte y no un
módulo más de `tareas/fuentes/`:

- Se escribe en cualquier lenguaje: Python, Node, Go o el CLI oficial de la app.
- Sus dependencias (un SDK, un cliente HTTP) no se le cobran a quien no lo usa.
- Funciona igual en Linux y en Windows: un ejecutable en el `PATH`, o una ruta.

El precio es un proceso por llamada, que para verbos de agente es poco comparado con leer el
segundo cerebro entero.

## El contrato

Todo sale en JSON con `"esquema": 1`. Los parámetros de la fuente —los de su entrada en la
config— llegan en la variable de entorno `COTEJO_FUENTE_CONFIG`, como JSON; así el adaptador no
tiene que saber dónde está el archivo de config de Cotejo ni cómo se organiza.

    doctor                                   {"ok": true, "mensaje": "Conectado a ..."}
    protocolo                                qué sabe hacer: {"nombre", "verbos", "parametros", ...}
    escanear [--hechas]                      {"proyectos": [...], "avisos": [...], "leido": N}
    estado <ref> <nuevo> --esperado JSON     {"cambio": bool, "tarea": {...}}
    agente <ref> <quien> --esperado JSON     (quien vacío: la deja sin dueño)
    marcar <ref> --hecha|--pendiente --esperado JSON     (solo lo usa el board: es de una persona)
    crear --proyecto N [--proyecto-ref R] --texto T [--dificultad D] [--version V]

Una tarea es `{"id", "texto", "estado", "agente", "dificultad", "hecha", "ref", "url",
"donde"}`: `id` es cómo la nombra un agente (en minúsculas y estable), `ref` es cómo la
encuentra el adaptador si no es el mismo `id`. Un proyecto es `{"nombre", "donde", "estado",
"prioridad", "url", "ref", "leido", "tareas": [...]}`.

`"version"` (v1.2.4) es opcional: la versión a la que pertenece la tarea, `"v1.2.4"` o
`"v1.2"` (con o sin la `v`); una que no lo sea se ignora. `crear` solo recibe `--version` si se
pidió, y siempre normalizada (`v1.2.4`): un adaptador que no sepa de versiones no la ve nunca.

`"cerrada"` (v1.2.2) es opcional: la fecha en que se dio por terminada, como "AAAA-MM-DD". Es
para el filtro de fechas de la columna Finalizada de CotejoBoard; un adaptador que no la sepa
la omite y la tarea solo se ve en el filtro "Todas", igual que una de Obsidian sin fecha.

Los errores salen con código distinto de 0 y `{"error", "tipo", "salida", "reintentable"}`.
`tipo` es lo que Cotejo traduce: `cambiada` (la tarea no está como en `--esperado`: no se tocó),
`no-se-crea-aqui`, `no-implementado`; cualquier otro es un fallo de la fuente.

## Lo que el adaptador **no** hace

Las reglas del trabajo —que entregar exige evidencia, que bloquear la suelta y exige motivo,
qué transiciones valen— siguen en `cli.py`. Al adaptador se le piden primitivas (poner un
estado, poner un agente), no verbos de negocio: si cada adaptador implementara `entregar`,
cada uno lo haría un poco distinto, y la evidencia acabaría en la app de fuera en vez de en la
bitácora de Cotejo. Por eso tampoco hay `--evidencia` ni `--motivo` en el contrato.

Lo que sí se le exige es lo mismo que a Obsidian: **escribir verificado**. `--esperado` lleva
la tarea como Cotejo la leyó; si ya no está así, el adaptador no escribe y contesta `cambiada`.
"""

import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

from .. import version as versiones
from ..fuente import Fuente
from ..modelo import (HECHA, PENDIENTE, FuenteNoResponde, NoSeCreaAqui, Proyecto, Tarea,
                      TareaCambiada)

ESQUEMA = 1
ESTADOS = (PENDIENTE, "en-curso", "por-validar", "por-integrar")
TIMEOUT = 30
# "cerrada" es opcional y de un adaptador que puede equivocarse: una que no tenga esta forma
# se descarta en vez de colar una fecha rara al filtro de la columna Finalizada.
FECHA_CERRADA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def comando_de(valor):
    """El comando de la config, como lista. Un texto se parte como lo partiría una shell."""
    if isinstance(valor, str):
        return shlex.split(valor, posix=os.name != "nt")
    return [str(parte) for parte in valor or []]


class Externa(Fuente):
    tipo = "externa"
    parametros = {
        "comando": "El adaptador: un ejecutable en el PATH o una ruta (\"cotejo-notion\").",
        "timeout_seg": f"Cuánto esperar a que conteste, en segundos (por defecto {TIMEOUT}).",
        "accion_abrir": "Cómo se llama abrir una tarea en su app, para el menú del board.",
    }

    def __init__(self, nombre, config=None):
        self.nombre = nombre
        self.config = {k: v for k, v in (config or {}).items() if k != "fuente"}
        self.comando = comando_de(self.config.get("comando"))
        self.timeout = self.config.get("timeout_seg") or TIMEOUT
        self.accion_abrir = (self.config.get("accion_abrir")
                             or f"Abrir en {nombre[:1].upper()}{nombre[1:]}")
        self._fallo = None
        self.reintentable = False  # si el último fallo se arregla solo repitiendo
        self._leido_total = 0
        self._leido = {}  # por `donde` de proyecto
        self._urls = {}  # por `donde` de proyecto, para abrir el proyecto entero
        self._refs = {}  # por `donde` de proyecto, para crear en él

    # --- el proceso -----------------------------------------------------

    @property
    def problema(self):
        # Lo barato primero y sin lanzar nada: esto lo consulta la barra cada pocos minutos.
        # Que el adaptador no conteste se descubre al escanear, y queda en `_fallo`.
        if not self.comando:
            return (f"La fuente «{self.nombre}» no dice qué comando lanzar. Regístrala con "
                    f"`fuentes agregar {self.nombre} --comando <ejecutable>`.")
        if shutil.which(self.comando[0]) is None and not Path(self.comando[0]).is_file():
            return (f"No encuentro el comando «{self.comando[0]}» de la fuente «{self.nombre}». "
                    f"Instálalo o pon su ruta completa con `fuentes agregar`.")
        return self._fallo

    def llamar(self, *argumentos):
        """Lanza el adaptador y devuelve su JSON. Traduce sus errores a los del modelo."""
        # También con el nombre de antes: un adaptador escrito cuando esto se llamaba Foco la
        # busca en FOCO_FUENTE_CONFIG, y no tiene por qué enterarse del cambio.
        parametros = json.dumps(self.config)
        entorno = {**os.environ, "COTEJO_FUENTE_CONFIG": parametros,
                   "FOCO_FUENTE_CONFIG": parametros}
        try:
            hecho = subprocess.run([*self.comando, *argumentos], capture_output=True,
                                   text=True, encoding="utf-8", timeout=self.timeout,
                                   env=entorno, stdin=subprocess.DEVNULL)
        except FileNotFoundError as error:
            raise FuenteNoResponde(f"No pude lanzar «{self.comando[0]}»: {error}",
                                   "Comprueba que el adaptador esté instalado.") from error
        except subprocess.TimeoutExpired as error:
            raise FuenteNoResponde(
                f"«{self.nombre}» no contestó en {self.timeout} s",
                "La app de fuera va lenta o no responde. Reintenta; si se repite, sube "
                "`timeout_seg` en su config.", reintentable=True) from error
        try:
            datos = json.loads(hecho.stdout)
        except ValueError:
            detalle = (hecho.stderr or hecho.stdout).strip().splitlines()[-1:] or ["sin salida"]
            raise FuenteNoResponde(
                f"«{self.nombre}» no contestó JSON (código {hecho.returncode}): {detalle[0]}",
                f"Pruébalo a mano: `fuentes probar {self.nombre}`.")
        if not isinstance(datos, dict):
            raise FuenteNoResponde(f"«{self.nombre}» contestó algo que no es un objeto JSON")
        if hecho.returncode != 0 or "error" in datos:
            self._traducir(datos)
        if datos.get("esquema") != ESQUEMA:
            raise FuenteNoResponde(
                f"«{self.nombre}» habla el esquema {datos.get('esquema')!r} y Cotejo el {ESQUEMA}",
                "Actualiza el adaptador o Cotejo para que hablen el mismo.")
        return datos

    def _traducir(self, datos):
        mensaje = datos.get("error") or "falló sin decir por qué"
        tipo = datos.get("tipo")
        if tipo == "cambiada":
            raise TareaCambiada(datos.get("donde") or self.nombre)
        if tipo == "no-se-crea-aqui":
            raise NoSeCreaAqui(mensaje)
        if tipo == "no-implementado":
            raise NotImplementedError(mensaje)
        raise FuenteNoResponde(f"{self.nombre}: {mensaje}", datos.get("salida", ""),
                               bool(datos.get("reintentable")))

    # --- leer -----------------------------------------------------------

    def escanear(self, incluir_hechas=False, avisos=None):
        self._fallo = None
        self._leido_total, self._leido, self._urls, self._refs = 0, {}, {}, {}
        try:
            datos = self.llamar("escanear", *(["--hechas"] if incluir_hechas else []))
        except (FuenteNoResponde, NotImplementedError, TareaCambiada, NoSeCreaAqui) as error:
            # No se devuelve una lista vacía y ya está: cero proyectos se ve como «todo al día»,
            # que es la peor mentira para un gestor de tareas. Queda como `problema`, que la
            # barra, el board y la CLI ya saben enseñar.
            salida = getattr(error, "salida", "")
            self._fallo = f"{error}" + (f". {salida}" if salida else "")
            self.reintentable = bool(getattr(error, "reintentable", False))
            return []
        if avisos is not None:
            avisos.extend(str(a) for a in datos.get("avisos") or [])
        self._leido_total = int(datos.get("leido") or 0)
        proyectos = []
        for crudo in datos.get("proyectos") or []:
            proyecto = self._proyecto(crudo, incluir_hechas, avisos)
            if proyecto is not None:
                proyectos.append(proyecto)
        proyectos.sort(key=lambda p: p.orden)
        return proyectos

    def _proyecto(self, crudo, incluir_hechas, avisos):
        nombre = str(crudo.get("nombre") or "").strip()
        if not nombre:
            if avisos is not None:
                avisos.append(f"{self.nombre}: un proyecto sin nombre, y sus tareas no están")
            return None
        donde = str(crudo.get("donde") or f"{self.nombre}: {nombre}")
        proyecto = Proyecto(nombre, donde=donde, estado=str(crudo.get("estado") or ""),
                            prioridad=str(crudo.get("prioridad") or ""))
        self._leido[donde] = int(crudo.get("leido") or 0)
        self._urls[donde] = str(crudo.get("url") or "")
        self._refs[donde] = str(crudo.get("ref") or "")
        for tarea in crudo.get("tareas") or []:
            tarea = self._tarea(tarea, donde, avisos)
            if tarea is None:
                continue
            if tarea.hecha:
                if incluir_hechas:
                    proyecto.hechas.append(tarea)
            else:
                proyecto.tareas.append(tarea)
        return proyecto

    def _tarea(self, crudo, donde, avisos=None):
        identificador = self.normalizar_id(crudo.get("id") or "")
        texto = " ".join(str(crudo.get("texto") or "").split())
        if not identificador or not texto:
            if avisos is not None:
                avisos.append(f"{self.nombre}: una tarea sin id o sin texto en {donde}, "
                              f"y no está en la lista")
            return None
        estado = crudo.get("estado") or PENDIENTE
        hecha = bool(crudo.get("hecha")) or estado == HECHA
        if estado not in ESTADOS:
            if not hecha and avisos is not None:
                avisos.append(f"{self.nombre}: la tarea {identificador} trae el estado "
                              f"{estado!r}, que Cotejo no conoce; se lee como pendiente")
            estado = PENDIENTE
        cerrada = crudo.get("cerrada")
        cerrada = cerrada if isinstance(cerrada, str) and FECHA_CERRADA_RE.match(cerrada) else None
        return Tarea(texto, id=identificador, donde=str(crudo.get("donde") or donde),
                     estado=estado, agente=str(crudo.get("agente") or ""),
                     dificultad=str(crudo.get("dificultad") or ""), hecha=hecha,
                     cerrada=cerrada, version=versiones.de_tarea(crudo.get("version")) or "",
                     sitio={"ref": str(crudo.get("ref") or identificador),
                            "url": str(crudo.get("url") or "")})

    def normalizar_id(self, texto):
        # El contrato pide ids en minúsculas; así `COTEJO-12` escrito por una persona sirve igual.
        return str(texto).strip().lower()

    def leido(self, proyectos=None):
        if proyectos is None:
            return self._leido_total or sum(self._leido.values())
        return sum(self._leido.get(p.donde, 0) for p in proyectos)

    # --- escribir -------------------------------------------------------

    def _escribir(self, verbo, tarea, *argumentos):
        esperado = {"texto": tarea.texto, "estado": tarea.estado, "agente": tarea.agente,
                    "hecha": tarea.hecha}
        datos = self.llamar(verbo, (tarea.sitio or {}).get("ref") or tarea.id, *argumentos,
                            "--esperado", json.dumps(esperado, ensure_ascii=False))
        actual = self._tarea(datos.get("tarea") or {}, tarea.donde)
        if actual is None:
            raise FuenteNoResponde(f"«{self.nombre}» escribió pero no devolvió la tarea",
                                   "Vuelve a pedir `tareas` para ver cómo quedó.")
        return actual

    def poner_estado(self, tarea, nuevo):
        return self._escribir("estado", tarea, nuevo)

    def poner_agente(self, tarea, agente):
        return self._escribir("agente", tarea, agente)

    def marcar(self, tarea, hecha=True):
        return self._escribir("marcar", tarea, "--hecha" if hecha else "--pendiente")

    def crear(self, proyecto, texto, dificultad="", version=""):
        argumentos = ["crear", "--proyecto", proyecto.nombre, "--texto", texto]
        if self._refs.get(proyecto.donde):
            argumentos += ["--proyecto-ref", self._refs[proyecto.donde]]
        if dificultad:
            argumentos += ["--dificultad", dificultad]
        if versiones.de_tarea(version):
            argumentos += ["--version", versiones.de_tarea(version)]
        datos = self.llamar(*argumentos)
        actual = self._tarea(datos.get("tarea") or {}, proyecto.donde)
        if actual is None:
            raise FuenteNoResponde(f"«{self.nombre}» creó pero no devolvió la tarea",
                                   "Vuelve a pedir `tareas` para ver si quedó.")
        return actual

    # --- dónde vive -----------------------------------------------------

    def uri(self, cosa):
        if isinstance(cosa, Tarea):
            return (cosa.sitio or {}).get("url", "")
        return self._urls.get(getattr(cosa, "donde", ""), "")
