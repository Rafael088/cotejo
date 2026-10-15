"""Mandar la tarea a un cliente de IA que corre solo, sin que nadie lo vea: `claude -p`,
`opencode run`, `codex exec`, `gemini -p`.

Es el camino desatendido, y por eso **no es el defecto**: se pide. Sirve para un script, un
hook, algo que corre de madrugada, o un `maestro` que reparte las tareas de un proyecto; para el
trabajo normal están `agente` (lo hace el agente con el que estás hablando) y `sesion` (una
instancia que puedes abrir y dirigir).

Qué se lanza lo decide el `cliente` del modelo en el catálogo (`clientes.py`): una tarea de
`#agente/kimi-k2.7-code` va a `opencode run -m opencode-go/kimi-k2.7-code`, no a `claude`. Para
Claude, `--model` toma el alias (`opus`, `sonnet`, `haiku`) y no el id exacto: el alias sigue
apuntando al modelo vigente de su familia cuando Anthropic saca uno nuevo. El id exacto viaja
igual en el encargo y queda escrito en la bitácora.

`motores.headless.comando` y `argumentos_extra` siguen siendo los de Claude; los de otro cliente
van en `motores.headless.clientes.<cliente>` con las mismas dos claves.

Cada lanzamiento se aísla en su propio *scope* de systemd cuando se puede —`aislamiento.py` dice
cuándo y con qué tope de memoria—, para que un OOM de este headless no se lleve detrás al
maestro ni a otro headless que esté corriendo a la vez.
"""

import shutil
import subprocess
import time

from .. import aislamiento, clientes, motor


class ClaudeCLI(motor.Motor):
    nombre = "headless"
    LANZA = True

    def _ajustes_de(self, cliente):
        if cliente.nombre == "claude":
            return self.ajustes
        return (self.ajustes.get("clientes") or {}).get(cliente.nombre) or {}

    def argv(self, encargo):
        cliente = clientes.de(encargo.cliente)
        propios = self._ajustes_de(cliente)
        return cliente.argv_sin_interfaz(
            cliente.modelo_de(encargo.modelo, encargo.modelo_id), encargo.prompt,
            comando=propios.get("comando"), extra=propios.get("argumentos_extra") or ())

    def comprobar(self, encargo):
        try:
            comando = self.argv(encargo)
        except clientes.ClienteDesconocido as error:
            return (f"{error} Cambia el cliente del modelo con `cotejo modelos agregar`, o usa "
                    f"--motor agente y pásale el encargo tú a quien lo vaya a hacer.")
        if shutil.which(comando[0]) is None:
            return (f"No encontré «{comando[0]}» en esta máquina, y es el cliente que ejecuta "
                    f"{encargo.modelo}. Instálalo, o usa --motor agente para quedarte con el "
                    f"encargo y dárselo tú a quien lo vaya a hacer.")
        return ""

    def ejecutar(self, encargo):
        try:
            comando = self.argv(encargo)
        except clientes.ClienteDesconocido as error:
            return motor.Resultado(False, [], 127, ejecutado=False,
                                   error=f"{error} Usa --motor agente.")
        timeout = self.ajustes.get("timeout_seg", 1800)
        arranque = time.monotonic()
        if shutil.which(comando[0]) is None:
            # Antes de envolver con systemd-run: aislado, el que falta al arrancar no es
            # "systemd-run" (ese sí está, o no se habría envuelto) sino el cliente, y systemd-run
            # lo diría con su propio mensaje en inglés en vez del de aquí abajo.
            return motor.Resultado(
                False, comando, 127, ejecutado=False,
                error=f"No encontré «{comando[0]}» en esta máquina. Instálalo, o cambia "
                      f"motores.headless.comando en la config, o usa --motor agente "
                      f"para quedarte con el encargo y dárselo tú a quien lo vaya a hacer.")
        # Aislado en su propio scope de systemd si se puede (Linux, systemd de usuario): un OOM
        # de este headless no debería llevarse detrás al maestro ni a otro headless que corra a
        # la vez. `lanzar` es lo que de verdad se ejecuta; `comando` —el argv del cliente, sin el
        # prefijo de systemd-run— es lo que se anota y lo que cuenta en los mensajes de error,
        # porque `enrutador/procesos.vivo` compara contra eso (ver `enrutador/aislamiento.py`).
        lanzar = aislamiento.envolver(comando, self.ajustes, encargo.tarea_id)
        try:
            proceso = subprocess.Popen(
                lanzar, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                cwd=str(encargo.directorio) if encargo.directorio else None)
        except FileNotFoundError:
            return motor.Resultado(
                False, comando, 127, ejecutado=False,
                error=f"No encontré «{comando[0]}» en esta máquina. Instálalo, o cambia "
                      f"motores.headless.comando en la config, o usa --motor agente "
                      f"para quedarte con el encargo y dárselo tú a quien lo vaya a hacer.")
        # Anotado en cuanto existe, con el argv del cliente y no el de systemd-run: si este
        # proceso (o el que lo lanzó) muere sin volver, el pid es lo que deja a `revisar`
        # darse cuenta.
        if self.al_lanzar:
            self.al_lanzar(proceso.pid, comando)
        try:
            salida, error = proceso.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proceso.kill()
            proceso.communicate()
            return motor.Resultado(
                False, comando, 124, duracion_ms=int((time.monotonic() - arranque) * 1000),
                error=f"El modelo no terminó en {timeout}s.")
        return motor.Resultado(
            proceso.returncode == 0, comando, proceso.returncode,
            salida=(salida or "").strip(),
            error=(error or "").strip(),
            duracion_ms=int((time.monotonic() - arranque) * 1000))
