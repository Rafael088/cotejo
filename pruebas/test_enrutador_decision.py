"""El orden de decisión. Es lo único que hace el enrutador, así que es lo más probado."""

import unittest

from enrutador import decision, niveles


def tarea(**cambios):
    """Una tarea como la devuelve la CLI de Cotejo."""
    base = {"id": "cotejo-a1b2", "texto": "Arreglar el parseo de los tags", "proyecto": "Cotejo",
            "estado": "pendiente", "agente": "", "dificultad": ""}
    base.update(cambios)
    return base


class Orden(unittest.TestCase):
    def test_el_override_gana_a_todo(self):
        d = decision.decidir("comprar el dominio", agente="opus", dificultad="facil",
                             override="haiku")
        self.assertEqual(d.nivel.modelo, "haiku")
        self.assertEqual(d.por, "override")

    def test_la_asignacion_gana_a_las_reglas(self):
        # Si una persona escribió #agente/opus en una tarea de comprar algo, sabrá por qué: su
        # decisión explícita gana. Es el único camino por el que una tarea «humana» sale a un
        # modelo, y pasa por haberlo escrito en la nota.
        d = decision.decidir("Comprar el dominio atlas.co", agente="opus")
        self.assertEqual(d.por, "asignacion")
        self.assertEqual(d.nivel.modelo, "opus")

    def test_asignada_a_persona_es_humano(self):
        d = decision.decidir("Refactorizar la capa Fuente", agente="persona")
        self.assertFalse(d.despachable)

    def test_el_veto_humano_gana_a_la_dificultad(self):
        # La razón de que este orden sea así: «#facil» dice «es corto», no «que lo haga un
        # modelo». Sin esta prioridad, «Comprar 3 tarjetas #facil» acaba en Haiku.
        d = decision.decidir("Comprar 3 tarjetas de muestra", dificultad="facil")
        self.assertEqual(d.por, "veto")
        self.assertFalse(d.despachable)
        self.assertEqual(d.regla, "compras")

    def test_la_dificultad_gana_a_las_reglas(self):
        d = decision.decidir("Arreglar el parseo de los tags", dificultad="dificil")
        self.assertEqual(d.por, "dificultad")
        self.assertEqual(d.nivel.clave, "n3")

    def test_un_agente_que_no_es_un_nivel_no_decide_pero_se_dice(self):
        d = decision.decidir("Arreglar el parseo", agente="ana")
        self.assertNotEqual(d.por, "asignacion")
        self.assertTrue(any("ana" in x for x in d.descartadas))

    def test_ante_la_duda_se_escala_nunca_se_abarata(self):
        d = decision.decidir("Ver qué pasa con eso de ayer")
        self.assertEqual(d.por, "defecto")
        self.assertEqual(d.nivel.modelo, "sonnet")
        self.assertEqual(d.confianza, "baja")

    def test_toda_decision_dice_por_que(self):
        for caso in [{}, {"agente": "opus"}, {"dificultad": "medio"},
                     {"texto_": "Comprar el dominio"}]:
            d = decision.decidir(caso.pop("texto_", "Arreglar el parseo"), **caso)
            self.assertTrue(d.razon, "una decisión sin razón no se puede discutir")

    def test_un_modelo_inventado_no_pasa_por_error_de_dedo(self):
        with self.assertRaises(ValueError):
            decision.decidir("lo que sea", override="gpt")


class DesdeTarea(unittest.TestCase):
    def test_lee_agente_y_dificultad_de_la_tarea_de_cotejo(self):
        d = decision.de_tarea(tarea(agente="haiku"))
        self.assertEqual(d.nivel.modelo, "haiku")
        d = decision.de_tarea(tarea(dificultad="dificil"))
        self.assertEqual(d.nivel.clave, "n3")


class Catalogo(unittest.TestCase):
    def test_el_nivel_humano_no_tiene_modelo(self):
        self.assertFalse(niveles.HUMANO_NIVEL.despachable)
        self.assertEqual(niveles.HUMANO_NIVEL.modelo, "")

    def test_los_alias_y_las_claves_resuelven_al_mismo_nivel(self):
        self.assertIs(niveles.por_nombre("opus"), niveles.por_nombre("n3"))

    def test_el_defecto_no_es_el_mas_barato(self):
        # Si algún día alguien "optimiza" el defecto a haiku, esta prueba lo dice.
        self.assertEqual(niveles.DEFECTO.modelo, "sonnet")

    def test_los_nombres_de_agente_son_los_que_usa_cotejo(self):
        # El nivel humano se llama «persona» porque es como se llama en `modelo.AGENTES`: quien
        # se asigna una tarea a sí mismo ya está diciendo «esto no es para un modelo».
        from tareas import modelo
        for agente in niveles.AGENTE_A_NIVEL:
            self.assertIn(agente, modelo.AGENTES)


if __name__ == "__main__":
    unittest.main()
