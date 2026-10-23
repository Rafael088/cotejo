"""El mapa del proyecto sin GTK (v1.3.0, cotejo-p86sa9).

Sobre un proyecto de prueba en un tmp: una arquitectura con piezas en las cuatro capas y en los
cuatro estados, y tareas enlazadas a ellas en `.cotejo/tareas.md`. El mapa agrupa por capa en
el orden del prototipo con el estado de cada pieza; la ficha trae la frase, las tareas con su
columna y la tecnología; y un proyecto sin arquitectura (o sin `.cotejo/`) da un mapa vacío que
lo dice, sin inventar nada. La pantalla se prueba con GTK en `test_pantalla_mapa.py`.
"""

import tempfile
import unittest
from pathlib import Path

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

from tareas import almacen, constelacion, mapa, modelo

TAREAS = (
    "# barberia\n\n"
    "- [ ] Pantalla de horarios libres #v0.1.0 #por-validar ^cotejo-aaa111\n"
    "- [ ] Formulario de reserva #v0.1.0 #en-curso #agente/sonnet ^cotejo-bbb222\n"
    "- [ ] Tu vista del día #v0.1.0 ^cotejo-ccc333\n"
    "- [x] Calcular huecos #v0.1.0 ^cotejo-ddd444\n"
    "- [x] Crear la hoja #v0.1.0 #agente/persona ^cotejo-eee555\n"
    "- [ ] Guardar la reserva en la hoja #v0.1.0 #por-validar ^cotejo-fff666\n"
)
PIEZAS = """# Mapa inicial

Cómo está hecha la barbería.

## Piezas

| Capa | Pieza | Qué es | Tecnología | Tareas |
| --- | --- | --- | --- | --- |
| ve | Horarios libres | Los turnos que todavía se pueden tomar | HTML + JS | cotejo-aaa111 |
| ve | Formulario de reserva | Donde el cliente deja nombre y teléfono | web/reservar.html | cotejo-bbb222 |
| ve | Mis turnos del día | Quién viene hoy y a qué hora | | cotejo-ccc333 |
| hace | Calcular huecos | Deja solo los turnos libres | huecos.js | cotejo-ddd444 |
| hace | Avisar | Un recordatorio por WhatsApp | | |
| guarda | Turnos | Cada reserva: día, hora y nombre | Google Sheets | cotejo-eee555 |
| conecta | Hoja de Google | Donde viven los turnos | Sheets API | cotejo-fff666, cotejo-zzz999 |
"""


def proyecto_de_prueba(raiz, con_arquitectura=True):
    carpeta = Path(raiz) / "barberia"
    (carpeta / ".git").mkdir(parents=True)
    (carpeta / ".cotejo").mkdir()
    (carpeta / ".cotejo" / "tareas.md").write_text(TAREAS, encoding="utf-8")
    alm = almacen.Almacen(carpeta)
    alm.crear("proyecto", "barberia", "## Objetivo\n\nReservas.\n")
    if con_arquitectura:
        alm.crear("arquitectura", "Mapa inicial", PIEZAS)
    return carpeta


class Puro(unittest.TestCase):
    def test_las_cuatro_capas_salen_siempre_en_el_orden_del_prototipo(self):
        m = mapa.armar("x", [])
        self.assertEqual([c.clave for c in m.capas], ["ve", "hace", "guarda", "conecta"])
        self.assertEqual([c.titulo for c in m.capas],
                         ["Qué ve la gente", "Qué hace", "Qué guarda", "Con qué se conecta"])
        self.assertFalse(m.con_arquitectura)
        self.assertEqual(m.texto_avance, "sin arquitectura todavía")
        self.assertIsNone(m.primera())

    def test_los_estados_y_la_leyenda_son_los_de_la_constelacion(self):
        self.assertEqual([e for e, _ in mapa.leyenda()], list(constelacion.ESTADOS_LEYENDA))
        for estado, nombre in constelacion.NOMBRES.items():
            self.assertEqual(mapa.nombre_estado(estado), nombre)
        # Un estado que no se conoce se dice como «Falta», nunca como lo que espera comprobación.
        self.assertEqual(mapa.nombre_estado("raro"), "Falta")

    def test_ficha_sin_tecnologia_ni_tareas(self):
        pieza = {"id": "avisar", "capa": "hace", "nombre": "Avisar", "frase": "Recordatorio",
                 "tecnologia": "", "tareas": [], "estado": "falta"}
        f = mapa.ficha(mapa.armar("x", [pieza]), pieza)
        self.assertEqual(f.texto_tecnologia, "Si programas: todavía sin elegir")
        self.assertEqual(f.tareas, [])
        self.assertFalse(f.verde)


