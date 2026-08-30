# SDD — Bot de Telegram

Documento de diseño. Estado: **propuesta**. Fecha: 2026-08-28.

## 1. Objetivo

Convertir el pipeline ya existente (sync diaria + análisis de Gemini) en un
producto usable desde el móvil: recibir el análisis diario automáticamente y
poder pedir análisis bajo demanda sin abrir la consola.

No objetivos (de esta iteración):
- Control de la nevera (feature siguiente; el bot será su interfaz).
- Multiusuario. El bot sirve a una sola persona.
- Panel web / API HTTP.

## 2. Actores

| Actor | Rol |
|---|---|
| Usuario (tú) | Único cliente autorizado. Identificado por `chat_id`. |
| Programador de tareas de Windows | Lanza `daily_sync` y mantiene vivo el proceso del bot. |
| Gemini API | Genera el texto del análisis (ya integrado en `health_ai/pruebas.py`). |
| Telegram Bot API | Transporte de mensajes. Modo **long polling** (sin webhook, sin HTTPS público). |

## 3. Decisión de arquitectura

**Opción A: proceso Python standalone en modo polling.** Descartadas:

- **Webhook + Django view**: exige HTTPS público (túnel/hosting) para un uso
  personal. Sobredimensionado.
- **Solo notificaciones HTTP desde `daily_sync`**: no permite comandos ni sirve
  de base para la nevera.
- **Serverless (Supabase Edge Function)**: otro runtime/lenguaje, no reutiliza
  el código Python/Django existente.

Ventajas de A: sin puertos expuestos, cero infra nueva, reutiliza el entorno
Django y `run_analysis()` tal cual.

Coste: un proceso extra que hay que mantener vivo (ver §8).

## 4. Componentes

Nuevo paquete `bot/` en la raíz del repo:

```
bot/
  __init__.py
  config.py      # carga .env, valida token y allowlist, arranca Django
  main.py        # construye la Application, registra handlers, run_polling()
  handlers.py    # un handler por comando; sin lógica de negocio
  notifier.py    # send_message(text): envío puntual reutilizable (push diario)
  formatting.py  # troceo a <=4096 chars, saneado de Markdown
```

Reglas:
- `handlers.py` **no** habla con la BD ni con Gemini directamente: llama a
  `health_ai.pruebas.run_analysis()` y a `supabase_data.services`.
- `notifier.py` es independiente de la `Application` de polling: crea un `Bot`
  efímero, envía y sale. Así `daily_sync.py` puede importarlo sin arrancar el
  bot completo.
- Arranque de Django idéntico al de `pruebas.py`:
  `DJANGO_SETTINGS_MODULE=core.settings` + `django.setup()`.

### Dependencia nueva

`python-telegram-bot` (v21+, async nativo). Añadir a `requirements.txt`.

## 5. Configuración (.env)

| Variable | Descripción |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token de @BotFather. |
| `TELEGRAM_ALLOWED_CHAT_IDS` | Lista separada por comas de `chat_id` autorizados. |
| `TELEGRAM_DEFAULT_INSTRUCTION` | Instrucción por defecto para `/analisis` sin argumentos. |

Añadir estas tres a `.env.example`. El `.env` ya está en `.gitignore`.

Todo mensaje cuyo `chat_id` no esté en la allowlist se **ignora** (log a
`WARNING`, sin responder, para no confirmar que el bot existe).

## 6. Comandos (iteración 1)

| Comando | Acción |
|---|---|
| `/start`, `/help` | Texto de ayuda con la lista de comandos. |
| `/analisis [instrucción]` | Ejecuta `run_analysis(instrucción or DEFAULT, send_to_api=True)`. Responde primero "Analizando…", luego el texto. Guarda en `ai_analysis_log` (comportamiento actual). |
| `/hoy` | Datos crudos resumidos del último día (`get_last_day_data`): nº de muestras por tabla, RHR, SpO2 media, TST. Sin llamar a Gemini. |
| `/historial [n]` | Últimos `n` análisis (por defecto 3) desde `get_recent_analyses`. |

Fuera de un comando conocido → responde con `/help`.

## 7. Flujos

### 7.1 Análisis bajo demanda

```
Usuario → /analisis "céntrate en el sueño"
  bot: valida chat_id
  bot → "Analizando… (~15-30 s)"
  bot: run_analysis(instrucción)           # get_last_day_data + historial + Gemini + save
  bot: formatting.split(texto)             # trocear a <=4096
  bot → mensaje(s) con el análisis
  en error: bot → "No se pudo completar el análisis: <motivo>"; log EXCEPTION
```

