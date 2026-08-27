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
            OxygenSaturationSamples.objects.filter(recorded_at__date=target_day).order_by("recorded_at")
        ),
        "resting_heart_rate_samples": serialize_queryset(
            RestingHeartRateSamples.objects.filter(recorded_at__date=target_day).order_by("recorded_at")
        ),
        "sleep_stages": serialize_queryset(
            SleepStages.objects.filter(stage_start__date=target_day).order_by("stage_start")
        ),
    }


def get_last_day_data_json():
    """Devuelve la salida JSON del último día guardado."""
    data = get_last_day_data()
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def main():
    print(get_last_day_data_json())


if __name__ == "__main__":
    main()
