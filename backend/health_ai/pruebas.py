import json
import os
import sys
from contextlib import nullcontext
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# La consola de Windows por defecto usa cp1252, que no soporta emojis del prompt.
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
# Asegurar que Django se inicialice antes de importar modelos
import django

django.setup()  # idempotente: no-op si ya está inicializado

from health_ai.locks import LOCK_ANALISIS_DIARIO, LockOcupado, advisory_lock
from supabase_data.services import get_last_day_data, get_recent_analyses, save_analysis

HISTORY_DAYS = 7

PROMPT_TEMPLATE = (
    'Actúa como un científico deportivo y analista de rendimiento de élite. El usuario te ha solicitado: "{instruccion_usuario}"\n'
    "\n"
    "A continuación, se proporcionan datos biométricos crudos en formato JSON extraídos del ecosistema de monitorización del atleta. \n"
    "\n"
    "⚠️ CONTEXTO CRUCIAL DEL ATLETA:\n"
    "- El atleta NO utiliza el monitor durante las sesiones de entrenamiento.\n"
    "- Por lo tanto, no busques carga de entrenamiento (Training Load) en estos datos.\n"
    "- Tu análisis debe centrarse EXCLUSIVAMENTE en la recuperación, la homeostasis, las tendencias del sueño y el estrés del sistema nervioso autónomo (SNA) basado en los datos de reposo.\n"
    "- Las caídas puntuales de SpO2 pueden deberse a una mala colocación del reloj (correa floja o sensor mal apoyado), no necesariamente a un evento fisiológico. Si ves una bajada aislada de SpO2 sin otros signos de estrés (RHR normal, sueño normal), considera y menciona esta causa como la más probable antes de asumir hipoxia o apnea.\n"
    "\n"
    "📊 LÍNEA BASE (Valores medios históricos de referencia):\n"
    "- Frecuencia Cardíaca en Reposo (RHR): 47 bpm\n"
    "- Saturación de Oxígeno (SpO2): 96%\n"
    "- Volumen Total de Sueño (TST): 7h 12m\n"
    "- Arquitectura del Sueño (Media): 30% Profundo (N3), 54% Ligero (N1/N2), 15% REM.\n"
    "\n"
    "📥 DATOS CRUDOS ACTUALES (Para analizar):\n"
    "{json_data}\n"
    "\n"
    "🕓 ANÁLISIS DE DÍAS ANTERIORES (para ver tendencia, no los reanalices):\n"
    "{historial}\n"
    "\n"
    "🎯 DIRECTRICES DEL ANÁLISIS:\n"
    "1. Evalúa la desviación de la RHR y SpO2 respecto a la línea base. Una RHR elevada sostenida debe interpretarse como fatiga central o estrés del SNA. Para la SpO2, distingue entre una tendencia sostenida (relevante) y una caída aislada (probable artefacto por mala colocación del reloj, ver contexto).\n"
    "2. Analiza la arquitectura del sueño. ¿Se ha respetado el 30% de sueño profundo (esencial para recuperación física) y el 15% REM (recuperación cognitiva)?\n"
    "3. Compara con los análisis anteriores: ¿mejora, empeora o se mantiene la tendencia?\n"
    "4. Entrega un análisis técnico, conciso y profesional, evitando tono excesivamente conversacional o entusiasta.\n"
    "5. Formatea la salida para ser leída en una interfaz móvil (Telegram). Usa formato Markdown (negritas) para métricas clave, listas precisas y párrafos de máximo 2 líneas.\n"
)


def format_historial(analyses: list) -> str:
    """Convierte los análisis previos (más reciente primero) en texto legible para el prompt."""
    if not analyses:
        return "(No hay análisis anteriores todavía.)"

    bloques = []
    for a in reversed(analyses):  # orden cronológico: el más antiguo primero
        bloques.append(f"### {a['analysis_date']}\n{a['analysis_text']}")
    return "\n\n".join(bloques)


def build_prompt(instruccion_usuario: str, json_data: str, historial: str) -> str:
    """Construye el prompt final sustituyendo los placeholders."""
    return PROMPT_TEMPLATE.format(
        instruccion_usuario=instruccion_usuario, json_data=json_data, historial=historial
    )


