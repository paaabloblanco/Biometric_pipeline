# SDD — Interfaz web (React + Vercel)

Documento de diseño. Estado: **propuesta**. Fecha: 2026-08-31.

## 1. Objetivo

Dar una segunda interfaz al proyecto de salud, además del bot de Telegram
(`docs/SDD-telegram-bot.md`), pensada para **consultar y gestionar** cómodamente
lo que hoy solo se ve en un chat:

1. Ver el histórico de análisis de Gemini, no solo los 3 últimos en texto plano.
2. Ver la evolución de los datos de salud (FC, RHR, SpO2, sueño) con gráficas.
3. Gestionar la nevera con tablas, filtros y edición en línea en vez de
   `/editar <id> campo=valor`.
4. Lanzar `/analisis`, `/comer`, `/comprar`, `/anadir` desde formularios con
   validación y viendo el resultado formateado.

El bot **no desaparece**: sigue siendo el canal de captura rápida sobre la
marcha y de notificaciones (`daily_sync`, alertas). La web es el canal de
revisión y gestión. No se busca paridad total de comandos desde el día uno.

No objetivos de esta iteración:
- Multiusuario real. Es una app de un solo usuario (el dueño) con login.
- Reescribir la lógica de negocio: vive y se queda en Django
  (`nevera/services.py`, `supabase_data/services.py`, `health_ai/`).
- PWA / app móvil nativa / notificaciones push web (para eso está Telegram).
- Subida del backend a la nube: es el siguiente SDD. Este documento asume que
  el backend Django se despliega en algún sitio con URL pública estable.

## 2. Decisión de arquitectura: API REST + SPA, dos clientes de un mismo backend

**Opción elegida:** exponer una **API REST sobre Django** (Django REST
Framework) que envuelve los servicios que ya existen, y un **frontend React
(SPA) desplegado en Vercel** que la consume. El bot de Telegram sigue llamando
a los servicios de Django directamente (in-process), sin pasar por la API.

```
                 ┌────────────────────────┐
   Telegram ───► │  bot/  (handlers)      │ ──┐
                 └────────────────────────┘   │  llamadas in-process
                 ┌────────────────────────┐   ▼
   Navegador ──► │  api/  (DRF views)     │ ─► nevera/services.py
   (React/Vercel)└────────────────────────┘    supabase_data/services.py
        ▲  HTTPS + JWT                          health_ai/
        └──────────────────────────────────────────────┘
                       (misma BD Supabase = única fuente de verdad)
```

**Por qué así:**
- **El bot ya es un cliente tonto.** `bot/handlers.py` no tiene lógica de
  negocio: parsea argumentos, llama a un servicio y formatea la respuesta. La
  web hace exactamente lo mismo desde el navegador. La lógica no se duplica
  porque no se toca: ambos entran por `nevera/services.py` y compañía.
- **Sin estado divergente.** Los dos clientes leen y escriben en la misma BD
  vía los mismos servicios. Registras algo en la web y aparece en Telegram y
  viceversa, sin sincronización porque no hay dos copias.
- **Vercel es solo frontend.** Vercel sirve estáticos + funciones edge; no es
  sitio para un Django con conexión a Postgres de larga vida. El frontend va a
  Vercel, el backend va aparte (siguiente SDD). Por eso la separación
  API/SPA no es opcional: es lo que impone el hosting elegido.
- **Descartado: plantillas Django server-rendered.** Funcionaría y sería un
  despliegue único, pero entonces no se puede usar Vercel (que es requisito
  del usuario) y no se aprende React. Además la parte de gráficas pide
  interactividad de cliente.
- **Descartado: Next.js con API routes propias.** Duplicaría la capa de API en
  TypeScript llamando a Django por HTTP igualmente, o reimplementaría acceso a
  datos fuera de Django. Más piezas, ninguna ventaja para un caso de un solo
  usuario. React + Vite basta.

## 3. Componentes nuevos

### 3.1 Backend — nueva app `api/`

```
api/
  __init__.py
  urls.py           # router DRF, montado en core/urls.py bajo /api/
  auth.py           # login (obtener JWT), refresh
  serializers.py    # formas de entrada/salida por endpoint
  views.py          # views finas: validan input, llaman a services.py, devuelven JSON
  permissions.py    # IsTheOwner — un solo usuario permitido
  tests/
```

- `api/views.py` es a la API lo que `bot/handlers.py` es a Telegram: **cero
  lógica de negocio**. Cada view llama a la misma función de `services.py` que
  usa el handler equivalente.
- Los comandos que hoy tienen estado conversacional en el bot (`/anadir` →
  `/confirmar`, `/comer` → `/hecho <n>`) en la web se resuelven sin estado de
  servidor: el cliente recibe la propuesta (items parseados / recetas), la
  muestra, y en un segundo request manda la propuesta ya confirmada. El
  backend no guarda `_pending_altas` para la web.

Dependencias nuevas en `requirements.txt`: `djangorestframework`,
`djangorestframework-simplejwt`, `django-cors-headers`.

### 3.2 Frontend — carpeta `frontend/` (antes `web/`)

```
frontend/
  package.json
  vite.config.ts
  src/
    api/          # cliente fetch tipado, manejo de JWT y refresh
    routes/       # Login, Dashboard, Análisis, Nevera, Comer, Comprar
    components/    # tabla de nevera, tarjeta de análisis, gráficas
    lib/
```

- **Stack:** Vite + React + TypeScript. Router: React Router.
  Data fetching: TanStack Query (cache, reintentos, estados de carga gratis).
- **Gráficas:** Recharts (datos de salud por día).
- **Estilos:** por decidir (§7-D). Propuesta: Tailwind + componentes propios
  mínimos, sin librería de componentes pesada.
- **Deploy:** proyecto de Vercel con Root Directory `frontend`, build `vite build`,
  variable `VITE_API_BASE_URL` con la URL del backend.

