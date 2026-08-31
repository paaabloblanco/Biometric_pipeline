# CLAUDE.md

Guía para trabajar en este repo. Léela antes de tocar código.

## Qué es

Pipeline biométrico personal de un solo usuario:

1. **Sync** — `extractor.py` lee el export de Health Connect (SQLite) y sube el
   último día a Supabase (Postgres). `daily_sync.py` lo automatiza: descomprime
   el `.db` del zip de Google Drive, sincroniza y dispara el análisis diario.
2. **Análisis IA** — `health_ai/pruebas.py` construye un prompt con los datos
   crudos + el historial de análisis y lo manda a Gemini (`google-genai`).
3. **Bot de Telegram** (`bot/`) — interfaz de captura y consulta (análisis,
   nevera, sugerencias de comida, ofertas). Long polling, un solo proceso.
4. **Interfaz web** (`api/` + `web/`, en construcción) — segunda interfaz de
   consulta/gestión: API REST (DRF) sobre los mismos servicios + SPA React en
   Vercel. Ver `docs/SDD-web.md`.

## Stack

- Python 3.12+ · Django 6.1 (no se usan vistas server-rendered salvo el admin)
- Postgres gestionado por Supabase (conexión por `DATABASES`, credenciales en `.env`)
- python-telegram-bot 22 · google-genai · djangorestframework + simplejwt
- Tests: `unittest` (runner) — `pytest` también descubre. Lint: `ruff`. Tipos: `mypy`.

## Layout

```
core/              # proyecto Django. settings/ es un paquete (ver abajo)
extractor.py       # sync SQLite -> Supabase
daily_sync.py      # orquesta la sync diaria + push del análisis
health_ai/pruebas.py   # prompt + llamada a Gemini (run_analysis)
supabase_data/     # modelos de SOLO LECTURA sobre tablas del sync (managed=False)
nevera/            # inventario de nevera (tablas propias, managed=True)
bot/               # bot de Telegram: main.py (arranque) + handlers.py + services
api/               # API REST para la web (capa fina, sin lógica de negocio)
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
