"""La pestaña Inicio (v1.3.0), sin GTK: saludo, titular y una tarjeta por proyecto.

Lo que se vigila es que el Inicio diga la verdad: el avance sale de las piezas de la
arquitectura y, sin piezas, dice «sin arquitectura todavía» en vez de inventarse un número;
lo que espera a la persona va primero; un proyecto recién creado (sin tareas) sale.
"""

import subprocess
import tempfile
import types
import unittest
from pathlib import Path

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

from tareas import almacen, resumen_inicio as ri

PIEZAS = """# Mapa

## Piezas

| Capa | Pieza | Qué es | Tecnología | Tareas |
| --- | --- | --- | --- | --- |
| ve | Horarios | La lista de turnos libres | HTML | t-uno |
| hace | Reservar | Aparta el turno | JS | t-dos |
| guarda | Turnos | Cada reserva | Sheets | t-tres |
"""


def tarea(ident, estado, columna=None):
    return types.SimpleNamespace(id=ident, estado=estado, columna=columna or estado)


def proyecto(nombre, tareas=(), hechas=()):
    return types.SimpleNamespace(nombre=nombre, tareas=list(tareas), hechas=list(hechas))


class FuenteFalsa:
    def __init__(self, carpetas=None):
        self.carpetas = carpetas or {}
        self.problema = None

    def carpeta_de(self, nombre):
        return self.carpetas.get(nombre)


class Saludo(unittest.TestCase):
    def test_segun_la_hora(self):
        self.assertEqual(ri.saludo(7), "Buenos días")
        self.assertEqual(ri.saludo(15), "Buenas tardes")
        self.assertEqual(ri.saludo(22), "Buenas noches")
        self.assertEqual(ri.saludo(2), "Buenas noches")


class Titular(unittest.TestCase):
    def test_sin_proyectos(self):
        self.assertEqual(ri.titular([]), "Todavía no tienes proyectos")

    def test_cuenta_proyectos_y_entregas_con_plurales(self):
        t = [ri.Tarjeta("A", por_comprobar=2), ri.Tarjeta("B"), ri.Tarjeta("C")]
        self.assertEqual(ri.titular(t), "Tienes 3 proyectos y 2 entregas por comprobar")
        self.assertEqual(ri.titular([ri.Tarjeta("A", por_comprobar=1)]),
                         "Tienes 1 proyecto y 1 entrega por comprobar")

    def test_todo_al_dia(self):
        self.assertEqual(ri.titular([ri.Tarjeta("A")]), "Tienes 1 proyecto, todo al día")

    def test_con_trabajo_pendiente_no_dice_todo_al_dia(self):
        # «Todo al día» con cuatro tareas sin terminar es justo lo que chocaba con
        # «0 de 4 piezas» en la tarjeta (v1.3.1).
        t = [ri.Tarjeta("A", sin_terminar=4)]
        self.assertEqual(ri.titular(t), "Tienes 1 proyecto y 4 tareas por hacer")
        self.assertEqual(ri.titular([ri.Tarjeta("A", sin_terminar=1)]),
                         "Tienes 1 proyecto y 1 tarea por hacer")
        # Lo que espera a la persona manda sobre lo que está por hacer.
        self.assertEqual(ri.titular([ri.Tarjeta("A", por_comprobar=1, sin_terminar=4)]),
                         "Tienes 1 proyecto y 1 entrega por comprobar")