class DeUnRepo(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.carpeta = proyecto_de_prueba(temporal.name)

    def test_agrupa_por_capa_con_el_estado_de_cada_pieza(self):
        m = mapa.leer("barberia", self.carpeta)
        por_capa = {c.clave: [(p["nombre"], p["estado"]) for p in c.piezas] for c in m.capas}
        self.assertEqual(por_capa, {
            "ve": [("Horarios libres", "por-comprobar"), ("Formulario de reserva", "en-curso"),
                   ("Mis turnos del día", "falta")],
            "hace": [("Calcular huecos", "hecho"), ("Avisar", "falta")],
            "guarda": [("Turnos", "hecho")],
            "conecta": [("Hoja de Google", "por-comprobar")],
        })
        self.assertEqual(m.texto_avance, "2 de 7 piezas")
        self.assertEqual(m.titulo, "Cómo está hecho barberia")
        self.assertEqual(m.ruta, "barberia  ›  Mapa")
        self.assertTrue(m.eyebrow.startswith("MAPA DEL PROYECTO"))
        # Al abrir se enseña primero lo que espera a la persona.
        self.assertEqual(m.primera()["nombre"], "Horarios libres")

    def test_la_ficha_trae_frase_tareas_con_su_columna_y_tecnologia(self):
        m = mapa.leer("barberia", self.carpeta)
        f = mapa.ficha(m, m.pieza("hoja-de-google"))
        self.assertEqual(f.capa, "Con qué se conecta")
        self.assertEqual(f.frase, "Donde viven los turnos")
        self.assertEqual(f.texto_estado, "Espera que lo compruebes")
        self.assertTrue(f.verde)
        self.assertEqual([(t["texto"], t["texto_columna"]) for t in f.tareas],
                         [("Guardar la reserva en la hoja", "Para comprobar")])
        self.assertEqual(f.desconocidas, ["cotejo-zzz999"])
        self.assertEqual(f.texto_tecnologia, "Si programas: Sheets API")
        hecha = mapa.ficha(m, m.pieza("calcular-huecos"))
        self.assertEqual(hecha.tareas[0]["texto_columna"], "Finalizada")
        self.assertFalse(hecha.verde)

    def test_con_el_proyecto_ya_leido_no_relee_las_tareas(self):
        # El board pasa lo que ya tiene en memoria: manda eso, aunque el archivo diga otra cosa.
        p = modelo.Proyecto("barberia", tareas=[
            modelo.Tarea("Pantalla de horarios libres", id="cotejo-aaa111", estado="pendiente")])
        m = mapa.leer("barberia", self.carpeta, p)
        self.assertEqual(m.pieza("horarios-libres")["estado"], "falta")
        self.assertEqual(m.pieza("calcular-huecos")["estado"], "falta")   # no está en memoria

    def test_sin_arquitectura_o_sin_carpeta_no_inventa_piezas(self):
        with tempfile.TemporaryDirectory() as otro:
            sin = proyecto_de_prueba(otro, con_arquitectura=False)
            m = mapa.leer("barberia", sin)
            self.assertFalse(m.con_arquitectura)
            self.assertEqual(len(m.tareas), 6)
        m = mapa.leer("suelto", "")
        self.assertFalse(m.con_arquitectura)
        self.assertTrue(m.avisos)


if __name__ == "__main__":
    unittest.main()
