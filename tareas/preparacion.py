"""Las preparaciones de proyectos en segundo plano (v1.3.0): qué se lanzó y cómo va.

Cuando la persona termina la entrevista de «Nuevo proyecto», Cotejo lanza su agente sin
interfaz con el prompt de inicio (`enrutador/preparar.py`, que es quien lanza). Aquí está lo que
no lanza nada: el registro de cada lanzamiento y la lectura de su estado, que piden la pantalla
Preparando del board y el resumen de la barra (`estado.py`). Sin GTK y sin importar el enrutador
al cargarse: `--estado` tiene que seguir arrancando en milisegundos.

El registro es el mismo de los despachos headless (`enrutador/bitacora.py`): `fase: "lanzado"`
con `pid`, `programa` (el argv del cliente, no el de systemd-run) y `host` en cuanto el proceso
existe, y `fase: "terminado"` con su `codigo` cuando vuelve. Por eso «¿murió sin volver?» se
contesta con la misma función que usa `revisar` para dar una tarea por «perdida»
(`enrutador.procesos.anotado_muerto`). Va en su propio archivo por preparación, en
`<estado>/preparaciones/<id>.json`, y no en `despachos.jsonl`: allí cada línea es una tarea
repartida, y un proyecto que se prepara todavía no tiene ninguna.

Los estados, en el orden en que se enseñan:

- `preparando`: el proceso sigue vivo y hubo actividad hace poco.
- `colgado`: el proceso sigue vivo pero nada se movió en `.cotejo/` del proyecto (donde escriben
  `init`, `editar`, `proponer`, `anotar`, `crear` y la bitácora) ni en su registro de salida
  durante `MINUTOS_SIN_ACTIVIDAD` (`enrutador.preparar.minutos_sin_actividad` en la config).
- `fallo`: el proceso volvió con un código distinto de 0, o volvió con 0 sin dejar ninguna
  tarea (un cliente sin permiso para correr `cotejo` sale «bien» sin haber hecho nada), o murió
  sin que nadie viera cómo y el proyecto no tiene tareas.
- `listo`: volvió con 0 y el proyecto tiene tareas (o murió sin que se viera, pero las tiene).
  También **con el proceso vivo** si el resultado ya está entero (`resultado_completo`): los
  cinco pasos están en `.cotejo/` y nada se movió ahí en `SEGUNDOS_DE_GRACIA`. En Windows
  `cmd.exe /c opencode.cmd` puede no salir nunca después de terminar el trabajo (cotejo-8m9ab7):
  lo que cuenta es lo que dejó, no que el proceso vuelva. El hilo que lo espera
  (`enrutador.preparar.vigilar`) lo para y lo anota como terminado con 0.
- `cancelado`: la persona lo paró con «Cancelar» mientras preparaba.

`colgado`, `fallo` y `cancelado` traen `acciones`: `reintentar` y `abrir_en_terminal`, lo que
ofrece la pantalla; `preparando` y `colgado`, `puede_cancelar`. `visto`, `en-terminal` y
`cancelado` dejan de contar para la barra.

Qué hay en disco de cada paso (`lo_que_existe`) se mira sin la bitácora: si sus líneas no
llegan (otro `cotejo`, otra ruta), la pantalla mueve los pasos igual.
"""

import json
import os
import re
import socket
import threading
import time
import uuid

from . import configuracion, rutas

ESQUEMA = 1
CARPETA = rutas.estado() / "preparaciones"
MINUTOS_SIN_ACTIVIDAD = 10
SEGUNDOS_DE_GRACIA = 120
RECORTE = 600

# Leer, cambiar y guardar un registro va bajo este candado: el hilo que espera al proceso viejo
# de un reintento no puede pisar lo que acaba de anotar el nuevo.
_CANDADO = threading.RLock()