class TarjetaDeProyecto(unittest.TestCase):
    def test_avance_en_piezas_hechas(self):
        p = proyecto("Faro", [tarea("a", "por-validar"), tarea("b", "pendiente")])
        piezas = [{"estado": "hecho"}, {"estado": "por-comprobar"}, {"estado": "falta"}]
        t = ri.tarjeta(p, "0.1.0", "Que reserven solos.\nY más.", piezas)
        self.assertEqual((t.piezas, t.piezas_hechas, t.por_comprobar, t.sin_terminar),
                         (3, 1, 1, 2))
        self.assertAlmostEqual(t.avance, 1 / 3)
        self.assertEqual(t.texto_avance, "0.1.0 · 1 de 3 piezas")
        self.assertEqual(t.texto_estado, "1 por comprobar")
        self.assertEqual(t.objetivo, "Que reserven solos.")

    def test_sin_piezas_lo_dice_y_no_inventa_avance(self):
        t = ri.tarjeta(proyecto("Faro", [tarea("a", "hecha")]), "0.2.0")
        self.assertFalse(t.con_arquitectura)
        self.assertIsNone(t.avance)
        self.assertEqual(t.texto_avance, "0.2.0 · sin arquitectura todavía")
        self.assertEqual(t.texto_estado, "al día")

    def test_el_chip_no_dice_al_dia_con_tareas_sin_terminar(self):
        t = ri.tarjeta(proyecto("Faro", [tarea("a", "pendiente"), tarea("b", "en-curso")]),
                       piezas=[{"estado": "falta"}] * 4)
        self.assertEqual(t.texto_avance, "0 de 4 piezas")
        self.assertEqual(t.texto_estado, "2 por hacer")
        # Solo cuando no queda nada se dice «al día».
        self.assertEqual(ri.tarjeta(proyecto("Faro", [tarea("a", "hecha")])).texto_estado,
                         "al día")

    def test_sin_version_solo_el_avance(self):
        t = ri.tarjeta(proyecto("Faro"), piezas=[{"estado": "hecho"}])
        self.assertEqual(t.texto_avance, "1 de 1 pieza")

    def test_lo_que_espera_va_primero(self):
        orden = ri.ordenar([ri.Tarjeta("A"), ri.Tarjeta("B", por_comprobar=1), ri.Tarjeta("C")])
        self.assertEqual([t.nombre for t in orden], ["B", "A", "C"])

    def test_columnas_de_con_las_hechas(self):
        p = proyecto("Faro", [tarea("t-uno", "pendiente")], [tarea("t-dos", "hecha")])
        self.assertEqual(ri.columnas_de(p), {"t-uno": "pendiente", "t-dos": "hecha"})


class ConRepo(unittest.TestCase):
    """`tarjetas` lee de verdad un repo con `.cotejo/`: versión, objetivo y piezas."""

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.repo = Path(temporal.name) / "faro"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.alm = almacen.Almacen(self.repo)
        entrada = self.alm.crear("proyecto", "faro")
        self.alm.reescribir(almacen.ID_PROYECTO, entrada.version,
                            texto="## Objetivo\n\nQue reserven solos.\n",
                            campos={"version": "0.1.0"})

    def test_proyecto_con_arquitectura(self):
        self.alm.crear("arquitectura", "Mapa", PIEZAS)
        p = proyecto("faro", [tarea("t-dos", "por-validar"), tarea("t-tres", "en-curso")],
                     [tarea("t-uno", "hecha")])
        [t] = ri.tarjetas([p], FuenteFalsa({"faro": self.repo}))
        self.assertEqual(t.version, "0.1.0")
        self.assertEqual(t.objetivo, "Que reserven solos.")
        self.assertEqual(t.estados, ["hecho", "por-comprobar", "en-curso"])
        self.assertEqual(t.texto_avance, "0.1.0 · 1 de 3 piezas")

    def test_recien_creado_sin_tareas_sale_igual(self):
        [t] = ri.tarjetas([proyecto("faro")], FuenteFalsa({"faro": self.repo}))
        self.assertEqual(t.texto_avance, "0.1.0 · sin arquitectura todavía")

    def test_sin_tareas_ni_almacen_no_sale(self):
        self.assertEqual(ri.tarjetas([proyecto("Suelto")], FuenteFalsa()), [])

    def test_un_almacen_que_falla_no_tumba_el_inicio(self):
        class Rota(FuenteFalsa):
            def carpeta_de(self, nombre):
                return "/no/existe/\x00rota"
        avisos = []
        [t] = ri.tarjetas([proyecto("Faro", [tarea("a", "pendiente")])], Rota(), avisos)
        self.assertEqual(t.texto_avance, "sin arquitectura todavía")


if __name__ == "__main__":
    unittest.main()
