"""Cuántos despachos caben a la vez (cotejo-0d5qbo).

La cuenta se prueba con máquinas inventadas: lo que se vigila es que nunca reparta de más
—medir un agente solo puede subir lo que se supone que cuesta— y que diga siempre por qué.
"""

import unittest
from unittest import mock

from apoyo import PruebaDeEnrutador, proyecto

from enrutador import capacidad, verbos


def maquina(**cambios):
    foto = {"sistema": "linux", "cpus": 8, "carga": 1.0, "memoria_total_mb": 8000,
            "memoria_disponible_mb": 5000, "swap_total_mb": 0, "swap_libre_mb": 0,
            "agentes": []}
    foto.update(cambios)
    return foto


class Calcular(unittest.TestCase):
    def test_la_memoria_disponible_menos_la_reserva_entre_lo_que_ocupa_un_agente(self):
        # 5000 − 800 de reserva (10 % de 8000) = 4200 → 6 agentes de 700.
        calculo = capacidad.calcular(maquina())
        self.assertEqual((calculo["caben"], calculo["limita"]), (6, "memoria"))
        self.assertEqual(calculo["mb_por_agente_origen"], "por_defecto")
        self.assertIn("4200 MB", calculo["por_que"][0])

    def test_una_maquina_de_8_gb_con_poco_libre_deja_lanzar_uno(self):
        # Lo que encontró el dueño: 7,6 GB con ~2,7 GB disponibles no dejaban lanzar ni uno.
        calculo = capacidad.calcular(maquina(memoria_total_mb=7625, memoria_disponible_mb=1700))
        self.assertGreaterEqual(calculo["caben"], 1)

    def test_la_reserva_crece_con_la_maquina(self):
        calculo = capacidad.calcular(maquina(memoria_total_mb=64000,
                                             memoria_disponible_mb=40000))
        self.assertEqual(calculo["reserva_mb"], 6400)

    def test_el_swap_cuenta_solo_en_parte(self):
        sin = capacidad.calcular(maquina())["caben"]
        con = capacidad.calcular(maquina(swap_libre_mb=8000))["caben"]
        self.assertEqual(con - sin, 2)   # 8000 × 0,25 = 2000 → dos más de 700

    def test_medir_un_agente_pequeño_no_abarata_la_cuenta(self):
        # Uno en reposo ocupa menos que trabajando: medirlo no puede repartir de más.
        calculo = capacidad.calcular(maquina(agentes=[{"pid": 1, "programa": "claude",
                                                      "mb": 300}]))
        self.assertEqual(calculo["mb_por_agente"], capacidad.MB_POR_AGENTE)
        self.assertEqual(calculo["caben"], 6)

    def test_medir_uno_grande_la_sube(self):
        calculo = capacidad.calcular(maquina(agentes=[{"pid": 1, "programa": "claude",
                                                      "mb": 3000}]))
        self.assertEqual((calculo["mb_por_agente"], calculo["mb_por_agente_origen"]),
                         (3000, "medido"))
        self.assertEqual(calculo["caben"], 1)

    def test_las_sesiones_de_la_persona_no_suben_la_cuenta_ni_cuentan(self):
        # Una sesión interactiva de 3000 MB (propio False) ya está restada de lo disponible.
        sesion = {"pid": 1, "programa": "claude", "mb": 3000, "propio": False}
        suyo = {"pid": 2, "programa": "claude", "mb": 550, "propio": True}
        calculo = capacidad.calcular(maquina(agentes=[sesion, suyo]))
        self.assertEqual((calculo["mb_por_agente"], calculo["mb_por_agente_origen"]),
                         (capacidad.MB_POR_AGENTE, "por_defecto"))
        self.assertEqual(capacidad.en_curso([sesion, suyo]), [suyo])
        # Sin distinguir quién los lanzó, cuentan todos (como antes).
        self.assertEqual(len(capacidad.en_curso([{"pid": 1, "mb": 1}])), 1)

    def test_una_maquina_cargada_no_recibe_mas(self):
        calculo = capacidad.calcular(maquina(carga=9.5))
        self.assertEqual((calculo["caben"], calculo["limita"]), (0, "cpu"))

    def test_sin_memoria_disponible_no_cabe_ninguno(self):
        self.assertEqual(capacidad.calcular(maquina(memoria_disponible_mb=900))["caben"], 0)

    def test_la_config_pisa_los_supuestos(self):
        calculo = capacidad.calcular(maquina(), {"mb_por_agente": 500, "reserva_mb": 0,
                                                 "maximo": 3})
        self.assertEqual((calculo["caben"], calculo["limita"]), (3, "maximo"))
        self.assertEqual(calculo["mb_por_agente_origen"], "config")

    def test_lo_que_no_se_puede_leer_no_se_inventa(self):
        # Windows no tiene carga media; una plataforma rara puede no dar ni la memoria.
        solo_memoria = capacidad.calcular(maquina(carga=None))
        self.assertNotIn("cpu", solo_memoria["limites"])
        nada = capacidad.calcular(maquina(carga=None, memoria_disponible_mb=None,
                                          memoria_total_mb=None))
        self.assertIsNone(nada["caben"])
        self.assertIn("No pude leer la memoria", nada["por_que"][0])