PREPARANDO, COLGADO, LISTO, FALLO = "preparando", "colgado", "listo", "fallo"
VISTO, EN_TERMINAL, CANCELADO = "visto", "en-terminal", "cancelado"
ACCIONES = ("reintentar", "abrir_en_terminal")
# Lo que la barra enseña: lo que está en marcha y lo que espera que la persona lo mire.
PARA_LA_BARRA = (PREPARANDO, COLGADO, FALLO, LISTO)


def nuevo_id(proyecto):
    base = re.sub(r"[^a-z0-9]+", "-", (proyecto or "proyecto").lower()).strip("-")[:40]
    return f"{base or 'proyecto'}-{uuid.uuid4().hex[:6]}"


def _ruta(ident):
    if not re.fullmatch(r"[a-z0-9-]{1,60}", ident or ""):
        raise ValueError(f"«{ident}» no es el id de una preparación.")
    return CARPETA / f"{ident}.json"


def guardar(registro):
    """Reemplazo atómico del registro: quien lo lee (la barra, el board) nunca lo ve a medias."""
    ruta = _ruta(registro["id"])
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(f".{ruta.name}.tmp")
    temporal.write_text(json.dumps({"esquema": ESQUEMA, **registro}, ensure_ascii=False),
                        encoding="utf-8")
    os.replace(temporal, ruta)
    return registro


