"""Integrar conserva las fichas locales de .cotejo/ y recibe el código (cotejo-7kmlvw).

Repos y worktrees reales, sin tocar el repo ni la configuración de quien corre las pruebas.
"""

import os
import unittest
from unittest import mock

from test_integrar_sola import ConRepo
from test_revision import git
from tareas import revision


class IntegrarConFichas(ConRepo):
    def arquitectura(self, texto="# Arquitectura\nApp del restaurante\n"):
        ruta = ".cotejo/arquitectura.md"
        (self.r.repo / ruta).write_text(texto, encoding="utf-8")
        (self.r.worktree / ".cotejo").mkdir(exist_ok=True)
        self.r.trabajar(ruta, texto, "ficha del agente")
        self.r.trabajar()
        return ruta

    def test_arquitectura_nueva_duplicada_en_master_recibe_la_app(self):
        git(self.r.repo, "branch", "-m", "master")
        ruta = self.arquitectura()
        antes = git(self.r.repo, "rev-parse", "HEAD")
        _plan, resultado = self.aprobar()
        self.assertTrue(resultado["integrada"], resultado)
        self.assertTrue(resultado["rama_borrada"])
        self.assertEqual((self.r.repo / "a.txt").read_text(), "uno\nDOS\ntres\n")
        self.assertEqual(git(self.r.repo, "show", f"HEAD:{ruta}"),
                         "# Arquitectura\nApp del restaurante")
        self.assertEqual(git(self.r.repo, "status", "--porcelain"), "")
        self.assertEqual(git(self.r.repo, "rev-parse", "HEAD^1^"), antes)
        # El guardado previo contiene solo las fichas; la app llega en el merge siguiente.
        self.assertEqual(set(git(self.r.repo, "diff-tree", "--no-commit-id", "--name-only",
                                 "-r", "HEAD^1").splitlines()),
                         {ruta, ".cotejo/tareas.md"})

    def test_modificaciones_compatibles_de_ficha_se_juntan(self):
        ruta = ".cotejo/arquitectura.md"
        base = "Título\n\nPrimera sección\n\nSegunda sección\n\nFinal\n"
        (self.r.repo / ruta).write_text(base, encoding="utf-8")
        git(self.r.repo, "add", ".cotejo")
        git(self.r.repo, "commit", "-qm", "ficha base")
        git(self.r.worktree, "merge", "--ff-only", "main")
        (self.r.repo / ruta).write_text(base.replace("Título", "Título del maestro"),
                                       encoding="utf-8")
        self.r.trabajar(ruta, base.replace("Final", "Final del agente"))
        self.r.trabajar()
        _plan, resultado = self.aprobar()
        self.assertTrue(resultado["integrada"], resultado)
        texto = (self.r.repo / ruta).read_text(encoding="utf-8")
        self.assertIn("Título del maestro", texto)
        self.assertIn("Final del agente", texto)

    def test_conflicto_conserva_fichas_de_ambos_lados_y_aborta_la_app(self):
        ruta = self.arquitectura()
        (self.r.repo / ruta).write_text("Arquitectura del maestro\n", encoding="utf-8")
        _plan, resultado = self.aprobar()
        self.assertFalse(resultado["integrada"], resultado)
        self.assertEqual(resultado["causa"], "conflicto")
        self.assertIn(ruta, resultado["archivos"])
        self.assertEqual(git(self.r.repo, "show", f"HEAD:{ruta}"), "Arquitectura del maestro")
        self.assertEqual(git(self.r.repo, "show", f"{self.r.rama}:{ruta}"),
                         "# Arquitectura\nApp del restaurante")
        self.assertEqual((self.r.repo / "a.txt").read_text(), "uno\ndos\n")
        self.assertEqual(git(self.r.repo, "status", "--porcelain"), "")
        self.assertNotEqual(revision._git(self.r.repo, "rev-parse", "--verify", "--quiet",
                                         "MERGE_HEAD")[0], 0)

    def test_guarda_borrados_y_fichas_preparadas_sin_incluir_archivos_ajenos(self):
        self.r.trabajar()
        (self.r.repo / ".cotejo/tareas.md").unlink()
        ficha = self.r.repo / ".cotejo/decisión con espacios.md"
        ficha.write_text("Elegido\n", encoding="utf-8")
        git(self.r.repo, "add", ".cotejo")
        (self.r.repo / "borrador.txt").write_text("No incluir\n", encoding="utf-8")
        _plan, resultado = self.aprobar()
        self.assertTrue(resultado["integrada"], resultado)
        self.assertNotIn(".cotejo/tareas.md", git(self.r.repo, "ls-tree", "-r", "HEAD"))
        self.assertEqual(git(self.r.repo, "show", "HEAD:.cotejo/decisión con espacios.md"),
                         "Elegido")
        self.assertEqual(git(self.r.repo, "status", "--porcelain"), "?? borrador.txt")

    def test_archivos_ignorados_no_se_guardan(self):
        self.r.trabajar()
        (self.r.repo / ".cotejo/.gitignore").write_text("temporal\n", encoding="utf-8")
        (self.r.repo / ".cotejo/temporal").write_text("Ignorado\n", encoding="utf-8")
        _plan, resultado = self.aprobar()
        self.assertTrue(resultado["integrada"], resultado)
        self.assertNotIn(".cotejo/temporal", git(self.r.repo, "ls-tree", "-r", "HEAD"))
        self.assertTrue((self.r.repo / ".cotejo/temporal").exists())

    def test_codigo_preparado_despues_del_plan_impide_el_guardado(self):
        self.arquitectura()
        plan = revision.plan_integracion(self.r.tarea_id, self.r.entregar())
        antes = git(self.r.repo, "rev-parse", "HEAD")
        (self.r.repo / "a.txt").write_text("A medias\n", encoding="utf-8")
        git(self.r.repo, "add", "a.txt")
        resultado = revision.integrar(plan)
        self.assertEqual(resultado["causa"], "sucio")
        self.assertEqual(git(self.r.repo, "rev-parse", "HEAD"), antes)
        self.assertEqual(git(self.r.repo, "diff", "--cached", "--name-only"), "a.txt")

    def test_sin_identidad_guarda_fichas_y_merge_sin_configurar_git(self):
        self.arquitectura()
        with mock.patch.dict(os.environ):
            for clave in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME",
                          "GIT_COMMITTER_EMAIL", "EMAIL"):
                os.environ.pop(clave, None)
            _plan, resultado = self.aprobar()
        self.assertTrue(resultado["integrada"], resultado)
        for commit in ("HEAD", "HEAD^1"):
            self.assertEqual(git(self.r.repo, "show", "-s", "--format=%cn <%ce>", commit),
                             "Cotejo <cotejo@localhost>")
        self.assertNotEqual(revision._git(self.r.repo, "config", "--local", "user.email")[0], 0)

    def test_si_falla_guardar_no_intenta_merge_ni_borra_la_rama(self):
        self.arquitectura()
        antes = git(self.r.repo, "rev-parse", "HEAD")
        original = revision._git

        def falla_commit(repo, *args, **kwargs):
            if "commit" in args:
                return 1, "", "No se pudo crear el commit"
            return original(repo, *args, **kwargs)

        with mock.patch.object(revision, "_git", side_effect=falla_commit) as llamadas:
            _plan, resultado = self.aprobar()
        self.assertFalse(resultado["integrada"], resultado)
        self.assertIn("No pude guardar .cotejo/", resultado["motivo"])
        self.assertFalse(any("merge" in c.args for c in llamadas.call_args_list))
        self.assertEqual(git(self.r.repo, "rev-parse", "HEAD"), antes)
        self.assertIn(self.r.rama, self.ramas())
        self.assertTrue((self.r.repo / ".cotejo/arquitectura.md").exists())
        # El fallo no deja un callejón sin salida: el mismo plan puede reintentarse.
        self.assertTrue(revision.integrar_sola(_plan)["integrada"])

    def test_otro_merge_despues_del_plan_no_se_cierra_con_el_commit_de_fichas(self):
        self.arquitectura()
        plan = revision.plan_integracion(self.r.tarea_id, self.r.entregar())
        antes = git(self.r.repo, "rev-parse", "HEAD")
        marca = self.r.repo / ".git/MERGE_HEAD"
        marca.write_text(git(self.r.repo, "rev-parse", self.r.rama) + "\n")
        resultado = revision.integrar(plan)
        self.assertEqual(resultado["causa"], "a-medias")
        self.assertEqual(git(self.r.repo, "rev-parse", "HEAD"), antes)
        self.assertTrue(marca.exists())


class IntegrarConfirmadoConFichas(ConRepo):
    """El mismo guardado protege también el merge que la persona confirma fuera del Inicio."""

    del_inicio = False

    def test_guardar_fichas_tambien_al_confirmar_sin_borrar_rama(self):
        ruta = ".cotejo/arquitectura.md"
        texto = "Arquitectura compartida\n"
        (self.r.repo / ruta).write_text(texto, encoding="utf-8")
        (self.r.worktree / ".cotejo").mkdir()
        self.r.trabajar(ruta, texto)
        self.r.trabajar()
        plan = revision.plan_integracion(self.r.tarea_id, self.r.entregar())
        self.assertFalse(plan["del_inicio"])
        resultado = revision.integrar(plan)
        self.assertTrue(resultado["integrada"], resultado)
        self.assertIn(self.r.rama, self.ramas())
        self.assertEqual((self.r.repo / "a.txt").read_text(), "uno\nDOS\ntres\n")
        self.assertEqual(git(self.r.repo, "status", "--porcelain"), "")


if __name__ == "__main__":
    unittest.main()
