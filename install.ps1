# Instala (o actualiza) Cotejo en Windows desde su última versión en GitHub Releases:
#
#   irm https://rafael088.github.io/cotejo/install.ps1 | iex
#
# Baja el instalador (Cotejo-<versión>-windows-x64-instalador.exe) y SHA256SUMS de la release,
# comprueba la suma SHA-256 (si no coincide, no lo ejecuta) y lo corre en silencio, para tu
# usuario y sin administrador: menú Inicio, `cotejo` en el PATH y el aviso a tus agentes.
# Volver a correrlo actualiza a la última versión; la configuración se conserva.
#
#   $env:COTEJO_VERSION = '1.0.0'     instala esa versión en vez de la última
#   $env:COTEJO_DESCARGAS = '<url>'   de dónde bajar (una URL o una carpeta local)
#
# Va entero dentro de un bloque: con `irm | iex` corre en tu sesión de PowerShell, y nada de
# aquí debe quedarse en ella ni cerrarla (por eso no hay ningún `exit`).
& {
    $ErrorActionPreference = 'Stop'
    # La barra de progreso de Invoke-WebRequest hace la descarga decenas de veces más lenta.
    $ProgressPreference = 'SilentlyContinue'
    # Windows PowerShell 5.1 no siempre ofrece TLS 1.2, y GitHub no acepta otra cosa.
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor
        [Net.SecurityProtocolType]::Tls12

    $repo = 'https://github.com/Rafael088/cotejo'
    # El AppId de empaquetado/windows/cotejo.iss: dónde Inno Setup deja la versión instalada.
    $clave = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{EA72ABDA-35CB-4BCC-AC9F-0B2E6FD479C1}_is1'

    function Di($texto) { Write-Host "Cotejo: $texto" }

    function Ultima-Version {
        # La redirección de /releases/latest dice la etiqueta sin pasar por la API (que limita
        # las peticiones sin token).
        $peticion = [Net.WebRequest]::Create("$repo/releases/latest")
        $peticion.Method = 'HEAD'
        $respuesta = $peticion.GetResponse()
        try { $destino = $respuesta.ResponseUri.AbsoluteUri } finally { $respuesta.Close() }
        if ($destino -notmatch '/tag/v([^/]+)$') {
            throw "no encontré la última versión en $repo/releases (¿sin conexión?)"
        }
        $Matches[1]
    }

    function Bajar($origen, $destino) {
        if (Test-Path -LiteralPath $origen) { Copy-Item -LiteralPath $origen $destino }
        else { Invoke-WebRequest -UseBasicParsing -Uri $origen -OutFile $destino }
    }

    try {
        if (-not [Environment]::Is64BitOperatingSystem) {
            throw 'Cotejo para Windows es de 64 bits, y este Windows es de 32.'
        }
        $version = if ($env:COTEJO_VERSION) { $env:COTEJO_VERSION } else { Ultima-Version }
        if ($version -notmatch '^[A-Za-z0-9._+-]+$') { throw "versión no válida: $version" }
        $descargas = if ($env:COTEJO_DESCARGAS) { $env:COTEJO_DESCARGAS.TrimEnd('/', '\') }
                     else { "$repo/releases/download/v$version" }
        $separador = if (Test-Path -LiteralPath $descargas) { '\' } else { '/' }

        $antes = (Get-ItemProperty -Path $clave -ErrorAction SilentlyContinue).DisplayVersion
        if ($antes -eq $version) { Di "ya tienes la $version; la reinstalo por si le falta algo." }
        elseif ($antes) { Di "actualizando de la $antes a la $version." }
        else { Di "instalando la $version." }

        $tmp = Join-Path ([IO.Path]::GetTempPath()) ("cotejo-" + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $tmp | Out-Null
        try {
            $nombre = "Cotejo-$version-windows-x64-instalador.exe"
            $instalador = Join-Path $tmp $nombre
            $sumas = Join-Path $tmp 'SHA256SUMS'
            Bajar "$descargas$separador$nombre" $instalador
            Bajar "$descargas${separador}SHA256SUMS" $sumas

            $esperada = $null
            foreach ($linea in Get-Content -LiteralPath $sumas) {
                $partes = $linea.Trim() -split '\s+', 2
                if ($partes.Count -eq 2 -and $partes[1].TrimStart('*') -eq $nombre) {
                    $esperada = $partes[0].ToLowerInvariant()
                }
            }
            if (-not $esperada) { throw "SHA256SUMS no trae la suma de ${nombre}: no instalo nada." }
            $real = (Get-FileHash -Algorithm SHA256 -LiteralPath $instalador).Hash.ToLowerInvariant()
            if ($real -ne $esperada) {
                throw "la suma SHA-256 de $nombre no coincide con SHA256SUMS: no instalo nada."
            }
            Di "descarga comprobada (SHA-256 $esperada)."

            $registro = Join-Path $tmp 'instalador.log'
            $proceso = Start-Process -FilePath $instalador -Wait -PassThru -ArgumentList @(
                '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CURRENTUSER', "/LOG=`"$registro`"")
            if ($proceso.ExitCode -ne 0) {
                $cola = if (Test-Path $registro) { (Get-Content $registro -Tail 15) -join "`n" } else { '' }
                throw "el instalador terminó con el código $($proceso.ExitCode).`n$cola"
            }
        } finally {
            Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
        }

        $cotejo = Join-Path $env:LOCALAPPDATA 'Programs\Cotejo\bin\cotejo.exe'
        if (-not (Test-Path -LiteralPath $cotejo)) {
            throw "el instalador terminó pero no está $cotejo."
        }
        Di "instalada la $version en $(Split-Path (Split-Path $cotejo))."
        Di 'abre una terminal nueva (el PATH se lee al abrirla) y corre: cotejo doctor'
    } catch {
        Write-Host "Cotejo: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "Cotejo: puedes bajar el instalador a mano desde $repo/releases/latest" -ForegroundColor Red
    }
}
