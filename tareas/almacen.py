"""El almacén `.cotejo/` de un repo (v1.2): el conocimiento del proyecto, una entrada por archivo.

Las tareas viven en `.cotejo/tareas.md` y las lleva `fuentes/repo.py`. Esto es todo lo demás:
decisiones, arquitectura, problemas, aprendizajes, bitácora, referencias y las fichas de los
recursos, cada uno en su carpeta y cada entrada en su archivo de Markdown con un frontmatter
mínimo. Es el contrato del que cuelgan los verbos (`contexto`, `buscar`, `leer`, `proponer`,
`anotar`, `editar`, `resolver`) y el importador: ninguno de ellos abre un archivo de
`.cotejo/` por su cuenta.

Lo que promete, y por qué:

- **Ids estables.** Cada entrada lleva `id` en el frontmatter, con un prefijo por tipo y cuatro
  caracteres en base36 (`dec-x7k2`). El archivo se puede renombrar y el id sigue nombrando la
  misma entrada, porque se busca por el frontmatter y nunca por el nombre. La bitácora es la
  excepción: un archivo por día, y el día es su id.
- **Lectura tolerante.** Un frontmatter roto no rompe nada: la entrada sale en `avisos`, con su
  archivo y qué tiene, y las demás se leen igual. Que falte una entrada porque está rota no es
  lo mismo que que no exista, y esa diferencia hay que poder contarla (como en las fuentes).
- **Escritura verificada por versión.** `version` es un hash del archivo tal como se leyó.
  Quien quiera cambiar una entrada pasa la versión que vio, y si el archivo ya no es ese se
  levanta `EntradaCambiada` sin escribir. El archivo se reemplaza entero de forma atómica.
- **Las decisiones no se editan.** Su texto no cambia nunca: una decisión nueva la reemplaza.
  Lo único que se mueve de una decisión es su `estado`, y solo por `TRANSICIONES`. Quién puede
  pedir cada transición (aceptar es de la persona, en el board) no se decide aquí, sino en los
  verbos: el almacén no sabe quién lo llama.
- **La bitácora solo crece.** Se añade al final del archivo del día; no hay forma de
  reescribirla.

No importa GTK, como el resto del núcleo.
"""

import difflib
import hashlib
import os
import random
import re
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

CARPETA = ".cotejo"
ARCHIVO_PROYECTO = "proyecto.md"
ID_PROYECTO = "proyecto"
CARPETA_RELEASES = "releases"  # las notas de cada versión (`cotejo release --aplicar`)
ALFABETO_ID = "abcdefghijklmnopqrstuvwxyz0123456789"
LARGO_ID = 4


@dataclass(frozen=True)
class Tipo:
    """Qué es cada clase de entrada: dónde vive, cómo se llama su id y qué se le puede hacer."""

    nombre: str
    carpeta: str
    prefijo: str  # "" en los que no llevan id generado (bitácora, proyecto)
    claves: tuple  # el frontmatter mínimo, en el orden en que se escribe
    estados: tuple = ()  # el primero es con el que nace
    editable: bool = False  # si el texto se puede cambiar en el sitio (`editar`)
    con_fecha: bool = False  # si el nombre del archivo empieza por la fecha


TIPOS = {t.nombre: t for t in (
    Tipo("decision", "decisiones", "dec",
         ("id", "fecha", "temas", "estado", "autor", "reemplaza"),
         estados=("propuesta", "aceptada", "reemplazada"), con_fecha=True),
    Tipo("problema", "problemas", "pro", ("id", "fecha", "temas", "estado"),
         estados=("abierto", "resuelto"), con_fecha=True),
    Tipo("arquitectura", "arquitectura", "arq", ("id", "temas", "actualizado"), editable=True),
    Tipo("aprendizaje", "aprendizajes", "apr", ("id", "fecha", "temas"), con_fecha=True),
    Tipo("bitacora", "bitacora", "", ("fecha",)),
    Tipo("referencia", "referencias", "ref", ("id", "temas", "resumen", "origen"),
         editable=True),
    Tipo("recurso", "recursos", "rec", ("id", "archivo", "temas", "resumen", "origen", "ficha"),
         editable=True),
    Tipo("proyecto", "", "", ("id",), editable=True),
)}

