/* liblzo2-2.dll de Cotejo: ocupa el sitio de la de LZO (GPL-2.0-or-later) sin una línea de su código.
 *
 * La importa libcairo-script-interpreter-2.dll, y GTK 4 importa ese intérprete (lee los nodos
 * «cairo» de los archivos de nodos de GSK), así que Windows la carga al abrir el board aunque
 * Cotejo nunca lea un script de cairo. Aquí están las dos funciones que el intérprete le pide,
 * con la misma firma, y las dos fallan: al comprimir, cairo se queda con el texto sin comprimir;
 * al descomprimir, da error ese script. Código propio de Cotejo, bajo su licencia.
 *
 * `*largo_salida` no se toca: si el ancho de lzo_uint no fuera el que se cree, escribirlo
 * pisaría memoria ajena, y quien llama no lo lee cuando la función falla.
 */

#define EXPORTA __declspec(dllexport)
#define LZO_E_ERROR (-1)

EXPORTA int lzo2a_999_compress(const unsigned char *origen, unsigned long long largo,
                               unsigned char *destino, void *largo_salida, void *trabajo) {
    (void)origen; (void)largo; (void)destino; (void)largo_salida; (void)trabajo;
    return LZO_E_ERROR;
}

EXPORTA int lzo2a_decompress(const unsigned char *origen, unsigned long long largo,
                             unsigned char *destino, void *largo_salida, void *trabajo) {
    (void)origen; (void)largo; (void)destino; (void)largo_salida; (void)trabajo;
    return LZO_E_ERROR;
}
