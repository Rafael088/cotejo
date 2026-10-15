#!/usr/bin/env python3
"""Adaptador de Cotejo para Notion: una base de datos de Notion como segundo cerebro.

Habla el contrato de `tareas/fuentes/externa.py` y nada más: Cotejo lo lanza, él llama a la API
oficial de Notion y contesta JSON. Solo usa la librería estándar, para que instalarlo no sea
instalar nada.

## Qué se lee como qué

- **Cada página de la base es una tarea.** Su título es el texto.
- **El proyecto** sale de la propiedad «Proyecto» (select, multi-select, texto o relación a
  otra base). Sin esa propiedad, o con ella vacía, el proyecto es la base entera, con su
  título: así una base por proyecto también funciona (`database_ids` con varias).
- **El estado** sale de la propiedad «Estado» (status o select). Los nombres se casan sin
  mirar mayúsculas ni tildes, y se entienden los de fábrica de Notion —«Not started», «In
  progress», «Done»— además de los de Cotejo.
- **Hecha** es el checkbox «Done» si existe; si no, que el estado diga hecha.
- **Agente** y **Dificultad**, si existen (select o texto). Sin «Agente», no se puede tomar.
- **El id** es la propiedad de tipo *ID único* si la base tiene una («COTEJO-12» → `cotejo-12`);
  si no, el id de la página, sin guiones.

Todos esos nombres se cambian con `propiedades` en la config, y los valores de estado con
`estados`: `fuentes info notion` los enseña.

## Lo que se exige, igual que en Obsidian

- **Escribir verificado**: antes de tocar una página se relee y se compara con `--esperado`.
  Si alguien la cambió en Notion desde que Cotejo la leyó, no se escribe y se contesta
  `cambiada`.
- **Idempotente**: si la página ya está como se pide, no se toca y sale `"cambio": false`.
- **El token no está en la config**: la config dice en qué variable de entorno está
  (`token_env`, por defecto `NOTION_TOKEN`).

`COTEJO_NOTION_API` apunta a otra URL base: es como se prueba contra un Notion de mentira.
"""

import argparse
import json
import os
import sys
import unicodedata
import urllib.error
import urllib.request

ESQUEMA = 1
VERSION_API = "2022-06-28"
ESTADOS = ("pendiente", "en-curso", "por-validar", "hecha")

PROPIEDADES = {"proyecto": "Proyecto", "estado": "Estado", "agente": "Agente",
               "dificultad": "Dificultad", "hecha": "Done", "version": "Versión", "id": None}
# Qué nombre se escribe en Notion para cada estado de Cotejo. Si la base no tiene esa opción, se
# busca entre los alias de abajo antes de rendirse.
ESTADOS_NOTION = {"pendiente": "Pendiente", "en-curso": "En curso",
                  "por-validar": "Por validar", "hecha": "Hecha"}
ALIAS = {
    "pendiente": ("pendiente", "not started", "sin empezar", "por hacer", "to do", "todo",
                  "backlog"),
    "en-curso": ("en curso", "in progress", "haciendola", "doing", "en progreso"),
    "por-validar": ("por validar", "para comprobar", "en revision", "in review", "review",
                    "por revisar"),
    "hecha": ("hecha", "done", "completed", "completada", "terminada", "listo", "finalizada"),
}


# Dónde buscar el token si no está en el entorno. Hace falta porque el board y la barra no los
# lanza una shell: los arranca Hyprland o Quickshell, que no ven las variables de fish ni las
# del .bashrc. Un archivo propio, legible solo por el usuario, llega a todos por igual.
# Va en la carpeta de config de Cotejo, que depende del sistema: la misma cuenta que
# `tareas/rutas.py`, repetida aquí porque el adaptador se instala y se lanza solo, sin Cotejo.
def carpeta_config():
    hogar = os.path.expanduser("~")
    if sys.platform.startswith(("win32", "cygwin")):
        return os.environ.get("APPDATA") or os.path.join(hogar, "AppData", "Roaming")
    if sys.platform == "darwin":
        return os.path.join(hogar, "Library", "Application Support")
    return os.environ.get("XDG_CONFIG_HOME") or os.path.join(hogar, ".config")


