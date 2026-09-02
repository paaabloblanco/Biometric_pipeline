import json
import os
from datetime import date, datetime, time, timedelta
from typing import Any

from django.apps import apps
from django.utils import timezone

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
    """Registros del último día escrito. Atajo de `get_day_data()`.

    Se conserva el nombre porque lo usan el bot (`/hoy`) y el prompt de Gemini.
    """
    return get_day_data()


def get_day_data(day=None):
    """Todos los registros de un día, sin promediar. `day=None` = el último."""
    ensure_django_setup()
    HeartRateSamples, OxygenSaturationSamples, RestingHeartRateSamples, SleepStages = get_models()
    target_day = _parse_day(day) or get_latest_written_day()

    data = {
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
        # Deduplicado: el sync guarda a veces la misma sesión dos veces (ver
        # _dedup_sessions). Sin esto, /hoy del bot y el prompt de Gemini ven el
        # doble de fases de las que hubo.
        "sleep_stages": _dedup_rows(
            serialize_queryset(
                SleepStages.objects.filter(stage_start__date=target_day).order_by("stage_start")
            )
        ),
    }
    data["summary"] = build_day_summary(data)
    return data


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


# --- Sueño: sesiones, deduplicación e hipnograma ---------------------------

# stage_type de Health Connect -> nombre legible (constantes STAGE_TYPE_*).
SLEEP_STAGE_NAMES = {
    0: "desconocido",
    1: "despierto",
    2: "dormido",
    3: "fuera_de_cama",
    4: "ligero",
    5: "profundo",
    6: "rem",
    7: "despierto_en_cama",
}


def _huella_fase(fase):
    """Identidad de una fase: qué fue y entre qué instantes. El `parent_key`
    queda fuera a propósito, porque es justo lo que difiere entre duplicados."""
    return (fase["stage_type"], fase["stage_start"], fase["stage_end"])


def _dedup_rows(fases):
    """Descarta fases repetidas de una lista de dicts, conservando el orden."""
    vistas, salida = set(), []
    for f in fases:
        huella = _huella_fase(f)
        if huella not in vistas:
            vistas.add(huella)
            salida.append(f)
    return salida


def _dedup_sessions(fases):
    """Agrupa las fases en sesiones de sueño y descarta las sesiones repetidas.

    El sync externo guarda a veces la misma noche dos veces, con dos
    `parent_key` distintos. El `unique_together (parent_key, stage_start)` del
    modelo no lo impide precisamente porque el `parent_key` sí difiere. Sin
    deduplicar, las duraciones se suman dos veces y una noche de 8h 20m
    aparece como 16h 40m.

    El criterio de duplicado es el **solapamiento temporal**, no la igualdad
    exacta: no siempre son copias idénticas. La noche del 12-08 estaba
    guardada como dos sesiones que empiezan a la misma hora pero acaban a las
    07:24 y a las 06:12 —seguramente dos pasadas del sync, la segunda
    incompleta—. Comparando huellas exactas ambas sobrevivían y el día sumaba
    14h 28m. Como nadie duerme dos veces a la vez, de cada grupo de sesiones
    solapadas se conserva la que más minutos de sueño tiene.

    Se deduplica **al leer** y no borrando filas porque `sleep_stages` es
    `managed = False`: la escribe el sync externo, no Django, así que las filas
    borradas volverían en la siguiente sincronización.

    Devuelve una lista de sesiones ordenadas por inicio; cada sesión es su
    lista de fases, a su vez ordenada.
    """
    por_parent: dict[int, list[dict[str, Any]]] = {}
    for f in fases:
        por_parent.setdefault(f["parent_key"], []).append(f)

    sesiones = []
    for lista in por_parent.values():
        lista.sort(key=lambda f: f["stage_start"])
        sesiones.append(lista)
    sesiones.sort(key=lambda ses: ses[0]["stage_start"])

    # Barrido lineal: cada sesión se compara con la última conservada. Si se
    # solapan, se queda la de más sueño; si no, empieza una noche nueva.
    conservadas: list[list[dict[str, Any]]] = []
    for sesion in sesiones:
        if conservadas and sesion[0]["stage_start"] < _fin(conservadas[-1]):
            if _minutos_de_sueno(sesion) > _minutos_de_sueno(conservadas[-1]):
                conservadas[-1] = sesion
        else:
            conservadas.append(sesion)
    return conservadas


def _fin(fases):
    return max(f["stage_end"] for f in fases)


def _minutos(fase):
    return (fase["stage_end"] - fase["stage_start"]).total_seconds() / 60


