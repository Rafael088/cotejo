"""De dónde salen las tareas y a dónde vuelven escritas.

Una fuente es un segundo cerebro concreto: hoy un vault de Obsidian, mañana Logseq, una carpeta
de Markdown pelada o Todoist. Todo lo que Cotejo sabe hacer con las tareas —listarlas, tomarlas,
entregarlas, marcarlas— se hace contra esta interfaz, así que añadir un segundo cerebro es
escribir un adaptador en `tareas/fuentes/`, no reescribir Cotejo ni reprogramar al agente.

Lo que una fuente tiene que garantizar, y por qué:

- **Escribir verificado.** Comprobar que la tarea sigue como cuando se leyó y levantar
  `TareaCambiada` si no, en vez de pisar lo que haya. Es el corazón del proyecto: el único
  código que toca las notas del usuario es este, y la forma de fallar es silenciosa.
- **Identificadores estables.** `tarea.id` tiene que seguir nombrando a la misma tarea entre
  una llamada del agente y la siguiente, aunque lo de alrededor se edite.
- **Devolver la tarea como quedó**, para que quien escribió no tenga que volver a preguntar.

Lo que una fuente **no** decide: qué significan las columnas, quién puede marcar una tarea como
hecha (nadie automático) ni qué se le muestra a una persona. Eso es de `modelo.py` y de la vista.
"""

from . import configuracion


