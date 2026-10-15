"""Instala Cotejo con su instalador y comprueba que quedó usable, como en un PC recién estrenado.

    python empaquetado/windows/probar_instalado.py <Cotejo-…-instalador.exe>

Solo corre en Windows (lo usa `.github/workflows/windows.yml`). Instala en silencio para el
usuario, sin config ni vault, y comprueba lo que el usuario va a hacer después: `cotejo` en el
PATH, el acceso del menú Inicio y que el board abre y se queda abierto. Si el board se cae, lo
que dijo Python queda en `construido/registros/`, que el workflow sube como artefacto.
"""

import atexit
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
REGISTROS = AQUI / "construido" / "registros"
# Lo que tarda el board en rendirse si algo falla al arrancar. Vivo después de esto es abierto.
ESPERA = 25
# Desde donde corren los comandos: una carpeta vacía, como el escritorio de cualquiera. Desde
# la raíz del repo, `python -m tareas` corría el código del repo y no el instalado.
VACIA = Path(tempfile.mkdtemp())
atexit.register(shutil.rmtree, VACIA, ignore_errors=True)  # y CotejoViejo con ella


def instalar(instalador):
    subprocess.run([str(instalador), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                    "/CURRENTUSER", "/TASKS=path,agentes", f"/LOG={REGISTROS / 'instalador.txt'}"],
                   check=True)
    raiz = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Cotejo"
    if not (raiz / "bin" / "cotejo.exe").is_file():
        raise SystemExit(f"El instalador terminó pero no hay {raiz}\\bin\\cotejo.exe")
    return raiz