POR_PREFIJO = {t.prefijo: t for t in TIPOS.values() if t.prefijo}
POR_CARPETA = {t.carpeta: t for t in TIPOS.values() if t.carpeta}

# Las únicas formas en que se mueve el estado de una entrada. Una decisión aceptada no vuelve a
# propuesta: si estaba mal, se reemplaza. Un problema resuelto sí se reabre, sin costo.
TRANSICIONES = {
    "decision": {("propuesta", "aceptada"), ("propuesta", "reemplazada"),
                 ("aceptada", "reemplazada")},
    "problema": {("abierto", "resuelto"), ("resuelto", "abierto")},
}

# Lo que dice `resumen` mientras nadie lo ha revisado: el importador lo deja así.
PENDIENTE = "pendiente"

ID_RE = re.compile(r"^([a-z]{3})-([a-z0-9]{%d})$" % LARGO_ID)
RELEASE_RE = re.compile(r"^v\d+\.\d+\.\d+$")
FECHA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CLAVE_RE = re.compile(r"^([A-Za-z_][\w-]*):(?:\s+(.*))?$")
ITEM_RE = re.compile(r"^\s+-\s+(.*)$")
TITULO_RE = re.compile(r"^#\s+(.+?)\s*#*\s*$")


# --- errores ---------------------------------------------------------------------------------

class EntradaCambiada(Exception):
    """La entrada ya no está como cuando se leyó: su versión no coincide.

    Es la misma garantía que `TareaCambiada` da con las tareas, y por la misma razón: lo que
    se evita es pisar en silencio lo que otro escribió entre la lectura y la escritura.
    """

    def __init__(self, entrada_id, version_vista, version_actual):
        super().__init__(f"«{entrada_id}» cambió desde que la leíste (viste {version_vista}, "
                         f"ahora es {version_actual}): vuelve a leerla y reintenta.")
        self.entrada_id = entrada_id
        self.version_actual = version_actual


class EntradaNoExiste(Exception):
    """No hay ninguna entrada con ese id. `parecidos` trae los ids que más se le acercan."""

    def __init__(self, entrada_id, parecidos=()):
        texto = f"No hay ninguna entrada «{entrada_id}» en {CARPETA}/."
        if parecidos:
            texto += f" ¿Buscabas {', '.join(parecidos)}?"
        super().__init__(texto)
        self.entrada_id = entrada_id
        self.parecidos = list(parecidos)


class IdRepetido(Exception):
    """Dos archivos dicen ser la misma entrada. Escribir en uno sería escoger a ciegas."""

    def __init__(self, entrada_id, rutas):
        super().__init__(f"«{entrada_id}» está en más de un archivo: {', '.join(rutas)}. "
                         f"Uno de los dos necesita otro id.")
        self.entrada_id = entrada_id
        self.rutas = list(rutas)


class NoSeEdita(Exception):
    """Lo que se pidió no se le puede hacer a esa entrada, y el mensaje dice qué sí."""


class FrontmatterRoto(ValueError):
    """El frontmatter de un archivo no se entiende. Al leer el almacén se vuelve un aviso."""


# --- entradas --------------------------------------------------------------------------------