## 4. Endpoints

| Método | Ruta | Servicio Django que envuelve | Equivale a |
|---|---|---|---|
| `POST` | `/api/auth/login` | `django.contrib.auth` + SimpleJWT | — |
| `POST` | `/api/auth/refresh` | SimpleJWT | — |
| `GET` | `/api/health/last-day` | `get_last_day_data()` | `/hoy` |
| `GET` | `/api/health/series?metric=&from=&to=` | consulta nueva en `supabase_data/services.py` | (nuevo — gráficas) |
| `GET` | `/api/health/day?date=` | `get_day_detail()` | (nuevo — detalle de un día) |
| `GET` | `/api/health/sleep-night?date=` | `get_sleep_night()` | (nuevo — hipnograma) |
| `GET` | `/api/analyses?limit=` | `get_recent_analyses()` | `/historial` |
| `POST` | `/api/analyses` | `run_analysis()` (con lock) | `/analisis` |
| `GET` | `/api/nevera` | `list_all()` | `/nevera` |
| `POST` | `/api/nevera/parse` | `parse_compra_text()` | `/anadir` (paso 1) |
| `POST` | `/api/nevera/items` | `add_items()` | `/confirmar` |
| `PATCH` | `/api/nevera/items/{id}` | `edit_item()` | `/editar` |
| `DELETE` | `/api/nevera/items/{id}` | `delete_item()` | `/borrar` |
| `POST` | `/api/nevera/suggestions` | `suggest_recipes()` | `/comer` |
| `POST` | `/api/nevera/consume` | `consume_items()` | `/hecho` |
| `POST` | `/api/ofertas/analyze` | `analizar_ofertas()` | `/comprar` |

Los cuatro servicios de datos nuevos viven en `supabase_data/services.py`:
`get_series` agrega muestras por día/rango, `get_day_detail` reúne todo lo de
la página de un día, `get_sleep_night` reconstruye la noche para el hipnograma
y `build_day_summary` calcula los KPIs de la cabecera. El resto de rutas son
envoltorios directos de servicios que ya usaba el bot.

### 4.1 Reparto por canal (estado final de la iteración)

Cada función existe donde tiene sentido usarla, no en los dos sitios por
simetría. Esta tabla es la fuente de verdad de qué hay en cada canal.

| Función | Telegram | Web | Por qué |
|---|---|---|---|
| Ver datos del día (`/hoy`) | ✅ | ✅ | La web además da hipnograma, gráficas y detalle por día |
| Histórico de análisis (`/historial`) | ✅ | ✅ | |
| Lanzar análisis (`/analisis`) | ✅ | ✅ | Coordinados por `pg_advisory_lock` |
| Ver nevera (`/nevera`) | ✅ | ✅ | |
| Alta con IA (`/anadir` + `/confirmar`) | ✅ | ✅ | En la web se pueden **corregir** las propuestas antes de guardar; en el bot es confirmar o cancelar |
| Editar / borrar item (`/editar`, `/borrar`) | ✅ | ✅ | La web edita en línea sin recordar ids |
| Sugerencias y consumo (`/comer` + `/hecho`) | ✅ | ✅ | |
| Ofertas (`/comprar`) | ✅ | ✅ | Nace para la web: pegar el folleto largo (§7-G) |
| Análisis diario automático | ✅ | ❌ | Es una **notificación**: llega sola, sin que nadie abra nada. Una web no puede empujar nada a nadie sin push notifications, que es infraestructura entera para un solo usuario. `daily_sync.py` lo seguirá mandando por Telegram |
| `/start`, `/help`, `/cancelar` | ✅ | ❌ | Andamiaje del propio bot: en una interfaz gráfica no significan nada (la ayuda es la pantalla y cancelar es cerrar el formulario) |

Lo que la web **no** hereda del bot no es deuda: es la parte que solo tiene
sentido en un chat. Y al revés, la web hace cosas que el bot no puede
(gráficas, hipnograma, edición en línea) porque un chat no es un lienzo.

## 5. Autenticación

**Por qué hace falta aunque sea un solo usuario** (decidido 2026-08-31): el
backend estará en una URL pública. Sin auth, cualquiera que dé con ella puede
leer los datos de salud (personales), gastar cuota de Gemini disparando
`/api/analyses` y `/api/ofertas/analyze`, y editar/borrar la nevera. Es el mismo
problema que el bot resolvió con la allowlist de `chat_id`. Un token fijo en el
frontend NO vale: las variables `VITE_*` se empaquetan en el bundle y quedan
a la vista. La versión mínima segura es la de abajo (~1-2 h en fase 1).

- **Modelo:** un único `User` de Django (el dueño), creado por `createsuperuser`
  o un management command. Login con usuario/contraseña → devuelve un JWT de
  acceso (corto) + refresh (largo). El frontend guarda el refresh y renueva.
- `api/permissions.py::IsTheOwner` rechaza cualquier request autenticada que no
  sea ese usuario. Defensa en profundidad aunque solo haya una cuenta.
- **CORS:** `django-cors-headers` con allowlist = dominio de Vercel (prod) +
  `localhost:5173` (dev). Nada de `CORS_ALLOW_ALL`.
- **Vínculo con Telegram:** no hace falta para esta iteración. El bot sigue
  identificando por `chat_id` en su allowlist; la web identifica por `User`.
  Son el mismo humano pero no necesitan compartir identidad mientras la web no
  dispare acciones *en nombre de* Telegram. Si más adelante se quiere (p. ej.
  "notifícame por Telegram cuando el análisis esté listo"), se añade un campo
  `telegram_chat_id` al perfil del usuario. _(fuera de esta iteración)_

## 6. Riesgos / notas

