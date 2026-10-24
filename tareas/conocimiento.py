"""Los verbos sobre el almacén `.cotejo/` que no son de instalación (v1.2): `buscar`, `leer`,
`proponer`, `anotar`, `bitacora`, `contexto`, `editar` y `resolver`. La arquitectura dibujable
(v1.3.0) la entiende `tareas/arquitectura.py`; aquí solo se le pasan cuerpos y tareas. Mismo patrón que
`conexion.anadir` y `temas.anadir`: un módulo que cuelga sus verbos del analizador de `cli.py`
y nunca abre `.cotejo/` por su cuenta, solo por `tareas/almacen.py`.

(`bitacora`, el verbo, no tiene nada que ver con `tareas/bitacora.py`: ese es el registro de
qué pasó con cada tarea —evidencias, rechazos—, que vive en `rutas.estado()` y no en el
almacén de ningún repo. Comparten nombre y no mucho más.)

Los verbos comparten cómo llegar al almacén: resolver el repo (`--repo`, o la raíz git de la
carpeta actual) y abrir su `Almacen`. Eso vive aquí, en `_abrir`, para no repetirlo y para que
todos fallen igual cuando no hay dónde leer.
"""

import datetime
import os
import subprocess
import unicodedata
from pathlib import Path

from . import bitacora as historial
from . import (almacen, arquitectura, configuracion, importar_obsidian, modelo,
               version as version_proyecto)
from .cli import ESQUEMA, ErrorCLI, imprimir, nucleo


# --- lo que comparten `buscar`, `leer` y `contexto` --------------------------------------------


def _abrir(args):
    """El almacén del repo que toca: `--repo`, o la raíz git desde la carpeta actual.

    Sin repo de git es un error; con repo pero sin `.cotejo/` es otro, porque el arreglo no es
    el mismo: al primero le falta `git init`, al segundo solo `cotejo init`. La comprobación
    es `Almacen.existe()`, la misma que usa el resto del almacén: nada de esto abre un archivo
    de `.cotejo/` a mano.
    """
    repo = getattr(args, "repo", None)
    if repo and not os.path.isdir(repo):
        raise ErrorCLI(f"«{repo}» no es una carpeta",
                       "Pasa en --repo la carpeta del repo, o quítalo para usar la actual.")
    from . import conexion  # aquí dentro: conexion importa de cli.py y esto evita el ciclo
    raiz = conexion._raiz_git(repo or Path.cwd())
    if raiz is None:
        raise ErrorCLI("No estás dentro de un repo git",
                       "`cotejo init` se corre dentro de un repo (o con --repo apuntando a "
                       "uno). Si todavía no lo es, `git init` primero.")
    alm = almacen.Almacen(raiz)
    if not alm.existe():
        raise ErrorCLI("Este repo no tiene .cotejo/", "`cotejo init`")
    return alm


def _normalizar(texto):
    """Minúsculas y sin acentos, para que «café» se encuentre buscando «cafe»."""
    sin_acentos = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin_acentos if not unicodedata.combining(c)).lower()


# --- buscar -------------------------------------------------------------------------------


def _temas_pedidos(texto):
    return [t.strip().lower() for t in (texto or "").split(",") if t.strip()]


def _fecha_de(entrada):
    """`fecha` o `actualizado`, la que tenga su tipo. Vacía si no tiene ninguna de las dos."""
    return str(entrada.datos.get("fecha") or entrada.datos.get("actualizado") or "")


def _coincide(entrada, temas, estado, desde, texto):
    """Si `entrada` pasa todos los filtros pedidos. Cada uno es opcional por su cuenta."""
    if temas and not all(t in entrada.temas for t in temas):
        return False
    if estado and entrada.estado != estado:
        return False
    if desde:
        # Sin `fecha` ni `actualizado` no hay con qué juzgar si es de --desde en adelante, así
        # que se queda fuera: lo mismo que pasaría con cualquier otro filtro sobre un campo
        # que la entrada no tiene.
        fecha = _fecha_de(entrada)
        if not fecha or fecha < desde:
            return False
    if texto:
        campos = (entrada.titulo, entrada.resumen(), entrada.cuerpo)
        if not any(texto in _normalizar(campo) for campo in campos if campo):
            return False
    return True


def _linea(entrada):
    """Lo mínimo para decidir si vale la pena pedir `leer`: id, tipo, título y resumen, más
    el estado si lo tiene. La medida de B2 es que esto pese ~30 tokens por entrada
    (≈4 caracteres por token)."""
    linea = {"id": entrada.id, "tipo": entrada.tipo, "titulo": entrada.titulo,
             "resumen": entrada.resumen()}
    if entrada.estado:
        linea["estado"] = entrada.estado
    return linea


