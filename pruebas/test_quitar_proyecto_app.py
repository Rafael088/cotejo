"""El dialogo solo usa la papelera cuando la persona elige expresamente esa respuesta."""

import unittest
from unittest import mock

import apoyo  # noqa: F401

try:
    from tareas.app import mapa
except (ImportError, ValueError):
    mapa = None


@unittest.skipIf(mapa is None, "sin GTK no se puede importar la accion del mapa")
class RespuestaDelDialogo(unittest.TestCase):
    def tablero(self):
        tablero = mock.Mock()
        tablero.app.config_fuente = {"fuente": "repo", "repos": ["/repo"]}
        return tablero

    def test_cancelar_no_toca_ni_config_ni_carpeta(self):
        tablero = self.tablero()
        with mock.patch.object(mapa.proyectos, "quitar") as quitar, \
                mock.patch.object(mapa.proyectos, "mover_a_papelera") as papelera:
            mapa.PestanaMapa.al_responder_quitar_proyecto(
                tablero, None, "cancelar", "Uno", "/repo")
        quitar.assert_not_called()
        papelera.assert_not_called()

    def test_quitar_solo_conserva_la_carpeta(self):
        self._responder("quitar", mueve=False)

    def test_papelera_exige_la_respuesta_especifica(self):
        self._responder("papelera", mueve=True)

    def _responder(self, respuesta, mueve):
        tablero = self.tablero()
        datos = {"fuente": "repo", "fuentes": {"repo": {"repos": ["/repo"]}}}
        with mock.patch.object(mapa.proyectos, "ubicacion", return_value="repos"), \
                mock.patch.object(mapa.proyectos, "quitar") as quitar, \
                mock.patch.object(mapa.proyectos, "mover_a_papelera") as papelera, \
                mock.patch.object(mapa.configuracion, "cargar", return_value=datos):
            mapa.PestanaMapa.al_responder_quitar_proyecto(
                tablero, None, respuesta, "Uno", "/repo")
        quitar.assert_called_once_with("Uno", "/repo")
        self.assertEqual(papelera.call_count, int(mueve))
        tablero.app.refrescar.assert_called_once_with()
        tablero.app.vigilar.assert_called_once_with()
        tablero.ver_pestana.assert_called_once_with("inicio")


if __name__ == "__main__":
    unittest.main()
