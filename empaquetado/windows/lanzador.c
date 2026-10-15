/* El lanzador de Cotejo en Windows: lo que hay detrás de `cotejo.exe`, `cotejoboard.exe`…

   Un solo programa, compilado dos veces —de consola y de ventana (`-DVENTANA`)— y copiado con
   cada nombre. Qué corre cada copia no está aquí: `construir.py` se lo pega al final del .exe
   (la «carga»), así la lista de comandos vive en un solo sitio. Formato de la cola del archivo:

       <orden en UTF-16LE> <largo de la orden en bytes, u32 LE> "COTEJO01"

   La orden es `-m modulo` o `@ruta\relativa\a\app.py`. El lanzador busca su carpeta, sube un
   nivel (la raíz de la instalación: `bin\..`, `interno\..`) y ejecuta

       <raiz>\runtime\bin\python.exe <orden> <los argumentos que le pasaron, tal cual>

   con PYTHONPATH en `<raiz>\app`, y espera para devolver su código de salida. La versión de
   ventana usa `pythonw.exe`, que no abre consola.

   No usa la biblioteca de C: solo kernel32 (y user32 para el aviso de la de ventana), así que
   se compila con clang y lld-link desde Linux, macOS o Windows sin SDK ni MinGW. Por eso las
   declaraciones de Win32 van escritas a mano abajo. */

#include <stddef.h>

typedef void *HANDLE;
typedef unsigned long DWORD;
typedef unsigned short WORD;
typedef int BOOL;
typedef long long LONGLONG;

typedef struct {
    DWORD cb;
    wchar_t *lpReserved, *lpDesktop, *lpTitle;
    DWORD dwX, dwY, dwXSize, dwYSize, dwXCountChars, dwYCountChars, dwFillAttribute, dwFlags;
    WORD wShowWindow, cbReserved2;
    unsigned char *lpReserved2;
    HANDLE hStdInput, hStdOutput, hStdError;
} STARTUPINFOW;

typedef struct {
    HANDLE hProcess, hThread;
    DWORD dwProcessId, dwThreadId;
} PROCESS_INFORMATION;

#define IMPORTADA __declspec(dllimport)
IMPORTADA DWORD GetModuleFileNameW(HANDLE, wchar_t *, DWORD);
IMPORTADA wchar_t *GetCommandLineW(void);
IMPORTADA BOOL SetEnvironmentVariableW(const wchar_t *, const wchar_t *);
IMPORTADA DWORD GetEnvironmentVariableW(const wchar_t *, wchar_t *, DWORD);
IMPORTADA HANDLE CreateFileW(const wchar_t *, DWORD, DWORD, void *, DWORD, DWORD, HANDLE);
IMPORTADA BOOL ReadFile(HANDLE, void *, DWORD, DWORD *, void *);
IMPORTADA BOOL SetFilePointerEx(HANDLE, LONGLONG, LONGLONG *, DWORD);
IMPORTADA BOOL CloseHandle(HANDLE);
IMPORTADA DWORD GetFileAttributesW(const wchar_t *);
IMPORTADA BOOL CreateProcessW(const wchar_t *, wchar_t *, void *, void *, BOOL, DWORD, void *,
                              const wchar_t *, STARTUPINFOW *, PROCESS_INFORMATION *);
IMPORTADA DWORD WaitForSingleObject(HANDLE, DWORD);
IMPORTADA BOOL GetExitCodeProcess(HANDLE, DWORD *);
IMPORTADA HANDLE GetStdHandle(DWORD);
IMPORTADA void ExitProcess(unsigned);
#ifdef VENTANA
IMPORTADA int MessageBoxW(HANDLE, const wchar_t *, const wchar_t *, unsigned);
#else
IMPORTADA BOOL SetConsoleCtrlHandler(void *, BOOL);
IMPORTADA BOOL WriteConsoleW(HANDLE, const void *, DWORD, DWORD *, void *);
IMPORTADA BOOL WriteFile(HANDLE, const void *, DWORD, DWORD *, void *);
IMPORTADA int WideCharToMultiByte(unsigned, DWORD, const wchar_t *, int, char *, int, const char *,
                                  BOOL *);
#endif

#define GENERIC_READ 0x80000000UL
#define FILE_SHARE_READ 1
#define OPEN_EXISTING 3
#define FILE_END 2
#define INVALID_HANDLE ((HANDLE)(LONGLONG)-1)
#define NO_EXISTE 0xFFFFFFFFUL
#define STARTF_USESTDHANDLES 0x100
#define STD_INPUT (-10)
#define STD_OUTPUT (-11)
#define STD_ERROR (-12)
#define INFINITO 0xFFFFFFFFUL
#define CP_UTF8 65001

