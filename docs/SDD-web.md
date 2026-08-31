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

### 3.2 Frontend — nuevo repo/carpeta `web/`

```
web/
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
- **Deploy:** proyecto de Vercel apuntando a `web/`, build `vite build`,
  variable `VITE_API_BASE_URL` con la URL del backend.

## 4. Endpoints (primera iteración)

| Método | Ruta | Servicio Django que envuelve | Equivale a |
|---|---|---|---|
| `POST` | `/api/auth/login` | `django.contrib.auth` + SimpleJWT | — |
| `POST` | `/api/auth/refresh` | SimpleJWT | — |
| `GET` | `/api/health/last-day` | `get_last_day_data()` | `/hoy` |
| `GET` | `/api/health/series?metric=&from=&to=` | consulta nueva en `supabase_data/services.py` | (nuevo — gráficas) |
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

`/api/health/series` es el único servicio de datos nuevo: agrega muestras por
día/rango para las gráficas. El resto son envoltorios directos.

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

- **`DEBUG = True` y `SECRET_KEY` en `core/settings.py`.** Antes de exponer
  nada públicamente hay que separar settings de dev y prod, `DEBUG=False`,
  `ALLOWED_HOSTS` real. Esto se solapa con el SDD de nube; aquí solo se
  señala como bloqueante.
- **Llamadas a Gemini desde la web sin lock compartido.** `run_analysis` tiene
  un `asyncio.Lock` que vive en el proceso del bot. La API es otro proceso: su
  propio lock no coordina con el del bot. Riesgo de dos análisis simultáneos
  (bot + web) gastando cuota. Opción: mover el lock a un lock de BD
  (`select_for_update` sobre una fila de control) o aceptar el riesgo como se
  aceptó en el SDD de nevera. _(decisión §7-C)_
- **Estado conversacional del bot vs. sin estado en la web.** Hay que
  refactorizar `/anadir` y `/comer` para que la lógica de "parsear" y
  "confirmar/consumir" sea llamable por separado desde la API sin depender de
  `_pending_altas` / `_pending_recetas`. Los servicios ya lo permiten
  (`parse_compra_text` + `add_items` son funciones distintas); es sobre todo
  no meter el estado en la capa de API.
- **Dos frontends que mantener.** Cada comando nuevo hay que decidir si va en
  web, en bot, o en ambos. Mitigación: la tabla del §4 es la fuente de verdad
  de qué existe en cada canal; no toda feature tiene que estar en los dos.
- **CSRF vs JWT.** Con JWT en header `Authorization` y sin cookies de sesión
  para la API, el middleware CSRF de Django no aplica a esos endpoints (DRF lo
  gestiona). No mezclar auth por sesión y por token en la misma ruta.
- **Coste de Vercel:** plan hobby gratis cubre de sobra un SPA de un usuario.
  Sin funciones serverless propias no hay riesgo de factura.

## 7. Decisiones abiertas

- **A. Repo del frontend.** **Resuelto: carpeta `web/` en el mismo repo**
  (monorepo). Vercel apunta al subdirectorio. Cambios de API + frontend en el
  mismo commit. _(2026-08-31, con el usuario)_
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
3. [código listo, falta deploy] **Frontend base en Vercel.** Carpeta `web/`:
   Vite + React 18 + TS + React Router + TanStack Query + Tailwind v4. Cliente
   HTTP (`src/api/client.ts`) con JWT en `Authorization` y renovación única en
   vuelo al recibir 401 (evento `salud:logout` cuando el refresh caduca).
   Pantallas Login, Dashboard (last-day + gráficas Recharts de FC y sueño),
   Análisis (histórico) y Nevera (tabla con alerta de caducidad, solo ver).
   `vercel.json` con build y rewrite de SPA; `.env.example` con
   `VITE_API_BASE_URL`. Verificado en local: `npm run build` (tsc + vite) y
   `npm run test` (3 tests de vitest sobre el flujo de refresh del cliente) en
   verde; `dev.py` ya tiene el CORS de `localhost:5173`.
   **Pendiente del usuario:** crear el proyecto en Vercel apuntando a `web/`,
   fijar `VITE_API_BASE_URL`, desplegar el backend en una URL pública y hacer
   la prueba end-to-end (login + datos reales desde el dominio de Vercel).

### Iteración 2 — escrituras

4. **Editar la nevera desde la web.** `PATCH`/`DELETE /api/nevera/items/{id}`
   + edición/borrado en línea en la tabla. Verificación: editar un item en la
   web se refleja en `/nevera` de Telegram y en BD.
5. **Acciones con IA desde la web.** `/api/nevera/parse` + `items`,
   `/api/nevera/suggestions` + `consume`, `/api/analyses` (POST),
   `/api/ofertas/analyze`. Resolver el estado conversacional (§6) y el lock
   (§7-C, `pg_advisory_lock`). Verificación end-to-end de cada flujo:
   parsear→confirmar alta, sugerir→marcar hecho con descuento en BD, lanzar
   análisis.
6. **Repaso y cierre:** revisar qué comandos quedan solo en Telegram a
   propósito, documentar en la tabla §4 el estado final, y dejar listado lo
   que depende del SDD de nube (dominio, HTTPS, `ALLOWED_HOSTS`, CORS de prod).
