"""Lo que pasó con cada tarea: quién la tomó, con qué la entregó, por qué se le devolvió.

Vive fuera del Markdown a propósito, y esa es la frontera que decide este archivo: **en la
línea de la tarea cabe su estado, y en la bitácora cabe lo que pasó para que llegara ahí.**

El estado se queda en la línea porque es lo que hace que el vault sea la única fuente y que
todo se vea igual desde Obsidian. El texto libre no puede seguirlo: la evidencia de una
entrega son comandos, salidas de pruebas y hashes de commit, y eso dentro de un `- [ ]` deja
la nota ilegible en Obsidian y en el board, que es justo lo que Cotejo existe para evitar. Ese
texto tampoco es estado: no dice dónde está la tarea, dice qué ocurrió en una transición. Si
este archivo se borra, no se pierde ni una tarea ni una columna; se pierde la memoria de por
qué. Esa asimetría es la que justifica tenerlo aparte.

Es append-only: una línea JSON por operación, nunca se reescribe. Se lee con `tail`.

No importa GTK, como `estado.py` y `cli.py`: lo escriben y lo leen igual la CLI de los agentes
y el board.
"""

import json
import os
import time

from . import rutas
from .modelo import id_actual

ARCHIVO = rutas.estado() / "bitacora.jsonl"

# Cuánto se lee hacia atrás para reconstruir lo último de cada tarea. El archivo solo crece, y
# esto se llama en cada repintado del board: sin tope, dentro de un año cada cambio del vault
# costaría leer el historial entero. Como solo interesa la última anotación de cada tarea, la
# cola basta; lo que quede más atrás ya estaba pisado por algo más nuevo.
COLA_BYTES = 256 * 1024

# Las claves que llevan texto de una persona o de un agente. Una anotación sin ninguna de
# ellas (tomar, mover) es historial, pero no tiene nada que enseñar en una carta.
CON_TEXTO = ("evidencia", "resumen", "motivo")

# La operación con la que un despacho deshace su propio `tomar` (`enrutador/cotejo.py`).
SOLTAR = "soltar"


def anotar(operacion, proyecto, tarea, **extra):
    """Deja constancia de quién hizo qué. Que falle no debe tumbar la operación ya escrita.

    La tarea ya está escrita en el vault cuando esto corre: el estado no depende de que esta
    línea llegue al disco, así que un fallo aquí se calla en vez de deshacer nada.
    """
    linea = {"cuando": int(time.time()), "operacion": operacion, "id": tarea.id,
             "proyecto": proyecto.nombre, "texto": tarea.texto,
             # "nota" se llama así desde la primera línea del archivo y así se queda, aunque
             # lo que traiga sea «dónde vive la tarea en su fuente».
             "nota": tarea.donde, "agente": tarea.agente, **extra}
    try:
        ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
        with ARCHIVO.open("a", encoding="utf-8") as archivo:
            archivo.write(json.dumps(linea, ensure_ascii=False) + "\n")
    except OSError:
        return False
    return True


def anotar_verbo(operacion, carpeta, **extra):
    """Deja constancia de un verbo del almacén de un repo (`init`, `editar`, `proponer`,
    `anotar`): no es de una tarea, es del proyecto de `carpeta`. Es lo que la pantalla
    Preparando (`tareas/progreso.py`) lee para saber en qué paso va el agente.

    Va al mismo archivo, con `carpeta` en vez de `id`: así `ultimas`, `ultima_entrega` e
    `ids_con` (que piden `id`) no la ven, y el historial de tareas queda como estaba. Que
    falle no tumba el verbo, igual que `anotar`.
    """
    linea = {"cuando": int(time.time()), "operacion": operacion,
             "proyecto": os.path.basename(os.path.normpath(str(carpeta))),
             "carpeta": str(carpeta), **extra}
    try:
        ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
        with ARCHIVO.open("a", encoding="utf-8") as archivo:
            archivo.write(json.dumps(linea, ensure_ascii=False) + "\n")
    except OSError:
        return False
    return True


def _anotaciones():
    """Las anotaciones válidas de la cola, ya como diccionarios."""
    salida = []
    for linea in _cola():
        try:
            anotacion = json.loads(linea)
        except ValueError:
            # Una línea a medio escribir o partida por el tope de lectura no invalida el resto.
            continue
        if isinstance(anotacion, dict):
            salida.append(anotacion)
    return salida


def _con_resultado_capturas(entrega, anotaciones):
    """La entrega con lo que el board obtuvo al capturarla fuera del sandbox, si ya terminó.

    La petición y el resultado son dos líneas append-only. Se unen al leer para que la ficha y
    `comprobar` sigan viendo una sola entrega, con sus imágenes o con el motivo del fallo.
    """
    if not entrega or entrega.get("operacion") != "entregar":
        return entrega
    for anotacion in anotaciones:
        if (anotacion.get("operacion") == "capturar"
                and id_actual(anotacion.get("id", "")) == id_actual(entrega.get("id", ""))
                and anotacion.get("entrega_cuando") == entrega.get("cuando")):
            entrega = {**entrega, "capturas": anotacion.get("capturas") or []}
            if anotacion.get("capturas_avisos"):
                entrega["capturas_avisos"] = anotacion["capturas_avisos"]
    return entrega


