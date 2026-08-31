# CLAUDE.md

Guía para trabajar en este repo. Léela antes de tocar código.

## Propósito: esto es un proyecto de APRENDIZAJE

El objetivo no es solo que el pipeline funcione: es que el usuario **entienda y
sepa explicar** lo que hay montado. Aspira a trabajar en desarrollo/cloud, así
que el proyecto es a la vez portfolio y material de estudio. Esto **prevalece
sobre la velocidad**: es preferible una entrega más lenta y entendida que una
rápida y opaca.

**Cómo se traduce en cada intervención:**

- **Nombra los conceptos con su nombre técnico.** No digas "la carpeta donde
  está la lógica": di *capa de servicio (service layer)*. No digas "el fichero
  que traduce el modelo a JSON": di *serializador*. El usuario quiere el
  vocabulario que se usa en entrevistas y en equipos reales, en español y con
  el término inglés entre paréntesis la primera vez.
- **Explica el porqué arquitectónico, no solo el qué.** Cada decisión de diseño
  (por qué `services.py` y no lógica en las vistas, por qué `managed=False`,
  por qué JWT y no sesiones, por qué monorepo) lleva un trade-off detrás.
  Explícalo: qué se gana, qué se pierde, qué alternativa se descartó.
- **Antes de introducir cualquier herramienta nueva, explica su uso
  empresarial.** Qué problema resuelve, quién la usa y para qué en una empresa
  de verdad, cómo encaja en un equipo (quién la toca, en qué momento del ciclo),
  y cuáles son las alternativas del mercado. Ejemplos de cosas que el usuario
  aún no conoce y que hay que explicar cuando aparezcan: el **admin de Django**,
  **Swagger/OpenAPI**, migraciones, ORM vs SQL crudo, CI/CD, contenedores.
- **Explica cómo se gestionan los datos en la práctica.** Cuando toquemos la BD:
  cuál es la forma idiomática y eficiente de leer/escribir con el ORM
  (`select_related`, problema N+1, transacciones, `bulk_create`), qué se hace a
  mano y qué se automatiza, y cómo se cambian datos en producción de verdad
  (admin, shell, comando de gestión, migración de datos) y cuándo cada uno.
- **Enseña las herramientas de diagnóstico**, no solo la solución. Cómo leer un
  traceback, cómo mirar el SQL que genera el ORM, dónde están los logs.
- **Pregunta antes de asumir nivel.** Si un concepto es prerequisito de lo que
  viene, comprueba si lo conoce en vez de darlo por sabido o de explicar algo
  que ya domina.

**Excepción de autoría:** en la línea de trabajo de infraestructura (Docker,
Azure, Terraform, CI/CD) el usuario quiere **escribir él el código**: ahí actúa
como mentor socrático — preguntas guía y pasos pequeños verificables, no
implementación directa. En el resto del repo se implementa normal, pero con la
explicación por delante.

## Qué es

Pipeline biométrico personal de un solo usuario:

1. **Sync** — `extractor.py` lee el export de Health Connect (SQLite) y sube el
   último día a Supabase (Postgres). `daily_sync.py` lo automatiza: descomprime
   el `.db` del zip de Google Drive, sincroniza y dispara el análisis diario.
2. **Análisis IA** — `health_ai/pruebas.py` construye un prompt con los datos
   crudos + el historial de análisis y lo manda a Gemini (`google-genai`).
3. **Bot de Telegram** (`bot/`) — interfaz de captura y consulta (análisis,
   nevera, sugerencias de comida, ofertas). Long polling, un solo proceso.
4. **Interfaz web** (`backend/api/` + `frontend/`, en construcción) — segunda interfaz de
   consulta/gestión: API REST (DRF) sobre los mismos servicios + SPA React en
   Vercel. Ver `docs/SDD-web.md`.

## Stack

- Python 3.12+ · Django 6.1 (no se usan vistas server-rendered salvo el admin)
- Postgres gestionado por Supabase (conexión por `DATABASES`, credenciales en `.env`)
- python-telegram-bot 22 · google-genai · djangorestframework + simplejwt
- Tests: `unittest` (runner) — `pytest` también descubre. Lint: `ruff`. Tipos: `mypy`.

## Layout

Monorepo: `backend/` (todo Python) + `frontend/` (SPA React, Vercel). Los
comandos Python (venv, manage.py, ruff, tests) se ejecutan **desde `backend/`**.

