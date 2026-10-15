"""El filtro de fechas de la columna Finalizada (CotejoBoard, v1.2.2 · cotejo-r3cs5t).

La lógica vive en `modelo.en_filtro_finalizada`, sin GTK y con la fecha de hoy inyectable, para
poder probarla sin pantalla: lo que hace CotejoBoard con ella —el botón, el menú, qué cuenta el
contador— es pintura encima de esto.
"""

import unittest
from datetime import date, timedelta

from tareas import modelo


class Ventanas(unittest.TestCase):
    HOY = "2026-10-06"

    def test_hoy_solo_deja_pasar_la_de_hoy(self):
        self.assertTrue(modelo.en_filtro_finalizada("2026-10-06", "hoy", self.HOY))
        self.assertFalse(modelo.en_filtro_finalizada("2026-10-05", "hoy", self.HOY))

    def test_7_dias_es_una_ventana_corrida_no_la_semana_de_calendario(self):
        # Hoy y los 6 anteriores: 7 fechas en total, caiga donde caiga la semana de calendario
        # — 2026-10-06 es martes, así que la ventana cruza a la semana anterior.
        hoy = date.fromisoformat(self.HOY)
        for hace in range(7):
            with self.subTest(hace=hace):
                fecha = (hoy - timedelta(days=hace)).isoformat()
                self.assertTrue(modelo.en_filtro_finalizada(fecha, "7-dias", self.HOY))
        octava = (hoy - timedelta(days=7)).isoformat()
        self.assertFalse(modelo.en_filtro_finalizada(octava, "7-dias", self.HOY))

    def test_30_dias_tambien_es_una_ventana_corrida(self):
        hoy = date.fromisoformat(self.HOY)
        self.assertTrue(modelo.en_filtro_finalizada((hoy - timedelta(days=29)).isoformat(),
                                                    "30-dias", self.HOY))
        self.assertFalse(modelo.en_filtro_finalizada((hoy - timedelta(days=30)).isoformat(),
                                                     "30-dias", self.HOY))

    def test_todas_no_filtra_nada(self):
        self.assertTrue(modelo.en_filtro_finalizada("2020-01-01", "todas", self.HOY))
        self.assertTrue(modelo.en_filtro_finalizada("2026-10-06", "todas", self.HOY))

    def test_una_fecha_futura_no_entra_en_ninguna_ventana_pero_si_en_todas(self):
        self.assertFalse(modelo.en_filtro_finalizada("2026-10-07", "hoy", self.HOY))
        self.assertFalse(modelo.en_filtro_finalizada("2026-10-07", "7-dias", self.HOY))
        self.assertTrue(modelo.en_filtro_finalizada("2026-10-07", "todas", self.HOY))


class SinFecha(unittest.TestCase):
    """Las hechas sin fecha de cierre: solo aparecen en «Todas»."""

    def test_sin_fecha_no_entra_en_ninguna_ventana(self):
        for clave in ("hoy", "7-dias", "30-dias"):
            with self.subTest(filtro=clave):
                self.assertFalse(modelo.en_filtro_finalizada(None, clave, "2026-10-06"))
                self.assertFalse(modelo.en_filtro_finalizada("", clave, "2026-10-06"))

    def test_sin_fecha_si_entra_en_todas(self):
        self.assertTrue(modelo.en_filtro_finalizada(None, "todas", "2026-10-06"))


class SinHoyInyectado(unittest.TestCase):
    def test_usa_la_fecha_local_si_no_se_le_da_una(self):
        hoy = modelo.hoy_local()
        self.assertTrue(modelo.en_filtro_finalizada(hoy, "hoy"))


class Defectos(unittest.TestCase):
    def test_un_filtro_que_no_existe_se_trata_como_el_de_por_defecto(self):
        self.assertEqual(
            modelo.en_filtro_finalizada("2026-10-06", "lo-que-sea", "2026-10-06"),
            modelo.en_filtro_finalizada("2026-10-06", modelo.FILTRO_FINALIZADA_DEFECTO,
                                       "2026-10-06"))

    def test_las_opciones_llevan_un_nombre_para_el_menu(self):
        claves = [clave for clave, _nombre, _dias in modelo.FILTROS_FINALIZADA]
        self.assertEqual(claves, ["hoy", "7-dias", "30-dias", "todas"])
        self.assertIn(modelo.FILTRO_FINALIZADA_DEFECTO, claves)


if __name__ == "__main__":
    unittest.main()