def ultimas():
    """Por id de tarea, la última anotación que trae texto libre.

    Es lo que contesta «¿qué me entregaron?» y «¿por qué me la devolvieron?» sin abrir el
    archivo a mano. Una tarea entregada, devuelta y vuelta a entregar se queda con lo último,
    que es lo que hay que leer para decidir.

    Con una excepción: el motivo de un `soltar` —un despacho que la tomó y no pudo lanzarla:
    sin worktree, o un cliente que salió con error— solo vale mientras la tarea sigue en
    Pendiente. Habla del despacho, no del trabajo, así que en cuanto alguien la vuelve a
    tomar se descarta y queda lo que había antes de él (cotejo-fyj565): si no, el encargo
    siguiente le decía al agente «esta tarea volvió atrás» con un «Not logged in» que ya no
    aplica. El motivo de un rechazo o de un `bloquear` sí sobrevive a tomarla, porque es lo
    que hay que leer para rehacerla.
    """
    datos = _PorId()
    antes_de_soltar = {}
    anotaciones = _anotaciones()
    for anotacion in anotaciones:
        if not anotacion.get("id"):
            continue
        clave = id_actual(anotacion["id"])
        previa = datos.get(clave)
        soltada = bool(previa) and previa.get("operacion") == SOLTAR
        if any(anotacion.get(c) for c in CON_TEXTO):
            if anotacion.get("operacion") != SOLTAR:
                antes_de_soltar.pop(clave, None)
            elif not soltada:
                # Varios despachos fallidos seguidos: lo que se recupera es lo de antes del
                # primero, no el motivo del anterior.
                antes_de_soltar[clave] = previa
            datos[clave] = anotacion
        elif anotacion.get("operacion") == "tomar" and soltada:
            anterior = antes_de_soltar.pop(clave, None)
            if anterior:
                datos[clave] = anterior
            else:
                del datos[clave]
    for clave, anotacion in list(datos.items()):
        datos[clave] = _con_resultado_capturas(anotacion, anotaciones)
    return datos


def ultima_entrega(tarea_id):
    """La última anotación de `entregar` para esta tarea, o None si nunca se entregó.

    A diferencia de `ultimas()`, que se queda con lo más reciente que traiga texto libre sin
    mirar la operación, esto busca específicamente `entregar`: ahí viven `git` y `pruebas`, y
    un rechazo posterior —que también lleva texto, en `motivo`— no puede tapar esa evidencia.
    Es lo que usa `comprobar` (B2) para saber qué volver a correr.
    """
    buscada = id_actual(tarea_id)
    encontrada = None
    anotaciones = _anotaciones()
    for anotacion in anotaciones:
        if anotacion.get("operacion") != "entregar":
            continue
        if id_actual(anotacion.get("id", "")) == buscada:
            encontrada = anotacion
    return _con_resultado_capturas(encontrada, anotaciones)


def pendientes_de_captura():
    """Entregas con `--captura-desde` cuyo resultado el board todavía no anotó.

    También una entrega hecha por CLI, sin un agente lanzado por el board, aparece aquí: así el
    próximo refresco del board la completa fuera del sandbox. Un fallo ya anotado no se reintenta
    en cada refresco.
    """
    anotaciones = _anotaciones()
    hechas = {(id_actual(a.get("id", "")), a.get("entrega_cuando"))
              for a in anotaciones if a.get("operacion") == "capturar"}
    return [a for a in anotaciones
            if a.get("operacion") == "entregar" and a.get("capturas_solicitadas")
            and (id_actual(a.get("id", "")), a.get("cuando")) not in hechas]


def ids_con(*operaciones):
    """Los ids (con el prefijo de ahora) que tienen alguna anotación de esas `operaciones`.

    Lee el archivo **entero** y no la cola: lo usa `limpiar`, que pregunta justo por tareas
    viejas, cuyo `comprobar` puede estar mucho más atrás de lo que `_cola` alcanza. Se llama
    una vez por limpieza, no en cada repintado, así que leerlo todo no cuesta lo que costaría
    en `ultimas()`. Sin archivo, ninguno.
    """
    ids = set()
    try:
        with ARCHIVO.open(encoding="utf-8", errors="replace") as archivo:
            for linea in archivo:
                try:
                    anotacion = json.loads(linea)
                except ValueError:
                    continue
                if (isinstance(anotacion, dict) and anotacion.get("id")
                        and anotacion.get("operacion") in operaciones):
                    ids.add(id_actual(anotacion["id"]))
    except OSError:
        pass
    return ids


class _PorId(dict):
    """Un dict de anotaciones que se consulta igual con el id de antes o el de ahora.

    La bitácora solo se agrega y nunca se reescribe, así que las líneas anteriores a la
    migración siguen diciendo `foco-…`; las claves se guardan con el id de ahora y la consulta
    se traduce, para que la evidencia de una tarea no desaparezca de su carta.
    """

    def get(self, clave, defecto=None):
        return super().get(id_actual(clave), defecto)

    def __getitem__(self, clave):
        return super().__getitem__(id_actual(clave))

    def __contains__(self, clave):
        return super().__contains__(id_actual(clave))


def _cola():
    """Las últimas líneas del archivo, o ninguna si no se puede leer.

    No hay avisos aquí: a diferencia de una nota que no se puede leer, perder la bitácora no
    esconde ninguna tarea. La carta se queda sin su evidencia, y eso se ve.
    """
    try:
        with ARCHIVO.open("rb") as archivo:
            tamano = archivo.seek(0, os.SEEK_END)
            archivo.seek(max(0, tamano - COLA_BYTES))
            crudo = archivo.read()
    except OSError:
        return []
    if tamano > COLA_BYTES:
        # Al saltar al final se cae en mitad de una línea: esa se descarta entera.
        crudo = crudo.partition(b"\n")[2]
    return crudo.decode("utf-8", "replace").splitlines()
