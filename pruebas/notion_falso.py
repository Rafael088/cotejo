"""Un Notion de mentira: la parte de la API que usa `cotejo-notion`, en memoria y en local.

Es un servidor HTTP de verdad en un hilo, no un `mock`: el adaptador es otro proceso y habla
por la red, así que la única forma honesta de probarlo es darle una red a la que hablar.
`COTEJO_NOTION_API` lo apunta aquí.

Imita lo que importa del comportamiento real: la paginación (`has_more`/`next_cursor`), el
filtro por checkbox, que un status solo acepta opciones que ya existen, que un token malo da
401 y una base no compartida 404, y que PATCH devuelve la página como quedó.
"""

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = "secreto-de-prueba"


def _texto(contenido):
    return [{"type": "text", "plain_text": contenido, "text": {"content": contenido}}]


class NotionFalso:
    def __init__(self, titulo="Tareas", propiedades=None, pagina_de=3):
        self.base_id = uuid.uuid4().hex
        self.titulo = titulo
        self.pagina_de = pagina_de  # resultados por página, pequeño para probar la paginación
        self.propiedades = propiedades or {
            "Nombre": {"type": "title", "title": {}},
            "Estado": {"type": "status", "status": {"options": [
                {"name": "Pendiente"}, {"name": "En curso"}, {"name": "Por validar"},
                {"name": "Hecha"}]}},
            "Agente": {"type": "select", "select": {"options": []}},
            "Dificultad": {"type": "select", "select": {"options": [
                {"name": "Fácil"}, {"name": "Medio"}, {"name": "Difícil"}]}},
            "Proyecto": {"type": "select", "select": {"options": []}},
            "Done": {"type": "checkbox", "checkbox": {}},
            "ID": {"type": "unique_id", "unique_id": {"prefix": "TAR"}},
        }
        self.paginas = {}
        self.otras = {}  # páginas sueltas (proyectos de una relación)
        self.peticiones = []
        self._numero = 0

    # --- sembrar ------------------------------------------------------------

    def tarea(self, texto, estado="Pendiente", agente="", proyecto="", hecha=False,
              dificultad="", **extra):
        self._numero += 1
        pid = str(uuid.uuid4())
        props = {}
        for nombre, definicion in self.propiedades.items():
            tipo = definicion["type"]
            if tipo == "title":
                props[nombre] = {"type": "title", "title": _texto(texto)}
            elif tipo == "unique_id":
                props[nombre] = {"type": "unique_id", "unique_id": {
                    "prefix": definicion["unique_id"].get("prefix"), "number": self._numero}}
            elif tipo == "checkbox":
                props[nombre] = {"type": "checkbox", "checkbox": hecha}
        valores = {"Estado": estado, "Agente": agente, "Proyecto": proyecto,
                   "Dificultad": dificultad, **extra}
        for nombre, valor in valores.items():
            if nombre in self.propiedades:
                props[nombre] = self._valor(nombre, valor)
        self.paginas[pid] = {"object": "page", "id": pid, "url": f"https://notion.so/{pid}",
                             "archived": False, "parent": {"type": "database_id",
                                                           "database_id": self.base_id},
                             "properties": props}
        return pid

    def pagina_suelta(self, titulo):
        pid = str(uuid.uuid4())
        self.otras[pid] = {"object": "page", "id": pid, "url": f"https://notion.so/{pid}",
                           "parent": {"type": "workspace"},
                           "properties": {"Nombre": {"type": "title", "title": _texto(titulo)}}}
        return pid

    def _valor(self, nombre, valor):
        tipo = self.propiedades[nombre]["type"]
        if tipo in ("select", "status"):
            return {"type": tipo, tipo: {"name": valor} if valor else None}
        if tipo == "multi_select":
            return {"type": tipo, tipo: [{"name": valor}] if valor else []}
        if tipo == "rich_text":
            return {"type": tipo, tipo: _texto(valor) if valor else []}
        if tipo == "relation":
            return {"type": tipo, tipo: [{"id": valor}] if valor else [], "has_more": False}
        raise ValueError(tipo)

    def por_texto(self, texto):
        for pagina in self.paginas.values():
            if pagina["properties"]["Nombre"]["title"][0]["plain_text"] == texto:
                return pagina
        raise KeyError(texto)

    def valor(self, texto, propiedad):
        crudo = self.por_texto(texto)["properties"].get(propiedad) or {}
        dentro = crudo.get(crudo.get("type"))
        if isinstance(dentro, dict):
            return dentro.get("name")
        if isinstance(dentro, list):
            return dentro[0].get("plain_text") or dentro[0].get("name") if dentro else ""
        return dentro

    def cambiar(self, texto, propiedad, valor):
        """Lo que haría una persona en Notion, sin pasar por Cotejo."""
        self.por_texto(texto)["properties"][propiedad] = self._valor(propiedad, valor)

    # --- servir -------------------------------------------------------------

    def responder(self, metodo, ruta, cuerpo, token):
        self.peticiones.append((metodo, ruta))
        if token != TOKEN:
            return 401, {"message": "API token is invalid."}
        partes = ruta.strip("/").split("/")
        if partes[0] == "databases":
            if partes[1] != self.base_id:
                return 404, {"message": "Could not find database."}
            if metodo == "GET":
                return 200, {"object": "database", "id": self.base_id,
                             "url": f"https://notion.so/{self.base_id}",
                             "title": _texto(self.titulo), "properties": self.propiedades}
            return 200, self._consultar(cuerpo)
        if partes[0] == "pages" and metodo == "POST":
            return self._crear(cuerpo)
        if partes[0] == "pages":
            pagina = self._buscar(partes[1])
            if pagina is None:
                return 404, {"message": "Could not find page."}
            if metodo == "PATCH":
                return self._actualizar(pagina, cuerpo["properties"])
            return 200, pagina
        return 404, {"message": "nope"}

    def _buscar(self, identificador):
        for coleccion in (self.paginas, self.otras):
            for pid, pagina in coleccion.items():
                if pid.replace("-", "") == identificador.replace("-", ""):
                    return pagina
        return None

    def _consultar(self, cuerpo):
        filas = list(self.paginas.values())
        filtro = cuerpo.get("filter")
        if filtro:
            filas = [p for p in filas if p["properties"][filtro["property"]]["checkbox"]
                     == filtro["checkbox"]["equals"]]
        inicio = int(cuerpo.get("start_cursor") or 0)
        trozo = filas[inicio:inicio + self.pagina_de]
        fin = inicio + self.pagina_de
        return {"object": "list", "results": trozo, "has_more": fin < len(filas),
                "next_cursor": str(fin) if fin < len(filas) else None}

    def _comprobar_opciones(self, props):
        for nombre, valor in props.items():
            if nombre not in self.propiedades:
                return 400, {"message": f"{nombre} is not a property that exists."}
            tipo = self.propiedades[nombre]["type"]
            if tipo == "status" and valor.get("status"):
                opciones = [o["name"] for o in self.propiedades[nombre]["status"]["options"]]
                if valor["status"]["name"] not in opciones:
                    return 400, {"message": f"Invalid status option {valor['status']['name']}"}
        return None

    def _normalizar(self, nombre, valor):
        tipo = self.propiedades[nombre]["type"]
        if tipo in ("title", "rich_text"):
            return {"type": tipo, tipo: [{"type": "text", "plain_text": t["text"]["content"],
                                          "text": t["text"]} for t in valor[tipo]]}
        return {"type": tipo, **valor}

    def _actualizar(self, pagina, props):
        malo = self._comprobar_opciones(props)
        if malo:
            return malo
        for nombre, valor in props.items():
            pagina["properties"][nombre] = self._normalizar(nombre, valor)
        return 200, pagina

    def _crear(self, cuerpo):
        if cuerpo["parent"]["database_id"].replace("-", "") != self.base_id:
            return 404, {"message": "Could not find database."}
        malo = self._comprobar_opciones(cuerpo["properties"])
        if malo:
            return malo
        texto = cuerpo["properties"]["Nombre"]["title"][0]["text"]["content"]
        pid = self.tarea(texto)
        for nombre, valor in cuerpo["properties"].items():
            self.paginas[pid]["properties"][nombre] = self._normalizar(nombre, valor)
        return 200, self.paginas[pid]

    # --- el servidor ----------------------------------------------------------

    def arrancar(self):
        falso = self

        class Manejador(BaseHTTPRequestHandler):
            def _atender(self, metodo):
                largo = int(self.headers.get("Content-Length") or 0)
                cuerpo = json.loads(self.rfile.read(largo)) if largo else {}
                token = (self.headers.get("Authorization") or "").removeprefix("Bearer ")
                with bloqueo:
                    codigo, datos = falso.responder(metodo, self.path.removeprefix("/v1"),
                                                    cuerpo, token)
                texto = json.dumps(datos).encode()
                self.send_response(codigo)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(texto)))
                self.end_headers()
                self.wfile.write(texto)

            def do_GET(self):
                self._atender("GET")

            def do_POST(self):
                self._atender("POST")

            def do_PATCH(self):
                self._atender("PATCH")

            def log_message(self, *args):
                pass

        bloqueo = threading.Lock()
        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
        # Sondeo corto: `shutdown` espera un intervalo entero, y con el de fábrica (0,5 s) eso
        # se comía más tiempo que las pruebas.
        threading.Thread(target=self.servidor.serve_forever, kwargs={"poll_interval": 0.02},
                         daemon=True).start()
        return f"http://127.0.0.1:{self.servidor.server_address[1]}/v1"

    def parar(self):
        self.servidor.shutdown()
        self.servidor.server_close()
