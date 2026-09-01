"""Migración de DATOS (no de esquema): marca como básicos de despensa los
items que ya estaban en la nevera antes de existir el campo `es_basico`.

Va en una migración y no en el admin ni en el shell porque el cambio de datos
es *consecuencia* del cambio de esquema anterior (0002): queda versionado en
git, se ejecuta solo en cualquier clon nuevo del repo y es reproducible. El
admin es para correcciones puntuales del día a día; el shell, para explorar.

Los nombres van normalizados (minúsculas y sin acentos), que es como los deja
`nevera.services.normalizar_nombre` al guardar.
"""

from django.db import migrations

# Condimentos, especias, aceites, vinagres y salsas de despensa: duran meses,
# se usan en cantidades que nadie pesa y no deben encabezar el ranking de
# caducidad ni descontarse al hacer una receta.
NOMBRES_BASICOS = [
    "sal",
    "ajo en polvo",
    "pimienta negra",
    "curcuma",
    "pimenton dulce",
    "albahaca",
    "romero",
    "aceite de canola",
    "aceite de oliva virgen extra",
    "vinagre de manzana",
    "salsa de soja",
    "miel",
    "mayonesa",
    "pesto",
    "limon concentrado",
]


def marcar_basicos(apps, schema_editor):
    # En migraciones se usa el modelo histórico (apps.get_model), no el import
    # directo: así la migración sigue funcionando aunque el modelo cambie luego.
    NeveraItem = apps.get_model("nevera", "NeveraItem")
    NeveraItem.objects.filter(nombre__in=NOMBRES_BASICOS).update(es_basico=True)


def desmarcar_basicos(apps, schema_editor):
    NeveraItem = apps.get_model("nevera", "NeveraItem")
    NeveraItem.objects.filter(nombre__in=NOMBRES_BASICOS).update(es_basico=False)


class Migration(migrations.Migration):
    dependencies = [
        ("nevera", "0002_neveraitem_es_basico"),
    ]

    # La función inversa permite `migrate nevera 0002` sin dejar datos a medias.
    operations = [
        migrations.RunPython(marcar_basicos, desmarcar_basicos),
    ]
