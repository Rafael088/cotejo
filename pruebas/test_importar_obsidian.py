"""`cotejo importar obsidian` en ensayo (v1.2, D1): de una nota del vault a un plan de `.cotejo/`.

Todo contra un vault de mentira con la plantilla de proyecto del vault de verdad. Lo que se
vigila: que cada sección vaya al tipo que le toca, que lo que no encaja salga en sin-clasificar
con su motivo y no se pierda, que el repo se resuelva sin inventarse uno, que el `origen` sea
estable (de eso depende que aplicar dos veces no duplique) y, sobre todo, que no se escriba nada.
"""

import json
import tempfile
from unittest import mock
from pathlib import Path

from apoyo import PruebaDeCLI, nota
from tareas import almacen
from tareas.importar_obsidian import NoSeImporta, SIN_CLASIFICAR, _titulo_corto, planear

# La plantilla `_Plantillas/Proyecto.md` del vault, recién creada: no debe salir nada de ella.
PLANTILLA = nota(
    "---", "tipo: proyecto", "estado: idea", "stack: []", "repo: ", "tags:", "  - proyecto",
    "---", "", "# Vacío", "", "> [!abstract] En una frase", "> Qué es y para quién.", "",
    "## 🎯 Objetivo", "¿Qué problema resuelve?", "",
    "## ✅ Tareas", "- [ ] Definir alcance", "- [ ] ", "",
    "## 🧠 Decisiones técnicas",
    "> Una línea por decisión: **qué** se decidió, **por qué**, y qué se descartó.", "",
    "| Fecha | Decisión | Motivo | Alternativas descartadas |", "| --- | --- | --- | --- |",
    "|  |  |  |  |", "",
    "## 📓 Bitácora", "### 2026-10-04", "- ", "",
    "## 🪤 Problemas y soluciones", "| Problema | Causa | Solución |", "| --- | --- | --- |",
    "|  |  |  |", "",
    "## 💡 Aprendizajes", "- ", "",
    "## 🔗 Enlaces", "- Repo: ", "",
    "## ⏭️ Siguiente paso", "- ")

LLENA = nota(
    "---", "tipo: proyecto", "estado: activo", "repo: ", "tags:", "  - proyecto", "---", "",
    "# App", "", "> [!abstract] En una frase", "> Una app.", "",
    "## 🎯 Objetivo", "Que funcione.", "",
    "## 🧱 Stack y arquitectura", "Python.", "", "```md", "## esto no es una sección", "```", "",
    "## ✅ Tareas", "- [ ] Hacer algo #medio ^cotejo-aaaa01", "- [x] Hecho ^cotejo-aaaa02", "",
    "## 🧠 Decisiones técnicas", "> La instrucción de la plantilla.", "",
    "| Fecha | Decisión | Motivo | Alternativas descartadas |", "| --- | --- | --- | --- |",
    "| 2026-09-16 | Usar `LD_PRELOAD` en GTK | Si no, no carga | Nada |",
    "| sin fecha | Sin `os.replace` no se escribe | Atómico |  |",
    "|  |  |  |  |", "",
    "Un párrafo suelto que no es una fila.", "",
    "## 📓 Bitácora", "Antes del primer día.", "### 2026-10-03", "- Empecé.", "",
    "### 2026-10-04", "- Seguí con [[Otra nota]].", "", "### Sin fecha", "- Algo.", "",
    "## 🪤 Problemas y soluciones", "| Problema | Causa | Solución |", "| --- | --- | --- |",
    "| Se caía | Un bug | Arreglado |", "| Va lento | ? |  |", "",
    "## 💡 Aprendizajes", "- Medir, no estimar. Siempre.", "  Con una segunda línea.",
    "- Otro aprendizaje", "",
    "## 🎨 Marca", "Colores y voz.", "",
    "## 🔗 Enlaces", "- Logo: ![[logo.png]]", "- Diagrama: [[flujo.excalidraw|el flujo]]",
    "- Plan: [[App - Planning v1.2]]", "- Falta: ![[no-esta.png]]", "",
    "## ⏭️ Siguiente paso", "Seguir.")


