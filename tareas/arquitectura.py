"""La arquitectura dibujable (v1.3.0): las piezas de un proyecto en cuatro capas.

Una entrada `arquitectura` del almacén puede llevar, además de su texto, una sección
`## Piezas` con una tabla de Markdown, una fila por pieza:

    ## Piezas

    | Capa | Pieza | Qué es | Tecnología | Tareas |
    | --- | --- | --- | --- | --- |
    | ve | Pantalla de pedidos | Donde el cliente elige y paga | React | cotejo-ab12cd, cotejo-ef34gh |
    | guarda | Pedidos | La lista de pedidos de cada día | SQLite | |

- **Capa**: una de `CAPAS` —qué *ve* la gente, qué *hace* el sistema, qué *guarda*, con qué se
  *conecta*—, decididas por el dueño en el planning de la fase 2.
- **Pieza**: el nombre, corto (≤ `LARGO_NOMBRE`), porque es la etiqueta del mapa. Su `id` es
  el nombre hecho slug y no se repite dentro del proyecto.
- **Qué es**: una frase en llano (≤ `LARGO_FRASE`), para alguien que no programa.
- **Tecnología**: puede ir vacía (un proyecto que empieza aún no la sabe).
- **Tareas**: ids de tareas separados por comas o espacios; puede ir vacía. Un texto que no es
  un id («Crear el login») **no es error**: si coincide con el nombre de una tarea existente
  se enlaza (`con_estado(..., textos_por_id)`) y si no se ignora sin avisar.

Sin la sección, la entrada es texto libre, como antes de la 1.3.0, y se sigue leyendo igual:
`analizar` dice `dibujable=False` y no hay nada que validar.

El estado de cada pieza sale de sus tareas (`estado_pieza`), en este orden:

- `por-comprobar`: alguna tarea está en «Para comprobar» (por-validar). Es lo único que la
  interfaz pinta en verde, como en el board.
- `hecho`: todas sus tareas están hechas.
- `en-curso`: alguna está en curso.
- `falta`: el resto. **Una pieza sin tareas —o cuyas tareas no existen— está en `falta`**:
  nadie ha hecho ni prometido nada que la cubra. Quien la dibuje puede distinguirla por
  `total == 0`, pero no es un quinto estado.

Todo aquí es puro: ni archivos, ni fuentes, ni GTK. Los verbos (`anotar`, `leer`, `editar`,
`contexto`, en `conocimiento.py`) le pasan el cuerpo de la entrada y las columnas de las
tareas; la constelación y el mapa del board pueden llamar a lo mismo.
"""

import re
import unicodedata
from dataclasses import dataclass, field

CAPAS = ("ve", "hace", "guarda", "conecta")
ESTADOS = ("hecho", "en-curso", "por-comprobar", "falta")
CABECERA = ("Capa", "Pieza", "Qué es", "Tecnología", "Tareas")
TITULO_SECCION = "Piezas"
LARGO_NOMBRE = 40
LARGO_FRASE = 140

_SECCION_RE = re.compile(r"^#{2,3}\s+(.+?)\s*#*\s*$")
_FILA_RE = re.compile(r"^\s*\|")
_SEPARADOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
_TAREA_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")
_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*-[A-Za-z0-9][A-Za-z0-9-]*$")  # como cotejo-ab12cd
_PREFIJO_VIEJO, _PREFIJO = "foco-", "cotejo-"  # como `modelo.id_actual`, sin importar el modelo


@dataclass(frozen=True)
class Pieza:
    """Una pieza de la arquitectura, tal como está escrita (sin estado)."""

    id: str
    capa: str
    nombre: str
    frase: str
    tecnologia: str = ""
    tareas: tuple = ()
    textos: tuple = ()   # fragmentos de la celda de tareas que no son ids (texto libre)

    def como_dict(self):
        return {"id": self.id, "capa": self.capa, "nombre": self.nombre, "frase": self.frase,
                "tecnologia": self.tecnologia, "tareas": list(self.tareas),
                "textos": list(self.textos)}


@dataclass(frozen=True)
class Analisis:
    """Lo que dice `analizar` de un cuerpo: si es dibujable, sus piezas válidas y sus errores.

    Una fila con error no sale en `piezas`; el error dice cuál es y qué tiene, para que `anotar`
    y `editar` se nieguen con eso y `leer`/`contexto` lo enseñen como aviso.
    """

    dibujable: bool
    piezas: tuple = ()
    errores: tuple = field(default_factory=tuple)


# --- leer ------------------------------------------------------------------------------------


