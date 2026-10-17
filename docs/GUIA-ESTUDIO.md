# Guía de estudio del proyecto

Mapa del repo para leerlo sin conexión y con criterio propio. No es
documentación de uso (eso está en `CLAUDE.md` y en los SDD de `docs/`): es una
**ruta de estudio**. Está escrita para un objetivo concreto: que puedas
reescribir las partes que no te convenzan y defender por qué.

Escrita el 2026-10-17 sobre la rama `feat/web-acciones-ia` (el estado más
avanzado del proyecto). Si lees esto desde `main` después de un merge, es el
mismo código.

---

## 0. Cómo usar este documento

Tres formas, según cuánto tiempo tengas:

- **Media hora:** §1 (qué es) + §2 (mapa de carpetas) + §7 (decisiones
  discutibles). Te devuelve el contexto perdido.
- **Un viaje largo:** la ruta de estudio de §4, en orden, con el código
  delante. Son 7 etapas; cada una te deja algo que sabrías explicar en una
  entrevista.
- **Si vienes a cambiar cosas:** §7 directamente. Son las decisiones que tomé
  yo y que tienen alternativa real. Para cada una está el trade-off, para que
  discutas con algo en la mano y no a ciegas.

**Antes de leer código, intenta responder tú.** Cada etapa de §4 acaba en
preguntas. Si las lees y pasas, te quedará la sensación de haber entendido sin
el aprendizaje. Si las contestas en voz alta o por escrito antes de mirar, se
te queda. Es la diferencia entre reconocer y producir.

---

## 1. Qué es el proyecto, en una frase

Un **pipeline biométrico personal de un solo usuario**: coge los datos de tu
reloj, los guarda en un Postgres, se los pasa a un modelo de IA para que los
interprete, y te lo sirve por dos interfaces (un bot de Telegram y una web).
Encima lleva un inventario de nevera que usa IA para sugerirte qué cocinar.

Son **cuatro flujos** independientes que comparten una base de datos:

```
  [Reloj] --Health Connect--> [SQLite export en un .zip de Drive]
                                        |
                                 extractor.py  (lee SQLite, sube filas)
                                        v
                               [Postgres en Supabase]  <-- única fuente de verdad
                                   ^         |
                                   |         +--> health_ai/  (prompt -> Gemini -> guarda el análisis)
                                   |                  ^
                      +------------+------------+      |
                      |                         |      |
                  bot/  (Telegram)         api/  (REST, DRF)
                      |                         |
                [tu móvil]                frontend/  (SPA React en Vercel)
```

La frase que resume la arquitectura: **toda la lógica vive en los
`services.py`, y el bot y la API son dos pieles finas sobre ellos**. Esa es la
decisión de la que cuelga todo lo demás, y la primera que deberías poner en
duda si no te convence (§7.1).

---

## 2. Mapa de carpetas

Monorepo: todo el Python en `backend/`, la SPA en `frontend/`. Los comandos de
Python se ejecutan **desde `backend/`**.

### `backend/core/` — el proyecto Django

El "cableado", no la aplicación. Lo que Django necesita para arrancar.

| Fichero | Qué hace |
|---|---|
| `settings/__init__.py` | **Selector de entorno.** Lee `DJANGO_ENV` y hace `from core.settings.dev import *` o `prod`. Así el resto del proyecto siempre apunta a `core.settings` y nunca cambia. |
| `settings/base.py` | Config común: apps instaladas, `DATABASES` (credenciales desde `.env`), DRF, JWT. |
| `settings/dev.py` | `DEBUG=True`, hosts locales, CORS a `localhost:5173`. |
| `settings/prod.py` | `DEBUG=False`, hosts y CORS **obligatorios** por variable de entorno, cabeceras de seguridad. Hoy no se usa: no hay despliegue. |
| `urls.py` | Monta `/admin/` y `/api/`. |
| `wsgi.py` / `asgi.py` | Puntos de entrada para un servidor real. Generados por Django, nunca tocados. |

### `backend/supabase_data/` — los datos del reloj (SOLO LECTURA)

La app más importante para entender el proyecto, y la que tiene la regla más
rara: **`managed = False`**.

