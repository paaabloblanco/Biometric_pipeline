"""
Sincronización diaria completa y desatendida:
1) Descomprime el export de Health Connect que Google Drive deja en
   HEALTH_CONNECT_ZIP (un .db dentro de un .zip).
2) Sube los datos del último día disponible a Supabase (reutilizando
   la lógica de extractor.py).

Pensado para ejecutarse desde el Programador de tareas de Windows,
sin nadie mirando la consola — por eso todo queda también en logs/daily_sync.log.
"""

import logging
import os
import sys
import zipfile
from pathlib import Path

from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "daily_sync.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

ZIP_PATH = Path(os.environ["HEALTH_CONNECT_ZIP"])
DB_MEMBER_NAME = "health_connect_export.db"
DB_TARGET_PATH = BASE_DIR / DB_MEMBER_NAME


def extract_db_from_zip():
    """Saca health_connect_export.db del zip de Drive a la raíz del proyecto."""
    if not ZIP_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró el zip en {ZIP_PATH}. ¿Ya terminó de sincronizar Google Drive hoy?"
        )

    with zipfile.ZipFile(ZIP_PATH) as zf:
        if DB_MEMBER_NAME not in zf.namelist():
            raise ValueError(f"El zip no contiene '{DB_MEMBER_NAME}'. Contenido: {zf.namelist()}")
        with zf.open(DB_MEMBER_NAME) as source, open(DB_TARGET_PATH, "wb") as target:
            target.write(source.read())

    log.info("Base de datos extraída a %s", DB_TARGET_PATH)


def main():
    log.info("=== Iniciando sincronización diaria ===")

    try:
        extract_db_from_zip()
    except Exception:
        log.exception("Fallo al extraer el .db del zip")
        sys.exit(1)

    # Reutilizamos extractor.py importándolo como módulo, en vez de duplicar su lógica.
    import extractor

    # Ruta absoluta explícita: no confiamos en el directorio de trabajo actual,
    # porque el Programador de tareas de Windows no siempre lo deja donde esperamos.
    extractor.SQLITE_PATH = str(DB_TARGET_PATH)

    try:
        extractor.main()
    except SystemExit as exc:
        if exc.code not in (0, None):
            log.error("extractor.main() terminó con errores (code=%s)", exc.code)
            sys.exit(exc.code)
    except Exception:
        log.exception("Fallo al sincronizar con Supabase")
        sys.exit(1)

    push_daily_analysis()

    log.info("=== Sincronización diaria completada ===")


def push_daily_analysis():
    """Genera el análisis del día con Gemini y lo envía por Telegram.

    Un fallo aquí NO debe tumbar la sync (que ya terminó bien): se registra y
    se continúa.
    """
    try:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
        import django

        django.setup()  # idempotente: no-op si ya está inicializado

        from bot.config import DEFAULT_INSTRUCTION
        from bot.notifier import send_message
        from health_ai.pruebas import run_analysis

        log.info("Generando análisis diario para Telegram…")
        result = run_analysis(DEFAULT_INSTRUCTION, send_to_api=True)
        if send_message(result["response"]):
            log.info("Análisis diario enviado por Telegram.")
        else:
            log.warning("El análisis se generó pero falló el envío por Telegram.")
    except Exception:
        log.exception("Fallo al generar/enviar el análisis diario (la sync sí terminó bien)")


if __name__ == "__main__":
    main()
