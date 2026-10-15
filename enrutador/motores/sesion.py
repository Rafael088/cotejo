"""Abrir una instancia de Claude Code de verdad, con su modelo puesto: `claude --bg --model`.

Es el motor del caso «hazme dos tareas de este proyecto»: una instancia maestra despacha varias
tareas, cada una a una instancia propia con el modelo que le toca, y las instancias trabajan a
la vez. No es la API ni es `claude -p`: son sesiones completas, con sus herramientas y sus
permisos, que se pueden abrir y dirigir con `claude attach <id>`.

Lo único que se devuelve es el identificador corto que imprime `claude --bg`. A propósito no se
lee la salida de la instancia: `claude logs` devuelve el volcado del terminal con sus códigos de
color, que no es un formato para leer con un programa. **El resultado del trabajo no se mira
aquí, se mira en Cotejo**: la instancia entrega su tarea con evidencia y aparece en la columna «Para
comprobar». Ese es el canal, y por eso no hace falta parsear nada.
"""

import re
import shutil
import subprocess
import time

from .. import motor

# `claude --bg` imprime «backgrounded · <id>» **con códigos de color**, y esos códigos llevan
# dígitos dentro (`ESC[36m`). Buscar el id sin quitarlos antes no falla a medias: engancha el
# «36» del color. Así que primero se limpia y después se busca.
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
ID = re.compile(r"backgrounded\W+([0-9a-f]{6,})")


def identificador(texto):
    """El id corto de la sesión recién abierta, o "" si no se reconoce la salida."""
    encontrado = ID.search(ANSI.sub("", texto))
    return encontrado.group(1) if encontrado else ""


class Sesion(motor.Motor):
    nombre = "sesion"
    LANZA = True

    def argv(self, encargo):
        comando = list(self.ajustes.get("comando") or ["claude"])
        return comando + ["--bg", "--model", encargo.modelo] + \
            list(self.ajustes.get("argumentos_extra") or []) + [encargo.prompt]

    def comprobar(self, encargo):
        # `--bg` y `attach` son de Claude Code: ningún otro cliente abre una instancia que se
        # pueda dirigir después, así que para ellos el camino es `headless`.
        if (encargo.cliente or "claude") != "claude":
            return (f"`--motor sesion` solo abre instancias de Claude Code (`claude --bg`), y "
                    f"{encargo.modelo} lo ejecuta {encargo.cliente}. Usa --motor headless, que "
                    f"lo lanza con su cliente, o --motor agente.")
        # Igual que headless: sin el cliente, tomarla primero dejaba la tarea «Haciéndola» y
        # respondía «Instancia abierta» con ok:false (cotejo-fyj565).
        programa = self.argv(encargo)[0]
        if shutil.which(programa) is None:
            return (f"No encontré «{programa}» en esta máquina, y `--motor sesion` lo necesita "
                    f"para abrir la instancia de {encargo.modelo}. Instálalo, o usa --motor "
                    f"agente para quedarte con el encargo y dárselo tú a quien lo vaya a hacer.")
        return ""

    def ejecutar(self, encargo):
        problema = self.comprobar(encargo)
        if problema:
            return motor.Resultado(False, [], 2, ejecutado=False, error=problema)
        comando = self.argv(encargo)
        arranque = time.monotonic()
        try:
            hecho = subprocess.run(
                comando, capture_output=True, text=True,
                timeout=self.ajustes.get("timeout_seg", 120),
                cwd=str(encargo.directorio) if encargo.directorio else None)
        except FileNotFoundError:
            return motor.Resultado(
                False, comando, 127, ejecutado=False,
                error=f"No encontré «{comando[0]}» en esta máquina. Si no vas a abrir "
                      f"instancias, usa --motor agente y hazla tú.")
        except subprocess.TimeoutExpired:
            return motor.Resultado(False, comando, 124, ejecutado=False,
                                   error="`claude --bg` no volvió. Debería tardar un segundo: "
                                         "mira `claude agents --json` por si quedó arrancada.")

        texto = ((hecho.stdout or "") + (hecho.stderr or "")).strip()
        instancia = identificador(texto)
        if hecho.returncode != 0 or not instancia:
            return motor.Resultado(
                False, comando, hecho.returncode or 1, salida=texto[:600],
                error="No pude arrancar la instancia ni leer su identificador.",
                duracion_ms=int((time.monotonic() - arranque) * 1000))

        return motor.Resultado(
            True, comando, 0, ejecutado=True,
            duracion_ms=int((time.monotonic() - arranque) * 1000),
            salida=f"Instancia {instancia} trabajando en {encargo.modelo}. "
                   f"Ábrela con `claude attach {instancia}`; cuando entregue, la verás en "
                   f"CotejoBoard.")
