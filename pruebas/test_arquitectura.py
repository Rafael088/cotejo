"""La arquitectura dibujable (v1.3.0): piezas en cuatro capas con estado desde sus tareas.

Dos partes: la función pura (`tareas/arquitectura.py`, sin archivos ni GTK), que es la base de
la constelación y del mapa del board; y los verbos de punta a punta —`anotar`, `leer`,
`editar` y `contexto`— por `cli.main`, contra un repo de git de verdad en una carpeta temporal
con su `.cotejo/tareas.md`.
"""

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)
from tareas import almacen, arquitectura, cli

TABLA = """# Arquitectura

Una tienda pequeña.

## Piezas

| Capa | Pieza | Qué es | Tecnología | Tareas |
| --- | --- | --- | --- | --- |
| ve | Pantalla de pedidos | Donde el cliente elige y paga | React | cotejo-aaaaaa, cotejo-bbbbbb |
| Guarda | Pedidos | La lista de pedidos \\| del día | SQLite | |

## Notas

Lo demás sigue siendo texto libre.
"""


class FuncionPura(unittest.TestCase):

    def test_lee_las_piezas_de_la_tabla(self):
        analisis = arquitectura.analizar(TABLA)
        self.assertTrue(analisis.dibujable)
        self.assertEqual(analisis.errores, ())
        ve, guarda = analisis.piezas
        self.assertEqual((ve.id, ve.capa, ve.tecnologia, ve.tareas),
                         ("pantalla-de-pedidos", "ve", "React", ("cotejo-aaaaaa", "cotejo-bbbbbb")))
        self.assertEqual((guarda.capa, guarda.frase, guarda.tareas),
                         ("guarda", "La lista de pedidos | del día", ()))

    def test_texto_libre_no_es_dibujable_ni_da_error(self):
        analisis = arquitectura.analizar("# Flujo\n\nEl login pasa por OAuth.\n")
        self.assertEqual(analisis, arquitectura.Analisis(dibujable=False))

    def test_tabla_y_analizar_son_inversos(self):
        piezas = arquitectura.analizar(TABLA).piezas
        self.assertEqual(arquitectura.analizar(arquitectura.tabla(piezas)).piezas, piezas)

    def test_valida_capa_nombre_frase_tareas_y_repetidos(self):
        filas = ("| vista | A | b | | |", "| ve |  | b | | |", "| ve | B |  | | |",
                 "| ve | " + "x" * 41 + " | d | | |",
                 "| ve | D | d | | |", "| hace | d | e | | |", "| ve | E | e | | | | |")
        cuerpo = "## Piezas\n\n" + "\n".join(filas) + "\n"
        analisis = arquitectura.analizar(cuerpo)
        self.assertEqual([p.nombre for p in analisis.piezas], ["D"])
        self.assertEqual(len(analisis.errores), 6)
        self.assertIn("vista", analisis.errores[0])
        self.assertIn("repite el nombre", analisis.errores[4])

    def test_texto_libre_en_tareas_no_es_error_y_se_enlaza_por_nombre(self):
        cuerpo = ("## Piezas\n\n| Capa | Pieza | Qué es | Tecnología | Tareas |\n| --- | --- | --- | --- | --- |\n"
                  "| ve | A | a | | Crear el login, cotejo-aaaaaa, algo que no existe |\n"
                  "| hace | B | b | | Montar la base de datos |\n")
        analisis = arquitectura.analizar(cuerpo)
        self.assertEqual(analisis.errores, ())
        a, b = analisis.piezas
        self.assertEqual(a.tareas, ("cotejo-aaaaaa",))
        self.assertEqual(a.textos, ("Crear el login", "algo que no existe"))
        columnas = {"cotejo-aaaaaa": "hecha", "cotejo-zzzzzz": "en-curso", "cotejo-yyyyyy": "pendiente"}
        textos = {"cotejo-zzzzzz": "Crear el login con Google", "cotejo-yyyyyy": "Otra cosa"}
        con = {p["id"]: p for p in arquitectura.con_estado(analisis.piezas, columnas, textos)}
        self.assertEqual(con["a"]["tareas"], ["cotejo-aaaaaa", "cotejo-zzzzzz"])
        self.assertEqual(con["a"]["estado"], "en-curso")
        # Sin coincidencia se ignora en silencio: ni estado raro ni ids desconocidos.
        self.assertEqual((con["b"]["tareas"], con["b"]["estado"], con["b"]["desconocidas"]),
                         ([], "falta", []))

    def test_seccion_sin_filas_es_un_error(self):
        analisis = arquitectura.analizar("## Piezas\n\nNada todavía.\n")
        self.assertTrue(analisis.dibujable)
        self.assertEqual(len(analisis.errores), 1)

    def test_pieza_de_texto_y_el_prefijo_viejo(self):
        pieza = arquitectura.pieza_de_texto("conecta|Stripe|El banco que cobra")
        self.assertEqual((pieza.capa, pieza.tecnologia, pieza.tareas), ("conecta", "", ()))
        self.assertEqual(arquitectura.pieza_de_texto("ve|A|b||foco-abc123").tareas,
                         ("cotejo-abc123",))
        with self.assertRaises(ValueError):
            arquitectura.pieza_de_texto("ve|solo nombre")

    def test_estado_de_una_pieza(self):
        e = arquitectura.estado_pieza
        self.assertEqual(e(["por-validar", "en-curso", "hecha"]), "por-comprobar")
        self.assertEqual(e(["hecha", "hecha"]), "hecho")
        self.assertEqual(e(["hecha", "en-curso", "pendiente"]), "en-curso")
        self.assertEqual(e(["hecha", "pendiente"]), "falta")
        self.assertEqual(e(["pendiente"]), "falta")
        self.assertEqual(e([]), "falta")  # sin tareas: nadie la ha hecho ni prometido

    def test_tareas_que_no_existen_no_cuentan_para_el_estado(self):
        pieza = arquitectura.pieza_de_texto("ve|A|b||cotejo-aaaaaa, cotejo-zzzzzz")
        (datos,) = arquitectura.con_estado([pieza], {"cotejo-aaaaaa": "hecha"})
        self.assertEqual((datos["estado"], datos["total"], datos["desconocidas"]),
                         ("hecho", 1, ["cotejo-zzzzzz"]))

    def test_resumen_una_linea_por_capa(self):
        piezas = [{"capa": "ve", "estado": "hecho"}, {"capa": "ve", "estado": "falta"},
                  {"capa": "hace", "estado": "por-comprobar"}]
        self.assertEqual(arquitectura.resumen_por_capa(piezas), {
            "ve": "2 piezas: 1 hecho, 1 falta", "hace": "1 pieza: 1 por-comprobar",
            "guarda": "sin piezas", "conecta": "sin piezas"})