def _minutos_de_sueno(fases):
    """Minutos dormidos de verdad: excluye las fases de vigilia."""
    return sum(_minutos(f) for f in fases if f["stage_type"] not in _SLEEP_AWAKE_STAGES)


def _dia_de_despertar(fases):
    """Día al que se atribuye una sesión: aquel en que termina.

    Una noche que empieza a las 23:24 y acaba a las 07:44 pertenece al día en
    que te despiertas, no repartida a medias entre dos días. Es el criterio de
    Health Connect, Fitbit y Garmin. Agrupar por `TruncDate(stage_start)`
    —lo que se hacía antes— partía cada noche que cruza medianoche en dos
    mitades y llenaba la serie de huecos y picos.
    """
    return timezone.localtime(max(f["stage_end"] for f in fases)).date()


def _inicio_del_dia(dia):
    """Medianoche local de `dia` como datetime consciente de la zona horaria.

    Comparar un `date` pelado contra un DateTimeField deja que Django construya
    un datetime naive y suelta un RuntimeWarning: la comparación se haría en
    una zona indeterminada y podría desplazar el corte varias horas.
    """
    return timezone.make_aware(datetime.combine(dia, time.min))


def _fases_en_ventana(day_from, day_to):
    """Fases cuya sesión puede terminar dentro del rango.

    La ventana se ensancha un día por cada lado: una sesión que termina el
    `day_from` empezó la tarde anterior, y sin ese margen se leería a medias.
    """
    *_, sleep_stages = get_models()
    return list(
        sleep_stages.objects.filter(
            stage_start__gte=_inicio_del_dia(day_from - timedelta(days=1)),
            stage_start__lt=_inicio_del_dia(day_to + timedelta(days=2)),
        )
        .order_by("stage_start")
        .values("parent_key", "stage_type", "stage_start", "stage_end")
    )


def _noches_por_dia(day_from, day_to):
    """La sesión principal de cada día: `{fecha: fases}`.

    "La noche" es la sesión más larga que termina ese día. Las siestas quedan
    fuera para que el KPI, el hipnograma y la serie de 30 días hablen todos
    del mismo número; mezclar una siesta de 47 min haría que la tarjeta dijera
    9h 07m mientras el hipnograma justo debajo dibuja 8h 20m.
    """
    noches: dict[date, list[dict[str, Any]]] = {}
    for fases in _dedup_sessions(_fases_en_ventana(day_from, day_to)):
        dia = _dia_de_despertar(fases)
        if not day_from <= dia <= day_to:
            continue
        if dia not in noches or _minutos_de_sueno(fases) > _minutos_de_sueno(noches[dia]):
            noches[dia] = fases
    return noches


def _sleep_series(day_from, day_to):
    """Minutos dormidos por noche, deduplicados y atribuidos al día del despertar."""
    return [
        {"date": dia.isoformat(), "minutes": round(_minutos_de_sueno(fases))}
        for dia, fases in sorted(_noches_por_dia(day_from, day_to).items())
        if _minutos_de_sueno(fases) > 0
    ]


def get_sleep_night(day=None):
    """Fases de la noche que termina en `day`, para el hipnograma de la web.

    "La noche" es la **sesión de sueño más larga** que termina ese día, no todo
    lo que se durmió: así una siesta de 47 min queda fuera y no se dibuja como
    si fuera parte de la noche.

    Devuelve ``{"date", "start", "end", "total_minutes", "segments", "totals"}``,
    con `start`/`end` de cada segmento en hora local y ya deduplicados.
    Si no hay sesión, `segments` viene vacío.
    """
    ensure_django_setup()
    dia = _parse_day(day) or get_latest_written_day()

    noche = _noches_por_dia(dia, dia).get(dia)
    if noche is None:
        return {
            "date": dia.isoformat(),
            "start": None,
            "end": None,
            "total_minutes": 0,
            "segments": [],
            "totals": [],
        }

    segmentos = [
        {
            "stage": SLEEP_STAGE_NAMES.get(f["stage_type"], "desconocido"),
            "start": timezone.localtime(f["stage_start"]).isoformat(),
            "end": timezone.localtime(f["stage_end"]).isoformat(),
            "minutes": round(_minutos(f)),
        }
        for f in noche
    ]

    totales: dict[str, int] = {}
    for seg in segmentos:
        totales[seg["stage"]] = totales.get(seg["stage"], 0) + seg["minutes"]

    # Los extremos se sacan de los datetime, no de comparar los ISO ya
    # formateados: la noche del cambio de hora mezcla offsets (+02:00 y
    # +01:00) y ahí el orden alfabético del texto deja de coincidir con el
    # orden real ("02:30+02:00" es *anterior* a "02:10+01:00").
    return {
        "date": dia.isoformat(),
        "start": timezone.localtime(min(f["stage_start"] for f in noche)).isoformat(),
        "end": timezone.localtime(_fin(noche)).isoformat(),
        "total_minutes": round(_minutos_de_sueno(noche)),
        "segments": segmentos,
        "totals": [
            {"stage": nombre, "minutes": minutos}
            for nombre, minutos in sorted(totales.items(), key=lambda kv: -kv[1])
        ],
    }


