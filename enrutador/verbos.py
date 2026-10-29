"""Los verbos del enrutador, que son verbos de Cotejo como cualquier otro.

    modelos            el catálogo: qué niveles hay y para qué   (~150 tokens, sin tocar nada)
    decidir            quién atendería esto, y por qué           (sin tocar nada)
    plan               qué modelo recibiría cada tarea pendiente (sin tocar nada)
    despachar          tomar la tarea y mandársela               (lo único que escribe)
    evaluar            si las reglas aciertan, medido            (sin tocar nada)
    revisar            qué pasó con lo repartido                 (sin tocar nada)
    capacidad          cuántos despachos caben ahora en esta máquina (sin tocar nada)
    despachos          la bitácora en crudo                      (sin tocar nada)
    protocolo          las instrucciones para un agente, en Markdown
    maestro            hablar con el maestro de un proyecto: tareas, preguntas, repartir
    importar plan      qué tareas sacaría un plan.md, con dificultad y modelo propuestos
    importar obsidian  qué entradas de .cotejo/ saldrían de un proyecto del vault (ensayo)
                        (ensayo por defecto; escribe con `crear` solo con --aplicar)

Lo que aquí **no** hay, a propósito:

- **Ningún verbo entrega ni finaliza tareas.** Cotejo ya no tiene `finalizar` porque marcar
  hecha una tarea es de una persona; el enrutador hereda esa ausencia y le añade la suya:
  tampoco entrega. Reparte trabajo, y quien lo hizo dice qué hizo. Si el que reparte pudiera
  entregar, la evidencia pasaría a significar «esto se mandó» en vez de «esto se hizo».
- **Ninguna forma de despachar una tarea del nivel humano.** Ni con una bandera. Una tarea que
  dice «comprar el dominio» no mejora porque insistas: mandarla a un modelo gasta dinero para
  producir una entrega falsa. Se cambia la asignación con `asignar`, o se discute la regla,
  que para eso la decisión dice cuál fue.
"""

import json
import os
import socket
import sys
import time
from pathlib import Path

from tareas import bitacora as bitacora_cotejo, worktrees
from tareas.cli import (ESQUEMA, ErrorCLI, imprimir as imprimir_json, cargar as cargar_cotejo,
                        un_proyecto, escribir as escribir_cotejo)
from tareas.cli import como_json as como_json_cotejo
from tareas.modelo import NoSeCreaAqui, PENDIENTE, id_actual
from . import (apertura, bitacora, capacidad, clientes, config as cfg, decision,
               despacho, encargo as enc,
               importar as imp, cotejo as f, motor, niveles, procesos, reglas)

# Códigos de salida, para que un script pueda distinguir sin leer el JSON. Los dos primeros son
# los de Cotejo y significan lo mismo; los dos últimos son de aquí.
OK, ERROR, CAMBIO, HUMANO, FALTA_MODELO = 0, 3, 4, 5, 6

# De qué escalones de la decisión se fía uno para gastar sin preguntar. Los dos son una persona
# diciéndolo: uno en la línea de comandos, el otro escrito en la nota. Lo demás es una
# propuesta de las reglas, y una propuesta no autoriza a nadie a ponerse a trabajar.
LO_DIJO_UNA_PERSONA = ("override", "asignacion")


def imprimir(datos, avisos=()):
    imprimir_json({**datos, "avisos": list(avisos)} if avisos else datos)


def preparar():
    """La config, las tareas y las reglas: lo que casi todos los verbos necesitan."""
    try:
        config = cfg.cargar()
    except cfg.ConfigInvalida as error:
        raise ErrorCLI(str(error),
                       "Arregla el JSON o quita la clave «enrutador»; `config` dice qué "
                       "archivo es.") from error
    humano, nivel = reglas.cargar(config.get("reglas_extra"), config.get("reglas_apagadas"))
    propios = niveles.personalizados(config.get("modelos"))
    return config, f.Cotejo(), humano, nivel, propios


def avisos_de_agentes():
    """El aviso de «ningún agente instalado» como lista, para `imprimir`. Vacía si hay alguno."""
    aviso = clientes.aviso_sin_agentes()
    return [aviso] if aviso else []


def anotar_despacho(tarea, elegida, **extra):
    """Deja constancia de una decisión sobre una tarea. Devuelve el aviso si no pudo."""
    return bitacora.anotar(
        tarea=tarea.get("id"), texto=tarea.get("texto"), proyecto=tarea.get("proyecto"),
        nivel=elegida.nivel.clave, modelo=elegida.nivel.modelo,
        modelo_id=elegida.nivel.modelo_id, por=elegida.por, regla=elegida.regla, **extra)


def rechazar(tarea, elegida, rechazo, mensaje, salida, codigo):
    """Anota por qué **no** se repartió, y entonces sí levanta el error.

    Un rechazo es una decisión del enrutador tanto como un despacho. Y es la mitad que
    contesta la pregunta que justifica todo esto: cuántas veces el veto evitó una entrega
    falsa. Mientras solo se anotara lo que llegaba hasta el final, ese número no se podía
    contar ni a posteriori, porque la negativa no dejaba rastro en ninguna parte: la tarea
    se quedaba como estaba y el JSON del error se lo llevaba la terminal.
    """
    aviso = anotar_despacho(tarea, elegida, motor="", tomada=False, ok=False, codigo=codigo,
                            rechazo=rechazo)
    raise ErrorCLI(mensaje, salida, codigo=codigo, avisos=[aviso] if aviso else ())


# --- verbos -----------------------------------------------------------------


def cmd_modelos(args):
    """El catálogo. Es lo primero que debería leer un agente que llega nuevo."""
    try:
        config = cfg.cargar()
        if args.accion == "agregar":
            definicion = {
                "clave": args.clave,
                "nombre": args.nombre or args.clave,
                "modelo_id": args.modelo_id,
                "cliente": args.cliente,
                "nivel": args.nivel,
                "entrada_mtok": args.entrada_mtok,
                "salida_mtok": args.salida_mtok,
                **({"argumentos": args.argumento} if args.argumento else {}),
            }
            guardado, reemplazado = cfg.registrar_modelo(definicion)
            imprimir({"esquema": ESQUEMA, "cambio": True,
                      "operacion": "actualizar" if reemplazado else "agregar",
                      "modelo": guardado})
            return OK
        if args.accion == "vivos":
            from . import modelos_vivos
            imprimir({"esquema": ESQUEMA, "agentes": modelos_vivos.resumen(
                          refrescar=args.refrescar, preguntar_cli=not args.sin_preguntar),
                      "nota": "Con sesión = instalado y con credenciales en disco. Los modelos "
                              "salen del propio CLI (opencode models, codex debug models) o de "
                              "sus alias (Claude, Gemini); se registran con `modelos agregar`."})
            return OK
        if args.accion == "quitar":
            cambio = cfg.quitar_modelo(args.clave)
            imprimir({"esquema": ESQUEMA, "cambio": cambio, "operacion": "quitar",
                      "clave": args.clave})
            return OK
    except cfg.ConfigInvalida as error:
        raise ErrorCLI(str(error), "Revisa la configuración de Cotejo y repite la operación.") from error

    imprimir({"esquema": ESQUEMA, "niveles": niveles.catalogo(config.get("modelos")),
              "defecto": niveles.DEFECTO.clave,
              "nota": "Los modelos personalizados se registran en la configuración de Cotejo; "
                      "su cliente de IA es quien decide cómo ejecutarlos."},
             avisos_de_agentes())
    return OK


