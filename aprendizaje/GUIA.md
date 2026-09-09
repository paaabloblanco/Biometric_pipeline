# Guía de uso

Cómo se usan las tres skills y para qué sirve cada una. Léela una vez; después
el hook de arranque te recuerda solo lo que toca.

## La idea de fondo

El modo por defecto de este repo es: Claude implementa, tú lees la explicación.
Eso enseña a **reconocer** conceptos, no a **producirlos**. Y produce *fluidez
ilusoria*: la sensación de haber entendido que da leer algo bien explicado.

Las tres skills invierten la carga en tres momentos distintos:

| Skill | Qué te obliga a hacer | Cuándo |
|---|---|---|
| `/recordar` | **Recuperar** de memoria | Al empezar a trabajar |
| `/revisar` | **Modificar** con tus manos | Sobre el código que ya existe |
| `/explicar` | **Verbalizar** con tus palabras | Al cerrar una fase de un SDD |

Ninguna de las tres funciona si respondes "no me acuerdo" y esperas. El coste
de recordar **es** el aprendizaje; si te lo ahorras, no queda nada.

---

## `/recordar` — arranque, 4-6 preguntas

Sesión corta de recuperación. Empieza con esto antes de ponerte a programar.

**Qué hace:** lee `conceptos.md` y `errores.md`, mezcla temas recientes y
antiguos y pregunta de una en una. Nunca definiciones: predicción de output,
"encuentra el bug", comparar dos enfoques, aplicar un concepto a una parte del
repo donde no lo hemos usado.

**Qué se espera de ti:** comprometerte con una respuesta antes de ver la buena.
Si no te acuerdas, **da tu mejor intento igualmente** — fallar y luego corregir
fija mucho más que leer la respuesta correcta.

**Cierre:** confianza, área floja, y una acción de práctica.

> Las primeras veces te dirá que el registro está vacío y hará el repaso sobre
> el código del repo. Es correcto: no se inventa historial que no existe.

---

## `/revisar` — el grueso del trabajo

Repaso guiado de **un fichero por sesión**. Es la más importante de las tres,
porque casi todo el repo ya está escrito y leerlo no lo hace tuyo.

**Cómo va:**

1. **Reconstruir el modelo mental.** Empieza con una pregunta de ejecución
   concreta ("llega este POST, ¿qué hace la línea 34?"), no con una explicación.
   Van saliendo preguntas sobre flujo, estado, invariantes y **por qué está
   diseñado así**.
2. **Encontrar problemas.** Primero te pregunta cuál te parece la parte más
   frágil, y tienes que señalar un problema **tú** antes de que aporte los
   suyos. Cada hallazgo va etiquetado: `bug crítico`, `problema de diseño`,
   `mejora` o `preferencia de estilo`. Lo último no se toca.
3. **El cambio lo escribes tú.** Claude tiene prohibido editar el fichero. Te
   guía por la escalera de pistas:

   | Nivel | Qué te da |
   |---|---|
   | 0 | Una pregunta |
   | 1 | Dónde mirar |
   | 2 | El concepto de fondo |
   | 3 | La estrategia |
   | 4 | Pseudocódigo |
   | 5 | Un trozo de implementación |
   | 6 | El código completo |

   Empieza en 0 y sube **de uno en uno**, solo si lo pides. Después de escribir
   el cambio te pedirá que expliques por qué funciona y cómo lo verificarías.

**Salida de emergencia:** si dices *"hazlo tú"*, *"implementa"* o *"modo
shipping"*, vuelve a asistencia normal. Esto es un pipeline en producción; no
tienes que estudiar cada vez que tocas algo.

**Qué fichero toca:** el primero sin marcar en `repaso.md`. Marca `[x]` al
terminar. El hook de arranque te lo dice.

---

## `/explicar` — al cerrar una fase

Autoexplicación (*teach-back*). Cuando termines una fase de un SDD, en vez de
que Claude te resuma lo hecho, resumes tú.

**Te pedirá tres cosas:**

1. Explicarlo como a alguien que empieza,
2. con un ejemplo **concreto de este repo**,
3. y **un límite**: cuándo NO aplica, o qué se rompería.

El punto 3 es el que discrimina. Recitar qué es un serializador lo hace
cualquiera; saber cuándo no usarlo, no.

Mientras hablas te pinchará los términos vagos ("gestiona", "se encarga de")
pidiendo un ejemplo. Al final: confianza, lo más sólido, lo más flojo, el
concepto que ni mencionaste, una pregunta y un ejercicio.

**No te va a explicar el concepto antes.** Si lo hiciera, reconocerías su
explicación y confundirías reconocer con saber.

---

## El registro

- **`conceptos.md`** — comprensión duradera. El campo *"cuándo NO usarlo"* es
  el que importa: si no sabes rellenarlo, aún no lo entiendes.
- **`errores.md`** — bugs y malentendidos **con patrón**. Una errata no va.
  Guarda tu modelo mental original *y* el corregido, separados.
- **`repaso.md`** — checklist de ficheros para `/revisar`.

**Regla:** nunca se reescribe una entrada antigua. Lo valioso es ver qué creías
antes. Si tu modelo cambió otra vez, entrada nueva.

Va versionado en git a propósito: en una entrevista, un registro de modelos
mentales corregidos demuestra reflexión, cosa que un commit limpio no hace.

---

## Rutina sugerida

```
Al abrir Claude Code   → el hook te dice qué toca
Antes de programar     → /recordar        (5 min)
Sesión de estudio      → /revisar <fichero de repaso.md>
Al cerrar fase de SDD  → /explicar
Después de un bug feo  → entrada en errores.md
```

No hace falta hacer las tres cada día. `/revisar` una o dos veces por semana y
`/recordar` cuando te acuerdes ya cambia el resultado.

## Cómo saber si esto está funcionando

**Criterio, fijado el 2026-09-09:** si el 23 de septiembre no has usado ninguna
de las tres, el problema no se arregla añadiendo más comandos. Se replantea el
enfoque, no se amplía. Por eso se adoptaron 3 de las 12 del toolkit original y
no al revés.
