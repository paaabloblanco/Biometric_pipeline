"""Normalización de unidades a una unidad base por magnitud, para que
'leche 1L' y 'leche 500ml' sean el mismo item en vez de fragmentarse."""

from decimal import Decimal

# alias de unidad (en minúsculas) -> (magnitud, factor a la unidad base de esa magnitud)
UNIT_CONVERSIONS = {
    # masa -> gramos
    "g": ("masa", 1),
    "gr": ("masa", 1),
    "gramo": ("masa", 1),
    "gramos": ("masa", 1),
    "kg": ("masa", 1000),
    "kilo": ("masa", 1000),
    "kilos": ("masa", 1000),
    # volumen -> mililitros
    "ml": ("volumen", 1),
    "mililitro": ("volumen", 1),
    "mililitros": ("volumen", 1),
    "l": ("volumen", 1000),
    "litro": ("volumen", 1000),
    "litros": ("volumen", 1000),
    # cuenta -> unidades
    "ud": ("unidad", 1),
    "uds": ("unidad", 1),
    "unidad": ("unidad", 1),
    "unidades": ("unidad", 1),
}

BASE_UNIT = {"masa": "g", "volumen": "ml", "unidad": "ud"}


def to_base(cantidad, unidad: str) -> tuple[Decimal, str]:
    """Convierte (cantidad, unidad) a (cantidad_en_unidad_base, unidad_base).

    Devuelve la cantidad como Decimal (mismo tipo que el campo del modelo,
    evita errores de aritmética mixta float/Decimal).

    Lanza ValueError si la unidad no se reconoce (mejor fallar alto y que
    /añadir pida aclaración, que guardar una unidad inconsistente).
    """
    clave = unidad.strip().lower()
    if clave not in UNIT_CONVERSIONS:
        raise ValueError(f"Unidad no reconocida: '{unidad}'")
    magnitud, factor = UNIT_CONVERSIONS[clave]
    return Decimal(str(cantidad)) * factor, BASE_UNIT[magnitud]


def format_cantidad(cantidad_base, unidad_base: str) -> str:
    """Formato legible para mostrar en el bot, deshaciendo la conversión si conviene."""
    cantidad_base = Decimal(str(cantidad_base))
    if unidad_base == "g" and cantidad_base >= 1000:
        return f"{_sin_ceros(cantidad_base / 1000)} kg"
    if unidad_base == "ml" and cantidad_base >= 1000:
        return f"{_sin_ceros(cantidad_base / 1000)} L"
    return f"{_sin_ceros(cantidad_base)} {unidad_base}"


def _sin_ceros(valor: Decimal) -> str:
    texto = f"{valor:.2f}".rstrip("0").rstrip(".")
    return texto if texto else "0"
