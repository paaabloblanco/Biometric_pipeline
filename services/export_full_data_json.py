import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django

django.setup()

from supabase_data.models import (
    HeartRateSamples,
    OxygenSaturationSamples,
    RestingHeartRateSamples,
    SleepStages,
)


def serialize_queryset(queryset):
    """Devuelve una lista de diccionarios con los registros tal cual están guardados."""
    return list(queryset.values())


def get_full_saved_data():
    """Recoge todos los datos de cada tabla sin aplicar ninguna media, filtrado ni análisis."""
    return {
        "heart_rate_samples": serialize_queryset(HeartRateSamples.objects.all()),
        "oxygen_saturation_samples": serialize_queryset(OxygenSaturationSamples.objects.all()),
        "resting_heart_rate_samples": serialize_queryset(RestingHeartRateSamples.objects.all()),
        "sleep_stages": serialize_queryset(SleepStages.objects.all()),
    }


def export_full_saved_data_as_json():
    """Devuelve un string JSON con todos los datos guardados."""
    data = get_full_saved_data()
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def main():
    print(export_full_saved_data_as_json())


if __name__ == "__main__":
    main()