- **`DEBUG = True` y `SECRET_KEY` en `core/settings.py`.** Mitigado en parte
  (settings por entorno, fase 1); lo que queda es de despliegue y está
  listado en el §9. Enunciado original: antes de exponer
  nada públicamente hay que separar settings de dev y prod, `DEBUG=False`,
  `ALLOWED_HOSTS` real. Esto se solapa con el SDD de nube; aquí solo se
  señala como bloqueante.
- ~~**Llamadas a Gemini desde la web sin lock compartido.**~~ **Resuelto en
  la fase 6.a** con `pg_advisory_lock` (`health_ai/locks.py`). Enunciado
  original: `run_analysis` tiene
  un `asyncio.Lock` que vive en el proceso del bot. La API es otro proceso: su
  propio lock no coordina con el del bot. Riesgo de dos análisis simultáneos
  (bot + web) gastando cuota. Opción: mover el lock a un lock de BD
  (`select_for_update` sobre una fila de control) o aceptar el riesgo como se
  aceptó en el SDD de nevera. _(decisión §7-C)_
- ~~**Estado conversacional del bot vs. sin estado en la web.**~~ **Resuelto
  en las fases 6.b y 6.c**: el estado intermedio lo tiene el cliente y vuelve
  entero en la segunda petición; el servidor no guarda nada. Enunciado
  original: hay que
  refactorizar `/anadir` y `/comer` para que la lógica de "parsear" y
  "confirmar/consumir" sea llamable por separado desde la API sin depender de
  `_pending_altas` / `_pending_recetas`. Los servicios ya lo permiten
  (`parse_compra_text` + `add_items` son funciones distintas); es sobre todo
  no meter el estado en la capa de API.
- **Dos frontends que mantener.** Cada comando nuevo hay que decidir si va en
  web, en bot, o en ambos. Mitigación: la tabla del §4.1 es la fuente de verdad
  de qué existe en cada canal; no toda feature tiene que estar en los dos.
- **CSRF vs JWT.** Con JWT en header `Authorization` y sin cookies de sesión
  para la API, el middleware CSRF de Django no aplica a esos endpoints (DRF lo
  gestiona). No mezclar auth por sesión y por token en la misma ruta.
- **Coste de Vercel:** plan hobby gratis cubre de sobra un SPA de un usuario.
  Sin funciones serverless propias no hay riesgo de factura.

## 7. Decisiones abiertas

- **A. Repo del frontend.** **Resuelto: monorepo con `backend/` + `frontend/`**
  (antes el frontend estaba en `web/` y el backend en la raíz; reorganizado el
  2026-08-31). Vercel apunta a `frontend/` (Root Directory). Cambios de API +
  frontend en el mismo commit. _(2026-08-31, con el usuario)_
- **B. Librería de API.** **Resuelto: Django REST Framework** + SimpleJWT para
  el login. Descartado Django Ninja por menos ecosistema y menos peso en
  ofertas de trabajo (el usuario apunta a cloud/DevOps). _(2026-08-31)_
- **C. Lock de Gemini entre procesos.** **Resuelto: `pg_advisory_lock` de
  Postgres** en `health_ai/` (2026-08-31, con el usuario). Función nativa de
  Postgres sobre un entero fijo, funciona entre el proceso del bot y el de la
  API, sin tabla ni migración. Sustituye al `asyncio.Lock` in-process actual
  para `run_analysis`. Se implementa en la fase 5. Descartada la "fila de
  control en tabla" porque exigiría una migración para cero ventaja frente al
  advisory lock.
- **D. Estilos del frontend.** **Resuelto: Tailwind CSS** sin librería de
  componentes; el usuario monta cada componente. _(2026-08-31)_
- **E. Alcance de la iteración 1.** **Resuelto: solo lectura primero.**
  Iteración 1 = Dashboard + gráficas + histórico de análisis + ver nevera.
  Las escrituras (`/anadir`, `/comer`, `/comprar`, editar nevera) van en la
  iteración 2, tras validar el circuito API↔SPA↔auth↔Vercel. _(2026-08-31)_
- **F. ¿App `api/` propia o endpoints repartidos por app?**
  **Resuelto: app `api/` propia** (2026-08-31, con el usuario). Todos los
  endpoints web (salud, nevera, ofertas, análisis) y la autenticación viven en
  una sola app `api/`, que es al navegador lo que `bot/` es a Telegram: una
  capa fina de interfaz separada de la lógica, no repartida dentro de las apps
  de dominio. `supabase_data/` y `nevera/` no exponen views HTTP. Descartado
  repartir views en `supabase_data/views.py` + `nevera/views.py` porque la
  auth, los serializers y los permisos (`IsTheOwner`) necesitan un hogar común
  igualmente, y `supabase_data` (tablas de sync de salud) no debe importar
  `nevera.services`.

- **G. ¿`/comprar` (ofertas) en la web o solo en Telegram?**
  **Resuelto: en la web** (2026-09-02, con el usuario). Se planteó dejarlo solo
  en Telegram para no construir una pantalla más, y se descartó por ergonomía
  de uso real: la entrada es un bloque largo de texto pegado del folleto del
  supermercado, y un `<textarea>` en el navegador lo acepta de una vez mientras
  Telegram parte los mensajes largos y obliga a mandarlos por trozos. Es la
  primera función del proyecto que vive mejor en la web que en el bot.

## 8. Plan de implementación (por fases)

Cada fase se verifica con una prueba real end-to-end antes de pasar a la
siguiente (igual que en el SDD de nevera).

### Iteración 1 — solo lectura

1. [hecho] **Settings dev/prod + app `api/` con auth.** `core/settings/` pasa a
   ser paquete (`base` + `dev` + `prod`, selector por `DJANGO_ENV`);
   `DJANGO_SETTINGS_MODULE=core.settings` no cambia en el resto del proyecto.
   Nueva app `api/` (interfaz fina, sin lógica de negocio): `OwnerTokenObtain
   PairView` rechaza a quien no sea superusuario, `IsTheOwner` como permiso por
   defecto de DRF. Endpoints `POST /api/auth/login` y `POST /api/auth/refresh`.
   Verificado con 4 tests (`api/tests/test_auth.py`, contra la BD real, patrón
   del resto del proyecto) + `curl` en vivo: login 401 con credenciales malas,
   400 sin cuerpo, 200 + access/refresh con el superusuario. Falta que el
   usuario cree su superusuario con `manage.py createsuperuser`.
