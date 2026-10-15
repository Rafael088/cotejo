#!/usr/bin/env python3
"""Un adaptador de Notion mínimo, solo para `test_nucleo_sin_gtk.py`.

No habla con ninguna API ni con la red: contesta siempre el mismo proyecto con una tarea, para
que `cotejo importar notion` tenga algo que traer en la prueba de humo que corre toda la CLI
sin GTK. No es un doble del adaptador de verdad —ese vive en `extras/notion/cotejo_notion.py`
y lo prueba `test_notion.py` contra el servidor HTTP de `notion_falso.py`—; esto es lo mínimo
del contrato de `tareas/fuentes/externa.py` para que una sola invocación de ensayo funcione.
"""

import argparse
import json
import sys

ESQUEMA = 1


def main():
    partes = argparse.ArgumentParser(prog="notion-minimo")
    sub = partes.add_subparsers(dest="verbo", required=True)
    sub.add_parser("doctor")
    sub.add_parser("protocolo")
    escanear = sub.add_parser("escanear")
    escanear.add_argument("--hechas", action="store_true")
    args = partes.parse_args()

    if args.verbo == "doctor":
        salida = {"esquema": ESQUEMA, "ok": True, "mensaje": "Conectado a Notion (de mentira)"}
    elif args.verbo == "protocolo":
        salida = {"esquema": ESQUEMA, "nombre": "notion-minimo", "lectura": True,
                  "escritura": False, "verbos": ["doctor", "escanear"], "parametros": {}}
    else:
        salida = {"esquema": ESQUEMA, "avisos": [], "leido": 42, "proyectos": [{
            "nombre": "Uno", "donde": "Notion · Tareas", "url": "https://notion.so/base",
            "tareas": [{"id": "notion-tar1", "ref": "tar1", "texto": "Importada de Notion",
                       "estado": "pendiente", "agente": "", "dificultad": "", "hecha": False,
                       "url": "https://notion.so/tar1"}]}]}
    json.dump(salida, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
