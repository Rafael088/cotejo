---
id: pro-8g7x
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: "La variable solo manda cuando el hogar es el de verdad (hogar is None). La prueba ahora la deja puesta apuntando a otro sitio y comprueba que ese sitio quede intacto: la prueba que habría cazado el fallo, en vez de la que lo tapaba"
---
# Instalar el protocolo contra un hogar de mentira escribió en el ~/.config/opencode de…

Instalar el protocolo contra un hogar de mentira escribió en el ~/.config/opencode de verdad, durante una prueba a mano

**Causa:** destinos() leía XDG_CONFIG_HOME del entorno aunque le pasaran otro hogar, así que la variable real le ganaba al directorio temporal. La prueba que debía cazarlo la borraba del entorno en su setUp, y por eso pasaba en verde

**Solución:** La variable solo manda cuando el hogar es el de verdad (hogar is None). La prueba ahora la deja puesta apuntando a otro sitio y comprueba que ese sitio quede intacto: la prueba que habría cazado el fallo, en vez de la que lo tapaba