| Fichero | Qué hace |
|---|---|
| `models.py` | 5 modelos sobre tablas que Django **no creó**: `HeartRateSamples`, `OxygenSaturationSamples`, `RestingHeartRateSamples`, `SleepStages`, `AiAnalysisLog`. Todos `managed = False`. |
| `services.py` | **553 líneas, el fichero con más lógica del repo.** Agregaciones: último día con datos, series por día, y toda la reconstrucción del sueño (deduplicar fases solapadas, decidir a qué día pertenece una noche, calcular minutos reales). |
| `admin.py` | Registro en el admin de Django para mirar las tablas a mano. |

> **`managed = False` explicado.** Normalmente defines un modelo, lanzas
> `makemigrations` + `migrate`, y Django crea la tabla. Aquí es al revés: las
> tablas las crea el sync externo, y el modelo solo las **describe** para poder
> consultarlas con el ORM. `managed = False` le dice a Django "lee y escribe
> filas, pero no toques el esquema ni intentes crear esto en los tests". Lo que
> ganas: usas el ORM sin pelearte por quién manda en el esquema. Lo que
> pierdes: el modelo puede **mentir** —si la tabla real cambia y el modelo no,
> te enteras con un error en ejecución, no en una migración.

### `backend/nevera/` — el inventario (lectura y escritura)

Al contrario que la anterior: tablas propias, `managed = True`, migraciones
normales.

| Fichero | Qué hace |
|---|---|
| `models.py` | Un solo modelo, `NeveraItem`. Pequeño pero lleno de decisiones: la restricción única `(nombre, unidad)`, y el campo `es_basico` que separa "se gestiona por cantidad" de "se gestiona por presencia". |
| `services.py` | La lógica: añadir con fusión de duplicados, consumir descontando cantidades, ranking por caducidad, editar, borrar. |
| `units.py` | Conversión de unidades a una base (`g`, `ml`, `ud`) con `Decimal`. 61 líneas que resuelven un problema real: sumar "2 kg" y "500 g". |
| `parsing.py` | Prompt + llamada a Gemini para convertir texto libre ("2 kg de pollo, 6 huevos") en items estructurados. |
| `suggestions.py` | Prompt que propone recetas con lo que hay en la nevera. |
| `ofertas.py` | Prompt que cruza una lista de ofertas del supermercado con tu inventario. |

### `backend/health_ai/` — el análisis con IA

| Fichero | Qué hace |
|---|---|
| `pruebas.py` | Construye el prompt (datos crudos + historial de 7 días) y llama a Gemini. `run_analysis()` es la entrada. El nombre del fichero es un resto de cuando era un experimento: **candidato claro a renombrar** (§7.6). |
| `locks.py` | **El fichero mejor documentado del repo. Léelo entero.** Exclusión mutua entre procesos con *advisory locks* de Postgres, para que el bot y la API no disparen dos análisis a la vez. |
| `checks.py` | Avisos de configuración (p. ej. si el puerto del pooler rompería el lock). |
| `config.py` | Carga de la clave de Gemini y el modelo. |

### `backend/bot/` — la interfaz de Telegram

| Fichero | Qué hace |
|---|---|
| `handlers.py` | **633 líneas, el fichero más grande.** Un *handler* por comando: `/hoy`, `/historial`, `/analisis`, `/anadir`, `/nevera`, `/comer`, `/hecho`, `/comprar`… Más el estado conversacional en memoria. |
| `main.py` | Arranque: registra los handlers y lanza el *long polling*. |
| `config.py` | Token y chat autorizado. |
| `formatting.py` | Formateo de texto para Telegram (Markdown, troceo de mensajes largos). |
| `notifier.py` | Envío de mensajes sin estar dentro de un handler (lo usa `daily_sync.py`). |

### `backend/api/` — la interfaz REST (DRF)

Capa fina. Si encuentras lógica de negocio aquí, es un bug de diseño.

| Fichero | Qué hace |
|---|---|
| `urls.py` | 16 rutas. Es el **índice de la API**: léelo primero para saber qué expone el proyecto. |
| `views.py` | 629 líneas, 13 vistas. Cada una: valida con un serializador, llama a un servicio, devuelve. |
| `serializers.py` | 415 líneas. Validación de entrada y forma de salida. **El concepto clave de DRF.** |
| `auth.py` | Login JWT que además exige `is_superuser`. 23 líneas que enseñan a extender una clase de una librería. |
| `permissions.py` | `IsTheOwner`: permiso por defecto de toda la API. |
| `docs.py` | Swagger UI / OpenAPI. Protegido por sesión de admin, no por JWT. |