class PruebaImportar(PruebaDeCLI):

    def setUp(self):
        super().setUp()
        self.escribir_nota("App/App.md", LLENA)
        self.escribir_nota("App/App - Planning v1.2.md", "# Plan\n\nAlgo.\n")
        self.escribir_nota("App/archivo/Viejo.md", "---\ntags:\n  - historia\n---\n# Viejo\n\nYa.\n")
        # Un repo dentro de la carpeta del proyecto, como Cotejo: sus .md no son subnotas.
        self.repo = self.vault / self.CARPETA / "App" / "app-src"
        (self.repo / ".git").mkdir(parents=True)
        (self.repo / "README.md").write_text("# Código\n", encoding="utf-8")
        (self.repo / "node_modules").mkdir()
        modulos = self.vault / self.CARPETA / "App" / "web" / "node_modules" / "x"
        modulos.mkdir(parents=True)
        (modulos / "README.md").write_text("# Ajeno\n", encoding="utf-8")
        (self.vault / self.CARPETA / "App" / "web" / "index.js").write_text("1", encoding="utf-8")
        (self.vault / self.CARPETA / "App" / "flujo.excalidraw").write_text("{}", encoding="utf-8")
        adjuntos = self.vault / "99-Adjuntos"
        adjuntos.mkdir()
        (adjuntos / "logo.png").write_bytes(b"\x89PNG")
        # Una subnota fuera de la carpeta que se declara del proyecto por su frontmatter.
        (self.vault / "04-Recursos").mkdir()
        (self.vault / "04-Recursos" / "Investigación.md").write_text(
            '---\nproyecto: "[[App]]"\n---\n# Investigación\n\nDatos.\n', encoding="utf-8")
        (self.vault / "04-Recursos" / "Ajena.md").write_text(
            '---\nproyecto: "[[Otro]]"\n---\n# Ajena\n', encoding="utf-8")

    def plan(self, nombre="App", destino=None):
        return planear(self.vault, self.CARPETA, nombre, destino)

    def de_tipo(self, plan, tipo):
        return [e for e in plan.entradas if e.tipo == tipo]

    def foto(self, *raices):
        """Todo lo que hay bajo las raíces, con su contenido: para ver que no cambió nada."""
        return {str(p): p.read_bytes() for r in raices if r.exists()
                for p in sorted(Path(r).rglob("*")) if p.is_file()}