def cmd_decidir(args):
    """Quién atendería esto. No escribe nada, así que preguntar es gratis."""
    config, cotejo, humano, nivel, propios = preparar()
    if args.tarea:
        tarea = cotejo.tarea(args.tarea)
    else:
        if not args.texto:
            raise ErrorCLI("No me diste nada que decidir",
                           'Pásame el texto (`decidir "arreglar el parseo"`) o una tarea '
                           "(`decidir --tarea cotejo-a1b2`).")
        tarea = {"texto": " ".join(args.texto), "agente": args.agente or "",
                 "dificultad": args.dificultad or ""}
    try:
        elegida = decision.de_tarea(tarea, override=args.modelo, reglas_humano=humano,
                                    reglas_nivel=nivel, niveles_extra=propios,
                                    alias_persona=config.get("alias_persona"),
                                    cliente=cotejo.agente_del_proyecto(tarea.get("proyecto"),
                                                                       config))
    except ValueError as error:
        raise ErrorCLI(str(error),
                       f"Los nombres válidos: "
                       f"{', '.join(n['modelo'] for n in niveles.catalogo(propios))}.") from error
    salida = {"esquema": ESQUEMA, "decision": elegida.como_json(),
              "texto": tarea.get("texto", "")}
    if tarea.get("id"):
        salida["tarea"] = {k: tarea.get(k) for k in ("id", "proyecto", "estado", "agente",
                                                     "dificultad") if tarea.get(k)}
    imprimir(salida, list(cotejo.avisos) + (avisos_de_agentes() if elegida.despachable else []))
    return OK


def cmd_plan(args):
    """Qué modelo recibiría cada tarea pendiente. El camino barato para repartir trabajo.

    Responde de una vez la pregunta que si no cuesta una llamada por tarea: qué hay para
    despachar, a quién, y cuánto de lo pendiente no es para ningún modelo.
    """
    config, cotejo, humano, nivel, propios = preparar()
    tareas = cotejo.tareas(args.proyecto, args.estado or "pendiente")
    por_modelo, salida = {}, []
    for tarea in tareas:
        elegida = decision.de_tarea(tarea, reglas_humano=humano, reglas_nivel=nivel,
                                    niveles_extra=propios,
                                    alias_persona=config.get("alias_persona"),
                                    cliente=cotejo.agente_del_proyecto(tarea.get("proyecto"),
                                                                       config))
        clave = elegida.nivel.modelo or niveles.HUMANO
        por_modelo[clave] = por_modelo.get(clave, 0) + 1
        salida.append({"id": tarea.get("id"), "proyecto": tarea.get("proyecto"),
                       "texto": tarea.get("texto"),
                       # Lo que de verdad necesita saber quien va a repartir: si el modelo lo
                       # puso una persona o lo propusieron las reglas. Va aquí para que se
                       # pregunte una vez por todas y no una vez por tarea.
                       "asignado": elegida.por in LO_DIJO_UNA_PERSONA,
                       **elegida.como_json()})
    total = len(salida)
    sin_asignar = [t for t in salida if not t["asignado"] and t["despachable"]]
    if args.solo_despachables:
        salida = [t for t in salida if t["despachable"]]
    if args.solo_asignadas:
        # Las que una persona ya le dio a un modelo: lo único que se puede despachar sin
        # preguntar. Es lo que reparte un `maestro`.
        salida = [t for t in salida if t["asignado"] and t["despachable"]]
    if args.limite:
        salida = salida[:args.limite]
    imprimir({"esquema": ESQUEMA, "total": total, "por_modelo": por_modelo,
              "despachables": sum(v for k, v in por_modelo.items() if k != niveles.HUMANO),
              "sin_asignar": len(sin_asignar),
              "tareas": salida},
             list(cotejo.avisos) + (avisos_de_agentes() if por_modelo.keys() - {niveles.HUMANO}
                                    else []))
    return OK