def cmd_buscar(args):
    """Una línea por entrada del almacén: el camino barato para decidir qué vale abrir,
    igual que `tareas` lo es para las tareas."""
    alm = _abrir(args)
    if args.desde and not almacen.FECHA_RE.match(args.desde):
        raise ErrorCLI(f"«{args.desde}» no es una fecha AAAA-MM-DD", "Usa --desde AAAA-MM-DD.")
    avisos = []
    entradas = alm.entradas(args.tipo, avisos)
    temas = _temas_pedidos(args.temas)
    texto = _normalizar(args.texto) if args.texto else None
    filtradas = sorted(
        (e for e in entradas if _coincide(e, temas, args.estado, args.desde, texto)),
        key=lambda e: e.ruta)
    total = len(filtradas)
    mostradas = filtradas[:args.limite]
    datos = {"esquema": ESQUEMA, "total": total, "entradas": [_linea(e) for e in mostradas]}
    if avisos:
        datos["avisos"] = avisos
    fuera = total - len(mostradas)
    if fuera > 0:
        datos["salida"] = (f"Quedaron {fuera} fuera por el límite ({args.limite}); sube "
                           "--limite para verlas.")
    imprimir(datos)
    return 0


# --- leer --------------------------------------------------------------------------------


def cmd_leer(args):
    """La entrada completa (con cuerpo y `version`); de un recurso, también la ruta de su
    archivo —nunca su contenido—, y si existe."""
    alm = _abrir(args)
    try:
        entrada = alm.leer(args.id)
    except almacen.EntradaNoExiste as error:
        raise ErrorCLI(str(error), "`cotejo buscar --texto <algo>`") from error
    except almacen.IdRepetido as error:
        raise ErrorCLI(str(error),
                       "Pon otro id en el frontmatter de uno de los dos archivos.") from error
    datos = entrada.como_dict(con_cuerpo=True)
    if entrada.tipo == "recurso":
        archivo = str(entrada.datos.get("archivo") or "")
        tipo_recurso = almacen.TIPOS["recurso"]
        ruta = f"{almacen.CARPETA}/{tipo_recurso.carpeta}/{archivo}" if archivo else None
        existe = bool(archivo and (alm.base / tipo_recurso.carpeta / archivo).is_file())
        datos["recurso"] = {"ruta": ruta, "existe": existe}
    elif entrada.tipo == "arquitectura":
        analisis = arquitectura.analizar(entrada.cuerpo)
        datos["formato"] = "piezas" if analisis.dibujable else "libre"
        if analisis.dibujable:
            datos["piezas"] = arquitectura.con_estado(
                analisis.piezas, _columnas_por_id(alm.raiz),
                _textos_por_id(alm.raiz) if any(p.textos for p in analisis.piezas) else None)
            if analisis.errores:
                datos["avisos"] = [{"nota": f"{almacen.CARPETA}/{entrada.ruta}", "motivo": e}
                                   for e in analisis.errores]
    imprimir(datos)
    return 0


# --- contexto --------------------------------------------------------------------------------


# De la cabecera `##` de `proyecto.md` (con el emoji que le pone el importador, o sin él) al
# campo de `contexto`. Reutiliza el mismo partidor y la misma normalización de título que
# `importar_obsidian`, para entender las cabeceras que él mismo escribe en `aplicar` (D2).
_CAMPOS_PROYECTO = {
    "objetivo": "objetivo", "stack": "stack", "stack y arquitectura": "stack",
    "arquitectura": "stack", "siguiente paso": "siguiente_paso",
}
LARGO_CAMPO = 500  # tope por campo de proyecto.md, para que un objetivo largo no se coma el 1k

DIAS_VIEJO = 14  # `contexto.dias_viejo` por defecto: días sin tocar `proyecto.md` para ser viejo
TOPE_VIGENTES = 10  # cuántas decisiones y problemas como mucho en `contexto` (v1.2 · B1b): un
                    # almacén importado con historial puede tener decenas, todas `aceptada`, y
                    # listarlas todas costó 2,2k tokens sobre un caso real de 68. El resto no
                    # desaparece: su total sale aparte y `buscar` las trae todas.
LARGO_TITULO_CONTEXTO = 120  # tope del título en esas dos listas; si se corta, la línea trae
                             # `cortado: true` en vez de fingir en silencio que ese es el título
                             # completo (`buscar`/`leer` sí lo dan entero).


def _secciones_proyecto(cuerpo):
    """{"objetivo", "stack", "siguiente_paso"} desde el cuerpo de la entrada `proyecto`.

    Si una cabecera se repite (no debería, pero un frontmatter a mano no lo impide), gana la
    primera. Cada campo se recorta: `contexto` presume un objetivo y un siguiente paso de una
    o dos frases, no la sección entera de una nota larga.
    """
    campos = {"objetivo": "", "stack": "", "siguiente_paso": ""}
    _, secciones = importar_obsidian._secciones(cuerpo)
    for titulo, texto in secciones:
        clave = _CAMPOS_PROYECTO.get(importar_obsidian._clave(titulo))
        if clave and not campos[clave] and texto.strip():
            campos[clave] = almacen._recortar(texto.strip(), LARGO_CAMPO)
    return campos


