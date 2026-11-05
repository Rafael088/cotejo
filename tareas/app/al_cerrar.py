"""Cerrar el board con agentes trabajando: preguntar antes, y no quedarse vivo sin ventana
(cotejo-qtegjk).

Antes, cerrar la ventana solo la ocultaba y los agentes lanzados desde el board seguían en lo
suyo sin que nadie lo dijera. En Linux eso es lo que se quiere (el proceso sigue para el widget
de la barra, que es quien vuelve a abrir el board), pero en Windows no hay barra: el
`pythonw.exe` se quedaba vivo, sin ventana, con su `cotejoboard.exe` y los agentes colgando de
él.

Ahora, si hay agentes trabajando en esta máquina, cerrar pregunta lo mismo en los dos sistemas:

- **Pararlos**: cada uno se para con su árbol entero (`procesos.terminar`) y su tarea vuelve a
  Pendiente pausada, igual que al arrastrarla allí (`despacho_board.pausar`): el worktree, la
  rama y el modelo se quedan para retomarla.
- **Dejarlos trabajando**: siguen. El fin que hace el board cuando vuelven lo hace `recoger` al
  abrirlo otra vez (si en Linux el proceso sigue vivo, lo hace su hilo de siempre).
- **Cancelar** (o Escape): la ventana no se cierra.

Y en Windows, después de cerrar, la app sale (`sale_al_cerrar`). Las pruebas cambian la
pregunta por una respuesta (`preguntar_al_cerrar`), como el humo de Windows.
"""

import socket
import sys

from gi.repository import Adw, GLib

from .. import bitacora, lanzados, modelo
from .comun import id_corto

PARAR, DEJAR, CANCELAR = "parar", "dejar", "cancelar"
MOTIVO = "se cerró el board y pediste pararlo"
EN_CURSO = "en-curso"


def sale_al_cerrar():
    """¿Cerrar la ventana termina el proceso? En Windows sí: allí no hay widget de barra que
    vuelva a abrir el board, y un `pythonw.exe` sin ventana no lo ve nadie."""
    return sys.platform == "win32"


def agentes_vivos():
    """Los registros de los agentes que el board lanzó y siguen trabajando en esta máquina."""
    host = socket.gethostname()
    vivos = []
    for registro in lanzados.todos().values():
        if registro.get("fase") != lanzados.LANZADO:
            continue
        if registro.get("host") and registro["host"] != host:
            continue
        if (lanzados.estado(registro) or {}).get("estado") == lanzados.TRABAJANDO:
            vivos.append(registro)
    return sorted(vivos, key=lambda r: r.get("ts") or 0)


def pregunta(vivos):
    """El título y el cuerpo de la pregunta, en llano."""
    if len(vivos) == 1:
        titulo = f"{vivos[0].get('modelo') or 'Un agente'} sigue trabajando"
    else:
        titulo = f"Hay {len(vivos)} agentes trabajando"
    lineas = [f"· {r.get('modelo') or 'agente'}: {r.get('texto') or id_corto(r.get('id'))}"
              for r in vivos[:5]]
    if len(vivos) > 5:
        lineas.append(f"· y {len(vivos) - 5} más")
    seguir = ("Si los dejas, siguen aunque Cotejo se cierre: al volver a abrirlo verás cómo "
              "acabaron." if sale_al_cerrar() else
              "Si los dejas, siguen aunque no veas el board.")
    cuerpo = ("\n".join(lineas) + "\n\nSi los paras, sus tareas vuelven a Pendiente pausadas: "
              "el worktree y la rama se quedan para retomarlas. " + seguir)
    return titulo, cuerpo


class AlCerrar:
    """Los métodos de `Board` para cerrar su ventana."""

    def poner_al_cerrar(self):
        # Se conecta antes que los demás «close-request» (`VerApp` para las apps al cerrar): si
        # la persona cancela, no se ha parado nada.
        self.cierre_decidido = False
        self.pregunta_cierre = None
        self.connect("close-request", self.al_pedir_cierre)

    def al_pedir_cierre(self, *_args):
        if self.pregunta_cierre is not None:
            return True   # ya se está preguntando
        if not self.cierre_decidido:
            vivos = agentes_vivos()
            if vivos:
                self.pregunta_cierre = self.preguntar_al_cerrar(vivos)
                return True   # la ventana se queda hasta que conteste
        self.cierre_decidido = False
        if sale_al_cerrar():
            GLib.idle_add(self.salir_de_la_app)
        return False

    def preguntar_al_cerrar(self, vivos):
        """Pregunta qué hacer con `vivos` y, al contestar, llama `al_responder_cierre`. Devuelve
        el diálogo (las pruebas y el humo la cambian por una respuesta directa)."""
        titulo, cuerpo = pregunta(vivos)
        dialogo = Adw.AlertDialog(heading=titulo, body=cuerpo)
        dialogo.add_response(CANCELAR, "Cancelar")
        dialogo.add_response(DEJAR, "Dejarlos trabajando")
        dialogo.add_response(PARAR, "Pararlos")
        dialogo.set_response_appearance(PARAR, Adw.ResponseAppearance.DESTRUCTIVE)
        dialogo.set_default_response(DEJAR)
        dialogo.set_close_response(CANCELAR)
        # Se actúa cuando el diálogo ya se fue («closed»), no en «response»: con el diálogo aún
        # puesto, cerrar la ventana solo cerraría el diálogo.
        dialogo.respuesta = CANCELAR
        dialogo.connect("response", lambda d, respuesta: setattr(d, "respuesta", respuesta))
        dialogo.connect("closed", lambda d: self.al_responder_cierre(d.respuesta, vivos))
        dialogo.present(self)
        return dialogo

    def al_responder_cierre(self, respuesta, vivos):
        self.pregunta_cierre = None
        if respuesta not in (PARAR, DEJAR):
            return
        if respuesta == PARAR:
            self.parar_agentes(vivos)
        self.cierre_decidido = True
        # Fuera de la señal en curso: un `close()` desde dentro de «close-request» o con el
        # diálogo aún yéndose no cierra la ventana.
        GLib.timeout_add(20, self._cerrar_ya)

    def _cerrar_ya(self):
        # Mientras el diálogo siga puesto (se está yendo), libadwaita gasta el cierre en él.
        if self.get_visible_dialog() is not None:
            return GLib.SOURCE_CONTINUE
        self.close()
        return GLib.SOURCE_REMOVE

    def parar_agentes(self, vivos):
        """Para cada agente (con su árbol) y devuelve su tarea a Pendiente, pausada. Devuelve
        los ids que paró."""
        from enrutador import despacho_board as db
        tareas = {t.id: (p, t) for p in self.app.proyectos for t in p.tareas}
        parados = []
        for registro in vivos:
            ident = registro.get("id")
            try:
                db.pausar(ident, MOTIVO)
            except OSError as error:
                print(f"Cotejo: no pude parar {ident} ({error})", file=sys.stderr)
                continue
            parados.append(ident)
            proyecto, tarea = tareas.get(ident, (None, None))
            if tarea is None or tarea.columna != EN_CURSO:
                continue
            try:
                actual = self.fuente.poner_estado(tarea, modelo.PENDIENTE)
            except (modelo.TareaCambiada, OSError):
                continue   # cambió mientras tanto: el agente ya está parado, la línea no se pisa
            bitacora.anotar("mover", proyecto, actual, de=tarea.columna, a=modelo.PENDIENTE)
        return parados

    def salir_de_la_app(self):
        self.app.quit()
        return GLib.SOURCE_REMOVE
