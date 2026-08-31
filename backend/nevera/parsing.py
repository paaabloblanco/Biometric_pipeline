"""Estructura texto libre (compra transcrita por una IA externa) en items de
nevera, usando Gemini. Reutiliza el cliente ya configurado en health_ai."""

import json
import re
from datetime import date

from health_ai.pruebas import send_prompt_to_gemini

PROMPT_TEMPLATE = (
    "Convierte esta lista de la compra en JSON estricto, sin explicaciones y "
    "sin bloques de código markdown.\n\n"
    "Formato exacto: una lista de objetos con las claves:\n"
    '- "nombre": string\n'
    '- "cantidad": número\n'
    '- "unidad": uno de "g", "kg", "ml", "l", "ud"\n'
    '- "categoria": uno de "proteina", "lacteo", "verdura", "fruta", "cereal", "otros"\n'
    '- "fecha_caducidad": string en formato YYYY-MM-DD, o null si no se menciona\n\n'
    "Si un producto no indica cantidad, asume 1 ud. Agrupa duplicados evidentes "
    "del mismo texto en un único objeto sumando cantidades.\n\n"
    "Texto de la compra:\n"
    "{texto}\n\n"
    "Responde solo con el JSON, nada más."
)


def parse_compra_text(texto: str) -> list[dict]:
    """Llama a Gemini para estructurar `texto` en una lista de items normalizados.

    Cada item devuelto: {"nombre": str, "cantidad": float, "unidad": str,
    "categoria": str | None, "fecha_caducidad": date | None}.

    Lanza ValueError si Gemini no devuelve JSON válido o no es una lista.
    """
    prompt = PROMPT_TEMPLATE.format(texto=texto)
    respuesta = send_prompt_to_gemini(prompt)

    crudo = _extraer_json(respuesta)
    try:
        items = json.loads(crudo)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini no devolvió JSON válido: {exc}") from exc

    if not isinstance(items, list):
        # ValueError (no TypeError): esto es un dato externo mal formado, no un
        # argumento de Python con el tipo equivocado.
        raise ValueError("Gemini no devolvió una lista de items.")  # noqa: TRY004

    return [_normalizar_item(item) for item in items]


def _extraer_json(texto: str) -> str:
    texto = texto.strip()
    match = re.search(r"\[.*\]", texto, re.DOTALL)
    return match.group(0) if match else texto


def _normalizar_item(item: dict) -> dict:
    if "nombre" not in item or "unidad" not in item:
        raise ValueError(f"Item incompleto devuelto por Gemini: {item!r}")

    fecha_raw = item.get("fecha_caducidad")
    fecha = None
    if fecha_raw:
        try:
            fecha = date.fromisoformat(fecha_raw)
        except ValueError:
            fecha = None

    return {
        "nombre": item["nombre"],
        "cantidad": item.get("cantidad", 1),
        "unidad": item["unidad"],
        "categoria": item.get("categoria"),
        "fecha_caducidad": fecha,
    }
