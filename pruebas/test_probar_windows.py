"""`herramientas/probar_windows.sh` y su humo (`herramientas/humo_windows.py`), sin Windows.

El humo de verdad solo corre en la máquina Windows (`probar_windows.sh` contra `ssh win`); aquí
se prueba lo que no depende de ella: el entorno con que se abre el board de la rama (el mismo
que pone el lanzador), la config del agente falso, cómo se cuentan los procesos que cuelgan del
board, cómo se resumen las latencias en el JSON y que el script arme su plan sin conectarse.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from apoyo import RAIZ

from herramientas import humo_windows as humo

SCRIPT = RAIZ / "herramientas" / "probar_windows.sh"
INST = r"C:\Users\U\AppData\Local\Programs\Cotejo"
CODIGO = r"C:\Users\U\AppData\Local\Temp\cotejo-prueba\rama\codigo"

# Lo esencial de un humo.json de verdad (contra win, 04-nov): el formato que leen 72a7di y gckm21.
EJEMPLO = {
    "esquema": 1, "ok": True, "error": None,
    "agente": {"lanzado": True, "termino": True, "pid": 592},
    "conhost": {"antes": 5, "despues": 5, "max_durante": 6, "nuevos": 9, "nuevos_del_board": 9,
                "abiertos_por": {"git.exe": 8, "python.exe": 1}},
    "terminal": {"ventanas_nuevas": 8, "procesos_antes": 0, "procesos_despues": 0},
    "bloqueo": {"peor_ms": 5000, "colgada": True, "bucle_peor_hueco_ms": 9578.5,
                "soltar_ms": 9549.2},
    "al_salir": {"procesos": [{"pid": 13996, "nombre": "gdbus.exe"}]},
    "volcados": ["bloqueo-01.txt"],
}


class Entorno(unittest.TestCase):
    def test_el_board_de_la_rama_corre_con_el_entorno_del_lanzador(self):
        base = {"PATH": r"C:\Windows", "PYTHONHOME": r"C:\otro", "MSYSTEM": "MINGW64",
                "PYTHONPATH": r"C:\otro\lib", "HOME": "x"}
        entorno = humo.entorno_del_lanzador(INST, CODIGO, base)
        self.assertEqual(entorno["PYTHONPATH"], CODIGO)
        self.assertNotIn("PYTHONHOME", entorno)
        self.assertNotIn("MSYSTEM", entorno)   # con él, el Python de MSYS2 cambia a `/`
        self.assertEqual(entorno["PYTHONSAFEPATH"], "1")
        self.assertEqual(entorno["PYTHONNOUSERSITE"], "1")
        self.assertEqual(entorno["GDK_WIN32_PER_MONITOR_HIDPI"], "1")
        self.assertTrue(entorno["GDK_PIXBUF_MODULEDIR"].startswith(INST + r"\runtime\lib"))
        self.assertEqual(entorno["PATH"],
                         INST + r"\bin;" + INST + r"\runtime\bin;" + r"C:\Windows")
        self.assertEqual(entorno["HOME"], "x")
        self.assertIn("PYTHONHOME", base)   # no toca el que le pasan

    def test_las_variables_coinciden_con_las_de_lanzador_c(self):
        # Si el lanzador gana una variable, el humo también debería ponerla.
        fuente = (RAIZ / "empaquetado" / "windows" / "lanzador.c").read_text(encoding="utf-8")
        import re
        puestas = set(re.findall(r'(?:SetEnvironmentVariableW|poner)\(L"([A-Z_0-9]+)"', fuente))
        entorno = humo.entorno_del_lanzador(INST, CODIGO, {"PATH": ""})
        for variable in puestas:
            if variable in ("PYTHONHOME", "MSYSTEM"):
                self.assertNotIn(variable, entorno)
            else:
                self.assertIn(variable, entorno, variable)

    def test_el_humo_usa_sus_carpetas_y_el_gancho_de_volcado_solo_si_se_pide(self):
        carpeta = Path("C:/t/humo")
        entorno = humo.entorno_del_humo(carpeta, 8)
        self.assertEqual(entorno["COTEJO_CONFIG"], str(carpeta / "config.json"))
        self.assertEqual(entorno["COTEJO_VAULT"], str(carpeta / "vault"))
        self.assertEqual(entorno["COTEJO_ESTADO"], str(carpeta / "estado"))
        self.assertEqual(entorno["COTEJO_WORKTREES"], str(carpeta / "wt"))
        self.assertEqual(entorno["FALSO_ESPERA"], "8")
        self.assertNotIn("COTEJO_HUMO_VOLCAR_MS", entorno)
        self.assertNotIn("COTEJO_HUMO_FAULTHANDLER_S", entorno)
        con = humo.entorno_del_humo(carpeta, 8, volcar_ms=500, faulthandler_s=2.5)
        self.assertEqual(con["COTEJO_HUMO_VOLCAR_MS"], "500")
        self.assertEqual(con["COTEJO_HUMO_FAULTHANDLER_S"], "2.5")

    def test_la_config_lanza_el_cliente_falso_con_el_python_de_consola(self):
        config = humo.config_humo("C:/t/humo", INST + r"\runtime\bin\python.exe",
                                  CODIGO + r"\pruebas\cliente_falso.py")
        enrutador = config["enrutador"]
        self.assertEqual(enrutador["proyectos"], {humo.PROYECTO: str(Path("C:/t/humo/repo"))})
        comando = enrutador["motores"]["headless"]["comando"]
        self.assertTrue(comando[0].endswith("python.exe"))   # de consola, como un CLI de verdad
        self.assertTrue(comando[1].endswith("cliente_falso.py"))
        self.assertFalse(enrutador["motores"]["headless"]["aislar"])
        self.assertTrue((RAIZ / "pruebas" / "cliente_falso.py").exists())

    def test_al_cerrar_trabajando_el_falso_va_detras_de_un_cmd_como_uno_de_npm(self):
        config = humo.config_humo("C:/t/humo", INST + r"\runtime\bin\python.exe",
                                  CODIGO + r"\pruebas\cliente_falso.py", por_cmd=True)
        comando = config["enrutador"]["motores"]["headless"]["comando"]
        self.assertEqual(comando[:2], ["cmd.exe", "/c"])
        self.assertTrue(comando[2].endswith("python.exe"))
        entorno = humo.entorno_del_humo(Path("C:/t/humo"), 60, al_cerrar="parar")
        self.assertEqual(entorno["COTEJO_HUMO_AL_CERRAR"], "parar")
        self.assertNotIn("COTEJO_HUMO_AL_CERRAR", humo.entorno_del_humo(Path("C:/t"), 8))

    def test_el_arbol_del_agente_es_lo_suyo_vivo(self):
        procesos = [{"pid": 2, "ppid": 1, "nombre": "cmd.exe"},
                    {"pid": 3, "ppid": 2, "nombre": "python.exe"},
                    {"pid": 4, "ppid": 1, "nombre": "git.exe"},
                    {"pid": 5, "ppid": 2, "nombre": "conhost.exe"}]
        vistos = {2: "cmd.exe", 3: "python.exe", 4: "git.exe", 5: "conhost.exe",
                  6: "python.exe"}   # el 6 ya no está
        self.assertEqual(humo.arbol_del_agente(procesos, vistos),
                         [{"pid": 2, "nombre": "cmd.exe"}, {"pid": 3, "nombre": "python.exe"}])

    def test_seguir_lo_que_queda_dice_cuanto_tardo_cada_uno(self):
        reloj = [0.0]
        fotos = [  # gdbus se va a los 3 s; el python, nunca
            [{"pid": 7, "nombre": "gdbus.exe"}, {"pid": 8, "nombre": "python.exe"}],
            [{"pid": 7, "nombre": "gdbus.exe"}, {"pid": 8, "nombre": "python.exe"}],
            [{"pid": 8, "nombre": "python.exe"}]]

        def foto():
            return fotos[min(int(reloj[0] // 1.5), len(fotos) - 1)]

        def dormir(s):
            reloj[0] += s

        hecho = humo.seguir_hasta_que_se_vayan(foto, {7: "gdbus.exe", 8: "python.exe",
                                                      9: "git.exe"},
                                               gracia_s=10, paso=1.5, reloj=lambda: reloj[0],
                                               dormir=dormir)
        self.assertEqual(hecho["al_instante"], [{"pid": 7, "nombre": "gdbus.exe"},
                                                {"pid": 8, "nombre": "python.exe"}])
        self.assertEqual(hecho["procesos"], [{"pid": 8, "nombre": "python.exe"}])
        self.assertEqual(hecho["tardaron_s"], {"gdbus.exe": 3.0})

    def test_sin_nada_vivo_no_espera(self):
        dormido = []
        hecho = humo.seguir_hasta_que_se_vayan(lambda: [], {7: "gdbus.exe"},
                                               dormir=dormido.append)
        self.assertEqual((hecho["procesos"], dormido), ([], []))

    def test_la_nota_trae_una_tarea_con_modelo_y_su_id(self):
        nota = humo.nota_humo()
        linea = next(l for l in nota.splitlines() if l.startswith("- [ ]"))
        self.assertIn(f"^{humo.TAREA}", linea)
        self.assertIn("#agente/sonnet", linea)   # con modelo: soltarla en Haciendo la lanza


class Procesos(unittest.TestCase):
    FOTO = [{"pid": 4, "ppid": 0, "nombre": "System"},
            {"pid": 100, "ppid": 4, "nombre": "pythonw.exe"},   # el board
            {"pid": 101, "ppid": 100, "nombre": "git.exe"},
            {"pid": 102, "ppid": 101, "nombre": "conhost.exe"},
            {"pid": 103, "ppid": 100, "nombre": "python.exe"},
            {"pid": 104, "ppid": 103, "nombre": "conhost.exe"},
            {"pid": 200, "ppid": 4, "nombre": "conhost.exe"},   # de otra cosa
            {"pid": 0, "ppid": 0, "nombre": "Idle"}]

    def test_descendientes_sigue_el_arbol_entero_y_no_cuenta_la_raiz(self):
        self.assertEqual(humo.descendientes(self.FOTO, 100), {101, 102, 103, 104})
        self.assertEqual(humo.descendientes(self.FOTO, 103), {104})
        self.assertEqual(humo.descendientes(self.FOTO, 999), set())

    def test_un_pid_reciclado_no_mete_a_otro_programa_en_el_arbol(self):
        # El board (10) recibió el pid del padre muerto de Chrome: los chrome.exe tienen ppid 10
        # pero nacieron antes que él. Su git (11) nació después: ese sí es suyo.
        procesos = [{"pid": 11, "ppid": 10}, {"pid": 20, "ppid": 10}, {"pid": 21, "ppid": 20}]
        nacio = {10: 500, 11: 600, 20: 100, 21: 120}
        self.assertEqual(humo.descendientes(procesos, 10, nacio.get), {11})
        self.assertEqual(humo.descendientes(procesos, 10), {11, 20, 21})   # sin fechas, todos
        # Uno que ya salió (sin fecha) cuenta: era suyo, y ya no se puede cerrar.
        self.assertEqual(humo.descendientes(procesos + [{"pid": 12, "ppid": 10}], 10, nacio.get),
                         {11, 12})

    def test_un_ciclo_de_pids_reusados_no_cuelga(self):
        foto = [{"pid": 1, "ppid": 2, "nombre": "a"}, {"pid": 2, "ppid": 1, "nombre": "b"}]
        self.assertEqual(humo.descendientes(foto, 1), {2})

    def test_contar_y_por_nombre(self):
        self.assertEqual(humo.contar(self.FOTO, "conhost.exe"), 3)
        self.assertEqual(humo.por_nombre(["git.exe", "python.exe", "git.exe"]),
                         {"git.exe": 2, "python.exe": 1})
        self.assertEqual(list(humo.por_nombre(["b", "a", "c", "c"])), ["c", "a", "b"])

    def test_de_terminal_solo_las_visibles_de_una_terminal(self):
        ventanas = [{"clase": "CASCADIA_HOSTING_WINDOW_CLASS", "visible": True},
                    {"clase": "ConsoleWindowClass", "visible": True},
                    {"clase": "ConsoleWindowClass", "visible": False},
                    {"clase": "gdkSurfaceToplevel", "visible": True}]
        self.assertEqual([v["clase"] for v in humo.de_terminal(ventanas)],
                         ["CASCADIA_HOSTING_WINDOW_CLASS", "ConsoleWindowClass"])


class Bloqueo(unittest.TestCase):
    def test_sin_respuesta_cuenta_como_el_tope_y_marca_colgada(self):
        muestras = [(1.0, 3.0), (2.0, None), (3.0, 150.0)]
        r = humo.resumen_bloqueo(muestras, colgada_vista=False)
        self.assertEqual(r["peor_ms"], humo.TOPE_MS)
        self.assertTrue(r["colgada"])
        self.assertFalse(r["is_hung_app_window"])
        self.assertEqual(r["sin_respuesta_en_tope"], 1)
        self.assertEqual((r["mas_de_100ms"], r["mas_de_250ms"], r["mas_de_1000ms"]), (2, 1, 1))
        self.assertEqual(r["muestras"], 3)

    def test_separa_lo_de_antes_y_despues_de_soltar_la_carta(self):
        muestras = [(1.0, 900.0), (5.0, 20.0), (6.0, 40.5)]
        r = humo.resumen_bloqueo(muestras, False, {"peor_hueco_ms": 30.0, "soltar_ms": 12.0},
                                 soltar_en=4.0)
        self.assertEqual(r["peor_ms"], 900.0)
        self.assertEqual(r["peor_ms_desde_soltar"], 40.5)
        self.assertFalse(r["colgada"])
        self.assertEqual(r["bucle_peor_hueco_ms"], 30.0)
        self.assertEqual(r["soltar_ms"], 12.0)
        self.assertIsNone(r["bucle_peor_hueco_desde_soltar_ms"])

    def test_sin_muestras_no_inventa_numeros(self):
        r = humo.resumen_bloqueo([], True)
        self.assertIsNone(r["peor_ms"])
        self.assertIsNone(r["peor_ms_desde_soltar"])
        self.assertTrue(r["colgada"])   # IsHungAppWindow la vio colgada

    def test_el_resultado_vacio_trae_todas_las_secciones(self):
        vacio = humo.resultado_vacio()
        for clave in ("agente", "conhost", "terminal", "bloqueo", "al_cerrar", "al_salir",
                      "limpieza", "volcados"):
            self.assertIn(clave, vacio)
        self.assertFalse(vacio["ok"])
        self.assertEqual(vacio["esquema"], humo.ESQUEMA)
        json.dumps(vacio)


class Resumen(unittest.TestCase):
    def correr(self, *argumentos):
        return subprocess.run([sys.executable, str(RAIZ / "herramientas" / "humo_windows.py"),
                               *argumentos], capture_output=True, text=True, timeout=30)

    def test_la_linea_dice_los_numeros(self):
        linea = humo.resumen_legible(EJEMPLO)
        for trozo in ("humo ok", "conhost 5→5 (nuevos 9, del board 9)", "terminales nuevas 8",
                      "peor bloqueo 5000 ms", "soltar la carta 9549.2 ms", "colgada=True",
                      "quedan al salir 1", "volcados 1"):
            self.assertIn(trozo, linea)

    def test_la_linea_dice_lo_del_cierre_con_el_agente_trabajando(self):
        datos = dict(EJEMPLO, al_cerrar={
            "board_vivo": False, "procesos": [],
            "agente": {"respuesta": "parar", "pregunto": ["cotejo-humo-win"],
                       "antes": [{"pid": 2, "nombre": "cmd.exe"},
                                 {"pid": 3, "nombre": "python.exe"}], "vivos": []}},
            temporales=[])
        linea = humo.resumen_legible(datos)
        datos["al_salir"] = {"procesos": [], "tardaron_s": {"gdbus.exe": 3.1}}
        self.assertIn("se fueron solos tras salir: gdbus.exe 3.1 s", humo.resumen_legible(datos))
        for trozo in ("al cerrar: board vivo=False, quedan 0",
                      "cerrar trabajando (parar): agente 2→0 vivos", ".tmp en lanzados 0"):
            self.assertIn(trozo, linea)

    def test_resumen_por_la_linea_de_comandos_y_su_codigo(self):
        with tempfile.TemporaryDirectory() as carpeta:
            bueno = Path(carpeta) / "humo.json"
            bueno.write_text(json.dumps(EJEMPLO), encoding="utf-8")
            hecho = self.correr("resumen", str(bueno))
            self.assertEqual(hecho.returncode, 0, hecho.stderr)
            self.assertIn("terminales nuevas 8", hecho.stdout)
            malo = Path(carpeta) / "malo.json"
            malo.write_text(json.dumps(dict(EJEMPLO, ok=False, error="sin ventana")),
                            encoding="utf-8")
            hecho = self.correr("resumen", str(malo))
            self.assertEqual(hecho.returncode, 1)
            self.assertIn("FALLÓ: sin ventana", hecho.stdout)
            self.assertEqual(self.correr("resumen", str(Path(carpeta) / "no")).returncode, 2)

    @unittest.skipIf(sys.platform == "win32", "en Windows sí corre")
    def test_vigilar_fuera_de_windows_se_niega(self):
        hecho = self.correr("vigilar", "--carpeta", "x", "--instalacion", "y")
        self.assertEqual(hecho.returncode, 2)
        self.assertIn("solo corre en Windows", hecho.stderr)


class Suite(unittest.TestCase):
    CORTADA = ("test_a (test_x.A.test_a) ... ok\n"
               "test_b (test_x.A.test_b) ... ERROR\n"
               "test_c (test_x.A.test_c) ... aviso de por medio\nok\n"
               "test_d (test_y.B.test_d) ... skipped 'sin git'\n"
               "test_e (test_y.B.test_e) ... ")

    def test_una_suite_cortada_dice_donde_murio_y_que_codigo_es(self):
        r = humo.resumen_suite(self.CORTADA, 0xC0000374)
        self.assertFalse(r["terminada"])
        self.assertEqual((r["ok"], r["omitidas"]), (2, 1))
        self.assertEqual(r["fallos"], ["ERROR: test_x.A.test_b"])
        self.assertEqual(r["ultima"], "test_y.B.test_e")
        texto = humo.resumen_suite_legible(r)
        self.assertIn("NO TERMINÓ: murió en test_y.B.test_e", texto)
        self.assertIn("HEAP_CORRUPTION", texto)

    def test_una_suite_entera_usa_su_informe(self):
        texto = ("test_a (m.A.test_a) ... ok\ntest_b (m.A.test_b) ... FAIL\n\n"
                 "======\nFAIL: test_b (m.A.test_b)\n------\nRan 2 tests in 0.1s\n\n"
                 "FAILED (failures=1)\n")
        r = humo.resumen_suite(texto, 1)
        self.assertTrue(r["terminada"])
        self.assertEqual(r["fallos"], ["FAIL: test_b (m.A.test_b)"])
        self.assertIn("Ran 2 tests", humo.resumen_suite_legible(r))
        self.assertNotIn("NO TERMINÓ", humo.resumen_suite_legible(r))

    def test_la_orden_de_la_suite(self):
        self.assertEqual(humo.orden_de_la_suite("py.exe"),
                         ["py.exe", "-m", "unittest", "discover", "-v", "-s", "pruebas"])
        self.assertEqual(humo.orden_de_la_suite("py.exe", "test_a*.py")[-2:],
                         ["-p", "test_a*.py"])


@unittest.skipIf(sys.platform == "win32", "el script es de bash, para correr desde Linux")
class Script(unittest.TestCase):
    def correr(self, *argumentos):
        entorno = {k: v for k, v in os.environ.items() if k != "SSH_AUTH_SOCK"}
        return subprocess.run(["bash", str(SCRIPT), *argumentos], capture_output=True,
                              text=True, timeout=30, env=entorno, cwd=RAIZ)

    def test_la_sintaxis_es_de_bash(self):
        hecho = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(hecho.returncode, 0, hecho.stderr)

    def test_en_seco_dice_el_plan_sin_conectarse(self):
        hecho = self.correr("--en-seco", "--host", "nadie.invalid", "--patron", "test_escala.py",
                            "--espera", "3", "--volcar-ms", "500")
        self.assertEqual(hecho.returncode, 0, hecho.stderr)
        self.assertIn("host: nadie.invalid", hecho.stdout)
        self.assertIn("-m unittest discover -v -s pruebas -p test_escala.py", hecho.stdout)
        self.assertIn("vigilar --espera 3 --volcar-ms 500", hecho.stdout)
        self.assertIn("cotejo-prueba", hecho.stdout)

    def test_solo_una_parte(self):
        suite = self.correr("--en-seco", "--solo", "suite").stdout
        self.assertIn("suite:", suite)
        self.assertNotIn("humo:", suite)
        solo_humo = self.correr("--en-seco", "--solo", "humo").stdout
        self.assertNotIn("suite:", solo_humo)
        self.assertIn("humo:", solo_humo)

    def test_lo_que_no_vale_se_rechaza_antes_de_conectarse(self):
        for argumentos in (["--nada"], ["--solo", "todo-y-mas"], ["--espera", "8; rm"],
                           ["--patron", "x'; Remove-Item"], ["--cerrar-trabajando", "x"]):
            hecho = self.correr("--en-seco", *argumentos)
            self.assertEqual(hecho.returncode, 2, argumentos)

    def test_la_ayuda_sale_de_la_cabecera(self):
        hecho = self.correr("--help")
        self.assertEqual(hecho.returncode, 0)
        self.assertIn("--volcar-ms", hecho.stdout)
        self.assertIn("schtasks /it", hecho.stdout)


if __name__ == "__main__":
    unittest.main()
