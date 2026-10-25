"""El servidor de una página estática para «Ver mi app» (cotejo-vn4qd2), sin lo oculto.

`python -m http.server` sirve la carpeta entera, y la del proyecto lleva `.git` (remotos,
historial) y `.cotejo` (tareas, decisiones): aunque solo escuche en 127.0.0.1, cualquier programa
o página del equipo podría leerlos. Este se niega a todo lo que tenga una parte que empiece por
punto. Solo la librería estándar: se lanza como script, con la carpeta del proyecto de cwd.

    python3 servidor_estatico.py <puerto> <carpeta>
"""

import functools
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit


def oculta(ruta_url):
    """True si alguna parte de la ruta empieza por punto (`.git`, `.cotejo`, `.env`…)."""
    partes = unquote(urlsplit(ruta_url).path).replace("\\", "/").split("/")
    return any(parte.startswith(".") for parte in partes if parte)


class SinOcultos(SimpleHTTPRequestHandler):
    def send_head(self):
        if oculta(self.path):
            self.send_error(HTTPStatus.NOT_FOUND, "No encontrado")
            return None
        return super().send_head()

    def list_directory(self, path):
        # Sin listados: una carpeta sin index.html no enseña lo que hay dentro.
        self.send_error(HTTPStatus.NOT_FOUND, "No encontrado")
        return None


def main(argv):
    puerto, carpeta = int(argv[0]), argv[1]
    manejador = functools.partial(SinOcultos, directory=carpeta)
    with ThreadingHTTPServer(("127.0.0.1", puerto), manejador) as servidor:
        servidor.serve_forever()


if __name__ == "__main__":
    main(sys.argv[1:])
