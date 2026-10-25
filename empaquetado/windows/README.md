# Cotejo para Windows

Un instalador `.exe` con el runtime dentro: quien lo instala no necesita Python, GTK ni MSYS2.
No hay ZIP portable: Cotejo es sobre todo la CLI de los agentes, y una carpeta suelta, sin PATH
ni aviso a los agentes, no sirve para eso. El instalador tampoco pide administrador.

```sh
python3 empaquetado/windows/construir.py          # → empaquetado/windows/construido/
```

| Sale | Qué es |
|---|---|
| `Cotejo/` | La instalación entera. Relocalizable: todo se busca a partir de donde está el `.exe`. |
| `Cotejo-<version>-windows-x64-instalador.exe` | Solo si hay Inno Setup 6 (`iscc`). |

La versión por defecto es la fecha y el hash del último commit (`--version` la cambia).

Aparte, `fuentes_terceros.py` arma `Cotejo-<versión>-fuentes-terceros.tar` (H11): la oferta de
código fuente que promete THIRD-PARTY-NOTICES, sección C.

```sh
python3 empaquetado/windows/fuentes_terceros.py empaquetado/windows/construido/Cotejo/runtime
```

## Qué hace falta para construir

- **Python 3.11+**, y para leer los paquetes de MSYS2, zstd: Python 3.14, el módulo
  `zstandard` o el comando `zstd`.
- **LLVM** (`clang`, `lld-link`, `llvm-dlltool`), para los lanzadores. No hace falta el SDK de
  Windows ni MinGW. En Windows: `winget install LLVM.LLVM`.
- **`glib-compile-schemas`** fuera de Windows (paquete `glib2`); en Windows se usa el del runtime.
- **Red** la primera vez (repo.msys2.org, los paquetes y, para completar licencias que falten,
  su código fuente); luego sale de `cache/`.
- **Inno Setup 6**, solo para el `.exe`, y solo existe en Windows. Sin él, se arma todo lo demás
  y `construir.py` imprime el `iscc …` que falta.

O sea: la carpeta se arma desde Linux; el instalador, en Windows (o donde haya `iscc`). Lo
compila `.github/workflows/windows.yml` en `windows-latest`, que después lo instala en
silencio y corre `probar_instalado.py`: `cotejo` en el PATH, menú Inicio y el board abierto. En
Windows, además, `construir.py` comprueba al final que `cotejo.exe` arranca y que el runtime
carga GTK 4 y libadwaita. Ese workflow no corre en cada push (los minutos de Windows cuentan
doble): corre desde `release.yml` o a mano con `gh workflow run windows.yml --ref <rama>`, y el
`.exe` se baja después con `gh run download`.

## Cómo está armado

```
Cotejo\
  bin\        cotejo.exe  cotejoboard.exe  cotejo-notion.exe
  interno\    cotejo-agentes.exe          (avisa a los agentes; lo corre el instalador)
  app\        tareas\  enrutador\  skills\  extras\  data\   (lo mismo que copia install.sh)
  runtime\    bin\python.exe, GTK 4, libadwaita, PyGObject… (de MSYS2 UCRT64)
  cotejo.ico
```

