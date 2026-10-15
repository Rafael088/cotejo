"""Que cada icono que la app pide exista, y que los generados sean los del generador.

Un icono que falta no rompe nada: GTK dibuja el hueco y sigue. Una carta se queda sin su
chip de agente, una columna sin su estado, y no hay excepción ni aviso en ninguna parte —el
board simplemente se ve un poco más pobre y nadie se entera—. Por eso el nombre de cada
icono se comprueba aquí y no a ojo.

La segunda prueba existe porque los SVG están generados: si alguien edita el archivo en vez
del generador, el siguiente `generar.py` le borra el cambio sin decir nada.
"""

import importlib.util
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ICONOS = RAIZ / "data" / "iconos" / "hicolor" / "scalable" / "actions"
FUENTES = tuple(sorted((RAIZ / "tareas" / "app").glob("*.py")))


def nombres_pedidos():
    """Los iconos que el código nombra, de las dos formas en que los nombra."""
    pedidos = set()
    for fuente in FUENTES:
        texto = fuente.read_text()
        pedidos |= set(re.findall(r'icono\(\s*"([a-z0-9-]+)"', texto))
        pedidos |= set(re.findall(r'"cotejo-([a-z0-9-]+)-symbolic"', texto))
        # Los diccionarios que traducen columna o dificultad a icono.
        for bloque in re.findall(r'ICONOS_\w+ = \{(.*?)\}', texto, re.S):
            pedidos |= set(re.findall(r':\s*"([a-z0-9-]+)"', bloque))
    # Los que se arman a trozos: `"persona" if ... else "agente"`, `sin-agente`.
    pedidos |= {"persona", "agente", "sin-agente"}
    return {n for n in pedidos if n}


class Iconos(unittest.TestCase):

    def test_existe_cada_icono_que_la_app_nombra(self):
        faltan = sorted(n for n in nombres_pedidos()
                        if not (ICONOS / f"cotejo-{n}-symbolic.svg").exists())
        self.assertEqual(faltan, [], f"iconos nombrados en el código y sin archivo: {faltan}")

    def test_los_svg_son_los_que_sale_de_generar(self):
        # Por ruta y no con `import`: `data/` guarda recursos, no es un paquete, y volverlo
        # uno solo para esta prueba metería archivos de Python en lo que se instala.
        specs = importlib.util.spec_from_file_location(
            "generar_iconos", RAIZ / "data" / "iconos" / "generar.py")
        generar = importlib.util.module_from_spec(specs)
        specs.loader.exec_module(generar)
        antes = {ruta.name: ruta.read_text() for ruta in ICONOS.glob("cotejo-*-symbolic.svg")}
        generar.escribir()
        despues = {ruta.name: ruta.read_text() for ruta in ICONOS.glob("cotejo-*-symbolic.svg")}
        self.assertEqual(antes, despues,
                         "hay iconos editados a mano: el cambio va en data/iconos/generar.py")

    def test_cada_icono_es_un_svg_de_una_sola_forma_rellena(self):
        """Relleno y no trazo: GTK descarta el `stroke` de un icono simbólico."""
        for ruta in sorted(ICONOS.glob("cotejo-*-symbolic.svg")):
            with self.subTest(icono=ruta.name):
                texto = ruta.read_text()
                self.assertIn('viewBox="0 0 24 24"', texto)
                self.assertNotIn("stroke", texto)
                self.assertEqual(texto.count("<path"), 1)


if __name__ == "__main__":
    unittest.main()
