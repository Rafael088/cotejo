---
id: pro-sms0
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: "Un flag de ensayo independiente del motor; comprobar() del motor pedido sigue corriendo y se enseña el argv sin lanzar (PR #15)"
---
# despachar --motor X --simular tomaba la tarea (agente) o lanzaba el cliente de verdad…

despachar --motor X --simular tomaba la tarea (agente) o lanzaba el cliente de verdad (headless)

**Causa:** --motor explícito ganaba la resolución del motor y tomar solo miraba si el motor se llamaba «simulado»

**Solución:** Un flag de ensayo independiente del motor; comprobar() del motor pedido sigue corriendo y se enseña el argv sin lanzar (PR #15)