#define MAGIA "COTEJO01"
#define LARGO 32768

/* clang puede emitir llamadas a estas dos aunque el código no las nombre. */
void *memset(void *d, int c, size_t n) {
    unsigned char *p = d;
    while (n--) *p++ = (unsigned char)c;
    return d;
}
void *memcpy(void *d, const void *o, size_t n) {
    unsigned char *p = d;
    const unsigned char *q = o;
    while (n--) *p++ = *q++;
    return d;
}

/* Estáticos y no en la pila: con buffers grandes en la pila haría falta __chkstk, del CRT. */
static wchar_t exe[LARGO], raiz[LARGO], python[LARGO], orden[2048], linea[LARGO];
static wchar_t valor[LARGO], viejo[LARGO];
static STARTUPINFOW inicio_hijo;
static PROCESS_INFORMATION hijo;

static size_t largo(const wchar_t *s) {
    size_t n = 0;
    while (s[n]) n++;
    return n;
}

/* Añade `s` al final de `d` (de capacidad LARGO); falso si no cabe. */
static int anadir(wchar_t *d, const wchar_t *s) {
    size_t n = largo(d), m = largo(s);
    if (n + m + 1 > LARGO) return 0;
    memcpy(d + n, s, (m + 1) * sizeof(wchar_t));
    return 1;
}

static void quitar_ultimo_tramo(wchar_t *ruta) {
    size_t n = largo(ruta);
    while (n > 0 && ruta[n - 1] != L'\\' && ruta[n - 1] != L'/') n--;
    ruta[n > 0 ? n - 1 : 0] = 0;
}

static void fallar(const wchar_t *mensaje) {
#ifdef VENTANA
    MessageBoxW(0, mensaje, L"Cotejo", 0x10);
#else
    /* En una consola, tal cual; si stderr va a un archivo o a un agente, en UTF-8. */
    static char utf8[4096];
    DWORD escrito;
    HANDLE err = GetStdHandle(STD_ERROR);
    if (!WriteConsoleW(err, mensaje, (DWORD)largo(mensaje), &escrito, 0)) {
        int n = WideCharToMultiByte(CP_UTF8, 0, mensaje, -1, utf8, sizeof(utf8) - 2, 0, 0);
        if (n > 0) {
            utf8[n - 1] = '\n';
            WriteFile(err, utf8, (DWORD)n, &escrito, 0);
        }
    } else {
        WriteConsoleW(err, L"\r\n", 2, &escrito, 0);
    }
#endif
    ExitProcess(120);
}