2. [hecho] **Endpoints de solo lectura.** `GET /api/health/last-day`
   (`get_last_day_data`), `GET /api/analyses?limit=` (`get_recent_analyses`),
   `GET /api/nevera` (`list_all`) y `GET /api/health/series?metric=&from=&to=`.
   La agregación nueva es `supabase_data.services.get_series`: agrega por día
   `heart_rate` / `resting_heart_rate` / `oxygen_saturation` (min/max/avg/count)
   y `sleep` (minutos, excluyendo fases de vigilia); rango por defecto = últimos
   30 días con datos. Views finas en `api/views.py` (llaman al mismo servicio
   que el handler de Telegram equivalente), serializers en `api/serializers.py`.
   Verificado con 13 tests (`api/tests/test_read_endpoints.py`, contra la
   Supabase real, autenticados, con centinelas y limpieza en tearDown): auth
   401 sin token, agregación de series, 400 en métrica/limit inválidos, paridad
   de forma con los datos reales.
3. [hecho y verificado e2e, 2026-08-31] **Frontend base en Vercel.** Carpeta `frontend/`:
   Vite + React 18 + TS + React Router + TanStack Query + Tailwind v4. Cliente
   HTTP (`src/api/client.ts`) con JWT en `Authorization` y renovación única en
   vuelo al recibir 401 (evento `salud:logout` cuando el refresh caduca).
   Pantallas Login, Dashboard (last-day + gráficas Recharts de FC y sueño),
   Análisis (histórico) y Nevera (tabla con alerta de caducidad, solo ver).
   `vercel.json` con build y rewrite de SPA; `.env.example` con
   `VITE_API_BASE_URL`. Verificado en local: `npm run build` (tsc + vite) y
   `npm run test` (3 tests de vitest sobre el flujo de refresh del cliente) en
   verde; `dev.py` ya tiene el CORS de `localhost:5173`.
   **Verificación end-to-end (2026-08-31):** SPA desplegada en Vercel
   (`biometric-pipeline.vercel.app`, Root Directory `frontend`) contra el
   backend local expuesto con un túnel `cloudflared`, autorizado vía
   `DEV_EXTRA_ALLOWED_HOSTS=.trycloudflare.com` y `DEV_EXTRA_CORS_ORIGINS`.
   Login con el superusuario y datos reales de salud, análisis y nevera
   visibles desde el dominio público. Procedimiento y `curl` de diagnóstico
   por capas documentados en `frontend/README.md`.

   Dos incidencias resueltas, ambas de configuración, no de código:
   - `405` en `POST /api/auth/login` — `VITE_API_BASE_URL` sin definir hacía
     que `client.ts` cayera a `""` y la SPA se llamara a sí misma; el hosting
     estático de Vercel solo acepta `GET`.
   - El valor no surtía efecto hasta **redesplegar**: Vite incrusta las
     variables `VITE_*` en el bundle en tiempo de build, no las lee en runtime
     (corolario de seguridad: nunca meter secretos en una variable `VITE_*`).

   **Pendiente:** el backend sigue siendo local; el túnel es una prueba
   puntual (URL nueva en cada arranque). Hosting real = SDD de nube.

### Iteración 2 — escrituras

4. [hecho y verificado e2e, 2026-09-02] **Editar la nevera desde la web.**
   `PATCH`/`DELETE /api/nevera/items/{id}` (`api.views.NeveraItemView`) +
   edición y borrado en línea en la tabla de la SPA. Ninguna lógica nueva: las
   dos rutas envuelven `nevera.services.edit_item` / `delete_item`, las mismas
   que usan `/editar` y `/borrar` en Telegram.

   Decisiones de esta fase:
   - **`PATCH`, no `PUT`.** La actualización es *parcial*: el cuerpo lleva solo
     los campos que cambian, y el frontend calcula ese delta antes de enviar.
     Con `PUT` (reemplazo del recurso completo) la web pisaría cualquier cambio
     que el bot hubiera hecho entre la carga de la tabla y el guardado.
   - **`cantidad` y `unidad` viajan juntas.** El servicio las convierte a la
     unidad base a la vez (`to_base`), así que mandar la unidad sola
     reinterpretaría la cantidad en otra escala: 500 g pasarían a ser 500 kg.
     Se rechaza con 400.
   - **409 en colisión con `unique_nombre_unidad`.** Renombrar un item al
     nombre de otro que ya existe en la misma unidad es un conflicto con el
     estado del recurso, no una petición mal formada. Sin capturar el
     `IntegrityError` sería un 500 y parecería un fallo del servidor.
   - **La entrada es un `Serializer` pelado, no un `ModelSerializer`.** Un
     `ModelSerializer` sabría guardar solo, y guardar salteándose
     `services.py` metería en la BD datos con una forma distinta a la que mete
     el bot. La validación se queda en la API; la escritura, en el servicio.
   - **Errores con forma única `{"detail": "..."}`.** DRF devolvería
     `{"campo": ["..."]}`; se aplana para que el cliente del frontend tenga un
     solo sitio del que leer el mensaje.
   - **La caché se invalida, no se parchea.** Las mutaciones de TanStack Query
     invalidan la query `nevera` al terminar. Cuesta una petición extra y a
     cambio la tabla enseña lo que el servidor guardó de verdad —que casi
     nunca es literalmente lo enviado, porque el nombre se normaliza y la
     unidad se convierte.

   Verificado con 14 tests (`api/tests/test_write_endpoints.py`, contra la
   Supabase real, patrón de centinela + limpieza en `tearDown`) y el build y
   los tests del frontend en verde.

   **Verificación end-to-end (2026-09-02):** editado un item desde la SPA en
   `localhost:5173` contra el `runserver` local, y el cambio visible en
   `/nevera` del bot de Telegram corriendo como proceso aparte. Es la prueba
   de que la decisión de §3.1 se sostiene: dos interfaces, un solo
   `services.py`, una sola BD, sin estado divergente.

   Incidencia resuelta, de configuración: la SPA no cargaba **ningún** dato
   porque `frontend/.env` seguía apuntando al túnel `cloudflared` de la prueba
   del 2026-08-31, que genera una URL nueva en cada arranque y llevaba muerto
   desde entonces. Diagnóstico por capas: `curl` al backend local devolvía
   `401` (servidor y auth vivos, respuesta correcta sin token) y `curl` al
   túnel devolvía `000` (curl no llega a conectar; no es un código HTTP), lo
   que sitúa el fallo en la configuración de destino, no en el código de la
   fase. Regla: si fallan todas las pantallas a la vez, el sospechoso es el
   transporte o la configuración, no la pantalla.