def cmd_despachar(args):
    """Tomar la tarea a nombre del modelo elegido y mandársela.

    El orden importa y no es casual: primero se decide (gratis), después se toma (barato, y es
    lo que evita que dos despachos se pisen la misma tarea) y solo al final se lanza al modelo,
    que es lo único caro. Si algo falla antes de tomarla, no se tocó nada.
    """
    config, cotejo, humano, nivel, propios = preparar()
    tarea = cotejo.tarea(args.id)
    try:
        elegida = decision.de_tarea(tarea, override=args.modelo, reglas_humano=humano,
                                    reglas_nivel=nivel, niveles_extra=propios,
                                    alias_persona=config.get("alias_persona"),
                                    cliente=cotejo.agente_del_proyecto(tarea.get("proyecto"),
                                                                       config))
    except ValueError as error:
        raise ErrorCLI(str(error), "Mira `cotejo modelos`.") from error

    if not elegida.despachable:
        # Cómo se rebate depende de quién lo dijo: una regla se apaga, una asignación se
        # cambia. Decirle «apaga la regla» a quien asignó la tarea a mano es mandarlo a buscar
        # una regla que no existe.
        rebatir = (f"apaga la regla «{elegida.regla}» en la config"
                   if elegida.regla else
                   f"cámbiale el agente (`cotejo asignar {tarea['id']} <modelo>`)")
        rechazar(
            tarea, elegida, "veto",
            f"Esta tarea no es para un modelo: {elegida.razon}",
            f"Es tuya. Si crees que la decisión se equivoca, {rebatir}; "
            f"no hay bandera para forzarlo.",
            HUMANO)

    if elegida.por not in LO_DIJO_UNA_PERSONA and not args.auto:
        # «Si no tiene modelo asignado, solicitar modelo.» Las reglas proponen; quien decide
        # gastar es una persona. Y la respuesta se escribe en la nota con `asignar`, así que se
        # pregunta una vez en la vida de la tarea y no una vez por despacho.
        rechazar(
            tarea, elegida, "falta_modelo",
            f"Nadie le ha asignado modelo a esta tarea. La propuesta es "
            f"{elegida.nivel.modelo} ({elegida.razon})",
            f"Pregúntale a quien te lo encargó y escribe la respuesta en la nota: "
            f"`cotejo asignar {tarea['id']} <haiku|sonnet|opus>`. Para esta vez sola, "
            f"`--modelo <x>`; para aceptar la propuesta sin preguntar, `--auto`.",
            FALTA_MODELO)

    if tarea.get("estado") != "pendiente":
        dueno = f" (la tiene {tarea['agente']})" if tarea.get("agente") else ""
        rechazar(
            tarea, elegida, "no_pendiente",
            f"La tarea no está pendiente, está en «{tarea.get('estado')}»{dueno}",
            "Elige otra de `plan`. Reasignar lo que ya está en curso lo hace una persona en "
            "CotejoBoard.",
            ERROR)

    # Sin `--motor`, `--simular` sigue resolviendo a `simulado` (enseña el cliente real del
    # modelo: `sesion` o `headless` según el catálogo, sin que nadie tenga que pedirlo). Con
    # `--motor` explícito, en cambio, el motor pedido es el que se abre: lo que lo hace un
    # ensayo de verdad no es *qué motor se abre* sino que, abra el que abra, no tome la tarea
    # ni ejecute nada —eso se decide más abajo con `ensayo`, no aquí—.
    motor_nombre = args.motor or ("simulado" if args.simular else config.get("motor", "agente"))
    try:
        motor_elegido = motor.abrir(motor_nombre, config)
    except motor.MotorDesconocido as error:
        raise ErrorCLI(str(error), "Cambia --motor o la clave enrutador.motor de la "
                                   "config.") from error

    directorio = (cfg.directorio_de(config, tarea.get("proyecto", ""))
                  or cotejo.carpeta_de(tarea.get("proyecto", "")))

    # Un worktree por despacho (B3). Se planea antes de tomar —sin crear nada— para que una
    # carpeta imposible (dentro del repo o del vault) se rechace con la tarea intacta; y se
    # crea después de tomarla, porque tomar puede ponerle a la tarea el id definitivo, que es
    # el que nombra la carpeta y la rama.
    ajustes_wt = config.get("worktrees") or {}
    base_wt = worktrees.carpeta_base(ajustes_wt.get("carpeta"))
    vedadas = cotejo.carpetas_propias()
    sin_aislar = ("--sin-aislar" if args.sin_aislar else
                  "enrutador.worktrees.aislar es false" if ajustes_wt.get("aislar") is False else
                  "")
    plan_wt = None
    if not sin_aislar:
        try:
            plan_wt = worktrees.planear(tarea.get("id", ""), directorio, base_wt, vedadas)
        except worktrees.ErrorWorktree as error:
            rechazar(tarea, elegida, "worktree", error.mensaje, error.salida, ERROR)
        if plan_wt is None:
            sin_aislar = "la tarea no es de un repo de git"

    def armar_encargo(tarea, worktree):
        trabajo = Path(worktree["ruta"]) if worktree else directorio
        return motor.Encargo(
            prompt=enc.armar(tarea, elegida, directorio, args.nota, worktree),
            modelo=elegida.nivel.modelo, modelo_id=elegida.nivel.modelo_id,
            directorio=trabajo, tarea_id=tarea.get("id", ""),
            proyecto=tarea.get("proyecto", ""), cliente=elegida.nivel.cliente,
            origen=directorio, worktree=worktree, argumentos=elegida.nivel.argumentos)

    encargo = armar_encargo(tarea, plan_wt)

    # Antes de tomarla, lo que impediría lanzarla: tomarla primero la deja «Haciéndola» a nombre
    # de un modelo que nunca empezó. Corre también en un ensayo: uno que no falla donde fallaría
    # el real no sirve de ensayo.
    for rechazo, problema in despacho.antes_de_tomar(motor_elegido, encargo, plan_wt):
        rechazar(tarea, elegida, rechazo, problema,
                 "No se tomó la tarea ni se ejecutó nada: sigue pendiente.", ERROR)

    # `simulado` como motor explícito (`--motor simulado`, sin `--simular`) sigue siendo una
    # forma de pedir el mismo ensayo a mano; las dos formas no tocan la tarea.
    ensayo = args.simular or motor_elegido.nombre == "simulado"

    tomada = False
    worktree = dict(plan_wt, creado=False) if plan_wt else None
    asignada = tarea.get("agente", "")
    if not ensayo:
        tarea = cotejo.tomar(tarea["id"], elegida.nivel.modelo)
        tomada = True
        if plan_wt:
            try:
                plan_wt = worktrees.planear(tarea["id"], directorio, base_wt, vedadas)
                worktree = dict(worktrees.crear(tarea["id"], plan_wt), creado=True)
            except worktrees.ErrorWorktree as error:
                # Ya estaba tomada: se suelta antes de decir que no, para que no se quede
                # «Haciéndola» a nombre de un modelo que nunca empezó.
                cotejo.soltar(tarea["id"], f"No se pudo crear su worktree: {error.mensaje}",
                              asignada=asignada)
                rechazar(tarea, elegida, "worktree", error.mensaje,
                         error.salida + " La tarea se soltó: vuelve a estar pendiente.", ERROR)
        encargo = armar_encargo(tarea, worktree)
    donde = ({"worktree": {k: worktree.get(k) for k in ("ruta", "rama", "repo")}}
             if worktree else {})

    # El headless tarda lo que tarde el modelo, y si muere a medias (un OOM, un reinicio) no
    # vuelve para contarlo: se anota al lanzarlo, con el pid, y `revisar` mira si sigue vivo.
    lanzado, avisos_lanzar = {}, []

    def al_lanzar(pid, comando):
        lanzado.update(pid=pid, programa=comando[0] if comando else "",
                       host=socket.gethostname())
        aviso = anotar_despacho(tarea, elegida, motor=motor_elegido.nombre, tomada=tomada,
                                fase="lanzado", comando=comando, **lanzado, **donde)
        if aviso:
            avisos_lanzar.append(aviso)

    if ensayo and motor_elegido.LANZA:
        # Este motor sí abriría un cliente de verdad (headless, sesion): en el ensayo no se
        # lanza, solo se enseña el comando que se habría corrido. `argv()` no puede fallar
        # aquí: si iba a fallar, `comprobar()` ya rechazó antes de llegar a este punto.
        comando = motor_elegido.argv(encargo)
        resultado = motor.Resultado(
            True, comando, 0, ejecutado=False,
            salida=f"Simulado con --motor {motor_elegido.nombre}: no se tomó la tarea ni se "
                   f"ejecutó nada. Se lanzaría: {' '.join(comando)}")
    else:
        motor_elegido.al_lanzar = al_lanzar
        resultado = motor_elegido.ejecutar(encargo)
    # Tomada y el cliente falló (un `claude` sin sesión): vuelve a Pendiente con lo que dijo.
    soltada = tomada and not resultado.ok and despacho.soltar_si_fallo(
        cotejo, tarea["id"], motor_elegido.nombre, resultado, elegida.nivel.modelo, asignada,
        avisos_lanzar)
    if soltada:
        tarea = {**tarea, "estado": PENDIENTE, "agente": asignada}

    aviso = anotar_despacho(
        tarea, elegida, motor=motor_elegido.nombre, tomada=tomada, ok=resultado.ok,
        codigo=resultado.codigo, duracion_ms=resultado.duracion_ms, salida=resultado.salida,
        error=resultado.error, **({"fase": "terminado", **lanzado} if lanzado else {}),
        **(dict(donde, soltada=soltada) if tomada else {}))

    salida = {
        "esquema": ESQUEMA,
        "decision": elegida.como_json(),
        "tarea": {k: tarea.get(k) for k in ("id", "texto", "proyecto", "estado", "agente")},
        "tomada": tomada,
        "soltada": soltada,
        "motor": motor_elegido.nombre,
        "ejecutado": resultado.ejecutado,
        "ok": resultado.ok,
        "comando": resultado.comando,
        "duracion_ms": resultado.duracion_ms,
        "aislado": worktree is not None,
    }
    if worktree:
        salida["worktree"] = worktree
    else:
        salida["sin_aislar"] = sin_aislar
    if resultado.salida:
        salida["salida"] = resultado.salida
    if resultado.error:
        salida["error_motor"] = resultado.error
    salida["nota_para_el_agente"] = despacho.nota(
        tarea.get("id"), elegida.nivel.modelo, motor_elegido.nombre, ensayo, resultado.ok,
        soltada)
    if lanzado:
        salida["pid"] = lanzado["pid"]
    avisos = list(cotejo.avisos) + avisos_lanzar + ([aviso] if aviso else [])
    if ensayo:
        avisos += avisos_de_agentes()
    imprimir(salida, avisos)
    return OK if resultado.ok else ERROR


def hablar_maestro(proyecto, pedido, cliente=None, modelo=None, simular=False,
                   al_terminar=None, esperar=False, olvidar=False):
    """Un turno de la conversación con el maestro (cotejo-9ybn1a): la CLI espera la respuesta,
    CotejoBoard la sigue en vivo. Nunca abre una terminal; ver `apertura.hablar`."""
    return apertura.hablar(preparar(), proyecto, pedido, cliente, modelo, simular,
                           al_terminar, esperar, olvidar)