`run_analysis` es síncrono y bloquea ~segundos → ejecutarlo en
`asyncio.to_thread(...)` para no congelar el event loop del bot.

### 7.2 Push diario

```
Programador de tareas (diario) → daily_sync.py
  extrae .db, sube a Supabase                 # comportamiento actual
  [NUEVO] si la sync fue OK:
     from bot.notifier import send_analysis_of_the_day
     run_analysis(DEFAULT_INSTRUCTION)  →  notifier.send_message(texto)
  errores del push no deben tumbar la sync (log y continuar)
```

Decisión abierta (§10-A): ¿el push diario manda el **análisis completo de
Gemini**, o solo un **aviso corto** ("sync OK, 1.240 muestras; pide /analisis")?

## 8. Despliegue y supervivencia del proceso (Windows)

- Tarea programada nueva "telegram-bot": acción `venv\Scripts\python.exe -m bot.main`,
  "ejecutar tanto si el usuario inició sesión como si no", **reiniciar si falla**
  cada 1 min, indefinidamente.
- Alternativa más robusta: [NSSM](https://nssm.cc/) para correrlo como servicio
  de Windows con reinicio automático y rotación de logs.
- `main.py` usa `run_polling()` con `drop_pending_updates=True` para no procesar
  la cola acumulada tras una caída.
- Un solo proceso de polling a la vez (Telegram da error 409 si hay dos).

## 9. Observabilidad y errores

- Logging a `logs/telegram_bot.log` (mismo patrón que `daily_sync.py`;
  `logs/` ya está en `.gitignore`).
- Handler global de errores de `python-telegram-bot` → log `EXCEPTION` + intento
  de avisar al usuario con un mensaje genérico.
- `formatting.py`: si el `parse_mode=Markdown` de Telegram falla por caracteres
  sueltos del texto de Gemini, reintento sin `parse_mode` (texto plano).

## 10. Decisiones

- **A. Contenido del push diario**: **análisis completo de Gemini**. _(resuelto 2026-08-28)_
- **B. Disparador del análisis diario**: **dentro de `daily_sync.py`**, tras
  confirmar sync OK. _(resuelto 2026-08-28)_
- **C. `/analisis` repetido el mismo día**: `save_analysis` hace
  `update_or_create` por fecha → se sobrescribe. ¿Aceptable? Propuesta: sí, y el
  bot avisa "(sobrescribe el análisis de hoy)".
- **D. Rate limiting**: ¿límite de N `/analisis` por hora para no gastar cuota de
  Gemini por accidente? Propuesta: 1 análisis en curso a la vez (lock simple);
  sin límite horario de momento.

## 11. Pruebas

- `bot/tests/test_formatting.py`: troceo en límites de 4096, no parte palabras a
  mitad, respeta saltos de párrafo.
- `bot/tests/test_config.py`: parseo de `TELEGRAM_ALLOWED_CHAT_IDS`
  (vacío, uno, varios, espacios).
- `handlers`: test con `unittest.mock` sobre `run_analysis` y un `Update` falso;
  verifica que un `chat_id` no autorizado no llama a `run_analysis`.
- Manual: `python -m bot.notifier "mensaje de prueba"` envía a tu chat.

## 12. Plan de implementación (por fases)

1. [hecho] **Andamiaje**: `bot/config.py` + `bot/notifier.py` + CLI de prueba.
   Dependencia `python-telegram-bot==22.8` y `.env.example`.
2. [hecho] **`formatting.py`** + tests (`bot/tests/`).
3. [hecho] **`main.py` + `handlers.py`**: `/start`, `/help`, `/hoy`, `/historial`.
4. [hecho] **`/analisis`** con `asyncio.to_thread` y lock de "análisis en curso".
5. [hecho] **Push diario**: `push_daily_analysis()` en `daily_sync.py`.
6. [pendiente] **Despliegue**: tarea programada / NSSM + doc en el README.

### Cómo ejecutar

```
venv\Scripts\python.exe -m bot.main        # bot interactivo (proceso permanente)
venv\Scripts\python.exe -m bot.notifier "texto"   # envío puntual de prueba
venv\Scripts\python.exe -m unittest discover -s bot/tests
```