@dataclass
class Entrada:
    """Una entrada del almacén, como la ven los verbos.

    `ruta` es relativa a `.cotejo/` y con barras `/` en cualquier sistema, para que salga igual
    en el JSON de Linux y en el de Windows. `version` es lo que hay que devolver al escribir.
    """

    id: str
    tipo: str
    ruta: str
    titulo: str
    datos: dict = field(default_factory=dict)  # el frontmatter, con las listas ya como listas
    cuerpo: str = ""  # lo que va después del frontmatter, tal cual
    version: str = ""

    @property
    def temas(self):
        return list(self.datos.get("temas") or [])

    @property
    def estado(self):
        return self.datos.get("estado", "")

    def resumen(self, largo=160):
        """Una línea que deje decidir si vale la pena abrirla.

        Si la entrada trae `resumen` revisado, ese. Si no (o sigue `pendiente`), el primer
        párrafo del cuerpo que no sea el título, recortado. Es lo que `buscar` pone por línea.
        """
        propio = str(self.datos.get("resumen") or "").strip()
        if propio and propio != PENDIENTE:
            return _recortar(propio, largo)
        for parrafo in re.split(r"\n\s*\n", self.cuerpo):
            texto = " ".join(l.strip() for l in parrafo.strip().splitlines()
                             if not TITULO_RE.match(l.strip()))
            if texto:
                return _recortar(texto, largo)
        return ""

    def como_dict(self, con_cuerpo=False):
        # Las claves propias ganan al frontmatter: `version: 1.2.4` de `proyecto.md` (v1.2.4)
        # no puede tapar el hash que `editar --version` necesita. Esa sale por `tareas.version`.
        propias = {"id": self.id, "tipo": self.tipo, "titulo": self.titulo, "ruta": self.ruta,
                   "version": self.version}
        datos = {**propias, **{k: v for k, v in self.datos.items() if k not in propias}}
        if con_cuerpo:
            datos["cuerpo"] = self.cuerpo
        return datos


def version_de(contenido):
    """La versión de un archivo: los primeros 12 caracteres del sha256 de sus bytes."""
    if isinstance(contenido, str):
        contenido = contenido.encode("utf-8")
    return hashlib.sha256(contenido).hexdigest()[:12]


# --- el almacén ------------------------------------------------------------------------------