def cmd_maestro(args):
    """Decirle algo al maestro de un proyecto y esperar su respuesta."""
    if args.clientes:
        imprimir({"esquema": ESQUEMA, "clientes": sorted(clientes.CLIENTES),
                  "instalados": clientes.instalados()})
        return OK
    if not args.proyecto:
        raise ErrorCLI("Falta el proyecto", "`cotejo maestro --proyecto <nombre>`.")
    imprimir(hablar_maestro(args.proyecto, args.pedido or "", args.cliente, args.modelo,
                            args.simular, esperar=True, olvidar=args.olvidar))
    return OK


def _vive_en(ruta, donde):
    """¿Es `donde` (dónde vive una tarea, en los términos de su fuente) el archivo `ruta`?

    `donde` es relativo a la raíz de la fuente («01-Proyectos/X/Plan.md»), así que basta con
    que la ruta absoluta del plan termine en él. Una fuente que no vive en archivos nunca
    coincide, que es lo correcto: su tarea no puede ser una casilla de este plan.
    """
    if not donde:
        return False
    plan = ruta.resolve().as_posix()
    cola = Path(donde).as_posix().lstrip("/")
    return plan == Path(donde).as_posix() or plan.endswith("/" + cola)


def cmd_importar_plan(args):
    """Qué tareas sacaría un plan.md, con la dificultad y el modelo que propone `decidir`.

    Ensayo por defecto, como todo lo demás que decide sin que nadie lo pida explícitamente:
    sin `--aplicar` solo se lee el archivo y se decide, nunca se toca el vault. Con `--aplicar`
    se escribe cada una con `crear` —la misma puerta que usa un agente, verificada y atómica—,
    y con la dificultad propuesta puesta de una vez, para no tener que etiquetarlas a mano
    después de que ya se decidieron solas.

    El plan se lee una sola vez y las tareas del proyecto, otra —antes del primer `crear`—, así
    que una tarea que el propio plan repite dos veces no se duplica: la segunda sale con
    `creada: false`, igual que si ya hubiera estado en el proyecto.

    El ensayo también mira el proyecto si existe, para decir de antemano cuáles no se crearían
    y por qué (`se_crearia`, `motivo`): un ensayo que promete 24 y un `--aplicar` que crea 18
    sin explicarlo es lo que pasó con cotejo-n9mou2. Y si el plan es una nota del propio
    proyecto, sus casillas ya son tareas: no se copian a la nota principal, se avisa.
    """
    ruta = Path(args.archivo)
    try:
        texto_plan = ruta.read_text(encoding="utf-8")
    except OSError as error:
        raise ErrorCLI(f"No pude leer «{args.archivo}»: {error}",
                       "Revisa la ruta; si es relativa, lo es al directorio desde el que "
                       "corres `cotejo`.")

    textos = imp.tareas_de_plan(texto_plan)
    if not textos:
        imprimir({"esquema": ESQUEMA, "plan": str(ruta), "proyecto": args.proyecto,
                 "aplicado": False, "total": 0, "tareas": [],
                 "salida": "No encontré casillas `- [ ]` sin marcar ni encabezados de paso "
                           "(`## Paso N`, `### Tarea N`) en ese plan. No se creó nada."})
        return OK

    config, _, humano, nivel, propios = preparar()
    alias_persona = config.get("alias_persona")

    fuente = proyecto = None
    avisos = []
    if args.aplicar:
        fuente, proyectos, avisos = cargar_cotejo()
        proyecto = un_proyecto(proyectos, args.proyecto)
    else:
        # Solo para contar lo que se saltaría: el ensayo sigue proponiendo aunque el proyecto
        # no exista todavía o la fuente no abra.
        try:
            _, proyectos, avisos = cargar_cotejo()
            proyecto = un_proyecto(proyectos, args.proyecto)
        except ErrorCLI:
            proyecto, avisos = None, []
    existentes = {t.texto: t for t in proyecto.tareas} if proyecto else {}
    plan_dentro = bool(proyecto) and any(
        _vive_en(ruta, t.donde) for t in [*proyecto.tareas, *proyecto.hechas])
    if plan_dentro:
        avisos = [*avisos,
                  f"El plan es una nota de «{proyecto.nombre}»: Cotejo ya lee sus casillas como "
                  "tareas, así que no se copian a la nota principal (saldrían dos veces). Si "
                  "las quieres allí, deja el plan como lista sin casillas y vuelve a importar."]

    propuestas, creadas = [], 0
    for crudo in textos:
        texto, escrita = imp.separar_dificultad(" ".join(crudo.split()))
        if not texto:
            continue
        elegida, dificultad = imp.proponer(texto, dificultad=escrita, reglas_humano=humano,
                                           reglas_nivel=nivel, niveles_extra=propios,
                                           alias_persona=alias_persona)
        fila = {"texto": texto, "dificultad": dificultad, **elegida.como_json()}
        ya = existentes.get(texto)
        motivo = ""
        if ya is not None:
            motivo = ("ya es una tarea de Cotejo: vive en este mismo plan, que es una nota del "
                      "proyecto" if _vive_en(ruta, ya.donde) else
                      "ya hay una tarea pendiente con este texto en el proyecto")
        if not args.aplicar:
            fila["se_crearia"] = not motivo
            if motivo:
                fila["motivo"] = motivo
        else:
            if motivo:
                fila["creada"] = False
                fila["motivo"] = motivo
            else:
                try:
                    actual = escribir_cotejo(fuente.crear, proyecto, texto, dificultad)
                except NotImplementedError as error:
                    raise ErrorCLI(
                        f"La fuente «{fuente.nombre}» no sabe crear tareas",
                        "Anótalas donde vivan sus tareas y vuelve a pedir `tareas`.") from error
                except NoSeCreaAqui as error:
                    raise ErrorCLI(
                        str(error),
                        "Revisa `--proyecto`: tiene que tener nota principal. No se creó "
                        "nada de lo que faltaba en este plan.") from error
                bitacora_cotejo.anotar("crear", proyecto, actual, a=PENDIENTE)
                existentes[texto] = actual
                fila["creada"] = True
                fila["tarea"] = como_json_cotejo(actual, proyecto)
                creadas += 1
        propuestas.append(fila)

    salida = {"esquema": ESQUEMA, "plan": str(ruta), "proyecto": args.proyecto,
             "aplicado": bool(args.aplicar), "total": len(propuestas),
             "creadas": creadas, "tareas": propuestas}
    if not args.aplicar:
        salida["nota_para_el_agente"] = (
            "Ensayo: no se escribió nada. Repite con --aplicar para crearlas con `crear`, cada "
            "una con la dificultad que se enseña aquí.")
    imprimir(salida, avisos)
    return OK


