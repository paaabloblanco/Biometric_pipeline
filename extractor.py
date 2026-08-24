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

import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SQLITE_PATH = os.environ.get("HEALTH_CONNECT_DB", "health_connect_export.db")
LOCAL_TZ = ZoneInfo("Europe/Warsaw")
CHUNK_SIZE = 500

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


def get_last_available_day(conn: sqlite3.Connection) -> date:
    """El día natural (hora local) más reciente presente en cualquiera de las 3 tablas."""
    cur = conn.cursor()
    candidates = []
    for table, col in [
        ("heart_rate_record_series_table", "epoch_millis"),
        ("sleep_stages_table", "stage_end_time"),
        ("oxygen_saturation_record_table", "time"),
        ("resting_heart_rate_record_table", "time"),
    ]:
        cur.execute(f"SELECT MAX({col}) FROM {table}")
        row = cur.fetchone()
        if row and row[0] is not None:
            candidates.append(row[0])
    if not candidates:
        raise RuntimeError("No hay datos en ninguna de las 3 tablas.")
    return ms_to_local_date(max(candidates))


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
    otras dos en un cron job desatendido."""
    if not rows:
        print(f"  {table}: 0 filas, se omite.")
        return True

    ok = True
    for i in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[i : i + CHUNK_SIZE]
        try:
            supabase.table(table).upsert(chunk, on_conflict=on_conflict).execute()
        except Exception as exc:
            ok = False
            print(
                f"  {table}: ERROR subiendo filas {i}-{i+len(chunk)} "
                f"({exc.__class__.__name__}: {exc})",
                file=sys.stderr,
            )
    if ok:
        print(f"  {table}: {len(rows)} filas sincronizadas.")
    else:
        print(f"  {table}: sincronización PARCIAL, revisa los errores arriba.", file=sys.stderr)
    return ok


def main():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    supabase = create_client(url, key)

    conn = sqlite3.connect(SQLITE_PATH)
    try:
        target_day = get_last_available_day(conn)
        start_ms, end_ms = local_day_window_ms(target_day)
        print(f"Sincronizando día {target_day} (Europe/Warsaw) -> {start_ms}..{end_ms} ms UTC")

        hr_rows = extract_heart_rate(conn, start_ms, end_ms)
        sleep_rows = extract_sleep_stages(conn, start_ms, end_ms)
        spo2_rows = extract_oxygen_saturation(conn, start_ms, end_ms)
        resting_hr_rows = extract_resting_heart_rate(conn, start_ms, end_ms)

        results = [
            push(supabase, "heart_rate_samples", hr_rows, on_conflict="parent_key,recorded_at"),
            push(supabase, "sleep_stages", sleep_rows, on_conflict="parent_key,stage_start"),
            push(supabase, "oxygen_saturation_samples", spo2_rows, on_conflict="uuid"),
            push(supabase, "resting_heart_rate_samples", resting_hr_rows, on_conflict="uuid"),
        ]
    finally:
        conn.close()

    if not all(results):
        print("Sync terminada con errores en al menos una tabla.", file=sys.stderr)
        sys.exit(1)
    print("Sync completada sin errores.")


if __name__ == "__main__":
    main()