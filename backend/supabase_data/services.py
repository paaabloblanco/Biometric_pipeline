import json
import os
from datetime import date, datetime, timedelta

from django.apps import apps

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")


def get_models():
    if not apps.ready:
        import django

        django.setup()

    from supabase_data.models import (
        HeartRateSamples,
        OxygenSaturationSamples,
        RestingHeartRateSamples,
        SleepStages,
    )

    return HeartRateSamples, OxygenSaturationSamples, RestingHeartRateSamples, SleepStages


def ensure_django_setup():
    get_models()


def serialize_queryset(queryset):
    """Convierte un queryset a una lista de diccionarios sin ninguna agregación."""
    return list(queryset.values())


def get_latest_written_day():
    """Devuelve el último día que tiene registros en cualquiera de las tablas relevantes."""
    ensure_django_setup()
    HeartRateSamples, OxygenSaturationSamples, RestingHeartRateSamples, SleepStages = get_models()

    dates = []
    for model, field_name in [
        (HeartRateSamples, "recorded_at"),
        (OxygenSaturationSamples, "recorded_at"),
        (RestingHeartRateSamples, "recorded_at"),
        (SleepStages, "stage_start"),
    ]:
        latest_value = (
            model.objects.order_by(f"-{field_name}").values_list(field_name, flat=True).first()
        )
        if latest_value is not None:
            if isinstance(latest_value, datetime):
                dates.append(latest_value.date())
            else:
                dates.append(latest_value)

    if not dates:
        raise ValueError("No hay datos guardados en ninguna tabla.")

    return max(dates)


def get_last_day_data():
    """Devuelve todos los registros del último día escrito, sin hacer ningún promedio ni resumen."""
    ensure_django_setup()
    HeartRateSamples, OxygenSaturationSamples, RestingHeartRateSamples, SleepStages = get_models()
    target_day = get_latest_written_day()

    return {
        "date": target_day.isoformat(),
        "heart_rate_samples": serialize_queryset(
            HeartRateSamples.objects.filter(recorded_at__date=target_day).order_by("recorded_at")
        ),
        "oxygen_saturation_samples": serialize_queryset(
            OxygenSaturationSamples.objects.filter(recorded_at__date=target_day).order_by(
                "recorded_at"
            )
        ),
        "resting_heart_rate_samples": serialize_queryset(
            RestingHeartRateSamples.objects.filter(recorded_at__date=target_day).order_by(
                "recorded_at"
            )
        ),
        "sleep_stages": serialize_queryset(
            SleepStages.objects.filter(stage_start__date=target_day).order_by("stage_start")
        ),
    }


def get_last_day_data_json():
    """Devuelve la salida JSON del último día guardado."""
    data = get_last_day_data()
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def get_recent_analyses(limit=7):
    """Devuelve los últimos `limit` análisis guardados, más reciente primero."""
    ensure_django_setup()
    from supabase_data.models import AiAnalysisLog

    return list(
        AiAnalysisLog.objects.order_by("-analysis_date")[:limit].values(
            "analysis_date", "user_instruction", "analysis_text"
        )
    )


def save_analysis(analysis_date, user_instruction, analysis_text):
    """Guarda (o sobrescribe si ya existe ese día) el análisis de Gemini."""
    ensure_django_setup()
    from supabase_data.models import AiAnalysisLog

    AiAnalysisLog.objects.update_or_create(
        analysis_date=analysis_date,
        defaults={
            "user_instruction": user_instruction,
            "analysis_text": analysis_text,
        },
    )


# --- Series agregadas por día (gráficas de la interfaz web, SDD-web §4) ---

# Métricas que expone GET /api/health/series.
SERIES_METRICS = ("heart_rate", "resting_heart_rate", "oxygen_saturation", "sleep")

# stage_type de Health Connect que NO cuentan como sueño (vigilia / fuera de cama):
# AWAKE=1, OUT_OF_BED=3, AWAKE_IN_BED=7. El resto son fases de sueño.
_SLEEP_AWAKE_STAGES = (1, 3, 7)


def _parse_day(value):
    """Acepta None, un date o una cadena ISO 'YYYY-MM-DD'."""
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _to_float(value):
    return None if value is None else float(value)


def get_series(metric, date_from=None, date_to=None):
    """Agrega muestras por día para las gráficas de la web (SDD-web §4).

    `metric`: una de `SERIES_METRICS`.
    `date_from` / `date_to`: date o cadena ISO 'YYYY-MM-DD', ambos inclusive.
    Si no se indican se usan los últimos 30 días hasta el último día con datos.

    Para las métricas de muestras (heart_rate, resting_heart_rate,
    oxygen_saturation) cada punto es
    ``{"date", "min", "max", "avg", "count"}``.
    Para "sleep" cada punto es ``{"date", "minutes"}`` (suma de las fases de
    sueño del día, excluyendo las de vigilia).

    Lanza `ValueError` si la métrica es desconocida o el rango es inválido.
    """
    ensure_django_setup()
    if metric not in SERIES_METRICS:
        raise ValueError(f"Métrica desconocida: {metric!r}. Válidas: {', '.join(SERIES_METRICS)}.")

    day_from = _parse_day(date_from)
    day_to = _parse_day(date_to)
    if day_to is None:
        day_to = get_latest_written_day()
    if day_from is None:
        day_from = day_to - timedelta(days=29)
    if day_from > day_to:
        raise ValueError("El parámetro 'from' es posterior a 'to'.")

    if metric == "sleep":
        return _sleep_series(day_from, day_to)
    return _sample_series(metric, day_from, day_to)


def _sample_series(metric, day_from, day_to):
    from django.db.models import Avg, Count, Max, Min
    from django.db.models.functions import TruncDate

    heart_rate, oxygen, resting, _ = get_models()
    model, field = {
        "heart_rate": (heart_rate, "bpm"),
        "resting_heart_rate": (resting, "resting_bpm"),
        "oxygen_saturation": (oxygen, "percentage"),
    }[metric]

    rows = (
        model.objects.filter(recorded_at__date__gte=day_from, recorded_at__date__lte=day_to)
        .annotate(day=TruncDate("recorded_at"))
        .values("day")
        .annotate(min=Min(field), max=Max(field), avg=Avg(field), count=Count("id"))
        .order_by("day")
    )
    return [
        {
            "date": r["day"].isoformat(),
            "min": _to_float(r["min"]),
            "max": _to_float(r["max"]),
            "avg": round(float(r["avg"]), 1) if r["avg"] is not None else None,
            "count": r["count"],
        }
        for r in rows
    ]


def _sleep_series(day_from, day_to):
    from django.db.models import DurationField, ExpressionWrapper, F, Sum
    from django.db.models.functions import TruncDate

    *_, sleep_stages = get_models()
    duracion = ExpressionWrapper(F("stage_end") - F("stage_start"), output_field=DurationField())
    rows = (
        sleep_stages.objects.filter(stage_start__date__gte=day_from, stage_start__date__lte=day_to)
        .exclude(stage_type__in=_SLEEP_AWAKE_STAGES)
        .annotate(day=TruncDate("stage_start"))
        .values("day")
        .annotate(total=Sum(duracion))
        .order_by("day")
    )
    return [
        {"date": r["day"].isoformat(), "minutes": round(r["total"].total_seconds() / 60)}
        for r in rows
        if r["total"] is not None
    ]


def main():
    print(get_last_day_data_json())


if __name__ == "__main__":
    main()
