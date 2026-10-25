"""Los verbos para conectar Cotejo con su segundo cerebro: de dónde lee y si puede leer.

    init                            dentro de un repo git: crea el esqueleto .cotejo/ completo y
                                    lo registra en la fuente «repo», sin activarla
    doctor                         todo lo que hay que saber para saber si funciona, en una llamada
    fuentes                        las que hay, cuál está activa y si les falta algo
    fuentes info <nombre>          qué parámetros pide y cómo se registra
    fuentes probar <nombre>        la conecta y la lee, sin escribir y sin activarla
    fuentes usar <nombre>          la activa (solo si `probar` pasa)
    fuentes agregar <nombre> ...   registra un adaptador externo
    fuentes quitar <nombre>        lo desregistra; no borra nada de la app de fuera
    config init | validar          crear el archivo, o decir qué tiene mal sin tocarlo

Está aparte de `cli.py` porque no es trabajo sobre tareas sino sobre la instalación, y porque
`cli.py` se lee entero para entender el contrato con el agente: esto no es parte de él.

Nada de aquí sabe de Obsidian ni de Notion. A una fuente se le pregunta qué parámetros tiene
(`parametros`, y `protocolo` si es externa); lo que no sabe decir de sí misma no lo inventa
Cotejo.
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from . import __version__, bitacora, configuracion, fuente as f, modelo, origen, usuario, version as _version
from .almacen import ARCHIVO_PROYECTO, Almacen, CARPETA as CARPETA_COTEJO, TIPOS
from .cli import ESQUEMA, ErrorCLI, imprimir
from .fuentes.obsidian import vault_valido
from .fuentes.repo import ARCHIVO as ARCHIVO_TAREAS

NOMBRE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
# Los que un adaptador no puede usar como parámetro: los pone Cotejo.
RESERVADAS = ("tipo", "comando", "fuente")


def _config_o_error():
    """El archivo, para escribirlo. Si está roto no se escribe encima: se perdería lo que hay."""
    try:
        return configuracion.leer()
    except configuracion.ConfigRota as error:
        raise ErrorCLI(str(error), "Arréglalo a mano (`config validar` dice qué tiene) y "
                                   "repite. No se escribió nada.") from error


def _abrir(nombre, datos):
    try:
        return f.abrir({**configuracion.parametros(datos, nombre), "fuente": nombre})
    except ValueError as error:
        raise ErrorCLI(str(error), "`fuentes` lista las que hay.") from error


def _conocida(nombre, datos):
    return nombre in f.FUENTES or nombre in configuracion.registradas(datos)


def diagnosticar(nombre, datos):
    """Si una fuente funciona, y si no, por qué. Lee, no escribe nunca.

    Pregunta por orden de lo barato a lo caro: la config, el adaptador (`doctor`), y al final
    un escaneo de verdad, que es lo único que demuestra que se puede trabajar con ella.
    """
    fuente = _abrir(nombre, datos)
    informe = {"nombre": nombre, "tipo": fuente.tipo, "ok": False}
    if fuente.problema:
        return {**informe, "problema": fuente.problema}
    if fuente.tipo == "externa":
        try:
            respuesta = fuente.llamar("doctor")
        except (modelo.FuenteNoResponde, NotImplementedError, modelo.TareaCambiada,
                modelo.NoSeCreaAqui) as error:
            return {**informe, "problema": str(error), "salida": getattr(error, "salida", "")}
        informe["mensaje"] = str(respuesta.get("mensaje") or "")
        if not respuesta.get("ok"):
            return {**informe, "problema": informe["mensaje"] or "El adaptador dice que no está bien",
                    "salida": str(respuesta.get("salida") or "")}
    avisos = []
    proyectos = fuente.escanear(incluir_hechas=False, avisos=avisos)
    if fuente.problema:
        return {**informe, "problema": fuente.problema}
    return {**informe, "ok": True, "proyectos": len(proyectos),
            "pendientes": sum(len(p.tareas) for p in proyectos), "avisos": avisos}


# --- init ---------------------------------------------------------------------


def _raiz_git(inicio):
    """La raíz del repo que contiene `inicio`, subiendo carpetas hasta encontrar un `.git`.

    `.git` puede ser carpeta (un repo normal) o archivo (un worktree, que es justo donde
    trabaja un agente despachado). Las dos cuentan: lo que importa aquí es «hay un repo»,
    no las reglas de `fuentes/repo.py` para no repetir un proyecto al escanear una raíz.
    """
    actual = Path(inicio).resolve()
    for candidato in (actual, *actual.parents):
        if (candidato / ".git").exists():
            return candidato
    return None


def _repo_registrado(raiz, datos):
    """Si `raiz` ya cuenta para la fuente «repo»: en su `repos`, o cubierta por su `raiz`.

    Comparte el criterio entre `init` (para no duplicar) y `doctor` (para saber si hace
    falta avisar). Lee de la config con `configuracion.parametros`, igual que la propia
    fuente, así que los dos sitios ven exactamente lo mismo.
    """
    params = configuracion.parametros(datos, "repo")
    repos = [r for r in (params.get("repos") or []) if isinstance(r, str) and r.strip()]
    if any(Path(r).expanduser().resolve() == raiz for r in repos):
        return True
    raiz_cfg = params.get("raiz")
    # Si una `raiz` configurada ya es el padre directo de este repo, `fuentes/repo.py` lo
    # descubre solo: contarlo también en `repos` sería un registro de más, no de menos.
    return bool(isinstance(raiz_cfg, str) and raiz_cfg.strip()
               and Path(raiz_cfg).expanduser().resolve() == raiz.parent)


def _iniciar_repo(destino):
    """Crea `destino` si no existe y le hace `git init -q` (sin commits). Devuelve su ruta
    resuelta. Si git falla o no está, error claro; una carpeta recién creada se retira."""
    if shutil.which("git") is None:
        raise ErrorCLI("No encuentro git", "Instálalo para que `cotejo init` pueda hacer "
                       "`git init`. No se escribió nada.")
    existia = destino.exists()
    destino.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(_version.comando_git(destino, "init", "-q"), check=True,
                       capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        if not existia:
            shutil.rmtree(destino, ignore_errors=True)
        raise ErrorCLI(f"No pude hacer `git init` en {destino}: {error}",
                       "Hazlo a mano y vuelve a correr `cotejo init`.") from None
    return destino.resolve()


def _git_salida(raiz, *args):
    """(código, salida+error) de un git en `raiz`; código None si no hay git o no arranca."""
    try:
        hecho = subprocess.run(_version.comando_git(raiz, *args), stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        return None, str(error)
    return hecho.returncode, (hecho.stdout + hecho.stderr).strip()


IDENTIDAD_COTEJO = {"user.name": "Cotejo", "user.email": "cotejo@localhost"}


def _asegurar_identidad(raiz):
    """Si git no tiene nombre o correo efectivos en `raiz`, los pone en la config LOCAL del repo
    (cotejo-q93zyw). Devuelve la lista de claves que puso, vacía si no hizo falta.

    Los agentes commitean dentro del proyecto y sin identidad cada commit exige `-c user.email=…`
    (y el sandbox no les deja escribir `.git/config`); `init` sí puede, porque tiene el `.git`
    permitido. Lo que la persona ya tiene (global, del sistema o local) manda: solo se rellena lo
    que `git config` ve vacío, nunca se sobrescribe. Lo que falte se rellena con el valor de
    Cotejo. No lanza: un fallo se queda en vacío y el commit inicial aún tiene su propio `-c`.
    """
    if shutil.which("git") is None:
        return []
    puestas = []
    for clave, valor in IDENTIDAD_COTEJO.items():
        codigo, actual = _git_salida(raiz, "config", "--get", clave)
        if codigo is None:
            return puestas
        if codigo == 0 and actual.strip():
            continue
        if _git_salida(raiz, "config", "--local", clave, valor)[0] == 0:
            puestas.append(clave)
    return puestas


def _commit_inicial(raiz):
    """Si el repo no tiene ningún commit, le hace uno con `.cotejo/` (v1.2.5). Devuelve
    `(hash, aviso)`: el hash corto si lo hizo, y un aviso en palabras si no pudo.

    Un repo sin commits no tiene HEAD y `despachar` no puede crearle un worktree. Sin identidad
    git configurada (un HOME vacío) usa una de Cotejo solo para este commit, pasada con `-c`:
    no toca la config de nadie. No lanza: `init` ya dejó todo lo suyo hecho, y un commit que
    falla se dice, no se esconde. Un repo que ya tiene commits no se toca ni se mira más.
    """
    if shutil.which("git") is None:
        return "", ""
    # 1 es «repo sin HEAD»; 0, que ya tiene commits; otro código, que no es un repo de verdad.
    if _git_salida(raiz, "rev-parse", "--verify", "-q", "HEAD")[0] != 1:
        return "", ""
    haga = "haz el primer commit a mano (`git add .cotejo && git commit`)"
    codigo, salida = _git_salida(raiz, "add", "--", CARPETA_COTEJO)
    if codigo != 0:
        return "", f"No pude preparar el commit inicial ({salida}): {haga}."
    identidad = []
    if _git_salida(raiz, "config", "user.name")[0] != 0 \
            or _git_salida(raiz, "config", "user.email")[0] != 0:
        identidad = ["-c", "user.name=Cotejo", "-c", "user.email=cotejo@localhost"]
    codigo, salida = _git_salida(raiz, *identidad, "-c", "commit.gpgsign=false", "commit",
                                 "-q", "--no-verify", "-m", "Cotejo: carpeta .cotejo/ inicial")
    if codigo != 0:
        return "", f"No pude hacer el commit inicial ({salida}): {haga}."
    return _git_salida(raiz, "rev-parse", "--short", "HEAD")[1], ""


def cmd_init(args):
    """Prepara un repo para Cotejo: su `.cotejo/` completo y su sitio en la fuente «repo».

    Por defecto es la carpeta actual, como en `entregar --repo`: el mismo `--repo` sirve para
    probarlo contra un repo de mentira sin movernos de sitio. No cambia la fuente activa —la
    decide quien instala, con `fuentes usar repo`—. Es idempotente: repetirlo sin haber tocado
    nada no escribe de nuevo ni duplica el repo en la config, que es lo que deja correrlo sin
    mirar primero si ya se hizo.

    El esqueleto es el de la 1.2: `tareas.md`, `proyecto.md` y una carpeta por cada tipo del
    almacén (`almacen.TIPOS`). Solo se crea lo que falta; lo que ya existe no se toca.

    Con `--repo` sobre una carpeta que no existe o que no es un repo, la crea y le hace
    `git init` (`"git_init": true` en el JSON; sin commits, y lo que ya hubiera dentro queda
    como está). Sin `--repo` y fuera de un repo sigue siendo un error: hacer `git init` en la
    carpeta actual por sorpresa (el home, por ejemplo) sería peor; se pide `--repo .`.
    """
    git_init = False
    if args.repo:
        destino = Path(args.repo).expanduser()
        if destino.exists() and not destino.is_dir():
            raise ErrorCLI(f"«{args.repo}» es un archivo, no una carpeta",
                           "Pasa en --repo la carpeta del proyecto (existente o nueva). "
                           "No se escribió nada.")
        nueva = not destino.exists()
        raiz = None if nueva else _raiz_git(destino)
        if raiz is None:
            # Carpeta que no existe o sin git: se crea y se le hace `git init`, sin commits y
            # sin tocar lo que ya tuviera dentro. Una carpeta nueva es siempre su propio repo,
            # aunque cuelgue de otro.
            raiz = _iniciar_repo(destino)
            git_init = True
    else:
        raiz = _raiz_git(Path.cwd())
        if raiz is None and shutil.which("git") is None:
            # `init --repo .` necesita git: sugerirlo sin decir que falta sería mandarle a
            # otro error.
            raise ErrorCLI("No encuentro git",
                           "Cotejo trabaja sobre repos de git y no hay git en esta máquina: "
                           "instálalo y luego `cotejo init --repo .`. No se escribió nada.")
        if raiz is None:
            raise ErrorCLI("No estás dentro de un repo git",
                           "Para empezar un proyecto aquí: `cotejo init --repo .` (hace "
                           "`git init`), o `--repo <carpeta>` para una nueva.")

    carpeta = raiz / CARPETA_COTEJO
    archivo_tareas = carpeta / ARCHIVO_TAREAS
    creados = []
    if not archivo_tareas.is_file():
        carpeta.mkdir(exist_ok=True)
        archivo_tareas.write_text("# Tareas\n", encoding="utf-8")
        creados.append(ARCHIVO_TAREAS)
    # El resto del almacén (v1.2). `proyecto.md` lo escribe el almacén, que nunca pisa uno que
    # ya exista; si falla por otra cosa (permisos, disco), que se vea: un «Listo» sin él
    # mandaría a los verbos del almacén contra un esqueleto a medias.
    if not (carpeta / ARCHIVO_PROYECTO).is_file():
        Almacen(raiz).crear("proyecto", raiz.name)
        creados.append(ARCHIVO_PROYECTO)
    # Las carpetas salen de `TIPOS`, no de una lista aquí: un tipo nuevo del almacén tiene su
    # carpeta en el siguiente `init` sin tocar esto. Con `.gitkeep` porque git no guarda
    # carpetas vacías, y una que no viaja con el repo no existe para el siguiente que lo clone.
    for tipo in TIPOS.values():
        if tipo.carpeta and not (carpeta / tipo.carpeta).is_dir():
            (carpeta / tipo.carpeta).mkdir(parents=True)
            (carpeta / tipo.carpeta / ".gitkeep").touch()
            creados.append(f"{tipo.carpeta}/")
    tareas_creado = ARCHIVO_TAREAS in creados
    # `version:` en proyecto.md (v1.2.4): también la pone a un proyecto de antes que no la tenía.
    version = _version.asegurar(raiz)
    # Creado desde el Inicio (`COTEJO_ORIGEN=inicio`, lo lleva el agente que lo prepara): la
    # marca va antes del commit inicial, para que viaje con el repo.
    del_inicio = origen.marcar_si_viene_del_inicio(raiz)

    datos = _config_o_error()
    cambio_config = False
    fuente_activa_antes = configuracion.fuente_activa(datos)
    if not _repo_registrado(raiz, datos):
        fuentes = dict(datos.get("fuentes") or {})
        params = dict(fuentes.get("repo") or {})
        repos = [r for r in (params.get("repos") or []) if isinstance(r, str) and r.strip()]
        params["repos"] = [*repos, str(raiz)]
        fuentes["repo"] = params
        datos = {**datos, "fuentes": fuentes}
        ruta_config = configuracion.guardar(datos)
        cambio_config = True
    else:
        ruta_config = configuracion.ruta()

    # Si la fuente activa no está configurada o no funciona, activar "repo"
    fuente_activa_ahora = configuracion.fuente_activa(datos)
    diagnostico = diagnosticar(fuente_activa_ahora, datos)
    cambio_fuente = False
    if not diagnostico["ok"]:
        # La fuente activa no funciona; activar "repo"
        datos_actualizado = {**datos, "fuente": "repo"}
        ruta_config = configuracion.guardar(datos_actualizado)
        fuente_activa_ahora = "repo"
        cambio_fuente = True
        cambio_config = True

    identidad = _asegurar_identidad(raiz)
    commit, aviso_commit = _commit_inicial(raiz)
    cambio = git_init or bool(identidad) or bool(commit) or bool(creados) or cambio_config or version["hecho"] == "puesta" or del_inicio
    if cambio_fuente:
        salida = f"Listo. La fuente activa ha cambiado a «repo» (la anterior «{fuente_activa_antes}» no funciona)."
    elif cambio:
        if fuente_activa_ahora == "repo":
            salida = "Listo. `fuentes usar repo` para leer las tareas de este repo."
        else:
            salida = f"Listo. La fuente activa sigue siendo «{fuente_activa_ahora}» (funciona bien)."
    else:
        salida = "Ya estaba. `fuentes probar repo` para comprobar que se lee bien."

    if commit:
        salida += f" Commit inicial {commit} con `.cotejo/`."
    if aviso_commit:
        salida += " " + aviso_commit
    # `creado` es el de siempre (solo `tareas.md`) y no se le cambia el sentido; lo nuevo va en
    # `creados`, con lo que esta vez se creó, vacío si ya estaba todo.
    bitacora.anotar_verbo("init", raiz, git_init=git_init, creados=len(creados))
    imprimir({"esquema": ESQUEMA, "repo": str(raiz), "tareas": str(archivo_tareas),
              "creado": tareas_creado, "creados": creados, "git_init": git_init, "commit": commit,
              "identidad": identidad,
              "version": version, "del_inicio": origen.es_del_inicio(raiz),
              "registrado_en": str(ruta_config),
              "cambio": cambio, "salida": salida})
    return 0


def _pista_repo_actual(nombre_activa, datos):
    """El aviso de `doctor` sobre el repo donde se para, para que `init` no parezca que no
    hizo nada cuando la fuente activa sigue siendo otra (lo normal justo después de usarlo).

    Dos casos, y nunca los dos a la vez porque dependen del mismo `registrado`:
    - Ya está en la fuente «repo» pero esa no es la activa → el siguiente paso es activarla.
    - Tiene `.cotejo/tareas.md` pero nadie lo registró → el siguiente paso es `cotejo init`.
    Ninguno de los dos es un error: no toca `ok`, solo se dice en «avisos» y, si todo lo
    demás está bien, también en «salida».
    """
    raiz = _raiz_git(Path.cwd())
    if raiz is None:
        return []
    registrado = _repo_registrado(raiz, datos)
    if _version.falta(raiz):
        return [f"El proyecto de este repo ({raiz}) existe pero {ARCHIVO_PROYECTO} no tiene "
               f"`version:`. `cotejo init` la pone (la siguiente de parche del último tag, o "
               f"0.1.0) sin tocar lo demás."]
    if registrado and nombre_activa != "repo":
        return [f"Este repo ({raiz}) ya está en la fuente «repo», pero la activa es "
               f"«{nombre_activa}». `cotejo fuentes usar repo` para leer sus tareas desde aquí."]
    archivo = raiz / CARPETA_COTEJO / ARCHIVO_TAREAS
    if archivo.is_file() and not registrado:
        return [f"Este repo tiene {CARPETA_COTEJO}/{ARCHIVO_TAREAS} pero no está registrado "
               f"en la fuente «repo». `cotejo init` para registrarlo."]
    return []


# --- doctor -------------------------------------------------------------------


def cmd_doctor(args):
    """Una llamada que contesta «¿funciona?, y si no, qué hago»."""
    errores, avisos = configuracion.validar(set(f.FUENTES))
    datos = configuracion.cargar()
    nombre = configuracion.fuente_activa(datos)
    try:
        fuente = diagnosticar(nombre, datos)
    except ErrorCLI as error:
        fuente = {"nombre": nombre, "ok": False, "problema": error.mensaje}
    ok = not errores and fuente["ok"]
    # El repo donde se para `doctor`, si es uno que la fuente «repo» conoce (o podría): no
    # cambia `ok` porque no es un error, es la pista que falta cuando `init` dejó todo listo
    # pero la fuente activa sigue siendo otra.
    pista_repo = _pista_repo_actual(nombre, datos)
    # Lo del $HOME de esta persona con un paquete del sistema. No cambia `ok`: sin el widget o
    # sin el protocolo, Cotejo funciona igual; se dice para que no se quede sin poner.
    de_usuario = usuario.revisar()
    # Sin ningún agente de terminal Cotejo funciona (no hay maestro ni despacho): aviso, no fallo.
    from enrutador import clientes
    sin_agentes = clientes.aviso_sin_agentes()

    if errores:
        salida = "Arregla la config: los errores de arriba dicen qué y dónde."
    elif not fuente["ok"]:
        # Si hay una pista del repo (init sin registrar, o repo sin activar), primero eso
        if pista_repo:
            salida = pista_repo[0]
        else:
            salida = fuente.get("salida") or (f"Arregla la fuente «{nombre}» (`fuentes info {nombre}` "
                                              f"dice qué pide) o cambia de fuente con `fuentes usar`.")
            if pista := f.pista_otra_fuente(nombre):
                salida = f"{salida} {pista}"
    elif ok and pista_repo:
        salida = "Funciona. " + pista_repo[0]
    elif ok and de_usuario.get("avisos"):
        salida = "Funciona. " + de_usuario["avisos"][0]
    elif ok and sin_agentes:
        salida = "Funciona. " + sin_agentes
    else:
        salida = "Todo en orden. `tareas` para ver qué hay."

    datos_salida = {"esquema": ESQUEMA, "ok": ok, "version": __version__,
                    "config": {"ruta": str(configuracion.ruta()),
                               "existe": configuracion.ruta().exists(),
                               "errores": errores, "avisos": avisos},
                    "fuente": fuente, "salida": salida}
    datos_salida["agentes"] = {"instalados": clientes.instalados()}
    if pista_repo or sin_agentes:
        datos_salida["avisos"] = list(pista_repo) + ([sin_agentes] if sin_agentes else [])
    if de_usuario.get("aplica"):
        datos_salida["usuario"] = de_usuario
    imprimir(datos_salida)
    return 0 if ok else 3


# --- fuentes ------------------------------------------------------------------


def cmd_fuentes(args):
    """Las que hay: las de fábrica y las registradas. No lanza ningún adaptador."""
    datos = configuracion.cargar()
    activa = configuracion.fuente_activa(datos)
    salida = []
    for nombre in sorted(set(f.FUENTES) | set(configuracion.registradas(datos)) | {activa}):
        params = configuracion.parametros(datos, nombre)
        try:
            fuente = f.abrir({**params, "fuente": nombre})
            uno = {"nombre": nombre, "tipo": fuente.tipo, "activa": nombre == activa,
                   "problema": fuente.problema}
        except ValueError as error:
            uno = {"nombre": nombre, "tipo": "?", "activa": nombre == activa,
                   "problema": str(error)}
        if params.get("comando"):
            uno["comando"] = params["comando"]
        salida.append(uno)
    imprimir({"esquema": ESQUEMA, "activa": activa, "fuentes": salida,
              "nota_para_el_agente": "Los problemas de aquí son los que se ven sin conectarse. "
                                     "`fuentes probar <nombre>` la conecta de verdad."})
    return 0


def _protocolo_de(comando, nombre, params):
    """Lo que un adaptador dice de sí mismo, o el error de no poder preguntárselo."""
    from .fuentes.externa import Externa
    fuente = Externa(nombre, {**params, "comando": comando})
    if fuente.problema:
        return None, fuente.problema
    try:
        return fuente.llamar("protocolo"), None
    except (modelo.FuenteNoResponde, NotImplementedError, modelo.TareaCambiada,
            modelo.NoSeCreaAqui) as error:
        return None, str(error)


def cmd_fuentes_info(args):
    """Qué pide una fuente para funcionar, dicho por ella misma."""
    datos = configuracion.cargar()
    nombre = args.nombre
    registradas = configuracion.registradas(datos)
    info = {"esquema": ESQUEMA, "nombre": nombre,
            "activa": nombre == configuracion.fuente_activa(datos),
            "registrada": nombre in f.FUENTES or nombre in registradas}
    clase = f.clase_de(nombre)
    if clase is not None:
        info.update(tipo="built-in", parametros=clase.parametros,
                    ejemplo={"fuentes": {nombre: clase.config_inicial()}})
    else:
        from .fuentes.externa import Externa
        params = registradas.get(nombre, {})
        # Por convención un adaptador se llama `cotejo-<nombre>`: así se puede preguntar por uno
        # instalado antes de registrarlo, que es justo cuando hace falta saber qué pide. Los que
        # se instalaron cuando esto se llamaba Foco se llaman `foco-<nombre>`.
        comando = params.get("comando") or next(
            (c for c in (f"cotejo-{nombre}", f"foco-{nombre}") if shutil.which(c)), None)
        if comando is None:
            raise ErrorCLI(
                f"No conozco la fuente «{nombre}» ni encuentro un «cotejo-{nombre}» instalado",
                f"Si tienes su adaptador, regístralo con `fuentes agregar {nombre} --comando "
                f"<ejecutable>`. `fuentes` lista las que hay.")
        protocolo, problema = _protocolo_de(comando, nombre, params)
        info.update(tipo="externa", comando=comando,
                    parametros={**Externa.parametros, **((protocolo or {}).get("parametros") or {})})
        if protocolo:
            info["protocolo"] = protocolo
            if protocolo.get("ejemplo"):
                info["ejemplo"] = {"fuentes": {nombre: protocolo["ejemplo"]}}
        if problema:
            info["problema"] = problema
        if nombre not in registradas:
            info["como_registrarla"] = (f"cotejo fuentes agregar {nombre} --comando {comando} "
                                        f"--param <clave>=<valor> ...")
    if nombre in f.FUENTES or nombre in registradas:
        info["config"] = configuracion.parametros(datos, nombre)
    imprimir(info)
    return 0


def cmd_fuentes_probar(args):
    """La conecta y la lee. No escribe nada, ni en ella ni en la config."""
    datos = configuracion.cargar()
    if not _conocida(args.nombre, datos):
        raise ErrorCLI(f"No hay ninguna fuente «{args.nombre}»",
                       f"Regístrala antes con `fuentes agregar {args.nombre} --comando ...`.")
    informe = diagnosticar(args.nombre, datos)
    salida = ("Funciona. `fuentes usar " + args.nombre + "` para activarla."
              if informe["ok"] else
              informe.get("salida") or f"`fuentes info {args.nombre}` dice qué parámetros pide.")
    imprimir({"esquema": ESQUEMA, **informe, "salida": salida})
    return 0 if informe["ok"] else 3


def cmd_fuentes_usar(args):
    """Cambia la fuente activa, solo si responde: activar una rota deja al board sin tareas."""
    datos = _config_o_error()
    nombre = args.nombre
    if not _conocida(nombre, datos):
        raise ErrorCLI(f"No hay ninguna fuente «{nombre}»",
                       f"Regístrala antes con `fuentes agregar {nombre} --comando ...`.")
    if configuracion.fuente_de_config(datos) == nombre:
        imprimir({"esquema": ESQUEMA, "cambio": False, "activa": nombre})
        return 0
    informe = diagnosticar(nombre, datos)
    if not informe["ok"]:
        raise ErrorCLI(f"«{nombre}» no funciona todavía: {informe.get('problema')}",
                       informe.get("salida") or "Arréglala y repite; la activa sigue siendo la "
                                                "de antes.")
    ruta = configuracion.guardar({**datos, "fuente": nombre})
    respuesta = {"esquema": ESQUEMA, "cambio": True, "activa": nombre, "ruta": str(ruta),
                 "proyectos": informe["proyectos"], "pendientes": informe["pendientes"]}
    if configuracion.fuente_activa(datos) != configuracion.fuente_de_config(datos):
        respuesta["avisos"] = ["COTEJO_FUENTE está definida y manda sobre la config mientras siga "
                               "definida."]
    imprimir(respuesta)
    return 0


def _parametro(texto):
    clave, igual, valor = texto.partition("=")
    clave = clave.strip()
    if not igual or not clave:
        raise ErrorCLI(f"«{texto}» no es un parámetro", "Se escriben como --param clave=valor.")
    if clave in RESERVADAS:
        raise ErrorCLI(f"«{clave}» no se pasa como parámetro", "Lo pone Cotejo: usa --comando.")
    if configuracion.parece_secreto(clave):
        raise ErrorCLI(
            f"«{clave}» parece un secreto, y la config no guarda secretos",
            "Déjalo en una variable de entorno y pasa su nombre: --param token_env=NOMBRE. "
            "No se escribió nada.")
    # Listas y objetos se escriben en JSON (`database_ids=["a","b"]`); lo demás es texto tal
    # cual, para que un id que parezca un número no pierda sus ceros de delante.
    if valor[:1] in "[{" or valor in ("true", "false"):
        try:
            valor = json.loads(valor)
        except ValueError as error:
            raise ErrorCLI(f"El valor de «{clave}» no es JSON válido: {error}",
                           "Revisa comillas y corchetes.") from error
    return clave, valor


def cmd_fuentes_agregar(args):
    """Registra un adaptador externo. No lo activa: primero se prueba."""
    nombre = args.nombre
    if not NOMBRE_RE.match(nombre):
        raise ErrorCLI(f"«{nombre}» no sirve de nombre", "Minúsculas, números, guion o guion bajo.")
    if nombre in f.FUENTES:
        raise ErrorCLI(f"«{nombre}» es una fuente de fábrica",
                       f"Sus parámetros se cambian en la config; `fuentes info {nombre}` dice cuáles.")
    params = dict(_parametro(p) for p in args.param or [])
    datos = _config_o_error()
    entrada = {"tipo": "externa", "comando": args.comando, **params}
    fuentes = dict(datos.get("fuentes") or {})
    if fuentes.get(nombre) == entrada:
        imprimir({"esquema": ESQUEMA, "cambio": False, "fuente": {nombre: entrada}})
        return 0
    fuentes[nombre] = entrada
    ruta = configuracion.guardar({**datos, "fuentes": fuentes})
    respuesta = {"esquema": ESQUEMA, "cambio": True, "fuente": {nombre: entrada},
                 "ruta": str(ruta),
                 "nota_para_el_agente": f"Registrada, no activa. `fuentes probar {nombre}` y, si "
                                        f"responde, `fuentes usar {nombre}`."}
    if shutil.which(args.comando.split()[0] if args.comando.strip() else "") is None:
        respuesta["avisos"] = [f"No encuentro «{args.comando}» en el PATH; `probar` fallará "
                               f"hasta que esté."]
    imprimir(respuesta)
    return 0


def cmd_fuentes_quitar(args):
    """La desregistra. Lo que haya en la app de fuera no se toca."""
    datos = _config_o_error()
    nombre = args.nombre
    if nombre in f.FUENTES:
        raise ErrorCLI(f"«{nombre}» es de fábrica y no se quita", "Cambia de fuente con `fuentes usar`.")
    if datos.get("fuente") == nombre:
        raise ErrorCLI(f"«{nombre}» es la fuente activa",
                       "Activa otra antes con `fuentes usar <otra>`. No se escribió nada.")
    fuentes = dict(datos.get("fuentes") or {})
    if nombre not in fuentes:
        imprimir({"esquema": ESQUEMA, "cambio": False, "quitada": nombre})
        return 0
    del fuentes[nombre]
    ruta = configuracion.guardar({**datos, "fuentes": fuentes})
    imprimir({"esquema": ESQUEMA, "cambio": True, "quitada": nombre, "ruta": str(ruta)})
    return 0


# --- config init | validar ----------------------------------------------------------


EXPLICACION = {
    "fuente": "De dónde lee Cotejo las tareas. `fuentes` lista las que hay.",
    "fuentes": "Los parámetros de cada fuente, por nombre. `fuentes info <nombre>` dice cuáles pide.",
    "enrutador": "Ajustes de quién atiende cada tarea (modelos, motores, reglas). Opcional.",
    "tema": "Los colores de CotejoBoard, por id. `temas` lista los que hay. Opcional: oscuro.",
}


def config_init():
    destino = configuracion.ruta()
    if destino == configuracion.legado() and destino.exists():
        # El archivo viejo: se pasa al nuevo y se aparta, para que no queden dos vivos.
        viejo = _config_o_error()
        nuevo = configuracion.migrar(viejo)
        ruta = configuracion.guardar(nuevo, configuracion.nueva())
        apartado = destino.with_suffix(".json.migrado")
        destino.rename(apartado)
        imprimir({"esquema": ESQUEMA, "cambio": True, "ruta": str(ruta),
                  "migrado_de": str(destino), "original_en": str(apartado),
                  "config": nuevo, "explicacion": EXPLICACION})
        return 0
    if destino.exists():
        imprimir({"esquema": ESQUEMA, "cambio": False, "ruta": str(destino),
                  "salida": "Ya existe; no se toca. `config validar` dice si está bien."})
        return 0
    # Obsidian solo si hay un vault que existe de verdad (v1.2.5); si no, la fuente es el repo,
    # que es la que funciona sin nada instalado. Escribir «obsidian» con el vault vacío dejaba a
    # quien no usa Obsidian con una fuente que no sirve.
    elegida = "obsidian" if vault_valido() else configuracion.DEFECTO_NUEVO
    clase = f.clase_de(elegida)
    nuevo = {"fuente": elegida, "fuentes": {elegida: clase.config_inicial() if clase else {}}}
    ruta = configuracion.guardar(nuevo, destino)
    imprimir({"esquema": ESQUEMA, "cambio": True, "ruta": str(ruta), "config": nuevo,
              "explicacion": {**EXPLICACION,
                              **{f"fuentes.{elegida}.{k}": v
                                 for k, v in (clase.parametros if clase else {}).items()}}})
    return 0


def config_validar():
    errores, avisos = configuracion.validar(set(f.FUENTES))
    imprimir({"esquema": ESQUEMA, "ok": not errores, "ruta": str(configuracion.ruta()),
              "errores": errores, "avisos": avisos})
    return 0 if not errores else 3


# --- los verbos, colgados del analizador de Cotejo -----------------------------


def anadir(sub):
    init = sub.add_parser(
        "init", help="Dentro de un repo git: crea .cotejo/tareas.md y lo registra en «repo»")
    init.add_argument("--repo", metavar="CARPETA",
                      help="El repo a preparar. Por defecto, la carpeta actual")
    init.set_defaults(funcion=cmd_init)

    doctor = sub.add_parser("doctor", help="¿Funciona?, y si no, qué hacer. Config y fuente activa")
    doctor.set_defaults(funcion=cmd_doctor)

    fuentes = sub.add_parser("fuentes", help="De dónde lee Cotejo: las que hay y cuál está activa")
    fuentes.set_defaults(funcion=cmd_fuentes)
    acciones = fuentes.add_subparsers(dest="accion")

    info = acciones.add_parser("info", help="Qué parámetros pide una fuente y cómo se registra")
    info.add_argument("nombre")
    info.set_defaults(funcion=cmd_fuentes_info)

    probar = acciones.add_parser("probar", help="Conectarla y leerla, sin escribir ni activarla")
    probar.add_argument("nombre")
    probar.set_defaults(funcion=cmd_fuentes_probar)

    usar = acciones.add_parser("usar", help="Activarla (solo si `probar` pasa)")
    usar.add_argument("nombre")
    usar.set_defaults(funcion=cmd_fuentes_usar)

    agregar = acciones.add_parser("agregar", help="Registrar un adaptador externo")
    agregar.add_argument("nombre")
    agregar.add_argument("--comando", required=True, help="El ejecutable: cotejo-notion, o una ruta")
    agregar.add_argument("--param", action="append", metavar="CLAVE=VALOR",
                         help="Un parámetro de la fuente; se repite. Sin secretos: token_env=NOMBRE")
    agregar.set_defaults(funcion=cmd_fuentes_agregar)

    quitar = acciones.add_parser("quitar", help="Desregistrarla; no borra nada de su app")
    quitar.add_argument("nombre")
    quitar.set_defaults(funcion=cmd_fuentes_quitar)
