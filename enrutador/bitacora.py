"""Qué se despachó, a quién y cómo salió. Un JSON por línea, solo se agrega.

Es la hermana de `tareas/bitacora.py` y está aparte de ella a propósito: aquella cuenta qué
pasó con **la tarea** (quién la tomó, con qué la entregó, por qué se le devolvió) y la lee el
board para enseñar la evidencia. Esta cuenta qué pasó con **el reparto**: a qué modelo fue,
por qué regla, cuánto tardó. Mezclarlas obligaría al board a saber qué es un modelo.

Borrar este archivo no pierde ni una tarea; solo la memoria de por qué se enrutó como se
enrutó. Y esa memoria es lo único que puede contestar la pregunta que justifica el enrutador:
¿el reparto está acertando? Sin registro, «creo que va bien» es todo lo que habrá.

De la salida del modelo se guarda un recorte y no el texto entero: una sesión de Claude Code
devuelve miles de tokens, y un archivo que crece así deja de poder leerse, que es la forma
educada de no existir. La salida completa la tiene quien la lanzó, en su terminal.
"""

import json
import os
import time

from tareas import rutas
from tareas.modelo import id_actual

ESQUEMA = 1
RECORTE = 600

# Las pruebas la parchean con `mock` para no ensuciar la de la persona. Si está puesta, manda;
# si no, `ruta()` la resuelve en cada uso: calcularla al importar dejaba a las pruebas que
# cambian `COTEJO_ESTADO` después escribiendo en la real (cotejo-lr1vj6), como pasó con
# `board.json` (cotejo-2j6un7).
ARCHIVO = None


def ruta():
    """El archivo de despachos, mirado en cada uso y no al importar."""
    return ARCHIVO if ARCHIVO is not None else rutas.estado() / "despachos.jsonl"


def anotar(archivo=None, **datos):
    """Agrega una línea. Si no se puede escribir, lo dice y no rompe el despacho.

    Un fallo al anotar no puede tumbar un despacho que ya ocurrió: la tarea está tomada y el
    modelo está trabajando. Pero tampoco puede desaparecer en silencio, así que devuelve el
    problema para que el verbo lo ponga en `avisos`.

    `archivo` es para quien anota en segundo plano (el hilo que vigila un lanzamiento): se
    queda con la ruta del momento en que empezó, aunque para entonces una prueba ya haya
    devuelto `ARCHIVO` a su sitio.
    """
    destino = archivo or ruta()
    linea = {"esquema": ESQUEMA, "ts": int(time.time()), **datos}
    if isinstance(linea.get("salida"), str) and len(linea["salida"]) > RECORTE:
        linea["salida"] = linea["salida"][:RECORTE] + "…"
        linea["salida_recortada"] = True
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        with open(destino, "a", encoding="utf-8") as salida:
            salida.write(json.dumps(linea, ensure_ascii=False) + "\n")
            salida.flush()
            os.fsync(salida.fileno())
    except OSError as error:
        return f"No pude anotar el despacho en {destino}: {error}"
    return ""


def ultimos(cuantos=20, tarea_id=None):
    """Los últimos despachos, los de una tarea si se pide. Para el verbo `despachos`."""
    archivo = ruta()
    if not archivo.exists():
        return []
    lineas = []
    try:
        with open(archivo, encoding="utf-8") as abierto:
            for linea in abierto:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    datos = json.loads(linea)
                except ValueError:
                    continue  # una línea rota no se lleva por delante el resto del archivo
                if tarea_id and id_actual(datos.get("tarea")) != id_actual(tarea_id):
                    continue
                lineas.append(datos)
    except OSError:
        return []
    return lineas[-cuantos:]
