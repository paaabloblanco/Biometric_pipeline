"""Sugerencia de recetas con Gemini, cruzando el inventario (priorizado por
caducidad) con el último análisis de recuperación guardado."""

import json
import re

from health_ai.pruebas import send_prompt_to_gemini
from nevera.units import format_cantidad

# Equipamiento de cocina disponible. Va en el prompt porque sin esto Gemini
# propone gratinados, asados o cremas batidas que no se pueden ejecutar.
EQUIPAMIENTO = "microondas, sartén y olla"

PROMPT_TEMPLATE = (
    "Eres un nutricionista deportivo especializado en nutrición evolutiva, "
    "comida real (whole foods) y dietas antiinflamatorias. Tu cliente es un "
    "jugador profesional de fútbol sala. Este es el inventario actual, en dos "
    "bloques: perecederos (ordenados priorizando lo que caduca antes) y "
    "despensa (usa los nombres EXACTAMENTE como aparecen, no los traduzcas ni "
    "los reformules):\n\n"
    "{inventario}\n\n"
    "Este es el último análisis de recuperación guardado (fecha: "
    "{fecha_analisis}; puede no ser de hoy):\n"
    "{analisis}\n\n"
    "RESTRICCIONES OBLIGATORIAS:\n\n"
    "1. RACIONES: cada receta es para UNA sola persona y UNA sola comida. Las "
    "cantidades del inventario son el STOCK TOTAL disponible, NO la cantidad "
    "que hay que usar. No vacíes el stock en un plato: un paquete de 300 g de "
    "pasta son 3 raciones, no una. Usa raciones realistas de una comida "
    "(orientación: 80-120 g de pasta o arroz en seco, 150-200 g de proteína, "
    "1 aguacate, 1-2 huevos por persona en un plato de acompañamiento, 50-80 g "
    "de cebolla, 1-2 piezas de fruta). Nunca pidas más cantidad de la que hay "
    "en el inventario.\n\n"
    "2. EQUIPAMIENTO: solo dispone de " + EQUIPAMIENTO + ". NO tiene horno, "
    "grill, batidora, robot de cocina ni freidora de aire. Toda receta debe "
    "poder hacerse únicamente con eso: nada de gratinar, hornear, asar al "
    "horno, triturar ni batir. Una tortilla o frittata debe hacerse a la "
    "sartén, cuajada por ambos lados.\n\n"
    "3. UNIDADES: expresa cada ingrediente en la MISMA unidad con la que "
    "aparece en el inventario. Si algo figura en 'ud', pídelo en 'ud'. Y "
    "cuando la unidad sea 'ud' y el producto no se fraccione de forma natural "
    "(huevos, latas, lonchas, piezas de fruta), usa números ENTEROS: pide "
    "1 loncha de queso, nunca 0,25.\n\n"
    "Propón entre 1 y 3 recetas que respeten estrictamente la filosofía de "
    "comida real y principios antiinflamatorios, y que se puedan hacer "
    "principalmente con lo que hay en el inventario. Prioriza usar primero "
    "lo que caduca antes. Ajusta la propuesta al estado de recuperación "
    "indicado y a las exigencias físicas de un jugador profesional de fútbol "
    "sala (por ejemplo, asegurando proteínas de alta calidad y una recarga "
    "óptima de glucógeno con carbohidratos naturales si hay fatiga o "
    "entrenamientos intensos, o platos más ligeros enfocados en "
    "micronutrientes si hay estrés elevado). Recuerda que puede sobrar comida "
    "en la nevera para otras comidas: es lo normal, no un problema a "
    "resolver.\n\n"
    "Usa solo ingredientes que aparezcan en el inventario. Responde solo con "
    "JSON estricto, sin explicaciones ni bloques de código markdown, con "
    "este formato exacto:\n"
    '[{{"nombre": "string", "descripcion": "string breve, 1-3 frases", '
    '"ingredientes": [{{"nombre": "string EXACTO del inventario", '
    '"cantidad": numero, "unidad": "g|ml|ud"}}]}}]'
)


def format_inventario(items) -> str:
    """Parte el inventario en dos bloques: perecederos (lo que hay que gastar)
    y básicos de despensa (lo que siempre está disponible para condimentar).

    La separación es deliberada: si la sal y las especias aparecen mezcladas
    con el pollo, Gemini las trata como ingredientes a priorizar por caducidad
    y propone recetas construidas alrededor de un condimento.
    """
    perecederos = []
    basicos = []
    for item in items:
        cantidad = format_cantidad(item.cantidad, item.unidad)
        if item.es_basico:
            # Sin cantidad: para un básico es un valor testigo, no un dato real.
            basicos.append(f"- {item.nombre}")
        else:
            cad = f", caduca {item.fecha_caducidad}" if item.fecha_caducidad else ""
            perecederos.append(f"- {item.nombre}: {cantidad}{cad}")

    bloques = []
    if perecederos:
        bloques.append(
            "PERECEDEROS (gástalos primero, ordenados por caducidad):\n" + "\n".join(perecederos)
        )
    if basicos:
        bloques.append(
            "DESPENSA (siempre disponible, en cantidad suficiente; úsalos para "
            "condimentar y cocinar, pero NO construyas la receta alrededor de "
            "ellos ni los priorices por caducidad):\n" + "\n".join(basicos)
        )
    return "\n\n".join(bloques)


def suggest_recipes(items, ultimo_analisis: dict | None) -> list[dict]:
    """items: iterable de NeveraItem (se recomienda ya ordenado por caducidad).
    ultimo_analisis: dict con "analysis_date" y "analysis_text", o None.

    Devuelve una lista de recetas: {"nombre", "descripcion", "ingredientes":
    [{"nombre", "cantidad", "unidad"}]}.
    """
    items = list(items)
    if not items:
        raise ValueError("La nevera está vacía.")

    if ultimo_analisis:
        fecha_analisis = ultimo_analisis["analysis_date"]
        analisis_texto = ultimo_analisis["analysis_text"]
    else:
        fecha_analisis = "sin análisis previo"
        analisis_texto = "(No hay ningún análisis de recuperación guardado todavía.)"

    prompt = PROMPT_TEMPLATE.format(
        inventario=format_inventario(items),
        fecha_analisis=fecha_analisis,
        analisis=analisis_texto,
    )
    respuesta = send_prompt_to_gemini(prompt)

    crudo = _extraer_json(respuesta)
    try:
        recetas = json.loads(crudo)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini no devolvió JSON válido: {exc}") from exc

    if not isinstance(recetas, list) or not recetas:
        raise ValueError("Gemini no devolvió ninguna receta.")

    for receta in recetas:
        if "nombre" not in receta or "ingredientes" not in receta:
            raise ValueError(f"Receta incompleta devuelta por Gemini: {receta!r}")
        for ingrediente in receta["ingredientes"]:
            if "nombre" not in ingrediente or "unidad" not in ingrediente:
                raise ValueError(f"Ingrediente incompleto devuelto por Gemini: {ingrediente!r}")

    return recetas


def _extraer_json(texto: str) -> str:
    texto = texto.strip()
    match = re.search(r"\[.*\]", texto, re.DOTALL)
    return match.group(0) if match else texto