### Iteración 3 — la web como interfaz de consulta de verdad

5. [hecho y verificado e2e, 2026-09-02] **Detalle de día, hipnograma e
   interfaz oscura.** Hasta aquí la web enseñaba el último día como una
   volcada de datos crudos; esta fase la convierte en algo que se mira. Tres
   endpoints nuevos de solo lectura, un dashboard con KPIs y navegación por
   días, y un rediseño completo de la interfaz.

   **Backend** — `GET /api/health/day?date=` (`get_day_detail`) y
   `GET /api/health/sleep-night?date=` (`get_sleep_night`), más un bloque
   `summary` añadido a `/health/last-day`. Toda la lógica en
   `supabase_data/services.py`; las views siguen siendo finas.

   Decisiones de esta fase:
   - **Los KPIs se calculan en el servicio, no en la SPA.** Si el frontend
     promediase la SpO₂ por su cuenta, la web y el bot podrían enseñar números
     distintos del mismo dato. `build_day_summary` es la única fuente de
     verdad, y la web solo la pinta.
   - **Una noche se atribuye al día en que te despiertas.** Antes la serie
     agrupaba por `TruncDate(stage_start)`, lo que partía en dos mitades cada
     noche que cruza medianoche y llenaba la gráfica de huecos y picos. Es el
     criterio de Health Connect, Fitbit y Garmin.
   - **Deduplicación de sesiones al leer, por solapamiento.** El sync externo
     guarda a veces la misma noche dos veces con dos `parent_key` distintos, y
     el `unique_together (parent_key, stage_start)` no lo impide justamente
     porque el `parent_key` difiere: una noche de 8h 20m salía como 16h 40m.
     Comparar huellas exactas no basta —la noche del 12-08 estaba guardada dos
     veces con finales distintos, seguramente dos pasadas del sync—, así que el
     criterio es el solapamiento temporal: como nadie duerme dos veces a la
     vez, de cada grupo solapado se conserva la sesión con más minutos de
     sueño. Se deduplica **al leer y no borrando filas** porque `sleep_stages`
     es `managed = False`: lo que borrase Django volvería en la siguiente
     sincronización.
   - **"La noche" es la sesión más larga que termina ese día, no todo lo que se
     durmió.** Mezclar una siesta de 47 min haría que la tarjeta dijera 9h 07m
     mientras el hipnograma justo debajo dibuja 8h 20m.
   - **Un solo endpoint para el detalle del día**, en vez de que la SPA encadene
     tres llamadas: resumen, series intradía y días vecinos salen del mismo
     día. El hipnograma va aparte porque su unidad es la noche, no el día
     natural.
   - **`prev_date`/`next_date` son días CON datos**, no el día natural
     anterior: el sync tiene huecos de semanas y las flechas llevarían a
     pantallas vacías.
   - **Las series intradía viajan como `{t, v}`**, no como la fila entera: la
     gráfica no necesita `uuid` ni `parent_key`, y un día de frecuencia
     cardíaca son ~700 filas.
   - **Los instantes se mandan en hora local con offset explícito** y el
     frontend los lee con `horaLocalServidor` (quita el offset y usa los
     getters `getUTC*`). Si no, `new Date(iso)` los reinterpretaría en la zona
     del navegador y la misma noche se dibujaría desplazada al abrir la web
     desde otro huso.

   **Frontend** — componentes nuevos `Card`, `StatCard`, `Icons`, `Hypnogram` e
   `IntradayChart`; ruta `/dia/:fecha` (`DayDetail`); utilidades en
   `lib/format.ts`. El dashboard pasa a ser cuatro KPIs + hipnograma de la
   última noche + las dos series de 30 días, y los puntos de las gráficas
   enlazan al detalle del día.

   - **La interfaz es oscura de forma fija**, sin conmutador: es una app de un
     solo usuario que se mira sobre todo de noche, y un único modo evita
     duplicar y revalidar toda la paleta. Si algún día hace falta el modo
     claro, se añade redefiniendo las mismas variables bajo
     `prefers-color-scheme`, sin tocar ningún componente.
   - **Todo el color vive en los tokens de `index.css`** (`@theme` de Tailwind
     v4). Ningún componente tiene colores propios; por eso el cambio a oscuro
     fue casi solo redefinir variables.
   - **En oscuro la elevación se comunica con luminosidad, no con sombra**
     (una sombra negra sobre negro no se ve): `canvas` → `navbar` → `surface`
     → `raised`, cada capa que sube aclara un paso.
   - **La paleta de datos se re-escalona, no se invierte.** Mismos tonos, otro
     escalón: los colores que funcionan sobre blanco pierden contraste sobre
     negro. Validado con el validador de paleta sobre la superficie oscura
     (banda de luminosidad, suelo de croma, separación bajo daltonismo 9,6 ΔE,
     visión normal 23,0 ΔE, contraste ≥ 3:1). Las fases del sueño se validan
     aparte como grupo de cuatro, en orden de fila.
   - **`color-scheme: dark` en `html`** para lo que el CSS no controla: barras
     de scroll, el desplegable del `<input type="date">` de la nevera y el
     relleno del autocompletado. Sin ello quedan islas blancas.
   - **`lib/chartTheme.ts` centraliza los hex de las gráficas.** Recharts pinta
     SVG y escribe el color como atributo, no como clase: no entiende
     Tailwind. En vez de dejar los hex sueltos por los componentes, hay un solo
     fichero y cada constante apunta al token del que sale.
   - **La identidad nunca depende solo del color**: cada fila del hipnograma
     lleva su etiqueta escrita, y el reparto de la noche va también en texto.

   Verificado con 8 tests nuevos (`supabase_data/tests/`, contra la Supabase
   real, con centinelas fuera del rango y limpieza en `tearDown`) que cubren la
   deduplicación, la atribución al día del despertar, la siesta que no se
   mezcla y los extremos de la noche del cambio de hora. `ruff`, `mypy` y los
   141 tests del backend en verde; `tsc`, `vite build` y `vitest` del frontend
   también.

   Bug encontrado y corregido en el repaso: `get_sleep_night` sacaba `start` y
   `end` comparando los ISO **ya formateados como texto**. La madrugada del
   cambio de hora convive con dos offsets y ahí el orden alfabético deja de
   coincidir con el cronológico (`"02:30:00+02:00"` es *anterior* a
   `"02:10:00+01:00"`, pero como texto gana el primero): una vez al año la
   cabecera del hipnograma habría dado la noche del revés. Ahora se calcula
   sobre los `datetime`.

   **Verificación end-to-end (2026-09-02):** backend local (`runserver`) y SPA
   local (`vite`) contra la Supabase real, recorriendo las cuatro pantallas con
   datos de verdad: KPIs del último día, hipnograma con el reparto por fases,
   las dos series de 30 días, el detalle de un día con sus gráficas intradía y
   la navegación entre días, el histórico de análisis y la nevera con una fila
   en edición.

   **Pendiente:** la pantalla de Login quedó migrada a los tokens pero no
   revisada en pantalla (habría que cerrar sesión para verla).