class Agentes(unittest.TestCase):
    def test_cada_agente_suma_su_arbol_y_uno_dentro_de_otro_cuenta_aparte(self):
        # 10 = terminal; 20 = maestro (claude); 21 = sus pruebas; 30 = cotejo despachando;
        # 31 = el headless (claude) que lanzó, con 32, su compilación.
        procesos = {10: (1, 50, ""), 20: (10, 500, "claude"), 21: (20, 200, ""),
                    30: (20, 40, ""), 31: (30, 600, "claude"), 32: (31, 900, "")}
        self.assertEqual(capacidad.agentes_de(procesos),
                         [{"pid": 20, "programa": "claude", "mb": 740},
                          {"pid": 31, "programa": "claude", "mb": 1500}])

    def test_solo_son_propios_los_que_lanzo_cotejo_o_cuelgan_de_lo_que_lanzo(self):
        # 20 = sesión de la persona; 40 = envoltorio que lanzó Cotejo; 41 = su claude.
        procesos = {10: (1, 50, ""), 20: (10, 500, "claude"), 40: (1, 5, ""),
                    41: (40, 550, "claude")}
        self.assertEqual([(a["pid"], a["propio"]) for a in capacidad.agentes_de(procesos, {40})],
                         [(20, False), (41, True)])

    def test_en_esta_maquina_se_lee_algo_con_sentido(self):
        foto = capacidad.leer()
        self.assertGreaterEqual(foto["cpus"], 1)
        if foto["memoria_total_mb"] is not None:
            self.assertGreater(foto["memoria_total_mb"], 0)


class Verbo(PruebaDeEnrutador):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Primera #agente/sonnet ^cotejo-a",
            "- [ ] Segunda #agente/opus ^cotejo-b",
            "- [ ] Tercera #agente/haiku ^cotejo-c",
            "- [ ] Sin asignar, no entra ^cotejo-d",
            "- [ ] Comprar el dominio #agente/persona ^cotejo-e",
        ))

    def capacidad(self, foto, *extra):
        with mock.patch.object(capacidad, "leer", return_value=foto):
            codigo, datos = self.correr("capacidad", *extra)
        self.assertEqual(codigo, verbos.OK)
        return datos

    def test_parte_las_asignadas_entre_ahora_y_esperar(self):
        self.escribir_config({"capacidad": {"mb_por_agente": 1500, "reserva_mb": 1024}})
        datos = self.capacidad(maquina(), "--proyecto", "Uno")
        self.assertEqual(datos["caben"], 2)
        self.assertEqual([t["id"] for t in datos["ahora"]], ["cotejo-a", "cotejo-b"])
        self.assertEqual([t["id"] for t in datos["esperar"]], ["cotejo-c"])

    def test_si_no_cabe_ninguno_dice_que_no_despache(self):
        datos = self.capacidad(maquina(memoria_disponible_mb=500))
        self.assertEqual(datos["caben"], 0)
        self.assertIn("No despaches", datos["salida"])

    def test_los_supuestos_salen_de_la_config(self):
        self.escribir_config({"capacidad": {"maximo": 1}})
        self.assertEqual(self.capacidad(maquina())["limita"], "maximo")


if __name__ == "__main__":
    unittest.main()