def ventanas_visibles():
    """Títulos de las ventanas de primer nivel visibles en el escritorio, con su tamaño."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    encontradas = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def una(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            titulo = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, titulo, 256)
            caja = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(caja))
            if titulo.value:
                encontradas.append((titulo.value, caja.right - caja.left, caja.bottom - caja.top))
        return True

    user32.EnumWindows(una, 0)
    return encontradas


def capturar(nombre):
    """Una captura de la pantalla entera en REGISTROS, para ver lo que vería el usuario."""
    destino = REGISTROS / nombre
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
                    "$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
                    "$i = New-Object System.Drawing.Bitmap $b.Width, $b.Height; "
                    "$g = [System.Drawing.Graphics]::FromImage($i); "
                    "$g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size); "
                    f"$i.Save('{destino}')"], capture_output=True)


def maximizar_board():
    """Maximiza la ventana CotejoBoard como lo haría su botón (ShowWindow con SW_MAXIMIZE)."""
    import ctypes
    import time
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, "CotejoBoard")
    if hwnd:
        user32.ShowWindow(hwnd, 3)
        time.sleep(3)
    return bool(hwnd)


def ventana_del_board():
    """¿Aparece una ventana visible «CotejoBoard» antes de ESPERA segundos?"""
    import time
    limite = time.monotonic() + ESPERA
    while time.monotonic() < limite:
        if any(titulo == "CotejoBoard" and ancho > 100 and alto > 100
               for titulo, ancho, alto in ventanas_visibles()):
            return True
        time.sleep(1)
    return False


def matar(proceso):
    # El lanzador espera a su Python: hay que llevarse el árbol entero.
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proceso.pid)], capture_output=True)


def se_queda_abierto(exe, *argumentos, registro, captura):
    """¿Sigue vivo a los ESPERA segundos y sin traceback? Su salida queda en `registro`.

    Vivo no basta: la app hace `hold()`, así que un error al crear la ventana la deja viva y
    sin ventana. Eso es lo que pasaba en Windows, y esta prueba lo daba por bueno.
    """
    with open(REGISTROS / registro, "w", encoding="utf-8", errors="replace") as salida:
        proceso = subprocess.Popen([str(exe), *argumentos], stdout=salida,
                                   stderr=subprocess.STDOUT, cwd=VACIA)
        visible = ventana_del_board()
        capturar(captura)
        try:
            codigo = proceso.wait(1)
            vivo = False
        except subprocess.TimeoutExpired:
            matar(proceso)
            vivo = True
    texto = (REGISTROS / registro).read_text(encoding="utf-8", errors="replace")
    if vivo and visible and "Traceback" not in texto:
        return True
    if vivo and not visible:
        print(f"{exe.name} {' '.join(argumentos)} sigue vivo pero no hay ventana CotejoBoard "
              f"visible. Ventanas visibles: {ventanas_visibles()}")
    print(f"{exe.name} {' '.join(argumentos)} " +
          ("sigue vivo pero se quejó:" if vivo else f"se cerró solo (código {codigo}):"))
    print(texto)
    return False


def cerrar_cotejo():
    """Cierra el Cotejo que se abrió sin pasar por aquí (desde el menú Inicio)."""
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process | Where-Object { "
                    r"$_.ExecutablePath -match '\\runtime\\bin\\pythonw?\.exe$' } | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"], capture_output=True)


EVIDENCIAS = (
    "Hecho.",
    "Publicado en el panel; el enlace está en la nota del proyecto y lo revisé en dos navegadores.",
    "Revisé las 42 filas del reporte contra la fuente. Cambié el formato de las fechas a ISO.\n\n"
    "Quedan dos avisos en la consola que no vienen de este cambio: los anoté aparte. Para "
    "comprobarlo: abre el panel, filtra por septiembre y compara el total con la hoja original, "
    "que tiene que dar 18.240 exactos.",
)


def board_con_entregas(raiz):
    """El board con tareas en Para comprobar, cada una con su evidencia, y una captura.

    Así se ve en Windows lo que en Linux no pasa: las cartas de esa columna, las únicas que
    llevan la evidencia dentro, crecían de más (cotejo-hjagw9).
    """
    sys.path.insert(0, str(AQUI.parent.parent / "herramientas"))
    import json
    import vault_prueba
    vault = vault_prueba.crear(VACIA.parent / "vault-entregas")
    entorno = {**os.environ, "COTEJO_VAULT": str(vault),
               "COTEJO_ESTADO": str(VACIA.parent / "estado-entregas")}
    cotejo = str(raiz / "bin" / "cotejo.exe")

    def cli(*argumentos):
        hecho = subprocess.run([cotejo, *argumentos], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", cwd=VACIA, env=entorno)
        if hecho.returncode:
            raise RuntimeError(f"cotejo {' '.join(argumentos)} salió con {hecho.returncode}:\n"
                               f"{hecho.stdout}\n{hecho.stderr}")
        return json.loads(hecho.stdout)

    for numero, evidencia in enumerate(EVIDENCIAS, 1):
        tarea = cli("crear", f"Entrega de prueba número {numero} para ver la carta",
                    "--proyecto", "Faro")["tarea"]["id"]
        cli("tomar", tarea, "--agente", "opus")
        cli("entregar", tarea, "--evidencia", evidencia)
    cerrar_cotejo()
    proceso = subprocess.Popen([cotejo, "--board"], cwd=VACIA, env=entorno,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    visible = ventana_del_board()
    capturar("board-entregas.png")
    # Maximizada no debería quedar ningún borde ni sombra alrededor (cotejo-yuwm63).
    if maximizar_board():
        capturar("board-maximizada.png")
    matar(proceso)
    cerrar_cotejo()
    return visible


def cierra_el_cotejo_de_otra_carpeta(raiz, instalador):
    """Lo que pasó con el ZIP: un Cotejo vivo en otra carpeta se quedaba con la orden del recién
    instalado y el board no aparecía. El instalador tiene que cerrarlo (cotejo-ksypkc)."""
    viejo = VACIA / "CotejoViejo"  # dentro de VACIA: se borra con ella y no choca al repetir
    shutil.copytree(raiz, viejo)
    proceso = subprocess.Popen([str(viejo / "bin" / "cotejo.exe"), "--fondo"], cwd=VACIA,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        proceso.wait(8)
        print("El Cotejo de otra carpeta no se quedó en segundo plano; no se puede probar.")
        return False
    except subprocess.TimeoutExpired:
        pass
    instalar(instalador)
    try:
        proceso.wait(15)
    except subprocess.TimeoutExpired:
        matar(proceso)
        return False
    print("El instalador cerró el Cotejo que corría desde otra carpeta.")
    return True


def main(instalador):
    REGISTROS.mkdir(parents=True, exist_ok=True)
    raiz = instalar(Path(instalador))
    print(f"Instalado en {raiz}")
    fallos = []

    version = subprocess.run([str(raiz / "bin" / "cotejo.exe"), "--version"],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", cwd=VACIA)
    print("cotejo --version:", version.stdout.strip() or version.stderr.strip())
    if version.returncode:
        fallos.append("cotejo --version falla")

    doctor = subprocess.run([str(raiz / "bin" / "cotejo.exe"), "doctor"],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", cwd=VACIA)
    print("cotejo doctor:", doctor.stdout.strip()[:2000], doctor.stderr.strip()[:2000])

    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as clave:
        path = winreg.QueryValueEx(clave, "Path")[0]
    if str(raiz / "bin").lower() not in path.lower():
        fallos.append("bin\\ no quedó en el PATH del usuario")

    cache = raiz / "runtime" / "lib" / "gdk-pixbuf-2.0" / "2.10.0" / "loaders.cache"
    if "pixbufloader_svg" not in (cache.read_text(errors="replace") if cache.is_file() else ""):
        fallos.append("loaders.cache no registra el cargador de SVG")

    # H7: la página de licencia del instalador (`LicenseFile=app\LICENSE` en cotejo.iss) la lee
    # Inno Setup con la página de códigos ANSI si el .txt no lleva BOM, y un LICENSE con tildes
    # sale con mojibake. /VERYSILENT no muestra esa página, así que no hay captura de pantalla
    # posible aquí; esto comprueba lo que de verdad decide cómo Inno Setup la lee: que la copia
    # instalada (app\LICENSE, la misma que empaquetó el instalador) lleva el BOM UTF-8.
    licencia = (raiz / "app" / "LICENSE").read_bytes()
    if not licencia.startswith(b"\xef\xbb\xbf"):
        fallos.append("app\\LICENSE no lleva BOM UTF-8: la página de licencia del instalador "
                       "podría mostrarse con mojibake")

    menu = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    if not (menu / "Cotejo.lnk").is_file():
        fallos.append("no hay acceso en el menú Inicio")

    if not cierra_el_cotejo_de_otra_carpeta(raiz, Path(instalador)):
        fallos.append("el instalador no cerró un Cotejo que corría desde otra carpeta")

    # De consola primero: si se cae, esta sí deja ver el traceback.
    if not se_queda_abierto(raiz / "bin" / "cotejo.exe", "--board", registro="board-consola.txt",
                            captura="board-consola.png"):
        fallos.append("el board (cotejo --board) no se queda abierto")
    # Lo que abre el menú Inicio: pythonw, sin consola.
    elif not se_queda_abierto(raiz / "bin" / "cotejoboard.exe", registro="board-ventana.txt",
                              captura="board-ventana.png"):
        fallos.append("cotejoboard.exe no se queda abierto")

    # Como lo abre la gente: desde el acceso del menú Inicio. La captura enseña la barra de
    # tareas, donde tiene que salir el ícono de Cotejo y no el de Python (cotejo-lwi9ft).
    os.startfile(menu / "Cotejo.lnk")
    if not ventana_del_board():
        fallos.append("el acceso del menú Inicio no abre el board")
    capturar("board-menu-inicio.png")
    cerrar_cotejo()

    try:
        if not board_con_entregas(raiz):
            fallos.append("el board con tareas entregadas no se ve")
    except RuntimeError as error:
        print(error)
        fallos.append("no se pudieron preparar las tareas entregadas")

    if fallos:
        print("Falló:\n- " + "\n- ".join(fallos))
        return 1
    print("Instalado y usable: cotejo en el PATH, menú Inicio y el board abre.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.exit(main(sys.argv[1]))