def cmd_evaluar(args):
    """Medir las reglas contra tareas reales etiquetadas a mano.

    Existe para responder con un número la única pregunta que decide el futuro del enrutador:
    ¿alcanzan las reglas, o hace falta un clasificador? Mientras la respuesta sea «alcanzan»,
    añadir un modelo para decidir a qué modelo mandar las cosas es gastar por gusto.
    """
    config, _, humano, nivel, propios = preparar()
    ruta = Path(args.set) if args.set else Path(__file__).resolve().parent / "datos" / "evaluacion.json"
    try:
        casos = json.loads(ruta.read_text(encoding="utf-8"))["casos"]
    except (OSError, ValueError, KeyError) as error:
        raise ErrorCLI(f"No pude leer el set de evaluación en {ruta}: {error}",
                       "Pásame otro con --set, o revisa que tenga una clave «casos».") from error

    aciertos, fallos, por_defecto = 0, [], 0
    # Dónde acierta y dónde no, para no tener que rehacer la cuenta a mano: la confusión
    # (esperado → decidido), cada escalón o regla con sus aciertos, y las etiquetas de fuera
    # (`tag`, puestas por una persona en la nota) aparte de las revisadas, que son la cifra
    # honesta porque nadie las escribió mirando las reglas.
    confusion, por_escalon, por_origen = {}, {}, {}

    def sumar(cuenta, clave, acierto):
        fila = cuenta.setdefault(clave, {"aciertos": 0, "casos": 0})
        fila["casos"] += 1
        fila["aciertos"] += int(acierto)

    for caso in casos:
        elegida = decision.decidir(caso["texto"], agente=caso.get("agente", ""),
                                   dificultad=caso.get("dificultad", ""),
                                   reglas_humano=humano, reglas_nivel=nivel,
                                   niveles_extra=propios, alias_persona=config.get("alias_persona"))
        if elegida.por == "defecto":
            por_defecto += 1
        acierto = elegida.nivel.clave == caso["esperado"]
        clave_confusion = f"{caso['esperado']}→{elegida.nivel.clave}"
        confusion[clave_confusion] = confusion.get(clave_confusion, 0) + 1
        sumar(por_escalon, elegida.por + (f":{elegida.regla}" if elegida.regla else ""), acierto)
        sumar(por_origen, caso.get("origen") or "sin_origen", acierto)
        if acierto:
            aciertos += 1
        else:
            fallos.append({"texto": caso["texto"], "esperado": caso["esperado"],
                           "decidido": elegida.nivel.clave, "por": elegida.por,
                           "regla": elegida.regla, "origen_etiqueta": caso.get("origen", "")})

    total = len(casos) or 1
    # Un fallo hacia arriba cuesta centavos; uno hacia abajo arruina la tarea. Se cuentan aparte
    # porque una tasa de acierto sola escondería justo la mitad que importa.
    orden = {"n0": 0, "n1": 1, "n2": 2, "n3": 3}
    abaratados = [x for x in fallos if orden[x["decidido"]] < orden[x["esperado"]]]
    imprimir({"esquema": ESQUEMA, "casos": len(casos), "aciertos": aciertos,
              "tasa": round(aciertos / total, 3),
              "por_defecto": por_defecto,
              "abaratados": len(abaratados),
              "confusion": dict(sorted(confusion.items())),
              "por_escalon": dict(sorted(por_escalon.items(),
                                         key=lambda par: -par[1]["casos"])),
              "por_origen": por_origen,
              "fallos": fallos,
              "nota": "«abaratados» son los que se decidieron por debajo de lo esperado, que "
                      "es el único tipo de fallo que arruina la tarea en vez de costar unos "
                      "centavos de más."})
    return OK


# Cuántos días sin moverse hacen que un despacho pase de «trabajando» a «colgado». Dos es lo
# que tarda en ser raro: una tarea normal se entrega el mismo día, y una que lleva dos sin
# aparecer por «Para comprobar» o sin volver con un motivo es una que se perdió.
DIAS_PARA_COLGADA = 2

# En qué orden se enseñan. Primero lo que pide que alguien mire, que es para lo que existe
# este verbo; lo que salió bien puede esperar al final de la lista.
ORDEN_DESENLACE = ("colgada", "devuelta", "perdida", "reasignada", "trabajando",
                   "entregada", "comprobada")


def proceso_muerto(linea):
    """¿Es un headless que se anotó al lanzar, nunca al terminar, y cuyo proceso ya no está?

    Solo se puede saber en la máquina que lo lanzó: el vault puede estar sincronizado con otra,
    y allí ese pid es de cualquiera. Desde otra máquina no se da por muerto.
    """
    return procesos.anotado_muerto(linea)  # también lo usa `preparar`, para el inicio


def desenlace(linea, tarea, dias, umbral):
    """En qué acabó un despacho, mirando dónde está hoy la tarea que se repartió."""
    if tarea is None:
        # El id dejó de resolver. Pasa de verdad: una tarea sin marca de bloque se nombra por
        # su nota y su línea, y cualquier edición por encima la mueve.
        return "perdida"
    estado = tarea.get("estado")
    if estado == "por-validar":
        return "entregada"
    if estado == "hecha":
        return "comprobada"
    if estado == "en-curso":
        if tarea.get("agente") != linea.get("modelo"):
            return "reasignada"
        if proceso_muerto(linea):
            # Nadie la está haciendo: el cliente que la tenía murió sin volver. Esperar a que
            # cuente como colgada son días con la tarea bloqueada por nadie.
            return "perdida"
        return "colgada" if dias >= umbral else "trabajando"
    return "devuelta"  # volvió a pendiente: alguien la bloqueó o la devolvieron


def cmd_revisar(args):
    """Qué pasó con lo que se repartió: entregado, colgado, devuelto o ni siquiera repartido.

    Es la contraparte de `plan`. `plan` contesta qué hay por repartir; esto contesta si
    repartirlo sirvió, que es la única pregunta que decide si el enrutador se queda. Sin este
    verbo, la bitácora de despachos era un archivo que solo crecía: decía a quién se le mandó
    cada tarea y no si aquello acabó en algo.

    Cruza las dos mitades que hasta ahora no se hablaban —lo que se decidió y dónde están hoy
    las tareas— y por eso enseña también lo que el enrutador **no** repartió: los rechazos que
    ahorró una entrega falsa, y las tareas que alguien puso en curso sin pasar por aquí.
    """
    _, cotejo, _, _, _ = preparar()
    umbral = args.dias if args.dias is not None else DIAS_PARA_COLGADA
    ahora = int(time.time())

    lineas = bitacora.ultimos(args.limite)
    if args.proyecto:
        lineas = [l for l in lineas if args.proyecto.lower() in (l.get("proyecto") or "").lower()]

    rechazos, ensayos, lanzamientos, ultimo_de = {}, 0, 0, {}
    for linea in lineas:
        if linea.get("fase") == "lanzado":
            # Media decisión: la otra mitad es su línea «terminado», si llegó. No cuenta aparte.
            lanzamientos += 1
        if linea.get("rechazo"):
            rechazos[linea["rechazo"]] = rechazos.get(linea["rechazo"], 0) + 1
        elif not linea.get("tomada"):
            ensayos += 1
        elif linea.get("tarea"):
            # La lista viene en orden: gana el más nuevo. Por el id de ahora, que los
            # despachos de antes de migrar dicen `foco-…`.
            ultimo_de[id_actual(linea["tarea"])] = linea

    tareas = {id_actual(t["id"]): t for t in cotejo.tareas(args.proyecto)}
    repartidas, cuenta = [], {}
    for identificador, linea in ultimo_de.items():
        tarea = tareas.get(identificador)
        dias = round((ahora - linea.get("ts", ahora)) / 86400, 1)
        cual = desenlace(linea, tarea, dias, umbral)
        cuenta[cual] = cuenta.get(cual, 0) + 1
        fila = {"tarea": identificador, "desenlace": cual, "dias": dias,
                "modelo": linea.get("modelo"), "por": linea.get("por"),
                "regla": linea.get("regla") or "",
                "proyecto": linea.get("proyecto") or (tarea or {}).get("proyecto"),
                "texto": linea.get("texto") or (tarea or {}).get("texto") or "",
                "motor": linea.get("motor")}
        if cual == "perdida":
            fila["por_que"] = ("el proceso que la hacía ya no existe" if tarea else
                               "su id ya no corresponde a ninguna tarea")
        if linea.get("pid"):
            fila["pid"] = linea["pid"]
        # Dónde quedó el trabajo: lo registrado ahora (con `existe`) manda sobre lo anotado al
        # despachar, que puede ser de un worktree que ya se retiró al aprobarla.
        registrado = worktrees.de_tarea(identificador)
        if registrado:
            fila["worktree"] = {k: registrado.get(k) for k in ("ruta", "rama", "repo", "existe")}
        elif linea.get("worktree"):
            fila["worktree"] = {**linea["worktree"], "existe": False}
        if tarea:
            fila["estado"] = tarea.get("estado")
            fila["agente"] = tarea.get("agente")
            # Lo último que se dijo de ella. En una devuelta es el motivo, y es exactamente el
            # dato que dice si el ruteo estuvo mal.
            for clave in ("motivo", "evidencia"):
                if tarea.get(clave):
                    fila[clave] = tarea[clave]
        repartidas.append(fila)
    repartidas.sort(key=lambda f: (ORDEN_DESENLACE.index(f["desenlace"]), -f["dias"]))

    # Lo que está en curso sin haber pasado por aquí. No es un error —una persona puede tomar
    # una tarea— pero sí es la diferencia entre «el enrutador reparte el trabajo» y «el
    # enrutador reparte parte del trabajo», y esa diferencia no se ve en ningún otro sitio.
    sin_despacho = [{"tarea": t["id"], "proyecto": t["proyecto"], "agente": t.get("agente", ""),
                     "texto": t.get("texto", "")}
                    for t in tareas.values()
                    if t.get("estado") == "en-curso" and id_actual(t["id"]) not in ultimo_de]

    imprimir({
        "esquema": ESQUEMA,
        "archivo": str(bitacora.ruta()),
        "dias_para_colgada": umbral,
        "resumen": {"decisiones": len(lineas) - lanzamientos, "repartidas": len(repartidas),
                    "ensayos": ensayos, "rechazos": rechazos,
                    "desenlaces": cuenta, "en_curso_sin_despacho": len(sin_despacho)},
        "repartidas": repartidas,
        "en_curso_sin_despacho": sin_despacho,
        "nota": "«colgada» es la que nadie entregó ni devolvió y ya lleva días tomada: es lo "
                "que hay que mirar. «devuelta» trae el motivo, que es lo que dice si el ruteo "
                "se equivocó. «perdida» en curso es un headless que murió sin volver: nadie la está "
                "haciendo; bloquéala o devuélvela a pendiente. «rechazos.veto» es cuántas "
                "entregas falsas se evitaron.",
    }, cotejo.avisos)
    return OK


