"""Qué entiende `vault.py` cuando lee el Markdown.

El parseo es la mitad del contrato con el agente: si una tarea no se lee, para Cotejo no existe,
y eso se ve igual que si no estuviera escrita.
"""

import json
import os
from unittest import mock

from apoyo import PruebaConVault, PruebaDeCLI, nota, proyecto

from tareas import modelo
from tareas.fuentes import obsidian


class Vinetas(PruebaConVault):
    def test_lee_las_tareas_con_cualquier_vineta(self):
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Con guion",
            "* [ ] Con asterisco",
            "+ [ ] Con mas",
            "1. [ ] Con numero y punto",
            "2) [ ] Con numero y parentesis",
        ))
        _, tareas = self.tareas_de("Uno")
        self.assertEqual([t.texto for t in tareas],
                         ["Con guion", "Con asterisco", "Con mas",
                          "Con numero y punto", "Con numero y parentesis"])

    def test_no_confunde_una_lista_normal_con_una_tarea(self):
        self.escribir_nota("Uno.md", proyecto("- Esto es una viñeta", "- [ ] Esto sí"))
        _, tareas = self.tareas_de("Uno")
        self.assertEqual([t.texto for t in tareas], ["Esto sí"])

    def test_lee_las_anidadas(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Madre", "  - [ ] Hija"))
        _, tareas = self.tareas_de("Uno")
        self.assertEqual([t.texto for t in tareas], ["Madre", "Hija"])

    def test_ignora_una_tarea_sin_texto(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] ", "- [ ] Con texto"))
        _, tareas = self.tareas_de("Uno")
        self.assertEqual([t.texto for t in tareas], ["Con texto"])

    def test_ignora_una_tarea_que_solo_tiene_tags(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] #en-curso", "- [ ] De verdad"))
        _, tareas = self.tareas_de("Uno")
        self.assertEqual([t.texto for t in tareas], ["De verdad"])


class BloquesDeCodigo(PruebaConVault):
    def test_ignora_las_tareas_dentro_de_un_bloque_de_codigo(self):
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Fuera",
            "```",
            "- [ ] Dentro de comillas",
            "```",
            "- [ ] Fuera otra vez",
        ))
        _, tareas = self.tareas_de("Uno")
        self.assertEqual([t.texto for t in tareas], ["Fuera", "Fuera otra vez"])

    def test_tambien_con_tildes(self):
        self.escribir_nota("Uno.md", proyecto("~~~", "- [ ] Dentro", "~~~", "- [ ] Fuera"))
        _, tareas = self.tareas_de("Uno")
        self.assertEqual([t.texto for t in tareas], ["Fuera"])

    def test_un_bloque_con_lenguaje_tambien_cuenta(self):
        self.escribir_nota("Uno.md", proyecto("```sh", "- [ ] Dentro", "```", "- [ ] Fuera"))
        _, tareas = self.tareas_de("Uno")
        self.assertEqual([t.texto for t in tareas], ["Fuera"])