class Verbos(unittest.TestCase):
    """`anotar`, `leer`, `editar` y `contexto` de punta a punta, con un repo de git real."""

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.repo = Path(temporal.name) / "tienda"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        cotejo = self.repo / ".cotejo"
        (cotejo / "arquitectura").mkdir(parents=True)
        (cotejo / "tareas.md").write_text(
            "# Tareas\n\n"
            "- [ ] Hacer la pantalla #en-curso ^cotejo-aaaaaa\n"
            "- [ ] Probar el cobro #por-validar ^cotejo-bbbbbb\n"
            "- [ ] Guardar pedidos ^cotejo-dddddd\n"
            "- [x] La base — 2026-10-01 ^cotejo-cccccc\n", encoding="utf-8")

    def correr(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            codigo = cli.main([*args, "--repo", str(self.repo)])
        salida = buf.getvalue().strip()
        return codigo, (json.loads(salida) if salida else None), salida

    def archivos(self):
        return sorted((self.repo / ".cotejo" / "arquitectura").glob("*.md"))

    def anotar_tienda(self):
        codigo, datos, _ = self.correr(
            "anotar", "arquitectura", "--titulo", "Arquitectura", "--texto", "Una tienda.",
            "--pieza", "ve|Pantalla de pedidos|Donde el cliente elige y paga|React|cotejo-aaaaaa",
            "--pieza", "hace|Cobro|Cobra el pedido||cotejo-bbbbbb, cotejo-cccccc",
            "--pieza", "guarda|Pedidos|La lista de pedidos|SQLite|cotejo-cccccc",
            "--pieza", "conecta|Stripe|El banco que cobra|API")
        self.assertEqual(codigo, 0, datos)
        return datos

    def test_anotar_con_piezas_deja_la_tabla_y_leer_trae_el_estado(self):
        datos = self.anotar_tienda()
        self.assertEqual(datos["piezas"], 4)
        texto = self.archivos()[0].read_text(encoding="utf-8")
        self.assertIn("## Piezas", texto)
        self.assertIn("| conecta | Stripe | El banco que cobra | API |", texto)

        _, leida, _ = self.correr("leer", datos["id"])
        self.assertEqual(leida["formato"], "piezas")
        estados = {p["id"]: p["estado"] for p in leida["piezas"]}
        self.assertEqual(estados, {"pantalla-de-pedidos": "en-curso", "cobro": "por-comprobar",
                                   "pedidos": "hecho", "stripe": "falta"})
        self.assertNotIn("avisos", leida)

    def test_anotar_con_la_tabla_en_el_texto(self):
        codigo, datos, _ = self.correr("anotar", "arquitectura", "--titulo", "Arquitectura",
                                       "--texto", TABLA)
        self.assertEqual((codigo, datos["piezas"]), (0, 2))

    def test_anotar_se_niega_sin_escribir_si_la_tabla_esta_mal(self):
        codigo, datos, _ = self.correr("anotar", "arquitectura", "--titulo", "A",
                                       "--texto", "## Piezas\n\n| vista | A | b | | |\n")
        self.assertNotEqual(codigo, 0)
        self.assertIn("vista", datos["error"])
        codigo, datos, _ = self.correr("anotar", "arquitectura", "--titulo", "A",
                                       "--pieza", "ve|A|b|", "--pieza", "ve|a|otra")
        self.assertNotEqual(codigo, 0)
        self.assertIn("repite el nombre", datos["error"])
        codigo, _, _ = self.correr("anotar", "arquitectura", "--titulo", "A")
        self.assertNotEqual(codigo, 0)
        codigo, _, _ = self.correr("anotar", "arquitectura", "--titulo", "A", "--texto", TABLA,
                                   "--pieza", "ve|B|c")
        self.assertNotEqual(codigo, 0)
        self.assertEqual(self.archivos(), [])

    def test_con_varias_entradas_manda_la_mas_reciente_sin_error(self):
        from tareas import conocimiento
        carpeta = self.repo / ".cotejo" / "arquitectura"
        tabla = lambda n: ("## Piezas\n\n| Capa | Pieza | Qué es | Tecnología | Tareas |\n"
                           "| --- | --- | --- | --- | --- |\n"
                           f"| ve | {n} | algo | | Texto suelto |\n")
        (carpeta / "arquitectura.md").write_text(
            "---\nid: arq-aaaa\ntemas: []\nactualizado: 2026-10-01\n---\n" + tabla("Vieja"))
        (carpeta / "arquitectura-2.md").write_text(
            "---\nid: arq-bbbb\ntemas: []\nactualizado: 2026-10-02\n---\n" + tabla("Nueva"))
        avisos = []
        piezas = conocimiento.piezas_del_repo(almacen.Almacen(self.repo), avisos=avisos)
        self.assertEqual([p["nombre"] for p in piezas], ["Nueva"])
        self.assertEqual(avisos, [])

    def test_la_arquitectura_en_texto_libre_se_sigue_leyendo(self):
        codigo, datos, _ = self.correr("anotar", "arquitectura", "--titulo", "Flujo de login",
                                       "--texto", "El login pasa por OAuth.")
        self.assertEqual(codigo, 0)
        self.assertNotIn("piezas", datos)
        _, leida, _ = self.correr("leer", datos["id"])
        self.assertEqual(leida["formato"], "libre")
        self.assertNotIn("piezas", leida)
        _, contexto, _ = self.correr("contexto")
        self.assertNotIn("arquitectura", contexto)

    def test_leer_avisa_de_filas_rotas_escritas_a_mano(self):
        entrada = almacen.Almacen(self.repo).crear(
            "arquitectura", "A", "## Piezas\n\n| ve | Bien | Una frase | | |\n"
                                 "| nube | Mal | Otra | | |\n")
        _, leida, _ = self.correr("leer", entrada.id)
        self.assertEqual([p["id"] for p in leida["piezas"]], ["bien"])
        self.assertIn("nube", leida["avisos"][0]["motivo"])
        _, contexto, _ = self.correr("contexto")
        self.assertIn("nube", contexto["avisos"][0]["motivo"])
        self.assertEqual(contexto["arquitectura"]["ve"], "1 pieza: 1 falta")

    def test_editar_valida_la_tabla(self):
        datos = self.anotar_tienda()
        _, leida, _ = self.correr("leer", datos["id"])
        codigo, error, _ = self.correr("editar", datos["id"], "--version", leida["version"],
                                       "--texto", "## Piezas\n\n| vista | A | b | | |\n")
        self.assertNotEqual(codigo, 0)
        self.assertIn("vista", error["error"])
        nuevo = leida["cuerpo"].replace("| conecta | Stripe | El banco que cobra | API |  |",
                                        "| conecta | Stripe | El banco que cobra | API | "
                                        "cotejo-dddddd |")
        codigo, _, _ = self.correr("editar", datos["id"], "--version", leida["version"],
                                   "--texto", nuevo)
        self.assertEqual(codigo, 0)
        _, leida, _ = self.correr("leer", datos["id"])
        self.assertEqual(leida["piezas"][-1]["tareas"], ["cotejo-dddddd"])

    def test_contexto_resume_una_linea_por_capa(self):
        datos = self.anotar_tienda()
        _, contexto, _ = self.correr("contexto")
        self.assertEqual(contexto["arquitectura"], {
            "entradas": [datos["id"]], "ve": "1 pieza: 1 en-curso",
            "hace": "1 pieza: 1 por-comprobar", "guarda": "1 pieza: 1 hecho",
            "conecta": "1 pieza: 1 falta"})
        self.assertEqual(contexto["tareas"], {"pendiente": 1, "en-curso": 1, "por-validar": 1,
                                              "hecha": 1})

    def test_contexto_sigue_barato_con_muchas_piezas(self):
        piezas = []
        for capa in arquitectura.CAPAS:
            for i in range(10):
                piezas += ["--pieza", f"{capa}|Pieza {capa} {i}|Una frase en llano bastante "
                                      f"larga para la pieza {i}|Tecnología|cotejo-aaaaaa"]
        self.correr("anotar", "arquitectura", "--titulo", "Grande", *piezas)
        _, _, salida = self.correr("contexto")
        self.assertLess(round(len(salida) / 4), 1000, f"contexto pesó ~{len(salida) // 4} tokens")


if __name__ == "__main__":
    unittest.main()