### `backend/` raíz — los scripts

| Fichero | Qué hace |
|---|---|
| `extractor.py` | Lee el SQLite de Health Connect y sube el último día a Supabase. **No usa Django ni el ORM**: `sqlite3` a mano y el cliente de Supabase. Es el más independiente del repo. |
| `daily_sync.py` | Orquestador: descomprime el `.db` del zip, llama al extractor, dispara el análisis, avisa por Telegram. |
| `manage.py` | CLI de Django. |
| `pyproject.toml` | Config de `ruff` y `mypy`. |

### `frontend/` — la SPA

React 18 + TypeScript + Vite + React Router + TanStack Query + Tailwind v4.

| Ruta | Qué hace |
|---|---|
| `src/api/client.ts` | **El fichero más interesante del frontend.** Cliente HTTP con JWT y renovación única en vuelo al recibir un 401. Es el único con tests (`client.test.ts`). |
| `src/api/hooks.ts` | Hooks de TanStack Query: uno por endpoint. |
| `src/api/types.ts` | Tipos TypeScript que **duplican a mano** la forma de los serializadores. Punto frágil (§7.5). |
| `src/lib/auth.tsx` | Contexto de sesión. |
| `src/routes/*.tsx` | Una pantalla por fichero: `Login`, `Dashboard`, `DayDetail`, `Analyses`, `Nevera`, `Comer`, `Comprar`. |
| `src/components/Hypnogram.tsx` | 254 líneas de SVG a mano para el gráfico de fases de sueño. |

---

## 3. Los números del proyecto

Para calibrar cuánto hay que leer:

- **~7.300 líneas de Python**, de las cuales **~3.000 son tests** (185 tests).
- **~2.760 líneas de TypeScript/TSX** (3 tests).
- 4 apps de Django + 2 scripts + 1 SPA.
- Los 5 ficheros más grandes concentran la mitad de la lógica:
  `bot/handlers.py` (633), `api/views.py` (629), `supabase_data/services.py`
  (553), `api/serializers.py` (415), `extractor.py` (302).

**Si solo pudieras leer 5 ficheros:** `api/urls.py` (qué existe),
`nevera/services.py` (cómo se escribe un servicio), `nevera/models.py` (cómo se
modela), `health_ai/locks.py` (el problema más interesante del repo),
`frontend/src/api/client.ts` (cómo se habla con la API).

---

## 4. Ruta de estudio en 7 etapas

Orden pensado para que cada etapa se apoye en la anterior. Cada una dice qué
ficheros, qué concepto aprendes y qué deberías saber contestar al acabar.

### Etapa 1 — El perímetro: qué expone el proyecto

**Lee:** `backend/api/urls.py`, `backend/core/urls.py`,
`backend/core/settings/__init__.py`, `backend/bot/handlers.py` (solo
`HELP_TEXT`, líneas 55-77).

**Concepto:** el *contrato* de un proyecto. Antes de entender cómo funciona
algo, saber qué promete. `urls.py` es la tabla de contenidos de la API y
`HELP_TEXT` la del bot.

**Pregúntate:**
1. ¿Qué operaciones existen en la web que **no** existen en el bot, y al revés?
2. ¿Por qué `/api/nevera/items/<int:item_id>` está declarada **después** de
   `/api/nevera/items` en la lista? ¿Importaría el orden si fuese al revés?
3. `DJANGO_SETTINGS_MODULE` vale siempre `core.settings`. ¿Qué problema evita
   eso, frente a apuntar directamente a `core.settings.dev`?

### Etapa 2 — Los datos: modelos y el ORM

**Lee:** `backend/supabase_data/models.py` (65 líneas, entero),
`backend/nevera/models.py` (44 líneas, entero).

**Concepto:** el **ORM** (*Object-Relational Mapper*). Una clase de Python por
tabla, un atributo por columna; escribes `NeveraItem.objects.filter(...)` y
Django genera el SQL. Lo que ganas: no escribes SQL, el código es portable
entre motores y tienes validación. Lo que pierdes: una capa de indirección que
oculta consultas caras — el problema N+1 nace aquí.

Compara los dos ficheros: uno es `managed = False` y el otro `managed = True`.
Esa diferencia es toda una decisión de arquitectura sobre **quién es dueño del
esquema**.

**Pregúntate:**
1. ¿Qué pasaría exactamente si el sync externo añadiese una columna a
   `heart_rate_samples` y nadie tocase `models.py`? ¿Y si *quitase* una?
