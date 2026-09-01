# SDD — Nevera

Documento de diseño. Estado: **propuesta**. Fecha: 2026-08-29.

## 1. Objetivo

Llevar un inventario vivo de lo que hay en la nevera/despensa y usarlo para:

1. Sugerir qué cocinar según lo que tienes, priorizando lo que caduca antes y
   ajustando la sugerencia a tu estado de recuperación reciente.
2. Actualizar el inventario automáticamente cuando confirmas que has hecho una
   comida (se descuentan los ingredientes usados).
3. Dar de alta la compra rápido: transcribes el ticket/lista con una IA
   externa y se lo pasas al bot en texto.
4. Antes de ir a comprar, cruzar lo que necesitas con las ofertas vigentes de
   Biedronka para aprovecharlas.

El bot de Telegram (`docs/SDD-telegram-bot.md`) es la interfaz; este documento
no repite su arquitectura de polling/allowlist, ya resuelta allí.

No objetivos de esta iteración:
- Control de stock por unidades exactas de peso en cada consumo (aceptamos
  estimaciones — ver §4).
- Lista de la compra colaborativa / multiusuario.
- Reconocimiento de imágenes dentro del propio bot (ver decisión de ingesta).

## 2. Decisión de arquitectura: Supabase, no JSON

**Opción elegida: tabla(s) en Supabase (Postgres), vía Django ORM**, igual que
`supabase_data` ya hace con las tablas de salud.

**Opción descartada: JSON en disco.**

Motivos:
- **Concurrencia real**: el inventario lo va a escribir el bot (comandos
  `/añadir`, `/hecho`) y potencialmente un flujo de `/comprar` en el mismo
  proceso o en otro. Un fichero JSON no tiene control de escrituras
  concurrentes; Postgres sí (transacciones, `update_or_create`).
- **Consultas, no solo lectura completa**: necesitamos "qué caduca en los
  próximos N días", "cuánto tengo de X", "resta 200 g de Y" — eso es SQL/ORM
  natural. En JSON habría que reimplementar índices y filtros a mano.
- **Consistencia con el resto del proyecto**: ya existe el patrón
  `supabase_data/models.py` (modelos `managed=False` sobre tablas creadas a
  mano en Supabase) + `services.py` (funciones de acceso). La nevera encaja
  como una app más de ese mismo patrón, no como una tecnología nueva.
- JSON solo tendría sentido como prototipo desechable; esto va a ser un
  componente que se usa a diario.

## 3. Modelo de datos

Nueva tabla `nevera_items`, esta vez **gestionada por Django** (`managed=True`,
migración normal `nevera/migrations/0001_initial.py`) a diferencia de
`supabase_data`, porque es una tabla propia del proyecto y no algo creado por
una herramienta externa de sync:

| Campo | Tipo | Notas |
|---|---|---|
| `id` | bigint PK | |
| `nombre` | text | Normalizado (minúsculas, sin acentos, espacios colapsados) para agrupar duplicados (ej. "Leche entera" → "leche entera"). |
| `cantidad` | numeric | **Siempre en la unidad base de su magnitud** (ver §3.1) — nunca en la unidad tal cual la escribiste. |
| `unidad` | text | Unidad base: `g` (masa), `ml` (volumen) o `ud` (cuenta). |
| `categoria` | text, nullable | proteína / lácteo / verdura / fruta / otros — la infiere la IA al dar de alta. |
| `fecha_caducidad` | date, nullable | No siempre se conoce (ej. congelados sin fecha visible). |
| `fecha_añadido` | timestamptz | `auto_now_add`. |
| `origen` | text | `compra` \| `manual`. |

Restricción única `(nombre, unidad)` — al ser `unidad` siempre la unidad base,
esto agrupa correctamente aunque compres en unidades distintas cada vez.

### 3.1 Normalización de unidades (`nevera/units.py`)

Resuelve el riesgo detectado en revisión: sin esto, "leche 1L" y "leche 500ml"
se guardaban como dos filas distintas y fragmentaban el inventario.

- Cada unidad reconocida (`g`, `gr`, `kg`, `ml`, `l`, `ud`, `uds`, sus plurales…)
  se mapea a una magnitud (`masa`, `volumen`, `unidad`) y a un factor hacia la
  unidad base de esa magnitud (`g`, `ml`, `ud` respectivamente).
- `add_items` y `consume_items` convierten la cantidad de entrada a la unidad
  base **antes** de tocar la tabla, así que "1kg" y "500g" del mismo producto
  se suman en la misma fila.
- Unidad no reconocida → `ValueError`. Se prefiere fallar alto a guardar una
  unidad inconsistente que rompa el matching más adelante.