def cmd_capacidad(args):
    """Cuántos despachos caben ahora sin llevar la máquina al OOM, y cuáles esperar.

    Se pregunta **antes** de repartir en paralelo: la respuesta cambia con lo que esté corriendo,
    así que no se guarda en ningún sitio. Con `--proyecto`, parte las tareas asignadas de ese
    proyecto entre las que caben ahora y las que esperan, en el orden de `plan`.
    """
    config, cotejo, humano, nivel, propios = preparar()
    ajustes = config.get("capacidad") or {}
    from tareas import lanzados
    foto = capacidad.leer((c.ejecutable for c in clientes.CLIENTES.values()),
                          lanzados.pids_propios())
    calculo = capacidad.calcular(foto, ajustes)
    caben = calculo["caben"]
    agentes = foto.get("agentes")
    salida = {
        "esquema": ESQUEMA,
        "caben": caben,
        "limita": calculo["limita"],
        "limites": calculo["limites"],
        "por_que": calculo["por_que"],
        "mb_por_agente": calculo["mb_por_agente"],
        "mb_por_agente_origen": calculo["mb_por_agente_origen"],
        "reserva_mb": calculo["reserva_mb"],
        "maquina": {k: foto.get(k) for k in ("sistema", "cpus", "carga", "memoria_total_mb",
                                             "memoria_disponible_mb", "swap_total_mb",
                                             "swap_libre_mb")},
        "agentes_en_curso": None if agentes is None else len(capacidad.en_curso(agentes)),
        "agentes": agentes,
    }

    if args.proyecto:
        tareas = cotejo.tareas(args.proyecto, "pendiente")
        asignadas = []
        for tarea in tareas:
            elegida = decision.de_tarea(tarea, reglas_humano=humano, reglas_nivel=nivel,
                                        niveles_extra=propios,
                                        alias_persona=config.get("alias_persona"))
            if elegida.despachable and elegida.por in LO_DIJO_UNA_PERSONA:
                asignadas.append({"id": tarea.get("id"), "texto": tarea.get("texto"),
                                  "modelo": elegida.nivel.modelo})
        corte = len(asignadas) if caben is None else caben
        salida["ahora"] = asignadas[:corte]
        salida["esperar"] = asignadas[corte:]

    if caben is None:
        salida["salida"] = ("No pude medir esta máquina: reparte de a uno y mira cómo va antes "
                            "de lanzar el siguiente.")
    elif caben == 0:
        salida["salida"] = (f"No despaches nada más ahora: lo limita {calculo['limita']}. "
                            f"Espera a que termine alguno de los que corren y vuelve a "
                            f"preguntar con `cotejo capacidad`.")
    else:
        salida["salida"] = (f"Caben {caben} despacho(s) más que abran su propio proceso "
                            f"(--motor sesion o headless); lo limita {calculo['limita']}. "
                            f"Vuelve a preguntar antes de cada tanda: cada uno que arranca "
                            f"cambia la cuenta.")
    salida["nota"] = ("Cuenta para los despachos que abren un proceso aparte. Un subagente de "
                      "esta misma sesión (--motor agente) pesa bastante menos, pero no nada. "
                      "Los supuestos se cambian en enrutador.capacidad de la config.")
    imprimir(salida, cotejo.avisos)
    return OK


def cmd_despachos(args):
    """Qué se repartió, a quién y cómo salió."""
    imprimir({"esquema": ESQUEMA, "archivo": str(bitacora.ruta()),
              "despachos": bitacora.ultimos(args.limite, args.tarea)})
    return OK


def cmd_config(args):
    """La config efectiva del enrutador y de dónde salió cada cosa.

    Con `init` o `validar` es otra cosa: el archivo entero, que es de Cotejo y no solo del
    enrutador. Van colgadas de este verbo porque el verbo ya se llamaba `config`.
    """
    if args.accion:
        from tareas import conexion
        return conexion.config_init() if args.accion == "init" else conexion.config_validar()
    config, cotejo, _, _, _ = preparar()
    visible = {k: v for k, v in config.items() if k != "_origen"}
    imprimir({"esquema": ESQUEMA, "config": visible, "origen": config["_origen"],
              "tareas_disponibles": cotejo.disponible(),
              "motores": sorted(motor.registro())})
    return OK


