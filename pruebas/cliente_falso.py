"""Un cliente de IA de mentira para las pruebas de lanzar desde el board: nunca llama a un modelo.

Escribe a su salida (que el lanzador manda al `.log` de la tarea) unas líneas como las de
`claude -p --output-format stream-json`, espera `FALSO_ESPERA` segundos y sale con
`FALSO_CODIGO`. Si hay `FALSO_ARGV`, deja ahí su argv y su carpeta, para que la prueba vea con
qué se lanzó.

Con `FALSO_ENTREGAR=<id>` hace lo que haría un agente que termina bien (cotejo-o253bs): un
commit en su carpeta y `cotejo entregar <id>` con el `cotejo` que le pusieron en el PATH, antes
de salir (y espera `FALSO_ESPERA_FIN` segundos más, vivo ya entregada).
"""

import json
import os
import subprocess
import sys
import time


def linea(datos):
    print(json.dumps(datos), flush=True)


def entregar(tarea_id):
    git = ["git", "-c", "user.name=Falso", "-c", "user.email=f@f"]
    with open("arreglo.txt", "a", encoding="utf-8") as archivo:
        archivo.write("arreglado\n")
    subprocess.run(git + ["add", "arreglo.txt"], check=False, capture_output=True)
    subprocess.run(git + ["commit", "-q", "-m", "Arreglo del falso"], check=False,
                   capture_output=True)
    hecho = subprocess.run(["cotejo", "entregar", tarea_id, "--evidencia", "commit del falso",
                            "--resumen", "Arreglé el parseo."], capture_output=True, text=True)
    linea({"type": "assistant", "message": {"content": [
        {"type": "text", "text": f"Entregué (código {hecho.returncode})."}]}})


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
    if os.environ.get("FALSO_ENTREGAR"):
        entregar(os.environ["FALSO_ENTREGAR"])
        time.sleep(float(os.environ.get("FALSO_ESPERA_FIN", "0")))
    linea({"type": "result", "subtype": "success", "is_error": False, "result": "Listo."})
    return int(os.environ.get("FALSO_CODIGO", "0"))


if __name__ == "__main__":
    sys.exit(main())