class Almacen:
    """El `.cotejo/` de un repo. `raiz` es el repo, no la carpeta `.cotejo/`."""

    def __init__(self, raiz):
        self.raiz = Path(raiz)
        self.base = self.raiz / CARPETA

    def existe(self):
        return self.base.is_dir()

    # --- leer ------------------------------------------------------------

    def entradas(self, tipo=None, avisos=None):
        """Todas las entradas (o las de un tipo), ordenadas por ruta.

        Lo que no se pudo leer va a `avisos`, si se pasa una lista, como `{"nota", "motivo"}`
        —la misma forma que los avisos de las fuentes, para que `contexto` los enseñe igual—, y
        no sale en la lista.
        """
        if tipo is not None and tipo not in TIPOS:
            raise ValueError(f"No conozco el tipo «{tipo}». Los que hay: {', '.join(TIPOS)}.")
        tipos = [TIPOS[tipo]] if tipo else list(TIPOS.values())
        encontradas = []
        for t in tipos:
            for ruta in self._archivos(t):
                entrada = self._leer_archivo(ruta, t, avisos)
                if entrada is not None:
                    encontradas.append(entrada)
        self._avisar_repetidos(encontradas, avisos)
        return encontradas

    def leer(self, entrada_id):
        """La entrada con ese id. Levanta `EntradaNoExiste` (con los parecidos) o `IdRepetido`."""
        entrada_id = str(entrada_id).strip()
        tipo = self._tipo_de_id(entrada_id)
        candidatas = self.entradas(tipo.nombre if tipo else None)
        iguales = [e for e in candidatas if e.id == entrada_id]
        if len(iguales) > 1:
            raise IdRepetido(entrada_id, [e.ruta for e in iguales])
        if iguales:
            return iguales[0]
        todos = [e.id for e in (candidatas if tipo else self.entradas())]
        raise EntradaNoExiste(entrada_id, difflib.get_close_matches(entrada_id, todos, n=3,
                                                                    cutoff=0.6))

    # --- escribir --------------------------------------------------------

    def crear(self, tipo, titulo, texto="", temas=(), nombre=None, **campos):
        """Una entrada nueva con su id. Devuelve la entrada como quedó, con su versión.

        El estado nace en el primero de su tipo (`propuesta`, `abierto`) salvo que se pase
        otro: el importador crea decisiones `aceptada`, y esa excepción es suya, no de aquí.
        `nombre` elige el nombre del archivo (sin `.md` ni fecha) en vez de sacarlo del
        título: el importador lo necesita para saber, antes de escribir, a dónde apuntan los
        enlaces que reescribe.
        """
        t = self._tipo(tipo)
        if t.nombre == "bitacora":
            raise NoSeEdita("La bitácora no se crea por entradas: se añade con `bitacora`.")
        if t.nombre == "proyecto":
            return self._crear_proyecto(titulo, texto)
        titulo = _una_linea(titulo)
        if not titulo:
            raise ValueError("Una entrada necesita título.")
        if t.nombre == "recurso" and not campos.get("archivo"):
            raise ValueError("La ficha de un recurso necesita `archivo`: la ruta de la imagen "
                             "dentro de recursos/.")
        datos = {"id": self._id_nuevo(t)}
        hoy = _hoy()
        for clave in t.claves[1:]:
            if clave in campos and campos[clave] is not None:
                datos[clave] = campos[clave]
            elif clave in ("fecha", "actualizado"):
                datos[clave] = hoy
            elif clave == "temas":
                datos[clave] = _temas(temas)
            elif clave == "estado" and t.estados:
                datos[clave] = t.estados[0]
            elif clave in ("resumen", "ficha"):
                datos[clave] = PENDIENTE
        estado = datos.get("estado")
        if t.estados and estado not in t.estados:
            raise ValueError(f"«{estado}» no es un estado de {t.nombre}: {', '.join(t.estados)}.")
        for clave, valor in campos.items():  # lo que no es del frontmatter mínimo, al final
            if clave not in datos and valor is not None:
                datos[clave] = valor

        carpeta = self.base / t.carpeta
        carpeta.mkdir(parents=True, exist_ok=True)
        if nombre:
            nombre = _slug(nombre, largo=120) or datos["id"]
        else:
            nombre = _slug(titulo) or datos["id"]
            if t.con_fecha:
                nombre = f"{datos.get('fecha', hoy)}-{nombre}"
        ruta = _libre(carpeta, nombre)
        contenido = componer(datos, f"# {titulo}\n\n{_con_salto(texto)}" if texto.strip()
                             else f"# {titulo}\n")
        _escribir_nuevo(ruta, contenido)
        return self._leer_archivo(ruta, t, None)

    def reescribir(self, entrada_id, version, texto=None, titulo=None, campos=None):
        """Cambia el texto (y el título o el frontmatter) de una entrada editable, verificado.

        `texto` reemplaza el cuerpo entero bajo el título; si ya empieza por «# <título>», esa
        línea no se repite. `campos` se mezcla con el
        frontmatter; el `id` no se toca nunca. Las decisiones se niegan siempre, y las entradas
        con estado no cambian de estado por aquí: para eso está `poner_estado`, que comprueba
        la transición.
        """
        entrada = self.leer(entrada_id)
        t = TIPOS[entrada.tipo]
        if not t.editable:
            if t.nombre == "decision":
                raise NoSeEdita(f"Las decisiones no se editan: se reemplazan con una nueva "
                                f"(`proponer decision --reemplaza {entrada.id}`).")
            raise NoSeEdita(f"Las entradas de tipo {t.nombre} no se editan en el sitio.")
        campos = dict(campos or {})
        if "id" in campos or "estado" in campos:
            raise NoSeEdita("El id no cambia nunca, y el estado se mueve con `poner_estado`.")
        datos = {**entrada.datos, **campos}
        if "actualizado" in t.claves:
            datos["actualizado"] = _hoy()
        titulo = _una_linea(titulo) if titulo is not None else entrada.titulo
        cuerpo = entrada.cuerpo
        if texto is not None or titulo != entrada.titulo:
            if texto is None:
                texto = _sin_titulo(cuerpo)
            elif _titulo(texto) == titulo:
                # `leer` devuelve el cuerpo con su «# Título»: si vuelve tal cual, no se
                # antepone otro (leer → editar con el mismo cuerpo es idempotente).
                texto = _sin_titulo(texto)
            cuerpo = f"# {titulo}\n\n{_con_salto(texto)}" if texto.strip() else f"# {titulo}\n"
        return self._reemplazar(entrada, version, componer(datos, cuerpo))

    def poner_estado(self, entrada_id, version, nuevo, campos=None):
        """Mueve el estado por una transición permitida, verificado por versión.

        `campos` va con el cambio en la misma escritura (`reemplazada_por`, `solucion`...), para
        que no haga falta una segunda versión entre medias.
        """
        entrada = self.leer(entrada_id)
        # La versión primero: con una vista atrasada, lo que hay que decir es «vuelve a leerla»,
        # no que la transición no vale desde un estado que ya no es el que se vio.
        if entrada.version != version:
            raise EntradaCambiada(entrada.id, version, entrada.version)
        permitidas = TRANSICIONES.get(entrada.tipo, set())
        if (entrada.estado, nuevo) not in permitidas:
            posibles = sorted(b for a, b in permitidas if a == entrada.estado)
            raise NoSeEdita(f"«{entrada.id}» está {entrada.estado or 'sin estado'} y no puede "
                            f"pasar a {nuevo}." + (f" Puede pasar a: {', '.join(posibles)}."
                                                    if posibles else ""))
        campos = dict(campos or {})
        campos.pop("id", None)
        datos = {**entrada.datos, **campos, "estado": nuevo}
        return self._reemplazar(entrada, version, componer(datos, entrada.cuerpo))

    def bitacora(self, texto, fecha=None):
        """Añade `texto` al final del archivo del día. Devuelve la entrada del día.

        Se abre en modo de añadir y se escribe de una vez: dos agentes que anotan a la vez
        quedan los dos, uno detrás del otro. Por eso no pide versión: no reemplaza nada.
        """
        texto = _con_salto(texto.strip())
        if not texto.strip():
            raise ValueError("La bitácora no recibe entradas vacías.")
        fecha = fecha or _hoy()
        if not FECHA_RE.match(fecha):
            raise ValueError(f"«{fecha}» no es una fecha AAAA-MM-DD.")
        carpeta = self.base / TIPOS["bitacora"].carpeta
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta = carpeta / f"{fecha}.md"
        try:
            _escribir_nuevo(ruta, componer({"fecha": fecha}, f"# {fecha}\n"))
        except FileExistsError:
            pass
        bloque = f"\n{time.strftime('%H:%M')} · {texto}"
        with open(ruta, "a", encoding="utf-8", newline="") as archivo:
            archivo.write(bloque)
        return self._leer_archivo(ruta, TIPOS["bitacora"], None)

    def importar_dia(self, fecha, texto):
        """El día entero de una bitácora que viene de otro sitio, tal cual. (entrada, creada).

        Es la única forma de escribir un día que no sea añadiendo, y solo si ese día no existe:
        un día que ya está no se toca (`creada` sale `False`), así que repetir la importación
        no duplica ni reescribe nada de lo que se anotó después.
        """
        if not FECHA_RE.match(str(fecha)):
            raise ValueError(f"«{fecha}» no es una fecha AAAA-MM-DD.")
        carpeta = self.base / TIPOS["bitacora"].carpeta
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta = carpeta / f"{fecha}.md"
        try:
            _escribir_nuevo(ruta, componer({"fecha": fecha}, f"# {fecha}\n\n{_con_salto(texto.strip())}"))
            creada = True
        except FileExistsError:
            creada = False
        return self._leer_archivo(ruta, TIPOS["bitacora"], None), creada

    def escribir_release(self, etiqueta, contenido, version=None):
        """Las notas de una versión en `releases/<etiqueta>.md`. `(hecho, ruta, version)`.

        No es un tipo de entrada (no tiene id ni sale en `buscar`): es lo que `cotejo release
        --aplicar` deja para la persona que etiqueta. Idempotente: con el mismo contenido no
        escribe (`ya-estaba`). Si el archivo ya existe con otro, solo se reescribe pasando su
        `version` (hash), como cualquier entrada; si no, `EntradaCambiada` sin escribir.
        """
        if not RELEASE_RE.match(str(etiqueta)):
            raise ValueError(f"«{etiqueta}» no es una etiqueta vX.Y.Z.")
        carpeta = self.base / CARPETA_RELEASES
        ruta = carpeta / f"{etiqueta}.md"
        relativa = f"{CARPETA_RELEASES}/{etiqueta}.md"
        nueva = version_de(contenido)
        try:
            actual = version_de(ruta.read_bytes())
        except FileNotFoundError:
            actual = None
        if actual == nueva:
            return "ya-estaba", relativa, actual
        if actual is not None and actual != version:
            raise EntradaCambiada(relativa, version, actual)
        carpeta.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_name(f".{ruta.name}.cotejo-tmp")
        with temporal.open("w", encoding="utf-8", newline="") as archivo:
            archivo.write(contenido)
        os.replace(temporal, ruta)
        return ("escrita" if actual is None else "reescrita"), relativa, nueva

    def release(self, etiqueta):
        """La `version` (hash) de `releases/<etiqueta>.md`, o None si no está."""
        try:
            return version_de((self.base / CARPETA_RELEASES / f"{etiqueta}.md").read_bytes())
        except (FileNotFoundError, NotADirectoryError):
            return None

    # --- por dentro ------------------------------------------------------

    def _tipo(self, nombre):
        if nombre not in TIPOS:
            raise ValueError(f"No conozco el tipo «{nombre}». Los que hay: {', '.join(TIPOS)}.")
        return TIPOS[nombre]

    @staticmethod
    def _tipo_de_id(entrada_id):
        if entrada_id == ID_PROYECTO:
            return TIPOS["proyecto"]
        if FECHA_RE.match(entrada_id):
            return TIPOS["bitacora"]
        m = ID_RE.match(entrada_id)
        return POR_PREFIJO.get(m.group(1)) if m else None

    def _archivos(self, t):
        if t.nombre == "proyecto":
            ruta = self.base / ARCHIVO_PROYECTO
            return [ruta] if ruta.is_file() else []
        carpeta = self.base / t.carpeta
        if not carpeta.is_dir():
            return []
        return sorted(r for r in carpeta.iterdir()
                      if r.is_file() and r.suffix == ".md" and not r.name.startswith("."))

    def _relativa(self, ruta):
        return ruta.relative_to(self.base).as_posix()

    def _leer_archivo(self, ruta, t, avisos):
        relativa = self._relativa(ruta)
        try:
            crudo = ruta.read_bytes()
            contenido = crudo.decode("utf-8")
        except OSError as error:
            _avisar(avisos, relativa, f"no pude abrirla ({error.strerror or error})")
            return None
        except UnicodeDecodeError:
            _avisar(avisos, relativa, "no está en UTF-8")
            return None
        try:
            datos, cuerpo = partir(contenido)
        except FrontmatterRoto as error:
            _avisar(avisos, relativa, f"frontmatter roto: {error}")
            return None

        if t.nombre == "bitacora":
            entrada_id = ruta.stem
            if not FECHA_RE.match(entrada_id):
                _avisar(avisos, relativa, "el nombre de un archivo de bitácora es su fecha "
                                          "(AAAA-MM-DD.md)")
                return None
        elif t.nombre == "proyecto":
            entrada_id = ID_PROYECTO
        else:
            entrada_id = str(datos.get("id") or "")
            m = ID_RE.match(entrada_id)
            if not entrada_id:
                _avisar(avisos, relativa, "no tiene id en el frontmatter")
                return None
            if not m or m.group(1) != t.prefijo:
                _avisar(avisos, relativa, f"el id «{entrada_id}» no es de {t.nombre} "
                                          f"({t.prefijo}-xxxx)")
                return None
        estado = datos.get("estado")
        if t.estados and estado not in t.estados:
            _avisar(avisos, relativa, f"estado «{estado or ''}» desconocido; los de "
                                      f"{t.nombre}: {', '.join(t.estados)}")
            return None
        if "temas" in datos:
            datos["temas"] = _temas(datos["temas"])
        return Entrada(id=entrada_id, tipo=t.nombre, ruta=relativa,
                       titulo=_titulo(cuerpo) or ruta.stem, datos=datos, cuerpo=cuerpo,
                       version=version_de(crudo))

    @staticmethod
    def _avisar_repetidos(entradas, avisos):
        vistas = {}
        for entrada in entradas:
            vistas.setdefault(entrada.id, []).append(entrada.ruta)
        for entrada_id, rutas in vistas.items():
            if len(rutas) > 1:
                for ruta in rutas:
                    _avisar(avisos, ruta, f"el id «{entrada_id}» está repetido en "
                                          f"{', '.join(r for r in rutas if r != ruta)}")

    def _id_nuevo(self, t):
        usados = {e.id for e in self.entradas(t.nombre)}
        # También los que no se pudieron leer: un archivo roto sigue ocupando su id.
        for ruta in self._archivos(t):
            try:
                m = re.search(r"^id:\s*['\"]?([a-z]{3}-[a-z0-9]+)", ruta.read_text("utf-8"),
                              re.MULTILINE)
            except (OSError, UnicodeDecodeError):
                continue
            if m:
                usados.add(m.group(1))
        while True:
            nuevo = f"{t.prefijo}-" + "".join(random.choices(ALFABETO_ID, k=LARGO_ID))
            if nuevo not in usados:
                return nuevo

    def _crear_proyecto(self, titulo, texto):
        ruta = self.base / ARCHIVO_PROYECTO
        self.base.mkdir(parents=True, exist_ok=True)
        titulo = _una_linea(titulo) or self.raiz.name
        cuerpo = f"# {titulo}\n\n{_con_salto(texto)}" if texto.strip() else f"# {titulo}\n"
        try:
            _escribir_nuevo(ruta, componer({"id": ID_PROYECTO}, cuerpo))
        except FileExistsError:
            raise NoSeEdita(f"{CARPETA}/{ARCHIVO_PROYECTO} ya existe: se cambia con `editar "
                            f"{ID_PROYECTO}`.") from None
        return self._leer_archivo(ruta, TIPOS["proyecto"], None)

    def _reemplazar(self, entrada, version, contenido):
        ruta = self.base / entrada.ruta
        try:
            actual = version_de(ruta.read_bytes())
        except FileNotFoundError:
            raise EntradaNoExiste(entrada.id) from None
        if actual != version:
            raise EntradaCambiada(entrada.id, version, actual)
        temporal = ruta.with_name(f".{ruta.name}.cotejo-tmp")
        with temporal.open("w", encoding="utf-8", newline="") as archivo:
            archivo.write(contenido)
        os.replace(temporal, ruta)
        return self._leer_archivo(ruta, TIPOS[entrada.tipo], None)


