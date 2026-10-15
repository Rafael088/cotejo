---
id: pro-ye5o
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: serve_forever(poll_interval=0.02)
---
# Las pruebas contra el Notion de mentira tardaban 12 s cuando la batería entera tardaba 1 s

Las pruebas contra el Notion de mentira tardaban 12 s cuando la batería entera tardaba 1 s

**Causa:** ThreadingHTTPServer.serve_forever sondea cada 0,5 s y shutdown() espera un intervalo entero en cada prueba

**Solución:** serve_forever(poll_interval=0.02)
