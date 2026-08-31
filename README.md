# Proyecto Salud

Pipeline biométrico personal: sincroniza los datos de **Health Connect** a
**Supabase**, los analiza con **Gemini** y los expone por un **bot de Telegram**
(y, en construcción, una **interfaz web** en React).

> Proyecto de un solo usuario. No está pensado como servicio multiusuario.

## Arquitectura

```
Health Connect (export SQLite)
        │  extractor.py / daily_sync.py
        ▼
   Supabase (Postgres) ──────────────┐
        │                            │
        │  supabase_data/services.py │  nevera/services.py
        ▼                            ▼
   health_ai/ (Gemini) ◄──── lógica de negocio ────►
        │                            │
        ├──────────────┬─────────────┤
        ▼              ▼             ▼
   bot/ (Telegram)   api/ (DRF)   web/ (React, Vercel) — en construcción
```

- **Toda la lógica vive en `*/services.py`.** El bot y la API son clientes
  finos de esos servicios; comparten la misma base de datos.
- `supabase_data/` son modelos de solo lectura (`managed=False`) sobre las
  tablas que crea el sync. `nevera/` gestiona sus propias tablas.
- Detalle de diseño por feature en [`docs/`](docs/).

## Puesta en marcha

```bash
python -m venv venv
venv/Scripts/python -m pip install -r requirements-dev.txt   # o requirements.txt sin las herramientas

cp .env.example .env        # y rellena los valores (Supabase, Gemini, Telegram)
venv/Scripts/python manage.py migrate
venv/Scripts/python manage.py createsuperuser   # para la API web
```

### Ejecutar

| Componente | Comando |
|---|---|
| Bot de Telegram | `venv/Scripts/python -m bot.main` |
| Sync diaria (manual) | `venv/Scripts/python daily_sync.py` |
| API web (dev) | `DJANGO_ENV=dev venv/Scripts/python manage.py runserver` |

En producción se ejecuta con `DJANGO_ENV=prod` (requiere `DJANGO_ALLOWED_HOSTS`
y `CORS_ALLOWED_ORIGINS` en el entorno).

## Desarrollo

```bash
venv/Scripts/python -m ruff check .
venv/Scripts/python -m ruff format --check .
venv/Scripts/python -m mypy .
venv/Scripts/python -m unittest discover -s . -p "test_*.py"
```

Los tests corren **contra la base de datos real** (no hay BD de test): usan un
prefijo único y limpian tras de sí. CI (`.github/workflows/ci.yml`) ejecuta
`ruff` + `mypy` en cada push; el job de tests es opt-in (variable de repo
`RUN_DB_TESTS=true` + secrets de la BD).

Convenciones y reglas del repo: [`CLAUDE.md`](CLAUDE.md).
