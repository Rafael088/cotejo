"""Cuántos despachos caben ahora en esta máquina sin llevarla al OOM.

El maestro reparte en paralelo, y cada agente es un proceso con su memoria (Claude Code son
cientos de MB, y lo que corre dentro —pruebas, compilaciones— suma). En un portátil de 8 GB
cuatro a la vez pueden tumbar la sesión entera. Nada de esto se puede saber de antemano ni
escribir en una constante: depende de la máquina y de lo que ya esté corriendo. Así que se
**mide** al preguntar y se dice cuánto cabe, y por qué.

Dos mitades, como `decision.py`:

- `leer()` mira la máquina: memoria disponible y swap libre, CPUs y carga, y los agentes que ya
  corren con lo que ocupa cada uno (en Linux, de `/proc`; en macOS y Windows, lo que el sistema
  da sin dependencias). Es lo único que hace E/S.
- `calcular()` es aritmética sobre esa foto y la config, sin E/S: se prueba entera con números
  inventados y da lo mismo en cualquier máquina.

Lo que cuesta un agente es `enrutador.capacidad.mb_por_agente` si la config lo dice; si no, un
supuesto que los agentes que ya corren solo pueden **subir**: el más grande de ellos, si pasa del
supuesto. Uno en reposo ocupa menos que trabajando, así que medirlo nunca abarata la cuenta —ante
la duda se escala—. Nada de aquí asume la máquina del autor: todo número fijo es un valor por
defecto que la config cambia.
"""

import math
import os
import subprocess
import sys
from pathlib import Path

# Lo que se supone que ocupa un agente cuando no hay ninguno corriendo que medir. Un Claude
# Code en marcha ronda los 400–900 MB; con las pruebas o una compilación de un proyecto
# encima, más. Se prefiere quedarse corto repartiendo a tumbar la máquina.
MB_POR_AGENTE = 1500
# Lo que se deja libre siempre: el escritorio, el navegador, el propio maestro creciendo.
RESERVA_MIN_MB = 1024
RESERVA_FRACCION = 0.10
# Del swap libre cuenta solo una parte: sirve para no morir, no para trabajar a gusto.
FRACCION_SWAP = 0.25
# Lo que un agente pide de CPU en promedio: casi todo el rato espera a la API, pero a ratos
# corre pruebas o compila.
CPU_POR_AGENTE = 0.5

# Los ejecutables que cuentan como un agente en marcha, además de los clientes del catálogo.
CLIENTES_CONOCIDOS = ("claude", "opencode", "codex", "gemini")


# --- leer la máquina (E/S) ------------------------------------------------------------------

def leer(clientes_extra=()):
    """La foto de la máquina ahora mismo. Lo que no se pueda saber va como None."""
    nombres = set(CLIENTES_CONOCIDOS) | set(clientes_extra)
    foto = {"sistema": sys.platform, "cpus": os.cpu_count() or 1, "carga": _carga(),
            "memoria_total_mb": None, "memoria_disponible_mb": None,
            "swap_total_mb": None, "swap_libre_mb": None, "agentes": None}
    if sys.platform.startswith("linux"):
        foto.update(_memoria_linux())
        foto["agentes"] = _agentes_linux(nombres)
    elif sys.platform == "darwin":
        foto.update(_memoria_mac())
    elif sys.platform == "win32":
        foto.update(_memoria_windows())
    return foto


def _carga():
    try:
        return round(os.getloadavg()[0], 2)
    except (AttributeError, OSError):
        return None  # Windows no tiene carga media


def _memoria_linux():
    try:
        campos = {}
        for linea in Path("/proc/meminfo").read_text().splitlines():
            clave, _, valor = linea.partition(":")
            campos[clave] = int(valor.split()[0]) // 1024   # kB → MB
    except (OSError, ValueError, IndexError):
        return {}
    return {"memoria_total_mb": campos.get("MemTotal"),
            "memoria_disponible_mb": campos.get("MemAvailable"),
            "swap_total_mb": campos.get("SwapTotal"), "swap_libre_mb": campos.get("SwapFree")}