class Reparto(PruebaImportar):

    def test_las_decisiones_salen_de_las_filas_aceptadas_e_importadas(self):
        decisiones = self.de_tipo(self.plan(), "decision")
        self.assertEqual([d.titulo for d in decisiones],
                         ["Usar LD_PRELOAD en GTK", "Sin os.replace no se escribe"])
        primera = decisiones[0]
        self.assertEqual(primera.campos, {"estado": "aceptada", "autor": "importado",
                                          "fecha": "2026-09-16"})
        self.assertIn("**Por qué:** Si no, no carga", primera.texto)
        self.assertIn("**Descartado:** Nada", primera.texto)
        self.assertNotIn("fecha", decisiones[1].campos)  # «sin fecha» no es una fecha

    def test_los_dos_puntos_no_cortan_el_titulo(self):
        # cotejo-1j0w3y: «v1.1: diff…» quedaba en «v1.1» porque `:` cerraba la frase.
        self.assertEqual(_titulo_corto("v1.1: diff de la revisión contra la base. Y más."),
                         "v1.1: diff de la revisión contra la base")
        self.assertEqual(_titulo_corto("Fuera de la 1.1: fuente compuesta"),
                         "Fuera de la 1.1: fuente compuesta")
        self.assertEqual(_titulo_corto("Medir, no estimar. Siempre."), "Medir, no estimar")
        self.assertEqual(_titulo_corto("¿Por qué? Porque sí"), "¿Por qué?")

    def test_una_decision_con_dos_puntos_conserva_su_titulo(self):
        con_dos_puntos = LLENA.replace("| sin fecha | Sin `os.replace` no se escribe |",
                                       "| sin fecha | v1.1: diff de la revisión. Más |")
        self.escribir_nota("App/App.md", con_dos_puntos)
        decisiones = self.de_tipo(self.plan(), "decision")
        self.assertEqual(decisiones[1].titulo, "v1.1: diff de la revisión")

    def test_los_problemas_con_solucion_salen_resueltos(self):
        problemas = {p.titulo: p.campos["estado"] for p in self.de_tipo(self.plan(), "problema")}
        self.assertEqual(problemas, {"Se caía": "resuelto", "Va lento": "abierto"})

    def test_los_aprendizajes_son_las_vinetas_con_su_continuacion(self):
        aprendizajes = self.de_tipo(self.plan(), "aprendizaje")
        self.assertEqual([a.titulo for a in aprendizajes], ["Medir, no estimar", "Otro aprendizaje"])
        self.assertIn("Con una segunda línea.", aprendizajes[0].texto)

    def test_la_bitacora_es_un_dia_por_fecha(self):
        dias = self.de_tipo(self.plan(), "bitacora")
        self.assertEqual([(d.titulo, d.campos["fecha"]) for d in dias],
                         [("2026-10-03", "2026-10-03"), ("2026-10-04", "2026-10-04")])
        self.assertIn("[[Otra nota]]", dias[1].texto)

    def test_las_tareas_se_copian_con_sus_ids_y_se_cuentan(self):
        plan = self.plan()
        self.assertEqual(plan.tareas, 2)
        self.assertIn("- [ ] Hacer algo #medio ^cotejo-aaaa01", plan.tareas_md)
        self.assertIn("- [x] Hecho ^cotejo-aaaa02", plan.tareas_md)

    def test_proyecto_md_junta_la_cabecera_y_las_secciones_del_proyecto(self):
        texto = self.plan().proyecto_md
        for trozo in ("# App", "Una app.", "## 🎯 Objetivo", "## 🧱 Stack y arquitectura",
                      "## esto no es una sección", "## 🔗 Enlaces", "## ⏭️ Siguiente paso"):
            self.assertIn(trozo, texto)
        self.assertNotIn("Decisiones", texto)

    def test_lo_que_no_encaja_va_a_sin_clasificar_con_su_motivo(self):
        sin = {e.titulo: e for e in self.plan().sin_clasificar()}
        self.assertEqual(set(sin), {"🎨 Marca", "🧠 Decisiones técnicas", "📓 Bitácora",
                                    "📓 Bitácora: Sin fecha"})
        self.assertEqual(sin["🎨 Marca"].texto, "Colores y voz.")
        self.assertIn("plantilla", sin["🎨 Marca"].motivo)
        self.assertEqual(sin["🧠 Decisiones técnicas"].texto, "Un párrafo suelto que no es una fila.")
        for entrada in sin.values():
            self.assertEqual(entrada.tipo, "referencia")
            self.assertEqual(entrada.campos["resumen"], almacen.PENDIENTE)
            self.assertEqual(entrada.temas, [SIN_CLASIFICAR])

    def test_la_plantilla_vacia_no_produce_nada(self):
        self.escribir_nota("Vacío.md", PLANTILLA)
        plan = self.plan("Vacío", destino=str(self.vault / "destino"))
        self.assertEqual(plan.entradas, [])
        self.assertEqual(plan.tareas, 1)  # «- [ ] Definir alcance»; la vacía no cuenta

    def test_los_origenes_son_estables_y_unicos(self):
        uno, dos = self.plan(), self.plan()
        origenes = [e.origen for e in uno.entradas]
        self.assertEqual(origenes, [e.origen for e in dos.entradas])
        self.assertEqual(len(origenes), len(set(origenes)))
        # Relativos al vault, sin rutas de esta máquina: el origen viaja con el repo.
        self.assertFalse([o for o in origenes if o.startswith("/") or str(self.vault) in o])


class NotasYAdjuntos(PruebaImportar):

    def test_subnotas_de_la_carpeta_y_por_frontmatter_sin_repos_ni_node_modules(self):
        plan = self.plan()
        self.assertEqual(plan.subnotas, ["01-Proyectos/App/App - Planning v1.2.md",
                                         "01-Proyectos/App/archivo/Viejo.md",
                                         "04-Recursos/Investigación.md"])
        referencias = {e.titulo: e for e in self.de_tipo(plan, "referencia")
                       if SIN_CLASIFICAR not in e.temas}
        self.assertEqual(referencias["Viejo"].texto, "Ya.")
        self.assertEqual(referencias["Viejo"].temas, ["historia"])
        self.assertEqual(referencias["Viejo"].campos["resumen"], "pendiente")

    def test_solo_los_adjuntos_enlazados_son_recursos(self):
        plan = self.plan()
        recursos = {e.campos["archivo"]: e.origen for e in self.de_tipo(plan, "recurso")}
        self.assertEqual(recursos, {"flujo.excalidraw": "01-Proyectos/App/flujo.excalidraw",
                                    "logo.png": "99-Adjuntos/logo.png"})
        # Una nota con punto en el nombre es una nota, no un adjunto.
        self.assertNotIn("App - Planning v1.2", recursos)

    def test_un_adjunto_que_no_esta_es_un_aviso(self):
        avisos = self.plan().avisos
        self.assertEqual([a["motivo"] for a in avisos],
                         ["enlaza «no-esta.png», que no está en el vault"])

    def test_lo_suelto_que_no_se_enlaza_se_cuenta_por_carpeta_y_no_se_importa(self):
        plan = self.plan()
        self.assertEqual(plan.no_enlazados, {"web": 1})
        self.assertNotIn("index.js", [e.titulo for e in plan.entradas])


