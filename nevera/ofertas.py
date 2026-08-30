"""Cruza el texto de una gazetka/oferta (transcrito manualmente, ver decisión
E del SDD: el scraping directo de biedronka.pl y de agregadores como Blix no
es viable sin un navegador headless) con el inventario actual, para decidir
qué ofertas merece la pena aprovechar."""

import json
import re

from health_ai.pruebas import send_prompt_to_gemini
from nevera.suggestions import format_inventario

PROMPT_TEMPLATE = (
    "Eres un asesor de compra para un deportista que sigue una dieta de "
    "comida real (whole foods) y antiinflamatoria. Te paso el texto de unas "
    "ofertas de supermercado (transcritas de una gazetka) y el inventario "
    "actual de su nevera.\n\n"
    "OFERTAS:\n{texto_ofertas}\n\n"
    "INVENTARIO ACTUAL:\n{inventario}\n\n"
    "Identifica qué ofertas merece la pena aprovechar, priorizando en este "
    "orden:\n"
    "1. Productos que ya suele tener en la nevera pero de los que quedan "
    "pocos o ninguno.\n"
    "2. Ofertas genuinas (descuento relevante) de productos básicos y "
    "compatibles con comida real, aunque no estén ahora en la nevera.\n"
    "Ignora ofertas de ultraprocesados o productos irrelevantes para esa "
    "dieta.\n\n"
    "Responde solo con JSON estricto, sin explicaciones ni bloques de "
    "código markdown, con este formato exacto:\n"
    '[{{"nombre": "string tal cual aparece en la oferta", "motivo": '
    '"string breve, 1 frase", "precio": "string tal cual aparece o null"}}]\n\n'
    "Si ninguna oferta merece la pena, responde con una lista vacía: []"
)


def analizar_ofertas(texto_ofertas: str, items) -> list[dict]:
    """items: iterable de NeveraItem del inventario actual (puede estar vacío).

    Devuelve una lista (puede ser vacía) de recomendaciones:
    {"nombre", "motivo", "precio"}.
    """
    items = list(items)
    inventario_texto = format_inventario(items) if items else "(La nevera está vacía.)"

    prompt = PROMPT_TEMPLATE.format(texto_ofertas=texto_ofertas, inventario=inventario_texto)
    respuesta = send_prompt_to_gemini(prompt)

    crudo = _extraer_json(respuesta)
    try:
        recomendaciones = json.loads(crudo)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini no devolvió JSON válido: {exc}") from exc

    if not isinstance(recomendaciones, list):
        # ValueError (no TypeError): esto es un dato externo mal formado, no un
        # argumento de Python con el tipo equivocado.
        raise ValueError("Gemini no devolvió una lista de recomendaciones.")  # noqa: TRY004

    for r in recomendaciones:
        if "nombre" not in r:
            raise ValueError(f"Recomendación incompleta devuelta por Gemini: {r!r}")

    return recomendaciones


def _extraer_json(texto: str) -> str:
    texto = texto.strip()
    match = re.search(r"\[.*\]", texto, re.DOTALL)
    return match.group(0) if match else texto
