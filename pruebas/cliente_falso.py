"""Un cliente de IA de mentira para las pruebas de lanzar desde el board: nunca llama a un modelo.

Escribe a su salida (que el lanzador manda al `.log` de la tarea) unas líneas como las de
`claude -p --output-format stream-json`, espera `FALSO_ESPERA` segundos y sale con
`FALSO_CODIGO`. Si hay `FALSO_ARGV`, deja ahí su argv y su carpeta, para que la prueba vea con
qué se lanzó.
"""

import json
import os
import sys
import time


def linea(datos):
    print(json.dumps(datos), flush=True)


def main():
    if os.environ.get("FALSO_ARGV"):
        with open(os.environ["FALSO_ARGV"], "w", encoding="utf-8") as archivo:
            json.dump({"argv": sys.argv[1:], "cwd": os.getcwd(),
                       "path": os.environ.get("PATH", ""),
                       "pwd": os.environ.get("PWD", "")}, archivo)
    linea({"type": "system", "subtype": "init", "model": "falso"})
    linea({"type": "assistant", "message": {"content": [
        {"type": "text", "text": "Voy a mirar el repo."},
        {"type": "tool_use", "name": "Bash", "input": {"command": "git status"}}]}})
    time.sleep(float(os.environ.get("FALSO_ESPERA", "0")))
    linea({"type": "result", "subtype": "success", "is_error": False, "result": "Listo."})
    return int(os.environ.get("FALSO_CODIGO", "0"))


if __name__ == "__main__":
    sys.exit(main())
