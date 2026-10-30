"""Los temas de CotejoBoard: que el CSS no tenga colores propios y que un tema roto no se use.

Lo que se vigila es lo que falla sin hacer ruido. Un color literal en el CSS se ve bien en el
tema en que se escribió y deja algo invisible en el otro —así quedó el `#FFFFFF` del hover de
los botones planos al tokenizar—. Un tema al que le falta un token deja ese color sin definir
y GTK lo pinta con lo que le parece. Y un tema que no se lee es un tema roto aunque el JSON
esté perfecto: por eso el contraste se mide, no se supone.

El CSS se lee de `tareas/app/estilo.py` como texto, igual que los iconos en `test_iconos.py`:
así estas pruebas corren también donde no hay GTK.
"""

import json
import os
import re
import unittest
from pathlib import Path
from unittest import mock

from apoyo import RAIZ, PruebaDeCLI
from tareas import configuracion, temas


def css_del_board():
    texto = (RAIZ / "tareas" / "app" / "estilo.py").read_text(encoding="utf-8")
    inicio = texto.index('CSS = """') + len('CSS = """')
    return texto[inicio:texto.index('"""', inicio)]


def sin_comentarios(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def tema_valido(**cambios):
    datos = json.loads((temas.DATOS / "oscuro.json").read_text(encoding="utf-8"))
    datos["colores"].update(cambios)
    return datos


class ElCSS(unittest.TestCase):

    def test_no_tiene_ningun_color_escrito_a_mano(self):
        css = sin_comentarios(css_del_board())
        literales = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|\b(?:white|black)\b", css)
        self.assertEqual(literales, [], "Los colores van en el tema (data/temas), no en el CSS")

    def test_cada_token_de_color_que_pide_lo_trae_el_tema(self):
        css = sin_comentarios(css_del_board())
        definidos = set(re.findall(r"--k-([a-z0-9-]+)\s*:", css))
        pedidos = set(re.findall(r"var\(--k-([a-z0-9-]+)\)", css))
        sin_definir = pedidos - definidos - set(temas.TOKENS)
        self.assertEqual(sin_definir, set())

    def test_ningun_token_del_tema_sobra(self):
        pedidos = set(re.findall(r"var\(--k-([a-z0-9-]+)\)", sin_comentarios(css_del_board())))
        self.assertEqual(set(temas.TOKENS) - pedidos, set(),
                         "Un token que el CSS no usa es un color que un tema rellena para nada")

    def test_el_css_no_redefine_ningun_token_del_tema(self):
        definidos = set(re.findall(r"--k-([a-z0-9-]+)\s*:", sin_comentarios(css_del_board())))
        self.assertEqual(definidos & set(temas.TOKENS), set())

    def test_el_bloque_del_tema_trae_todos_los_tokens_y_nada_mas(self):
        bloque = temas.css(temas.cargar("claro"))
        self.assertEqual(set(re.findall(r"--k-([a-z0-9-]+):", bloque)), set(temas.TOKENS))

    def test_dim_label_no_hereda_la_opacidad_de_adwaita(self):
        # Adwaita atenúa dim-label con opacity: 0.55; sobre el claro eso deja el texto chico
        # en 4,1:1. Cotejo lo pinta con el token tenue y sin opacidad.
        css = sin_comentarios(css_del_board())
        regla = next(r for r in css.split("}") if r.strip().startswith(".dim-label"))
        self.assertIn("var(--k-tenue)", regla)
        self.assertIn("opacity: 1", regla)

    def test_la_pista_de_un_vacio_no_va_atenuada(self):
        # Al 75 % daba 3,4:1 sobre la columna del claro, por debajo de 4,5.
        css = sin_comentarios(css_del_board())
        regla = next(r for r in css.split("}") if r.strip().startswith(".vacio-pista"))
        self.assertIn("opacity: 1", regla)


class LosDeFabrica(unittest.TestCase):

    def test_oscuro_y_claro_existen_y_se_pueden_usar(self):
        for ident, esquema in (("oscuro", "oscuro"), ("claro", "claro")):
            with self.subTest(ident):
                datos = temas.cargar(ident)
                self.assertEqual(datos["esquema"], esquema)
                errores, medidas = temas.problemas_de(datos)
                self.assertEqual((errores, temas.fallos(medidas)), ([], []))

    def test_el_oscuro_es_el_de_siempre(self):
        # Pasar los colores al tema era un refactor: el board oscuro no podía cambiar.
        colores = temas.cargar("oscuro")["colores"]
        self.assertEqual((colores["fondo"], colores["texto"], colores["senal"],
                          colores["tenue"], colores["velo-fuerte"]),
                         ("#101114", "#FFFFFF", "#16C98D", "#A8ACB6",
                          "rgba(255, 255, 255, 0.06)"))

    def test_el_de_defecto_es_de_fabrica(self):
        self.assertTrue((temas.DATOS / f"{temas.DEFECTO}.json").exists())

    def test_la_instalacion_se_los_lleva(self):
        # install.sh copia las carpetas de data/ una a una: sin esta, el board instalado no
        # tiene ni el tema de defecto, y eso solo se ve después de instalar.
        self.assertIn('"$ORIGEN/data/temas"', (RAIZ / "install.sh").read_text(encoding="utf-8"))


class Comprobar(unittest.TestCase):

    def test_los_colores_que_acepta_y_los_que_no(self):
        self.assertEqual(temas.color("#fff"), (255, 255, 255, 1.0))
        self.assertEqual(temas.color("#10111480")[:3], (16, 17, 20))
        self.assertEqual(temas.color("rgba(1, 2, 3, 0.5)"), (1, 2, 3, 0.5))
        self.assertEqual(temas.color("rgb(1,2,3)"), (1, 2, 3, 1.0))
        for malo in ("red", "#12", "rgb(300, 0, 0)", "rgb(1, 2, 3, 0.5)", "rgba(1,2,3,2)",
                     "#fff; } window { background: red", "var(--k-fondo)", 12, None):
            with self.subTest(malo):
                self.assertIsNone(temas.color(malo))

    def test_una_regla_colada_donde_iba_un_color_no_pasa(self):
        errores, _ = temas.problemas_de(tema_valido(fondo="#000; } * { color: red"))
        self.assertTrue(any("fondo" in e for e in errores))

    def test_falta_un_token(self):
        datos = tema_valido()
        del datos["colores"]["senal"]
        errores, _ = temas.problemas_de(datos)
        self.assertTrue(any("senal" in e for e in errores))

    def test_sobra_un_token_o_una_clave(self):
        datos = tema_valido(inventado="#000")
        datos["css"] = "window {}"
        errores, _ = temas.problemas_de(datos)
        self.assertTrue(any("inventado" in e for e in errores))
        self.assertTrue(any("css" in e for e in errores))

    def test_el_fondo_translucido_no_vale(self):
        errores, _ = temas.problemas_de(tema_valido(fondo="rgba(0, 0, 0, 0.5)"))
        self.assertTrue(any("opaco" in e for e in errores))

    def test_el_esquema_tiene_que_ser_claro_u_oscuro(self):
        datos = tema_valido()
        datos["esquema"] = "sepia"
        errores, _ = temas.problemas_de(datos)
        self.assertTrue(any("esquema" in e for e in errores))

    def test_un_texto_que_no_se_lee_no_pasa(self):
        # El caso del `#FFFFFF` del hover: texto claro sobre fondo claro.
        errores, medidas = temas.problemas_de(tema_valido(fondo="#F6F7F9", texto="#FFFFFF"))
        self.assertEqual(errores, [])
        fallidos = [m for m in medidas if not m["ok"]]
        self.assertIn(("texto", "fondo"), [(m["delante"], m["detras"]) for m in fallidos])

    def test_el_velo_se_compone_sobre_el_fondo_antes_de_medir(self):
        # senal-suave es translúcido: medido a pelo saldría contra negro, y el verde pasaría
        # siempre. Con un velo casi opaco del mismo verde, el texto verde se pierde.
        _, medidas = temas.problemas_de(tema_valido(**{"senal-suave": "rgba(22, 201, 141, 0.95)"}))
        par = next(m for m in medidas if (m["delante"], m["detras"]) == ("senal", "senal-suave"))
        self.assertFalse(par["ok"])

    def test_el_velo_se_mide_encima_de_su_base_y_no_solo_del_fondo(self):
        # El chip de la banda va en tenue sobre columna + velo: la base importa, y componerlo
        # solo sobre el fondo daría un contraste que el chip no tiene.
        with mock.patch.object(temas, "CONTRASTES",
                               (("tenue", ("columna", "velo"), 4.5, "chip"),)):
            _, medidas = temas.problemas_de(temas._leer(temas.DATOS / "claro.json"))
        self.assertEqual(medidas[0]["contraste"], 5.3)
        self.assertEqual(temas.nombre_de(medidas[0]["detras"]), "velo sobre columna")

    def test_mide_la_opacidad_del_texto_no_solo_su_color(self):
        # dim-label de Adwaita: texto al 55 % sobre el fondo claro. El color a pelo da 17,6:1;
        # con la opacidad, 4,1:1, y por eso no llega a 4,5.
        with mock.patch.object(temas, "CONTRASTES",
                               (("texto", "fondo", 4.5, "dato atenuado", 0.55),)):
            _, medidas = temas.problemas_de(temas._leer(temas.DATOS / "claro.json"))
        self.assertFalse(medidas[0]["ok"])
        self.assertAlmostEqual(medidas[0]["contraste"], 4.09, places=2)
        self.assertIn("4.09:1, pide 4.5:1", temas.fallos(medidas)[0])

    def test_cargar_un_tema_roto_lo_dice(self):
        with self.assertRaises(temas.TemaRoto):
            temas.cargar("no-existe")


class ConLaConfig(unittest.TestCase):

    def test_tema_no_se_confunde_con_un_parametro_de_obsidian(self):
        datos = {"vault": "/x", "tema": "claro"}
        self.assertNotIn("tema", configuracion.parametros(datos, "obsidian"))
        self.assertEqual(configuracion.migrar(datos).get("tema"), "claro")

    def test_sin_tema_en_la_config_se_usa_el_de_defecto(self):
        self.assertEqual(temas.elegido({}), temas.DEFECTO)
        self.assertEqual(temas.elegido({"tema": "claro"}), "claro")


class Verbos(PruebaDeCLI):

    def setUp(self):
        super().setUp()
        self.carpeta = self.config.parent / "temas"

    def config_escrita(self):
        return json.loads(self.config.read_text(encoding="utf-8"))

    def test_lista_los_de_fabrica_y_el_elegido(self):
        codigo, datos = self.correr("temas")
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["elegido"], "oscuro")
        ids = {t["id"]: t for t in datos["temas"]}
        self.assertTrue(ids["oscuro"]["elegido"] and ids["oscuro"]["ok"])
        self.assertEqual(ids["claro"]["esquema"], "claro")
        self.assertEqual(datos["carpeta"], str(self.carpeta))

    def test_nuevo_copia_al_lado_de_la_config_y_no_pisa(self):
        codigo, datos = self.correr("temas", "nuevo", "sepia", "--desde", "claro")
        self.assertEqual(codigo, 0)
        archivo = self.carpeta / "sepia.json"
        self.assertEqual(datos["ruta"], str(archivo))
        self.assertEqual(json.loads(archivo.read_text())["esquema"], "claro")
        self.assertEqual(set(datos["tokens"]), set(temas.TOKENS))
        codigo, datos = self.correr("temas", "nuevo", "sepia")
        self.assertEqual(codigo, 3)
        codigo, _ = self.correr("temas", "nuevo", "oscuro")
        self.assertEqual(codigo, 3)

    def test_comprobar_mide_cada_contraste(self):
        self.correr("temas", "nuevo", "mio")
        codigo, datos = self.correr("temas", "comprobar", "mio")
        self.assertEqual((codigo, datos["ok"]), (0, True))
        self.assertEqual(len(datos["contrastes"]), len(temas.CONTRASTES))

    def test_sin_descripcion_avisa_pero_se_puede_usar(self):
        # Lo que pasó con el primer tema que creó un agente: sin subtítulo en el selector.
        _, nuevo = self.correr("temas", "nuevo", "mio")
        self.assertIn("descripcion", nuevo["nota_para_el_agente"])
        codigo, datos = self.correr("temas", "comprobar", "mio")
        self.assertEqual((codigo, datos["ok"]), (0, True))
        self.assertTrue(any("descripcion" in a for a in datos.get("avisos", [])))
        archivo = self.carpeta / "mio.json"
        tema = json.loads(archivo.read_text())
        tema["descripcion"] = "Para probar."
        archivo.write_text(json.dumps(tema))
        _, datos = self.correr("temas", "comprobar", "mio")
        self.assertNotIn("avisos", datos)

    def test_un_tema_que_no_se_lee_no_se_puede_elegir(self):
        self.correr("temas", "nuevo", "mio")
        archivo = self.carpeta / "mio.json"
        datos = json.loads(archivo.read_text())
        datos["colores"]["tenue"] = "#202226"
        archivo.write_text(json.dumps(datos))
        codigo, respuesta = self.correr("temas", "comprobar", str(archivo))
        self.assertEqual((codigo, respuesta["ok"]), (3, False))
        self.assertEqual(respuesta["errores"], [])
        codigo, respuesta = self.correr("temas", "usar", "mio")
        self.assertEqual(codigo, 3)
        self.assertFalse(self.config.exists())
        _, lista = self.correr("temas")
        mio = next(t for t in lista["temas"] if t["id"] == "mio")
        self.assertFalse(mio["ok"])
        self.assertTrue(any("tenue" in p for p in mio["problemas"]))

    def test_usar_lo_apunta_en_la_config_sin_tocar_lo_demas(self):
        self.config.write_text(json.dumps({"fuente": "obsidian", "enrutador": {"x": 1}}))
        codigo, datos = self.correr("temas", "usar", "claro")
        self.assertEqual((codigo, datos["cambio"]), (0, True))
        self.assertEqual(self.config_escrita(),
                         {"fuente": "obsidian", "enrutador": {"x": 1}, "tema": "claro"})
        _, datos = self.correr("temas", "usar", "claro")
        self.assertFalse(datos["cambio"])
        _, lista = self.correr("temas")
        self.assertEqual(lista["elegido"], "claro")

    def test_uno_propio_no_tapa_a_uno_de_fabrica(self):
        self.carpeta.mkdir()
        roto = tema_valido(texto="#101114")
        (self.carpeta / "oscuro.json").write_text(json.dumps(roto))
        self.assertEqual(temas.cargar("oscuro")["colores"]["texto"], "#FFFFFF")
        codigo, datos = self.correr("temas", "comprobar", str(self.carpeta / "oscuro.json"))
        self.assertTrue(any("fábrica" in a for a in datos.get("avisos", [])))

    def test_config_validar_avisa_de_un_tema_elegido_que_no_existe(self):
        self.config.write_text(json.dumps({"tema": "fantasma"}))
        codigo, datos = self.correr("config", "validar")
        self.assertEqual(codigo, 0)
        self.assertTrue(any("fantasma" in a for a in datos["avisos"]))

    def test_temas_no_arranca_la_ventana(self):
        # Ya no hay lista de verbos sin interfaz que mantener: la ventana solo se abre con sus
        # opciones (`tareas/board.py`), y que `temas` corra sin GTK de verdad lo comprueba
        # `pruebas/test_nucleo_sin_gtk.py` ejecutándolo.
        from tareas.board import es_del_board
        self.assertFalse(es_del_board(["temas"]))
        self.assertFalse(es_del_board(["temas", "comprobar", "oscuro"]))


if __name__ == "__main__":
    unittest.main()