2. La restricción `unique_nombre_unidad` impide dos filas con el mismo
   `(nombre, unidad)`. ¿Qué comportamiento del servicio `add_items` depende de
   que esa restricción exista?
3. `cantidad` es `DecimalField`, no `FloatField`. ¿Por qué? (pista: `0.1 + 0.2`
   en Python).

**Truco de diagnóstico que deberías aprender ahora:** para ver el SQL que
genera el ORM, desde `backend/`:

```bash
venv/Scripts/python manage.py shell
>>> from nevera.models import NeveraItem
>>> print(NeveraItem.objects.filter(es_basico=False).query)
```

### Etapa 3 — La capa de servicio: donde vive la lógica

**Lee:** `backend/nevera/services.py` (215 líneas, entero),
`backend/nevera/units.py` (61 líneas, entero).

**Concepto:** la **capa de servicio** (*service layer*). Funciones que no saben
nada de Telegram ni de HTTP: reciben datos de Python, tocan la base de datos y
devuelven datos de Python. Es lo que permite que dos interfaces compartan
comportamiento sin duplicarlo.

`units.py` es el fichero perfecto para estudiar en un viaje: corto, autónomo,
con un problema real y decisiones visibles.

**Pregúntate:**
1. `add_items` recibe `{"nombre": "pollo", "cantidad": 2, "unidad": "kg"}` y
   ya hay una fila de `pollo` en `g`. ¿Qué ocurre, y por qué hace falta
   `units.py` para que ocurra?
2. `normalizar_nombre` existe para que "Pollo" y "pollo " sean lo mismo. ¿Qué
   casos **no** cubre? ("pollos", "pechuga de pollo")
3. `consume_items` descuenta cantidades. ¿Qué pasa si descuentas más de lo que
   hay? Busca la respuesta en el código, no la supongas.
4. Si `add_items` tuviera que insertar 300 items, ¿qué tiene de malo un bucle
   con un `save()` dentro? (busca `bulk_create` y transacciones)

### Etapa 4 — Las dos pieles: handler y vista, lado a lado

**Lee en paralelo** el mismo caso de uso en las dos interfaces:
`backend/bot/handlers.py` → `nevera_cmd` (línea 242) y `comer` (línea 356);
`backend/api/views.py` → `NeveraView` (línea 294) y `NeveraSuggestionsView`
(línea 490).

**Concepto:** **capa fina** (*thin layer*) y separación de responsabilidades.
Las dos hacen lo mismo en tres pasos —parsear entrada, llamar al servicio,
formatear salida— con ergonomías distintas: una habla Markdown de Telegram, la
otra JSON y códigos HTTP.

**Pregúntate:**
1. Localiza **la línea exacta** en la que cada una llama al servicio. ¿Es la
   misma función en ambos casos?
2. El bot responde a los errores con una frase; la API con un código de estado.
   ¿Dónde se decide ese código y por qué 409 y no 400 cuando la nevera está
   vacía?
3. El decorador `@restricted` (línea 78) autoriza en el bot. ¿Qué cumple ese
   papel en la API? (hay dos piezas, no una)
4. **La pregunta importante:** si mañana añades una tercera interfaz (una CLI),
   ¿qué tendrías que escribir y qué no?

### Etapa 5 — El Python de verdad: construcciones del lenguaje

Aquí el objetivo no es el proyecto, es **el lenguaje**. Estas son las
construcciones de Python no triviales que tu repo usa, con la línea exacta.
Para cada una: léela, entiéndela, y reescríbela a mano en un fichero aparte.

