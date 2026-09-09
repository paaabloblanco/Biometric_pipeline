# Registro de aprendizaje

Este directorio es **tuyo**, no del proyecto: no lo lee ningún proceso, no
afecta al pipeline. Existe porque el código del repo demuestra que *funciona*
algo, pero no demuestra que lo *entiendas*. Esto sí.

Va versionado en git a propósito. En una entrevista o revisando el portfolio,
un `aprendizaje/errores.md` con modelos mentales corregidos dice más que un
commit limpio: demuestra reflexión, no solo output.

## Qué se apunta y qué no

Se apunta lo **duradero**: una idea equivocada que tenías y ya no tienes, un
concepto que ahora podrías explicarle a otro, un bug cuya causa era conceptual.

**No** se apunta cada interacción, ni definiciones sueltas, ni erratas. Si esto
se convierte en un libro de texto, deja de servir: nadie repasa un libro de
texto a diario.

## Reglas

- **Nunca se reescribe una entrada antigua.** El valor está justo en ver qué
  creías antes. Si tu modelo mental cambió otra vez, se añade entrada nueva.
- **Tu explicación original y la corregida van separadas.** Si se funden, se
  pierde la señal de dónde estaba el hueco.
- Fecha absoluta (`YYYY-MM-DD`) en cada entrada.
- Entradas cortas. Si no cabe en pantalla, sobra.

## Ficheros

| Fichero | Para qué |
|---|---|
| `conceptos.md` | Comprensión duradera: qué es, por qué existe, cuándo NO usarlo |
| `errores.md` | Bugs y malentendidos con patrón; incluye la causa raíz conceptual |

Se alimentan desde `/explicar` (autoexplicación al cerrar una fase) y `/revisar`
(repaso de código ya escrito). Se releen desde `/recordar`.