# --- Resumen del día (KPIs de la cabecera del dashboard) -------------------


def _media(valores, decimales=1):
    return round(sum(valores) / len(valores), decimales) if valores else None


def build_day_summary(data):
    """Métricas agregadas del día a partir de la respuesta cruda de `get_last_day_data`.

    Vive en la capa de servicio y no en el frontend a propósito: si la SPA
    calculase la media de SpO2 por su cuenta, la web y el bot podrían enseñar
    números distintos del mismo dato. Una sola fuente de verdad (CLAUDE.md).
    """
    bpms = [s["bpm"] for s in data["heart_rate_samples"]]
    rbpms = [s["resting_bpm"] for s in data["resting_heart_rate_samples"]]
    spo2 = [float(s["percentage"]) for s in data["oxygen_saturation_samples"]]

    dia = _parse_day(data["date"])
    serie = _sleep_series(dia, dia)  # minutos de la noche que termina ese día

    return {
        "heart_rate_avg": _media(bpms, 0),
        "heart_rate_min": min(bpms) if bpms else None,
        "heart_rate_max": max(bpms) if bpms else None,
        "resting_heart_rate": _media(rbpms, 0),
        "oxygen_saturation_avg": _media(spo2),
        "oxygen_saturation_min": min(spo2) if spo2 else None,
        "sleep_minutes": serie[0]["minutes"] if serie else None,
    }


# --- Detalle de un día (página /dia/:fecha de la web) ----------------------


def get_available_days():
    """Días con algún dato, ordenados de más antiguo a más reciente.

    Sirve para las flechas de día anterior/siguiente: saltar de día en día
    naturales llevaría a pantallas vacías, porque el sync tiene huecos de
    semanas. Se navega solo entre días que existen.

    Usa `TruncDate`, que convierte a la zona horaria de `TIME_ZONE` en la BD,
    para que el corte del día sea el mismo que el de los filtros `__date`.
    """
    ensure_django_setup()
    from django.db.models.functions import TruncDate

    heart_rate, oxygen, resting, sleep_stages = get_models()
    dias = set()
    for model, campo in (
        (heart_rate, "recorded_at"),
        (oxygen, "recorded_at"),
        (resting, "recorded_at"),
        (sleep_stages, "stage_start"),
    ):
        dias.update(
            model.objects.annotate(d=TruncDate(campo)).values_list("d", flat=True).distinct()
        )
    return sorted(d for d in dias if d is not None)


def _vecinos(dia, dias):
    """Día anterior y siguiente *con datos* respecto a `dia`."""
    anteriores = [d for d in dias if d < dia]
    siguientes = [d for d in dias if d > dia]
    return (
        anteriores[-1].isoformat() if anteriores else None,
        siguientes[0].isoformat() if siguientes else None,
    )


def _serie_intradia(muestras, campo):
    """Muestras crudas -> puntos `{t, v}` con la hora ya en local.

    Se devuelve solo instante y valor, no la fila entera: la gráfica no
    necesita `uuid` ni `parent_key`, y un día de frecuencia cardíaca son ~700
    filas que no tiene sentido mandar completas.
    """
    return [
        {
            "t": timezone.localtime(m["recorded_at"]).isoformat(),
            "v": float(m[campo]),
        }
        for m in muestras
    ]


def get_day_detail(day=None):
    """Todo lo que necesita la página de detalle de un día.

    Un único endpoint en vez de que el frontend encadene tres llamadas: el
    resumen, las series intradía y los días vecinos salen del mismo día y se
    piden juntos. El hipnograma va aparte (`get_sleep_night`) porque su unidad
    es la noche, no el día natural.
    """
    ensure_django_setup()
    datos = get_day_data(day)
    dia = _parse_day(datos["date"])
    anterior, siguiente = _vecinos(dia, get_available_days())

    return {
        "date": datos["date"],
        "prev_date": anterior,
        "next_date": siguiente,
        "summary": datos["summary"],
        "heart_rate": _serie_intradia(datos["heart_rate_samples"], "bpm"),
        "oxygen_saturation": _serie_intradia(datos["oxygen_saturation_samples"], "percentage"),
    }


def main():
    print(get_last_day_data_json())


if __name__ == "__main__":
    main()
