"""
Sincroniza el último día de datos biométricos desde el export de Health Connect
(SQLite) hacia Supabase.

Tablas origen:
    - heart_rate_record_series_table
    - sleep_stages_table
    - oxygen_saturation_record_table
    - resting_heart_rate_record_table

Tablas destino en Supabase (ver supabase_schema.sql):
    - heart_rate_samples
    - sleep_stages
    - oxygen_saturation_samples
    - resting_heart_rate_samples

Requisitos:
    pip install supabase python-dotenv

Variables de entorno (.env o exportadas):
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY   # service_role, no la anon key
"""

import logging
import os
import sqlite3
import sys
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

log = logging.getLogger(__name__)

SQLITE_PATH = os.environ.get("HEALTH_CONNECT_DB", "health_connect_export.db")
LOCAL_TZ = ZoneInfo("Europe/Warsaw")
CHUNK_SIZE = 500

# Si el último dato de una tabla es más antiguo que esto (en días respecto a
# hoy), lo avisamos: normalmente significa que esa métrica ha dejado de
# sincronizarse desde el móvil aunque las demás sigan entrando.
STALE_AFTER_DAYS = 3

# Health Connect es AOSP/Java: java.util.UUID serializa sus bytes en orden
# big-endian (RFC 4122 estandar), que es lo que usa uuid.UUID(bytes=...).
# bytes_le es el formato de GUIDs estilo Windows/COM, no debería aplicar aqui.
# Si al comparar un registro contra otro visor de Health Connect ves que el
# UUID no coincide, cambia esto a "little" y ya está: no hay que tocar nada
# más en el código.
UUID_BYTE_ORDER = "big"  # "big" o "little"


def blob_to_uuid(uuid_blob: bytes) -> str:
    if UUID_BYTE_ORDER == "little":
        return str(uuid.UUID(bytes_le=uuid_blob))
    return str(uuid.UUID(bytes=uuid_blob))


def ms_to_local_date(epoch_ms: int) -> date:
    return datetime.fromtimestamp(epoch_ms / 1000, tz=LOCAL_TZ).date()


def ms_to_iso_utc(epoch_ms: int) -> str:
    return datetime.fromtimestamp(epoch_ms / 1000, tz=ZoneInfo("UTC")).isoformat()


def local_day_window_ms(day: date) -> tuple[int, int]:
    """Devuelve (start_ms, end_ms) en epoch millis UTC para un día natural en LOCAL_TZ."""
    start_local = datetime(day.year, day.month, day.day, tzinfo=LOCAL_TZ)
    end_local = start_local + timedelta(days=1)
    return int(start_local.timestamp() * 1000), int(end_local.timestamp() * 1000)


def latest_day_for(conn: sqlite3.Connection, table: str, col: str) -> date | None:
    """Día natural (hora local) del registro más reciente de `table`, o None si está vacía."""
    cur = conn.cursor()
    cur.execute(f"SELECT MAX({col}) FROM {table}")
    row = cur.fetchone()
    if not row or row[0] is None:
        return None
    return ms_to_local_date(row[0])


def extract_heart_rate(conn, start_ms: int, end_ms: int) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT parent_key, beats_per_minute, epoch_millis
        FROM heart_rate_record_series_table
        WHERE epoch_millis >= ? AND epoch_millis < ?
        """,
        (start_ms, end_ms),
    )
    return [
        {
            "parent_key": parent_key,
            "bpm": bpm,
            "recorded_at": ms_to_iso_utc(epoch_millis),
        }
        for parent_key, bpm, epoch_millis in cur.fetchall()
    ]


def extract_sleep_stages(conn, start_ms: int, end_ms: int) -> list[dict]:
    cur = conn.cursor()
    # Una etapa "pertenece" al día si empieza dentro de la ventana.
    cur.execute(
        """
        SELECT parent_key, stage_type, stage_start_time, stage_end_time
        FROM sleep_stages_table
        WHERE stage_start_time >= ? AND stage_start_time < ?
        """,
        (start_ms, end_ms),
    )
    return [
        {
            "parent_key": parent_key,
            "stage_type": stage_type,
            "stage_start": ms_to_iso_utc(stage_start),
            "stage_end": ms_to_iso_utc(stage_end),
        }
        for parent_key, stage_type, stage_start, stage_end in cur.fetchall()
    ]


def extract_oxygen_saturation(conn, start_ms: int, end_ms: int) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT uuid, time, percentage
        FROM oxygen_saturation_record_table
        WHERE time >= ? AND time < ?
        """,
        (start_ms, end_ms),
    )
    return [
        {
            "uuid": blob_to_uuid(uuid_blob),
            "recorded_at": ms_to_iso_utc(time_ms),
            "percentage": percentage,
        }
        for uuid_blob, time_ms, percentage in cur.fetchall()
    ]


