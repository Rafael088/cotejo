---
id: apr-6ujb
fecha: 2026-10-08
temas: [empaquetado, linux, seguridad]
---
# makepkg graba la ruta de compilación (con el usuario) en el .BUILDINFO del paquete Arch

Al compilar con construir.sh --arch dentro del repo, makepkg escribe builddir y startdir en el .BUILDINFO, y el paquete publicado expone /home/<usuario>/... de la máquina de compilación. purga.py lo detecta, pero no se puede poner en lista blanca porque el archivo lo genera makepkg. Hay que compilar fuera del repo y del home (DIST=/tmp/cotejo-arch sh empaquetado/linux/construir.sh --arch) y repetir la purga sobre el artefacto final antes de subirlo.
