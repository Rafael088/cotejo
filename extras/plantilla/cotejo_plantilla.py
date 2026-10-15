#!/usr/bin/env python3
"""Plantilla de adaptador de Cotejo: el contrato entero, con un archivo JSON haciendo de app.

Para conectar Cotejo a una app nueva se copia esto y se cambian `leer()` y `guardar()` —y lo que
haga falta dentro de cada verbo— por llamadas a la API de esa app. Todo lo demás (los
subcomandos, la forma del JSON, cómo se contesta un error) es el contrato y no cambia.

El archivo tiene la forma:

    {"proyectos": [{"nombre": "Casa", "tareas": [
        {"id": "casa-1", "texto": "Pintar la reja", "estado": "pendiente",
         "agente": "", "dificultad": "", "hecha": false}]}]}

Se registra así, y desde ahí la usa todo Cotejo —la CLI, el board, la barra—:

    cotejo fuentes agregar demo --comando "python3 extras/plantilla/cotejo_plantilla.py" \\
        --param archivo=/ruta/tareas.json

Solo usa la librería estándar. Los parámetros de la fuente llegan en `COTEJO_FUENTE_CONFIG`.
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ESQUEMA = 1
ESTADOS = ("pendiente", "en-curso", "por-validar")


class Fallo(Exception):
    def __init__(self, mensaje, tipo="fuente", salida="", reintentable=False):
        super().__init__(mensaje)
        self.datos = {"esquema": ESQUEMA, "error": mensaje, "tipo": tipo, "salida": salida,
                      "reintentable": reintentable}


def config():
    try:
        # FOCO_FUENTE_CONFIG es el nombre de antes: así la leen los adaptadores ya escritos.
        crudo = os.environ.get("COTEJO_FUENTE_CONFIG") or os.environ.get("FOCO_FUENTE_CONFIG")
        return json.loads(crudo or "{}")
    except ValueError as error:
        raise Fallo(f"COTEJO_FUENTE_CONFIG no es JSON: {error}") from error


def ruta():
    archivo = config().get("archivo")
    if not archivo:
        raise Fallo("Falta el parámetro «archivo»",
                    salida="Regístrala con --param archivo=/ruta/tareas.json")
    return Path(archivo).expanduser()


# --- la «app» -------------------------------------------------------------------
# En un adaptador de verdad, estas dos son la API: una consulta y una actualización.


def leer():
    try:
        texto = ruta().read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise Fallo(f"No existe {ruta()}", salida="Crea el archivo o corrige «archivo».") from error
    return json.loads(texto), len(texto)


def guardar(datos):
    destino = ruta()
    descriptor, temporal = tempfile.mkstemp(dir=destino.parent, suffix=".json")
    with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=2)
    os.replace(temporal, destino)


# --- el contrato ----------------------------------------------------------------


def buscar(datos, ref):
    for proyecto in datos["proyectos"]:
        for tarea in proyecto["tareas"]:
            if tarea["id"] == ref:
                return proyecto, tarea
    raise Fallo(f"No hay ninguna tarea {ref}", tipo="cambiada",
                salida="Vuelve a pedir `tareas`.")


def comprobar(tarea, esperado):
    """Escribir verificado: si alguien la tocó desde que Cotejo la leyó, no se escribe."""
    for clave in ("texto", "estado", "agente", "hecha"):
        if clave in esperado and tarea.get(clave, "" if clave != "hecha" else False) != esperado[clave]:
            raise Fallo(f"La tarea {tarea['id']} cambió ({clave})", tipo="cambiada")


def cambiar(args, **cambios):
    datos, _ = leer()
    _, tarea = buscar(datos, args.ref)
    comprobar(tarea, json.loads(args.esperado or "{}"))
    if all(tarea.get(k) == v for k, v in cambios.items()):
        return {"esquema": ESQUEMA, "cambio": False, "tarea": tarea}
    tarea.update(cambios)
    guardar(datos)
    return {"esquema": ESQUEMA, "cambio": True, "tarea": tarea}


def cmd_doctor(args):
    datos, _ = leer()
    return {"esquema": ESQUEMA, "ok": True,
            "mensaje": f"{len(datos['proyectos'])} proyectos en {ruta()}"}


def cmd_protocolo(args):
    return {"esquema": ESQUEMA, "nombre": "plantilla", "lectura": True, "escritura": True,
            "verbos": ["escanear", "estado", "agente", "marcar", "crear"],
            "parametros": {"archivo": "El JSON con los proyectos y sus tareas."},
            "ejemplo": {"tipo": "externa", "comando": "cotejo-plantilla",
                        "archivo": "~/tareas.json"}}


def cmd_escanear(args):
    datos, peso = leer()
    for proyecto in datos["proyectos"]:
        if not args.hechas:
            proyecto["tareas"] = [t for t in proyecto["tareas"] if not t.get("hecha")]
    return {"esquema": ESQUEMA, "proyectos": datos["proyectos"], "avisos": [], "leido": peso}


def cmd_estado(args):
    if args.nuevo not in ESTADOS:
        raise Fallo(f"Estado desconocido: {args.nuevo}")
    return cambiar(args, estado=args.nuevo)


def cmd_agente(args):
    return cambiar(args, agente=args.quien)


def cmd_marcar(args):
    return cambiar(args, hecha=args.hecha)


def cmd_crear(args):
    datos, _ = leer()
    proyecto = next((p for p in datos["proyectos"] if p["nombre"] == args.proyecto), None)
    if proyecto is None:
        raise Fallo(f"No hay un proyecto «{args.proyecto}»", tipo="no-se-crea-aqui")
    numero = 1 + sum(len(p["tareas"]) for p in datos["proyectos"])
    tarea = {"id": f"{proyecto['nombre'].lower()}-{numero}", "texto": args.texto,
             "estado": "pendiente", "agente": "", "dificultad": args.dificultad or "",
             "hecha": False}
    if args.version:
        tarea["version"] = args.version
    proyecto["tareas"].append(tarea)
    guardar(datos)
    return {"esquema": ESQUEMA, "cambio": True, "tarea": tarea}


def analizador():
    partes = argparse.ArgumentParser(prog="cotejo-plantilla")
    sub = partes.add_subparsers(dest="verbo", required=True)
    sub.add_parser("doctor").set_defaults(funcion=cmd_doctor)
    sub.add_parser("protocolo").set_defaults(funcion=cmd_protocolo)
    escanear = sub.add_parser("escanear")
    escanear.add_argument("--hechas", action="store_true")
    escanear.set_defaults(funcion=cmd_escanear)
    for verbo, funcion, valor in (("estado", cmd_estado, "nuevo"), ("agente", cmd_agente, "quien")):
        uno = sub.add_parser(verbo)
        uno.add_argument("ref")
        uno.add_argument(valor)
        uno.add_argument("--esperado")
        uno.set_defaults(funcion=funcion)
    marcar = sub.add_parser("marcar")
    marcar.add_argument("ref")
    marcar.add_argument("--hecha", action="store_true")
    marcar.add_argument("--pendiente", dest="hecha", action="store_false")
    marcar.add_argument("--esperado")
    marcar.set_defaults(funcion=cmd_marcar)
    crear = sub.add_parser("crear")
    crear.add_argument("--proyecto", required=True)
    crear.add_argument("--proyecto-ref")
    crear.add_argument("--texto", required=True)
    crear.add_argument("--dificultad")
    crear.add_argument("--version")
    crear.set_defaults(funcion=cmd_crear)
    return partes


def main():
    args = analizador().parse_args()
    try:
        salida, codigo = args.funcion(args), 0
    except Fallo as fallo:
        salida, codigo = fallo.datos, 3
    json.dump(salida, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