class Repo(PruebaImportar):

    def test_un_repo_en_una_subcarpeta_es_el_destino(self):
        self.assertEqual(self.plan().repo, {"ruta": str(self.repo.resolve()),
                                            "como": "subcarpeta", "git_init": False})

    def test_repo_local_en_el_frontmatter(self):
        otro = self.vault / "fuera" / "repo"
        (otro / ".git").mkdir(parents=True)
        self.escribir_nota("Sola.md", f"---\ntipo: proyecto\nrepo: {otro}\n---\n# Sola\n")
        self.assertEqual(self.plan("Sola").repo["como"], "repo")

    def test_sin_repo_pide_destino_y_lo_dice(self):
        self.escribir_nota("Sola.md", "---\ntipo: proyecto\nrepo: https://github.com/x/y\n---\n")
        with self.assertRaises(NoSeImporta) as caso:
            self.plan("Sola")
        self.assertIn("https://github.com/x/y", str(caso.exception))
        self.assertIn("--destino", caso.exception.salida)

    def test_el_destino_sin_git_se_anuncia_como_git_init_y_no_se_crea(self):
        destino = self.vault.parent / "nuevo-repo"
        self.escribir_nota("Sola.md", "---\ntipo: proyecto\n---\n# Sola\n")
        plan = self.plan("Sola", destino=str(destino))
        self.assertEqual((plan.repo["como"], plan.repo["git_init"]), ("destino", True))
        self.assertFalse(destino.exists())

    def test_dos_repos_dentro_obligan_a_elegir(self):
        (self.vault / self.CARPETA / "App" / "otro-src" / ".git").mkdir(parents=True)
        with self.assertRaisesRegex(NoSeImporta, "varios repos"):
            self.plan()

    def test_un_proyecto_que_no_existe_sugiere_el_parecido(self):
        with self.assertRaisesRegex(NoSeImporta, "¿Buscabas App"):
            self.plan("Ap")

    def test_el_nombre_no_distingue_mayusculas(self):
        self.assertEqual(self.plan("app").proyecto, "App")

    def test_cuenta_lo_que_el_repo_ya_tiene_importado(self):
        primero = self.plan()
        decision = self.de_tipo(primero, "decision")[0]
        cotejo = almacen.Almacen(self.repo)
        cotejo.crear("decision", decision.titulo, estado="aceptada", origen=decision.origen)
        cotejo.bitacora("x", fecha="2026-10-03")
        resumen = self.plan().resumen()
        self.assertEqual(resumen["ya_importadas"], 2)
        self.assertEqual(resumen["nuevas"], len(primero.entradas) - 2)


class Cli(PruebaImportar):

    def test_el_ensayo_por_la_cli_no_escribe_nada(self):
        antes = self.foto(self.vault)
        codigo, datos = self.correr("importar", "obsidian", "App", "--detalle")
        self.assertEqual(codigo, 0, datos)
        self.assertTrue(datos["ensayo"])
        self.assertEqual(datos["conteo"]["decision"], 2)
        self.assertEqual(datos["conteo"]["tareas"], 2)
        self.assertEqual(len(datos["sin_clasificar"]), 4)
        self.assertEqual(len(datos["entradas"]), datos["nuevas"])
        self.assertIn("no se escribió nada", datos["salida"])
        self.assertEqual(self.foto(self.vault), antes)
        self.assertFalse((self.repo / ".cotejo").exists())

    def test_sin_repo_es_un_error_con_el_siguiente_paso(self):
        self.escribir_nota("Sola.md", "---\ntipo: proyecto\n---\n# Sola\n")
        codigo, datos = self.correr("importar", "obsidian", "Sola")
        self.assertEqual(codigo, 3)
        self.assertIn("--destino", datos["salida"])

    def test_lee_el_vault_aunque_la_fuente_activa_sea_otra(self):
        self.config.write_text(json.dumps({"fuente": "repo"}), encoding="utf-8")
        codigo, datos = self.correr("importar", "obsidian", "App")
        self.assertEqual(codigo, 0, datos)