- `format_cantidad()` deshace la conversión para mostrar cifras legibles en
  `/nevera` (ej. 1500 g → "1.5 kg").

Tabla auxiliar `nevera_movimientos` (alta/baja con motivo) — descartada para
la iteración 1, ver decisión C (§7).

## 4. Componentes

Nueva app `nevera/` (paralela a `supabase_data/`, mismo patrón):

```
nevera/
  models.py     # NeveraItem (managed=True, migración propia)
  units.py      # to_base(), format_cantidad() — normalización de unidades (§3.1)
  services.py   # add_items(), get_items_by_expiry(), consume_items(),
                # delete_item(), edit_item(), list_all()
```

Nuevos handlers en `bot/handlers.py` (sin lógica de negocio, igual que ahora):

| Comando | Acción |
|---|---|
| `/añadir <texto>` | Parsea el texto transcrito de una foto de compra (o escrito a mano) con Gemini → estructura a items → `nevera.services.add_items()`. Responde con lo que ha entendido para que confirmes antes de guardar (ver §7-A). |
| `/nevera` | Lista el inventario actual agrupado por categoría, marcando lo que caduca en ≤3 días. Cada item muestra su `id` para poder editarlo/borrarlo. |
| `/borrar <id>` | Borra un item por id (`nevera.services.delete_item`). Para corregir un alta equivocada una vez ya confirmada. |
| `/editar <id> <campo>=<valor> ...` | Edita cantidad/unidad/categoría/caducidad de un item (`nevera.services.edit_item`). |
| `/comer` | Sugerencia de qué cocinar: cruza inventario (priorizando caducidad) + último `ai_analysis_log` (estado de recuperación) → prompt a Gemini → receta(s) propuestas. |
| `/hecho <receta o ids>` | Confirma que has hecho una comida sugerida → `consume_items()` descuenta el inventario. |
| `/comprar <texto>` | Recibe el texto de la gazetka/ofertas (transcrito manualmente, sin scraping — ver §5.4) y dice qué merece la pena aprovechar según el inventario actual. Solo lectura. |

## 5. Flujos

### 5.1 Alta de compra (texto ya transcrito)

```
Tú: le pasas la foto del ticket/compra a una IA externa (fuera del bot)
Tú → bot: /añadir "<texto transcrito>"
bot: Gemini estructura el texto → lista de {nombre, cantidad, unidad, categoría, caducidad?}
bot → "He entendido: 2x leche (1L), 500g pollo, ... ¿confirmo? (sí/no)"
Tú: confirmas
bot: nevera.services.add_items(...)  # update_or_create por nombre normalizado, suma cantidades
```

Se elige transcripción manual (tú pasas el texto ya extraído) en vez de que el
bot reciba la foto y la mande él mismo a una IA con visión: menos superficie
en el bot, reutilizas la IA que prefieras para OCR sin acoplarla al proyecto.

### 5.2 Sugerencia de comida

```
Tú → bot: /comer
bot: nevera.services.get_items_by_expiry()  # ordenado, lo que caduca antes primero
bot: supabase_data.services.get_recent_analyses(1)  # último análisis de Gemini = estado de recuperación
bot: prompt a Gemini con ambos → receta(s) usando lo que caduca antes, ajustada a cómo estás
bot → receta(s) + "cuando la hagas, /hecho <n>"
```

Usar el último `ai_analysis_log` como fuente del estado de recuperación evita
que tengas que describirlo cada vez; el coste es que si aún no has pedido
`/analisis` ese día, la sugerencia usa el análisis más reciente disponible
(no el de hoy). Aceptable — se avisa en la respuesta con la fecha del análisis
usado.

### 5.3 Confirmación y descuento dinámico

```
Tú → bot: /hecho 1
bot: nevera.services.consume_items(receta_1.ingredientes)
     # resta cantidades; si un item llega a 0 (o negativo), se elimina/marca agotado
bot → "Actualizado. Te queda: ..."
```

### 5.4 Compra inteligente con ofertas Biedronka

```
Tú: le pasas al bot el texto de las ofertas (transcrito de la app oficial, Blix, o donde las mires)
Tú → bot: /comprar "<texto de la gazetka>"
bot: nevera.services.list_all()  # inventario actual
bot: nevera.ofertas.analizar_ofertas(texto, inventario) → Gemini prioriza qué aprovechar
bot → lista de ofertas que merece la pena aprovechar, con motivo
```

**Cambio respecto al diseño original — el scraping automático no es viable
sin navegador headless.** Antes de implementar se probaron en vivo las dos
fuentes de la decisión E:
- `biedronka.pl`: la sección de gazetka son páginas de imágenes escaneadas
  (visor tipo pasa-páginas), sin texto ni datos de producto/precio.
