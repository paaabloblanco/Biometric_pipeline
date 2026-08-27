import os
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
# Asegurar que Django se inicialice antes de importar modelos
import django
try:
    django.setup()
except Exception:
    # Si ya está inicializado o falla por estar en un contexto distinto, continuar
    pass

# Importamos la función que devuelve el JSON del último día guardado
from supabase_data.services import get_last_day_data_json

PROMPT_TEMPLATE = (
    "Actúa como un científico deportivo y analista de rendimiento de élite. El usuario te ha solicitado: \"{instruccion_usuario}\"\n"
    "\n"
    "A continuación, se proporcionan datos biométricos crudos en formato JSON extraídos del ecosistema de monitorización del atleta. \n"
    "\n"
    "⚠️ CONTEXTO CRUCIAL DEL ATLETA:\n"
    "- El atleta NO utiliza el monitor durante las sesiones de entrenamiento.\n"
    "- Por lo tanto, no busques carga de entrenamiento (Training Load) en estos datos.\n"
    "- Tu análisis debe centrarse EXCLUSIVAMENTE en la recuperación, la homeostasis, las tendencias del sueño y el estrés del sistema nervioso autónomo (SNA) basado en los datos de reposo.\n"
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
    "🎯 DIRECTRICES DEL ANÁLISIS:\n"
    "1. Evalúa la desviación de la RHR y SpO2 respecto a la línea base. Una RHR elevada sostenida debe interpretarse como fatiga central o estrés del SNA.\n"
    "2. Analiza la arquitectura del sueño. ¿Se ha respetado el 30% de sueño profundo (esencial para recuperación física) y el 15% REM (recuperación cognitiva)?\n"
    "3. Entrega un análisis técnico, conciso y profesional, evitando tono excesivamente conversacional o entusiasta.\n"
    "4. Formatea la salida para ser leída en una interfaz móvil (Telegram). Usa formato Markdown (negritas) para métricas clave, listas precisas y párrafos de máximo 2 líneas.\n"
)


def build_prompt(instruccion_usuario: str, json_data: str) -> str:
    """Construye el prompt final sustituyendo los placeholders."""
    return PROMPT_TEMPLATE.format(instruccion_usuario=instruccion_usuario, json_data=json_data)


def _load_env_candidates() -> Optional[Path]:
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


def send_prompt_to_gemini(prompt: str, timeout: float = 60.0) -> str:
    """Envía el prompt a la API configurada en variables de entorno.

    Variables usadas (leer desde .env):
    - GEMINI_API_KEY (obligatorio)
    - GEMINI_API_URL (opcional). Si se proporciona, se hace POST con JSON {"model": model, "prompt": prompt}
    - GEMINI_MODEL (opcional) - nombre del modelo, por defecto 'models/text-bison-001'

    Si no se proporciona GEMINI_API_URL, se intenta la URL de la API Generativa de Google
    como fallback: https://generativelanguage.googleapis.com/v1beta2/{model}:generate?key={API_KEY}

    La función intenta extraer texto de la respuesta usando varias heurísticas.
    """
    _load_env_candidates()

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API")
    if not api_key:
        raise RuntimeError(
            "No se encontró GEMINI_API_KEY en el entorno. Añádela en health_ai/.env con la clave GEMINI_API_KEY."
        )

    model = os.getenv("GEMINI_MODEL", "models/text-bison-001")
    url = os.getenv("GEMINI_API_URL")

    headers = {"Content-Type": "application/json"}

    # Preferir Authorization Bearer si el usuario configuró URL personalizada
    if url:
        headers["Authorization"] = f"Bearer {api_key}"
        payload = {"model": model, "prompt": prompt}
        resp = httpx.post(url, json=payload, headers=headers, timeout=timeout)
    else:
        # Intentar llamada a la API generativa de Google con api key en querystring
        gen_url = f"https://generativelanguage.googleapis.com/v1beta2/{model}:generate?key={api_key}"
        payload = {"prompt": {"text": prompt}}
        resp = httpx.post(gen_url, json=payload, headers=headers, timeout=timeout)

    if resp.status_code >= 400:
        raise RuntimeError(f"Error en llamada a la API ({resp.status_code}): {resp.text}")

    j = resp.json()

    # Heurísticas para extraer texto de la respuesta
    # 1) Google generative returns 'candidates' or 'output'
    if isinstance(j, dict):
        if "candidates" in j and isinstance(j["candidates"], list) and j["candidates"]:
            c = j["candidates"][0]
            return c.get("output", c.get("content", json.dumps(c, ensure_ascii=False)))

        if "output" in j:
            # output may be a list of blocks with content containing text
            out = j["output"]
            if isinstance(out, list):
                # search for content->text
                for block in out:
                    if isinstance(block, dict) and "content" in block:
                        for item in block.get("content", []):
                            if isinstance(item, dict) and "text" in item:
                                return item["text"]
            # fallback to stringifying
            return json.dumps(out, ensure_ascii=False)

        # 2) OpenAI-like responses
        if "choices" in j and isinstance(j["choices"], list) and j["choices"]:
            ch = j["choices"][0]
            # chat-completions style
            if "message" in ch and "content" in ch["message"]:
                return ch["message"]["content"]
            if "text" in ch:
                return ch["text"]

    # Fallback: devolver JSON completo como string
    return json.dumps(j, ensure_ascii=False, indent=2)


def run_analysis(instruccion_usuario: str, send_to_api: bool = True) -> Dict[str, Any]:
    """Construye el prompt y opcionalmente lo envía a la API.

    Devuelve un dict con keys: 'prompt' y, si send_to_api es True, 'response'.
    """
    # Obtener JSON del servicio (string)
    datos_json_str = get_last_day_data_json()

    # Intentar parsear para obtener un JSON pretty (asegurar indent y caracteres unicode)
    try:
        datos = json.loads(datos_json_str)
        datos_pretty = json.dumps(datos, ensure_ascii=False, indent=2)
    except Exception:
        # Si no se puede parsear, usar la cadena tal cual
        datos_pretty = datos_json_str

    prompt = build_prompt(instruccion_usuario, datos_pretty)

    result: Dict[str, Any] = {"prompt": prompt}

    if send_to_api:
        # Enviar el prompt a la API y guardar la respuesta
        response_text = send_prompt_to_gemini(prompt)
        print(response_text)
        result["response"] = response_text
    else:
        # Solo imprimir el prompt para uso desde CLI
        print(prompt)

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python health_ai/pruebas.py \"<instruccion_usuario>\" [--no-send]")
        sys.exit(1)

    instruction = sys.argv[1]
    no_send = False
    if len(sys.argv) > 2 and sys.argv[2] == "--no-send":
        no_send = True

    run_analysis(instruction, send_to_api=not no_send)
