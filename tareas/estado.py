"""Resumen de tareas para el widget de la barra de Omarchy.

Vive aparte de `tareas/app/` a propósito: no importa GTK, así que `tareas-obsidian --estado`
arranca en milisegundos y la barra puede llamarlo aunque la app no esté corriendo.
Mientras la app sí corre, es ella quien reescribe el archivo en cada cambio del vault.
"""

import json
import os
import sys
import time

from . import fuente as f, modelo, rutas

ARCHIVO = rutas.estado() / "estado.json"


# Versión del formato de este archivo. Lo leen el widget de la barra y quien quiera desde
# fuera, así que es un contrato: las claves se agregan, nunca se renombran ni se quitan. Si
# algún día hiciera falta romperlo, se sube el número y quien lee puede darse cuenta.
ESQUEMA = 1


def resumir(proyectos, problema=None, avisos=()):
    datos = modelo.resumen(proyectos)
    datos["esquema"] = ESQUEMA
    datos["actualizado"] = int(time.time())
    if avisos:
        # Lo que Cotejo no pudo leer viaja con el resumen: una nota que desaparece del board
        # sin explicación se ve igual que una nota sin tareas.
        datos["avisos"] = list(avisos)
    if problema:
        # La clave se llama "error" desde el esquema 1 y así se queda: lo que cambió es que el
        # texto lo pone la fuente, que es quien sabe qué le falta para poder trabajar.
        datos["error"] = problema
    return datos


def escribir(datos):
    """Reemplazo atómico: la barra vigila el archivo y no debe leerlo a medio escribir.

    Devuelve el motivo si no se pudo escribir, o None si salió bien. Antes se tragaba el
    error, y eso significaba que con el disco lleno la barra seguía enseñando el conteo de
    ayer para siempre, sin manera de saberlo.
    """
    try:
        ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
        temporal = ARCHIVO.with_name(f".{ARCHIVO.name}.tmp")
        temporal.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        os.replace(temporal, ARCHIVO)
    except OSError as error:
        return f"No pude escribir {ARCHIVO}: {error.strerror or error}"
    return None


def calcular():
    fuente = f.abrir()
    avisos = []
    proyectos = [] if fuente.problema else fuente.escanear(avisos=avisos)
    return resumir(proyectos, fuente.problema, avisos)


def main():
    datos = calcular()
    fallo = escribir(datos)
    print(json.dumps(datos, ensure_ascii=False))
    if fallo:
        # A la salida estándar va el resumen, que es lo que pidieron; el problema va aparte,
        # para que un script que canaliza la salida no se lo coma sin darse cuenta.
        print(fallo, file=sys.stderr)
        return 1
    return 0