class Tags(PruebaConVault):
    def test_saca_los_tags_del_texto_y_los_guarda_aparte(self):
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Hacer la cosa #en-curso #agente/opus #dificil"))
        tarea = self.una_tarea()
        self.assertEqual(tarea.texto, "Hacer la cosa")
        self.assertEqual(tarea.estado, "en-curso")
        self.assertEqual(tarea.agente, "opus")
        self.assertEqual(tarea.dificultad, "dificil")

    def test_los_tags_valen_en_cualquier_orden(self):
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Primero #dificil #agente/sonnet #por-validar",
            "- [ ] Segundo #agente/sonnet #por-validar #dificil"))
        _, tareas = self.tareas_de("Uno")
        for tarea in tareas:
            self.assertEqual((tarea.estado, tarea.agente, tarea.dificultad),
                             ("por-validar", "sonnet", "dificil"))

    def test_un_tag_en_medio_del_texto_tambien_se_saca(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Hacer #en-curso la cosa"))
        tarea = self.una_tarea()
        self.assertEqual(tarea.texto, "Hacer la cosa")
        self.assertEqual(tarea.estado, "en-curso")

    def test_una_tarea_sin_tags_queda_pendiente_y_sin_dueno(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Pelada"))
        tarea = self.una_tarea()
        self.assertEqual((tarea.estado, tarea.agente, tarea.dificultad, tarea.sitio.marca),
                         (modelo.PENDIENTE, "", "", ""))

    def test_un_tag_que_empieza_igual_no_cuenta(self):
        # Un guion no es carácter de palabra: sin un límite propio, "#en-curso-de-verdad"
        # colaba como "#en-curso" y movía sola la tarea de columna.
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Con #en-curso-de-verdad y #facilito y #por-validar-luego y #dificilillo"))
        tarea = self.una_tarea()
        self.assertEqual(tarea.estado, modelo.PENDIENTE)
        self.assertEqual(tarea.dificultad, "")
        self.assertEqual(
            tarea.texto,
            "Con #en-curso-de-verdad y #facilito y #por-validar-luego y #dificilillo")


class FechaDeCierre(PruebaConVault):
    """`Tarea.cerrada` (v1.2.2): la fecha que `marcar` escribe al final de la línea, para el
    filtro de fechas de la columna Finalizada (cotejo-r3cs5t). Se lee aparte y no se saca del
    texto: `releida.texto` la sigue mostrando, como antes de que existiera este campo."""

    def test_una_hecha_con_fecha_la_trae_en_cerrada(self):
        self.escribir_nota("Uno.md", proyecto("- [x] Lista — 2026-09-23"))
        _, tareas = self.tareas_de("Uno", incluir_hechas=True)
        tarea = next(t for t in tareas if t.texto.startswith("Lista"))
        self.assertEqual(tarea.cerrada, "2026-09-23")
        self.assertEqual(tarea.texto, "Lista — 2026-09-23")

    def test_una_hecha_sin_fecha_la_deja_en_none(self):
        self.escribir_nota("Uno.md", proyecto("- [x] Sin fecha"))
        _, tareas = self.tareas_de("Uno", incluir_hechas=True)
        tarea = next(t for t in tareas if t.texto == "Sin fecha")
        self.assertIsNone(tarea.cerrada)

    def test_una_pendiente_normal_no_trae_fecha_de_cierre(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Pendiente de verdad"))
        tarea = self.una_tarea()
        self.assertIsNone(tarea.cerrada)


class Marcas(PruebaConVault):
    def test_lee_la_marca_de_bloque_y_no_la_muestra(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Con marca ^cotejo-a1b2c3"))
        tarea = self.una_tarea()
        self.assertEqual(tarea.texto, "Con marca")
        self.assertEqual(tarea.sitio.marca, "cotejo-a1b2c3")

    def test_la_marca_vale_aunque_quede_un_tag_detras(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Con marca ^cotejo-a1b2c3 #en-curso"))
        tarea = self.una_tarea()
        self.assertEqual(tarea.texto, "Con marca")
        self.assertEqual(tarea.sitio.marca, "cotejo-a1b2c3")
        self.assertEqual(tarea.estado, "en-curso")

    def test_acepta_una_marca_puesta_a_mano_sin_el_prefijo(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Mía ^la-mia"))
        self.assertEqual(self.una_tarea().sitio.marca, "la-mia")

    def test_el_id_es_la_marca_cuando_la_tiene(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Con marca ^cotejo-a1b2c3"))
        self.assertEqual(self.una_tarea().id, "cotejo-a1b2c3")

    def test_el_id_cae_a_la_nota_y_la_linea_cuando_no_la_tiene(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Sin marca"))
        tarea = self.una_tarea()
        self.assertEqual(tarea.id, f"01-Proyectos/Uno.md:{tarea.sitio.linea}")


class Estados(PruebaConVault):
    def test_la_columna_sale_del_tag_y_del_check(self):
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Pendiente",
            "- [ ] Haciéndola #en-curso",
            "- [ ] Esperando #por-validar",
            "- [ ] Aprobada #por-integrar",
            "- [x] Finalizada",
        ))
        _, tareas = self.tareas_de("Uno")
        self.assertEqual([t.columna for t in tareas],
                         [modelo.PENDIENTE, "en-curso", "por-validar", "por-validar",
                          modelo.HECHA])
        self.assertEqual(tareas[3].estado, modelo.POR_INTEGRAR)

    def test_una_hecha_no_sale_si_no_se_piden(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Falta", "- [x] Ya está"))
        proyectos = self.escanear(incluir_hechas=False)
        self.assertEqual([t.texto for t in proyectos[0].tareas], ["Falta"])
        self.assertEqual(proyectos[0].hechas, [])

    def test_las_hechas_van_en_su_propia_lista(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Falta", "- [x] Ya está"))
        proyectos = self.escanear()
        self.assertEqual([t.texto for t in proyectos[0].tareas], ["Falta"])
        self.assertEqual([t.texto for t in proyectos[0].hechas], ["Ya está"])

    def test_cualquier_cosa_que_no_sea_espacio_cuenta_como_hecha(self):
        self.escribir_nota("Uno.md", proyecto("- [X] Mayúscula", "- [-] Guion"))
        _, tareas = self.tareas_de("Uno")
        self.assertTrue(all(t.hecha for t in tareas))


class Proyectos(PruebaConVault):
    def test_una_nota_suelta_es_un_proyecto(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Algo"))
        self.assertEqual([p.nombre for p in self.escanear()], ["Uno"])

    def test_una_carpeta_junta_sus_subnotas_en_un_solo_proyecto(self):
        self.escribir_nota("Casa/Casa.md", proyecto("- [ ] De la principal"))
        self.escribir_nota("Casa/Cocina.md", nota("- [ ] De la sub-nota"))
        proyectos = self.escanear()
        self.assertEqual([p.nombre for p in proyectos], ["Casa"])
        self.assertEqual([t.texto for t in proyectos[0].tareas],
                         ["De la principal", "De la sub-nota"])

    def test_omite_las_notas_de_otro_tipo(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Sí"))
        self.escribir_nota("Léeme.md", proyecto("- [ ] No", tipo="nota"))
        self.assertEqual([p.nombre for p in self.escanear()], ["Uno"])

    def test_omite_los_proyectos_terminados_o_descartados(self):
        self.escribir_nota("Vivo.md", proyecto("- [ ] Sí", estado="activo"))
        self.escribir_nota("Muerto.md", proyecto("- [ ] No", estado="terminado"))
        self.escribir_nota("Roto.md", proyecto("- [ ] No", estado="descartado"))
        self.assertEqual([p.nombre for p in self.escanear()], ["Vivo"])

    def test_omite_archivos_y_carpetas_ocultos(self):
        self.escribir_nota(".Oculto.md", proyecto("- [ ] No"))
        self.escribir_nota("_Plantilla.md", proyecto("- [ ] Tampoco"))
        self.escribir_nota("Uno.md", proyecto("- [ ] Sí"))
        self.assertEqual([p.nombre for p in self.escanear()], ["Uno"])

    def test_ordena_por_estado_luego_prioridad_luego_nombre(self):
        self.escribir_nota("Pausado.md", proyecto("- [ ] x", estado="pausado"))
        self.escribir_nota("Idea.md", proyecto("- [ ] x", estado="idea"))
        self.escribir_nota("ActivoBaja.md", proyecto("- [ ] x", estado="activo", prioridad="baja"))
        self.escribir_nota("ActivoAlta.md", proyecto("- [ ] x", estado="activo", prioridad="alta"))
        self.assertEqual([p.nombre for p in self.escanear()],
                         ["ActivoAlta", "ActivoBaja", "Idea", "Pausado"])

    def test_el_frontmatter_admite_comillas(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] x", estado='"activo"', prioridad="'alta'"))
        uno = self.escanear()[0]
        self.assertEqual((uno.estado, uno.prioridad), ("activo", "alta"))


class Buscar(PruebaConVault):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] Con marca ^cotejo-aaa111",
                                              "- [ ] Sin marca"))

    def test_encuentra_por_marca(self):
        proyecto_, tarea = modelo.buscar(self.escanear(), "cotejo-aaa111")
        self.assertEqual(tarea.texto, "Con marca")
        self.assertEqual(proyecto_.nombre, "Uno")

    def test_acepta_la_marca_con_el_acento_circunflejo_delante(self):
        # Quién limpia el "^" es la fuente: cómo se escribe una referencia a una tarea es cosa
        # suya, no del modelo, que solo compara ids ya normalizados.
        _, tarea = modelo.buscar(self.escanear(), self.fuente.normalizar_id("^cotejo-aaa111"))
        self.assertEqual(tarea.texto, "Con marca")

    def test_encuentra_por_nota_y_linea_cuando_no_hay_marca(self):
        proyectos = self.escanear()
        sin_marca = next(t for t in proyectos[0].tareas if t.texto == "Sin marca")
        _, tarea = modelo.buscar(proyectos, sin_marca.id)
        self.assertEqual(tarea.texto, "Sin marca")

    def test_un_id_que_no_existe_devuelve_nada(self):
        self.assertEqual(modelo.buscar(self.escanear(), "cotejo-nohay"), (None, None))

    def test_un_id_ambiguo_se_niega_en_vez_de_elegir(self):
        # Dos notas pueden toparse: la marca se genera única dentro de una nota, no del vault.
        self.escribir_nota("Dos.md", proyecto("- [ ] La otra ^cotejo-aaa111"))
        with self.assertRaises(modelo.IdAmbiguo) as caso:
            modelo.buscar(self.escanear(), "cotejo-aaa111")
        self.assertIn("Uno.md", str(caso.exception))
        self.assertIn("Dos.md", str(caso.exception))


class Resumen(PruebaConVault):
    def test_cuenta_los_estados_por_separado(self):
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Pendiente", "- [ ] Haciéndola #en-curso",
            "- [ ] Esperando #por-validar", "- [x] Hecha"))
        datos = modelo.resumen(self.escanear())
        self.assertEqual(datos["pendientes"], 3)  # todo lo que no está marcado
        self.assertEqual(datos["en_curso"], 1)
        self.assertEqual(datos["por_validar"], 1)
        self.assertEqual(datos["hechas"], 1)
        self.assertEqual(datos["proyectos"], 1)

    def test_un_proyecto_sin_pendientes_no_cuenta_como_proyecto(self):
        self.escribir_nota("Uno.md", proyecto("- [x] Todo hecho"))
        self.assertEqual(modelo.resumen(self.escanear())["proyectos"], 0)

    def test_el_top_se_queda_en_cuatro(self):
        for i in range(6):
            self.escribir_nota(f"P{i}.md", proyecto("- [ ] x"))
        self.assertEqual(len(modelo.resumen(self.escanear())["top"]), 4)


class Rarezas(PruebaConVault):
    def test_lee_acentos_y_emojis(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Añadir el símbolo 🎯 a la cabecera"))
        self.assertEqual(self.una_tarea().texto, "Añadir el símbolo 🎯 a la cabecera")

    def test_una_nota_ilegible_no_tumba_el_escaneo(self):
        self.escribir_nota("Rota.md", None, binario=b"\xff\xfe\x00 tareas")
        self.escribir_nota("Uno.md", proyecto("- [ ] Sí"))
        proyectos = self.escanear()
        self.assertEqual([p.nombre for p in proyectos], ["Rota", "Uno"])
        self.assertEqual(next(p for p in proyectos if p.nombre == "Uno").tareas[0].texto, "Sí")

    def test_una_carpeta_de_proyectos_que_no_existe_no_revienta(self):
        fuente = obsidian.Obsidian({"vault": str(self.vault), "carpeta_proyectos": "No-existe"})
        self.assertEqual(fuente.escanear(), [])

    def test_un_vault_que_no_existe_es_un_problema_y_no_un_vault_vacio(self):
        # Escanear da [] en los dos casos, y la app no distinguía «no hay tareas» de «no hay
        # de dónde leerlas»: la lista decía «Todo al día» con la ruta mal escrita.
        ruta = self.vault / "no-existe"
        with mock.patch.dict(os.environ, {"COTEJO_VAULT": str(ruta)}):
            fuente = obsidian.Obsidian()
        self.assertIn("no existe", fuente.problema)
        ruta.mkdir()
        self.assertIsNone(fuente.problema, "si la carpeta aparece, deja de ser un problema")

    def test_el_texto_conserva_el_markdown_de_dentro(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Usar `poner_estado()` y **no** otra cosa"))
        self.assertEqual(self.una_tarea().texto, "Usar `poner_estado()` y **no** otra cosa")


class Avisos(PruebaConVault):
    """Lo que no se pudo leer tiene que poder contarse. Una nota que desaparece del board sin
    explicación se ve exactamente igual que una nota que nunca tuvo tareas."""

    def escanear_con_avisos(self):
        avisos = []
        proyectos = self.fuente.escanear(incluir_hechas=True, avisos=avisos)
        return proyectos, avisos

    def test_avisa_de_una_nota_que_no_es_utf8(self):
        self.escribir_nota("Rota.md", None, binario=b"\xff\xfe\x00 tareas")
        _, avisos = self.escanear_con_avisos()
        self.assertEqual(len(avisos), 1)
        self.assertEqual(avisos[0]["nota"], "01-Proyectos/Rota.md")
        self.assertIn("UTF-8", avisos[0]["motivo"])

    def test_avisa_de_una_nota_que_no_se_puede_abrir(self):
        ruta = self.escribir_nota("Cerrada.md", proyecto("- [ ] No se lee"))
        ruta.chmod(0o000)
        self.addCleanup(ruta.chmod, 0o644)
        _, avisos = self.escanear_con_avisos()
        self.assertEqual(avisos[0]["nota"], "01-Proyectos/Cerrada.md")
        self.assertIn("no pude abrirla", avisos[0]["motivo"])

    def test_no_repite_el_aviso_de_la_nota_principal(self):
        # Se lee dos veces, una para el frontmatter y otra para las tareas.
        self.escribir_nota("Rota.md", None, binario=b"\xff\xfe tareas")
        _, avisos = self.escanear_con_avisos()
        self.assertEqual(len(avisos), 1)

    def test_avisa_de_una_subnota_de_un_proyecto_carpeta(self):
        self.escribir_nota("Casa/Casa.md", proyecto("- [ ] Se lee"))
        self.escribir_nota("Casa/Rota.md", None, binario=b"\xff\xfe tareas")
        proyectos, avisos = self.escanear_con_avisos()
        self.assertEqual([t.texto for t in proyectos[0].tareas], ["Se lee"])
        self.assertEqual(avisos[0]["nota"], "01-Proyectos/Casa/Rota.md")

    def test_sin_problemas_no_hay_avisos(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Todo bien"))
        _, avisos = self.escanear_con_avisos()
        self.assertEqual(avisos, [])

    def test_quien_no_pasa_la_lista_sigue_funcionando_igual(self):
        self.escribir_nota("Rota.md", None, binario=b"\xff\xfe tareas")
        self.escribir_nota("Uno.md", proyecto("- [ ] Sí"))
        self.assertEqual([p.nombre for p in self.fuente.escanear()], ["Rota", "Uno"])


# Una nota diaria como la de `_Plantillas/Plantilla Diaria.md` y una captura como las que
# deja `sb.py inbox`: frontmatter que no es de proyecto, y tareas sueltas bajo cualquier título.
DIARIA = nota("---", "tipo: diario", "fecha: 2026-09-22", "tags:", "  - diario", "---", "",
              "# 2026-09-22", "", "## 🎯 Cotejo de hoy", "- Acabar Cotejo", "",
              "## ⏭️ Mañana", "- [ ] Llamar al proveedor", "- [ ] ", "- [x] Pagar el dominio")
CAPTURA = nota("---", "tipo: captura", "fecha: 2026-09-23", "tags:", "  - inbox", "---", "",
               "# Capturas 2026-09-23", "", "- una idea sin tarea", "- [ ] Revisar el correo")


class CarpetasSueltas(PruebaConVault):
    """`00-Inbox` y `06-Diario` no son proyectos, pero sus `- [ ]` son tareas. Cada carpeta
    sale como un proyecto sintético, y cada nota como una sub-nota."""

    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] Del proyecto", estado="activo"))
        for ruta, texto in (("06-Diario/2026-09-22.md", DIARIA),
                            ("00-Inbox/2026-09-23.md", CAPTURA)):
            (self.vault / ruta).parent.mkdir(parents=True, exist_ok=True)
            (self.vault / ruta).write_text(texto, encoding="utf-8")

    def fuente_con(self, sueltas, **config):
        return obsidian.Obsidian({"vault": str(self.vault), "carpeta_proyectos": self.CARPETA,
                                  "carpetas_sueltas": sueltas, **config})

    def test_por_defecto_no_se_leen(self):
        self.assertEqual([p.nombre for p in self.escanear()], ["Uno"])

    def test_cada_carpeta_es_un_proyecto_con_el_nombre_sin_numero(self):
        proyectos = self.fuente_con(["00-Inbox", "06-Diario"]).escanear()
        self.assertEqual([p.nombre for p in proyectos], ["Uno", "Diario", "Inbox"])

    def test_cada_nota_es_una_sub_nota_y_la_fecha_sale_de_etiqueta(self):
        diario = next(p for p in self.fuente_con(["06-Diario"]).escanear(incluir_hechas=True)
                      if p.nombre == "Diario")
        self.assertEqual([(t.texto, t.sub) for t in diario.tareas],
                         [("Llamar al proveedor", "2026-09-22")])
        self.assertEqual([t.texto for t in diario.hechas], ["Pagar el dominio"])
        self.assertEqual(diario.tareas[0].donde, "06-Diario/2026-09-22.md")
        self.assertEqual(diario.donde, "06-Diario")

    def test_van_detras_de_los_proyectos_de_verdad(self):
        # Sin estado ni prioridad: son el cajón de lo que aún no tiene proyecto.
        self.escribir_nota("Zeta.md", proyecto("- [ ] z", estado="pausado"))
        nombres = [p.nombre for p in self.fuente_con(["00-Inbox"]).escanear()]
        self.assertEqual(nombres, ["Uno", "Zeta", "Inbox"])

    def test_una_carpeta_sin_tareas_no_sale(self):
        (self.vault / "05-Archivo").mkdir()
        (self.vault / "05-Archivo" / "Vieja.md").write_text("- sin tareas\n", encoding="utf-8")
        nombres = [p.nombre for p in self.fuente_con(["05-Archivo", "No-existe"]).escanear()]
        self.assertEqual(nombres, ["Uno"])

    def test_si_el_nombre_ya_es_de_un_proyecto_se_queda_con_el_de_la_carpeta(self):
        self.escribir_nota("Inbox.md", proyecto("- [ ] Proyecto que se llama Inbox"))
        nombres = {p.nombre for p in self.fuente_con(["00-Inbox"]).escanear()}
        self.assertEqual(nombres, {"Uno", "Inbox", "00-Inbox"})

    def test_no_sale_del_vault(self):
        fuente = self.fuente_con(["../fuera", "/etc", "", "00-Inbox/"])
        self.assertEqual(fuente.carpetas_sueltas, ["00-Inbox"])

    def test_la_carpeta_de_proyectos_no_se_lee_dos_veces(self):
        nombres = [p.nombre for p in self.fuente_con([self.CARPETA]).escanear()]
        self.assertEqual(nombres, ["Uno"])

    def test_la_variable_de_entorno_manda_sobre_la_config(self):
        with mock.patch.dict(os.environ, {"COTEJO_CARPETAS_SUELTAS": "00-Inbox"}):
            self.assertEqual(self.fuente_con(["06-Diario"]).carpetas_sueltas, ["00-Inbox"])
        with mock.patch.dict(os.environ, {"COTEJO_CARPETAS_SUELTAS": ""}):
            self.assertEqual(self.fuente_con(["06-Diario"]).carpetas_sueltas, [])

    def test_se_vigilan_para_recargar_el_board(self):
        vigiladas = self.fuente_con(["06-Diario"]).vigilables()
        self.assertIn(str(self.vault / "06-Diario"), vigiladas)
        self.assertIn(str(self.vault / self.CARPETA), vigiladas)

    def test_se_escriben_como_cualquier_otra_tarea(self):
        fuente = self.fuente_con(["00-Inbox"])
        inbox = next(p for p in fuente.escanear() if p.nombre == "Inbox")
        tarea = fuente.poner_estado(inbox.tareas[0], "en-curso")
        texto = (self.vault / "00-Inbox" / "2026-09-23.md").read_text(encoding="utf-8")
        self.assertIn(f"- [ ] Revisar el correo #en-curso ^{tarea.id}", texto)
        self.assertIn("tipo: captura", texto)  # el resto de la nota, intacto


class CarpetasSueltasEnLaCLI(PruebaDeCLI):
    """Lo que prometen las carpetas sueltas es que el resto de Cotejo no note la diferencia:
    se listan, se toman, se entregan y se cuentan en `estado.json` como las de un proyecto."""

    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] Del proyecto", estado="activo"))
        (self.vault / "06-Diario").mkdir()
        (self.vault / "06-Diario" / "2026-09-22.md").write_text(DIARIA, encoding="utf-8")
        parche = mock.patch.dict(os.environ, {"COTEJO_CARPETAS_SUELTAS": "06-Diario"})
        parche.start()
        self.addCleanup(parche.stop)

    def test_tareas_la_lista_con_su_proyecto_sintetico(self):
        _, datos = self.correr("tareas", "--proyecto", "Diario", "--estado", "pendiente")
        self.assertEqual([(t["texto"], t["proyecto"], t["nota"]) for t in datos["tareas"]],
                         [("Llamar al proveedor", "Diario", "06-Diario/2026-09-22.md")])

    def test_se_toma_y_se_entrega(self):
        _, datos = self.correr("tareas", "--proyecto", "Diario", "--estado", "pendiente")
        id_ = datos["tareas"][0]["id"]
        codigo, tomada = self.correr("tomar", id_, "--agente", "opus")
        self.assertEqual(codigo, 0)
        id_ = tomada["tarea"]["id"]
        codigo, entregada = self.correr("entregar", id_, "--evidencia", "hecho")
        self.assertEqual(codigo, 0)
        self.assertEqual(entregada["tarea"]["estado"], "por-validar")
        texto = (self.vault / "06-Diario" / "2026-09-22.md").read_text(encoding="utf-8")
        linea = next(l for l in texto.splitlines() if "Llamar al proveedor" in l)
        self.assertTrue(linea.startswith("- [ ] Llamar al proveedor"))
        for trozo in ("#por-validar", "#agente/opus", f"^{id_}"):
            self.assertIn(trozo, linea)

    def test_estado_json_las_cuenta(self):
        self.correr("estado")
        datos = json.loads(self.archivo_estado.read_text(encoding="utf-8"))
        self.assertEqual(datos["pendientes"], 2)
        self.assertEqual([p["nombre"] for p in datos["top"]], ["Uno", "Diario"])

    def test_plan_las_reparte_como_a_las_demas(self):
        codigo, datos = self.correr("plan", "--proyecto", "Diario")
        self.assertEqual(codigo, 0)
        self.assertEqual([t["texto"] for t in datos["tareas"]], ["Llamar al proveedor"])


class ReposAnidados(PruebaConVault):
    """La carpeta de un proyecto puede llevar dentro el código (otro proyecto con su código dentro): sus
    READMEs, CHANGELOGs y `node_modules` tienen casillas que no son tareas de nadie."""

    def setUp(self):
        super().setUp()
        self.escribir_nota("Casa/Casa.md", proyecto("- [ ] De la principal"))
        self.escribir_nota("Casa/Ideas/Cocina.md", nota("- [ ] De una sub-nota"))

    def textos(self):
        _, tareas = self.tareas_de("Casa")
        return [t.texto for t in tareas]

    def test_no_lee_las_notas_de_un_repo_anidado(self):
        self.escribir_nota("Casa/web/README.md", nota("- [ ] Del README"))
        self.escribir_nota("Casa/web/docs/guia.md", nota("- [ ] De la guía"))
        (self.vault / self.CARPETA / "Casa/web/.git").mkdir()
        self.assertEqual(self.textos(), ["De la principal", "De una sub-nota"])

    def test_tambien_si_su_git_es_un_archivo(self):
        # Así lo deja un worktree o un submódulo.
        self.escribir_nota("Casa/web/README.md", nota("- [ ] Del README"))
        self.escribir_nota("Casa/web/.git", "gitdir: /otro/sitio/.git/worktrees/web\n")
        self.assertEqual(self.textos(), ["De la principal", "De una sub-nota"])

    def test_no_lee_node_modules_aunque_no_haya_repo(self):
        self.escribir_nota("Casa/app/node_modules/paquete/CHANGELOG.md", nota("- [ ] Del paquete"))
        self.escribir_nota("Casa/app/notas.md", nota("- [ ] De app"))
        self.assertEqual(self.textos(), ["De la principal", "De app", "De una sub-nota"])

    def test_un_proyecto_que_es_un_repo_se_sigue_leyendo(self):
        # El `.git` que se salta es el de una subcarpeta, no el de la carpeta del proyecto.
        (self.vault / self.CARPETA / "Casa/.git").mkdir()
        self.assertEqual(self.textos(), ["De la principal", "De una sub-nota"])

    def test_no_vigila_las_carpetas_que_salta(self):
        self.escribir_nota("Casa/web/README.md", nota("- [ ] Del README"))
        (self.vault / self.CARPETA / "Casa/web/.git").mkdir()
        self.escribir_nota("Casa/app/node_modules/p/README.md", nota("x"))
        vigiladas = {os.path.relpath(r, self.vault / self.CARPETA)
                     for r in self.fuente.vigilables()}
        self.assertIn(os.path.join("Casa", "Ideas"), vigiladas)
        self.assertIn(os.path.join("Casa", "app"), vigiladas)
        self.assertFalse({v for v in vigiladas if "web" in v or "node_modules" in v})

    def test_las_carpetas_sueltas_tampoco(self):
        from tareas.fuentes.obsidian import Obsidian
        (self.vault / "00-Inbox/clon/.git").mkdir(parents=True)
        (self.vault / "00-Inbox/clon/README.md").write_text("- [ ] Del clon\n", encoding="utf-8")
        (self.vault / "00-Inbox/Captura.md").write_text("- [ ] Capturada\n", encoding="utf-8")
        fuente = Obsidian({"vault": str(self.vault), "carpeta_proyectos": self.CARPETA,
                           "carpetas_sueltas": ["00-Inbox"]})
        inbox = next(p for p in fuente.escanear() if p.nombre == "Inbox")
        self.assertEqual([t.texto for t in inbox.tareas], ["Capturada"])