def cmd_importar_obsidian(args):
    """Traer un proyecto del vault a su `.cotejo/` (v1.2): ensayo (D1) o, con `--aplicar`, de verdad (D2).

    Lee el vault de la config de la fuente obsidian (o `COTEJO_VAULT`), aunque la fuente activa
    sea otra: se importa *desde* Obsidian, no se lee el proyecto *por* Obsidian. Todo el reparto
    está en `tareas/importar_obsidian.py`; aquí solo se arma la respuesta.
    """
    from tareas import configuracion, importar_obsidian as io
    from tareas.fuentes.obsidian import Obsidian
    vault = Obsidian(configuracion.parametros(configuracion.cargar(), "obsidian"))
    if vault.problema:
        raise ErrorCLI(vault.problema, "`cotejo fuentes info obsidian` dice qué pide.")
    try:
        plan = io.planear(vault.vault, vault.carpeta_proyectos, args.proyecto, args.destino)
    except io.NoSeImporta as error:
        raise ErrorCLI(str(error), error.salida)
    datos = plan.resumen(detalle=args.detalle)
    if args.aplicar:
        try:
            hecho = io.aplicar(plan, vault.vault)
        except io.NoSeImporta as error:
            raise ErrorCLI(str(error), error.salida)
        repo = plan.repo["ruta"]
        imprimir_json({"esquema": ESQUEMA, "ensayo": False, **datos, **hecho,
                       "salida": (f"Escrito en {Path(repo, '.cotejo')} sin commit: revísalo con "
                                  f"`git -C {repo} status` y haz tú el commit. «{plan.proyecto}» "
                                  "ya se lee del repo; la nota del vault no se tocó, y quitarlo "
                                  "de `migrados` en la config de obsidian lo deshace.")})
        return OK
    sin = len(datos["sin_clasificar"])
    imprimir_json({"esquema": ESQUEMA, "ensayo": True, **datos,
                   "salida": (f"Ensayo: no se escribió nada. {datos['nuevas']} entradas nuevas "
                              f"irían a {Path(plan.repo['ruta'], '.cotejo')}"
                              + (f", {sin} sin clasificar" if sin else "")
                              + (" (y se le haría `git init`)" if plan.repo["git_init"] else "")
                              + ". Enséñalo a quien lo pidió antes de `--aplicar`.")})
    return OK


def cmd_importar_notion(args):
    """Las tareas de un proyecto de Notion a su `.cotejo/` (v1.2 · D3): ensayo o `--aplicar`.

    Más modesto que `importar obsidian`: solo trae lo que el adaptador que ya existe sabe leer
    (`tareas/fuentes/externa.py` + `extras/notion/cotejo_notion.py`). Las tareas van a
    `tareas.md` con el mismo formato que Obsidian; cada página de Notion, además, como una
    referencia con resumen pendiente, para que la tarea de revisión decida qué hacer con lo
    que el adaptador no lee (el contenido de la página). Todo el reparto está en
    `tareas/importar_notion.py`; aquí solo se arma la respuesta.
    """
    from tareas import importar_notion as inot
    try:
        plan = inot.planear(args.proyecto, args.destino)
    except inot.NoSeImporta as error:
        raise ErrorCLI(str(error), error.salida)
    datos = plan.resumen(detalle=args.detalle)
    if args.aplicar:
        try:
            hecho = inot.aplicar(plan)
        except inot.NoSeImporta as error:
            raise ErrorCLI(str(error), error.salida)
        repo = plan.repo["ruta"]
        imprimir_json({"esquema": ESQUEMA, "ensayo": False, **datos, **hecho,
                       "salida": (f"Escrito en {Path(repo, '.cotejo')} sin commit: revísalo con "
                                  f"`git -C {repo} status` y haz tú el commit. La tarea de "
                                  "revisión dice qué abrir en Notion para completar resúmenes.")})
        return OK
    imprimir_json({"esquema": ESQUEMA, "ensayo": True, **datos,
                   "salida": (f"Ensayo: no se escribió nada. {datos['conteo']['tareas']} "
                              f"tarea(s) irían a tareas.md y {datos['nuevas']} referencia(s) "
                              f"nuevas a "
                              f"{Path(plan.repo['ruta'], '.cotejo')}"
                              + (" (y se le haría `git init`)" if plan.repo["git_init"] else "")
                              + ". Enséñalo a quien lo pidió antes de `--aplicar`.")})
    return OK


def _sin_frontmatter(texto):
    if texto.startswith("---"):
        partes = texto.split("---", 2)
        texto = partes[2].lstrip() if len(partes) > 2 else texto
    return texto


def cmd_protocolo(args):
    """El protocolo del agente, escrito una sola vez y repartido desde aquí.

    Sin bandera, el núcleo (SKILL.md); con `--completo`, además las referencias que van al lado.
    """
    desde_entorno = os.environ.get("COTEJO_PROTOCOLO")
    raiz = Path(__file__).resolve().parent.parent
    candidatas = ([Path(desde_entorno)] if desde_entorno else []) + [
        raiz / "skills" / "cotejo" / "SKILL.md"]
    for ruta in candidatas:
        if ruta.exists():
            # Sin el frontmatter: quien pide el protocolo por aquí no es Claude Code leyendo una
            # skill, es alguien con una terminal que quiere las instrucciones.
            texto = _sin_frontmatter(ruta.read_text(encoding="utf-8"))
            if getattr(args, "completo", False):
                for referencia in sorted((ruta.parent / "referencias").glob("*.md")):
                    texto = texto.rstrip("\n") + "\n\n---\n\n" + referencia.read_text(
                        encoding="utf-8")
            sys.stdout.write(texto if texto.endswith("\n") else texto + "\n")
            return OK
    raise ErrorCLI("No encontré el protocolo",
                   "Debería estar en skills/cotejo/SKILL.md junto al paquete; apúntalo con "
                   "COTEJO_PROTOCOLO=/ruta/SKILL.md.")


# --- los verbos, colgados del analizador de Cotejo ------------------------------