def extract_resting_heart_rate(conn, start_ms: int, end_ms: int) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT uuid, beats_per_minute, time
        FROM resting_heart_rate_record_table
        WHERE time >= ? AND time < ?
        """,
        (start_ms, end_ms),
    )
    return [
        {
            "uuid": blob_to_uuid(uuid_blob),
            "resting_bpm": beats_per_minute,
            "recorded_at": ms_to_iso_utc(time_ms),
        }
        for uuid_blob, beats_per_minute, time_ms in cur.fetchall()
    ]


def push(supabase: Client, table: str, rows: list[dict], on_conflict: str) -> bool:
    """Sube las filas en chunks. Devuelve False si algún chunk falla, pero
    no lanza excepción: un fallo en una tabla no debe tumbar la sync de las
    otras en un cron job desatendido."""
    if not rows:
        log.info("  %s: 0 filas, se omite.", table)
        return True

    ok = True
    for i in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[i : i + CHUNK_SIZE]
        try:
            supabase.table(table).upsert(chunk, on_conflict=on_conflict).execute()
        except Exception as exc:  # noqa: BLE001 - aislar el fallo de un chunk, no tumbar la sync
            ok = False
            log.error(
                "  %s: ERROR subiendo filas %d-%d (%s: %s)",
                table, i, i + len(chunk), exc.__class__.__name__, exc,
            )
    if ok:
        log.info("  %s: %d filas sincronizadas.", table, len(rows))
    else:
        log.error("  %s: sincronización PARCIAL, revisa los errores arriba.", table)
    return ok


# Cada flujo: nombre legible, tabla/columna origen para el día, función de
# extracción, tabla destino en Supabase y clave de conflicto para el upsert.
SOURCES = [
    {
        "name": "frecuencia cardíaca",
        "src_table": "heart_rate_record_series_table",
        "src_col": "epoch_millis",
        "extract": extract_heart_rate,
        "dest_table": "heart_rate_samples",
        "on_conflict": "parent_key,recorded_at",
    },
    {
        "name": "etapas de sueño",
        "src_table": "sleep_stages_table",
        "src_col": "stage_start_time",
        "extract": extract_sleep_stages,
        "dest_table": "sleep_stages",
        "on_conflict": "parent_key,stage_start",
    },
    {
        "name": "saturación de oxígeno",
        "src_table": "oxygen_saturation_record_table",
        "src_col": "time",
        "extract": extract_oxygen_saturation,
        "dest_table": "oxygen_saturation_samples",
        "on_conflict": "uuid",
    },
    {
        "name": "frecuencia cardíaca en reposo",
        "src_table": "resting_heart_rate_record_table",
        "src_col": "time",
        "extract": extract_resting_heart_rate,
        "dest_table": "resting_heart_rate_samples",
        "on_conflict": "uuid",
    },
]


def sync_source(conn, supabase, source: dict, today: date) -> tuple[bool, bool]:
    """Sincroniza el último día disponible de un flujo.

    Devuelve (push_ok, stale): `push_ok` False si el upsert falló; `stale` True
    si esa métrica lleva demasiados días sin datos nuevos.
    """
    name = source["name"]
    day = latest_day_for(conn, source["src_table"], source["src_col"])
    if day is None:
        log.warning("[%s] la tabla de origen está vacía, se omite.", name)
        return True, True

    age = (today - day).days
    stale = age >= STALE_AFTER_DAYS
    if stale:
        log.warning(
            "[%s] último dato el %s (%d días atrás). ¿Ha dejado de sincronizarse "
            "esta métrica en Health Connect?", name, day, age,
        )

    start_ms, end_ms = local_day_window_ms(day)
    log.info("[%s] sincronizando día %s (Europe/Warsaw)", name, day)
    rows = source["extract"](conn, start_ms, end_ms)
    push_ok = push(supabase, source["dest_table"], rows, on_conflict=source["on_conflict"])
    return push_ok, stale


def main():
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
        )

    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    supabase = create_client(url, key)

    today = datetime.now(tz=LOCAL_TZ).date()
    conn = sqlite3.connect(SQLITE_PATH)
    try:
        results = [sync_source(conn, supabase, src, today) for src in SOURCES]
    finally:
        conn.close()

    push_oks = [r[0] for r in results]
    stales = [r[1] for r in results]

    if all(stales):
        log.error("Ninguna tabla tiene datos recientes. ¿Export de Health Connect vacío o corrupto?")
        sys.exit(1)
    if not all(push_oks):
        log.error("Sync terminada con errores en al menos una tabla.")
        sys.exit(1)
    if any(stales):
        log.warning("Sync completada, pero hay métricas sin datos recientes (ver avisos arriba).")
    else:
        log.info("Sync completada sin errores.")


if __name__ == "__main__":
    main()