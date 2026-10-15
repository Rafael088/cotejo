"""El almacén `.cotejo/` (v1.2, A1): el contrato del que cuelgan los verbos y el importador.

Todo corre contra un repo de mentira en una carpeta temporal. Lo que se vigila es lo que el
almacén promete: ids estables aunque el archivo cambie de nombre, lectura que no se rompe por
un frontmatter malo, escritura que se niega con una versión vieja, decisiones que no se editan
y bitácora que solo crece.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)
from tareas import almacen
from tareas.almacen import (Almacen, EntradaCambiada, EntradaNoExiste, FrontmatterRoto,
                            IdRepetido, NoSeEdita, componer, partir)


class PruebaConAlmacen(unittest.TestCase):

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.repo = Path(temporal.name) / "mi-repo"
        (self.repo / ".git").mkdir(parents=True)
        self.almacen = Almacen(self.repo)
        hoy = mock.patch.object(almacen, "_hoy", return_value="2026-10-04")
        hoy.start()
        self.addCleanup(hoy.stop)

    def escribir(self, relativa, contenido):
        ruta = self.repo / ".cotejo" / relativa
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(contenido, encoding="utf-8")
        return ruta


class Crear(PruebaConAlmacen):

    def test_cada_tipo_con_id_lleva_su_prefijo_y_cuatro_caracteres_base36(self):
        for tipo, prefijo in (("decision", "dec"), ("problema", "pro"), ("arquitectura", "arq"),
                              ("aprendizaje", "apr"), ("referencia", "ref")):
            with self.subTest(tipo=tipo):
                entrada = self.almacen.crear(tipo, f"Algo de {tipo}", "Texto.")
                self.assertRegex(entrada.id, rf"^{prefijo}-[a-z0-9]{{4}}$")
                self.assertEqual(entrada.tipo, tipo)

    def test_la_decision_nace_propuesta_con_fecha_y_en_su_carpeta(self):
        entrada = self.almacen.crear("decision", "Auth con JWT", "Usamos JWT.",
                                     temas=["Auth", "api", "auth"], autor="opus")
        self.assertEqual(entrada.estado, "propuesta")
        self.assertEqual(entrada.datos["fecha"], "2026-10-04")
        self.assertEqual(entrada.datos["autor"], "opus")
        self.assertEqual(entrada.temas, ["auth", "api"])  # minúsculas y sin repetir
        self.assertEqual(entrada.ruta, "decisiones/2026-10-04-auth-con-jwt.md")
        self.assertEqual(entrada.titulo, "Auth con JWT")

    def test_el_frontmatter_sale_en_el_orden_del_tipo(self):
        entrada = self.almacen.crear("decision", "X", autor="opus")
        crudo = (self.repo / ".cotejo" / entrada.ruta).read_text(encoding="utf-8")
        claves = [l.split(":")[0] for l in crudo.split("---")[1].strip().splitlines()]
        self.assertEqual(claves, ["id", "fecha", "temas", "estado", "autor"])

    def test_el_problema_nace_abierto_y_la_referencia_con_resumen_pendiente(self):
        self.assertEqual(self.almacen.crear("problema", "Se cae").estado, "abierto")
        ref = self.almacen.crear("referencia", "Manual de marca", "Colores y tipografías.")
        self.assertEqual(ref.datos["resumen"], "pendiente")
        self.assertEqual(ref.ruta, "referencias/manual-de-marca.md")

    def test_un_estado_que_no_es_del_tipo_no_se_crea(self):
        with self.assertRaises(ValueError):
            self.almacen.crear("decision", "X", estado="firmada")
        self.assertEqual(self.almacen.entradas(), [])

    def test_el_importador_puede_crear_decisiones_ya_aceptadas(self):
        entrada = self.almacen.crear("decision", "Vieja", estado="aceptada", autor="importado",
                                     origen="Cotejo.md#Decisiones")
        self.assertEqual(entrada.estado, "aceptada")
        self.assertEqual(entrada.datos["origen"], "Cotejo.md#Decisiones")

    def test_el_recurso_exige_el_archivo_y_nace_con_ficha_pendiente(self):
        with self.assertRaises(ValueError):
            self.almacen.crear("recurso", "Logo")
        ficha = self.almacen.crear("recurso", "Logo principal", archivo="logo-principal.svg")
        self.assertEqual(ficha.datos["ficha"], "pendiente")
        self.assertEqual(ficha.datos["archivo"], "logo-principal.svg")
        self.assertEqual(ficha.ruta, "recursos/logo-principal.md")

    def test_dos_titulos_iguales_no_se_pisan(self):
        a = self.almacen.crear("aprendizaje", "Medir, no estimar")
        b = self.almacen.crear("aprendizaje", "Medir, no estimar")
        self.assertNotEqual(a.ruta, b.ruta)
        self.assertNotEqual(a.id, b.id)
        self.assertEqual(len(self.almacen.entradas("aprendizaje")), 2)

    def test_el_nombre_de_archivo_vale_en_windows(self):
        entrada = self.almacen.crear("arquitectura", 'Flujo: pago <con> "tarjeta"? / ñandú')
        nombre = Path(entrada.ruta).name
        self.assertRegex(nombre, r"^[a-z0-9-]+\.md$")
        self.assertEqual(entrada.titulo, 'Flujo: pago <con> "tarjeta"? / ñandú')

    def test_un_titulo_sin_letras_usa_el_id_como_nombre(self):
        entrada = self.almacen.crear("referencia", "¿¿??")
        self.assertEqual(entrada.ruta, f"referencias/{entrada.id}.md")

    def test_sin_titulo_no_se_crea(self):
        with self.assertRaises(ValueError):
            self.almacen.crear("problema", "   ")

    def test_el_id_nuevo_no_repite_uno_ocupado_por_un_archivo_roto(self):
        self.escribir("problemas/roto.md", "---\nid: pro-aaaa\nestado abierto\n---\n")
        with mock.patch.object(almacen.random, "choices",
                               side_effect=[list("aaaa"), list("bbbb")]):
            entrada = self.almacen.crear("problema", "Otro")
        self.assertEqual(entrada.id, "pro-bbbb")

    def test_proyecto_md_se_crea_una_vez(self):
        proyecto = self.almacen.crear("proyecto", "Mi repo", "Objetivo: algo.")
        self.assertEqual(proyecto.id, "proyecto")
        self.assertEqual(proyecto.ruta, "proyecto.md")
        with self.assertRaises(NoSeEdita):
            self.almacen.crear("proyecto", "Otra vez")

    def test_un_tipo_desconocido_dice_cuales_hay(self):
        with self.assertRaisesRegex(ValueError, "decision"):
            self.almacen.crear("marca", "X")

    def test_crear_devuelve_la_version_del_archivo_que_dejo(self):
        entrada = self.almacen.crear("referencia", "R", "Texto.")
        crudo = (self.repo / ".cotejo" / entrada.ruta).read_bytes()
        self.assertEqual(entrada.version, almacen.version_de(crudo))


class Leer(PruebaConAlmacen):

    def test_sin_cotejo_no_hay_entradas_ni_error(self):
        self.assertFalse(self.almacen.existe())
        self.assertEqual(self.almacen.entradas(), [])

    def test_el_id_sobrevive_a_un_cambio_de_nombre(self):
        entrada = self.almacen.crear("decision", "Auth con JWT", "Texto.")
        vieja = self.repo / ".cotejo" / entrada.ruta
        vieja.rename(vieja.with_name("otro-nombre-cualquiera.md"))
        leida = self.almacen.leer(entrada.id)
        self.assertEqual(leida.ruta, "decisiones/otro-nombre-cualquiera.md")
        self.assertEqual(leida.titulo, "Auth con JWT")

    def test_frontmatter_roto_es_un_aviso_y_las_demas_se_leen(self):
        buena = self.almacen.crear("problema", "Bueno")
        self.escribir("problemas/sin-cierre.md", "---\nid: pro-zzzz\n# Se olvidó el cierre\n")
        self.escribir("problemas/sin-id.md", "---\nestado: abierto\n---\n# Sin id\n")
        self.escribir("problemas/otro-prefijo.md", "---\nid: dec-abcd\nestado: abierto\n---\n")
        self.escribir("problemas/estado-raro.md", "---\nid: pro-yyyy\nestado: quizas\n---\n")
        self.escribir("problemas/latin1.md", "")
        (self.repo / ".cotejo/problemas/latin1.md").write_bytes(b"---\nid: pro-\xf1\n---\n")
        avisos = []
        entradas = self.almacen.entradas(avisos=avisos)
        self.assertEqual([e.id for e in entradas], [buena.id])
        rotas = {a["nota"] for a in avisos}
        self.assertEqual(rotas, {f".cotejo/problemas/{n}.md" for n in
                                 ("sin-cierre", "sin-id", "otro-prefijo", "estado-raro",
                                  "latin1")})
        self.assertTrue(all(a["motivo"] for a in avisos))

    def test_sin_lista_de_avisos_lo_roto_se_salta_sin_reventar(self):
        self.escribir("aprendizajes/x.md", "---\nid apr-aaaa\n---\n")
        self.assertEqual(self.almacen.entradas(), [])

    def test_archivos_que_no_son_md_ni_ocultos_no_cuentan(self):
        ficha = self.almacen.crear("recurso", "Logo", archivo="logo.svg")
        (self.repo / ".cotejo/recursos/logo.svg").write_text("<svg/>", encoding="utf-8")
        (self.repo / ".cotejo/recursos/.logo.md.cotejo-tmp").write_text("x", encoding="utf-8")
        self.assertEqual([e.id for e in self.almacen.entradas()], [ficha.id])

    def test_leer_un_id_que_no_existe_sugiere_el_parecido(self):
        self.escribir("decisiones/a.md", "---\nid: dec-x7k2\nestado: aceptada\n---\n# A\n")
        with self.assertRaises(EntradaNoExiste) as caso:
            self.almacen.leer("dec-x7k3")
        self.assertEqual(caso.exception.parecidos, ["dec-x7k2"])
        self.assertIn("dec-x7k2", str(caso.exception))

    def test_leer_algo_sin_forma_de_id_busca_en_todo(self):
        self.escribir("decisiones/a.md", "---\nid: dec-x7k2\nestado: aceptada\n---\n# A\n")
        with self.assertRaises(EntradaNoExiste) as caso:
            self.almacen.leer("dec-x7k")
        self.assertEqual(caso.exception.parecidos, ["dec-x7k2"])

    def test_un_id_repetido_avisa_en_los_dos_y_leer_se_niega(self):
        for nombre in ("a", "b"):
            self.escribir(f"decisiones/{nombre}.md",
                          "---\nid: dec-aaaa\nestado: propuesta\n---\n# X\n")
        avisos = []
        self.assertEqual(len(self.almacen.entradas(avisos=avisos)), 2)
        self.assertEqual(len(avisos), 2)
        with self.assertRaises(IdRepetido):
            self.almacen.leer("dec-aaaa")

    def test_lee_lo_que_escribe_una_persona_en_obsidian(self):
        self.escribir("arquitectura/flujo.md",
                      "---\r\nid: arq-k2m9\r\ntemas:\r\n  - Pagos\r\n  - api\r\n"
                      "actualizado: 2026-09-01\r\n---\r\n# Flujo de pago\r\n\r\n"
                      "El cobro pasa por [[dec-x7k2]].\r\n")
        entrada = self.almacen.leer("arq-k2m9")
        self.assertEqual(entrada.temas, ["pagos", "api"])
        self.assertEqual(entrada.titulo, "Flujo de pago")
        self.assertEqual(entrada.resumen(), "El cobro pasa por [[dec-x7k2]].")

    def test_el_resumen_propio_gana_salvo_que_este_pendiente(self):
        ref = self.almacen.crear("referencia", "Marca", "Primer párrafo.\n\nSegundo.")
        self.assertEqual(ref.resumen(), "Primer párrafo.")
        ref = self.almacen.reescribir(ref.id, ref.version, campos={"resumen": "Colores y voz"})
        self.assertEqual(ref.resumen(), "Colores y voz")

    def test_el_resumen_se_recorta(self):
        ref = self.almacen.crear("referencia", "Larga", "palabra " * 100)
        self.assertLessEqual(len(ref.resumen()), 160)
        self.assertTrue(ref.resumen().endswith("…"))

    def test_entradas_de_un_tipo_solo_trae_ese_tipo(self):
        self.almacen.crear("decision", "D")
        self.almacen.crear("problema", "P")
        self.assertEqual([e.tipo for e in self.almacen.entradas("problema")], ["problema"])

    def test_como_dict_lleva_lo_que_necesita_un_verbo(self):
        entrada = self.almacen.crear("problema", "Se cae", "Detalle.", temas=["red"])
        datos = entrada.como_dict(con_cuerpo=True)
        for clave in ("id", "tipo", "titulo", "ruta", "version", "temas", "estado", "cuerpo"):
            self.assertIn(clave, datos)


class Escribir(PruebaConAlmacen):

    def test_editar_con_la_version_vista_cambia_el_texto_y_conserva_el_id(self):
        arq = self.almacen.crear("arquitectura", "Flujo", "Viejo.", temas=["pagos"])
        nueva = self.almacen.reescribir(arq.id, arq.version, texto="Nuevo.")
        self.assertEqual(nueva.id, arq.id)
        self.assertNotEqual(nueva.version, arq.version)
        self.assertIn("Nuevo.", nueva.cuerpo)
        self.assertNotIn("Viejo.", nueva.cuerpo)
        self.assertEqual(nueva.titulo, "Flujo")
        self.assertEqual(nueva.temas, ["pagos"])

    def test_editar_con_una_version_vieja_se_niega_sin_escribir(self):
        arq = self.almacen.crear("arquitectura", "Flujo", "Uno.")
        ruta = self.repo / ".cotejo" / arq.ruta
        ruta.write_text(ruta.read_text(encoding="utf-8") + "Lo de otro.\n", encoding="utf-8")
        antes = ruta.read_bytes()
        with self.assertRaises(EntradaCambiada) as caso:
            self.almacen.reescribir(arq.id, arq.version, texto="Mío.")
        self.assertEqual(ruta.read_bytes(), antes)
        self.assertEqual(caso.exception.version_actual, almacen.version_de(antes))

    def test_editar_sigue_a_la_entrada_aunque_la_hayan_renombrado(self):
        ref = self.almacen.crear("referencia", "R", "Uno.")
        ruta = self.repo / ".cotejo" / ref.ruta
        ruta.rename(ruta.with_name("renombrada.md"))
        nueva = self.almacen.reescribir(ref.id, ref.version, texto="Dos.")
        self.assertEqual(nueva.ruta, "referencias/renombrada.md")

    def test_las_decisiones_no_se_editan_y_el_error_dice_como_reemplazarlas(self):
        dec = self.almacen.crear("decision", "D", "Texto.")
        with self.assertRaisesRegex(NoSeEdita, f"--reemplaza {dec.id}"):
            self.almacen.reescribir(dec.id, dec.version, texto="Otro.")

    def test_los_problemas_y_aprendizajes_no_se_editan_en_el_sitio(self):
        for tipo in ("problema", "aprendizaje"):
            entrada = self.almacen.crear(tipo, "X")
            with self.subTest(tipo=tipo), self.assertRaises(NoSeEdita):
                self.almacen.reescribir(entrada.id, entrada.version, texto="Y")

    def test_editar_no_toca_el_id_ni_el_estado(self):
        ref = self.almacen.crear("referencia", "R")
        for campos in ({"id": "ref-zzzz"}, {"estado": "x"}):
            with self.subTest(campos=campos), self.assertRaises(NoSeEdita):
                self.almacen.reescribir(ref.id, ref.version, campos=campos)

    def test_editar_arquitectura_pone_la_fecha_de_actualizado(self):
        arq = self.almacen.crear("arquitectura", "A")
        self.escribir(arq.ruta, componer({**arq.datos, "actualizado": "2026-01-01"}, arq.cuerpo))
        arq = self.almacen.leer(arq.id)
        self.assertEqual(self.almacen.reescribir(arq.id, arq.version, texto="B").datos[
            "actualizado"], "2026-10-04")

    def test_cambiar_solo_el_titulo_conserva_el_texto(self):
        ref = self.almacen.crear("referencia", "Viejo", "Cuerpo.")
        nueva = self.almacen.reescribir(ref.id, ref.version, titulo="Nuevo")
        self.assertEqual(nueva.titulo, "Nuevo")
        self.assertIn("Cuerpo.", nueva.cuerpo)
        self.assertEqual(nueva.cuerpo.count("# "), 1)

    def test_proyecto_md_se_edita_por_version(self):
        proyecto = self.almacen.crear("proyecto", "Repo", "Objetivo.")
        nuevo = self.almacen.reescribir("proyecto", proyecto.version, texto="Otro objetivo.")
        self.assertIn("Otro objetivo.", nuevo.cuerpo)

    def test_la_escritura_no_deja_temporales(self):
        ref = self.almacen.crear("referencia", "R")
        self.almacen.reescribir(ref.id, ref.version, texto="X")
        sobras = [p.name for p in (self.repo / ".cotejo").rglob(".*") if p.is_file()]
        self.assertEqual(sobras, [])


class Estados(PruebaConAlmacen):

    def test_una_decision_se_acepta_y_luego_se_reemplaza(self):
        dec = self.almacen.crear("decision", "D")
        dec = self.almacen.poner_estado(dec.id, dec.version, "aceptada")
        self.assertEqual(dec.estado, "aceptada")
        dec = self.almacen.poner_estado(dec.id, dec.version, "reemplazada",
                                        campos={"reemplazada_por": "dec-zzzz"})
        self.assertEqual(dec.estado, "reemplazada")
        self.assertEqual(dec.datos["reemplazada_por"], "dec-zzzz")

    def test_una_decision_no_vuelve_atras(self):
        dec = self.almacen.crear("decision", "D", estado="aceptada")
        with self.assertRaisesRegex(NoSeEdita, "reemplazada"):
            self.almacen.poner_estado(dec.id, dec.version, "propuesta")
        dec = self.almacen.poner_estado(dec.id, dec.version, "reemplazada")
        with self.assertRaises(NoSeEdita):
            self.almacen.poner_estado(dec.id, dec.version, "aceptada")

    def test_cambiar_el_estado_no_toca_el_texto_de_la_decision(self):
        dec = self.almacen.crear("decision", "D", "El texto firmado.")
        nueva = self.almacen.poner_estado(dec.id, dec.version, "aceptada")
        self.assertEqual(nueva.cuerpo, dec.cuerpo)

    def test_un_problema_se_resuelve_y_se_reabre(self):
        pro = self.almacen.crear("problema", "P")
        pro = self.almacen.poner_estado(pro.id, pro.version, "resuelto",
                                        campos={"solucion": "reiniciar"})
        self.assertEqual((pro.estado, pro.datos["solucion"]), ("resuelto", "reiniciar"))
        self.assertEqual(self.almacen.poner_estado(pro.id, pro.version, "abierto").estado,
                         "abierto")

    def test_el_estado_tambien_se_verifica_por_version(self):
        pro = self.almacen.crear("problema", "P")
        self.almacen.poner_estado(pro.id, pro.version, "resuelto")
        with self.assertRaises(EntradaCambiada):
            self.almacen.poner_estado(pro.id, pro.version, "resuelto")

    def test_los_tipos_sin_estado_no_tienen_transiciones(self):
        apr = self.almacen.crear("aprendizaje", "A")
        with self.assertRaises(NoSeEdita):
            self.almacen.poner_estado(apr.id, apr.version, "resuelto")


class Bitacora(PruebaConAlmacen):

    def test_un_archivo_por_dia_que_solo_crece(self):
        primera = self.almacen.bitacora("Empecé A1.")
        crudo1 = (self.repo / ".cotejo" / primera.ruta).read_text(encoding="utf-8")
        segunda = self.almacen.bitacora("Terminé A1.")
        crudo2 = (self.repo / ".cotejo" / segunda.ruta).read_text(encoding="utf-8")
        self.assertEqual(primera.ruta, "bitacora/2026-10-04.md")
        self.assertEqual(segunda.id, "2026-10-04")
        self.assertTrue(crudo2.startswith(crudo1))
        self.assertIn("Terminé A1.", crudo2[len(crudo1):])

    def test_respeta_lo_que_otro_anoto_el_mismo_dia(self):
        self.escribir("bitacora/2026-10-04.md", "---\nfecha: 2026-10-04\n---\n# Hoy\n\nDe otro.\n")
        entrada = self.almacen.bitacora("Mío.")
        self.assertIn("De otro.", entrada.cuerpo)
        self.assertTrue(entrada.cuerpo.rstrip().endswith("Mío."))

    def test_otro_dia_es_otro_archivo_y_se_lee_por_fecha(self):
        self.almacen.bitacora("Ayer.", fecha="2026-10-03")
        self.almacen.bitacora("Hoy.")
        self.assertEqual([e.id for e in self.almacen.entradas("bitacora")],
                         ["2026-10-03", "2026-10-04"])
        self.assertIn("Ayer.", self.almacen.leer("2026-10-03").cuerpo)

    def test_no_recibe_vacios_ni_fechas_raras(self):
        with self.assertRaises(ValueError):
            self.almacen.bitacora("   ")
        with self.assertRaises(ValueError):
            self.almacen.bitacora("x", fecha="ayer")

    def test_no_se_crea_ni_se_edita_como_entrada(self):
        dia = self.almacen.bitacora("x")
        with self.assertRaises(NoSeEdita):
            self.almacen.crear("bitacora", "x")
        with self.assertRaises(NoSeEdita):
            self.almacen.reescribir(dia.id, dia.version, texto="otra cosa")

    def test_un_archivo_de_bitacora_que_no_es_una_fecha_es_un_aviso(self):
        self.escribir("bitacora/notas-sueltas.md", "algo\n")
        avisos = []
        self.assertEqual(self.almacen.entradas("bitacora", avisos=avisos), [])
        self.assertEqual(len(avisos), 1)


class Frontmatter(unittest.TestCase):

    def test_ida_y_vuelta_con_valores_dificiles(self):
        datos = {"id": "ref-ab12", "temas": ["a, b", "c]", "#tag", "normal"],
                 "resumen": 'Dice: "hola" # y más', "origen": "", "vacio_lista": [],
                 "barra": "C:\\ruta\\x", "guion": "- algo"}
        leidos, cuerpo = partir(componer(datos, "# T\n"))
        self.assertEqual(leidos, datos)
        self.assertEqual(cuerpo, "# T\n")

    def test_sin_frontmatter_todo_es_cuerpo(self):
        self.assertEqual(partir("# Hola\n"), ({}, "# Hola\n"))

    def test_lo_que_no_se_entiende_dice_en_que_linea(self):
        with self.assertRaisesRegex(FrontmatterRoto, "línea 3"):
            partir("---\nid: x\nesto no\n---\n")

    def test_una_clave_repetida_esta_rota(self):
        with self.assertRaises(FrontmatterRoto):
            partir("---\nid: a\nid: b\n---\n")

    def test_una_lista_en_linea_sin_cerrar_esta_rota(self):
        with self.assertRaises(FrontmatterRoto):
            partir("---\ntemas: [a, b\n---\n")

    def test_comillas_simples_y_comentarios(self):
        datos, _ = partir("---\n# comentario\nresumen: 'it''s'\n---\n")
        self.assertEqual(datos, {"resumen": "it's"})


if __name__ == "__main__":
    unittest.main()
