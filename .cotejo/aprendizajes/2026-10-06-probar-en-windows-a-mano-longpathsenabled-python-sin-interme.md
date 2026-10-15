---
id: apr-2es5
fecha: 2026-10-06
temas: [windows, pruebas, empaquetado]
---
# Probar en Windows a mano: LongPathsEnabled, Python sin intermedios TLS y scripts que se puedan repetir

1) LongPathsEnabled viene en 0 en un Windows normal y en 1 en el runner windows-latest: un script que pasa en CI puede reventar en un PC; que lo compruebe al arrancar (winreg) y diga el comando. 2) El OpenSSL de Python solo ve el almacén de Windows y no baja certificados intermedios; SChannel sí. En un Windows recién instalado, urllib falla contra cadenas nuevas (Let's Encrypt YE1) hasta que algo del sistema construye la cadena una vez; truststore lo evita. 3) subprocess con text=True sin encoding decodifica en cp1252: pasar siempre encoding="utf-8" al leer la salida de cotejo. 4) En CI cada máquina es nueva y no se ve que un script deja carpetas con nombre fijo en %TEMP%: probar a mano dos veces seguidas lo destapa. 5) Sin minutos de Actions, un git bundle en una USB más un prompt para el Claude de Windows sustituye al runner (informes en cotejo-1.2-windows-informe y -v2).