| Construcción | Dónde está | Qué aprender |
|---|---|---|
| **Decorador que envuelve** | `bot/handlers.py:78` (`restricted`) + `functools.wraps` en la 81 | Una función que recibe una función y devuelve otra. Por qué hace falta `wraps`: sin él, la función pierde su nombre y su docstring. |
| **Gestor de contexto** (*context manager*) | `health_ai/locks.py:54` (`@contextmanager` + `yield`) | El `with` del que nadie te explica cómo se fabrica. El `yield` parte la función en "antes" y "después", y el `finally` garantiza que el lock se suelta pase lo que pase. |
| **`async` / `await`** | `bot/handlers.py` (todos los handlers) | Concurrencia cooperativa. El bot atiende un comando mientras otro espera respuesta de Gemini. |
| **`asyncio.to_thread`** | `bot/handlers.py:116, 138, 169, 197` | El puente entre mundos: el ORM de Django es **síncrono** y bloquearía el bucle de eventos. Esto lo echa a un hilo. Entender *por qué* hace falta es entender asyncio. |
| **`Decimal`** | `nevera/units.py`, `nevera/models.py` | Aritmética exacta frente a coma flotante. Por qué el dinero y las cantidades nunca son `float`. |
| **Anotaciones de tipo** | casi todo: `def to_base(cantidad, unidad: str) -> tuple[Decimal, str]` | Tipado gradual. No lo comprueba Python en ejecución: lo comprueba `mypy` antes. |
| **`ClassVar`** | `nevera/models.py:7, 39` | Por qué `ORIGEN_CHOICES` necesita esa anotación (pista: `ruff` te lo pidió, y tiene que ver con cómo Django trata los atributos de clase). |
| **Excepciones propias** | `health_ai/locks.py:50` (`LockOcupado`), `pruebas.py:120` (`AnalysisInProgress`) | Cuándo crear una excepción en vez de devolver `None` o `False`. Fíjate en el docstring: *"no es un fallo, es un estado esperable"*. |
| **Jerarquía de excepciones** | `AnalysisInProgress(LockOcupado)` | Heredar para que quien captura pueda elegir el nivel de detalle. |

**Pregúntate:**
1. Quita mentalmente el `functools.wraps` de `restricted`. ¿Qué se rompe, y
   cuándo te darías cuenta?
2. En `locks.py`, ¿qué pasa si el código dentro del `with` lanza una excepción?
   ¿Se libera el lock? ¿Dónde lo garantiza?
3. ¿Por qué `asyncio.to_thread(get_last_day_data)` y no
   `asyncio.to_thread(get_last_day_data())`? (la diferencia es un error muy
   común)

### Etapa 6 — El problema más interesante: concurrencia entre procesos

**Lee:** `backend/health_ai/locks.py` **entero, docstring incluido** (131
líneas), y `backend/health_ai/checks.py`.

**Concepto:** exclusión mutua **entre procesos distintos**. El bot y la API son
dos procesos de Python; un `asyncio.Lock` vive dentro de uno y el otro no se
entera. El lock tiene que vivir en algo que ambos compartan: Postgres.

Es la parte del proyecto que mejor demuestra pensamiento de sistemas, y la
mejor para contar en una entrevista. Fíjate sobre todo en el aviso del
docstring sobre el **modo del pooler**: con el puerto 6543 el lock deja de
proteger nada **sin dar ningún error**. Un fallo silencioso que depende de una
variable de entorno.

**Pregúntate:**
1. ¿Por qué `pg_try_advisory_lock` y no `pg_advisory_lock`? ¿Qué le pasaría a
   una petición HTTP con la variante que espera?
2. Explica con tus palabras por qué el puerto 6543 rompe el lock.
3. De las tres alternativas descartadas en el docstring (Redis, fila de
   control, cola de trabajos), ¿cuál elegirías si el proyecto pasara de un
   usuario a mil?

### Etapa 7 — El frontend y el contrato entre los dos lados

**Lee:** `frontend/src/api/client.ts` (105 líneas) + `client.test.ts`,
`frontend/src/api/types.ts`, `frontend/src/api/hooks.ts`.

**Concepto:** **JWT** (*JSON Web Token*) y renovación de tokens. El cliente
guarda un `access` corto y un `refresh` largo; al recibir un 401 pide uno
nuevo. Lo interesante es el detalle de *"renovación única en vuelo"*: si cinco
peticiones fallan a la vez, solo se dispara **un** refresh. Los 3 tests del
frontend prueban justo eso.

**Pregúntate:**
1. ¿Por qué hay que evitar cinco refresh simultáneos? ¿Qué se rompería?
2. El token vive en `localStorage`. ¿Qué ataque lo hace peligroso, y qué se
   gana a cambio frente a una cookie `HttpOnly`?
3. `types.ts` copia a mano la forma de los serializadores. ¿Qué pasa el día que
   cambies un nombre de campo en `api/serializers.py` y olvides este fichero?
   ¿En qué momento te enterarías?

---

## 5. Tabla de prioridad de ficheros

Si el tiempo se acaba, este es el orden.

