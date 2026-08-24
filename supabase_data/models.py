

# Create your models here.
# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class HeartRateSamples(models.Model):
    id = models.BigAutoField(primary_key=True)
    parent_key = models.BigIntegerField()
    bpm = models.SmallIntegerField()
    recorded_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'heart_rate_samples'
        unique_together = (('parent_key', 'recorded_at'),)


class OxygenSaturationSamples(models.Model):
    id = models.BigAutoField(primary_key=True)
    uuid = models.TextField(unique=True)
    recorded_at = models.DateTimeField()
    percentage = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        managed = False
        db_table = 'oxygen_saturation_samples'


class RestingHeartRateSamples(models.Model):
    id = models.BigAutoField(primary_key=True)
    uuid = models.TextField(unique=True)
    resting_bpm = models.SmallIntegerField()
    recorded_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'resting_heart_rate_samples'


class SleepStages(models.Model):
    id = models.BigAutoField(primary_key=True)
    parent_key = models.BigIntegerField()
    stage_type = models.SmallIntegerField()
    stage_start = models.DateTimeField()
    stage_end = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'sleep_stages'
        unique_together = (('parent_key', 'stage_start'),)