### Iteración 4 — escrituras con IA

6. [en curso] **Acciones con IA desde la web.** `/api/nevera/parse` + `items`,
   `/api/nevera/suggestions` + `consume`, `/api/analyses` (POST),
   `/api/ofertas/analyze`. Resolver el estado conversacional (§6) y el lock
   (§7-C, `pg_advisory_lock`). Verificación end-to-end de cada flujo:
   parsear→confirmar alta, sugerir→marcar hecho con descuento en BD, lanzar
   análisis.

   **6.a [hecho y verificado e2e, 2026-09-02] Lanzar un análisis desde la web.**
   `pg_advisory_lock` en `health_ai/locks.py` (cierra la decisión §7-C),
   `POST /api/analyses` en `api/views.py` y el formulario de la pantalla
   `/analisis` en la SPA (`useLanzarAnalisis` + el componente `LanzarAnalisis`).

   Decisiones de esta parte:
   - **`200`, no `201`.** Llamar dos veces el mismo día no crea dos análisis:
     sobrescribe el mismo. Un `201` prometería un recurso nuevo cada vez, con
     su propia URL, y aquí no lo hay.
   - **`409`, no `429`, cuando el lock está tomado.** El cliente no ha hecho
     nada mal ni se ha pasado de cuota: es que el estado del sistema es
     incompatible con lo que pide, y encima el conflicto puede haberlo causado
     el bot, no él. El frontend lo traduce a lenguaje humano en vez de enseñar
     el `detail` crudo.
   - **El lock es de Postgres, no del proceso.** El `asyncio.Lock` anterior
     vivía en el proceso del bot y no coordinaba nada con el de la API. Un
     *advisory lock* sobre un entero fijo sí cruza procesos, y no necesita
     tabla ni migración.
   - **La mutación invalida el histórico, no lo parchea.** El análisis del día
     se sobrescribe, así que añadir a la caché lo que enviamos duplicaría la
     fila del día en pantalla.
   - **Sin reintento automático.** Las mutaciones de TanStack Query no
     reintentan por defecto y aquí se deja así a propósito: un reintento son
     otros 30-40 s de Gemini y cuota gastada por un fallo que probablemente no
     sea transitorio.
   - **El estado de carga se cuenta con palabras.** Con una espera de medio
     minuto, deshabilitar el botón y nada más se lee como que la web se ha
     colgado.

   **Verificación end-to-end (2026-09-02):** backend local (`runserver`) y SPA
   local contra la Supabase real. `POST /api/analyses` → `200` en **40 s**, y
   el `GET /api/analyses?limit=20` inmediatamente después devolvió el histórico
   ya con el análisis nuevo (14.886 → 20.235 bytes), o sea que la invalidación
   de la caché funciona. El análisis era el del día, que faltaba porque
   `daily_sync.py` había fallado esa tarde por una causa ajena (se lanzó con el
   Python del sistema en vez de con el del venv, sin Django instalado).

   **Deuda que hereda el SDD de nube:** el `POST` es **síncrono** — no responde
   hasta que Gemini contesta, y la medida real fue de 40 s. En local funciona;
   detrás de un proxy o gateway gestionado, no: muchos cortan la petición entre
   30 y 60 s, y además cada análisis deja un worker de gunicorn ocupado sin
   atender nada más. El arreglo estándar es que el `POST` encole y devuelva
   `202 Accepted` con un id que el cliente consulta (*polling*), lo que exige
   dónde ejecutar el trabajo (hilo o cola tipo Celery/RQ) y una tabla de
   estado. No se hace aquí a propósito: la mitad difícil —la exclusión entre
   procesos— ya está resuelta con el advisory lock.
   **6.b [hecho y verificado e2e, 2026-09-02] Alta de nevera con IA.**
   `POST /api/nevera/parse` + `POST /api/nevera/items` (`api/views.py`) y la
   tarjeta "Añadir con IA" de la pantalla `/nevera` en la SPA
   (`components/AltaConIA.tsx`). Cierra el riesgo del §6 sobre el estado
   conversacional.

   **La decisión de fondo: el estado intermedio lo tiene el cliente.**
   `/anadir` guarda lo que entendió Gemini en `_pending_altas`, un diccionario
   en memoria del proceso del bot, y espera un `/confirmar`. La API no guarda
   nada entre las dos llamadas: `parse` devuelve los items propuestos, la SPA
   los tiene en el estado de React y los manda enteros de vuelta a `items`.
   Se gana que el servidor no tenga sesiones que caducar ni altas huérfanas si
   nadie confirma, que dos pestañas no se pisen, y que dé igual qué instancia
   del backend atienda cada petición el día que haya más de una detrás de un
   balanceador —que es el argumento de por qué una API REST se diseña
   *stateless*—. Se paga que el cuerpo de la segunda petición lleve la lista
   completa en vez de un identificador. Descartada la alternativa de guardar
   las propuestas en una tabla `altas_pendientes`: exigiría migración, una
   política de caducidad y limpieza de huérfanas, todo para no repetir unos
   pocos kB.

   Resto de decisiones:
   - **Un solo serializer para las dos mitades.** `ItemPropuestoSerializer` es
     a la vez la salida de `parse` y la entrada de `items`. Declarado una vez,
     los dos extremos del flujo no pueden desincronizarse.
   - **`502` cuando Gemini contesta mal**, sea JSON inválido o una unidad que
     `to_base` no conoce. No es un `400`: la petición del cliente era correcta
     y quien falló fue el servicio de terceros de detrás.
   - **La unidad se valida antes de tocar la BD.** `add_items` da de alta item
     por item, así que validar dentro dejaría escritos los items anteriores al
     que falla y el alta a medias. Con la validación en el serializer, el alta
     es todo o nada sin necesidad de una transacción explícita.
   - **`201`, a diferencia del `200` de los análisis.** Aquí sí se añaden
     recursos a la colección. Sin cabecera `Location` porque no se crea *un*
     recurso sino varios, y algunos ni se crean: los que ya existían con el
     mismo nombre normalizado y unidad base **suman** cantidad. Por eso la
     respuesta son las filas resultantes, que es lo que el cliente necesita
     para pintar la tabla ya normalizada.
   - **Los items viajan en la unidad que dijo el usuario** (1 l), no en la
     base (1000 ml). La conversión la hace `add_items` al guardar, igual que
     para el bot; convertir antes haría que la pantalla de confirmación
     enseñara números que el usuario no reconoce.
   - **Las clases de formulario se extraen a `lib/ui.ts`.** La nevera tiene ya
     dos formularios (editar una fila y dar de alta) que deben parecer el
     mismo; repetir las clases en dos ficheros es garantía de que diverjan.

   Verificado con 13 tests (`api/tests/test_nevera_alta.py`, contra la Supabase
   real, con centinela y limpieza en `tearDown`). La llamada a Gemini se
   sustituye por un doble: lo que se prueba es el contrato HTTP —códigos, forma
   y validación—, no la calidad del parseo, que ya tiene sus tests en
   `nevera/tests/test_parsing.py`; llamar a Gemini de verdad sería lento, caro
   y no determinista.

   **Verificación end-to-end (2026-09-02):** backend local y SPA local contra
   la Supabase real. `POST /api/nevera/parse` → `200` en ~3 s con los items
   propuestos y **ninguna fila escrita**; corrección en pantalla; `POST
   /api/nevera/items` → `201` con las filas ya normalizadas y la tabla
   refrescándose sola. Item de prueba borrado después con el `DELETE` de la
   fase 4.

   **6.c [hecho y verificado e2e, 2026-09-02] Sugerencias de comida y consumo.**
   `POST /api/nevera/suggestions` + `POST /api/nevera/consume` y la pantalla
   `/comer` de la SPA (`routes/Comer.tsx`, pestaña nueva en la barra).

   Decisiones de esta parte:
   - **Al confirmar se mandan los ingredientes, no "la receta número 2".**
     Mandar el índice obligaría al servidor a recordar lo que propuso, que es
     justo el estado del que se libró la 6.b. La objeción —así el cliente
     decide cuánto se resta de la BD— no se sostiene aquí: quien llega está
     autenticado como el dueño y desde la fase 4 ya puede poner cualquier
     cantidad en cualquier item con un `PATCH`. El endpoint no concede ningún
     poder nuevo. En un sistema multiusuario, o si el descuento tuviera efectos
     fuera del inventario (facturar, pedir stock), la respuesta sería la
     contraria: el servidor tendría que derivar las cantidades de algo que él
     controle.
   - **`POST` para pedir sugerencias, aunque sea una consulta.** Cada llamada
     gasta una petición a Gemini: no es idempotente en coste y ningún proxy
     debe cachearla. Además los términos de exclusión son texto libre y varios,
     y un `GET` con cuerpo no es una opción.
   - **`409` si la nevera está vacía** o si al excluir no queda nada. No es un
     `404` (la nevera existe) ni un `400` (la petición era correcta): es el
     estado del recurso lo que impide atenderla, mismo criterio que el `409`
     del lock de análisis.
   - **`200` aunque falte un ingrediente**, no `404`. Que ya no queden tomates
     no invalida la comida ni deshace lo que sí se descontó. El detalle va en
     el cuerpo (`aplicados` / `basicos` / `no_encontrados`) y ninguno de los
     tres bloques es un error: los básicos no se descuentan a propósito, porque
     se gestionan por presencia y si no una receta con "sal: 1 ud" borraría la
     sal del inventario.
   - **Confirmar una receta borra las demás sugerencias de la pantalla.** Ya no
     valen: se han gastado ingredientes y las cantidades sobre las que se
     propusieron no son las que hay ahora.
   - **Los términos de exclusión que no casan con nada se devuelven en
     `not_found`** y la pantalla los enseña en rojo. Casi siempre son una
     errata, y callarlos haría parecer que la exclusión se ignoró.

   Verificado con 12 tests (`api/tests/test_nevera_comer.py`, Gemini
   sustituido por un doble) que cubren el descuento, la conversión de unidad
   antes de restar, el borrado al agotarse, los básicos que no se tocan y el
   rechazo de una unidad desconocida sin escribir nada.

   **Verificación end-to-end (2026-09-02):** `POST /api/nevera/suggestions` →
   `200` con recetas reales sobre el inventario real, y `POST
   /api/nevera/consume` → `200` con la nevera descontada y la tabla
   refrescándose sola.

   **6.d [hecho, pendiente de verificación e2e] Ofertas del supermercado.**
   `POST /api/ofertas/analyze` y la pantalla `/comprar` de la SPA. Es la única
   función del proyecto que nace pensada para la web y no para el bot
   (decisión §7-G).

   Decisiones de esta parte:
   - **`precio` viaja como texto, no como número.** Llega tal cual aparece en
     la oferta y muchas promociones no son un precio: `2x1`, `-30%`,
     `5,99 zł/kg`. Convertirlo a decimal obligaría a decidir divisa, formato y
     qué hacer con lo que no es una cifra, a cambio de nada: aquí solo se
     muestra. Si algún día hay que ordenar por precio o calcular ahorro, ese
     será el momento de parsearlo, y con reglas explícitas.
   - **Lista vacía = `200`, no `404`.** "Ninguna oferta compensa" es una
     respuesta del análisis, no la ausencia de un recurso. La pantalla lo dice
     con palabras en vez de quedarse en blanco, que se leería como un fallo.
   - **La nevera vacía no bloquea**, al contrario que en las sugerencias: sin
     inventario todavía se pueden recomendar ofertas buenas de básicos, pero no
     se puede cocinar con la nevera vacía. Por eso allí hay `409` y aquí no.
   - **Tope de 12.000 caracteres** (`MAX_OFERTAS_CHARS`), frente a los 4.000
     del alta: una lista de la compra son unas líneas y una gazetka transcrita
     son varias páginas.

   Verificado con 7 tests (`api/tests/test_ofertas.py`, Gemini sustituido por
   un doble). `ruff`, `mypy` y los 185 tests del backend en verde; `tsc`,
   `vite build` y `vitest` del frontend también.

   **Pendiente:** la prueba en pantalla con una gazetka real. Hasta que esté,
   la fase 6 no se da por cerrada.

