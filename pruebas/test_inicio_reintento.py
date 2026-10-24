"""Reintentar o rehacer el inicio no duplica (v1.3.0, cotejo-uh9s2m).

«El agente» va guionizado con los mismos verbos del prompt de inicio, dos veces seguidas sobre
el mismo repo, con otros títulos en el segundo intento (como pasó de verdad). Todo corre en un
proceso aparte con HOME y XDG_* en un tmp; no se lanza ningún agente.
"""

import dataclasses
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from apoyo import RAIZ
from tareas import almacen, arquitectura, inicio, reintento
from enrutador import preparar

PIEZAS = ("--pieza", "ve|Pantalla|Lo que ve la gente||", "--pieza", "guarda|Datos|El menú|JSON|")


class ReintentoDelInicio(unittest.TestCase):

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        base = Path(temporal.name)
        self.casa = base / "casa"
        self.casa.mkdir()
        self.carpeta = base / "proyectos" / "menu"
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("COTEJO_", "FOCO_"))}
        self.env.update(HOME=str(self.casa), XDG_CONFIG_HOME=str(base / "config"),
                        XDG_STATE_HOME=str(base / "estado"), XDG_DATA_HOME=str(base / "datos"),
                        PYTHONPATH=str(RAIZ), COTEJO_FUENTE="repo")
        self.repo = str(self.carpeta)

    def cotejo(self, *args, **entorno):
        hecho = subprocess.run([sys.executable, "-m", "tareas", *args], cwd=self.casa,
                               env={**self.env, **entorno}, capture_output=True, text=True,
                               timeout=60)
        self.assertEqual(hecho.returncode, 0, f"{args}: {hecho.stderr}{hecho.stdout}")
        return json.loads(hecho.stdout)

    def intento(self, titulos, previas=""):
        """Los verbos del prompt, en orden. Devuelve los ids de las decisiones propuestas."""
        entorno = {reintento.ENV_PROPUESTAS_PREVIAS: previas} if previas else {}
        self.cotejo("init", "--repo", self.repo)
        ids = [self.cotejo("proponer", "decision", "--repo", self.repo, "--titulo", titulo,
                           "--temas", temas, "--texto", "Razón.", **entorno)
               for titulo, temas in titulos]
        arq = self.cotejo("anotar", "arquitectura", "--repo", self.repo, "--titulo",
                          "Arquitectura", "--temas", "arquitectura", "--texto", "Cómo se hablan.",
                          *PIEZAS)
        for tarea in ("Estructura: la página base", "Datos: el JSON del menú"):
            self.cotejo("crear", tarea, "--proyecto", "menu", "--version", "0.1.0")
        return ids, arq

    def alm(self):
        return almacen.Almacen(self.carpeta)

    def estados(self):
        return sorted((e.estado for e in self.alm().entradas("decision")))

    def test_dos_intentos_dejan_un_solo_juego(self):
        primero, _ = self.intento([("Stack del menú digital", "stack,propuesta"),
                                   ("Dónde viven los datos", "datos"),
                                   ("Qué queda fuera", "alcance")])
        previas = ",".join(p["id"] for p in primero)
        segundo, arq = self.intento([("Stack: web estática ligera", "stack"),
                                     ("Datos del menú en un JSON", "datos,propuesta"),
                                     ("Fuera de la 0.1.0: clientes", "alcance")], previas)
        self.assertTrue(all("reemplazada" in d for d in segundo), segundo)
        self.assertEqual(self.estados(), ["propuesta"] * 3 + ["reemplazada"] * 3)
        contexto = self.cotejo("contexto", "--repo", self.repo)
        self.assertCountEqual(contexto["decisiones_propuestas"], [d["id"] for d in segundo])
        self.assertEqual(len(self.alm().entradas("arquitectura")), 1)
        self.assertTrue(arq.get("actualizada"))
        tareas = (self.carpeta / ".cotejo" / "tareas.md").read_text()
        self.assertEqual(tareas.count("Estructura: la página base"), 1)
        self.assertEqual(tareas.count("Datos: el JSON del menú"), 1)

    def test_lo_aceptado_no_se_toca(self):
        primero, _ = self.intento([("Stack", "stack"), ("Datos", "datos")])
        aceptada = self.alm().leer(primero[0]["id"])
        self.alm().poner_estado(aceptada.id, aceptada.version, "aceptada")
        antes = self.alm().leer(aceptada.id).version
        previas = ",".join(p["id"] for p in primero)
        # La id aceptada aunque viniera en la variable: solo se reemplazan las `propuesta`.
        self.intento([("Stack: otra vez", "stack"), ("Datos otra vez", "datos")], previas)
        despues = self.alm().leer(aceptada.id)
        self.assertEqual((despues.estado, despues.version), ("aceptada", antes))
        # una aceptada, dos propuestas nuevas, la propuesta vieja reemplazada
        self.assertEqual(self.estados(), ["aceptada", "propuesta", "propuesta", "reemplazada"])

    def test_sin_la_variable_nada_cambia(self):
        self.intento([("Stack", "stack")])
        self.intento([("Stack otra", "stack")])
        self.assertEqual(self.estados(), ["propuesta", "propuesta"])  # uso normal intacto

    def test_dos_decisiones_del_mismo_intento_no_se_pisan(self):
        primero, _ = self.intento([("A", "stack")])
        previas = primero[0]["id"]
        self.intento([("B", "stack"), ("C", "stack")], previas)
        self.assertEqual(self.estados(), ["propuesta", "propuesta", "reemplazada"])

    def test_arquitectura_se_actualiza_y_conserva_tareas_enlazadas(self):
        self.intento([("A", "stack")])
        arq = self.alm().entradas("arquitectura")[0]
        piezas = [dataclasses.replace(p, tareas=("cotejo-abc123",)) if p.nombre == "Pantalla"
                  else p for p in arquitectura.analizar(arq.cuerpo).piezas]
        self.cotejo("editar", arq.id, "--repo", self.repo, "--version", arq.version,
                    "--texto", "Cómo se hablan.\n\n" + arquitectura.tabla(piezas))
        # el enlace a una tarea se conserva si el reintento vuelve a anotar la misma pieza
        self.cotejo("anotar", "arquitectura", "--repo", self.repo, "--titulo", "Otra",
                    "--texto", "x", *PIEZAS)
        self.assertEqual(len(self.alm().entradas("arquitectura")), 1)
        reescrita = self.alm().entradas("arquitectura")[0]
        enlazada = [p for p in arquitectura.analizar(reescrita.cuerpo).piezas
                    if p.nombre == "Pantalla"][0]
        self.assertEqual(enlazada.tareas, ("cotejo-abc123",))


