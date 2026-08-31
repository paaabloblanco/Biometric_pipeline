"""Modelos de solo lectura sobre tablas que crea y mantiene el sync externo
(`extractor.py` / la herramienta de Health Connect), no Django. Todos con
`managed = False`: Django lee y escribe filas pero nunca toca el esquema.
No renombrar `db_table` ni los nombres de campo."""

from django.db import models


class HeartRateSamples(models.Model):
    id = models.BigAutoField(primary_key=True)
    parent_key = models.BigIntegerField()
    bpm = models.SmallIntegerField()
    recorded_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "heart_rate_samples"
        unique_together = (("parent_key", "recorded_at"),)


class OxygenSaturationSamples(models.Model):
    id = models.BigAutoField(primary_key=True)
    uuid = models.TextField(unique=True)
    recorded_at = models.DateTimeField()
    percentage = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        managed = False
        db_table = "oxygen_saturation_samples"


class RestingHeartRateSamples(models.Model):
    id = models.BigAutoField(primary_key=True)
    uuid = models.TextField(unique=True)
    resting_bpm = models.SmallIntegerField()
    recorded_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "resting_heart_rate_samples"


class SleepStages(models.Model):
    id = models.BigAutoField(primary_key=True)
    parent_key = models.BigIntegerField()
    stage_type = models.SmallIntegerField()
    stage_start = models.DateTimeField()
    stage_end = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "sleep_stages"
        unique_together = (("parent_key", "stage_start"),)


class AiAnalysisLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    analysis_date = models.DateField(unique=True)
    user_instruction = models.TextField(null=True, blank=True)
    analysis_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "ai_analysis_log"