| Prioridad | Fichero | Por qué |
|---|---|---|
| 🔴 1 | `backend/nevera/services.py` | El patrón de capa de servicio, que se repite en todo el repo. |
| 🔴 2 | `backend/health_ai/locks.py` | El problema más difícil, y documentado para enseñar. |
| 🔴 3 | `backend/nevera/models.py` | Modelado y decisiones de dominio en 44 líneas. |
| 🔴 4 | `backend/api/urls.py` + `api/views.py` (3 vistas) | Qué es una capa fina, en concreto. |
| 🔴 5 | `backend/nevera/units.py` | Corto, autónomo, con un problema real. Ideal para leer en el tren. |
| 🟠 6 | `backend/bot/handlers.py` (`restricted`, `hoy`, `comer`) | Decoradores, async, y el contraste con la API. |
| 🟠 7 | `backend/api/serializers.py` (`NeveraItemUpdateSerializer`) | Validación declarativa, el concepto central de DRF. |
| 🟠 8 | `frontend/src/api/client.ts` | JWT, refresh, y el único trozo del frontend con tests. |
| 🟠 9 | `backend/supabase_data/services.py` (`get_sleep_night`) | Algoritmo de verdad: deduplicar fases de sueño solapadas. |
| 🟡 10 | `backend/extractor.py` | Python sin Django: `sqlite3`, UUIDs binarios, zonas horarias. |
| 🟡 11 | `backend/core/settings/` | Configuración por entorno. |
| 🟡 12 | `backend/api/auth.py` + `permissions.py` | 40 líneas en total; extender clases de una librería. |

---

## 6. Vocabulario para defender el proyecto

Términos que aparecen en el código y que conviene saber decir con su nombre:

- **ORM** (*Object-Relational Mapper*) — clases de Python ↔ tablas SQL.
- **Capa de servicio** (*service layer*) — `*/services.py`: la lógica de
  negocio, sin saber quién la llama.
- **Capa fina** (*thin layer*) — `bot/handlers.py`, `api/views.py`: parsear,
  delegar, formatear.
- **Serializador** (*serializer*) — valida la entrada y define la forma de la
  salida. En DRF hace las dos cosas.
- **Migración** (*migration*) — fichero versionado que lleva el esquema de la
  BD de un estado al siguiente.
- **Advisory lock** — cerrojo de Postgres sobre un número arbitrario; no
  protege datos, protege un acuerdo entre procesos.
- **Pooler** (*connection pooler*) — intermediario que multiplexa muchas
  conexiones de cliente sobre pocas reales. En Supabase, `pooler.supabase.com`.
- **JWT** (*JSON Web Token*) — credencial firmada que el cliente guarda y
  manda en cada petición; sustituye a la sesión con cookie.
- **SPA** (*Single Page Application*) — la página se carga una vez y luego
  pide datos por HTTP.
- **Long polling** — el bot pregunta a Telegram "¿hay mensajes?" en bucle. La
  alternativa es un *webhook*, que exige una URL pública.
- **Problema N+1** — una consulta para la lista y otra por cada elemento. Se
  arregla con `select_related` / `prefetch_related`.
- **Monorepo** — backend y frontend en el mismo repositorio.

---

## 7. Decisiones discutibles: por dónde atacar

Esta es la sección que pediste. Son decisiones **mías**, cada una con
alternativa real. No están aquí porque estén mal, sino porque son *decisiones*
y no verdades, y tienes derecho a tomarlas tú.

### 7.1 Toda la lógica en `services.py`, nada en los modelos

**Lo que hay:** los modelos son estructuras de datos pasivas; el
comportamiento vive en funciones de módulo en `services.py`.

**La alternativa:** *modelo rico* (*fat model*, el estilo que recomienda la
propia documentación de Django). `NeveraItem.consumir(cantidad)` como método
del modelo, en vez de `consume_items([...])` como función suelta.

**Trade-off:** las funciones de módulo son triviales de testear y de llamar
desde cualquier sitio, pero dispersan el comportamiento de una entidad lejos de
su definición. El método de modelo mantiene juntos datos y comportamiento, pero
tiende a modelos de 800 líneas y a lógica que arrastra la BD a sitios donde no
hacía falta.

**Para discutir:** ¿cuáles de las funciones de `nevera/services.py` son
claramente "cosas que hace un item" y cuáles son "cosas que hace el
inventario"? La respuesta no es la misma para todas.