def analizar(cuerpo):
    """Las piezas de la sección `## Piezas` de `cuerpo`, validadas. Sin la sección, texto libre."""
    filas = _filas_de_la_seccion(cuerpo or "")
    if filas is None:
        return Analisis(dibujable=False)
    errores, piezas, vistas = [], [], {}
    datos = [f for f in filas if not _SEPARADOR_RE.match(f)]
    if datos and _es_cabecera(_celdas(datos[0])):
        datos = datos[1:]
    if not datos:
        errores.append(f"la sección «{TITULO_SECCION}» no tiene ninguna fila de pieza")
    for numero, fila in enumerate(datos, start=1):
        try:
            pieza = _pieza(_celdas(fila))
        except ValueError as error:
            errores.append(f"pieza {numero}: {error}")
            continue
        if pieza.id in vistas:
            errores.append(f"pieza {numero}: «{pieza.nombre}» repite el nombre de la pieza "
                           f"{vistas[pieza.id]}")
            continue
        vistas[pieza.id] = numero
        piezas.append(pieza)
    return Analisis(dibujable=True, piezas=tuple(piezas), errores=tuple(errores))


def pieza_de_texto(texto):
    """Una pieza desde «capa|nombre|frase|tecnología|tareas» (lo que recibe `anotar --pieza`).

    Las dos últimas partes se pueden omitir. Levanta `ValueError` con lo que tiene mal.
    """
    partes = _partir(texto)
    if len(partes) < 3:
        raise ValueError(f"«{texto}» necesita al menos capa|nombre|frase "
                         "(y opcionalmente |tecnología|tareas)")
    return _pieza(partes)


def tabla(piezas):
    """La sección `## Piezas` con su tabla: lo inverso de `analizar`."""
    lineas = [f"## {TITULO_SECCION}", "", "| " + " | ".join(CABECERA) + " |",
              "| " + " | ".join("---" for _ in CABECERA) + " |"]
    for p in piezas:
        celdas = (p.capa, p.nombre, p.frase, p.tecnologia,
                  ", ".join([*p.tareas, *p.textos]))
        lineas.append("| " + " | ".join(_escapar(c) for c in celdas) + " |")
    return "\n".join(lineas) + "\n"


# --- el estado de cada pieza -----------------------------------------------------------------


def estado_pieza(columnas):
    """El estado de una pieza desde las columnas de sus tareas («pendiente», «en-curso»,
    «por-validar», «hecha»). Lista vacía —pieza sin tareas— es `falta`."""
    columnas = list(columnas)
    if "por-validar" in columnas:
        return "por-comprobar"
    if columnas and all(c == "hecha" for c in columnas):
        return "hecho"
    if "en-curso" in columnas:
        return "en-curso"
    return "falta"


def tarea_por_texto(texto, textos_por_id):
    """El id de la tarea cuyo nombre coincide con `texto`, o None. Coincide si es igual o uno
    contiene al otro (mínimo 4 letras); si hay varias, solo vale la igual o la única."""
    buscado = _plano(texto)
    if len(buscado) < 4:
        return None
    iguales, parecidas = [], []
    for ident, nombre in (textos_por_id or {}).items():
        plano = _plano(nombre)
        if plano == buscado:
            iguales.append(ident)
        elif len(plano) >= 4 and (buscado in plano or plano in buscado):
            parecidas.append(ident)
    if iguales:
        return iguales[0]
    return parecidas[0] if len(parecidas) == 1 else None


def con_estado(piezas, columnas_por_id, textos_por_id=None):
    """Cada pieza como dict, con `estado`, `total` (tareas que existen), `cuenta` por columna y
    `desconocidas` (ids que no son de ninguna tarea; no cuentan para el estado). El texto libre
    de la celda de tareas se enlaza por nombre con `textos_por_id` ({id: texto}) o se ignora."""
    resultado = []
    for pieza in piezas:
        enlazadas = []
        for texto in pieza.textos:
            ident = tarea_por_texto(texto, textos_por_id)
            if ident and ident in columnas_por_id and ident not in pieza.tareas \
                    and ident not in enlazadas:
                enlazadas.append(ident)
        pieza = Pieza(**{**pieza.__dict__, "tareas": (*pieza.tareas, *enlazadas)}) \
            if enlazadas else pieza
        columnas = [columnas_por_id[t] for t in pieza.tareas if t in columnas_por_id]
        cuenta = {}
        for columna in columnas:
            cuenta[columna] = cuenta.get(columna, 0) + 1
        datos = pieza.como_dict()
        datos.update(estado=estado_pieza(columnas), total=len(columnas), cuenta=cuenta,
                     desconocidas=[t for t in pieza.tareas if t not in columnas_por_id])
        resultado.append(datos)
    return resultado


