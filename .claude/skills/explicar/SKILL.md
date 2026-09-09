---
name: explicar
description: Autoexplicación (teach-back) — el usuario explica un concepto o una fase recién terminada con sus palabras y Claude lo evalúa sin rellenarle los huecos. Úsala al cerrar una fase de un SDD, o cuando el usuario diga "explícame X" y convenga comprobar primero qué sabe ya.
---

# Examinador de autoexplicación

El objetivo es exponer la **fluidez ilusoria**: la sensación de haber entendido
que produce leer una explicación clara. Explicar con palabras propias la rompe;
volver a leer, no.

## Regla que gobierna todo lo demás

**No expliques el concepto tú.** Ni al principio, ni "para situar", ni
completando una frase que el usuario deja a medias. Si lo haces, la skill no
sirve para nada: el usuario reconocerá tu explicación y confundirá reconocer
con saber.

Si pide directamente la respuesta, dásela — pero solo después de pedirle una
vez que lo intente.

## Procedimiento

1. **Fija el objeto.** Un concepto, una decisión de diseño o la fase de SDD que
   se acaba de cerrar. Uno solo; si hay varios, elige el más central y dilo.

2. **Pide la explicación** en este formato exacto:
   - explícalo como si se lo enseñaras a alguien que empieza,
   - con **un ejemplo concreto de este repo** (no genérico),
   - y **un límite o contraejemplo**: cuándo NO aplica, o qué se rompería.

   El límite es la parte que discrimina. Casi todo el mundo puede recitar qué
   es un serializador; mucha menos gente sabe decir cuándo no usarlo.

3. **Espera.** Una sola pregunta cada vez. No encadenes.

4. **Sonda, no corrijas todavía.** Cuando use un término vago ("gestiona",
   "se encarga de", "lo maneja"), pide que lo defina con un ejemplo concreto.
   Busca: afirmaciones inexactas, omisiones, contradicciones, modelo mental
   difuso, errores de terminología.

   **Separa error de terminología de error conceptual.** Decir "instancia"
   donde toca "clase" entendiendo la diferencia es lo primero; no es grave y
   se corrige en una línea. Creer que `managed=False` impide escribir en la
   tabla es lo segundo, y eso sí importa.

5. **Cuando el usuario diga que ha terminado**, y no antes, entrega:
   - **Confianza:** alta / media / baja, y por qué
   - **Lo más sólido:**
   - **Lo más flojo:**
   - **Concepto ausente:** lo que ni siquiera mencionó
   - **Una pregunta de seguimiento**
   - **Un ejercicio recomendado** (pequeño, verificable)

6. **Corrige solo lo necesario** y pide que **reformule la idea reparada** con
   sus palabras. Sin ese último paso la corrección se olvida.

## Al terminar

Si salió un malentendido con patrón o una comprensión que costó, propón una
entrada en `aprendizaje/conceptos.md`. **Solo si es duradero.** No conviertas
cada sesión en una entrada: un registro inflado no se repasa.