class Aplicar(PruebaImportar):
    """`--aplicar` (D2): escribe el plan en el repo, sin commit, y marca el proyecto migrado."""

    def aplicar(self, *extra):
        codigo, datos = self.correr("importar", "obsidian", "App", "--aplicar", *extra)
        self.assertEqual(codigo, 0, datos)
        return datos

    def cotejo(self):
        return almacen.Almacen(self.repo)

    def test_escribe_cada_entrada_con_su_tipo_y_su_origen(self):
        datos = self.aplicar()
        self.assertFalse(datos["ensayo"])
        self.assertEqual(datos["escritas"], {"aprendizaje": 2, "bitacora": 2, "decision": 2,
                                             "problema": 2, "recurso": 2, "referencia": 7})
        decisiones = self.cotejo().entradas("decision")
        self.assertEqual({d.estado for d in decisiones}, {"aceptada"})
        self.assertEqual({d.datos["autor"] for d in decisiones}, {"importado"})
        self.assertTrue(all(d.datos["origen"].startswith("01-Proyectos/App/App.md#")
                            for d in decisiones))
        sin = [r for r in self.cotejo().entradas("referencia") if SIN_CLASIFICAR in r.temas]
        self.assertEqual(len(sin), 4)

    def test_pone_version_en_proyecto_md_y_repetirlo_la_deja_igual(self):
        datos = self.aplicar()
        self.assertEqual(datos["version"], {"version": "0.1.0", "hecho": "puesta"})
        self.assertEqual(self.cotejo().leer("proyecto").datos["version"], "0.1.0")
        antes = (self.repo / ".cotejo" / "proyecto.md").read_bytes()
        otra = self.aplicar()
        self.assertEqual(otra["version"]["hecho"], "ya-estaba")
        self.assertEqual((self.repo / ".cotejo" / "proyecto.md").read_bytes(), antes)

    def test_proyecto_tareas_y_bitacora_salen_tal_cual(self):
        self.aplicar()
        proyecto = self.cotejo().leer("proyecto")
        self.assertEqual(proyecto.titulo, "App")
        self.assertIn("## 🎯 Objetivo", proyecto.cuerpo)
        tareas = (self.repo / ".cotejo" / "tareas.md").read_text(encoding="utf-8")
        self.assertIn("- [ ] Hacer algo #medio ^cotejo-aaaa01", tareas)
        self.assertIn("- [x] Hecho ^cotejo-aaaa02", tareas)
        self.assertIn("- Empecé.", self.cotejo().leer("2026-10-03").cuerpo)

    def test_copia_los_adjuntos_con_su_ficha(self):
        self.aplicar()
        recursos = self.repo / ".cotejo" / "recursos"
        self.assertEqual((recursos / "logo.png").read_bytes(), b"\x89PNG")
        self.assertTrue((recursos / "flujo.excalidraw").is_file())
        fichas = {f.datos["archivo"]: f for f in self.cotejo().entradas("recurso")}
        self.assertEqual(set(fichas), {"logo.png", "flujo.excalidraw"})
        self.assertEqual(fichas["logo.png"].datos["ficha"], "pendiente")

    def test_reescribe_los_enlaces(self):
        self.escribir_nota("Otra nota.md", "# De otro proyecto\n")
        self.aplicar()
        proyecto = self.cotejo().leer("proyecto").cuerpo
        self.assertIn("[[app-planning-v1-2|App - Planning v1.2]]", proyecto)
        self.assertIn("![[logo.png]]", proyecto)
        self.assertIn("[[flujo.excalidraw|el flujo]]", proyecto)
        self.assertIn("![[no-esta.png]]", proyecto)  # no está en ningún sitio: igual
        self.assertTrue((self.repo / ".cotejo" / "referencias" / "app-planning-v1-2.md").is_file())
        dia = self.cotejo().leer("2026-10-04").cuerpo
        self.assertIn("Otra nota (vault: Otra nota)", dia)
        self.assertNotIn("[[Otra nota]]", dia)

    def test_repetirlo_no_escribe_nada(self):
        self.aplicar()
        antes = self.foto(self.repo)
        datos = self.aplicar()
        self.assertEqual(datos["escritas"], {})
        self.assertEqual(datos["ya_estaban"], 17)
        self.assertEqual((datos["tareas_md"], datos["proyecto_md"]), ("ya-estaban", "ya-estaba"))
        self.assertEqual(self.foto(self.repo), antes)

    def test_no_toca_el_vault_y_marca_el_proyecto_migrado(self):
        # El repo vive dentro de la carpeta del proyecto (como Cotejo): lo suyo sí cambia.
        def notas():
            return {k: v for k, v in self.foto(self.vault / self.CARPETA,
                                              self.vault / "99-Adjuntos",
                                              self.vault / "04-Recursos").items()
                    if str(self.repo) not in k}
        antes = notas()
        datos = self.aplicar()
        self.assertEqual(notas(), antes)
        self.assertEqual(datos["migrado"], {"App": str(self.repo.resolve())})
        config = json.loads(self.config.read_text(encoding="utf-8"))
        self.assertEqual(config["fuentes"]["obsidian"]["migrados"], datos["migrado"])
        # Y desde ya, App se lee del repo (fuente compuesta), con su tarea de revisión.
        codigo, tareas = self.correr("tareas", "--proyecto", "App")
        self.assertEqual(codigo, 0, tareas)
        self.assertEqual({t["nota"] for t in tareas["tareas"]}, {"app-src/.cotejo/tareas.md"})
        self.assertIn("Revisar lo importado: resúmenes, temas y fichas",
                      [t["texto"] for t in tareas["tareas"]])

    def test_la_tarea_de_revision_no_se_duplica(self):
        self.aplicar()
        self.aplicar()
        tareas = (self.repo / ".cotejo" / "tareas.md").read_text(encoding="utf-8")
        self.assertEqual(tareas.count("Revisar lo importado"), 1)

    def test_un_repo_con_otras_tareas_se_niega_sin_escribir(self):
        (self.repo / ".cotejo").mkdir()
        (self.repo / ".cotejo" / "tareas.md").write_text("- [ ] Otra cosa ^cotejo-otra01\n",
                                                         encoding="utf-8")
        antes = self.foto(self.repo)
        codigo, datos = self.correr("importar", "obsidian", "App", "--aplicar")
        self.assertEqual(codigo, 3)
        self.assertIn("ya tiene tareas", datos["error"])
        self.assertEqual(self.foto(self.repo), antes)
        self.assertFalse(self.config.exists())

    def test_completa_el_proyecto_md_que_deja_init(self):
        self.correr("init", "--repo", str(self.repo))
        datos = self.aplicar()
        self.assertEqual(datos["proyecto_md"], "actualizado")
        self.assertIn("## 🎯 Objetivo", self.cotejo().leer("proyecto").cuerpo)

    def test_un_destino_nuevo_recibe_git_init(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        destino = Path(temporal.name) / "repo-nuevo"
        datos = self.aplicar("--destino", str(destino))
        self.assertTrue(datos["git_init"])
        self.assertTrue((destino / ".git").is_dir())
        self.assertTrue((destino / ".cotejo" / "proyecto.md").is_file())

    def test_en_windows_un_destino_demasiado_largo_para_git_se_niega_sin_crear_nada(self):
        # git no puede tener la raíz de un repo por encima de MAX_PATH en Windows (prueba a
        # mano de F1): mejor decirlo así que con el CalledProcessError crudo de git.
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        destino = Path(temporal.name, *["carpeta con un nombre largo"] * 10, "repo")
        with mock.patch("tareas.rutas.sistema", return_value="windows"):
            codigo, datos = self.correr("importar", "obsidian", "App", "--aplicar",
                                        "--destino", str(destino))
        self.assertEqual(codigo, 3, datos)
        self.assertIn("demasiado larga para git en Windows", datos["error"])
        self.assertFalse(destino.parent.exists())
