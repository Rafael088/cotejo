"""El vacío del primer arranque: sin fuente configurada, qué es Cotejo y cómo empezar.

Regla nueva (dec-hgq7, propuesta que reemplaza la del 2026-10-10; queda a la espera de que el
dueño la acepte): el board tiene una pestaña Inicio que abre primero y crea proyectos de punta
a punta, con un formulario sin IA y el agente lanzado por detrás (`headless` solo para preparar
un proyecto, con progreso en vivo). Hasta que exista esa pestaña, esto es lo que hay: un vacío
que sirve: una línea de qué es, el camino recomendado y, si se
detecta un vault de Obsidian, el comando para usarlo. Los comandos se copian con un clic.
Habla con los tokens del tema, igual que `piezas.vacio`.
"""

from gi.repository import Gdk, Gtk

from .comun import ESPACIADO_SM, ESPACIADO_XS
from .piezas import con_mano, etiquetar, icono

QUE_ES = ("Cotejo reparte las tareas de tus proyectos entre agentes de IA y te deja "
          "comprobar lo que entregan.")
PEDIR_AL_AGENTE = "Empieza un proyecto con Cotejo"
INICIAR_REPO = "cotejo init --repo <carpeta>"
USAR_VAULT = "cotejo fuentes usar obsidian"


def es_primer_arranque(fuente):
    """Una fuente de repos sin ningún repo ni carpeta: no está rota, nadie la ha configurado.

    Un repo que no existe o una carpeta mal escrita siguen siendo un problema (ámbar): ahí
    sí hay algo que corregir.
    """
    return (fuente.problema is not None and hasattr(fuente, "repos")
            and not fuente.repos and not fuente.raiz)


def _paso(texto):
    return Gtk.Label(label=texto, xalign=0, wrap=True, css_classes=["vacio-pista"])


def _comando(texto, copiar):
    """El comando en una caja de mono, seleccionable, con su botón para copiarlo."""
    fila = Gtk.Box(spacing=ESPACIADO_SM, css_classes=["comando-copiable"])
    fila.append(Gtk.Label(label=texto, xalign=0, hexpand=True, wrap=True, selectable=True,
                          css_classes=["comando-texto"]))
    boton = con_mano(Gtk.Button(label="Copiar", valign=Gtk.Align.CENTER, css_classes=["flat"]))
    etiquetar(boton, f"Copiar: {texto}")
    boton.connect("clicked", lambda *_: copiar(texto))
    fila.append(boton)
    return fila


def vacio_de_arranque(aviso, vault=None):
    """La tarjeta del primer arranque; `aviso` es lo que se le dice a la persona al copiar."""
    def copiar(texto):
        Gdk.Display.get_default().get_clipboard().set(texto)
        aviso("Copiado al portapapeles")

    caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=ESPACIADO_SM,
                   css_classes=["vacio", "primer-arranque"])
    marca = icono("agente", 20, "vacio-icono")
    marca.set_halign(Gtk.Align.START)
    caja.append(marca)
    caja.append(Gtk.Label(label="Todavía no hay proyectos", xalign=0, wrap=True,
                          css_classes=["vacio-titulo"]))
    caja.append(_paso(QUE_ES))
    caja.append(_paso("Pídele a tu agente:"))
    caja.append(_comando(PEDIR_AL_AGENTE, copiar))
    caja.append(_paso("o créalo tú, desde una terminal:"))
    caja.append(_comando(INICIAR_REPO, copiar))
    if vault:
        caja.append(_paso(f"Encontré un vault de Obsidian ({vault}). Para usarlo:"))
        caja.append(_comando(USAR_VAULT, copiar))
    return caja