def _tareas_por_estado(raiz, columnas=None):
    """Cuántas tareas hay en cada columna de `.cotejo/tareas.md`, sin pasar por la config.

    `contexto` habla de un repo (`--repo`, o la raíz git de aquí), no de la lista de repos que
    conoce la instalación, así que se abre una `Repo` ad-hoc apuntando solo a él —el mismo
    truco que usa `importar_obsidian._tarea_de_revision` para crear la tarea de revisión—, en
    vez de duplicar el parser de líneas `- [ ]` que ya tiene `fuentes/obsidian.py`.
    """
    conteo = {clave: 0 for clave, _ in modelo.COLUMNAS}
    for columna in (_columnas_por_id(raiz) if columnas is None else columnas).values():
        conteo[columna] = conteo.get(columna, 0) + 1
    return conteo


def _columnas_por_id(raiz):
    """{id: columna} de cada tarea de `.cotejo/tareas.md` (las hechas también). Las sin id
    llevan una clave propia para seguir contando en `_tareas_por_estado`."""
    from .fuentes.repo import Repo
    fuente = Repo({"repos": [str(raiz)]})
    fuente.repos, fuente.raiz = [raiz], None
    proyectos = fuente.escanear(incluir_hechas=True)
    columnas = {}
    if proyectos:
        for numero, tarea in enumerate([*proyectos[0].tareas, *proyectos[0].hechas]):
            columnas[modelo.id_actual(tarea.id) or f"#{numero}"] = tarea.columna
    return columnas


def _textos_por_id(raiz):
    """{id: texto} de cada tarea de `.cotejo/tareas.md`, para enlazar por nombre."""
    from .fuentes.repo import Repo
    fuente = Repo({"repos": [str(raiz)]})
    fuente.repos, fuente.raiz = [raiz], None
    textos = {}
    for proyecto in fuente.escanear(incluir_hechas=True)[:1]:
        for tarea in [*proyecto.tareas, *proyecto.hechas]:
            ident = modelo.id_actual(tarea.id)
            if ident:
                textos[ident] = tarea.nombre_corto or tarea.texto
    return textos


def _marca_de(alm, entrada):
    """Qué tan reciente es una entrada: su `actualizado` y, a igual fecha, su archivo."""
    try:
        mtime = (alm.base / entrada.ruta).stat().st_mtime_ns
    except OSError:
        mtime = 0
    return (str(entrada.datos.get("actualizado") or ""), mtime)


def piezas_del_repo(alm, columnas=None, avisos=None, entradas=None, textos=None):
    """Las piezas de la arquitectura del almacén, con su estado (v1.3.0).

    Es la API para quien dibuje el proyecto (la constelación, el mapa): una lista de dicts de
    `arquitectura.con_estado`, cada uno con `entrada` (el id de la entrada que la define). Si
    hay varias entradas de arquitectura con tabla (un reintento deja dos), manda la más reciente
    y las demás se ignoran sin error. Las de texto libre no aportan piezas. `textos` ({id:
    nombre}) enlaza por nombre el texto libre de la columna de tareas.
    `entradas` evita releer el almacén si ya se leyó (se filtran las de arquitectura).
    """
    columnas = _columnas_por_id(alm.raiz) if columnas is None else columnas
    if entradas is None:
        entradas = alm.entradas("arquitectura", avisos)
    candidatas = []
    for entrada in (e for e in entradas if e.tipo == "arquitectura"):
        analisis = arquitectura.analizar(entrada.cuerpo)
        if analisis.dibujable:
            candidatas.append((_marca_de(alm, entrada), entrada, analisis))
    if not candidatas:
        return []
    _, entrada, analisis = max(candidatas, key=lambda c: c[0])
    for error in analisis.errores:
        almacen._avisar(avisos, entrada.ruta, error)
    if textos is None and any(p.textos for p in analisis.piezas):
        textos = _textos_por_id(alm.raiz)
    return [{**pieza, "entrada": entrada.id}
            for pieza in arquitectura.con_estado(analisis.piezas, columnas, textos)]


def _linea_vigente(entrada):
    """`id` y título para `decisiones_vigentes`/`problemas_abiertos`, con el título recortado
    (y marcado) si pasa `LARGO_TITULO_CONTEXTO`. Mismo formato de siempre —solo esas dos
    claves, más `cortado` cuando aplica— para no romper lo que ya lee `cotejo mcp` ni las
    pruebas que comparan el conjunto exacto de claves."""
    titulo = entrada.titulo
    recortado = almacen._recortar(titulo, LARGO_TITULO_CONTEXTO)
    linea = {"id": entrada.id, "titulo": recortado}
    if recortado != titulo:
        linea["cortado"] = True
    return linea


def _acotar_vigentes(entradas, tope):
    """Las `tope` más recientes por fecha (o `actualizado`) de una lista ya filtrada por tipo
    y estado, más el total real. Las sin fecha quedan al final (``_fecha_de`` vacío es lo
    mínimo al ordenar al revés), que es la mejor aproximación sin inventarles una."""
    ordenadas = sorted(entradas, key=_fecha_de, reverse=True)
    elegidas = ordenadas[:tope] if tope else ordenadas
    return [_linea_vigente(e) for e in elegidas], len(ordenadas)


