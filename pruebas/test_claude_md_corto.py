"""El CLAUDE.md del repo se queda corto, y lo que cita existe.

Cada turno de cada agente que trabaja aquí paga el CLAUDE.md entero. Llegó a 54 KB (≈ 16k tokens
por turno) porque cada cosa nueva se explicaba ahí. Desde cotejo-d9cbol solo lleva cómo probar,
las reglas duras en una línea y un índice con ids; el detalle vive en `.cotejo/` y se pide con
`cotejo leer <id>`. Si esta prueba se pone roja por tamaño, lo que toca es mover texto a
`.cotejo/` (`cotejo anotar`, `cotejo proponer decision`), no subir el tope.
"""

import re
import unittest

from apoyo import RAIZ

TOPE = 8 * 1024   # bytes
ID = re.compile(r"\b(?:dec|arq|pro|apr|ref|rec)-[a-z0-9]{4}\b")


def ids_del_almacen():
    ids = set()
    for ruta in (RAIZ / ".cotejo").rglob("*.md"):
        m = re.search(r"^id:\s*(\S+)\s*$", ruta.read_text(encoding="utf-8"), re.M)
        if m:
            ids.add(m.group(1))
    return ids


class ClaudeMdCorto(unittest.TestCase):
    def setUp(self):
        self.ruta = RAIZ / "CLAUDE.md"

    def test_no_pasa_de_8_kb(self):
        tamano = len(self.ruta.read_bytes())
        self.assertLessEqual(tamano, TOPE,
                             f"CLAUDE.md pesa {tamano} bytes (tope {TOPE}): mueve el detalle a "
                             ".cotejo/ y deja aquí su id")

    def test_cada_id_que_cita_existe_en_cotejo(self):
        citados = set(ID.findall(self.ruta.read_text(encoding="utf-8")))
        self.assertTrue(citados, "el índice tendría que citar entradas de .cotejo/")
        faltan = sorted(citados - ids_del_almacen())
        self.assertEqual(faltan, [], f"CLAUDE.md cita ids que no están en .cotejo/: {faltan}")


if __name__ == "__main__":
    unittest.main()
