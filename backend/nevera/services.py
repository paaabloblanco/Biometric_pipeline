import os
import unicodedata
from datetime import timedelta

from django.apps import apps
from django.utils import timezone

from nevera.units import to_base

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")


def ensure_django_setup():
    if not apps.ready:
        import django

        django.setup()


def normalizar_nombre(nombre: str) -> str:
    """minúsculas, sin acentos, espacios sueltos colapsados."""
    sin_acentos = unicodedata.normalize("NFKD", nombre.strip().lower())
    sin_acentos = "".join(c for c in sin_acentos if not unicodedata.combining(c))
    return " ".join(sin_acentos.split())


def add_items(items: list[dict], origen: str = "manual"):
    """Da de alta o suma cantidad a items existentes (mismo nombre normalizado + unidad).

    Cada item: {"nombre": str, "cantidad": float, "unidad": str,
                "categoria": str | None, "fecha_caducidad": date | None,
                "es_basico": bool}
    Devuelve la lista de NeveraItem resultantes.
    """
    ensure_django_setup()
    from nevera.models import NeveraItem

    resultado = []
    for item in items:
        nombre = normalizar_nombre(item["nombre"])
        cantidad, unidad = to_base(item["cantidad"], item["unidad"])
        existente = NeveraItem.objects.filter(nombre=nombre, unidad=unidad).first()
        if existente:
            existente.cantidad += cantidad
            if item.get("fecha_caducidad"):
                existente.fecha_caducidad = item["fecha_caducidad"]
            if item.get("categoria"):
                existente.categoria = item["categoria"]
            # Solo promociona a básico, nunca degrada: si ya lo marcaste tú a
            # mano, una compra posterior mal clasificada no debe deshacerlo.
            if item.get("es_basico"):
                existente.es_basico = True
            existente.save()
            resultado.append(existente)
        else:
            nuevo = NeveraItem.objects.create(
                nombre=nombre,
                cantidad=cantidad,
                unidad=unidad,
                categoria=item.get("categoria"),
                fecha_caducidad=item.get("fecha_caducidad"),
                origen=origen,
                es_basico=bool(item.get("es_basico", False)),
            )
            resultado.append(nuevo)
    return resultado


def get_items_by_expiry(dias_limite: int | None = None):
    """Devuelve items ordenados por urgencia de consumo.

    Orden: primero los perecederos con fecha (los que antes caducan), luego
    los perecederos sin fecha anotada, y al final los básicos de despensa
    (ver decisión D del SDD y `NeveraItem.es_basico`). Los básicos siguen
    apareciendo —hacen falta para cocinar— pero nunca encabezan la lista.

    Si `dias_limite` se indica, solo incluye perecederos que caduquen dentro
    de ese número de días: los básicos quedan fuera por definición, igual que
    los que no tienen fecha.
    """
    ensure_django_setup()
    from nevera.models import NeveraItem

    qs = NeveraItem.objects.all()
    if dias_limite is not None:
        limite = timezone.localtime().date() + timedelta(days=dias_limite)
        qs = qs.filter(es_basico=False, fecha_caducidad__isnull=False, fecha_caducidad__lte=limite)
        return list(qs.order_by("fecha_caducidad"))

    perecederos = qs.filter(es_basico=False)
    con_fecha = list(perecederos.filter(fecha_caducidad__isnull=False).order_by("fecha_caducidad"))
    sin_fecha = list(perecederos.filter(fecha_caducidad__isnull=True).order_by("nombre"))
    basicos = list(qs.filter(es_basico=True).order_by("nombre"))
    return con_fecha + sin_fecha + basicos


def consume_items(consumos: list[dict]):
    """Resta cantidades del inventario.

    Cada consumo: {"nombre": str, "unidad": str, "cantidad": float}.
    Si la cantidad restante es <= 0, el item se elimina.

    Los básicos de despensa (`es_basico=True`) se gestionan por presencia, no
    por cantidad: se ignoran aquí y se devuelven aparte en "basicos". Sin esto,
    una receta con "sal: 1 ud" borraría la sal del inventario.

    Devuelve {"aplicados", "basicos", "no_encontrados"}.
    """
    ensure_django_setup()
    from nevera.models import NeveraItem

    aplicados = []
    basicos = []
    no_encontrados = []
    for consumo in consumos:
        nombre = normalizar_nombre(consumo["nombre"])
        cantidad, unidad = to_base(consumo["cantidad"], consumo["unidad"])
        item = NeveraItem.objects.filter(nombre=nombre, unidad=unidad).first()
        if item is None:
            # Para un básico la unidad de la receta casi nunca coincide con la
            # guardada: la sal está como "1 ud" y Gemini pide "3 g". Como no se
            # va a descontar nada, la unidad da igual — basta con reconocerlo
            # por nombre y evitar un "no encontrado" que asustaría sin motivo.
            item = NeveraItem.objects.filter(nombre=nombre, es_basico=True).first()
            if item is None:
                no_encontrados.append(consumo)
                continue

        if item.es_basico:
            basicos.append({"nombre": nombre, "unidad": item.unidad})
            continue

        item.cantidad -= cantidad
        if item.cantidad <= 0:
            item.delete()
            aplicados.append({"nombre": nombre, "unidad": unidad, "restante": 0})
        else:
            item.save()
            aplicados.append({"nombre": nombre, "unidad": unidad, "restante": float(item.cantidad)})

    return {"aplicados": aplicados, "basicos": basicos, "no_encontrados": no_encontrados}


def list_all():
    ensure_django_setup()
    from nevera.models import NeveraItem

    return list(NeveraItem.objects.all().order_by("categoria", "nombre"))


def delete_item(item_id: int) -> bool:
    """Borra un item por id. Devuelve False si no existía."""
    ensure_django_setup()
    from nevera.models import NeveraItem

    borrados, _ = NeveraItem.objects.filter(id=item_id).delete()
    return borrados > 0


def edit_item(item_id: int, **cambios):
    """Edita campos de un item existente (nombre, cantidad, unidad, categoria,
    fecha_caducidad, es_basico). `cantidad`/`unidad` se normalizan igual que en add_items
    si se pasan juntas; si solo se pasa `cantidad` se asume que ya está en la
    unidad base actual del item. Devuelve el item actualizado o None si no existe.
    """
    ensure_django_setup()
    from nevera.models import NeveraItem

    item = NeveraItem.objects.filter(id=item_id).first()
    if not item:
        return None

    if "nombre" in cambios:
        item.nombre = normalizar_nombre(cambios["nombre"])
    if "cantidad" in cambios and "unidad" in cambios:
        item.cantidad, item.unidad = to_base(cambios["cantidad"], cambios["unidad"])
    elif "cantidad" in cambios:
        item.cantidad = cambios["cantidad"]
    if "categoria" in cambios:
        item.categoria = cambios["categoria"]
    if "fecha_caducidad" in cambios:
        item.fecha_caducidad = cambios["fecha_caducidad"]
    if "es_basico" in cambios:
        item.es_basico = bool(cambios["es_basico"])

    item.save()
    return item