class Fuente:
    """La interfaz. Una fuente nueva hereda de aquí y llena lo que le sirva.

    Los valores por defecto describen la fuente más pobre que puede existir: una que se lee y
    se escribe, pero que no vive en archivos (nada que vigilar) ni tiene una app donde abrir
    una tarea. Una fuente así funciona: el board pierde la recarga automática y el botón de
    abrir, no la capacidad de mover tareas.
    """

    nombre = ""  # cómo se la llama en la config
    tipo = "built-in"  # built-in (vive en tareas/fuentes/) o externa (un comando aparte)
    # Qué se le puede poner en la config, y para qué. Es lo que enseña `fuentes info`: un
    # agente que va a configurar una fuente no tiene por qué leer su código para saberlo.
    parametros = {}
    problema = None  # por qué no se puede usar todavía (texto para una persona), o None
    accion_abrir = "Abrir la tarea"  # cómo se llama «abrirla» en su app, para el menú
    respaldo = ()  # comando de reserva si el sistema no sabe abrir su uri

    # --- leer ---------------------------------------------------------

    def escanear(self, incluir_hechas=False, avisos=None):
        """Los proyectos con sus tareas, ya ordenados. `avisos`, si se pasa una lista, recoge
        lo que no se pudo leer: una tarea que falta porque su nota está rota se ve exactamente
        igual que una tarea que no existe, y esa diferencia hay que poder contarla."""
        raise NotImplementedError

    def normalizar_id(self, texto):
        """El id tal como lo escribe un humano, convertido al que usa la fuente."""
        return str(texto).strip()

    def leido(self, proyectos=None):
        """Cuánto pesaba, en caracteres, lo que hubo que leer en el último `escanear`.

        Es la mitad cara del medidor de ahorro (`tareas/ahorro.py`): lo que le habría costado
        al agente enterarse leyendo el segundo cerebro en vez de preguntarle a Cotejo. Se
        pregunta, no se mide aparte, justamente porque la fuente ya leyó eso para contestar y
        contar no puede costar una segunda lectura.

        Si se pasan `proyectos`, cuenta solo lo que pesaron las notas de esos proyectos —los
        que pasaron el filtro de quien llama (`tareas --proyecto`)— y no el vault entero que
        `escanear` tuvo que recorrer para encontrarlos. Sin `proyectos`, cuenta todo lo leído,
        que es lo correcto cuando tampoco hubo filtro.

        Una fuente que no vive en archivos devuelve 0, y entonces no se cuenta nada: es más
        honesto que comparar contra un cero y anunciar un ahorro infinito.
        """
        return 0

    # --- escribir -----------------------------------------------------

    def crear(self, proyecto, texto, dificultad=""):
        """Anota una tarea nueva, pendiente y sin dueño. Devuelve la tarea como quedó.

        Una fuente que sepa de versiones acepta además `version="v1.2.4"` (v1.2.4) y la guarda
        como la lee (en Obsidian, el tag `#v1.2.4`). La CLI solo la pasa si se pidió
        `--version`, así que una fuente que no la acepte sigue creando como siempre.

        Es opcional, y por eso viene levantando `NotImplementedError` en vez de siendo
        obligatoria: hay segundos cerebros donde anotar no es cosa de quien lee —una lista
        generada, un tablero ajeno de solo lectura— y obligar a todos a saber crear los
        dejaría fuera por una capacidad que no necesitan. Quien no la implemente sigue
        sirviendo para todo lo demás; la CLI lo dice con su nombre en vez de reventar.

        Si sabe crear pero no en ese proyecto, levanta `modelo.NoSeCreaAqui` con el porqué.

        Crear no es finalizar: apuntar trabajo no afirma que esté hecho, así que esto no toca
        lo que protege la ausencia de un verbo para marcar `[x]`.
        """
        raise NotImplementedError

    def marcar(self, tarea, hecha=True):
        """La transición humana. Devuelve la tarea como quedó."""
        raise NotImplementedError

    def poner_estado(self, tarea, nuevo):
        """Mover entre pendiente, en-curso y por-validar."""
        raise NotImplementedError

    def poner_agente(self, tarea, agente):
        """Asignar, o soltar con el agente vacío."""
        raise NotImplementedError

    def quitar(self, tarea):
        """Borra la tarea de su fuente si sigue igual que al leerla; si no, `TareaCambiada`.

        Es lo que usa `limpiar` (v1.2.2) con las finalizadas antiguas, después de dejar su
        rastro en la bitácora. Qué se puede borrar —solo lo que una persona ya dio por hecho—
        no lo decide la fuente: lo decide el verbo. Opcional como `crear`: una fuente que no la
        implementa sigue sirviendo para todo lo demás, y la CLI lo dice con su nombre.
        """
        raise NotImplementedError

    def fecha_cierre(self, tarea):
        """Cuándo se dio por hecha la tarea ("AAAA-MM-DD"), o None si la fuente no lo sabe.

        `Tarea.cerrada`, si el modelo la trae, gana; si no, cada fuente la lee a su manera.
        """
        return getattr(tarea, "cerrada", None)

    def asegurar_id(self, tarea):
        """Darle id a una tarea que todavía no lo tiene, sin cambiar nada más.

        Solo hace falta en fuentes donde el id se escribe (Obsidian escribe una marca de
        bloque); donde los ids ya existen, esto no es nada.
        """
        return tarea

    @classmethod
    def config_inicial(cls):
        """Los parámetros con los que `config init` la deja escrita, ya rellenos si se puede."""
        return {}

    # --- dónde vive ---------------------------------------------------

    def vigilables(self):
        """Rutas que, si cambian, quieren decir que hay que releer. Vacío si no aplica."""
        return []

    def uri(self, tarea):
        """Cómo abrir la tarea en su propia app, o "" si no hay dónde."""
        return ""

    def carpeta_de(self, proyecto):
        """La carpeta de trabajo de un proyecto si la fuente la sabe (un repo), o None.

        Es lo que deja a `despachar` saber que una tarea es de un repo de git sin que nadie lo
        escriba en `enrutador.proyectos`: en la fuente repo, el proyecto *es* el repo.
        """
        return None

    def carpetas_propias(self):
        """Dónde guarda la fuente sus notas. Nada que no sea una tarea puede caer ahí dentro
        (un worktree de despacho con `.md` metería sus casillas como tareas de verdad)."""
        return []