# --- frontmatter -----------------------------------------------------------------------------

def partir(contenido):
    """(frontmatter, cuerpo) de un archivo. Sin frontmatter, ({}, todo).

    Entiende lo que escribe `componer` y lo que escribe una persona en Obsidian: claves
    escalares, listas en línea (`[a, b]`) y listas en bloque (`- a`). Cualquier otra cosa
    dentro del frontmatter levanta `FrontmatterRoto` con la línea que no se entiende.
    """
    lineas = contenido.splitlines(keepends=True)
    if not lineas or lineas[0].strip() != "---":
        return {}, contenido
    datos = {}
    clave_lista = None
    for numero, linea in enumerate(lineas[1:], start=2):
        limpia = linea.rstrip("\r\n")
        if limpia.strip() == "---":
            return datos, "".join(lineas[numero:])
        if not limpia.strip() or limpia.lstrip().startswith("#"):
            continue
        m = ITEM_RE.match(limpia)
        if m and clave_lista is not None:
            datos[clave_lista].append(_escalar(m.group(1)))
            continue
        m = CLAVE_RE.match(limpia)
        if not m:
            raise FrontmatterRoto(f"la línea {numero} no es «clave: valor» ({limpia.strip()!r})")
        clave, valor = m.group(1), (m.group(2) or "").strip()
        if clave in datos:
            raise FrontmatterRoto(f"«{clave}» aparece dos veces")
        if not valor:
            datos[clave] = []
            clave_lista = clave
            continue
        clave_lista = None
        datos[clave] = _valor(valor, numero)
    raise FrontmatterRoto("empieza con --- pero no se cierra")