TOKEN_ARCHIVO = os.path.join(carpeta_config(), "cotejo", "notion.token")
# Donde lo guardaba cuando el producto se llamaba Foco. Se lee si el nuevo no está.
TOKEN_ARCHIVO_VIEJO = os.path.join(carpeta_config(), "foco", "notion.token")


def entorno(nombre):
    """`COTEJO_<nombre>`, o `FOCO_<nombre>` si es la única que hay: el nombre de antes."""
    return os.environ.get(f"COTEJO_{nombre}") or os.environ.get(f"FOCO_{nombre}")


def leer_token(ruta):
    try:
        return open(ruta, encoding="utf-8").read().strip()
    except OSError:
        return ""


class Fallo(Exception):
    def __init__(self, mensaje, tipo="fuente", salida="", reintentable=False, donde=""):
        super().__init__(mensaje)
        self.datos = {"esquema": ESQUEMA, "error": mensaje, "tipo": tipo, "salida": salida,
                      "reintentable": reintentable}
        if donde:
            self.datos["donde"] = donde


def llano(texto):
    """Para comparar nombres: sin tildes, sin mayúsculas, sin guiones ni espacios de más."""
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    return " ".join(texto.replace("-", " ").replace("_", " ").split())


def sin_guiones(identificador):
    return str(identificador or "").replace("-", "").lower()


# --- la API -------------------------------------------------------------------------