class PromptYPuerta(unittest.TestCase):

    def respuestas(self, carpeta):
        return inicio.Respuestas(que_es="Un menú", que_hace="Mostrar la carta", carpeta=carpeta)

    def test_el_prompt_mira_antes_lo_que_hay(self):
        prompt = inicio.armar(self.respuestas("/tmp/menu"))
        self.assertIn("cotejo contexto --repo /tmp/menu", prompt)
        self.assertIn("## Si ya hay algo", prompt)
        self.assertNotIn(inicio.MARCA_REINTENTO, prompt)

    def test_para_reintento_es_idempotente(self):
        prompt = inicio.armar(self.respuestas("/tmp/menu"))
        una = inicio.para_reintento(prompt)
        self.assertTrue(una.startswith(inicio.MARCA_REINTENTO))
        self.assertEqual(inicio.para_reintento(una), una)
        self.assertTrue(una.endswith(prompt))

    def test_marcar_propuestas_previas_solo_las_propuestas(self):
        with tempfile.TemporaryDirectory() as tmp:
            alm = almacen.Almacen(tmp)
            a = alm.crear("decision", "Una", "x", temas=["stack"])
            b = alm.crear("decision", "Dos", "x", temas=["datos"])
            alm.poner_estado(b.id, b.version, "aceptada")
            registro = {"carpeta": tmp, "entorno": {"COTEJO_FUENTE": "repo"}}
            self.assertEqual(preparar.marcar_propuestas_previas(registro), [a.id])
            self.assertEqual(registro["entorno"][reintento.ENV_PROPUESTAS_PREVIAS], a.id)
            self.assertEqual(registro["entorno"]["COTEJO_FUENTE"], "repo")
            alm.poner_estado(a.id, alm.leer(a.id).version, "aceptada")
            preparar.marcar_propuestas_previas(registro)
            self.assertNotIn(reintento.ENV_PROPUESTAS_PREVIAS, registro["entorno"])

    def test_rehacer_prompt_pide_no_repetir(self):
        texto = inicio.armar_rehacer("/tmp/menu", "dec-abcd", "Stack", "no me gusta")
        self.assertIn("No repitas lo que ya existe", texto)


if __name__ == "__main__":
    unittest.main()