/* Lee la orden que construir.py dejó al final de este mismo .exe. */
static void leer_carga(void) {
    unsigned char cola[12];
    DWORD leido, bytes;
    HANDLE f = CreateFileW(exe, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
    if (f == INVALID_HANDLE) fallar(L"Cotejo: no pude leerme a mí mismo.");
    if (!SetFilePointerEx(f, -12, 0, FILE_END) || !ReadFile(f, cola, 12, &leido, 0) || leido != 12)
        fallar(L"Cotejo: lanzador sin orden (¿se copió sin construir.py?).");
    for (int i = 0; i < 8; i++)
        if (cola[4 + i] != (unsigned char)MAGIA[i])
            fallar(L"Cotejo: lanzador sin orden (¿se copió sin construir.py?).");
    bytes = cola[0] | cola[1] << 8 | cola[2] << 16 | (DWORD)cola[3] << 24;
    if (bytes == 0 || bytes % 2 || bytes >= sizeof(orden))
        fallar(L"Cotejo: la orden del lanzador está dañada.");
    SetFilePointerEx(f, -(LONGLONG)(12 + bytes), 0, FILE_END);
    if (!ReadFile(f, orden, bytes, &leido, 0) || leido != bytes)
        fallar(L"Cotejo: la orden del lanzador está dañada.");
    orden[bytes / 2] = 0;
    CloseHandle(f);
}

/* Los argumentos con que llamaron al lanzador, sin su propio nombre y sin retocar comillas. */
static const wchar_t *argumentos(void) {
    const wchar_t *c = GetCommandLineW();
    if (*c == L'"') {
        c++;
        while (*c && *c != L'"') c++;
        if (*c) c++;
    } else {
        while (*c && *c != L' ' && *c != L'\t') c++;
    }
    while (*c == L' ' || *c == L'\t') c++;
    return c;
}

/* Pone la variable `nombre` en `<raiz><carpeta>`. */
static void poner(const wchar_t *nombre, const wchar_t *carpeta) {
    valor[0] = 0;
    anadir(valor, raiz);
    anadir(valor, carpeta);
    SetEnvironmentVariableW(nombre, valor);
}

void inicio(void) {
    DWORD codigo = 0;

    if (!GetModuleFileNameW(0, exe, LARGO)) fallar(L"Cotejo: no sé dónde estoy.");
    leer_carga();
    memcpy(raiz, exe, sizeof(exe));
    quitar_ultimo_tramo(raiz); /* …\bin\cotejo.exe → …\bin */
    quitar_ultimo_tramo(raiz); /* …\bin → la raíz */

    python[0] = 0;
    anadir(python, raiz);
#ifdef VENTANA
    anadir(python, L"\\runtime\\bin\\pythonw.exe");
#else
    anadir(python, L"\\runtime\\bin\\python.exe");
#endif
    if (GetFileAttributesW(python) == NO_EXISTE)
        fallar(L"Cotejo: falta runtime\\bin\\python.exe junto a esta carpeta. Reinstala Cotejo.");

    /* El Python de Cotejo no mira lo que el usuario tenga puesto para otro Python. */
    poner(L"PYTHONPATH", L"\\app");
    SetEnvironmentVariableW(L"PYTHONHOME", 0);
    SetEnvironmentVariableW(L"PYTHONNOUSERSITE", L"1");
    SetEnvironmentVariableW(L"PYTHONUTF8", L"1");
    /* Sin esto `python -m tareas` pone la carpeta actual primero en sys.path, y desde una
       carpeta con un subdirectorio `tareas` correría ese y no Cotejo. */
    SetEnvironmentVariableW(L"PYTHONSAFEPATH", L"1");
    /* El Python de MSYS2 cambia su separador a `/` si ve MSYSTEM, que Git Bash define (y es
       donde corren los agentes en Windows). Los listados de Windows siguen dando `\`, y las
       rutas mezcladas rompían `relative_to` al leer el vault (cotejo-cj8xh5). */
    SetEnvironmentVariableW(L"MSYSTEM", 0);
    /* Dónde están los cargadores de gdk-pixbuf, para `gdk-pixbuf-query-loaders`. La app no
       mira esta variable sino `loaders.cache`, que el instalador genera al instalar: sin él
       no hay SVG y el board no podía dibujar su logo (cotejo-bezrqz). */
    poner(L"GDK_PIXBUF_MODULEDIR", L"\\runtime\\lib\\gdk-pixbuf-2.0\\2.10.0\\loaders");
    /* bin\ primero, para que Cotejo encuentre a cotejo-notion aunque no esté en el PATH. */
    viejo[0] = 0;
    GetEnvironmentVariableW(L"PATH", viejo, LARGO);
    valor[0] = 0;
    anadir(valor, raiz);
    anadir(valor, L"\\bin;");
    anadir(valor, raiz);
    anadir(valor, L"\\runtime\\bin;");
    anadir(valor, viejo);
    SetEnvironmentVariableW(L"PATH", valor);

    linea[0] = 0;
    anadir(linea, L"\"");
    anadir(linea, python);
    anadir(linea, L"\" ");
    if (orden[0] == L'@') {
        anadir(linea, L"\"");
        anadir(linea, raiz);
        anadir(linea, L"\\app\\");
        anadir(linea, orden + 1);
        anadir(linea, L"\"");
    } else {
        anadir(linea, orden);
    }
    const wchar_t *resto = argumentos();
    if (*resto) {
        anadir(linea, L" ");
        if (!anadir(linea, resto)) fallar(L"Cotejo: la línea de comandos es demasiado larga.");
    }

    inicio_hijo.cb = sizeof(inicio_hijo);
    inicio_hijo.dwFlags = STARTF_USESTDHANDLES;
    inicio_hijo.hStdInput = GetStdHandle(STD_INPUT);
    inicio_hijo.hStdOutput = GetStdHandle(STD_OUTPUT);
    inicio_hijo.hStdError = GetStdHandle(STD_ERROR);
#ifndef VENTANA
    /* Ctrl+C le llega también al hijo, que es quien debe decidir qué hacer con él. */
    SetConsoleCtrlHandler(0, 1);
#endif
    if (!CreateProcessW(python, linea, 0, 0, 1, 0, 0, 0, &inicio_hijo,
                        &hijo))
        fallar(L"Cotejo: no pude arrancar el Python de Cotejo.");
    WaitForSingleObject(hijo.hProcess, INFINITO);
    GetExitCodeProcess(hijo.hProcess, &codigo);
    ExitProcess(codigo);
}