def anadir(sub):
    """Cuelga los verbos del enrutador del `add_subparsers` de la CLI de Cotejo."""
    modelos = sub.add_parser("modelos", help="Listar, agregar o quitar modelos disponibles")
    acciones_modelos = modelos.add_subparsers(dest="accion")
    agregar = acciones_modelos.add_parser(
        "agregar", help="Registrar o actualizar un modelo de cualquier cliente")
    agregar.add_argument("--clave", required=True,
                         help="Nombre corto que se guardará en #agente/<clave>")
    agregar.add_argument("--modelo-id", required=True,
                         help="Identificador que entiende el cliente, por ejemplo provider/model")
    agregar.add_argument("--cliente", required=True,
                         help="Cliente que ejecuta el modelo, por ejemplo opencode")
    agregar.add_argument("--nivel", choices=["n1", "n2", "n3"], default="n2",
                         help="Tamaño de trabajo que representa (por defecto n2)")
    agregar.add_argument("--nombre", help="Nombre legible para el catálogo")
    agregar.add_argument("--entrada-mtok", type=float, default=0.0)
    agregar.add_argument("--salida-mtok", type=float, default=0.0)
    agregar.add_argument("--argumento", action="append", metavar="ARG",
                         help="Argumento extra para el cliente con este modelo (repetible; "
                              "p. ej. --argumento=-c --argumento=model_reasoning_effort=high)")
    agregar.set_defaults(funcion=cmd_modelos)
    vivos = acciones_modelos.add_parser(
        "vivos", help="Qué agentes tienen sesión y qué modelos ofrece cada uno hoy")
    vivos.add_argument("--refrescar", action="store_true",
                       help="Preguntar a los CLIs aunque haya una lista reciente guardada")
    vivos.add_argument("--sin-preguntar", action="store_true",
                       help="Solo lo guardado o los alias, sin lanzar ningún CLI")
    vivos.set_defaults(funcion=cmd_modelos)
    quitar = acciones_modelos.add_parser("quitar", help="Quitar un modelo personalizado")
    quitar.add_argument("clave")
    quitar.set_defaults(funcion=cmd_modelos)
    modelos.set_defaults(funcion=cmd_modelos)

    decidir = sub.add_parser("decidir", help="Quién atendería esto, y por qué. No escribe nada")
    decidir.add_argument("texto", nargs="*", help="El texto a enrutar")
    decidir.add_argument("--tarea", help="Un id de Cotejo, en vez del texto")
    decidir.add_argument("--agente", help="Simular que está asignada a este agente")
    decidir.add_argument("--dificultad", choices=["facil", "medio", "dificil"])
    decidir.add_argument("--modelo", help="Forzar el nivel y ver qué habría salido si no")
    decidir.set_defaults(funcion=cmd_decidir)

    plan = sub.add_parser("plan", help="Qué modelo recibiría cada tarea pendiente")
    plan.add_argument("--proyecto")
    plan.add_argument("--estado", choices=["pendiente", "en-curso", "por-validar", "hecha"])
    plan.add_argument("--limite", type=int)
    plan.add_argument("--solo-despachables", action="store_true", dest="solo_despachables",
                      help="Esconde las que son de una persona")
    plan.add_argument("--solo-asignadas", action="store_true", dest="solo_asignadas",
                      help="Solo las que una persona asignó a un modelo (#agente/<modelo>)")
    plan.set_defaults(funcion=cmd_plan)

    despachar = sub.add_parser("despachar", help="Tomar la tarea y mandársela al modelo")
    despachar.add_argument("id")
    despachar.add_argument("--modelo", help="Forzar el nivel (no sirve para forzar el humano)")
    despachar.add_argument("--motor", help="agente | sesion | headless | simulado")
    despachar.add_argument("--nota", default="",
                           help="Contexto tuyo para quien la haga: qué ya está hecho, qué no "
                                "tocar, qué cambió desde que se escribió la tarea")
    despachar.add_argument("--auto", action="store_true",
                           help="Acepta la propuesta de las reglas sin preguntar por el modelo")
    despachar.add_argument("--simular", action="store_true",
                           help="Decide y arma el encargo sin tomar la tarea ni ejecutar nada")
    despachar.add_argument("--sin-aislar", action="store_true", dest="sin_aislar",
                           help="No crear el worktree con rama cotejo/<id>: el agente trabaja "
                                "en la carpeta del proyecto, como antes de la 1.1")
    despachar.set_defaults(funcion=cmd_despachar)

    evaluar = sub.add_parser("evaluar", help="Medir las reglas contra tareas reales etiquetadas")
    evaluar.add_argument("--set", help="Otro archivo de casos")
    evaluar.set_defaults(funcion=cmd_evaluar)

    revisar = sub.add_parser("revisar", help="Qué pasó con lo que se repartió")
    revisar.add_argument("--proyecto")
    revisar.add_argument("--dias", type=int,
                         help=f"Desde cuántos días sin moverse cuenta como colgada "
                              f"(por defecto {DIAS_PARA_COLGADA})")
    revisar.add_argument("--limite", type=int, default=500,
                         help="Cuántas líneas de la bitácora mirar hacia atrás")
    revisar.set_defaults(funcion=cmd_revisar)

    capacidad_ = sub.add_parser(
        "capacidad", help="Cuántos despachos caben ahora en esta máquina sin llevarla al OOM, "
                          "y cuáles esperar. No escribe nada")
    capacidad_.add_argument("--proyecto", help="Parte sus tareas asignadas entre ahora y esperar")
    capacidad_.set_defaults(funcion=cmd_capacidad)

    despachos = sub.add_parser("despachos", help="La bitácora de despachos, en crudo")
    despachos.add_argument("--limite", type=int, default=20)
    despachos.add_argument("--tarea", help="Solo los de esta tarea")
    despachos.set_defaults(funcion=cmd_despachos)

    config = sub.add_parser("config", help="La config del enrutador y de dónde salió; "
                                           "init la crea, validar dice qué tiene mal")
    config.add_argument("accion", nargs="?", choices=["init", "validar"])
    config.set_defaults(funcion=cmd_config)

    maestro_ = sub.add_parser(
        "maestro", help="Hablar con el maestro de un proyecto: añade tareas, contesta sobre "
                        "el proyecto y propone repartir lo asignado")
    maestro_.add_argument("--proyecto")
    maestro_.add_argument("--cliente",
                          help=f"Con qué agente habla el maestro: {' | '.join(clientes.CLIENTES)} "
                               f"(por defecto, el primero que esté instalado)")
    maestro_.add_argument("--modelo", help="El modelo del maestro (por defecto, el de "
                                           "enrutador.maestro.modelos o el del cliente)")
    maestro_.add_argument("--pedido", "--indicacion", dest="pedido",
                          help="Lo que le dices, en llano («apunta que falta el login»)")
    maestro_.add_argument("--olvidar", action="store_true", help="Empezar la conversación")
    maestro_.add_argument("--simular", action="store_true",
                          help="Enseña qué lanzaría y con qué instrucción, sin lanzar nada")
    maestro_.add_argument("--clientes", action="store_true",
                          help="Qué clientes sabe abrir y cuáles están instalados")
    maestro_.set_defaults(funcion=cmd_maestro)

    importar = sub.add_parser(
        "importar", help="Traer cosas a Cotejo: un plan.md como tareas, un proyecto del vault")
    acciones_importar = importar.add_subparsers(dest="accion", required=True)
    # Subcomando porque en la 1.2 llega `importar obsidian|notion`: otras fuentes, mismo verbo.
    plan_ = acciones_importar.add_parser(
        "plan", help="Casillas `- [ ]` o, si no hay, encabezados de paso. Ensayo por defecto")
    plan_.add_argument("archivo", help="Ruta al plan.md")
    plan_.add_argument("--proyecto", required=True,
                       help="En qué proyecto de Cotejo crear las tareas")
    plan_.add_argument("--aplicar", action="store_true",
                       help="Escribe las tareas con `crear`; sin esto es un ensayo que no "
                            "toca el vault")
    plan_.set_defaults(funcion=cmd_importar_plan)
    obsidian_ = acciones_importar.add_parser(
        "obsidian", help="Un proyecto del vault a su .cotejo/. Ensayo por defecto")
    obsidian_.add_argument("proyecto", help="El nombre del proyecto en el vault")
    obsidian_.add_argument("--destino", metavar="CARPETA",
                           help="El repo donde va .cotejo/ si el proyecto no tiene uno")
    obsidian_.add_argument("--detalle", action="store_true",
                           help="Lista cada entrada (tipo, título, origen), no solo los conteos")
    obsidian_.add_argument("--aplicar", action="store_true",
                           help="Lo escribe en el repo (sin commit), crea la tarea de revisión "
                                "y lo marca como migrado; sin esto es un ensayo")
    obsidian_.set_defaults(funcion=cmd_importar_obsidian)
    notion_ = acciones_importar.add_parser(
        "notion", help="Las tareas de un proyecto de Notion y sus páginas como referencias. "
                       "Ensayo por defecto")
    notion_.add_argument("proyecto", help="El nombre del proyecto, como lo ve Cotejo en Notion")
    notion_.add_argument("--destino", metavar="CARPETA",
                         help="El repo donde va .cotejo/ si el proyecto no tiene uno")
    notion_.add_argument("--detalle", action="store_true",
                         help="Lista cada entrada (tipo, título, origen), no solo los conteos")
    notion_.add_argument("--aplicar", action="store_true",
                         help="Lo escribe en el repo (sin commit) y crea la tarea de revisión; "
                              "sin esto es un ensayo")
    notion_.set_defaults(funcion=cmd_importar_notion)

    protocolo = sub.add_parser("protocolo", help="Las instrucciones para un agente, en Markdown")
    protocolo.add_argument("--completo", action="store_true",
                           help="Añade las referencias (repartir, almacén, mantenimiento)")
    protocolo.set_defaults(funcion=cmd_protocolo)
