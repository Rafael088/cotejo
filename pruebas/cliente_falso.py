"""Un cliente de IA de mentira para las pruebas de lanzar desde el board: nunca llama a un modelo.

Escribe a su salida (que el lanzador manda al `.log` de la tarea) unas líneas como las de
`claude -p --output-format stream-json`, espera `FALSO_ESPERA` segundos y sale con
`FALSO_CODIGO`. Si hay `FALSO_ARGV`, deja ahí su argv y su carpeta, para que la prueba vea con
qué se lanzó. Con `FALSO_ESPERA_HASTA=<archivo>`, en vez de esperar un tiempo fijo se queda
vivo hasta que ese archivo exista: es el freno que usan las pruebas para verla «trabajando» sin
que eso dependa de que no haya acabado de salir.

Con `FALSO_ENTREGAR=<id>` hace lo que haría un agente que termina bien (cotejo-o253bs): un
commit en su carpeta y `cotejo entregar <id>` con el `cotejo` que le pusieron en el PATH, antes
de salir (y espera `FALSO_ESPERA_FIN` segundos más, vivo ya entregada).

Para el maestro (cotejo-9ybn1a): con `FALSO_CREAR=<texto>` y `FALSO_PROYECTO=<nombre>` corre
`cotejo crear` como lo haría el maestro al apuntar una tarea; `FALSO_RESPUESTA` es el texto de su
`result` (por defecto «Listo.»), y con `FALSO_PLANO=1` escribe solo ese texto, sin JSON, como
`codex exec` u `opencode run` en su salida.
"""

import json
import os
import subprocess
import sys
import time


def linea(datos):
    print(json.dumps(datos), flush=True)


def esperar():
    """Espera antes de terminar: `FALSO_ESPERA` segundos, o hasta que exista `FALSO_ESPERA_HASTA`
    (el freno de las pruebas: se queda viva todo lo que haga falta, sin depender del reloj)."""
    hasta = os.environ.get("FALSO_ESPERA_HASTA")
    if hasta:
        while not os.path.exists(hasta):
            time.sleep(0.01)
        return
    time.sleep(float(os.environ.get("FALSO_ESPERA", "0")))


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


def crear(texto, proyecto):
    hecho = subprocess.run(["cotejo", "crear", texto, "--proyecto", proyecto],
                           capture_output=True, text=True)
    if os.environ.get("FALSO_PLANO"):
        print(f"(corrí cotejo crear: código {hecho.returncode})", file=sys.stderr, flush=True)
    else:
        linea({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash",
             "input": {"command": f'cotejo crear "{texto}" --proyecto "{proyecto}"'}}]}})
    if hecho.returncode:
        print(hecho.stdout + hecho.stderr, file=sys.stderr, flush=True)


def main():
    if os.environ.get("FALSO_ARGV"):
        with open(os.environ["FALSO_ARGV"], "w", encoding="utf-8") as archivo:
            json.dump({"argv": sys.argv[1:], "cwd": os.getcwd(),
                       "path": os.environ.get("PATH", ""),
                       "pwd": os.environ.get("PWD", "")}, archivo)
    respuesta = os.environ.get("FALSO_RESPUESTA", "Listo.")
    if os.environ.get("FALSO_PLANO"):
        if os.environ.get("FALSO_CREAR"):
            crear(os.environ["FALSO_CREAR"], os.environ.get("FALSO_PROYECTO", ""))
        esperar()
        print(respuesta, flush=True)
        return int(os.environ.get("FALSO_CODIGO", "0"))
    linea({"type": "system", "subtype": "init", "model": "falso"})
    if os.environ.get("FALSO_CREAR"):
        crear(os.environ["FALSO_CREAR"], os.environ.get("FALSO_PROYECTO", ""))
    linea({"type": "assistant", "message": {"content": [
        {"type": "text", "text": "Voy a mirar el repo."},
        {"type": "tool_use", "name": "Bash", "input": {"command": "git status"}}]}})
    esperar()
    if os.environ.get("FALSO_ENTREGAR"):
        entregar(os.environ["FALSO_ENTREGAR"])
        time.sleep(float(os.environ.get("FALSO_ESPERA_FIN", "0")))
    linea({"type": "result", "subtype": "success", "is_error": False, "result": respuesta})
    return int(os.environ.get("FALSO_CODIGO", "0"))


if __name__ == "__main__":
    sys.exit(main())