class Notion:
    def __init__(self, config):
        self.config = config
        self.base = entorno("NOTION_API") or "https://api.notion.com/v1"
        self.version = config.get("version_api") or VERSION_API
        variable = config.get("token_env") or "NOTION_TOKEN"
        archivo = os.path.expanduser(config.get("token_archivo") or TOKEN_ARCHIVO)
        self.token = os.environ.get(variable) or leer_token(archivo)
        if not self.token and not config.get("token_archivo"):
            self.token = leer_token(os.path.expanduser(TOKEN_ARCHIVO_VIEJO))
        if not self.token:
            raise Fallo(f"No hay token de Notion: ni en la variable {variable} ni en {archivo}",
                        tipo="config",
                        salida=f"Crea una integración interna en notion.so/my-integrations, "
                               f"comparte la base con ella y guarda su token en {archivo} "
                               f"(chmod 600), o expórtalo en {variable}.")
        # Lo que pesaron las respuestas: la mitad cara del medidor de ahorro de Cotejo.
        self.leido = 0

    def pedir(self, metodo, ruta, cuerpo=None):
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        peticion = urllib.request.Request(
            self.base.rstrip("/") + ruta, data=datos, method=metodo,
            headers={"Authorization": f"Bearer {self.token}", "Notion-Version": self.version,
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(peticion, timeout=20) as respuesta:
                texto = respuesta.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            self._fallo_http(error, ruta)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise Fallo(f"No llego a Notion: {error}", tipo="red",
                        salida="Revisa la conexión y reintenta.", reintentable=True) from error
        self.leido += len(texto)
        return json.loads(texto)

    def _fallo_http(self, error, ruta):
        try:
            detalle = json.loads(error.read().decode("utf-8")).get("message", "")
        except (ValueError, OSError):
            detalle = ""
        if error.code == 401:
            raise Fallo(f"Notion no acepta el token: {detalle}", tipo="config",
                        salida="El token caducó o no es de una integración interna.") from error
        if error.code == 404:
            raise Fallo(f"Notion no encuentra {ruta}: {detalle}", tipo="config",
                        salida="Comprueba el id y comparte la base con la integración "
                               "(… → Conexiones en la base).") from error
        if error.code == 429 or error.code >= 500:
            raise Fallo(f"Notion no puede ahora ({error.code}): {detalle}", tipo="red",
                        salida="Reintenta en un momento.", reintentable=True) from error
        raise Fallo(f"Notion contestó {error.code}: {detalle}",
                    salida="`fuentes probar notion` dice si la base está bien.") from error


# --- la base: qué propiedad es qué ---------------------------------------------------


class Base:
    """Una base de Notion con sus propiedades ya resueltas contra la config."""

    def __init__(self, api, identificador, config):
        self.api = api
        self.id = sin_guiones(identificador)
        crudo = api.pedir("GET", f"/databases/{self.id}")
        self.titulo = "".join(t.get("plain_text", "") for t in crudo.get("title") or []) \
            or "Notion"
        self.url = crudo.get("url") or ""
        self.props = crudo.get("properties") or {}
        nombres = {**PROPIEDADES, **(config.get("propiedades") or {})}
        self.titulo_prop = next((n for n, p in self.props.items() if p.get("type") == "title"), None)
        self.prop = {}
        for clave, nombre in nombres.items():
            if clave == "id" and not nombre:
                nombre = next((n for n, p in self.props.items() if p.get("type") == "unique_id"),
                              None)
            if nombre and nombre in self.props:
                self.prop[clave] = nombre
        if "hecha" in self.prop and self.tipo("hecha") != "checkbox":
            del self.prop["hecha"]
        self.estados = {**ESTADOS_NOTION, **(config.get("estados") or {})}

    def tipo(self, clave):
        nombre = self.prop.get(clave)
        return self.props[nombre]["type"] if nombre else None

    def opciones(self, clave):
        tipo = self.tipo(clave)
        if tipo not in ("status", "select", "multi_select"):
            return []
        return [o.get("name", "") for o in (self.props[self.prop[clave]].get(tipo) or {})
                .get("options") or []]

    def opcion_estado(self, estado):
        """El nombre que hay que escribir en Notion para un estado de Cotejo, o None."""
        opciones = self.opciones("estado")
        pedido = self.estados.get(estado)
        if not opciones:
            return pedido  # texto, o un select que acepta opciones nuevas
        for candidato in (pedido, *ALIAS[estado]):
            for opcion in opciones:
                if llano(opcion) == llano(candidato):
                    return opcion
        return pedido if self.tipo("estado") == "select" else None

    def problemas(self):
        """Lo que impediría trabajar con esta base, dicho para arreglarlo."""
        faltan = []
        if "estado" not in self.prop:
            faltan.append(f"La base «{self.titulo}» no tiene la propiedad "
                          f"«{PROPIEDADES['estado']}» (status o select): sin ella no se puede "
                          f"tomar ni entregar. Créala o nómbrala en «propiedades».")
        else:
            for estado in ("pendiente", "en-curso", "por-validar"):
                if self.opcion_estado(estado) is None:
                    faltan.append(f"El estado «{self.prop['estado']}» de «{self.titulo}» no "
                                  f"tiene opción para «{estado}»: añade «{self.estados[estado]}» "
                                  f"en Notion o dile cuál es en «estados».")
        if "agente" not in self.prop:
            faltan.append(f"La base «{self.titulo}» no tiene la propiedad «Agente» (select o "
                          f"texto): sin ella no se puede tomar una tarea.")
        return faltan

    # --- de página a tarea ------------------------------------------------------

    def valor(self, pagina, clave):
        nombre = self.prop.get(clave)
        if not nombre:
            return None
        return texto_de((pagina.get("properties") or {}).get(nombre) or {})

    def estado_de(self, pagina):
        """(estado de Cotejo, hecha)."""
        crudo = self.valor(pagina, "estado") or ""
        estado = "pendiente"
        for cotejo, nombre in self.estados.items():
            if crudo and llano(crudo) in {llano(nombre), *ALIAS[cotejo]}:
                estado = cotejo
                break
        hecha = estado == "hecha"
        if "hecha" in self.prop:
            hecha = bool(((pagina.get("properties") or {})[self.prop["hecha"]]).get("checkbox"))
        if estado == "hecha":
            estado = "pendiente"  # «hecha» no es una columna de trabajo: la dice `hecha`
        return estado, hecha

    def id_de(self, pagina):
        if "id" in self.prop:
            unico = ((pagina.get("properties") or {})[self.prop["id"]]).get("unique_id") or {}
            if unico.get("number") is not None:
                prefijo = unico.get("prefix")
                return (f"{prefijo}-{unico['number']}" if prefijo else str(unico["number"])).lower()
        return sin_guiones(pagina.get("id"))

    def tarea(self, pagina):
        estado, hecha = self.estado_de(pagina)
        titulo = texto_de((pagina.get("properties") or {}).get(self.titulo_prop) or {})
        return {"id": self.id_de(pagina), "ref": sin_guiones(pagina.get("id")),
                "texto": " ".join(titulo.split()), "estado": estado, "hecha": hecha,
                "agente": self.valor(pagina, "agente") or "",
                "dificultad": dificultad(self.valor(pagina, "dificultad")),
                "version": self.valor(pagina, "version") or "",
                "url": pagina.get("url") or ""}

    # --- de lo que se pide a propiedades --------------------------------------------

    def escribir_valor(self, clave, valor):
        """El JSON de una propiedad para PATCH, según su tipo en esta base."""
        tipo = self.tipo(clave)
        if tipo in ("status", "select"):
            return {tipo: {"name": valor} if valor else None}
        if tipo == "multi_select":
            return {tipo: [{"name": valor}] if valor else []}
        if tipo in ("rich_text", "title"):
            return {tipo: [{"type": "text", "text": {"content": valor}}] if valor else []}
        if tipo == "checkbox":
            return {tipo: bool(valor)}
        raise Fallo(f"No sé escribir «{self.prop.get(clave, clave)}», que es de tipo {tipo}",
                    tipo="no-implementado",
                    salida="Cámbiala a select o texto, o apunta «propiedades» a otra.")


def texto_de(propiedad):
    """El valor de una propiedad de Notion como texto, sea del tipo que sea."""
    tipo = propiedad.get("type")
    valor = propiedad.get(tipo)
    if valor is None:
        return ""
    if tipo in ("title", "rich_text"):
        return "".join(t.get("plain_text", "") for t in valor)
    if tipo in ("select", "status"):
        return valor.get("name", "")
    if tipo == "multi_select":
        return valor[0].get("name", "") if valor else ""
    if tipo == "formula":
        return str(valor.get(valor.get("type")) or "")
    if tipo == "people":
        return valor[0].get("name", "") if valor else ""
    if tipo == "relation":
        return valor[0].get("id", "") if valor else ""
    if isinstance(valor, (str, int, float)):
        return str(valor)
    return ""


def dificultad(texto):
    llanos = {"facil": "facil", "medio": "medio", "media": "medio", "dificil": "dificil",
              "easy": "facil", "medium": "medio", "hard": "dificil"}
    return llanos.get(llano(texto), "")


# --- el adaptador -------------------------------------------------------------------


class Adaptador:
    def __init__(self):
        try:
            self.config = json.loads(entorno("FUENTE_CONFIG") or "{}")
        except ValueError as error:
            raise Fallo(f"COTEJO_FUENTE_CONFIG no es JSON: {error}", tipo="config") from error
        ids = self.config.get("database_ids") or self.config.get("database_id")
        self.ids = [ids] if isinstance(ids, str) else list(ids or [])
        if not self.ids:
            raise Fallo("Falta «database_id»: la base de Notion con las tareas", tipo="config",
                        salida="Es el trozo de 32 caracteres de la URL de la base. Pásalo con "
                               "--param database_id=<id>.")
        self.api = Notion(self.config)
        self._bases = {}
        self._titulos = {}

    def base(self, identificador):
        clave = sin_guiones(identificador)
        if clave not in self._bases:
            self._bases[clave] = Base(self.api, clave, self.config)
        return self._bases[clave]

    def bases(self):
        return [self.base(i) for i in self.ids]

    def titulo_de_pagina(self, identificador):
        """El título de una página relacionada (el proyecto, en una relación)."""
        if identificador not in self._titulos:
            pagina = self.api.pedir("GET", f"/pages/{sin_guiones(identificador)}")
            titulo = next((texto_de(p) for p in (pagina.get("properties") or {}).values()
                           if p.get("type") == "title"), "")
            self._titulos[identificador] = (titulo, pagina.get("url") or "")
        return self._titulos[identificador]

    def proyecto_de(self, base, pagina):
        """(nombre, ref, url) del proyecto de una página."""
        if "proyecto" not in base.prop:
            return base.titulo, "", base.url
        crudo = base.valor(pagina, "proyecto")
        if not crudo:
            return base.titulo, "", base.url
        if base.tipo("proyecto") == "relation":
            titulo, url = self.titulo_de_pagina(crudo)
            return titulo or base.titulo, sin_guiones(crudo), url
        return crudo, "", base.url

    def paginas(self, base, hechas):
        cuerpo = {"page_size": 100}
        if not hechas and "hecha" in base.prop:
            cuerpo["filter"] = {"property": base.prop["hecha"], "checkbox": {"equals": False}}
        while True:
            respuesta = self.api.pedir("POST", f"/databases/{base.id}/query", cuerpo)
            yield from respuesta.get("results") or []
            if not respuesta.get("has_more"):
                return
            cuerpo["start_cursor"] = respuesta.get("next_cursor")

    def pagina(self, ref):
        pagina = self.api.pedir("GET", f"/pages/{sin_guiones(ref)}")
        padre = sin_guiones((pagina.get("parent") or {}).get("database_id"))
        if padre not in {sin_guiones(i) for i in self.ids}:
            raise Fallo(f"La página {ref} no es de ninguna base de esta fuente", tipo="cambiada",
                        salida="Vuelve a pedir `tareas`.")
        return self.base(padre), pagina

    # --- verbos -----------------------------------------------------------------------

    def doctor(self, args):
        problemas = [p for base in self.bases() for p in base.problemas()]
        nombres = ", ".join(f"«{b.titulo}»" for b in self.bases())
        if problemas:
            return {"esquema": ESQUEMA, "ok": False, "mensaje": problemas[0],
                    "problemas": problemas,
                    "salida": "Arregla la base en Notion o dile a Cotejo cómo se llaman sus "
                              "propiedades con «propiedades» y «estados»."}
        return {"esquema": ESQUEMA, "ok": True, "mensaje": f"Conectado a Notion: {nombres}"}

    def escanear(self, args):
        proyectos, avisos = {}, []
        for base in self.bases():
            antes = self.api.leido
            if "estado" not in base.prop:
                avisos.append(f"«{base.titulo}» no tiene propiedad de estado: todas sus tareas "
                              f"se leen como pendientes")
            for pagina in self.paginas(base, args.hechas):
                if pagina.get("archived") or pagina.get("in_trash"):
                    continue
                tarea = base.tarea(pagina)
                if not tarea["texto"]:
                    continue  # la fila vacía que Notion deja al final de una tabla
                if tarea["hecha"] and not args.hechas:
                    continue
                nombre, ref, url = self.proyecto_de(base, pagina)
                proyecto = proyectos.setdefault(nombre, {
                    "nombre": nombre, "donde": f"Notion · {base.titulo}", "estado": "",
                    "prioridad": "", "url": url, "ref": ref, "leido": 0, "tareas": []})
                proyecto["tareas"].append({**tarea, "donde": f"Notion · {base.titulo}"})
            # Lo que pesó leer la base se reparte entre sus proyectos por número de tareas.
            leido = self.api.leido - antes
            suyos = [p for p in proyectos.values() if p["donde"] == f"Notion · {base.titulo}"]
            total = sum(len(p["tareas"]) for p in suyos) or 1
            for proyecto in suyos:
                proyecto["leido"] += leido * len(proyecto["tareas"]) // total
        return {"esquema": ESQUEMA, "proyectos": list(proyectos.values()), "avisos": avisos,
                "leido": self.api.leido}

    def _comprobar(self, base, pagina, esperado):
        actual = base.tarea(pagina)
        for clave in ("texto", "estado", "agente", "hecha"):
            if clave in esperado and actual[clave] != esperado[clave]:
                raise Fallo(f"La tarea {actual['id']} cambió en Notion ({clave}: "
                            f"{esperado[clave]!r} → {actual[clave]!r})", tipo="cambiada",
                            donde=f"Notion · {base.titulo}")
        return actual

    def _cambiar(self, ref, esperado, propiedades_de):
        base, pagina = self.pagina(ref)
        actual = self._comprobar(base, pagina, json.loads(esperado or "{}"))
        propiedades = propiedades_de(base, actual)
        if not propiedades:
            return {"esquema": ESQUEMA, "cambio": False, "tarea": actual}
        nueva = self.api.pedir("PATCH", f"/pages/{sin_guiones(pagina['id'])}",
                               {"properties": propiedades})
        return {"esquema": ESQUEMA, "cambio": True, "tarea": base.tarea(nueva)}

    def estado(self, args):
        if args.nuevo not in ESTADOS[:3]:
            raise Fallo(f"Estado desconocido: {args.nuevo}")

        def propiedades(base, actual):
            if actual["estado"] == args.nuevo:
                return {}
            if "estado" not in base.prop:
                raise Fallo(f"«{base.titulo}» no tiene propiedad de estado", tipo="no-implementado",
                            salida="Créala en Notion (status o select).")
            opcion = base.opcion_estado(args.nuevo)
            if opcion is None:
                raise Fallo(f"«{base.prop['estado']}» no tiene opción para «{args.nuevo}»",
                            tipo="config", salida="Añádela en Notion o nómbrala en «estados».")
            return {base.prop["estado"]: base.escribir_valor("estado", opcion)}
        return self._cambiar(args.ref, args.esperado, propiedades)

    def agente(self, args):
        def propiedades(base, actual):
            if actual["agente"] == args.quien:
                return {}
            if "agente" not in base.prop:
                raise Fallo(f"«{base.titulo}» no tiene propiedad «Agente»", tipo="no-implementado",
                            salida="Créala en Notion (select o texto).")
            return {base.prop["agente"]: base.escribir_valor("agente", args.quien)}
        return self._cambiar(args.ref, args.esperado, propiedades)

    def marcar(self, args):
        def propiedades(base, actual):
            if actual["hecha"] == args.hecha:
                return {}
            if "hecha" in base.prop:
                return {base.prop["hecha"]: {"checkbox": args.hecha}}
            opcion = base.opcion_estado("hecha" if args.hecha else "pendiente")
            if "estado" not in base.prop or opcion is None:
                raise Fallo(f"«{base.titulo}» no tiene cómo decir que una tarea está hecha",
                            tipo="no-implementado",
                            salida="Añade un checkbox «Done» o una opción «Hecha» al estado.")
            return {base.prop["estado"]: base.escribir_valor("estado", opcion)}
        return self._cambiar(args.ref, args.esperado, propiedades)

    def crear(self, args):
        base = self._base_para(args.proyecto)
        propiedades = {base.titulo_prop: {"title": [{"type": "text",
                                                     "text": {"content": args.texto}}]}}
        if "estado" in base.prop and base.opcion_estado("pendiente"):
            propiedades[base.prop["estado"]] = base.escribir_valor(
                "estado", base.opcion_estado("pendiente"))
        if "proyecto" in base.prop and args.proyecto != base.titulo:
            if base.tipo("proyecto") == "relation":
                if not args.proyecto_ref:
                    raise Fallo(f"No sé qué página es el proyecto «{args.proyecto}»",
                                tipo="no-se-crea-aqui")
                propiedades[base.prop["proyecto"]] = {"relation": [{"id": args.proyecto_ref}]}
            else:
                propiedades[base.prop["proyecto"]] = base.escribir_valor("proyecto", args.proyecto)
        if args.dificultad and "dificultad" in base.prop:
            opcion = next((o for o in base.opciones("dificultad")
                           if dificultad(o) == args.dificultad), args.dificultad)
            propiedades[base.prop["dificultad"]] = base.escribir_valor("dificultad", opcion)
        if args.version and "version" in base.prop:
            propiedades[base.prop["version"]] = base.escribir_valor("version", args.version)
        pagina = self.api.pedir("POST", "/pages", {"parent": {"database_id": base.id},
                                                   "properties": propiedades})
        return {"esquema": ESQUEMA, "cambio": True, "tarea": base.tarea(pagina)}

    def _base_para(self, proyecto):
        """En qué base se crea una tarea de ese proyecto."""
        bases = self.bases()
        por_titulo = [b for b in bases if llano(b.titulo) == llano(proyecto)]
        if por_titulo:
            return por_titulo[0]
        con_proyecto = [b for b in bases if "proyecto" in b.prop]
        if len(con_proyecto) == 1:
            return con_proyecto[0]
        raise Fallo(f"No sé en qué base de Notion va el proyecto «{proyecto}»",
                    tipo="no-se-crea-aqui")


def protocolo(args):
    return {
        "esquema": ESQUEMA, "nombre": "notion", "lectura": True, "escritura": True,
        "verbos": ["doctor", "escanear", "estado", "agente", "marcar", "crear"],
        "parametros": {
            "database_id": "La base con las tareas: los 32 caracteres de su URL. Para varias, "
                           "database_ids=[\"…\",\"…\"] (cada una sin «Proyecto» es un proyecto).",
            "token_env": "La variable de entorno con el token de la integración (por defecto "
                         "NOTION_TOKEN). El token nunca va en la config.",
            "token_archivo": "Si la variable no está: un archivo solo con el token, con permisos "
                             f"600 (por defecto {TOKEN_ARCHIVO}). Es lo que ven el board y la "
                             "barra, que no arrancan desde una shell.",
            "propiedades": "Cómo se llaman en tu base, si no son las de fábrica: "
                           + json.dumps({k: v for k, v in PROPIEDADES.items() if v},
                                        ensure_ascii=False),
            "estados": "Qué opción de Notion es cada estado de Cotejo, si no son las de fábrica: "
                       + json.dumps(ESTADOS_NOTION, ensure_ascii=False),
        },
        "ejemplo": {"tipo": "externa", "comando": "cotejo-notion", "token_env": "NOTION_TOKEN",
                    "database_id": "0123456789abcdef0123456789abcdef"},
        "campos_tarea": ["id", "texto", "estado", "agente", "dificultad", "hecha", "version",
                         "url"],
        "estados": list(ESTADOS),
    }


def analizador():
    partes = argparse.ArgumentParser(prog="cotejo-notion",
                                     description="Adaptador de Cotejo para Notion.")
    sub = partes.add_subparsers(dest="verbo", required=True)
    sub.add_parser("doctor").set_defaults(metodo="doctor")
    sub.add_parser("protocolo").set_defaults(metodo=None)
    escanear = sub.add_parser("escanear")
    escanear.add_argument("--hechas", action="store_true")
    escanear.set_defaults(metodo="escanear")
    for verbo, valor in (("estado", "nuevo"), ("agente", "quien")):
        uno = sub.add_parser(verbo)
        uno.add_argument("ref")
        uno.add_argument(valor)
        uno.add_argument("--esperado")
        uno.set_defaults(metodo=verbo)
    marcar = sub.add_parser("marcar")
    marcar.add_argument("ref")
    marcar.add_argument("--hecha", action="store_true")
    marcar.add_argument("--pendiente", dest="hecha", action="store_false")
    marcar.add_argument("--esperado")
    marcar.set_defaults(metodo="marcar")
    crear = sub.add_parser("crear")
    crear.add_argument("--proyecto", required=True)
    crear.add_argument("--proyecto-ref", dest="proyecto_ref")
    crear.add_argument("--texto", required=True)
    crear.add_argument("--dificultad")
    crear.add_argument("--version")
    crear.set_defaults(metodo="crear")
    return partes


def main():
    args = analizador().parse_args()
    try:
        if args.metodo is None:
            salida = protocolo(args)
        else:
            salida = getattr(Adaptador(), args.metodo)(args)
        codigo = 0
    except Fallo as fallo:
        # `doctor` contesta siempre con `ok`, también cuando lo que falla es la config: es la
        # pregunta «¿funciona?», y «no, por esto» es una respuesta, no un error.
        if args.verbo == "doctor":
            salida = {"esquema": ESQUEMA, "ok": False, "mensaje": fallo.datos["error"],
                      "salida": fallo.datos["salida"]}
            codigo = 0
        else:
            salida, codigo = fallo.datos, 3
    json.dump(salida, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