def componer(datos, cuerpo):
    """El archivo entero: el frontmatter de `datos` y el cuerpo. Inverso de `partir`."""
    lineas = ["---\n"]
    for clave, valor in datos.items():
        if isinstance(valor, (list, tuple)):
            lineas.append(f"{clave}: [{', '.join(_citar(v, en_lista=True) for v in valor)}]\n")
        else:
            lineas.append(f"{clave}: {_citar(valor)}\n")
    lineas.append("---\n")
    return "".join(lineas) + cuerpo


def _valor(texto, numero):
    if texto.startswith("["):
        if not texto.endswith("]"):
            raise FrontmatterRoto(f"la lista de la línea {numero} no se cierra")
        dentro = texto[1:-1].strip()
        return [_escalar(p) for p in _partir_lista(dentro)] if dentro else []
    return _escalar(texto)


def _partir_lista(texto):
    """Parte `a, "b, c", d` por las comas de fuera de las comillas."""
    partes, actual, comilla = [], "", None
    for caracter in texto:
        if comilla:
            actual += caracter
            if caracter == comilla and not actual.endswith("\\" + comilla):
                comilla = None
        elif caracter in "\"'":
            comilla = caracter
            actual += caracter
        elif caracter == ",":
            partes.append(actual.strip())
            actual = ""
        else:
            actual += caracter
    partes.append(actual.strip())
    return [p for p in partes if p]