def leer(ident):
    try:
        datos = json.loads(_ruta(ident).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return datos if isinstance(datos, dict) else None


def todas():
    """Los registros, del más nuevo al más viejo. Uno roto se salta: no tumba a los demás."""
    if not CARPETA.is_dir():
        return []
    registros = [leer(r.stem) for r in CARPETA.glob("*.json")]
    return sorted((r for r in registros if r), key=lambda r: -int(r.get("ts", 0)))


def anotar_lanzado(registro, pid, programa):
    """Lo que se anota en cuanto el proceso existe, como `al_lanzar` en `despachar`."""
    with _CANDADO:
        from enrutador import procesos  # aquí y no arriba, como en `_muerto`
        registro.update(fase="lanzado", pid=pid, programa=programa, host=socket.gethostname(),
                        nacio=procesos.nacimiento(pid), ts=int(time.time()))
        for clave in ("codigo", "terminado_ts", "por_resultado"):
            registro.pop(clave, None)
        return guardar(registro)


def anotar_terminado(ident, codigo, pid=None, por_resultado=False):
    """La otra mitad: el proceso volvió. Si alguien ya lo dio por visto, se lo llevó a una
    terminal, lo canceló o lo relanzó (`pid` ya es otro), no se pisa. `por_resultado`: no
    volvió solo, se paró porque el resultado ya estaba entero."""
    with _CANDADO:
        registro = leer(ident)
        if registro is None or registro.get("fase") != "lanzado":
            return registro
        if pid is not None and registro.get("pid") != pid:
            return registro
        registro.update(fase="terminado", codigo=int(codigo), terminado_ts=int(time.time()))
        registro.pop("por_resultado", None)
        if por_resultado:
            registro["por_resultado"] = True
        return guardar(registro)


def cambiar_fase(ident, fase):
    with _CANDADO:
        registro = leer(ident)
        if registro is None:
            raise KeyError(ident)
        registro["fase"] = fase
        return guardar(registro)


def anotar_cancelado(ident):
    """La persona lo paró con «Cancelar»: `cancelado`, con la hora para que el reloj se pare."""
    with _CANDADO:
        registro = leer(ident)
        if registro is None:
            raise KeyError(ident)
        registro.update(fase=CANCELADO, terminado_ts=int(time.time()))
        return guardar(registro)


def marcar_visto(ident):
    """La persona ya lo vio (abrió el proyecto, o descartó el fallo): deja de salir en la barra."""
    return cambiar_fase(ident, VISTO)


def _mtime(ruta):
    try:
        return os.stat(ruta).st_mtime
    except OSError:
        return 0


def _movido_en(base):
    """El último mtime de `base` y lo que lleva dentro (0 si no existe)."""
    marcas = [0]
    for raiz, _carpetas, archivos in os.walk(base):
        marcas.append(_mtime(raiz))
        marcas.extend(_mtime(os.path.join(raiz, a)) for a in archivos)
    return max(marcas)


def ultima_actividad(registro):
    """El último momento en que algo se movió: el lanzamiento, su salida o `.cotejo/`."""
    marcas = [float(registro.get("ts", 0)),
              _movido_en(os.path.join(registro.get("carpeta", ""), ".cotejo"))]
    if registro.get("log"):
        marcas.append(_mtime(registro["log"]))
    return int(max(marcas))


def _contar_md(carpeta):
    try:
        return sum(1 for n in os.listdir(carpeta) if n.endswith(".md"))
    except OSError:
        return 0


def _proyecto_escrito(base):
    """¿`proyecto.md` tiene algo más que el título que le pone `init`?"""
    try:
        with open(os.path.join(base, "proyecto.md"), encoding="utf-8") as archivo:
            texto = archivo.read()
    except OSError:
        return None
    texto = re.sub(r"\A---\n.*?\n---\n", "", texto, flags=re.S)
    texto = re.sub(r"^\s*# .*$", "", texto, count=1, flags=re.M)
    return bool(texto.strip())


def lo_que_existe(carpeta):
    """Lo que ya hay en `<carpeta>/.cotejo/` de cada paso del inicio: `{verbo: cuántos}`, solo
    con los que tienen algo. Se mira el disco, no la bitácora, y sin parsear el almacén: lo lee
    la barra."""
    base = os.path.join(carpeta or "", ".cotejo")
    escrito = _proyecto_escrito(base)
    if escrito is None:
        return {}
    hay = {"init": 1, "editar": int(escrito),
           "proponer": _contar_md(os.path.join(base, "decisiones")),
           "anotar": _contar_md(os.path.join(base, "arquitectura")),
           "crear": contar_tareas(carpeta)}
    return {verbo: n for verbo, n in hay.items() if n}


def segundos_de_gracia():
    ajustes = ((configuracion.cargar().get("enrutador") or {}).get("preparar") or {})
    try:
        return max(0, int(ajustes.get("segundos_de_gracia", SEGUNDOS_DE_GRACIA)))
    except (TypeError, ValueError):
        return SEGUNDOS_DE_GRACIA


def resultado_completo(registro, ahora=None, segundos=None):
    """¿Dejó el agente el resultado entero, aunque su proceso no haya vuelto?

    Los cinco pasos en `.cotejo/`, algo movido ahí desde que se lanzó (un reintento sobre un
    proyecto ya hecho no cuenta solo por lo de antes) y nada movido en `segundos` (el agente
    crea las tareas de una en una y luego enlaza sus ids en la arquitectura). Al rehacer una
    decisión, lo que tiene que haberse movido es `decisiones/`."""
    carpeta = registro.get("carpeta", "")
    if len(lo_que_existe(carpeta)) < 5:
        return False
    ahora = ahora if ahora is not None else time.time()
    segundos = segundos if segundos is not None else segundos_de_gracia()
    base = os.path.join(carpeta, ".cotejo")
    if registro.get("rehacer") and _movido_en(os.path.join(base, "decisiones")) < \
            float(registro.get("ts", 0)):
        return False
    movido = _movido_en(base)
    return movido >= float(registro.get("ts", 0)) and ahora - movido >= segundos


def contar_tareas(carpeta):
    """Cuántas tareas dejó el agente en `<carpeta>/.cotejo/tareas.md` (`- [ ]`, `- [/]`…)."""
    try:
        with open(os.path.join(carpeta, ".cotejo", "tareas.md"), encoding="utf-8") as archivo:
            texto = archivo.read()
    except OSError:
        return 0
    return len(re.findall(r"^\s*- \[.\] \S", texto, re.M))


def tiene_tareas(carpeta):
    """¿Dejó el agente alguna tarea en `<carpeta>/.cotejo/tareas.md`?"""
    return contar_tareas(carpeta) > 0


def cola_del_log(registro):
    try:
        with open(registro.get("log", ""), "rb") as archivo:
            archivo.seek(0, os.SEEK_END)
            archivo.seek(max(0, archivo.tell() - RECORTE))
            return archivo.read().decode(errors="replace").strip()
    except OSError:
        return ""


def minutos_sin_actividad():
    ajustes = ((configuracion.cargar().get("enrutador") or {}).get("preparar") or {})
    try:
        return max(1, int(ajustes.get("minutos_sin_actividad", MINUTOS_SIN_ACTIVIDAD)))
    except (TypeError, ValueError):
        return MINUTOS_SIN_ACTIVIDAD


def _muerto(registro):
    from enrutador import procesos  # aquí y no arriba: `tareas` no importa el enrutador al cargar
    return procesos.anotado_muerto(registro)


def estado(registro, ahora=None, minutos=None):
    """Cómo va una preparación, para la pantalla y para la barra. No escribe nada."""
    ahora = int(ahora if ahora is not None else time.time())
    minutos = minutos if minutos is not None else minutos_sin_actividad()
    fase = registro.get("fase")
    actividad = ultima_actividad(registro)
    salida = {k: registro.get(k) for k in ("id", "proyecto", "carpeta", "cliente", "modelo",
                                          "pid", "log", "intentos")}
    salida.update(ultima_actividad=actividad, minutos_sin_actividad=minutos, por_que="")
    preparado = tiene_tareas(registro.get("carpeta", ""))
    if fase in (VISTO, EN_TERMINAL, CANCELADO):
        cual = fase
    elif fase == "terminado":
        codigo = registro.get("codigo")
        salida["codigo"] = codigo
        if codigo == 0 and preparado:
            cual = LISTO
        elif codigo == 0:
            cual = FALLO
            salida["por_que"] = ("El agente terminó sin crear ninguna tarea: puede que no "
                                 "tuviera permiso para usar `cotejo`.")
        else:
            cual = FALLO
            salida["por_que"] = ("El agente no terminó en el tiempo máximo." if codigo == 124
                                 else f"El agente terminó con un error (código {codigo}).")
    elif fase == "lanzado" and _muerto(registro):
        # Nadie lo vio volver (se cerró Cotejo del todo, se reinició la máquina): decide lo
        # que dejó en la carpeta.
        cual = LISTO if preparado else FALLO
        if not preparado:
            salida["por_que"] = ("El proceso del agente ya no existe y no dejó las tareas del "
                                 "proyecto.")
    elif fase == "lanzado" and resultado_completo(registro, ahora):
        # Vivo, pero el trabajo ya está: el hilo que lo espera lo parará.
        cual = LISTO
    elif fase == "lanzado" and ahora - actividad >= minutos * 60:
        cual = COLGADO
        salida["por_que"] = (f"Lleva {(ahora - actividad) // 60} minutos sin escribir nada en "
                             f"el proyecto.")
    else:
        cual = PREPARANDO
    salida["estado"] = cual
    if cual == FALLO and registro.get("log"):
        salida["salida"] = cola_del_log(registro)
    salida["acciones"] = list(ACCIONES) if cual in (COLGADO, FALLO, CANCELADO) else []
    salida["puede_cancelar"] = cual in (PREPARANDO, COLGADO)
    return salida


def listar(ahora=None):
    """El estado de todas, de la más nueva a la más vieja."""
    minutos = minutos_sin_actividad()
    return [estado(r, ahora, minutos) for r in todas()]


def para_la_barra():
    """Lo que `estado.json` lleva en `preparaciones`: poco, que la barra lo lee cada vez."""
    try:
        return [{"id": e["id"], "proyecto": e["proyecto"], "estado": e["estado"]}
                for e in listar() if e["estado"] in PARA_LA_BARRA]
    except OSError:
        return []