7. **Repaso y cierre.** Reparto final por canal en la tabla del §4.1 y
   herencia para el SDD de nube en el §9. Pendiente de cerrar cuando la 6.d
   tenga su verificación en pantalla.

## 9. Lo que hereda el SDD de nube

Todo esto se ha dejado a propósito fuera de este SDD porque depende de dónde se
despliegue, no de cómo esté escrita la aplicación. Listado aquí para que el
siguiente documento no empiece de cero.

**Bloqueantes para exponer nada públicamente:**

- **Hosting del backend.** Hoy es `runserver` en local; la SPA en Vercel solo
  se probó contra un túnel `cloudflared` de usar y tirar. Sin backend alojado
  no hay web de verdad.
- **`DJANGO_ENV=prod` de verdad**: `DEBUG=False`, `SECRET_KEY` desde el
  entorno (hay historial de una filtrada: no repetirlo), `ALLOWED_HOSTS` con el
  dominio real y `CORS_ALLOWED_ORIGINS` con el de Vercel, sin los extras de dev.
- **HTTPS y dominio.** Con JWT en `localStorage`, todo el tráfico tiene que ir
  cifrado o el token viaja a la vista.
- **Secretos**: `.env` no se despliega. Hacen falta variables de entorno del
  proveedor o un gestor de secretos (Key Vault, Secret Manager).