def _git_fecha(raiz, *args):
    """Fecha (AAAA-MM-DD) que imprime `git log -1 --format=%cs <args>`, o None si no hay git,
    el archivo no está en un commit o algo falla. Nunca levanta: la frescura es una pista."""
    try:
        hecho = subprocess.run(["git", "-C", str(raiz), "log", "-1", "--format=%cs", *args],
                               stdin=subprocess.DEVNULL, capture_output=True, text=True,
                               timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    texto = hecho.stdout.strip()
    return texto if hecho.returncode == 0 and texto else None


def _ultimo_tag(raiz):
    """(nombre, fecha) del tag más reciente alcanzable desde HEAD, o None si no hay."""
    try:
        hecho = subprocess.run(["git", "-C", str(raiz), "describe", "--tags", "--abbrev=0"],
                               stdin=subprocess.DEVNULL, capture_output=True, text=True,
                               timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    nombre = hecho.stdout.strip()
    if hecho.returncode != 0 or not nombre:
        return None
    fecha = _git_fecha(raiz, nombre)
    return (nombre, fecha) if fecha else None


def _hoy():
    return datetime.date.today()


def dias_viejo(datos=None):
    """`contexto.dias_viejo` de la config, o `DIAS_VIEJO` si falta o no se entiende (`config
    validar` dice qué tiene mal; un valor roto nunca tumba `contexto` ni `entregar`)."""
    datos = configuracion.cargar() if datos is None else datos
    seccion = datos.get("contexto")
    valor = seccion.get("dias_viejo") if isinstance(seccion, dict) else None
    if isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0:
        return valor
    return DIAS_VIEJO


def frescura_proyecto(raiz, campos, entrada=None, hoy=None, limite=None):
    """Qué tan viejo está `proyecto.md` y qué campos conviene revisar. Reutilizable (la usa
    `contexto`; `entregar` puede usarla para avisar).

    La fecha es la del último commit que tocó el archivo; sin git (o sin commit del archivo),
    la de la entrada (`fecha`/`actualizado` del frontmatter). Un campo con texto está viejo si
    esa fecha tiene más de `limite` días (`contexto.dias_viejo`, 14 por defecto) y, cuando el
    repo tiene tags, además es anterior al último tag: lo que se ha editado después de la
    última versión no se acusa. Devuelve `{"actualizado": fecha|"", "dias": n|None, "tag":
    nombre|"", "viejos": [campos], "pistas": [texto]}`. Nunca levanta y nunca frena nada.
    """
    limite = dias_viejo() if limite is None else limite
    hoy = hoy or _hoy()
    ruta = Path(raiz) / almacen.CARPETA / almacen.ARCHIVO_PROYECTO
    fecha = _git_fecha(raiz, "--", str(ruta)) or (_fecha_de(entrada)[:10] if entrada else "")
    resultado = {"actualizado": fecha or "", "dias": None, "tag": "", "viejos": [], "pistas": []}
    try:
        dias = (hoy - datetime.date.fromisoformat(fecha)).days
    except ValueError:
        return resultado
    resultado["dias"] = dias
    tag = _ultimo_tag(raiz)
    if tag:
        resultado["tag"] = tag[0]
    if dias <= limite or (tag and tag[1] <= fecha):
        return resultado
    resultado["viejos"] = [c for c in ("objetivo", "stack", "siguiente_paso") if campos.get(c)]
    if resultado["viejos"]:
        desde = f", anterior al tag {tag[0]}" if tag else ""
        resultado["pistas"].append(
            f"proyecto.md sin tocar desde {fecha} ({dias} días{desde}); revisa "
            f"{', '.join(resultado['viejos'])} y corrígelos con `cotejo editar proyecto`")
    return resultado


def pistas_de_frescura(carpeta):
    """Las pistas de `frescura_proyecto` para el repo que contiene `carpeta` (la actual si es
    None), o [] si no hay repo, no tiene `.cotejo/proyecto.md` o algo falla. La usa `entregar`,
    donde es un aviso: nada de esto puede tumbar una entrega."""
    from . import conexion  # aquí dentro: conexion importa de cli.py y esto evita el ciclo
    try:
        raiz = conexion._raiz_git(carpeta or Path.cwd())
        if raiz is None:
            return []
        entrada = almacen.Almacen(raiz).leer(almacen.ID_PROYECTO)
        return frescura_proyecto(raiz, _secciones_proyecto(entrada.cuerpo), entrada)["pistas"]
    except Exception:
        return []


def cmd_contexto(args):
    """Lo mínimo para empezar a trabajar en el repo sin leer sus notas.

    Objetivo, stack y siguiente paso de `proyecto.md`; cuántas tareas hay en cada columna;
    las decisiones que siguen vigentes (ni reemplazadas ni rechazadas) y los problemas que siguen abiertos
    —las `--tope` más recientes de cada una, con su total real y, si se cortó, una pista a
    `buscar` para las demás—, solo por id y título; y los temas que existen con cuántas
    entradas tiene cada uno. Pensado para costar <1k tokens medido con `medir.py`
    (B1), incluso sobre un almacén importado con decenas de decisiones todas `aceptada` (B1b):
    nada de cuerpos ni resúmenes largos, y nada de listar algo que crece sin tope.

    El frontmatter roto de cualquier entrada sale en `avisos`, con el mismo mecanismo que
    `buscar`: que una entrada no se pudiera leer no debe desaparecer en silencio.
    """
    alm = _abrir(args)
    avisos = []
    entradas = alm.entradas(None, avisos)

    proyecto = {"titulo": "", "objetivo": "", "stack": "", "siguiente_paso": ""}
    try:
        entrada_proyecto = alm.leer(almacen.ID_PROYECTO)
    except almacen.EntradaNoExiste:
        entrada_proyecto = None
    if entrada_proyecto is not None:
        proyecto["titulo"] = entrada_proyecto.titulo
        proyecto.update(_secciones_proyecto(entrada_proyecto.cuerpo))
    frescura = frescura_proyecto(alm.raiz, proyecto, entrada_proyecto)
    if frescura["actualizado"]:
        proyecto["actualizado"] = frescura["actualizado"]

    temas = {}
    for entrada in entradas:
        for tema in entrada.temas:
            temas[tema] = temas.get(tema, 0) + 1

    decisiones_entradas = [e for e in entradas
                           if e.tipo == "decision"
                           and e.estado not in ("reemplazada", "rechazada")]
    problemas_entradas = [e for e in entradas
                          if e.tipo == "problema" and e.estado == "abierto"]
    # Las importadas sin revisar (`autor: importado`, v1.2.3) cuentan aparte y no ocupan el
    # tope: `decisiones_vigentes(_total)` habla solo de las demás. Es un hecho de origen, sin
    # marca de «revisada»: una que sigue valiendo se reemplaza con `proponer decision
    # --reemplaza` y, al aceptarla, ya cuenta como propia.
    importadas = [e for e in decisiones_entradas if e.datos.get("autor") == "importado"]
    decisiones_entradas = [e for e in decisiones_entradas if e.datos.get("autor") != "importado"]
    decisiones, total_decisiones = _acotar_vigentes(decisiones_entradas, args.tope)
    problemas, total_problemas = _acotar_vigentes(problemas_entradas, args.tope)

    columnas = _columnas_por_id(alm.raiz)
    piezas = piezas_del_repo(alm, columnas, avisos, entradas)
    en_curso = version_proyecto.estado(alm.raiz)["en_curso"]
    datos = {
        "esquema": ESQUEMA,
        "proyecto": proyecto,
        "version": en_curso,
        "tareas": _tareas_por_estado(alm.raiz, columnas),
        "decisiones_vigentes": decisiones,
        "decisiones_propuestas": [e.id for e in decisiones_entradas if e.estado == "propuesta"],
        "decisiones_vigentes_total": total_decisiones,
        "decisiones_importadas": len(importadas),
        "problemas_abiertos": problemas,
        "problemas_abiertos_total": total_problemas,
        "temas": dict(sorted(temas.items(), key=lambda par: (-par[1], par[0]))),
    }
    if piezas:  # una línea por capa; el detalle, con `leer <arq-id>`
        datos["arquitectura"] = {"entradas": sorted({p["entrada"] for p in piezas}),
                                 **arquitectura.resumen_por_capa(piezas)}
    pistas = []
    if total_decisiones > len(decisiones):
        pistas.append(f"hay {total_decisiones} decisiones vigentes (mostrando "
                      f"{len(decisiones)}); `cotejo buscar --tipo decision --temas <tema>` "
                      "para verlas todas")
    if total_problemas > len(problemas):
        pistas.append(f"hay {total_problemas} problemas abiertos (mostrando "
                      f"{len(problemas)}); `cotejo buscar --tipo problema --temas <tema>` "
                      "para verlos todos")
    if importadas:
        pistas.append(f"{len(importadas)} decisiones importadas sin revisar, aparte de las "
                      "vigentes; `cotejo buscar --tipo decision` las trae")
    pistas.extend(frescura["pistas"])
    if pistas:
        datos["salida"] = "; ".join(pistas)
    if avisos:
        datos["avisos"] = avisos
    imprimir(datos)
    return 0


# --- proponer ------------------------------------------------------------------------------


def cmd_proponer_decision(args):
    """Una decisión nueva, en `propuesta`, con el agente como autor —nunca se edita su texto—.

    Con `--reemplaza`, lee la vieja antes de crear nada: si no existe, está repetida o ya está
    `reemplazada`, el error sale sin tocar el almacén. Si pasa, crea la nueva con
    `reemplaza=<vieja>` y recién entonces mueve la vieja a `reemplazada` con
    `reemplazada_por=<nueva>`; no hay ninguna acción para `aceptar`, eso es de la persona en
    el board.
    """
    alm = _abrir(args)
    vieja = None
    if args.reemplaza:
        try:
            vieja = alm.leer(args.reemplaza)
        except almacen.EntradaNoExiste as error:
            raise ErrorCLI(str(error), "`cotejo buscar --texto <algo>`") from error
        except almacen.IdRepetido as error:
            raise ErrorCLI(str(error),
                           "Pon otro id en el frontmatter de uno de los dos archivos.") from error
        if vieja.tipo != "decision":
            raise ErrorCLI(f"«{vieja.id}» no es una decisión (es {vieja.tipo}).",
                           "--reemplaza solo vale entre decisiones.")
        if vieja.estado == "reemplazada":
            quien = vieja.datos.get("reemplazada_por")
            raise ErrorCLI(
                f"«{vieja.id}» ya está reemplazada" + (f" por «{quien}»" if quien else "") + ".",
                "Propón la decisión sin --reemplaza, o reemplaza la que ya la reemplazó.")

    nueva = alm.crear("decision", args.titulo, args.texto, temas=_temas_pedidos(args.temas),
                      autor=args.autor, reemplaza=vieja.id if vieja else None)
    datos = {"esquema": ESQUEMA, "id": nueva.id, "ruta": nueva.ruta, "version": nueva.version}
    historial.anotar_verbo("proponer", alm.raiz, tipo="decision", entrada=nueva.id,
                           titulo=nueva.titulo)
    if vieja is not None:
        try:
            actualizada = alm.poner_estado(vieja.id, vieja.version, "reemplazada",
                                          campos={"reemplazada_por": nueva.id})
        except almacen.EntradaCambiada as error:
            raise ErrorCLI(
                f"Creé «{nueva.id}» pero «{vieja.id}» cambió antes de poder dejarla "
                f"reemplazada ({error}).",
                f"Vuelve a leer «{vieja.id}»: si sigue aplicando, pon su estado a mano; "
                f"«{nueva.id}» ya quedó creada, no hace falta repetirla.") from error
        datos["reemplazada"] = {"id": actualizada.id, "ruta": actualizada.ruta,
                                "version": actualizada.version}
    imprimir(datos)
    return 0


# --- anotar --------------------------------------------------------------------------------


def cmd_anotar(args):
    """Una entrada nueva del tipo que toca —problema, aprendizaje, referencia o arquitectura—.

    Apuntar no es resolver ni aceptar: un problema nace `abierto` y una referencia con
    `resumen: pendiente`, igual que crea `Almacen.crear`. Quien quiera moverle el estado o
    revisarla usa otro verbo (`resolver`, cuando llegue); este solo deja constancia.
    """
    alm = _abrir(args)
    titulo = " ".join(args.titulo.split())
    if not titulo:
        raise ErrorCLI("Una entrada necesita título", "Repite con --titulo.")
    texto = args.texto or ""
    analisis = None
    if args.tipo == "arquitectura":
        texto = _texto_con_piezas(texto, getattr(args, "pieza", None) or [])
        analisis = _validar_piezas(texto)
    entrada = alm.crear(args.tipo, titulo, texto, temas=_temas_pedidos(args.temas))
    datos = {"esquema": ESQUEMA, "id": entrada.id, "ruta": entrada.ruta,
             "version": entrada.version}
    if analisis is not None and analisis.dibujable:
        datos["piezas"] = len(analisis.piezas)
    historial.anotar_verbo("anotar", alm.raiz, tipo=args.tipo, entrada=entrada.id,
                           **({"piezas": datos["piezas"]} if "piezas" in datos else {}))
    imprimir(datos)
    return 0


def _texto_con_piezas(texto, crudas):
    """El texto de una arquitectura con la tabla de `--pieza` al final, si se pasó alguna."""
    if not crudas:
        if not texto.strip():
            raise ErrorCLI("Una arquitectura necesita texto o piezas",
                           'Repite con --texto, o con --pieza "capa|nombre|frase|tecnología|'
                           'tareas" una vez por pieza.')
        return texto
    if arquitectura.analizar(texto).dibujable:
        raise ErrorCLI(f"El texto ya trae una sección «## {arquitectura.TITULO_SECCION}» y "
                       "además pasaste --pieza", "Usa una de las dos, no las dos.")
    try:
        piezas = [arquitectura.pieza_de_texto(c) for c in crudas]
    except ValueError as error:
        raise ErrorCLI(f"--pieza: {error}", "Las capas son: " + ", ".join(arquitectura.CAPAS)
                       + ". No se escribió nada.") from error
    tabla = arquitectura.tabla(piezas)
    return f"{texto.rstrip()}\n\n{tabla}" if texto.strip() else tabla


def _validar_piezas(texto):
    """El análisis de `texto`, o ErrorCLI con sus errores si su tabla de piezas tiene alguno."""
    analisis = arquitectura.analizar(texto)
    if analisis.errores:
        raise ErrorCLI("La tabla de piezas tiene errores: " + "; ".join(analisis.errores),
                       "Corrígelos y repite; cada fila es capa (" + "|".join(arquitectura.CAPAS)
                       + "), pieza, qué es, tecnología y tareas. No se escribió nada.")
    return analisis


# --- bitacora --------------------------------------------------------------------------------


def cmd_bitacora(args):
    """Añade `texto` al final de la bitácora de hoy: un archivo por día, que solo crece.

    No pide versión porque no reemplaza nada —dos agentes que anotan a la vez quedan los dos,
    uno detrás del otro—, así que tampoco hay forma de que choque con `EntradaCambiada`.
    """
    alm = _abrir(args)
    texto = args.texto.strip()
    if not texto:
        raise ErrorCLI("La bitácora no recibe entradas vacías", "Pasa el texto a anotar.")
    entrada = alm.bitacora(texto)
    imprimir({"esquema": ESQUEMA, "id": entrada.id, "ruta": entrada.ruta,
             "version": entrada.version})
    return 0


# --- editar --------------------------------------------------------------------------------


def cmd_editar(args):
    """Cambia el texto de una entrada editable (arquitectura, referencia, recurso o
    `proyecto.md`), verificado por la `--version` que se vio al leerla con `leer`.

    Las decisiones no se editan nunca —su texto es fijo, solo se reemplazan—, y una versión
    vieja se niega sin escribir nada: las dos cosas se dicen con el siguiente paso, no solo
    con el error, igual que `TareaCambiada` con las tareas.
    """
    alm = _abrir(args)
    if almacen.Almacen._tipo_de_id(args.id.strip()) is almacen.TIPOS["arquitectura"]:
        _validar_piezas(args.texto)
    try:
        actual = alm.reescribir(args.id, args.version, texto=args.texto)
    except almacen.EntradaNoExiste as error:
        raise ErrorCLI(str(error), "`cotejo buscar --texto <algo>`") from error
    except almacen.IdRepetido as error:
        raise ErrorCLI(str(error),
                       "Pon otro id en el frontmatter de uno de los dos archivos.") from error
    except almacen.NoSeEdita as error:
        mensaje = str(error)
        if mensaje.startswith("Las decisiones no se editan"):
            raise ErrorCLI(
                "Las decisiones no se editan",
                f"`cotejo proponer decision --reemplaza {args.id}`") from error
        raise ErrorCLI(
            mensaje, "Anota una entrada nueva si lo que cambió es otra cosa. No se escribió "
                     "nada.") from error
    except almacen.EntradaCambiada as error:
        raise ErrorCLI(
            f"«{error.entrada_id}» cambió desde que la leíste",
            f"`cotejo leer {error.entrada_id}` y reintenta. No se escribió nada.",
            reintentable=True, codigo=4) from error
    historial.anotar_verbo("editar", alm.raiz, tipo=actual.tipo, entrada=actual.id)
    imprimir({"esquema": ESQUEMA, "id": actual.id, "ruta": actual.ruta,
             "version": actual.version})
    return 0


# --- resolver ------------------------------------------------------------------------------


def cmd_resolver(args):
    """Problema abierto → resuelto, con la solución que lo cerró.

    Solo vale sobre problemas: otro tipo, o un id que no existe, fallan igual que `leer`. No
    pide `--version` porque resolver no cambia el texto, solo mueve el estado del problema que
    acaba de leer; si justo en medio alguien lo cambió, se dice que vuelva a leerlo y reintente,
    igual que en `editar`. Ya resuelto, reintentar es seguro y no vuelve a escribir.
    """
    alm = _abrir(args)
    try:
        entrada = alm.leer(args.id)
    except almacen.EntradaNoExiste as error:
        raise ErrorCLI(str(error), "`cotejo buscar --texto <algo>`") from error
    except almacen.IdRepetido as error:
        raise ErrorCLI(str(error),
                       "Pon otro id en el frontmatter de uno de los dos archivos.") from error
    if entrada.tipo != "problema":
        raise ErrorCLI(f"«{entrada.id}» no es un problema (es {entrada.tipo})",
                       "`resolver` solo vale sobre problemas (pro-xxxx).")
    solucion = " ".join(args.solucion.split())
    if not solucion:
        raise ErrorCLI("Resolver un problema necesita la solución", "Repite con --solucion.")
    if entrada.estado == "resuelto":
        imprimir({"esquema": ESQUEMA, "cambio": False, "id": entrada.id, "ruta": entrada.ruta,
                 "version": entrada.version})
        return 0
    try:
        actual = alm.poner_estado(entrada.id, entrada.version, "resuelto",
                                  campos={"solucion": solucion, "resuelto_el": almacen._hoy()})
    except almacen.EntradaCambiada as error:
        raise ErrorCLI(
            f"«{error.entrada_id}» cambió justo al resolverla",
            f"`cotejo leer {error.entrada_id}` y reintenta. No se escribió nada.",
            reintentable=True, codigo=4) from error
    imprimir({"esquema": ESQUEMA, "cambio": True, "id": actual.id, "ruta": actual.ruta,
             "version": actual.version})
    return 0


# --- los verbos, colgados del analizador de Cotejo ---------------------------------------------


def anadir(sub):
    buscar = nucleo(sub.add_parser(
        "buscar", help="Una línea por entrada (id, tipo, título, resumen); barato"))
    buscar.add_argument("--repo", metavar="CARPETA",
                        help="El repo donde buscar. Por defecto, su raíz git desde aquí")
    buscar.add_argument("--tipo", choices=sorted(almacen.TIPOS))
    buscar.add_argument("--temas", help="Coma-separados; las que tengan todos")
    buscar.add_argument("--estado", help="Estado de la entrada")
    buscar.add_argument("--desde", metavar="AAAA-MM-DD",
                        help="Desde esa fecha (por `fecha` o `actualizado`)")
    buscar.add_argument("--texto", help="En título, resumen y cuerpo; sin mayúsculas ni acentos")
    buscar.add_argument("--limite", type=int, default=50,
                        help="Máximo de entradas")
    buscar.set_defaults(funcion=cmd_buscar)

    leer = nucleo(sub.add_parser(
        "leer", help="La entrada completa, con cuerpo y version; de un recurso, la ruta"))
    leer.add_argument("id", help="Id de la entrada, o «proyecto»")
    leer.add_argument("--repo", metavar="CARPETA",
                      help="El repo donde leer. Por defecto, su raíz git desde aquí")
    leer.set_defaults(funcion=cmd_leer)

    contexto = nucleo(sub.add_parser(
        "contexto", help="Objetivo, tareas por estado, decisiones vigentes, problemas "
                         "abiertos, temas y arquitectura; <1k tokens"))
    contexto.add_argument("--repo", metavar="CARPETA",
                          help="El repo del que enterarse. Por defecto, su raíz git desde aquí")
    contexto.add_argument("--tope", type=int, default=TOPE_VIGENTES,
                          help="Máximo de decisiones y problemas (los más recientes)")
    contexto.set_defaults(funcion=cmd_contexto)

    proponer = sub.add_parser(
        "proponer", help="Proponer algo nuevo al almacén; hoy solo decisiones")
    acciones_proponer = proponer.add_subparsers(dest="accion", required=True)

    decision = acciones_proponer.add_parser(
        "decision", help="Una decisión nueva en propuesta, con el agente como autor")
    decision.add_argument("--titulo", required=True)
    decision.add_argument("--temas", help="Coma-separados")
    decision.add_argument("--texto", required=True, help="El razonamiento de la decisión")
    decision.add_argument("--reemplaza", metavar="DEC-ID",
                          help="La decisión que esta deja reemplazada")
    decision.add_argument("--autor", default="agente",
                          help="Quién la propone (por defecto, «agente»)")
    decision.add_argument("--repo", metavar="CARPETA",
                          help="El repo donde escribir. Por defecto, su raíz git desde aquí")
    decision.set_defaults(funcion=cmd_proponer_decision)

    anotar = nucleo(sub.add_parser(
        "anotar", help="Una entrada nueva: problema, aprendizaje, referencia o arquitectura"))
    acciones_anotar = anotar.add_subparsers(dest="accion", required=True)
    for tipo in ("problema", "aprendizaje", "referencia", "arquitectura"):
        carpeta = almacen.TIPOS[tipo].carpeta
        accion = acciones_anotar.add_parser(
            tipo, help=f"Una entrada nueva en {almacen.CARPETA}/{carpeta}/")
        accion.add_argument("--titulo", required=True)
        accion.add_argument("--temas", help="Coma-separados")
        accion.add_argument("--texto", required=tipo != "arquitectura")
        if tipo == "arquitectura":
            accion.add_argument(
                "--pieza", action="append", metavar="CAPA|NOMBRE|FRASE|TECNOLOGIA|TAREAS",
                help="capa|nombre|frase|tecnología|tareas")
        accion.add_argument("--repo", metavar="CARPETA",
                            help="El repo donde escribir. Por defecto, su raíz git desde aquí")
        accion.set_defaults(funcion=cmd_anotar, tipo=tipo)

    bitacora = nucleo(sub.add_parser(
        "bitacora", help="Añade al final de la bitácora de hoy; nunca reescribe"))
    bitacora.add_argument("texto")
    bitacora.add_argument("--repo", metavar="CARPETA",
                          help="El repo donde escribir. Por defecto, su raíz git desde aquí")
    bitacora.set_defaults(funcion=cmd_bitacora)

    editar = sub.add_parser(
        "editar", help="Cambia el texto de arquitectura, referencia, recurso o proyecto.md; "
                       "las decisiones no se editan")
    editar.add_argument("id", help="El id de la entrada a editar (o «proyecto»)")
    editar.add_argument("--version", required=True, metavar="HASH",
                        help="La version que viste al leerla con `leer`; si ya cambió, se "
                             "niega y dice cómo reintentar")
    editar.add_argument("--texto", required=True, help="El texto nuevo del cuerpo, bajo el título")
    editar.add_argument("--repo", metavar="CARPETA",
                        help="El repo donde escribir. Por defecto, su raíz git desde aquí")
    editar.set_defaults(funcion=cmd_editar)

    resolver = sub.add_parser(
        "resolver", help="Problema abierto -> resuelto, con la solución que lo cerró")
    resolver.add_argument("id", help="El id del problema (pro-xxxx)")
    resolver.add_argument("--solucion", required=True, help="Qué lo resolvió")
    resolver.add_argument("--repo", metavar="CARPETA",
                          help="El repo donde escribir. Por defecto, su raíz git desde aquí")
    resolver.set_defaults(funcion=cmd_resolver)
