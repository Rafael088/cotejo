"""Que ningún módulo crezca hasta no poder leerse de una vez.

`tareas/app.py` pasó de 1.320 a 3.721 líneas en tres semanas (2026-09-18 → 2026-10-10), casi
1.000 de ellas en un día: cada cosa nueva del board caía en `Board` porque ahí estaba todo lo
demás. Para un agente eso es caro —tiene que leer media ventana para tocar un botón—, y es
justo lo que Cotejo promete ahorrar. Se partió en `tareas/app/` y esta prueba existe para que
no vuelva a pasar en silencio.

Es un trinquete: un tope para todos y, para los que ya lo pasaban cuando nació la prueba, su
tamaño de entonces. Esos pueden bajar (y entonces se baja aquí su número o se borran), nunca
subir. Si una prueba de aquí se pone roja, lo que toca es partir el módulo, no subir el número.
"""

import unittest

from apoyo import RAIZ

TOPE = 800

# Los que ya pasaban del tope el 2026-10-10. Partirlos es trabajo pendiente, no una excepción.
CONGELADOS = {
    "enrutador/verbos.py": 1147,
    "tareas/dot.py": 935,
    "tareas/importar_obsidian.py": 892,
}


def modulos():
    for carpeta in ("tareas", "enrutador"):
        for ruta in sorted((RAIZ / carpeta).rglob("*.py")):
            if "__pycache__" not in ruta.parts:
                yield ruta.relative_to(RAIZ).as_posix(), ruta


class TamanoDeModulos(unittest.TestCase):

    def test_ningun_modulo_pasa_del_tope(self):
        for nombre, ruta in modulos():
            maximo = CONGELADOS.get(nombre, TOPE)
            with self.subTest(modulo=nombre):
                lineas = len(ruta.read_text(encoding="utf-8").splitlines())
                self.assertLessEqual(
                    lineas, maximo,
                    f"{nombre} tiene {lineas} líneas y su tope es {maximo}: pártelo por sus "
                    "partes (mira cómo está `tareas/app/`) en vez de subir el número")

    def test_los_congelados_siguen_existiendo(self):
        # Uno que se borra o se mueve deja aquí un número que ya no vigila nada.
        nombres = {nombre for nombre, _ruta in modulos()}
        self.assertEqual(sorted(set(CONGELADOS) - nombres), [])


if __name__ == "__main__":
    unittest.main()
