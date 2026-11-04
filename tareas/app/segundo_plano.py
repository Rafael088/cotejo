"""Lo lento del board fuera del hilo de GTK (cotejo-72a7di).

Lanzar una tarea desde el board (`lanzar.py`) toma la tarea con `cotejo`, crea su worktree con
varios `git` y arranca el cliente: en Linux son décimas, pero en Windows cada proceso cuesta
mucho más y el bucle de GTK se quedaba parado ~10 s al soltar una carta en Haciendo («Cotejo no
responde», medido con `herramientas/probar_windows.sh`). Aquí ese trabajo corre en **un** hilo
de despachos y la respuesta vuelve a la interfaz con `GLib.idle_add`.

Un solo hilo y en orden, a propósito: dos sueltas seguidas se despachan una detrás de otra,
igual que cuando corrían en el hilo principal. Así dos `git worktree add` no se pisan en el
mismo repo y la capacidad no deja entrar a dos agentes en el mismo hueco. Al salir de la app,
Python espera a que termine el despacho que estaba en marcha (los hilos de
`ThreadPoolExecutor` se esperan al cerrar el intérprete): la tarea no se queda a medio tomar.
"""

import threading
from concurrent.futures import ThreadPoolExecutor

from gi.repository import GLib

TOPE_PRINCIPAL_S = 60

_cola = None
_cerrojo = threading.Lock()
_en_marcha = 0


def _la_cola():
    global _cola
    with _cerrojo:
        if _cola is None:
            _cola = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cotejo-despacho")
        return _cola


def en_segundo_plano(trabajo, al_volver):
    """Corre `trabajo()` en el hilo de despachos y, en el hilo de GTK, `al_volver(resultado,
    error)`: `error` es la excepción que levantó `trabajo` (o None) y `resultado` lo que
    devolvió (o None si falló)."""
    global _en_marcha
    with _cerrojo:
        _en_marcha += 1

    def volver(resultado, error):
        global _en_marcha
        try:
            al_volver(resultado, error)
        finally:
            with _cerrojo:
                _en_marcha -= 1
        return GLib.SOURCE_REMOVE

    def hecho(futuro):
        error = futuro.exception()
        GLib.idle_add(volver, None if error else futuro.result(), error)

    _la_cola().submit(trabajo).add_done_callback(hecho)


def en_marcha():
    """Cuántos despachos faltan por volver a la interfaz (las pruebas esperan a que sea 0)."""
    return _en_marcha


def en_hilo_principal(funcion, tope_s=TOPE_PRINCIPAL_S):
    """Desde el hilo de despachos, corre `funcion()` en el de GTK y devuelve lo que devuelva.

    Para lo que tiene que tocar la interfaz a mitad de un despacho (devolver una tarea a
    Haciendo escribe su línea y repinta antes de lanzar el agente nuevo). Desde el hilo
    principal la llama sin más. Si la interfaz no la atiende en `tope_s` (la app se cerró),
    levanta `TimeoutError`."""
    if threading.current_thread() is threading.main_thread():
        return funcion()
    listo = threading.Event()
    caja = {}

    def correr():
        try:
            caja["resultado"] = funcion()
        except BaseException as error:  # noqa: BLE001 — se levanta en el hilo que espera
            caja["error"] = error
        finally:
            listo.set()
        return GLib.SOURCE_REMOVE

    GLib.idle_add(correr)
    if not listo.wait(tope_s):
        raise TimeoutError("la interfaz no contestó")
    if "error" in caja:
        raise caja["error"]
    return caja.get("resultado")