def cargar_config():
    """Qué fuente se usa y con qué parámetros, ya resuelto.

    Devuelve `{"fuente": <nombre>, **parámetros de esa fuente}`: cada fuente se lee sus propias
    claves y no tiene por qué saber cómo está organizado el archivo. `COTEJO_FUENTE` elige otra
    en una sola invocación, igual que `COTEJO_VAULT` en la de Obsidian. Cómo se encuentra el
    archivo y cómo se leía el formato viejo está en `tareas/configuracion.py`.
    """
    datos = configuracion.cargar()
    nombre = configuracion.fuente_activa(datos)
    return {**configuracion.parametros(datos, nombre), "fuente": nombre}


def _obsidian(config):
    # El import va aquí dentro y no arriba a propósito: así una fuente que algún día necesite
    # una librería suya no se la cobra a quien no la usa, y `abrir` sigue costando lo mismo.
    from .fuentes.obsidian import Obsidian
    # Con proyectos migrados a su repo (v1.2), el vault se lee junto con esos repos y sin esos
    # proyectos. Sin la marca, es el Obsidian de siempre: no se paga nada por no migrar.
    if config.get("migrados"):
        from .fuentes.compuesta import Compuesta
        return Compuesta(config)
    return Obsidian(config)


def _repo(config):
    from .fuentes.repo import Repo
    return Repo(config)


FUENTES = {"obsidian": _obsidian, "repo": _repo}


def clase_de(nombre):
    """La clase de una fuente de fábrica, para preguntarle qué parámetros tiene."""
    if nombre == "obsidian":
        from .fuentes.obsidian import Obsidian
        return Obsidian
    if nombre == "repo":
        from .fuentes.repo import Repo
        return Repo
    return None


def abrir(config=None):
    """La fuente que dice la config, lista para usar.

    Siempre devuelve una fuente, incluso mal configurada: en ese caso trae `problema` con qué
    le falta, que es lo que la ventana enseña y lo que la CLI convierte en error. Una fuente
    que no existe sí es un error de programa, no un estado.

    Las de fábrica se construyen desde `FUENTES`. Cualquier otra con `"tipo": "externa"` en la
    config es un comando aparte al que se le habla por subproceso (`fuentes/externa.py`): así
    se conecta Cotejo a una app nueva sin tocar este paquete.
    """
    config = cargar_config() if config is None else config
    nombre = config["fuente"]
    construir = FUENTES.get(nombre)
    if construir is not None:
        return construir(config)
    if config.get("tipo") == "externa":
        from .fuentes.externa import Externa
        return Externa(nombre, config)
    raise ValueError(
        f"No conozco la fuente «{nombre}». Las de fábrica son {', '.join(sorted(FUENTES))}, "
        f"y una externa se registra con `fuentes agregar`. Se elige con \"fuente\" en "
        f"{configuracion.ruta()}.")


def pista_otra_fuente(nombre):
    """Qué probar cuando la fuente activa `nombre` no sirve, o "" si no hay nada que sugerir.

    Con la fuente «repo» sin repos, el arranque es `cotejo init`; y si Obsidian tiene un vault
    que existe de verdad, `cotejo fuentes usar obsidian` también. Un vault que `obsidian.json`
    nombra pero ya no está en disco no cuenta: sugerirlo mandaría a otro error.
    """
    from .fuentes.obsidian import vault_valido
    pistas = []
    if nombre == "repo":
        pistas.append("`cotejo init` dentro de un repo de git (crea .cotejo/tareas.md)")
    vault = vault_valido() if nombre != "obsidian" else None
    if vault:
        pistas.append(f"`cotejo fuentes usar obsidian` (hay un vault en {vault})")
    return "Prueba " + " o ".join(pistas) + "." if pistas else ""


def problema_con_pista(fuente):
    """El `problema` de una fuente más lo que probar en su lugar (`pista_otra_fuente`)."""
    pista = pista_otra_fuente(getattr(fuente, "nombre", ""))
    return f"{fuente.problema.rstrip('.')}. {pista}" if pista else fuente.problema
