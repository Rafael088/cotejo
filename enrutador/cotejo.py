"""Las tareas de Cotejo, vistas desde el enrutador. El vault se lee una vez por invocación.

Este adaptador existía cuando el enrutador era otro programa: hablaba con Cotejo por su CLI, en
un subproceso, y las tres razones para hacerlo así eran que Cotejo se iba a compilar, que su CLI
ya era el contrato y que el enrutador no merecía privilegios que un agente no tuviera. Las tres
se evaporaron el día que los dos pasaron a ser el mismo comando: un programa no se llama a sí
mismo por subproceso para preguntarse algo que sabe.

Lo que **no** se evaporó es la costura, y por eso el archivo sigue aquí. Decidir, planear y
despachar siguen hablando con este objeto y no con la fuente, así que el día que las tareas
vengan de otro sitio se cambia esto y nada más. Por dentro llama a las mismas funciones que
usan los verbos de Cotejo —`cargar`, `tomar_tarea`, `tomar_para`—, que es lo que garantiza que
el enrutador escriba en el vault exactamente igual que un agente: verificado y atómico.

Lo que ganó la mudanza se ve en `plan`: antes eran 68 tareas pedidas por subproceso, una lista
entera vuelta a pedir por cada tarea que se despachaba. Ahora el vault se escanea una vez y de
ahí salen todas las respuestas.
"""

from pathlib import Path

from tareas import bitacora as bitacora_cotejo, cli as cotejo


class Cotejo:
    """Las tareas del vault, cargadas perezosamente y una sola vez."""

    def __init__(self):
        self.avisos = []
        self._abierto = None

    def _abrir(self):
        if self._abierto is None:
            fuente, proyectos, avisos = cotejo.cargar()
            for aviso in avisos:
                if aviso not in self.avisos:
                    self.avisos.append(aviso)
            self._abierto = (fuente, proyectos)
        return self._abierto

    def _olvidar(self):
        """Tras escribir, lo cargado ya no describe el vault: se vuelve a leer si hace falta."""
        self._abierto = None

    # --- lo que se le pide ---------------------------------------------------

    def disponible(self):
        try:
            self._abrir()
            return True
        except cotejo.ErrorCLI:
            return False

    def proyectos(self):
        """Los nombres de los proyectos, en el orden en que los da la fuente."""
        _, proyectos = self._abrir()
        return [uno.nombre for uno in proyectos]

    def tareas(self, proyecto=None, estado=None):
        _, proyectos = self._abrir()
        ultimas = bitacora_cotejo.ultimas()
        salida = []
        for uno in proyectos:
            if proyecto and proyecto.lower() not in uno.nombre.lower():
                continue
            for tarea in list(uno.tareas) + list(uno.hechas):
                if estado and tarea.columna != estado:
                    continue
                salida.append(cotejo.como_json(tarea, uno, ultimas.get(tarea.id)))
        return salida

    def tarea(self, tarea_id):
        """Una tarea por su id, con el mismo trato que le daría cualquier verbo de Cotejo.

        Un id ambiguo o inexistente sale por donde sale siempre: con el error que ya escribió
        Cotejo para un agente, sin traducirlo por el camino.
        """
        fuente, proyectos = self._abrir()
        proyecto, tarea = cotejo.tomar_tarea(fuente, proyectos, tarea_id)
        return cotejo.como_json(tarea, proyecto, bitacora_cotejo.ultimas().get(tarea.id))

    def tomar(self, tarea_id, agente):
        """Toma la tarea a nombre del modelo elegido. Devuelve la tarea como quedó."""
        fuente, proyectos = self._abrir()
        proyecto, tarea = cotejo.tomar_tarea(fuente, proyectos, tarea_id)
        actual, _ = cotejo.tomar_para(fuente, proyecto, tarea, agente)
        self._olvidar()
        return cotejo.como_json(actual, proyecto, bitacora_cotejo.ultimas().get(actual.id))

    def soltar(self, tarea_id, motivo, agente=None, asignada=""):
        """Deshace un `tomar` de este mismo despacho: pendiente, sin dueño y con el motivo.

        Solo para cuando lo que venía después de tomarla falló —crear su worktree, o el cliente
        que tenía que hacerla—: dejarla «Haciéndola» a nombre de un modelo que nunca empezó es
        justo lo que `despachar` evita comprobando el motor antes de tomar. El motivo va a la
        bitácora, como el de `bloquear`, para que quien la vea en Pendiente sepa por qué volvió.

        Con `agente`, solo la suelta si sigue «Haciéndola» a su nombre: un cliente que falla al
        salir puede haberla entregado o bloqueado antes, y eso no se pisa. `asignada` es el
        agente que tenía en Pendiente antes de tomarla (el `#agente/sonnet` que puso una
        persona): un despacho fallido no le quita la asignación. Devuelve si la soltó.
        """
        fuente, proyectos = self._abrir()
        proyecto, tarea = cotejo.tomar_tarea(fuente, proyectos, tarea_id)
        if agente is not None and (tarea.columna != "en-curso" or tarea.agente != agente):
            return False
        quien = tarea.agente
        actual = cotejo.escribir(fuente.poner_estado, tarea, "pendiente")
        actual = cotejo.escribir(fuente.poner_agente, actual, asignada or "")
        bitacora_cotejo.anotar("soltar", proyecto, actual, de="en-curso", a="pendiente",
                               agente=quien, motivo=motivo)
        self._olvidar()
        return True

    def carpeta_de(self, proyecto):
        """La carpeta del proyecto según la fuente (en la de repos, el repo), o None."""
        fuente, _ = self._abrir()
        return fuente.carpeta_de(proyecto)

    def agente_del_proyecto(self, proyecto, config=None):
        """El agente con el que se creó el proyecto (`origen.agente_de` sobre su carpeta), o ""
        si no lo dice o no tiene carpeta: entonces se propone con Claude (cotejo-qixs4j)."""
        if not proyecto:
            return ""
        cache = self.__dict__.setdefault("_agentes", {})
        if proyecto not in cache:
            from tareas import origen
            from . import config as cfg
            try:
                carpeta = ((cfg.directorio_de(config, proyecto) if config else None)
                           or self.carpeta_de(proyecto))
            except Exception:  # noqa: BLE001 - sin carpeta se propone como siempre
                carpeta = None
            cache[proyecto] = origen.agente_de(carpeta) if carpeta else ""
        return cache[proyecto]

    def carpeta_de_la_tarea(self, tarea_id):
        """La carpeta local donde la fuente escribe esta tarea (el `.cotejo/` de su repo, o la
        carpeta de su nota en el vault), o None si no vive en un archivo de esta máquina (una
        fuente externa). Es donde escribe `cotejo entregar`, y el sandbox del agente del board
        tiene que dejarle (cotejo-amui0f)."""
        fuente, proyectos = self._abrir()
        try:
            _, tarea = cotejo.tomar_tarea(fuente, proyectos, tarea_id)
        except cotejo.ErrorCLI:
            return None
        duena = fuente._duena(tarea.donde) if hasattr(fuente, "_duena") else fuente
        archivo = getattr(duena, "_archivo", None)
        if archivo is None or not tarea.donde:
            return None
        try:
            carpeta = Path(archivo(tarea.donde)).parent
        except (FileNotFoundError, ValueError, TypeError):
            return None
        return carpeta if carpeta.is_dir() else None

    def carpetas_propias(self):
        """Dónde guarda la fuente sus notas: ningún worktree puede caer ahí dentro."""
        fuente, _ = self._abrir()
        return fuente.carpetas_propias()