def _load_env_candidates() -> Path | None:
    """Carga el archivo .env local si existe (busca en health_ai/ y en la raíz del repo)."""
    here = Path(__file__).resolve().parent
    candidates = [here / ".env", here.parent / ".env"]
    for p in candidates:
        if p.exists():
            load_dotenv(p)
            return p
    # Fallback a cargar variables de entorno ya presentes
    load_dotenv()
    return None


def send_prompt_to_gemini(prompt: str) -> str:
    """Envía el prompt a Gemini usando el SDK oficial (google-genai).

    Variables usadas (leídas desde .env):
    - GEMINI_API_KEY (obligatorio)
    - GEMINI_MODEL (opcional) - por defecto 'gemini-2.5-flash'
    """
    _load_env_candidates()

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API")
    if not api_key:
        raise RuntimeError(
            "No se encontró GEMINI_API_KEY en el entorno. Añádela en health_ai/.env con la clave GEMINI_API_KEY."
        )

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model=model, contents=prompt)

    if not response.text:
        raise RuntimeError(f"Gemini no devolvió texto. Respuesta cruda: {response}")

    return response.text


class AnalysisInProgress(LockOcupado):
    """Ya hay un análisis en curso en otro proceso (el bot o la API web).

    Es una excepción y no un valor de retorno a propósito: en Python nada
    obliga a mirar lo que devuelve una función, así que un `{"skipped": True}`
    que alguien no comprobara se manifestaría como un mensaje vacío para el
    usuario, lejos de la causa. Además, una excepción con nombre propio deja
    sitio a un segundo motivo el día que lo haya; un booleano, no.

    Cada interfaz la traduce a su medio: la API a un 409 Conflict, el bot a su
    mensaje de "espera a que termine".
    """


def run_analysis(instruccion_usuario: str, send_to_api: bool = True) -> dict[str, Any]:
    """Construye el prompt (con historial de análisis previos) y opcionalmente lo envía a la API.

    Devuelve un dict con keys: 'prompt' y, si send_to_api es True, 'response'.

    Lanza `AnalysisInProgress` si otro proceso está analizando ahora mismo. El
    lock se coge **aquí dentro** y no en cada llamador (bot, API, CLI) por dos
    razones: ninguno puede olvidarse de cogerlo, y se garantiza que cogerlo y
    soltarlo ocurren en el mismo hilo —el bot llama a esta función con
    `asyncio.to_thread`, y la conexión de Django es thread-local—.
    """
    # Solo se protege la llamada de verdad a Gemini. Con `send_to_api=False`
    # (el CLI, que solo imprime el prompt) no se gasta cuota ni se escribe en
    # la BD, así que coger el lock solo serviría para bloquear un análisis real
    # que estuviera en curso. `nullcontext` es un gestor de contexto que no
    # hace nada: evita duplicar el cuerpo de la función en un if/else.
    guarda = (
        advisory_lock(LOCK_ANALISIS_DIARIO, AnalysisInProgress) if send_to_api else nullcontext()
    )
    with guarda:
        return _run_analysis(instruccion_usuario, send_to_api)


def _run_analysis(instruccion_usuario: str, send_to_api: bool) -> dict[str, Any]:
    """El trabajo en sí, ya con el lock cogido (o sin él, si no se envía)."""
    day_data = get_last_day_data()
    target_date = date.fromisoformat(day_data["date"])
    datos_pretty = json.dumps(day_data, ensure_ascii=False, indent=2, default=str)

    analyses = get_recent_analyses(limit=HISTORY_DAYS)
    historial = format_historial(analyses)

    prompt = build_prompt(instruccion_usuario, datos_pretty, historial)

    result: dict[str, Any] = {"prompt": prompt}

    if send_to_api:
        response_text = send_prompt_to_gemini(prompt)
        print(response_text)
        save_analysis(target_date, instruccion_usuario, response_text)
        result["response"] = response_text
    else:
        # Solo imprimir el prompt para uso desde CLI
        print(prompt)

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Uso: python health_ai/pruebas.py "<instruccion_usuario>" [--no-send]')
        sys.exit(1)

    instruction = sys.argv[1]
    no_send = False
    if len(sys.argv) > 2 and sys.argv[2] == "--no-send":
        no_send = True

    run_analysis(instruction, send_to_api=not no_send)
