/* libjbig-0.dll de Cotejo: ocupa el sitio de la de jbigkit (GPL-2.0) sin una línea de su código.
 *
 * libtiff-6.dll la importa, y GTK 4 y gdk-pixbuf importan libtiff, así que Windows la carga al
 * abrir el board aunque Cotejo nunca lea ni escriba un TIFF comprimido con JBIG. Aquí están
 * las funciones que libtiff (tif_jbig.c) le pide, con la misma firma, y ninguna hace nada: el
 * decodificador contesta «no implementado» y libtiff lo da como error de esa imagen; el
 * codificador no produce datos. Código propio de Cotejo, bajo su licencia.
 */

typedef unsigned long long tamano; /* size_t en Win64 */

#define EXPORTA __declspec(dllexport)
#define JBG_EOK (0 << 4)
#define JBG_EIMPL (7 << 4)

struct jbg_dec_state;
struct jbg_enc_state;

EXPORTA void jbg_dec_init(struct jbg_dec_state *s) { (void)s; }

EXPORTA int jbg_dec_in(struct jbg_dec_state *s, unsigned char *datos, tamano largo, tamano *leidos) {
    (void)s; (void)datos; (void)largo;
    if (leidos) *leidos = 0;
    return JBG_EIMPL;
}

EXPORTA unsigned long jbg_dec_getsize(const struct jbg_dec_state *s) { (void)s; return 0; }

EXPORTA unsigned char *jbg_dec_getimage(const struct jbg_dec_state *s, int plano) {
    (void)s; (void)plano;
    return 0;
}

EXPORTA void jbg_dec_free(struct jbg_dec_state *s) { (void)s; }

EXPORTA void jbg_enc_init(struct jbg_enc_state *s, unsigned long x, unsigned long y, int planos,
                          unsigned char **p, void (*salida)(unsigned char *, tamano, void *),
                          void *archivo) {
    (void)s; (void)x; (void)y; (void)planos; (void)p; (void)salida; (void)archivo;
}

EXPORTA void jbg_enc_out(struct jbg_enc_state *s) { (void)s; }

EXPORTA void jbg_enc_free(struct jbg_enc_state *s) { (void)s; }

EXPORTA int jbg_newlen(unsigned char *bie, tamano largo) { (void)bie; (void)largo; return JBG_EOK; }

EXPORTA const char *jbg_strerror(int error) {
    (void)error;
    return "JBIG no disponible en Cotejo para Windows";
}