def _escalar(texto):
    texto = texto.strip()
    if len(texto) >= 2 and texto[0] == texto[-1] == '"':
        return texto[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if len(texto) >= 2 and texto[0] == texto[-1] == "'":
        return texto[1:-1].replace("''", "'")
    return texto


def _citar(valor, en_lista=False):
    """El valor tal cual si se lee igual de vuelta; entre comillas dobles si no."""
    texto = "" if valor is None else str(valor)
    especial = (not texto or texto != texto.strip() or ": " in texto or " #" in texto
                or texto[0] in "\"'[]{}#&*!|>%@`-,?" or (en_lista and "," in texto)
                or (en_lista and "]" in texto))
    if not especial:
        return texto
    return '"' + texto.replace("\\", "\\\\").replace('"', '\\"') + '"'


# --- utilidades ------------------------------------------------------------------------------

def _hoy():
    """La fecha de hoy en AAAA-MM-DD, aparte para que las pruebas la fijen sin tocar el reloj."""
    return time.strftime("%Y-%m-%d")


def _temas(temas):
    if isinstance(temas, str):
        temas = [temas] if temas.strip() else []
    vistos = []
    for tema in temas or ():
        tema = str(tema).strip().lower()
        if tema and tema not in vistos:
            vistos.append(tema)
    return vistos


def _slug(texto, largo=60):
    """Un nombre de archivo que vale en Linux, macOS y Windows: ASCII, minúsculas y guiones."""
    plano = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", plano.lower()).strip("-")
    return slug[:largo].rstrip("-")


def _libre(carpeta, nombre):
    """`carpeta/nombre.md`, o `nombre-2.md`, `-3`... si ya existe."""
    ruta = carpeta / f"{nombre}.md"
    numero = 2
    while ruta.exists():
        ruta = carpeta / f"{nombre}-{numero}.md"
        numero += 1
    return ruta


def _escribir_nuevo(ruta, contenido):
    """Crea el archivo solo si no existe (`FileExistsError` si sí): crear nunca pisa."""
    with open(ruta, "x", encoding="utf-8", newline="") as archivo:
        archivo.write(contenido)


def _titulo(cuerpo):
    for linea in cuerpo.splitlines():
        if linea.strip():
            m = TITULO_RE.match(linea.strip())
            return m.group(1) if m else ""
    return ""


def _sin_titulo(cuerpo):
    lineas = cuerpo.splitlines(keepends=True)
    for i, linea in enumerate(lineas):
        if linea.strip():
            if TITULO_RE.match(linea.strip()):
                return "".join(lineas[i + 1:]).lstrip("\r\n")
            break
    return cuerpo


def _una_linea(texto):
    return " ".join(str(texto or "").split())


def _con_salto(texto):
    return texto if texto.endswith("\n") else texto + "\n"


def _recortar(texto, largo):
    texto = " ".join(texto.split())
    return texto if len(texto) <= largo else texto[:largo - 1].rstrip() + "…"


def _avisar(avisos, ruta, motivo):
    if avisos is not None:
        avisos.append({"nota": f"{CARPETA}/{ruta}", "motivo": motivo})
