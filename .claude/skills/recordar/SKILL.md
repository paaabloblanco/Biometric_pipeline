---
name: recordar
description: Práctica de recuperación (retrieval practice) — sesión corta de repaso sobre aprendizaje/ y el código del repo, con preguntas de predicción y aplicación. Úsala al empezar a trabajar, o cuando el usuario pida repasar.
---

# Sesión de recuperación

Recordar algo cuesta, y ese coste es lo que consolida la memoria. Releer no
cuesta y por eso no consolida. Esta skill hace trabajar a la memoria, no a la
lectura.

## Antes de empezar

Lee `aprendizaje/conceptos.md` y `aprendizaje/errores.md`.

**Si están vacíos o solo tienen la plantilla, dilo y para.** No inventes
historial de aprendizaje: preguntar sobre cosas que el usuario nunca registró
convierte el repaso en un examen aleatorio. En ese caso ofrece hacer una
sesión sobre el código del repo (`supabase_data`, `bot/services`, `api/`) y
pide permiso.

## Selección

Mezcla **reciente y antiguo**. Lo antiguo es lo que está a punto de olvidarse,
y por eso es donde el repaso rinde más — recuperar algo justo cuando cuesta
consolida mucho más que recuperar algo fresco. Prioriza:

- entradas de `errores.md` con categoría *modelo mental* o *suposiciones*,
- conceptos cuyo campo "cuándo NO usarlo" quedó en blanco,
- decisiones de arquitectura del repo (`managed=False`, capa de servicio, JWT
  vs sesiones, estado conversacional en memoria del bot).

## Formato de las preguntas

**Nunca preguntes definiciones.** "¿Qué es un serializador?" se contesta de
memoria sin entender nada. Usa estas formas:

- **Predicción:** te enseño un fragmento, dime qué imprime / qué SQL genera /
  qué falla.
- **Por qué funciona (o falla) este patrón:** aquí está el código, explica el
  mecanismo.
- **Encuentra el bug:** fragmento corto con un fallo plantado.
- **Compara dos enfoques:** cuál elegirías aquí y qué pierdes.
- **Transferencia:** aplica el concepto a un contexto **nuevo** del repo, uno
  donde no lo hayamos usado. Esto es lo que de verdad mide comprensión.

## Reglas de conducción

- Una pregunta cada vez.
- **Espera a que se comprometa con una respuesta antes de revelar nada.** Si
  dice "no me acuerdo", pide igualmente su mejor intento: un intento fallido
  seguido de la corrección fija mucho mejor que la respuesta directa.
- Corta cuando lleve 4-6 preguntas. Es un calentamiento, no un examen.
- **Dificultad adaptativa:** si acierta seguido, sube — más restricciones, más
  transferencia. Si falla seguido, baja al prerequisito en vez de repetir.

## Cierre

Termina con exactamente tres cosas: una valoración de confianza, un área
floja, y una acción de práctica concreta.
