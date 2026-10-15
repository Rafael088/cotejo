"""Crea el vault de prueba de una instalación limpia (tarea cotejo-cqa8vq) donde se le pida.

    python3 herramientas/vault_prueba.py [DESTINO]    # sin destino, una carpeta temporal

Dos proyectos de mentira, Faro (nota suelta) y Horizonte (carpeta con una sub-nota), con tareas
en los cuatro estados. Se genera y no se guarda como notas en el repo porque el repo vive dentro
de un vault de verdad: sus `- [ ]` aparecían como tareas del proyecto Cotejo.
Imprime la carpeta; úsala con COTEJO_VAULT=<carpeta>.
"""

import sys
import tempfile
from pathlib import Path

ARCHIVOS = {
    '01-Proyectos/Faro.md': '---\ntipo: proyecto\n---\n\n# Faro\n\nVault de prueba para probar una instalación limpia de Cotejo (tarea `cotejo-cqa8vq`). No es un\nproyecto real: las tareas de aquí abajo son de mentira, pensadas para cubrir los cuatro estados\nque entiende Cotejo.\n\n## Tareas\n\n- [ ] Redactar el resumen semanal de avance\n- [ ] Revisar el formulario de alta de usuarios #en-curso\n- [ ] Publicar el reporte mensual en el panel #por-validar\n- [x] Archivar las notas antiguas de la carpeta de borradores — 2026-09-10\n- [ ] Probar la exportación a PDF #facil\n',
    '01-Proyectos/Horizonte/Bitacora.md': '# Bitácora\n\nSub-nota de Horizonte, en el vault de prueba.\n\n- [ ] Anotar la fecha de la próxima revisión #en-curso\n- [ ] Sumar una tarea nueva desde la CLI para comprobar `cotejo crear`\n',
    '01-Proyectos/Horizonte/Horizonte.md': '---\ntipo: proyecto\n---\n\n# Horizonte\n\nSegundo proyecto del vault de prueba (`cotejo-cqa8vq`), de mentira. Este es un proyecto con\ncarpeta propia y una sub-nota, para probar esa forma además de la nota suelta de `Faro.md`.\n\n## Tareas\n\n- [ ] Ordenar el índice de referencias #medio\n- [x] Cerrar la encuesta de satisfacción — 2026-09-05\n',
}


def crear(destino):
    destino = Path(destino)
    for ruta, texto in ARCHIVOS.items():
        archivo = destino / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(texto, encoding="utf-8")
    return destino


if __name__ == "__main__":
    print(crear(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="cotejo-vault-")))