### 7.2 `bot/handlers.py` tiene 633 líneas

**Lo que hay:** un solo módulo con todos los comandos, más los formateadores,
más el estado conversacional.

**La alternativa:** partirlo por dominio (`handlers/salud.py`,
`handlers/nevera.py`, `handlers/compra.py`) y sacar los formateadores a
`formatting.py`, que ya existe y solo tiene 55 líneas.

**Trade-off:** un fichero se busca con Ctrl+F y no obliga a decidir
fronteras; varios ficheros hacen explícitas las fronteras pero añaden
importaciones y la duda de dónde va cada cosa nueva.

**Para discutir:** 633 líneas no es un problema por sí mismo. ¿Lo es aquí?
Mira cuántas de esas líneas son formateo de texto y no lógica de handler.

### 7.3 El estado conversacional del bot vive en memoria

**Lo que hay:** `_pending_altas` y `_pending_recetas` son diccionarios de
módulo. Si reinicias el bot a mitad de un alta, el usuario pierde el hilo.

**La alternativa:** persistirlo (tabla, Redis, o `PicklePersistence` de
python-telegram-bot), **o** eliminar el estado como hizo la API, que resuelve
parsear→confirmar en dos peticiones sin recordar nada.

**Trade-off:** la memoria es gratis y simple; se pierde al reiniciar y no
sobrevive a más de un proceso. Persistir cuesta infraestructura. La vía sin
estado es la más limpia pero obliga a devolverle al cliente todo el contexto.

**Para discutir:** la API ya resolvió este problema sin estado. ¿Por qué el
bot no hace lo mismo? ¿Es una limitación de Telegram o una inconsistencia?

### 7.4 Los tests corren contra la base de datos real

**Lo que hay:** no hay BD de test. Los 185 tests usan la Supabase de
producción, con prefijos centinela en los nombres y limpieza en `tearDown`.

**La alternativa:** `sqlite` en memoria (choca con `managed = False` y con los
advisory locks, que son de Postgres), un Postgres en Docker, o el
`TestCase` normal de Django con una BD de test de verdad.

**Trade-off:** lo actual no necesita infraestructura y prueba contra el motor
real, incluidas las peculiaridades de Supabase. A cambio: los tests pueden
dejar basura si fallan a mitad, no se pueden ejecutar dos a la vez, y **ya te
ha mordido** — hoy, 2026-10-17, la suite entera ha fallado porque Supabase
había pausado el proyecto por inactividad. 54 errores, ninguno del código.

**Para discutir:** esta es, de todas, la que yo tocaría primero. Un Postgres
en Docker resolvería el problema y además es exactamente la herramienta que
quieres aprender.

### 7.5 `types.ts` duplica a mano los serializadores

**Lo que hay:** el backend define la forma de los datos en
`api/serializers.py` y el frontend la repite en `src/api/types.ts`. Dos
fuentes de verdad para un mismo contrato.

**La alternativa:** generar los tipos desde el esquema OpenAPI que ya produce
`api/docs.py` (hay herramientas que lo hacen), y meter la generación en CI.

**Trade-off:** escribirlos a mano es inmediato y legible; se desincronizan en
silencio. Generarlos garantiza la sincronía pero mete un paso de build y tipos
generados que no controlas.

**Para discutir:** ya tienes el esquema OpenAPI publicado. Está a medio camino
de la solución buena y nadie lo está aprovechando.

### 7.6 Nombres que mienten

- **`health_ai/pruebas.py`** contiene el motor de análisis en producción. Se
  llamó así cuando era un experimento. Debería ser `analysis.py` o
  `analyzer.py`.
- **`supabase_data`** nombra la app por **dónde** están los datos (un
  proveedor concreto), no por **qué** son. El día que migres de Supabase, el
  nombre miente. `biometrics` o `health_data` no tendría ese problema.

**Para discutir:** renombrar es barato ahora y caro más tarde. ¿Cuál es el
coste real de renombrar una app de Django? (pista: `db_table`, migraciones,
importaciones)

### 7.7 `POST /api/analyses` es síncrono y tarda 40 segundos

**Lo que hay:** la petición HTTP se queda esperando a que Gemini termine.
Medido: 40 segundos.

**La alternativa:** encolar y devolver `202 Accepted` con un identificador que
el cliente consulta después.

**Trade-off:** síncrono es trivial de escribir y de entender; muchos proxies
cortan entre 30 y 60 segundos, y cada análisis deja un *worker* ocupado.

