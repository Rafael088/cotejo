---
id: pro-5jhh
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: "Rama rescate/medidor-ahorro para protegerlos, y portados a mano encima del rediseño en 0c81faf (ahorro) y 770e74d (crear). Para detectar otros: git fsck --unreachable --no-reflogs y mirar las puntas"
---
# El medidor de ahorro y el verbo crear desaparecieron de la app, aunque la tarea del…

El medidor de ahorro y el verbo crear desaparecieron de la app, aunque la tarea del medidor ya estaba marcada como hecha

**Causa:** Vivían en una línea de commits del 2026-09-18 (b104841..b3b1256) que se separó en c8fb0c1 y nunca se unió: la rama principal siguió por 297e192. Quedaron como commits huérfanos, sin rama y sin reflog, a un git gc de borrarse

**Solución:** Rama rescate/medidor-ahorro para protegerlos, y portados a mano encima del rediseño en 0c81faf (ahorro) y 770e74d (crear). Para detectar otros: git fsck --unreachable --no-reflogs y mirar las puntas
