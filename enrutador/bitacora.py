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

# Junto a la bitácora de Cotejo y por el mismo camino: un solo sitio donde mirar qué pasó.
ARCHIVO = rutas.estado() / "despachos.jsonl"


def anotar(**datos):
    """Agrega una línea. Si no se puede escribir, lo dice y no rompe el despacho.

    Un fallo al anotar no puede tumbar un despacho que ya ocurrió: la tarea está tomada y el
    modelo está trabajando. Pero tampoco puede desaparecer en silencio, así que devuelve el
    problema para que el verbo lo ponga en `avisos`.
    """
    linea = {"esquema": ESQUEMA, "ts": int(time.time()), **datos}
    if isinstance(linea.get("salida"), str) and len(linea["salida"]) > RECORTE:
        linea["salida"] = linea["salida"][:RECORTE] + "…"
        linea["salida_recortada"] = True
    try:
        ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
        with open(ARCHIVO, "a", encoding="utf-8") as archivo:
            archivo.write(json.dumps(linea, ensure_ascii=False) + "\n")
            archivo.flush()
            os.fsync(archivo.fileno())
    except OSError as error:
        return f"No pude anotar el despacho en {ARCHIVO}: {error}"
    return ""


def ultimos(cuantos=20, tarea_id=None):
    """Los últimos despachos, los de una tarea si se pide. Para el verbo `despachos`."""
    if not ARCHIVO.exists():
        return []
    lineas = []
    try:
        with open(ARCHIVO, encoding="utf-8") as archivo:
            for linea in archivo:
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
