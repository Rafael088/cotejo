"""El dot es opcional (v1.2.4 G): `"dot": true` en la config lo enciende, y sin la clave el board
no crea nada de él. La config se lee sin GTK; el board de verdad, con GTK y pantalla (si no,
se salta). Con GTK se espera a la condición, no al reloj."""

import json
import os
import unittest
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del proyecto en el path)

from tareas import configuracion
from test_presencia import HAY_GTK, ConBoardDot, girar


class LaClave(apoyo.PruebaConVault):
    def con_config(self, datos):
        donde = self.vault / "config.json"
        donde.write_text(json.dumps(datos), encoding="utf-8")
        entorno = mock.patch.dict(os.environ, {"COTEJO_CONFIG": str(donde)})
        entorno.start()
        self.addCleanup(entorno.stop)

    def test_sin_la_clave_esta_apagado(self):
        self.assertFalse(configuracion.dot_activo({}))
        self.assertFalse(configuracion.dot_activo({"dot": False}))

    def test_solo_true_lo_enciende(self):
        self.assertTrue(configuracion.dot_activo({"dot": True}))
        for raro in ("true", 1, None, "si"):
            self.assertFalse(configuracion.dot_activo({"dot": raro}))

    def test_validar_acepta_el_booleano_y_regaña_lo_demas(self):
        for valor, errores in ((True, 0), (False, 0), ("true", 1), (1, 1)):
            self.con_config({"dot": valor})
            malos, _avisos = configuracion.validar({"obsidian"})
            self.assertEqual(len([e for e in malos if "«dot»" in e]), errores, valor)

    def test_la_migracion_no_pierde_la_clave(self):
        self.assertEqual(configuracion.migrar({"vault": "/v", "dot": True})["dot"], True)


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se arma el board")
class SinElDot(ConBoardDot):
    dot_encendido = False

    def hijos(self):
        hijo, cuenta = self.board.encima.get_first_child(), []
        while hijo is not None:
            cuenta.append(hijo)
            hijo = hijo.get_next_sibling()
        return cuenta

    def escribir(self, datos):
        # Como la CLI: un archivo nuevo que reemplaza al viejo.
        temporal = self.config.with_suffix(".tmp")
        temporal.write_text(json.dumps(datos), encoding="utf-8")
        temporal.replace(self.config)

    def test_por_defecto_no_hay_dot_ni_overlay_que_tape_un_clic(self):
        b = self.board
        girar(600)
        self.assertIsNone(b.dot)
        self.assertIsNone(b.presencia)
        self.assertEqual(len(self.hijos()), 1)      # solo el cuerpo del board
        self.assertEqual((b.dot_tick, b.dot_fin_momento, b.dot_fin_entrada), (0, 0, 0))
        self.assertEqual(b.dot_conexiones, [])
        b.actualizar_dot()
        b.entrar_dot()
        self.assertIsNone(b.dot)

    def test_cambiar_de_tema_sin_dot_pone_el_esquema_de_adwaita(self):
        # Con el dot apagado, `aplicar_tema` fallaba antes de cambiar el esquema: el board
        # pasaba a claro y los diálogos y avisos de Adwaita se quedaban en oscuro.
        from gi.repository import Adw
        girar(600)
        estilo = Adw.StyleManager.get_default()
        for ident, esquema in (("claro", Adw.ColorScheme.FORCE_LIGHT),
                               ("oscuro", Adw.ColorScheme.FORCE_DARK)):
            self.assertIsNone(self.app.aplicar_tema(ident))
            self.assertEqual(estilo.get_color_scheme(), esquema, ident)

    def test_encenderlo_en_caliente_lo_crea_y_apagarlo_lo_destruye_entero(self):
        b = self.board
        self.escribir({"dot": True})
        self.assertTrue(girar(5000, hasta=lambda: b.dot is not None and b.dot_entrado))
        self.assertIs(b.dot.get_parent(), b.encima)
        self.assertFalse(b.dot.get_can_target())
        self.assertEqual(len(self.hijos()), 2)
        self.assertTrue(girar(3000, hasta=lambda: b.dot.get_mapped()))

        self.escribir({"dot": False})
        self.assertTrue(girar(5000, hasta=lambda: b.dot is None))
        self.assertEqual(len(self.hijos()), 1)
        self.assertIsNone(b.presencia)
        self.assertEqual((b.dot_tick, b.dot_fin_momento, b.dot_fin_entrada), (0, 0, 0))
        self.assertEqual(b.dot_conexiones, [])
        self.assertFalse(b.dot_entrado)
        # Y el board sigue pintando sin él.
        b.pintar()

    def test_un_valor_que_no_es_booleano_lo_deja_apagado(self):
        self.escribir({"dot": "true"})
        girar(900)
        self.assertIsNone(self.board.dot)


if __name__ == "__main__":
    unittest.main()
