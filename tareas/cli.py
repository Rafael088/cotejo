"""La cara de Cotejo para los agentes: enterarse barato y escribir por verbos.

No importa GTK, igual que `estado.py`: un agente que pregunta qué tareas hay no debe pagar
el arranque de la interfaz. Todo entra y sale en JSON por la salida estándar.

Por qué existe este archivo y no basta con que el agente edite el Markdown: la fuente ya
verifica que la tarea siga igual antes de escribir y reemplaza el archivo de forma atómica.
Escribir por fuera se salta eso, y la forma de fallar es pisar trabajo ajeno en silencio.

Nada de aquí sabe qué es una nota ni un tag: habla con la fuente (`tareas/fuente.py`), así que
los mismos verbos sirven para un vault de Obsidian o para lo que venga después.

Lo que aquí **no** hay, a propósito, es un verbo para finalizar una tarea. Si el agente puede
marcar hecha la suya, «hecha» deja de significar «alguien la revisó». Esa transición es de una
persona y se hace en CotejoBoard.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import date

from . import (__version__, ahorro, bitacora, capturas, configuracion, estado, evidencia,
               fuente as f, modelo, revision, version as versiones, worktrees)

# Versión del formato de salida. Se agregan claves; no se renombran ni se quitan.
ESQUEMA = 1

AGENTE_RE = re.compile(r"^[\w.-]+$")


class ErrorCLI(Exception):
    """Un error que el agente puede leer: qué pasó, qué hacer y si vale reintentar.

    `avisos` es para lo que salió mal *además* del error y no cabe en él: hoy, que no se
    pudiera anotar el rechazo de un despacho. Un fallo así no cambia lo que hay que hacer,
    pero tampoco puede desaparecer en silencio.
    """

    def __init__(self, mensaje, salida, reintentable=False, codigo=3, avisos=()):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.salida = salida
        self.reintentable = reintentable
        self.codigo = codigo
        self.avisos = list(avisos)


def imprimir(datos):
    """Saca la respuesta y devuelve cuánto ocupó, que es lo que de verdad le cuesta al agente."""
    texto = json.dumps(datos, ensure_ascii=False)
    print(texto)
    return len(texto)


def como_json(tarea, proyecto, ultima=None):
    """La tarea como la ve un agente. `ultima` es su anotación más reciente con texto libre.

    Va incluida porque sin ella la devolución es de un solo sentido: un agente que recoge una
    tarea que le rechazaron no tiene forma de saber qué estuvo mal, y la vuelve a entregar
    igual. La evidencia viaja por la misma razón, para no releer la bitácora a mano.
    """
    datos = {
        "id": tarea.id,
        "texto": tarea.texto,
        "nombre": tarea.nombre_corto,
        "version": tarea.version_del_texto,
        "proyecto": proyecto.nombre,
        "estado": tarea.columna,
        "agente": tarea.agente,
        "dificultad": tarea.dificultad,
        # La clave se llama "nota" desde el esquema 1 y así se queda, aunque lo que trae sea
        # «dónde vive la tarea en su fuente»: las claves se agregan, no se renombran.
        "nota": tarea.donde,
    }
    for clave in bitacora.CON_TEXTO:
        if ultima and ultima.get(clave):
            datos[clave] = ultima[clave]
    return datos


def cargar():
    """La fuente y sus proyectos, más lo que no se pudo leer.

    Los avisos viajan con la lista porque son parte de la respuesta: si una nota no se pudo
    abrir, sus tareas faltan, y un agente que no lo sepa concluye que no hay nada que hacer
    ahí.
    """
    try:
        fuente = f.abrir()
    except ValueError as error:
        raise ErrorCLI(str(error), "`fuentes` lista las que hay; `doctor` dice qué falla.") from error
    if fuente.problema:
        raise ErrorCLI("No hay de dónde leer las tareas", f.problema_con_pista(fuente))
    avisos = []
    proyectos = fuente.escanear(incluir_hechas=True, avisos=avisos)
    # Otra vez después de leer: una fuente externa solo se entera de que su app no contesta
    # al intentarlo, y cero proyectos por un fallo no es lo mismo que cero proyectos.
    if fuente.problema:
        raise ErrorCLI("No hay de dónde leer las tareas", fuente.problema,
                       reintentable=getattr(fuente, "reintentable", False))
    return fuente, proyectos, avisos


def tomar_tarea(fuente, proyectos, tarea_id):
    try:
        proyecto, tarea = modelo.buscar(proyectos, fuente.normalizar_id(tarea_id))
    except modelo.IdAmbiguo as error:
        raise ErrorCLI(
            f"El id {tarea_id} responde a más de una tarea ({error})",
            "Vuelve a pedir `tareas --proyecto <uno solo>` y usa el id de esa lista. "
            "No se escribió nada.") from error
    if tarea is None:
        raise ErrorCLI(
            f"No hay ninguna tarea con id {tarea_id}",
            "Vuelve a pedir `tareas`: los identificadores cambian si alguien editó la nota "
            "por encima de la tarea.",
            reintentable=True)
    return proyecto, tarea


def escribir(funcion, *args, **opciones):
    """Traduce los fallos de escritura a errores que dicen qué hacer."""
    try:
        return funcion(*args, **opciones)
    except modelo.TareaCambiada as error:
        raise ErrorCLI(
            f"La tarea cambió en {error} desde que la leíste",
            "Vuelve a pedir `tareas` y repite la operación con el id nuevo. No se escribió nada.",
            reintentable=True, codigo=4) from error
    except modelo.FuenteNoResponde as error:
        raise ErrorCLI(f"No pude escribir la tarea: {error}",
                       (error.salida + " " if error.salida else "")
                       + "`doctor` dice qué falla. No se escribió nada.",
                       reintentable=error.reintentable) from error
    except OSError as error:
        raise ErrorCLI(f"No pude escribir la tarea: {error}",
                       "Revisa permisos y espacio en disco. No se escribió nada.") from error


# --- verbos -----------------------------------------------------------------


def cmd_tareas(args):
    """El camino barato para saber *cuáles*, que es lo que `--estado` no contesta."""
    fuente, proyectos, avisos = cargar()
    ultimas = bitacora.ultimas()
    salida = []
    filtrados = []
    for proyecto in proyectos:
        if args.proyecto and args.proyecto.lower() not in proyecto.nombre.lower():
            continue
        filtrados.append(proyecto)
        # Por defecto excluye las hechas; --estado hecha o --todas las incluye
        tareas_a_listar = list(proyecto.tareas) + (list(proyecto.hechas) if (args.todas or args.estado == "hecha") else [])
        for tarea in tareas_a_listar:
            if args.estado and tarea.columna != args.estado:
                continue
            if args.agente is not None and tarea.agente != args.agente:
                continue
            if args.version and not versiones.pertenece(tarea.version_del_texto, args.version):
                continue
            salida.append(como_json(tarea, proyecto, ultimas.get(tarea.id)))
    total = len(salida)
    if args.limite:
        salida = salida[:args.limite]
    datos = {"esquema": ESQUEMA, "total": total, "tareas": salida}
    if avisos:
        datos["avisos"] = avisos
    # Las dos mitades del medidor, las dos medidas: lo que se lleva el agente y lo que pesaba
    # lo que hubo que leer para contestarle. Se apunta solo aquí y no en `estado`, porque a
    # `estado` lo llama el widget de la barra cada pocos minutos sin que haya ningún agente
    # detrás: sumarlo convertiría el ahorro en una medida de cuánto lleva encendida la barra.
    #
    # `escanear` lee el vault entero aunque se pida `--proyecto` —tiene que, para saber cuáles
    # hay—, pero la mitad cara no es «cuánto se escaneó», es «cuánto habría costado leer para
    # contestar esto». Sin filtro las dos cosas coinciden y se sigue pidiendo el total; con
    # `--proyecto` se le pasan a `leido()` los mismos proyectos que ya pasaron el filtro para
    # la respuesta, para que cuente solo esas notas y no el vault entero (tarea cotejo-mbzjoj).
    ahorro.anotar(imprimir(datos), fuente.leido(filtrados if args.proyecto else None))
    return 0


def cmd_ahorro(args):
    """Lo que costó enterarse por aquí contra lo que habría costado leer las notas.

    Se consulta, no se anuncia: un número permanente es el FOMO que la app evita, y por eso
    esto no está en la barra. El supuesto viaja dentro de la respuesta —que sin Cotejo habrías
    leído esas notas enteras— para que quien lo lea no tenga que ir a buscarlo.
    """
    datos = ahorro.resumen()
    if datos is None:
        imprimir({"esquema": ESQUEMA, "lecturas": 0,
                  "salida": "Todavía no hay ninguna lectura que contar. Pide `tareas` y vuelve."})
        return 0
    imprimir({"esquema": ESQUEMA, **{k: v for k, v in datos.items() if k != "esquema"}})
    return 0


def cmd_crear(args):
    """Anotar trabajo nuevo: la contraparte de poder leer lo que falta.

    Sin esto, un agente que encuentra algo que hay que hacer solo puede decírselo a quien le
    esté leyendo, y eso se pierde al cerrar la sesión. Crear no es finalizar: apuntar una
    tarea no afirma que esté hecha, así que no toca lo que protege la ausencia de `[x]`.

    Repetirlo es seguro, que es el contrato del resto de los verbos y el que más falta hace
    aquí: un reintento después de un fallo de red no puede dejar la nota con la misma tarea
    dos veces. Si el proyecto ya tiene una sin terminar que dice exactamente lo mismo, se
    devuelve esa con `cambio: false` en vez de escribir otra.
    """
    # Una tarea es una línea: un salto dentro del texto partiría la nota en dos cosas, y la
    # segunda ya no sería una tarea. Los espacios de más se van con él.
    texto = " ".join(args.texto.split())
    if not texto:
        raise ErrorCLI("Una tarea sin texto no dice qué hay que hacer",
                       "Repite la llamada con el texto de la tarea.")

    fuente, proyectos, _ = cargar()
    proyecto = un_proyecto(proyectos, args.proyecto)

    for tarea in proyecto.tareas:
        if tarea.texto == texto:
            imprimir({"esquema": ESQUEMA, "cambio": False, "tarea": como_json(tarea, proyecto)})
            return 0

    try:
        actual = escribir(fuente.crear, proyecto, texto, args.dificultad or "",
                          **({"version": args.version} if args.version else {}))
    except NotImplementedError as error:
        raise ErrorCLI(
            f"La fuente «{fuente.nombre}» no sabe crear tareas",
            "Anótala donde vivan sus tareas y vuelve a pedir `tareas`.") from error
    except modelo.NoSeCreaAqui as error:
        raise ErrorCLI(
            str(error),
            "Anótala en el proyecto al que pertenece. Lo que va a una carpeta suelta lo "
            "escribe una persona. No se escribió nada.") from error

    bitacora.anotar("crear", proyecto, actual, a=modelo.PENDIENTE)
    imprimir({"esquema": ESQUEMA, "cambio": True, "tarea": como_json(actual, proyecto),
              "nota_para_el_agente": "Queda en Pendiente y sin dueño. Si la vas a hacer tú, "
                                     "tómala con `tomar`."})
    return 0


def un_proyecto(proyectos, nombre):
    """El proyecto que nombra `nombre`, o un error que dice por qué no hay uno solo.

    El nombre exacto gana a los parciales: en el vault de verdad «Cotejo» es parte de «Cotejo -
    Planning para Producción», y sin esa preferencia `--proyecto Cotejo` no serviría nunca para
    escribir. Parcial y ambiguo, se niega y los nombra: escribir en el primero que salga es
    escribir en el equivocado sin que nadie se entere.
    """
    buscado = nombre.strip().lower()
    exactos = [p for p in proyectos if p.nombre.lower() == buscado]
    candidatos = exactos or [p for p in proyectos if buscado in p.nombre.lower()]
    if not candidatos:
        raise ErrorCLI(
            f"No hay ningún proyecto que se llame «{nombre}»",
            "Pide `tareas` para ver los nombres que hay. Crear el proyecto es de una persona: "
            "es una nota nueva en el segundo cerebro, no una tarea.")
    if len(candidatos) > 1:
        raise ErrorCLI(
            f"«{nombre}» responde a más de un proyecto "
            f"({', '.join(p.nombre for p in candidatos)})",
            "Repite con el nombre completo. No se escribió nada.")
    return candidatos[0]


def tomar_para(fuente, proyecto, tarea, agente):
    """Pendiente → haciéndola a nombre de `agente`. Devuelve (la tarea como quedó, si cambió).

    Está aparte del verbo porque el enrutador toma tareas por este mismo camino cuando
    despacha una a un modelo. Dos implementaciones de «tomar» discreparían justo en el caso
    que importa —la tarea que ya tiene dueño—, y la que se equivocara escribiría en el vault.
    """
    if tarea.columna == "en-curso" and tarea.agente == agente:
        return tarea, False  # ya estaba tomada por el mismo: reintentar es seguro
    if tarea.columna != modelo.PENDIENTE:
        dueno = f" (la tiene {tarea.agente})" if tarea.agente else ""
        raise ErrorCLI(
            f"La tarea no está pendiente, está en «{tarea.columna}»{dueno}",
            "Elige otra de `tareas --estado pendiente`. Si de verdad hay que reasignarla, "
            "eso lo hace una persona desde CotejoBoard.")

    actual = escribir(fuente.poner_estado, tarea, "en-curso")
    actual = escribir(fuente.poner_agente, actual, agente)
    bitacora.anotar("tomar", proyecto, actual, de=modelo.PENDIENTE, a="en-curso")
    return actual, True


def cmd_tomar(args):
    """Pendiente → haciéndola, y de paso queda asignada: tomarla es decir quién la tiene."""
    fuente, proyectos, _ = cargar()
    proyecto, tarea = tomar_tarea(fuente, proyectos, args.id)
    # Lo último que se dijo de ella, que en una tarea devuelta es el motivo del rechazo: es lo
    # que hay que leer antes de volver a hacerla, no después de volver a entregarla.
    ultima = bitacora.ultimas().get(tarea.id)
    actual, cambio = tomar_para(fuente, proyecto, tarea, args.agente)
    imprimir({"esquema": ESQUEMA, "cambio": cambio,
              "tarea": como_json(actual, proyecto, ultima)})
    return 0


def cmd_entregar(args):
    """Haciéndola → Para comprobar. La evidencia es obligatoria a propósito:
    si revisar la entrega cuesta lo mismo que haberla hecho, la columna no sirve de nada."""
    fuente, proyectos, _ = cargar()
    proyecto, tarea = tomar_tarea(fuente, proyectos, args.id)

    if tarea.columna == "por-validar":
        imprimir({"esquema": ESQUEMA, "cambio": False, "tarea": como_json(tarea, proyecto)})
        return 0
    if tarea.columna != "en-curso":
        raise ErrorCLI(
            f"No puedes entregar una tarea que está en «{tarea.columna}»",
            "Tómala primero con `tomar`, y entrégala cuando esté hecha."
            if tarea.columna == modelo.PENDIENTE else
            "Ya está finalizada; no hay nada que entregar.")

    if args.repo and not os.path.isdir(args.repo):
        raise ErrorCLI(f"«{args.repo}» no es una carpeta",
                       "Pasa en --repo la carpeta del trabajo (el worktree), o quítalo para usar "
                       "la actual. No se escribió nada.")
    # Sin --repo, el worktree de la tarea si `despachar` le creó uno (B3): es donde está su
    # rama, y entregar desde otra carpeta anotaría la rama equivocada.
    carpeta = args.repo or worktrees.carpeta_de(tarea.id)
    # La evidencia estructurada se reúne antes de escribir: las pruebas tardan, y si mientras
    # tanto alguien movió la tarea, `escribir` lo detecta y no queda una entrega a medias.
    estructurada = evidencia.reunir(carpeta, args.prueba or ())
    estructurada.update(resumen=args.resumen) if args.resumen is not None else None  # solo se agrega
    try:
        if args.captura:
            estructurada["capturas"] = capturas.guardar(tarea.id, args.captura)
        if args.captura_desde:
            estructurada["capturas_solicitadas"] = capturas.solicitudes(args.captura_desde)
    except (ValueError, OSError) as error:
        raise ErrorCLI(f"No pude guardar las capturas: {error}", "No se escribió nada.")
    actual = escribir(fuente.poner_estado, tarea, "por-validar")
    bitacora.anotar("entregar", proyecto, actual, de="en-curso", a="por-validar",
                    evidencia=args.evidencia, **estructurada)
    datos = {"esquema": ESQUEMA, "cambio": True, "tarea": como_json(actual, proyecto),
             "evidencia": args.evidencia, **estructurada,
             "nota_para_el_agente": "Queda esperando que una persona la compruebe en CotejoBoard. "
                                    "Marcar [x] no es tuyo."}
    if args.captura_desde:
        datos["nota_para_el_agente"] += (" Las capturas pedidas las sacará CotejoBoard fuera "
                                         "del sandbox; no tienes que esperarlas ni producir PNG.")
    # Una prueba en rojo no frena la entrega —puede venir roja de antes, y eso lo juzga quien
    # revisa—, pero tampoco pasa callada: queda en la bitácora con su código y se avisa aquí.
    rojas = [p["comando"] for p in estructurada.get("pruebas", ()) if p["codigo"] != 0]
    if rojas:
        datos["avisos"] = [f"La prueba «{c}» no terminó con código 0; quedó anotado así."
                           for c in rojas]
    # Las finalizadas se acumulan en la nota sin que nadie las vuelva a mirar (cotejo-r3cs5t).
    # Se avisa aquí, y no en `tareas`, porque entregar es el momento en que el agente ya acabó
    # y puede preguntar sin interrumpir nada. Preguntar, no limpiar: borrar es de la persona.
    umbral = configuracion.umbral_limpiar()
    if umbral and len(proyecto.hechas) > umbral:
        datos.setdefault("avisos", []).append(
            f"«{proyecto.nombre}» acumula {len(proyecto.hechas)} tareas finalizadas (el umbral "
            f"es {umbral}). Pregúntale a la persona si quiere limpiarlas: `cotejo limpiar "
            f"{proyecto.nombre}` enseña cuáles saldrían sin tocar nada.")
    # `proyecto.md` viejo (v1.2.3): el agente que cierra trabajo es quien se entera de que el
    # siguiente paso quedó atrás. Es una pista con la misma regla de `contexto`, nunca un freno.
    from . import conocimiento  # aquí dentro: conocimiento importa de cli.py y esto evita el ciclo
    viejas = conocimiento.pistas_de_frescura(carpeta)
    if viejas:
        datos.setdefault("avisos", []).extend(viejas)
    imprimir(datos)
    return 0


def cmd_bloquear(args):
    """Haciéndola → pendiente, sin dueño y diciendo qué lo impide.

    Es la salida honesta del agente, la contraparte de `entregar` para cuando la tarea no se
    puede terminar. Sin este verbo, un agente atascado solo tenía dos salidas y las dos son
    peores: dejarla en curso ocupando la columna sin que nadie sepa por qué, o entregarla a
    medias, que mete en «Para comprobar» algo que no hay nada que comprobar.

    El motivo es obligatorio por la misma razón que la evidencia al entregar: una tarea que
    vuelve a Pendiente sin explicación la toma el siguiente agente para estrellarse contra lo
    mismo. Y va a la bitácora, no a la línea, porque es texto libre como los otros dos.
    """
    fuente, proyectos, _ = cargar()
    proyecto, tarea = tomar_tarea(fuente, proyectos, args.id)

    if tarea.columna == modelo.PENDIENTE and not tarea.agente:
        # Ya estaba libre: reintentar es seguro. Va con su motivo, que en un reintento es el
        # que dejó la llamada que sí pasó.
        imprimir({"esquema": ESQUEMA, "cambio": False,
                  "tarea": como_json(tarea, proyecto, bitacora.ultimas().get(tarea.id))})
        return 0
    if tarea.columna != "en-curso":
        raise ErrorCLI(
            f"Solo se bloquea una tarea que estés haciendo, y esta está en «{tarea.columna}»",
            "Tómala primero con `tomar`; si al hacerla te atascas, entonces sí."
            if tarea.columna == modelo.PENDIENTE else
            "Ya la entregaste: lo que pase con ella ahora lo decide una persona en CotejoBoard.")

    # Quién la tenía se guarda antes de soltarla: la tarea queda libre, pero la bitácora tiene
    # que poder decir quién se atascó y en qué.
    quien = tarea.agente
    actual = escribir(fuente.poner_estado, tarea, modelo.PENDIENTE)
    actual = escribir(fuente.poner_agente, actual, "")
    bitacora.anotar("bloquear", proyecto, actual, de="en-curso", a=modelo.PENDIENTE,
                    agente=quien, motivo=args.motivo)
    imprimir({"esquema": ESQUEMA, "cambio": True, "tarea": como_json(actual, proyecto),
              "motivo": args.motivo,
              "nota_para_el_agente": "Vuelve a Pendiente y sin dueño, con el motivo a la vista "
                                     "en CotejoBoard. No la retomes hasta que ese motivo cambie."})
    return 0


def cmd_comprobar(args):
    """Vuelve a correr las pruebas que anotó la última entrega y dice si el resultado sigue igual.

    Esto **lee**: no toca el estado de la tarea ni la bitácora. Comprobar de un vistazo es
    justo lo que B1 hizo posible al guardar el `argv` y la carpeta de cada prueba en vez de
    solo el texto de un «pasan las pruebas»; esto es lo que vuelve a correrlas con eso, sin
    pasar por ningún shell —ni el del agente que entregó ni el de quien comprueba—, y con el
    mismo tiempo límite que al entregarlas. Aprobar la tarea sigue siendo de una persona, en
    CotejoBoard.
    """
    fuente, proyectos, _ = cargar()
    proyecto, tarea = tomar_tarea(fuente, proyectos, args.id)
    entrega = bitacora.ultima_entrega(tarea.id)
    # Si la tarea tiene su worktree (B3), las pruebas se vuelven a correr ahí, que es donde
    # está su rama, aunque la entrega se hiciera desde otra carpeta. Es la misma función que
    # usa el botón «Volver a comprobar» del board (B4).
    propio = worktrees.carpeta_de(tarea.id) if entrega and entrega.get("pruebas") else None
    resultado = revision.recomprobar(entrega, propio)
    if resultado["sigue_igual"] is None:
        imprimir({"esquema": ESQUEMA, "tarea": como_json(tarea, proyecto), **resultado})
        return 0
    datos = {"esquema": ESQUEMA,
             "tarea": como_json(tarea, proyecto, bitacora.ultimas().get(tarea.id)),
             **resultado}
    if propio:
        datos["worktree"] = propio
    imprimir(datos)
    return 0


# Cuántos días tiene que llevar finalizada una tarea para que `limpiar` la proponga. Las de
# esta semana son las que la persona todavía mira en la columna Finalizada.
DIAS_LIMPIAR = 7


def _hoy():
    """Hoy, en local. Aparte para que las pruebas lo fijen sin tocar el reloj."""
    return date.fromisoformat(time.strftime("%Y-%m-%d"))


def _dias_desde(fecha, hoy):
    """Días desde `fecha` ("AAAA-MM-DD") hasta `hoy`, o None si no hay fecha o no se entiende."""
    try:
        return (hoy - date.fromisoformat(fecha)).days if fecha else None
    except (TypeError, ValueError):
        return None


def cmd_limpiar(args):
    """Borrar de la fuente las finalizadas antiguas sin perder su rastro (v1.2.2, cotejo-r3cs5t).

    Solo toca tareas que una persona **ya** dio por hechas: no mueve ninguna de columna, así
    que no es un verbo para finalizar. Salen las que llevan más de `DIAS_LIMPIAR` días hechas
    y las que no tienen fecha (nadie sabe desde cuándo: no son de esta semana).

    Es un ensayo por defecto: lista las que saldrían y cuáles tienen ya su `comprobar` en la
    bitácora —la anotación que deja el board al aprobar—. Con `--aplicar`, a las que no lo
    tienen se les escribe **antes** una anotación `limpiar` con su texto, su fecha y su nota,
    para que el id siga resolviendo en la bitácora; si esa anotación no se puede escribir, la
    tarea no se borra. Luego se borra la línea por la fuente, verificando que no cambió.
    """
    fuente, proyectos, _ = cargar()
    proyecto = un_proyecto(proyectos, args.proyecto)
    hoy = _hoy()
    comprobadas = bitacora.ids_con("comprobar")

    candidatas = []
    for tarea in proyecto.hechas:
        fecha = fuente.fecha_cierre(tarea)
        dias = _dias_desde(fecha, hoy)
        if dias is not None and dias <= DIAS_LIMPIAR:
            continue
        candidatas.append({"tarea": tarea, "fila": {
            "id": tarea.id, "texto": tarea.texto, "fecha": fecha, "nota": tarea.donde,
            "comprobada": modelo.id_actual(tarea.id) in comprobadas}})

    filas = [c["fila"] for c in candidatas]
    resumen = {"esquema": ESQUEMA, "proyecto": proyecto.nombre, "dias": DIAS_LIMPIAR,
               "finalizadas": len(proyecto.hechas), "total": len(filas),
               "sin_comprobar": sum(1 for fila in filas if not fila["comprobada"])}

    if not args.aplicar:
        imprimir({**resumen, "ensayo": True, "tareas": filas,
                  "salida": "Es un ensayo: no se tocó nada. Antes de `--aplicar`, guarda en "
                            "`.cotejo/` lo que valga la pena de estas tareas (`proponer "
                            "decision`, `anotar`) y pídele confirmación a la persona."
                            if filas else "No hay finalizadas antiguas que limpiar."})
        return 0

    if filas and type(fuente).quitar is f.Fuente.quitar:
        raise ErrorCLI(f"La fuente «{fuente.nombre}» no sabe borrar tareas",
                       "Las finalizadas se quedan donde están; si estorban, archívalas en su "
                       "propia app. No se escribió nada.")

    borradas, saltadas = [], []
    # De la última a la primera: una tarea sin marca se encuentra por su número de línea, y
    # borrar antes una de más arriba se lo movería.
    for candidata in reversed(candidatas):
        tarea, fila = candidata["tarea"], dict(candidata["fila"])
        if not fila["comprobada"]:
            if not bitacora.anotar("limpiar", proyecto, tarea, fecha=fila["fecha"]):
                saltadas.append({**fila, "motivo": "No pude escribir su anotación en la "
                                                   "bitácora, así que no se borró."})
                continue
            fila["anotada"] = True
        try:
            fuente.quitar(tarea)
        except modelo.TareaCambiada:
            saltadas.append({**fila, "motivo": "Cambió desde que se leyó: no se borró."})
            continue
        except (modelo.FuenteNoResponde, OSError) as error:
            saltadas.append({**fila, "motivo": f"No se pudo borrar: {error}"})
            continue
        borradas.append(fila)
    borradas.reverse()
    saltadas.reverse()

    datos = {**resumen, "ensayo": False, "cambio": bool(borradas), "borradas": borradas,
             "nota_para_el_agente": "Las borradas siguen en la bitácora con su id: "
                                    "`comprobar` si una persona las aprobó en el board, "
                                    "`limpiar` si no."}
    if saltadas:
        datos["saltadas"] = saltadas
        datos["avisos"] = [f"{len(saltadas)} no se borraron (cada una dice por qué). Vuelve a "
                           "correr `limpiar` para ver cómo quedan."]
    imprimir(datos)
    return 0


# Dónde tiene que estar una tarea para que su worktree sobre: aprobada, o devuelta a Pendiente
# (descartada o soltada: quien la retome tendrá uno nuevo sobre la misma rama, con sus commits).
SOBRA_EN = (modelo.HECHA, modelo.PENDIENTE)


def cmd_worktrees(args):
    """Los worktrees de despacho: dónde quedó cada tarea, y con --limpiar, retirar los que sobran.

    El board retira el de una tarea al aprobarla o devolverla a Pendiente; esto es para lo que
    se movió por otro lado (marcada en Obsidian a mano, una tarea que ya no existe). No toca el
    estado de ninguna tarea, ni borra ramas, ni nada sin commitear: `retirar` se niega.
    """
    registrados = worktrees.todos()
    estados = {}
    if registrados:
        try:
            _, proyectos, _ = cargar()
            for uno in proyectos:
                for tarea in list(uno.tareas) + list(uno.hechas):
                    estados[modelo.id_actual(tarea.id)] = tarea.columna
        except ErrorCLI:
            estados = None  # sin fuente no se sabe cuáles sobran: no se retira ninguno
    filas = []
    for datos in registrados:
        identificador = modelo.id_actual(datos.get("tarea", ""))
        estado_tarea = None if estados is None else estados.get(identificador, "no-existe")
        fila = {k: datos.get(k) for k in ("tarea", "ruta", "rama", "repo", "existe")}
        fila["estado"] = estado_tarea
        fila["sobra"] = estado_tarea in SOBRA_EN + ("no-existe",)
        if args.limpiar and fila["sobra"]:
            hecho = worktrees.retirar(datos.get("tarea", ""))
            fila["retirado"] = hecho.get("retirado", False)
            if hecho.get("motivo"):
                fila["motivo"] = hecho["motivo"]
        filas.append(fila)
    salida = {"esquema": ESQUEMA, "registro": str(worktrees.REGISTRO), "worktrees": filas}
    if estados is None:
        salida["avisos"] = ["No pude leer las tareas: no sé cuáles sobran y no retiré ninguno."]
    elif not args.limpiar and any(f["sobra"] for f in filas):
        salida["salida"] = ("Los que tienen «sobra» son de tareas aprobadas, devueltas a "
                            "Pendiente o que ya no existen: `worktrees --limpiar` los retira "
                            "(la rama se queda).")
    imprimir(salida)
    return 0


def cmd_asignar(args):
    fuente, proyectos, _ = cargar()
    proyecto, tarea = tomar_tarea(fuente, proyectos, args.id)
    if tarea.agente == args.agente:
        imprimir({"esquema": ESQUEMA, "cambio": False, "tarea": como_json(tarea, proyecto)})
        return 0
    actual = escribir(fuente.poner_agente, tarea, args.agente)
    bitacora.anotar("asignar", proyecto, actual, de=tarea.agente, a=args.agente)
    imprimir({"esquema": ESQUEMA, "cambio": True, "tarea": como_json(actual, proyecto)})
    return 0


# --- entrada ----------------------------------------------------------------


def agente(texto):
    """Un nombre de agente. El vacío no vale: tomar una tarea es decir quién la tiene."""
    if not AGENTE_RE.match(texto):
        raise argparse.ArgumentTypeError(
            f"«{texto}» no sirve como nombre de agente: letras, números, punto o guion. "
            f"Los que usa el board son {', '.join(modelo.AGENTES)}.")
    return texto


def agente_o_ninguno(texto):
    """Como `agente`, pero el vacío sí vale: es como se le quita el dueño a una tarea.

    Va aparte porque argparse pasa también el valor por defecto por el `type`, así que un
    validador que rechace el vacío rompe justo el caso de `asignar <id>` sin nombre.
    """
    return agente(texto) if texto else ""


def nucleo(verbo):
    """Marca un verbo como del núcleo: lo que `cotejo mcp` sirve por defecto (`--perfil nucleo`).

    La marca va en el verbo, aquí donde se declara, y no en una lista aparte: `mcp.py` solo
    filtra por ella. Si el verbo tiene acciones (`anotar problema`…), todas son del núcleo.
    """
    verbo.nucleo = True
    return verbo


def analizador():
    partes = argparse.ArgumentParser(
        prog="cotejo",
        description="Cotejo para agentes: leer las tareas del segundo cerebro y moverlas por sus estados. "
                    "Finalizar una tarea no está aquí: esa transición es de una persona.")
    partes.add_argument("--version", action="version", version=f"cotejo {__version__}")
    sub = partes.add_subparsers(dest="comando", required=True)

    sub.add_parser("estado", help="Resumen con los conteos (lo que lee el widget de la barra)")

    listar = nucleo(sub.add_parser(
        "tareas", help="Las tareas, filtrables; el camino barato"))
    listar.add_argument("--proyecto", help="Nombre o parte")
    listar.add_argument("--estado", choices=[c for c, _ in modelo.COLUMNAS], help="Columna")
    listar.add_argument("--agente", type=str, help='Quién la tiene ("" = sin dueño)')
    listar.add_argument("--version", type=versiones.argumento,
                        help="X.Y.Z o X.Y")
    listar.add_argument("--limite", type=int, help="Máximo a devolver")
    listar.add_argument("--todas", action="store_true", help="Incluir las hechas")
    listar.set_defaults(funcion=cmd_tareas)

    medidor = sub.add_parser(
        "ahorro", help="Cuánto costó enterarse por aquí contra leer las notas enteras")
    medidor.set_defaults(funcion=cmd_ahorro)

    crear = nucleo(sub.add_parser(
        "crear", help="Anotar una tarea nueva, pendiente y sin dueño"))
    crear.add_argument("texto", help="Qué hay que hacer")
    crear.add_argument("--proyecto", required=True, help="Nombre o parte")
    crear.add_argument("--dificultad", choices=("facil", "medio", "dificil"),
                       help="La del Enrutador, si se sabe")
    # Sin `help`: por MCP cada descripción se paga en cada sesión, y el nombre y el error de
    # una versión mal escrita ya lo dicen (`version.argumento`).
    crear.add_argument("--version", type=versiones.argumento)
    crear.set_defaults(funcion=cmd_crear)

    tomar = nucleo(sub.add_parser(
        "tomar", help="Pendiente → haciéndola, a nombre de quien la toma"))
    tomar.add_argument("id")
    tomar.add_argument("--agente", type=agente, required=True)
    tomar.set_defaults(funcion=cmd_tomar)

    entregar = nucleo(sub.add_parser(
        "entregar", help="Haciéndola → Para comprobar, con evidencia"))
    entregar.add_argument("id")
    entregar.add_argument("--evidencia", required=True,
                          help="Archivos, pruebas, commit")
    entregar.add_argument("--resumen", type=evidencia.resumen_para_humanos, metavar="TEXTO",
                          help="Qué cambió y cómo probarlo")
    entregar.add_argument("--prueba", action="append", type=evidencia.prueba, metavar="COMANDO",
                          help="Comando de prueba, sin shell; repetible")
    entregar.add_argument("--captura", action="append", type=capturas.captura, help="PNG; repetible")
    entregar.add_argument("--captura-desde", action="append", type=capturas.destino,
                          metavar="ARCHIVO|URL",
                          help="El board saca móvil y escritorio fuera del sandbox; repetible")
    entregar.add_argument("--repo", metavar="CARPETA",
                          help="Dónde corren las pruebas")
    entregar.set_defaults(funcion=cmd_entregar)

    bloquear = nucleo(sub.add_parser(
        "bloquear", help="Haciéndola → pendiente, sin dueño y con el motivo"))
    bloquear.add_argument("id")
    bloquear.add_argument("--motivo", required=True,
                          help="Qué te lo impide y qué haría falta")
    bloquear.set_defaults(funcion=cmd_bloquear)

    comprobar = sub.add_parser(
        "comprobar", help="Vuelve a correr las pruebas de la última entrega, sin tocar el estado")
    comprobar.add_argument("id")
    comprobar.set_defaults(funcion=cmd_comprobar)

    lista_wt = sub.add_parser(
        "worktrees", help="Los worktrees de despacho y su tarea; --limpiar retira los que sobran")
    lista_wt.add_argument("--limpiar", action="store_true",
                          help="Retira los de tareas aprobadas, en Pendiente o que ya no existen "
                               "(sin borrar la rama ni nada sin commitear)")
    lista_wt.set_defaults(funcion=cmd_worktrees)

    limpiar = sub.add_parser(
        "limpiar", help="Borra las finalizadas antiguas de un proyecto dejando su rastro en la "
                        "bitácora. Ensayo por defecto")
    limpiar.add_argument("proyecto", help="Nombre del proyecto (o parte, si no es ambiguo)")
    limpiar.add_argument("--aplicar", action="store_true",
                         help="Borrarlas de verdad, después de que la persona lo confirme")
    limpiar.set_defaults(funcion=cmd_limpiar)

    asignar = sub.add_parser("asignar", help="Cambiar quién tiene la tarea")
    asignar.add_argument("id")
    asignar.add_argument("agente", type=agente_o_ninguno, nargs="?", default="",
                         help="Sin nombre, la deja sin dueño")
    asignar.set_defaults(funcion=cmd_asignar)

    # Y los del enrutador: quién atiende cada tarea. El import va aquí dentro y no arriba
    # porque el enrutador importa este módulo para leer y escribir tareas; arriba sería un
    # ciclo. Aquí no lo es: cuando alguien llama a `analizador()`, este módulo ya está entero.
    from enrutador import verbos as verbos_enrutador
    verbos_enrutador.anadir(sub)
    # Y los de la instalación: de qué fuente se lee y si funciona. Aquí dentro por lo mismo:
    # `conexion` importa este módulo.
    from . import conexion
    conexion.anadir(sub)
    # Y los de los temas del board: se crean y se comprueban aquí, en la ventana solo se eligen.
    from . import temas
    temas.anadir(sub)
    # Y los del almacén `.cotejo/` (v1.2): `buscar`, `leer`, `contexto`, `proponer`, `anotar`,
    # `bitacora`, `editar` y `resolver`.
    from . import conocimiento
    conocimiento.anadir(sub)
    from . import release, version_verbo; version_verbo.anadir(sub); release.anadir(sub)
    # Y la puerta MCP: los mismos verbos, como tools. El catálogo lo saca de este analizador.
    from . import mcp
    mcp.anadir(sub)
    return partes


# Lo que el agente puede pedir y no es suyo. No son verbos —el analizador no los conoce, y
# `test_no_hay_ningun_verbo_para_finalizar_una_tarea` vigila que siga así—: son palabras que, si
# llegan como verbo (o como tool por MCP), se contestan con un error que dice de quién es en vez
# del «invalid choice» de argparse.
_ACEPTAR = ("Aceptar es de la persona: se hace desde el board",
            "Propón con `cotejo proponer decision`; la persona la acepta en CotejoBoard")
_FINALIZAR = ("Dar una tarea por hecha es de la persona: se hace desde el board",
              "`cotejo entregar <id> --evidencia ...` y la persona la revisa en CotejoBoard")
DE_LA_PERSONA = {
    **dict.fromkeys(("aceptar", "acepta", "aprobar", "aprueba", "firmar", "ratificar",
                     "confirmar"), _ACEPTAR),
    **dict.fromkeys(("finalizar", "completar", "terminar", "cerrar", "marcar", "hecha"),
                    _FINALIZAR),
}


def de_la_persona(palabras):
    """El ErrorCLI para quien pide aceptar o finalizar con alguna de `palabras`, o None."""
    for palabra in palabras:
        motivo = DE_LA_PERSONA.get(str(palabra).strip().lower())
        if motivo:
            return ErrorCLI(*motivo)
    return None


def _imprimir_error(error):
    datos = {"esquema": ESQUEMA, "error": error.mensaje, "salida": error.salida,
             "reintentable": error.reintentable}
    if error.avisos:
        datos["avisos"] = error.avisos
    json.dump(datos, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return error.codigo


def main(argumentos=None):
    # `argumentos` es para quien llama desde dentro (`cotejo mcp`); la terminal usa sys.argv.
    argumentos = sys.argv[1:] if argumentos is None else list(argumentos)
    # `--estado` es el contrato viejo con el widget de la barra y sigue funcionando igual, pero
    # solo como primer argumento: `tareas --estado pendiente` es un filtro, no el resumen.
    if argumentos[:1] in (["--estado"], ["estado"]):
        return estado.main()

    pedido = de_la_persona(argumentos[:1])
    if pedido:
        return _imprimir_error(pedido)
    args = analizador().parse_args(argumentos)
    try:
        return args.funcion(args)
    except (ErrorCLI, configuracion.ConfigVedada) as error:
        return _imprimir_error(error)