```
backend/
  core/            # proyecto Django. settings/ es un paquete (ver abajo)
  extractor.py     # sync SQLite -> Supabase
  daily_sync.py    # orquesta la sync diaria + push del análisis
  health_ai/pruebas.py   # prompt + llamada a Gemini (run_analysis)
  supabase_data/   # modelos de SOLO LECTURA sobre tablas del sync (managed=False)
  nevera/          # inventario de nevera (tablas propias, managed=True)
  bot/             # bot de Telegram: main.py (arranque) + handlers.py + services
  api/             # API REST para la web (capa fina, sin lógica de negocio)
  venv/  manage.py  pyproject.toml  requirements*.txt  .env
frontend/          # SPA React + Vite, deploy en Vercel (Root Directory = frontend)
docs/              # SDDs (documentos de diseño por feature)
```

## Convenciones (importantes)

- **La lógica de negocio vive en `*/services.py`.** `bot/handlers.py` y
  `api/views.py` son capas finas: parsean entrada, llaman a un servicio,
  formatean salida. No metas lógica ahí. El bot llama a los servicios
  in-process; la web entra por la API. Misma BD = única fuente de verdad.
- **`supabase_data` es `managed = False`.** Esas tablas las crea el sync
  externo, no Django. Nunca hagas `migrate` para cambiar su esquema; solo
  actualiza el modelo para reflejar la tabla real. Las migraciones de esta app
  son solo de estado.
- **`nevera` es `managed = True`.** Cambios de esquema = `makemigrations nevera`
  + `migrate` normales.
- **Settings por entorno.** `DJANGO_SETTINGS_MODULE` es siempre `core.settings`.
  El entorno lo elige `core/settings/__init__.py` según `DJANGO_ENV`
  (`dev` por defecto, `prod`). Config común en `base.py`.
- **Comandos de Telegram**: solo `[a-z0-9_]`. Por eso `/anadir`, no `/añadir`
  (la función sí se llama `añadir`).
- **Estado conversacional del bot** (`_pending_altas`, `_pending_recetas` en
  `handlers.py`) vive en memoria del proceso y se pierde al reiniciar. La API
  NO usa ese estado: resuelve parse→confirmar en dos requests sin estado.
- **Tests contra la BD real** (no hay BD de test): usan prefijo único en los
  nombres y limpian en `tearDown`. Sigue ese patrón, no dejes basura.
- Docstrings y comentarios en español, como el resto del repo.

## Comandos

```bash
cd backend   # todos los comandos Python parten de aquí

# entorno
venv/Scripts/python -m pip install -r requirements-dev.txt

# calidad (lo que corre CI)
venv/Scripts/python -m ruff check .
venv/Scripts/python -m ruff format --check .
venv/Scripts/python -m mypy .
venv/Scripts/python -m unittest discover -s . -p "test_*.py"

# Django
venv/Scripts/python manage.py makemigrations --check --dry-run
venv/Scripts/python manage.py migrate

# ejecutar
venv/Scripts/python -m bot.main            # bot (long polling)
venv/Scripts/python daily_sync.py          # sync diaria manual
DJANGO_ENV=dev venv/Scripts/python manage.py runserver   # API

# frontend (desde frontend/)
npm install && npm run dev
```

## Hooks (`.claude/`)

Guardarraíles automáticos (`.claude/settings.json` + `.claude/hooks/*.py`):

| Cuándo | Qué hace |
|---|---|
| Antes de editar | Bloquea escrituras a `.env`, `*.pem`, `*.key`, `credentials.json`… (permite `.env.example`) |
| Antes de `git push` | Pide confirmación si el push va a `main` |
| Tras editar un `.py` | `ruff format` + orden de imports sobre ese fichero |
| Al terminar (Stop) | `ruff check` + `ruff format --check`; avisa si algo falla (no bloquea) |

Tras clonar o si no se activan: abrir `/hooks` una vez o reiniciar Claude Code.

## Reglas críticas

- **Nunca** subas `.env` ni ningún secreto (hay historial de una `SECRET_KEY`
  filtrada — no repetirlo). El `.env` está en `.gitignore`.
- **Nunca** hagas `git push` directo a `main`: rama + merge.
- No toques el esquema de tablas `managed = False`.
- Antes de avanzar de fase en un SDD, verifica la fase con una prueba real
  end-to-end (no solo tests unitarios).
- Si cambias dependencias, actualiza `requirements.txt` (runtime) o
  `requirements-dev.txt` (herramientas) con la versión exacta.