- `blix.pl` (el agregador previsto como fallback): la rejilla de productos
  con precios se renderiza por JavaScript en el cliente — una petición HTTP
  simple no devuelve ningún precio, solo un puñado de ejemplos sueltos
  embebidos en el FAQ (schema.org), insuficiente para comparar contra la
  nevera.

Se decidió (2026-08-29, con el usuario) **no** añadir un navegador headless
(Playwright) por el coste de mantenimiento que supondría para un comando de
uso personal bajo demanda. En su lugar, el fallback manual que ya estaba
diseñado como red de seguridad pasa a ser **el flujo único de `/comprar` en
esta iteración**: no hay scraping, `/comprar` siempre recibe el texto de las
ofertas como argumento, igual que `/anadir` recibe el texto de la compra.
`/comprar` es de solo lectura (no escribe en `nevera_items`), así que no
necesita el paso de confirmación sí/no de la decisión A.

Si en el futuro se quiere automatizar la obtención de ofertas, la vía sería
Playwright/Selenium contra `blix.pl` — queda fuera de esta iteración.

## 6. Riesgos / notas

- **Parseo de texto de compra por IA**: el formato del texto transcrito varía
  según la IA externa que uses. `/añadir` debe ser tolerante y siempre mostrar
  lo que ha entendido antes de guardar (§5.1) para evitar altas erróneas
  silenciosas.
- **Normalización de nombres**: "Leche entera" y "leche" deben agregarse como
  el mismo item o la nevera se llena de duplicados. Normalizar en minúsculas +
  quitar acentos como mínimo; matching más fino (sinónimos) queda para una
  iteración posterior si hace falta.
- **Fragmentación por unidad — resuelto con §3.1**: ya no es un riesgo abierto;
  `to_base()` unifica cualquier unidad reconocida a la unidad base de su
  magnitud antes de guardar o consumir.
- **Scraping Biedronka**: es un sitio público de ofertas al consumidor, uso
  personal y bajo demanda (no masivo/automatizado en bucle) — bajo riesgo,
  pero conviene meter caché y no golpear la web en cada mensaje.
- **Cuota de Gemini en `/añadir`, `/comer`, `/comprar`**: a diferencia de
  `/analisis`, estos comandos no tienen lock de "una llamada a la vez".
  Aceptado como responsabilidad del usuario para esta iteración, no como
  gap a resolver en el diseño.

## 7. Decisiones

- **A. Confirmación en `/añadir`**: **pide sí/no antes de guardar**. El bot
  muestra lo que ha entendido del texto transcrito y espera confirmación en
  el chat antes de escribir en `nevera_items`. Requiere estado conversacional
  simple en el handler (guardar la propuesta pendiente por `chat_id` hasta
  que confirmes o la descartes). _(resuelto 2026-08-29)_
- **B. Formato de `/hecho`**: **por índice de la sugerencia** (`/hecho 1`),
  ligado a la última sugerencia de `/comer` en esa sesión/chat. Determinista,
  sin ambigüedad en qué ingredientes restar. _(resuelto 2026-08-29)_
- **C. `nevera_movimientos`**: **no en la iteración 1**. `NeveraItem` con
  `update_or_create` basta para empezar; se añade más adelante si hace falta
  depurar consumos o dar histórico a Gemini. _(resuelto 2026-08-29)_
- **D. Caducidad desconocida**: items sin fecha (congelados, secos) **se
  excluyen del ranking de urgencia** pero siguen apareciendo como disponibles
  en `/comer`. _(resuelto 2026-08-29)_
- **E. Fuente de scraping de Biedronka**: **descartado — ninguna de las dos
  fuentes es scrapeable sin navegador headless.** Se probaron en vivo
  `biedronka.pl` (gazetka = imágenes escaneadas) y `blix.pl` (precios
  renderizados por JS, no presentes en el HTML plano). En vez de invertir en
  Playwright para un comando personal bajo demanda, `/comprar` usa
  directamente el fallback manual como único flujo (ver §5.4).
  _(resuelto 2026-08-29, revisado tras probar ambas fuentes en fase 4)_
- **F. Fragmentación por unidad**: **normalizar a unidad base por magnitud**
  (`g`/`ml`/`ud`) en `nevera/units.py`, aplicado en `add_items` y
  `consume_items` (ver §3.1). Cierra el riesgo detectado en revisión de que
  el mismo producto en distinta unidad se guardara como filas separadas.
  _(resuelto 2026-08-29, implementado en fase 1)_