**Deuda técnica conocida, con nombre:**

- **`POST /api/analyses` es síncrono.** Medido: 40 s. Muchos proxies y gateways
  gestionados cortan entre 30 y 60 s, y además cada análisis deja un worker
  ocupado. El arreglo estándar es encolar y devolver `202 Accepted` con un id
  que el cliente consulta; exige dónde ejecutar el trabajo (hilo o cola tipo
  Celery/RQ) y una tabla de estado. La mitad difícil —la exclusión entre
  procesos— ya está resuelta con el advisory lock. Lo mismo aplica, en menor
  medida, a los otros endpoints que llaman a Gemini (`parse`, `suggestions`,
  `ofertas/analyze`), que tardan segundos y no medio minuto.
- **`daily_sync.py` termina con código 0 aunque falle el análisis.** El
  `try/except` de `push_daily_analysis` es deliberado (un fallo del análisis no
  debe perder los datos ya sincronizados), pero desatendido en la nube ese `0`
  es una mentira que ningún monitor detectaría. Hace falta separar "la sync fue
  bien" de "todo fue bien" en el código de salida o en las métricas.
- **No hay BD de test.** Los tests corren contra la Supabase real con prefijos
  centinela. Funciona con un desarrollador; en CI compartida o con dos personas
  a la vez, no.
- **El bot es un proceso de long polling en el portátil.** Para que viva en la
  nube hay que decidir entre seguir con polling en un contenedor siempre
  encendido o pasar a webhooks.