def resumen_por_capa(piezas_con_estado):
    """Una línea por capa —«2 piezas: 1 hecho, 1 falta»—, para `contexto`. Las cuatro capas
    salen siempre, en orden, aunque estén vacías («sin piezas»)."""
    resumen = {}
    for capa in CAPAS:
        de_la_capa = [p for p in piezas_con_estado if p["capa"] == capa]
        if not de_la_capa:
            resumen[capa] = "sin piezas"
            continue
        cuenta = [(e, sum(1 for p in de_la_capa if p["estado"] == e)) for e in ESTADOS]
        partes = ", ".join(f"{n} {e}" for e, n in cuenta if n)
        total = len(de_la_capa)
        resumen[capa] = f"{total} pieza{'s' if total != 1 else ''}: {partes}"
    return resumen


# --- por dentro ------------------------------------------------------------------------------


def _filas_de_la_seccion(cuerpo):
    """Las líneas de tabla bajo `## Piezas` (o `###`), o None si no hay tal sección."""
    lineas = cuerpo.splitlines()
    for i, linea in enumerate(lineas):
        m = _SECCION_RE.match(linea.strip())
        if m and _normal(m.group(1)) == _normal(TITULO_SECCION):
            filas = []
            for siguiente in lineas[i + 1:]:
                if _SECCION_RE.match(siguiente.strip()):
                    break
                if _FILA_RE.match(siguiente):
                    filas.append(siguiente)
                elif filas and siguiente.strip():
                    break  # la tabla terminó; lo que sigue es texto
            return filas
    return None


def _pieza(celdas):
    celdas = [" ".join(c.split()) for c in celdas] + [""] * (5 - len(celdas))
    if len(celdas) > 5:
        raise ValueError(f"tiene {len(celdas)} columnas y son 5: {', '.join(CABECERA)}")
    capa, nombre, frase, tecnologia, tareas = celdas
    capa_normal = _normal(capa)
    if capa_normal not in CAPAS:
        raise ValueError(f"la capa «{capa}» no es ninguna de {', '.join(CAPAS)}")
    if not nombre:
        raise ValueError("le falta el nombre")
    if len(nombre) > LARGO_NOMBRE:
        raise ValueError(f"el nombre «{nombre}» pasa de {LARGO_NOMBRE} caracteres; es la "
                         "etiqueta del mapa")
    if not frase:
        raise ValueError(f"«{nombre}» no tiene la frase en llano de qué es")
    if len(frase) > LARGO_FRASE:
        raise ValueError(f"la frase de «{nombre}» pasa de {LARGO_FRASE} caracteres")
    ids, textos = [], []
    for fragmento in re.split(r"[,;]", tareas):
        fragmento = fragmento.strip()
        palabras = [w.lstrip("^") for w in fragmento.split()]
        if not palabras:
            continue
        if not all(_ID_RE.match(w) for w in palabras):
            if fragmento not in textos:
                textos.append(fragmento)   # texto libre: no es un error
            continue
        for tarea in palabras:
            if tarea.startswith(_PREFIJO_VIEJO):
                tarea = _PREFIJO + tarea[len(_PREFIJO_VIEJO):]
            if tarea not in ids:
                ids.append(tarea)
    pieza_id = _slug(nombre)
    if not pieza_id:
        raise ValueError(f"el nombre «{nombre}» no deja un id (usa letras o números)")
    return Pieza(id=pieza_id, capa=capa_normal, nombre=nombre, frase=frase,
                 tecnologia=tecnologia, tareas=tuple(ids), textos=tuple(textos))


def _celdas(fila):
    fila = fila.strip()
    if fila.startswith("|"):
        fila = fila[1:]
    if fila.endswith("|") and not fila.endswith("\\|"):
        fila = fila[:-1]
    return _partir(fila)


def _partir(texto):
    """Parte por `|` sin escapar; `\\|` queda como `|` dentro de la celda."""
    return [p.replace("\\|", "|").strip() for p in re.split(r"(?<!\\)\|", texto)]


def _es_cabecera(celdas):
    return bool(celdas) and _normal(celdas[0]) == "capa"


def _escapar(texto):
    return str(texto).replace("|", "\\|")


def _normal(texto):
    plano = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in plano if not unicodedata.combining(c)).strip().lower()


def _plano(texto):
    """Minúsculas, sin tildes ni signos, para comparar un texto con el nombre de una tarea."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", _normal(texto)).split())


def _slug(texto):
    plano = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", plano.lower()).strip("-")