- **G. Corrección de altas ya guardadas**: se mantiene la decisión A tal cual
  (confirmación sí/no antes de guardar) y se añaden `/borrar` y `/editar`
  como comandos de la fase 2, para corregir un item después de confirmado sin
  tocar la base a mano. _(resuelto 2026-08-29)_
- **H. Básicos de despensa**: nuevo campo `NeveraItem.es_basico`, que
  **refina la decisión D**. Esta reservaba `fecha_caducidad = NULL` para todo
  lo que no tuviera fecha, pero el NULL quedaba semánticamente sobrecargado:
  valía a la vez para "no caduca en la práctica" (sal, especias, aceite) y
  para "es perecedero pero no anoté la fecha" (el pollo). Con el campo
  explícito, el NULL recupera un único significado y el discriminador queda
  separado de `categoria`, que es taxonomía nutricional y sí se usa para
  razonar en los prompts.

  Un básico se gestiona **por presencia** (hay / no hay), no por cantidad —
  su `cantidad` es un valor testigo. En consecuencia: queda fuera del ranking
  de urgencia, `consume_items` no le descuenta nada, aparece en un bloque
  `DESPENSA` aparte del prompt de `/comer` y solo sale del inventario al
  borrarlo a mano. Esto cierra un fallo real: una receta con "sal: 1 ud"
  llegaba a `consume_items`, dejaba la cantidad en 0 y **borraba la sal**.

  Trade-off aceptado: el stock de básicos deja de ser automático y pasa a ser
  declarativo (si se acaba el aceite, hay que decirlo). A cambio no hay que
  pesar la cúrcuma. La alternativa de recuento periódico (*cycle counting*)
  es sobreingeniería para un pipeline personal.
  _(resuelto 2026-09-01, implementado en la misma fecha)_

## 8. Plan de implementación (por fases)

1. [hecho] **Tabla y modelo**: `nevera_items` vía migración de Django +
   `nevera/models.py` + `nevera/units.py` + `nevera/services.py`
   (`add_items`, `get_items_by_expiry`, `consume_items`, `delete_item`,
   `edit_item`, `list_all`). Verificado con 17 tests contra la base real
   (`nevera/tests/test_services.py`, `nevera/tests/test_units.py`).
2. [hecho] **`/anadir`, `/nevera`, `/borrar`, `/editar`**: alta con
   confirmación sí/no (`/confirmar` / `/cancelar`) + listado del inventario
   agrupado por categoría con alerta de caducidad + corrección de altas.
   `nevera/parsing.py` estructura el texto transcrito vía Gemini
   (reutilizando `health_ai.pruebas.send_prompt_to_gemini`). Verificado con
   23 tests en `nevera/tests/` + 32 en `bot/tests/` y una prueba manual
   end-to-end contra la Supabase real (parseo mockeado, alta, edición con
   conversión de unidad y borrado). Nota: el comando de Telegram es
   `/anadir` sin ñ — Telegram solo admite `[a-z0-9_]` en nombres de comando.
3. [hecho] **`/comer` y `/hecho`**: `nevera/suggestions.py` cruza el
   inventario ordenado por caducidad (`get_items_by_expiry`) con el último
   `ai_analysis_log` y pide a Gemini 1-3 recetas en JSON (nombre, descripción,
   ingredientes con nombre EXACTO del inventario). `/comer` guarda la
   sugerencia por `chat_id`; `/hecho <n>` la referencia por índice (decisión
   B) y llama a `consume_items()`. Verificado con 8 tests de
   `nevera/tests/test_suggestions.py` + 7 de `bot/tests/` (39 en total) y una
   prueba end-to-end contra la Supabase real (alta → sugerencia con Gemini
   mockeado usando nombres reales del inventario → confirmación → descuento
   verificado en BD).
4. [hecho] **`/comprar`**: sin scraping (ver decisión E revisada) — recibe el
   texto de las ofertas como argumento y `nevera/ofertas.py` lo cruza con el
   inventario vía Gemini, priorizando reponer lo que falta/escasea y
   descartando ofertas de ultraprocesados. Solo lectura, sin confirmación.
   Verificado con 7 tests de `nevera/tests/test_ofertas.py` + 4 de
   `bot/tests/` (43 en total) y una prueba end-to-end contra la Supabase real
   confirmando que el inventario real entra en el prompt.
5. Revisar el uso real contra la decisión D (`/comer` con último análisis) y
   el punto de cuota de Gemini en los comandos nuevos (§6) y ajustar si hace
   falta — quedan fuera de esta iteración por decisión explícita del usuario.
   Si en el futuro se quiere automatizar `/comprar` con scraping real,
   evaluar Playwright contra `blix.pl` como trabajo aparte.