**Para discutir:** la mitad difícil ya está resuelta (`locks.py`). Falta
decidir **dónde** se ejecuta el trabajo — y esa decisión pertenece al SDD de
nube, no a este.

### 7.8 CI no ejecuta los tests

**Lo que hay:** `.github/workflows/ci.yml` tiene el job de tests en *opt-in*:
`if: vars.RUN_DB_TESTS == 'true'`, y esa variable no está creada. CI solo corre
`ruff` y `mypy`. **Las PR en verde no significan que los tests pasen.**

**La alternativa:** un Postgres como *service container* en el workflow (va de
la mano de 7.4).

**Para discutir:** ¿qué sentido tiene un CI que no ejecuta los tests? ¿Es
mejor eso o no tener CI, en términos de la falsa confianza que da un check
verde?

---

## 8. Cómo trastear sin romper nada

Desde `backend/`, con el venv:

```bash
# El shell de Django: la herramienta de diagnóstico más útil
venv/Scripts/python manage.py shell
>>> from nevera.services import list_all
>>> list_all()
>>> from nevera.models import NeveraItem
>>> print(NeveraItem.objects.all().query)      # el SQL que genera el ORM

# Ver la API documentada (necesita sesión de admin)
DJANGO_ENV=dev venv/Scripts/python manage.py runserver
#   -> http://localhost:8000/admin/      el admin
#   -> http://localhost:8000/api/docs/   Swagger UI

# Correr solo una parte de los tests
venv/Scripts/python -m unittest nevera.tests.test_units -v

# Calidad (lo que corre CI)
venv/Scripts/python -m ruff check .
venv/Scripts/python -m mypy .
```

⚠️ **Cuidado en la tablet / sin conexión:** el `.env` **no está en git** (y así
debe seguir). Sin él nada que toque la BD o Gemini arranca. Para estudiar y
leer no hace falta; para ejecutar, sí. Lo que **sí** puedes correr sin BD ni
credenciales: `ruff`, `mypy`, y los tests que no tocan la base de datos
(`nevera/tests/test_units.py`, `nevera/tests/test_parsing.py`,
`bot/tests/test_formatting.py`).

⚠️ **Supabase se pausa.** El plan gratuito pausa el proyecto tras ~7 días sin
actividad; el síntoma es `FATAL: (ENOTFOUND) tenant/user postgres.<ref> not
found` y se arregla con *Restore* en el panel. Si vuelves tras un parón, es lo
primero que hay que mirar.

---

## 9. Dónde está el resto de la documentación

- **`CLAUDE.md`** — convenciones del repo y comandos. La referencia operativa.
- **`docs/SDD-web.md`** — diseño de la API + SPA, con las fases y lo que se
  verificó en cada una. **El §9 lista la deuda técnica con nombre**: léelo.
- **`docs/SDD-nevera.md`** — diseño del inventario.
- **`docs/SDD-telegram-bot.md`** — diseño del bot.
- **`docs/SDD-wearos.md`** — ingesta directa desde el reloj. Diseñado, sin
  empezar.
- **`aprendizaje/`** — tu registro de aprendizaje: `conceptos.md`,
  `errores.md`, `repaso.md`, y `GUIA.md` con las tres skills (`/explicar`,
  `/recordar`, `/revisar`).
- **`frontend/README.md`** — procedimiento de prueba end-to-end con túnel
  `cloudflared` y `curl` de diagnóstico por capas.

---

## 10. Estado del proyecto a 2026-10-17

- **SDD-web:** fases 1-5 cerradas y verificadas end-to-end. Fase 6 (acciones
  con IA) completa salvo la **6.d (ofertas)**, que tiene código y 7 tests pero
  le falta la prueba en pantalla con una gazetka real. Fase 7 (cierre
  documental) pendiente de la 6.d.
- **SDD-wearos:** diseñado el 2026-09-07, sin empezar. La Fase 0 es un sondeo
  de capacidades del reloj.
- **Siguiente decisión grande:** el SDD de nube. Hoy el backend es
  `runserver` en el portátil y la SPA en Vercel solo se probó contra un túnel
  temporal. Sin hosting no hay web de verdad.
- **Lo que llevas sin verificar:** la suite de tests solo corre en tu
  portátil (§7.8), y hoy ha hecho falta restaurar Supabase para poder
  ejecutarla.