def _memoria_mac():
    def sysctl(nombre):
        hecho = subprocess.run(["sysctl", "-n", nombre], capture_output=True, text=True)
        return int(hecho.stdout.strip())
    try:
        total = sysctl("hw.memsize") // 2**20
        pagina = sysctl("hw.pagesize")
        vm = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
        paginas = {}
        for linea in vm.splitlines()[1:]:
            clave, _, valor = linea.partition(":")
            paginas[clave.strip()] = int(valor.strip().rstrip("."))
        libres = sum(paginas.get(k, 0) for k in ("Pages free", "Pages inactive",
                                                  "Pages speculative", "Pages purgeable"))
        return {"memoria_total_mb": total, "memoria_disponible_mb": libres * pagina // 2**20}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {}


def _memoria_windows():
    import ctypes
    from ctypes import wintypes

    class Estado(ctypes.Structure):
        _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

    estado = Estado()
    estado.dwLength = ctypes.sizeof(Estado)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado)):
        return {}
    mb = 2**20
    return {"memoria_total_mb": estado.ullTotalPhys // mb,
            "memoria_disponible_mb": estado.ullAvailPhys // mb,
            # El archivo de paginación incluye la RAM: lo de más es lo que hace de swap.
            "swap_total_mb": max(0, (estado.ullTotalPageFile - estado.ullTotalPhys) // mb),
            "swap_libre_mb": max(0, (estado.ullAvailPageFile - estado.ullAvailPhys) // mb)}


def _agentes_linux(nombres):
    """Los agentes en marcha, cada uno con la memoria de su árbol de procesos.

    Un agente es un proceso cuyo ejecutable (o su script, en `node …/claude`) se llama como un
    cliente; lo que cuesta es él más todo lo que cuelga de él —las pruebas que lanzó, el
    servidor de lenguaje—, que es lo que de verdad se come la memoria. Un agente que cuelga de
    otro (el cliente que el maestro lanzó por un despacho headless) cuenta aparte, y su árbol
    no se suma al de arriba.
    """
    procesos = {}
    for carpeta in Path("/proc").iterdir():
        if not carpeta.name.isdigit():
            continue
        try:
            estado = (carpeta / "status").read_text()
            linea = (carpeta / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        campos = dict(l.split(":", 1) for l in estado.splitlines() if ":" in l)
        try:
            ppid = int(campos.get("PPid", "0").strip())
            rss = int(campos.get("VmRSS", "0 kB").split()[0]) // 1024
        except ValueError:
            continue
        palabras = [Path(p.decode(errors="replace")).name for p in linea[:2] if p]
        agente = next((p for p in palabras if p in nombres), "")
        procesos[int(carpeta.name)] = (ppid, rss, agente)
    return agentes_de(procesos)


def agentes_de(procesos):
    """De {pid: (ppid, mb, nombre_de_agente_o_"")} a la lista de agentes con su árbol. Sin E/S."""
    hijos = {}
    for pid, (ppid, _, _) in procesos.items():
        hijos.setdefault(ppid, []).append(pid)

    def arbol(raiz):
        total, pendientes = 0, [raiz]
        while pendientes:
            actual = pendientes.pop()
            total += procesos[actual][1]
            pendientes.extend(h for h in hijos.get(actual, ()) if not procesos[h][2])
        return total

    return [{"pid": pid, "programa": procesos[pid][2], "mb": arbol(pid)}
            for pid in sorted(procesos) if procesos[pid][2]]


# --- calcular (sin E/S) --------------------------------------------------------------------

def calcular(foto, ajustes=None):
    """Cuántos despachos caben ahora, qué los limita y con qué números se decidió."""
    ajustes = ajustes or {}
    agentes = foto.get("agentes")
    medidos = [a["mb"] for a in agentes or () if a.get("mb")]
    if ajustes.get("mb_por_agente"):
        por_agente, origen = int(ajustes["mb_por_agente"]), "config"
    elif medidos and max(medidos) > MB_POR_AGENTE:
        por_agente, origen = max(medidos), "medido"
    else:
        por_agente, origen = MB_POR_AGENTE, "por_defecto"

    limites, motivos = {}, []
    total, disponible = foto.get("memoria_total_mb"), foto.get("memoria_disponible_mb")
    reserva = None
    if disponible is not None:
        reserva = int(ajustes.get("reserva_mb") or
                      max(RESERVA_MIN_MB, int((total or 0) * RESERVA_FRACCION)))
        swap = int((foto.get("swap_libre_mb") or 0) *
                   float(ajustes.get("fraccion_swap", FRACCION_SWAP)))
        utilizable = disponible + swap - reserva
        limites["memoria"] = max(0, utilizable // por_agente)
        motivos.append(f"{disponible} MB disponibles + {swap} MB de swap que cuentan − {reserva} "
                       f"MB de reserva = {max(0, utilizable)} MB, a {por_agente} MB por agente "
                       f"({_origen_legible(origen)})")
    else:
        motivos.append("No pude leer la memoria de esta máquina: no hay límite por memoria, "
                       "reparte con cuidado.")

    carga = foto.get("carga")
    cpus = foto.get("cpus") or 1
    if carga is not None:
        cpu_por_agente = float(ajustes.get("cpu_por_agente", CPU_POR_AGENTE))
        libres = cpus - carga
        limites["cpu"] = max(0, math.floor(libres / cpu_por_agente)) if libres > 0 else 0
        motivos.append(f"{cpus} CPUs con carga {carga}: {max(0, round(libres, 2))} libres, a "
                       f"{cpu_por_agente} por agente")

    if ajustes.get("maximo"):
        limites["maximo"] = int(ajustes["maximo"])
        motivos.append(f"enrutador.capacidad.maximo = {limites['maximo']}")

    if limites:
        limita = min(limites, key=lambda k: limites[k])
        caben = limites[limita]
    else:
        limita, caben = None, None
    return {"caben": caben, "limita": limita, "limites": limites,
            "mb_por_agente": por_agente, "mb_por_agente_origen": origen,
            "reserva_mb": reserva, "por_que": motivos}


def _origen_legible(origen):
    return {"config": "enrutador.capacidad.mb_por_agente",
            "medido": "el agente más grande de los que ya corren",
            "por_defecto": "supuesto; ningún agente en marcha ocupa más"}[origen]
