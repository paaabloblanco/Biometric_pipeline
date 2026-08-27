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

sys.stdout.reconfigure(encoding="utf-8")

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

    log.info("=== Sincronización diaria completada ===")


if __name__ == "__main__":
    main()