- **`bin\` es lo único que va al PATH.** `interno\` no, para que `cotejo-agentes` no aparezca
  como comando. Los dos cuelgan de la raíz, que es lo que el lanzador busca.
- **Los lanzadores** son `lanzador.c`, un programa sin biblioteca de C compilado dos veces (de
  consola y de ventana) y copiado con cada nombre. Qué corre cada uno se le pega al final
  del `.exe`; la lista está en `LANZADORES`, de `construir.py`, y en ningún otro sitio. Corren
  `runtime\bin\python.exe` (o `pythonw.exe`, el board) con `PYTHONPATH=app`, sin mirar el
  Python ni las variables `PYTHON*` que tenga el usuario, y devuelven su código de salida.
  Son `.exe` y no `.cmd` porque un `.cmd` no se encuentra desde Git Bash (que es donde corren
  los agentes en Windows) ni desde `subprocess` sin `shell=True` (que es como Cotejo llama a
  `cotejo-notion`).
- **El runtime sale de MSYS2**: se leen su índice y sus dependencias y se comprueba el SHA-256
  de cada paquete contra el índice. `runtime\PAQUETES.txt` dice cuáles entraron, con la licencia
  que declara cada uno y el nombre de su paquete fuente. `tcl` y `tk` se cortan (los pide
  Python para tkinter).
- **A ningún paquete que de verdad reparte algo le falta su licencia** (`runtime\share\licenses\<paquete>\`).
  Cuando el binario de MSYS2 no la trae, `completar_licencias` la saca de su código fuente (el
  mismo `.src.tar.zst` que usa `fuentes_terceros.py`): busca el `COPYING`/`LICENSE` de su raíz
  y, si no hay ninguno (como el certdata de Mozilla en ca-certificates), `debian/copyright`. A
  un paquete que no deja ningún archivo en el runtime (como `egl-headers` o `gles-headers`, que
  son solo cabeceras que se podan enteras) no se le pide la suya. Las tres versiones generales
  que promete THIRD-PARTY-NOTICES (`licenses/LGPL-2.1.txt`, `LGPL-3.0.txt`, `GPL-3.0.txt`) salen
  de ahí mismo.
- **Nada bajo GPL entra en el proceso de Cotejo**, que es propietario. Dos dependencias GPL sin
  excepción de enlace se cargan al abrir el board aunque Cotejo no las use: jbigkit
  (gtk4/gdk-pixbuf2 → libtiff → `libjbig-0.dll`) y lzo2 (gtk4 → cairo →
  `libcairo-script-interpreter-2.dll` → `liblzo2-2.dll`). No se bajan (`SUSTITUTAS`): en su
  sitio va una DLL propia con los mismos símbolos que no hace nada (`sustitutas/<paquete>.c`;
  JBIG y los scripts de cairo con LZO dan error). Borrarlas sin más no sirve: son importaciones
  de carga y Windows no abriría el board. `construir.py` comprueba que exporten todo lo que el
  runtime les pide, y falla si un paquete nuevo nombra la GPL y no está en `GPL_REVISADOS`. Los
  programas GPL que traen otros paquetes (gnutls, nettle, libtasn1…) se podan.
- **Lo que pacman haría al instalar**: los esquemas de GSettings se compilan al construir; la
  caché de cargadores de gdk-pixbuf no se genera, porque llevaría rutas absolutas y la carpeta
  se puede instalar en cualquier sitio: el lanzador apunta `GDK_PIXBUF_MODULEDIR` a la carpeta de cargadores.
- **La escala de la pantalla**: GTK en Windows solo escala por enteros y deja el 125, 150 y
  175 % en 1. El lanzador pone `GDK_WIN32_PER_MONITOR_HIDPI=1` (el DPI de cada monitor) y el
  resto lo escala la app (`tareas/app/escala.py`). `COTEJO_ESCALA=1.5` fuerza un factor, y
  `GDK_WIN32_DISABLE_HIDPI=1` vuelve a dejar que Windows estire la ventana como una imagen.
- **La config y el estado** van donde dice `tareas/rutas.py`: `%APPDATA%\cotejo` y
  `%LOCALAPPDATA%\cotejo\estado`. El instalador no los toca, ni al desinstalar.

## El instalador (`cotejo.iss`)

Para el usuario y sin administrador, como `install.sh`: en `%LOCALAPPDATA%\Programs\Cotejo`.
Añade `bin\` al PATH del usuario (y lo quita al desinstalar), pone Cotejo en el menú Inicio,
instala las tipografías del board para el usuario y, si se deja marcado, avisa a los agentes
(`python -m tareas.skill`, lo mismo que `install.sh`); al desinstalar, les quita el aviso. El
`AppId` no se cambia nunca: es lo que hace que una versión nueva actualice a la anterior.

## Si cambias algo

- **Un comando nuevo**: una línea en `LANZADORES`. Si es para el menú, también en `cotejo.iss`.
- **Una función de Win32 nueva en `lanzador.c`**: en `IMPORTACIONES`. La prueba lo vigila.
- **El icono de la app**: `python3 empaquetado/windows/icono.py` rehace `cotejo.ico`.
- `pruebas/test_empaquetado_windows.py` finge MSYS2 con un espejo en una carpeta y construye
  entero sin red; compila los lanzadores de verdad si hay LLVM.

## Lo que no se ha podido comprobar desde Linux

Los `.exe` se compilan y se comprueba que son ejecutables de Windows con su subsistema y su
orden, pero correrlos exige Windows. La primera construcción allí tiene que confirmar que el
board abre (`bin\cotejoboard.exe`), que `cotejo doctor` responde y que los iconos SVG se ven
(eso último es lo que depende de `GDK_PIXBUF_MODULEDIR`).

## Probar a mano en Windows, sin minutos de Actions

`windows.yml` cuenta doble y no corre en cada push; mientras no haya minutos, esto se prueba a
mano en un PC con Windows.

**Requisitos:** Python 3.11+ (`pip install zstandard`, para leer los paquetes de MSYS2),
`winget install LLVM.LLVM` (los lanzadores) e Inno Setup 6 (el `.exe`). Si `construir.py` no
puede verificar el certificado de `repo.msys2.org` (pasa en un Windows recién instalado, al que
le falta un intermedio de Let's Encrypt), `pip install truststore` y vuelve a construir.

`probar_despachar.py` y `probar_almacen.py` necesitan además las rutas largas de Windows
activadas, que el runner `windows-latest` ya trae y un Windows normal no. Lo comprueban al
arrancar; para activarlas, en una PowerShell de administrador:

```powershell
New-ItemProperty -Path HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem -Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force
```

Clona en una ruta corta (`C:\cotejo`): los scripts dejan sus pruebas en `%TEMP%` y suman
mucho a la ruta.

```powershell
python empaquetado\windows\construir.py                      # -> empaquetado\windows\construido\
empaquetado\windows\construido\Cotejo-*-instalador.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CURRENTUSER /TASKS=path,agentes
```

Y, con eso instalado, los tres scripts que corre `windows.yml` después de instalar (cada uno
sale con código 0 si todo fue bien, y deja su registro en `empaquetado\windows\construido\registros\`):

```powershell
python empaquetado\windows\probar_instalado.py empaquetado\windows\construido\Cotejo-*-instalador.exe
python empaquetado\windows\probar_despachar.py
python empaquetado\windows\probar_almacen.py
```

`probar_almacen.py` (v1.2 · F1) es el único de los tres que también corre en Linux —pásale la
ruta de un `cotejo` instalado, o déjalo encontrar el del PATH— para poder probarlo antes de
pedirle a nadie que lo corra en Windows; ahí no prueba nada de Windows en sí, solo que el
script funciona.

Lo que no se puede probar es una raíz de repo de más de ~248 caracteres: en Windows `git
init` no puede con ella, ni con `LongPathsEnabled=1` ni con `core.longpaths=true` (crea la
carpeta, pero no entra). Por eso `probar_almacen.py` deja la raíz en 240 y lo que pasa de los
260 son los archivos de `recursos/` y de la bitácora, y `importar obsidian --aplicar` sobre un
destino más largo se niega con un mensaje que lo dice.
