"""El motor que no ejecuta nada: dice qué habría corrido.

Es lo que hace que `--simular` sea de verdad gratis, y lo que deja probar el despacho entero
—decisión, permisos, encargo, bitácora— sin gastar un token ni tocar el vault. Un enrutador que
solo se puede probar gastando dinero se prueba poco.
"""

from .. import motor
from . import claude_cli as _headless, sesion as _sesion


class Simulado(motor.Motor):
    nombre = "simulado"

    def ejecutar(self, encargo):
        # Lo que se lanzaría de verdad: una sesión de Claude Code, o el cliente que ejecuta el
        # modelo si no es Claude.
        if (encargo.cliente or "claude") == "claude":
            comando = _sesion.Sesion(self.ajustes).argv(encargo)
        else:
            comando = _headless.ClaudeCLI(self.ajustes).argv(encargo)
        return motor.Resultado(
            True, comando, 0, ejecutado=False,
            salida=f"Simulado: no se ejecutó nada. Habría corrido {comando[0]} "
                   f"con el modelo {encargo.modelo}"
                   + (f" en {encargo.directorio}" if encargo.directorio else ""))
