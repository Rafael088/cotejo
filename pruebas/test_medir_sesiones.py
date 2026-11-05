"""La medición de sesiones de Claude con JSONL falsos y aislados."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from apoyo import RAIZ

from herramientas import medir_sesiones


SCRIPT = RAIZ / "herramientas" / "medir_sesiones.py"


def registro(mensaje_id, instante, entrada, creada=0, leida=0):
    return {
        "type": "assistant",
        "timestamp": instante,
        "message": {
            "id": mensaje_id,
            "role": "assistant",
            "usage": {
                "input_tokens": entrada,
                "cache_creation_input_tokens": creada,
                "cache_read_input_tokens": leida,
                "output_tokens": 99,
            },
        },
    }


class MedirSesiones(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.raiz = Path(self.temporal.name)

    def tearDown(self):
        self.temporal.cleanup()

    def escribir(self, proyecto, sesion, *registros, basura=False):
        carpeta = self.raiz / proyecto
        carpeta.mkdir(parents=True, exist_ok=True)
        lineas = [json.dumps(r) for r in registros]
        if basura:
            lineas.append('{"type": "assistant"')  # última línea aún a medio escribir
        (carpeta / f"{sesion}.jsonl").write_text("\n".join(lineas), encoding="utf-8")

    def test_agrupa_sesiones_y_suma_toda_la_entrada_sin_duplicar_mensajes(self):
        proyecto = "-home-prueba-wt-cotejo-abc123"
        primero = registro("msg-1", "2026-01-01T10:00:00Z", 2, 30, 400)
        self.escribir(proyecto, "sesion-1", primero, primero,
                      registro("msg-2", "2026-01-01T10:01:00Z", 3, 40, 500), basura=True)
        self.escribir(proyecto, "sesion-2",
                      registro("msg-3", "2026-01-02T10:00:00Z", 4, 50, 600))

        tareas = medir_sesiones.medir(self.raiz)

        self.assertEqual([t.entrada for t in tareas["cotejo-abc123"]], [432, 543, 654])
        self.assertEqual(
            medir_sesiones.tabla(tareas),
            "tarea\tprimer_turno\tturnos\tentrada_sumada\n"
            "cotejo-abc123\t432\t3\t1629",
        )

    def test_ignora_otros_proyectos_y_registros_sin_uso(self):
        self.escribir("-home-prueba-proyecto-normal", "otra",
                      registro("msg-otro", "2026-01-01T00:00:00Z", 900))
        self.escribir("-home-prueba-wt-cotejo-vale42", "sesion",
                      {"type": "user", "message": {"role": "user"}},
                      {"type": "assistant", "message": {"id": "sin-uso"}},
                      registro("msg-bien", "2026-01-01T00:00:00Z", 7))

        self.assertEqual(list(medir_sesiones.medir(self.raiz)), ["cotejo-vale42"])

    def test_cli_acepta_una_raiz_temporal(self):
        self.escribir("-home-prueba-wt-cotejo-cli123", "sesion",
                      registro("msg-cli", "2026-01-01T00:00:00Z", 10, 20, 30))

        hecho = subprocess.run(
            [sys.executable, str(SCRIPT), "--raiz", str(self.raiz)],
            cwd=self.raiz,
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(hecho.returncode, 0, hecho.stderr)
        self.assertEqual(
            hecho.stdout,
            "tarea\tprimer_turno\tturnos\tentrada_sumada\n"
            "cotejo-cli123\t60\t1\t60\n",
        )


if __name__ == "__main__":
    unittest.main()
