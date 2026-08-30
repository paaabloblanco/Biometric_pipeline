"""Handlers de comandos del bot. Sin lógica de negocio: todo lo pesado vive en
`health_ai.pruebas` y `supabase_data.services`."""

import asyncio
import functools
import logging
from datetime import date

from django.utils import timezone
from telegram import Update
from telegram.constants import ChatAction
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.config import DEFAULT_INSTRUCTION, is_authorized
from bot.formatting import split_message

log = logging.getLogger(__name__)


def _args(context: ContextTypes.DEFAULT_TYPE) -> list[str]:
    """context.args solo es None antes de que la librería lo rellene; en un
    handler ya registrado, collect_additional_context lo hace siempre antes
    de invocar el callback (ver telegram.ext._handlers.commandhandler)."""
    assert context.args is not None
    return context.args


# Un solo análisis de Gemini a la vez (evita gastar cuota por pulsaciones repetidas).
_analysis_lock = asyncio.Lock()

# Altas de /añadir pendientes de confirmación, por chat_id. Se pierden si el
# proceso del bot se reinicia (aceptado en el SDD, ver decisión A).
_pending_altas: dict[int, list[dict]] = {}

# Última sugerencia de /comer por chat_id, para que /hecho <n> sepa qué
# ingredientes restar. También se pierde si el bot se reinicia (decisión B).
_pending_recetas: dict[int, list[dict]] = {}

DIAS_ALERTA_CADUCIDAD = 3

HELP_TEXT = (
    "Comandos disponibles:\n\n"
    "/analisis [instrucción] — análisis del último día con Gemini. "
    "Sin texto usa la instrucción por defecto.\n"
    "/hoy — resumen de datos crudos del último día (sin IA).\n"
    "/historial [n] — últimos n análisis guardados (por defecto 3).\n"
    "/anadir <texto> — da de alta una compra transcrita (pide confirmación).\n"
    "/confirmar — guarda la última alta pendiente de /anadir.\n"
    "/cancelar — descarta la alta pendiente.\n"
    "/nevera — lista el inventario actual.\n"
    "/borrar <id> — borra un item de la nevera.\n"
    "/editar <id> <campo>=<valor> ... — edita un item "
    "(campos: cantidad, unidad, categoria, fecha_caducidad, nombre).\n"
    "/comer — sugerencia de qué cocinar con lo que hay en la nevera.\n"
    "/hecho <n> — confirma la receta n de la última sugerencia de /comer "
    "y descuenta sus ingredientes.\n"
    "/comprar <texto de la gazetka> — dice qué ofertas merece la pena "
    "aprovechar según lo que tienes en la nevera.\n"
    "/help — esta ayuda."
)


def restricted(func):
    """Ignora en silencio a cualquier chat que no esté en la allowlist."""

    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        if chat is None or not is_authorized(chat.id):
            log.warning("Mensaje ignorado de chat no autorizado: %s", chat and chat.id)
            return
        return await func(update, context)

    return wrapper


async def _reply_long(update: Update, text: str, parse_mode: str | None = "Markdown"):
    for part in split_message(text):
        try:
            await update.effective_message.reply_text(part, parse_mode=parse_mode)
        except TelegramError:
            # Markdown mal formado (texto de Gemini): reintento en plano.
            await update.effective_message.reply_text(part)


@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "Bot de salud activo.\n\n" + HELP_TEXT
    )


@restricted
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(HELP_TEXT)


@restricted
async def hoy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from supabase_data.services import get_last_day_data

    try:
        data = await asyncio.to_thread(get_last_day_data)
    except Exception as exc:
        log.exception("Fallo en /hoy")
        await update.effective_message.reply_text(f"No se pudieron leer los datos: {exc}")
        return

    await update.effective_message.reply_text(_summarize_day(data), parse_mode="Markdown")


@restricted
async def historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from supabase_data.services import get_recent_analyses

    n = 3
    args = _args(context)
    if args:
        try:
            n = max(1, min(10, int(args[0])))
        except ValueError:
            pass

    try:
        analyses = await asyncio.to_thread(get_recent_analyses, n)
    except Exception as exc:
        log.exception("Fallo en /historial")
        await update.effective_message.reply_text(f"No se pudo leer el historial: {exc}")
        return

    if not analyses:
        await update.effective_message.reply_text("Todavía no hay análisis guardados.")
        return

    bloques = [
        f"*{a['analysis_date']}*\n{a['analysis_text']}" for a in analyses
    ]
    await _reply_long(update, "\n\n———\n\n".join(bloques))


@restricted
async def analisis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    instruccion = " ".join(_args(context)).strip() or DEFAULT_INSTRUCTION

    if _analysis_lock.locked():
        await update.effective_message.reply_text(
            "Ya hay un análisis en curso, espera a que termine."
        )
        return

    async with _analysis_lock:
        await update.effective_message.reply_text(
            "Analizando… (~15-30 s). Se sobrescribe el análisis de hoy si ya existía."
        )
        await update.effective_chat.send_action(ChatAction.TYPING)

        from health_ai.pruebas import run_analysis

        try:
            result = await asyncio.to_thread(run_analysis, instruccion, True)
        except Exception as exc:
            log.exception("Fallo en /analisis")
            await update.effective_message.reply_text(
                f"No se pudo completar el análisis: {exc}"
            )
            return

    await _reply_long(update, result["response"])


@restricted
async def añadir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    texto = " ".join(_args(context)).strip()
    if not texto:
        await update.effective_message.reply_text("Uso: /anadir <texto de la compra>")
        return

    await update.effective_chat.send_action(ChatAction.TYPING)

    from nevera.parsing import parse_compra_text
    from nevera.units import to_base

    try:
        items = await asyncio.to_thread(parse_compra_text, texto)
        for item in items:
            to_base(item["cantidad"], item["unidad"])  # valida unidad pronto
    except Exception as exc:
        log.exception("Fallo en /añadir")
        await update.effective_message.reply_text(f"No se pudo interpretar el texto: {exc}")
        return

    _pending_altas[chat_id] = items
    await update.effective_message.reply_text(
        "He entendido:\n\n" + _formato_items(items) +
        "\n\n¿Confirmo? /confirmar o /cancelar"
    )


@restricted
async def confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    items = _pending_altas.get(chat_id)
    if not items:
        await update.effective_message.reply_text("No hay ninguna alta pendiente de /anadir.")
        return

    from nevera.services import add_items

    try:
        await asyncio.to_thread(add_items, items, "compra")
    except Exception as exc:
        log.exception("Fallo al confirmar /añadir")
        await update.effective_message.reply_text(f"No se pudo guardar: {exc}")
        return

    del _pending_altas[chat_id]
    await update.effective_message.reply_text(f"Añadido a la nevera: {len(items)} item(s).")


@restricted
async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if _pending_altas.pop(chat_id, None) is None:
        await update.effective_message.reply_text("No había ninguna alta pendiente.")
    else:
        await update.effective_message.reply_text("Alta cancelada.")


@restricted
async def nevera_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from nevera.services import list_all

    try:
        items = await asyncio.to_thread(list_all)
    except Exception as exc:
        log.exception("Fallo en /nevera")
        await update.effective_message.reply_text(f"No se pudo leer la nevera: {exc}")
        return

    if not items:
        await update.effective_message.reply_text("La nevera está vacía.")
        return

    await _reply_long(update, _formato_nevera(items))


@restricted
async def borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = _args(context)
    if not args:
        await update.effective_message.reply_text("Uso: /borrar <id>")
        return
    try:
        item_id = int(args[0])
    except ValueError:
        await update.effective_message.reply_text("El id debe ser un número. Consulta /nevera.")
        return

    from nevera.services import delete_item

    borrado = await asyncio.to_thread(delete_item, item_id)
    await update.effective_message.reply_text("Borrado." if borrado else f"No existe el item {item_id}.")


@restricted
async def editar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = _args(context)
    if len(args) < 2:
        await update.effective_message.reply_text(
            "Uso: /editar <id> <campo>=<valor> ... "
            "(campos: cantidad, unidad, categoria, fecha_caducidad, nombre)"
        )
        return

    try:
        item_id = int(args[0])
    except ValueError:
        await update.effective_message.reply_text("El id debe ser un número. Consulta /nevera.")
        return

    cambios: dict = {}
    for par in args[1:]:
        if "=" not in par:
            await update.effective_message.reply_text(f"Argumento inválido: {par!r} (usa campo=valor)")
            return
        campo, valor = par.split("=", 1)
        campo = campo.strip().lower()
        if campo == "cantidad":
            try:
                cambios["cantidad"] = float(valor)
            except ValueError:
                await update.effective_message.reply_text(f"Cantidad inválida: {valor!r}")
                return
        elif campo == "unidad":
            cambios["unidad"] = valor.strip()
        elif campo == "categoria":
            cambios["categoria"] = valor.strip()
        elif campo == "nombre":
            cambios["nombre"] = valor.strip()
        elif campo == "fecha_caducidad":
            if valor.strip().lower() in ("none", "null", "-"):
                cambios["fecha_caducidad"] = None
            else:
                try:
                    cambios["fecha_caducidad"] = date.fromisoformat(valor.strip())
                except ValueError:
                    await update.effective_message.reply_text(
                        f"Fecha inválida: {valor!r} (usa YYYY-MM-DD)"
                    )
                    return
        else:
            await update.effective_message.reply_text(f"Campo desconocido: {campo!r}")
            return

    from nevera.services import edit_item

    try:
        actualizado = await asyncio.to_thread(edit_item, item_id, **cambios)
    except Exception as exc:
        log.exception("Fallo en /editar")
        await update.effective_message.reply_text(f"No se pudo editar: {exc}")
        return

    if actualizado is None:
        await update.effective_message.reply_text(f"No existe el item {item_id}.")
        return

    await update.effective_message.reply_text(f"Actualizado: {actualizado}")


@restricted
async def comer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.effective_chat.send_action(ChatAction.TYPING)

    from nevera.services import get_items_by_expiry
    from nevera.suggestions import suggest_recipes
    from supabase_data.services import get_recent_analyses

    try:
        items = await asyncio.to_thread(get_items_by_expiry)
        if not items:
            await update.effective_message.reply_text(
                "La nevera está vacía. Usa /anadir para dar de alta la compra."
            )
            return

        analyses = await asyncio.to_thread(get_recent_analyses, 1)
        ultimo_analisis = analyses[0] if analyses else None

        recetas = await asyncio.to_thread(suggest_recipes, items, ultimo_analisis)
    except Exception as exc:
        log.exception("Fallo en /comer")
        await update.effective_message.reply_text(f"No se pudo generar una sugerencia: {exc}")
        return

    _pending_recetas[chat_id] = recetas
    await _reply_long(update, _formato_recetas(recetas, ultimo_analisis))


@restricted
async def hecho(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = _args(context)
    if not args:
        await update.effective_message.reply_text("Uso: /hecho <n> (número de la sugerencia de /comer)")
        return

    try:
        indice = int(args[0])
    except ValueError:
        await update.effective_message.reply_text("El número debe ser un entero. Mira /comer.")
        return

    recetas = _pending_recetas.get(chat_id)
    if not recetas:
        await update.effective_message.reply_text("No hay ninguna sugerencia de /comer pendiente.")
        return

    if not (1 <= indice <= len(recetas)):
        await update.effective_message.reply_text(f"Elige un número entre 1 y {len(recetas)}.")
        return

    receta = recetas[indice - 1]

    from nevera.services import consume_items

    try:
        resultado = await asyncio.to_thread(consume_items, receta["ingredientes"])
    except Exception as exc:
        log.exception("Fallo en /hecho")
        await update.effective_message.reply_text(f"No se pudo actualizar la nevera: {exc}")
        return

    del _pending_recetas[chat_id]
    await update.effective_message.reply_text(_formato_resultado_hecho(receta, resultado))


@restricted
async def comprar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = " ".join(_args(context)).strip()
    if not texto:
        await update.effective_message.reply_text(
            "Uso: /comprar <texto de las ofertas>\n\n"
            "Pásame el texto de la gazetka/ofertas de Biedronka (transcrito de la "
            "app oficial, de Blix o de donde las mires) y te digo cuáles merece "
            "la pena aprovechar según lo que tienes en la nevera."
        )
        return

    await update.effective_chat.send_action(ChatAction.TYPING)

    from nevera.ofertas import analizar_ofertas
    from nevera.services import list_all

    try:
        items = await asyncio.to_thread(list_all)
        recomendaciones = await asyncio.to_thread(analizar_ofertas, texto, items)
    except Exception as exc:
        log.exception("Fallo en /comprar")
        await update.effective_message.reply_text(f"No se pudo analizar las ofertas: {exc}")
        return

    if not recomendaciones:
        await update.effective_message.reply_text(
            "Ninguna oferta parece merecer la pena con lo que tienes ahora mismo en la nevera."
        )
        return

    await _reply_long(update, _formato_ofertas(recomendaciones))


def _formato_ofertas(recomendaciones: list[dict]) -> str:
    lineas = ["Ofertas que merece la pena aprovechar:"]
    for r in recomendaciones:
        precio = f" ({r['precio']})" if r.get("precio") else ""
        motivo = r.get("motivo", "")
        lineas.append(f"• {r['nombre']}{precio} — {motivo}")
    return "\n".join(lineas)


def _formato_recetas(recetas: list[dict], ultimo_analisis: dict | None) -> str:
    bloques = []
    if ultimo_analisis:
        bloques.append(f"(Sugerencia según el análisis del {ultimo_analisis['analysis_date']})")
    else:
        bloques.append("(No hay ningún análisis de recuperación guardado todavía.)")

    for i, receta in enumerate(recetas, start=1):
        ingredientes = ", ".join(
            f"{ing['cantidad']} {ing['unidad']} {ing['nombre']}" for ing in receta["ingredientes"]
        )
        bloques.append(
            f"*{i}. {receta['nombre']}*\n{receta.get('descripcion', '')}\nIngredientes: {ingredientes}"
        )

    bloques.append("Cuando hagas una, confirma con /hecho <n>")
    return "\n\n".join(bloques)


def _formato_resultado_hecho(receta: dict, resultado: dict) -> str:
    lineas = [f"Hecho: *{receta['nombre']}*. Nevera actualizada:"]
    for item in resultado["aplicados"]:
        if item["restante"] == 0:
            lineas.append(f"• {item['nombre']}: agotado")
        else:
            lineas.append(f"• {item['nombre']}: quedan {item['restante']} {item['unidad']}")

    if resultado["no_encontrados"]:
        nombres = ", ".join(c["nombre"] for c in resultado["no_encontrados"])
        lineas.append(f"⚠️ No encontrados en la nevera (no se descontaron): {nombres}")

    return "\n".join(lineas)


def _formato_items(items: list[dict]) -> str:
    lineas = []
    for it in items:
        cat = f" [{it['categoria']}]" if it.get("categoria") else ""
        cad = f" (caduca {it['fecha_caducidad']})" if it.get("fecha_caducidad") else ""
        lineas.append(f"• {it['cantidad']} {it['unidad']} {it['nombre']}{cat}{cad}")
    return "\n".join(lineas)


def _formato_nevera(items) -> str:
    from nevera.units import format_cantidad

    hoy = timezone.localtime().date()
    grupos: dict[str, list] = {}
    for item in items:
        clave = item.categoria or "sin categoría"
        grupos.setdefault(clave, []).append(item)

    bloques = []
    for categoria in sorted(grupos):
        lineas = [f"*{categoria}*"]
        for item in grupos[categoria]:
            alerta = ""
            if item.fecha_caducidad and (item.fecha_caducidad - hoy).days <= DIAS_ALERTA_CADUCIDAD:
                alerta = " ⚠️ caduca pronto"
                if (item.fecha_caducidad - hoy).days < 0:
                    alerta = " ⚠️ caducado"
            cad = f", caduca {item.fecha_caducidad}" if item.fecha_caducidad else ""
            lineas.append(
                f"#{item.id} {item.nombre}: {format_cantidad(item.cantidad, item.unidad)}{cad}{alerta}"
            )
        bloques.append("\n".join(lineas))
    return "\n\n".join(bloques)


def _summarize_day(data: dict) -> str:
    hr = data.get("heart_rate_samples", [])
    spo2 = data.get("oxygen_saturation_samples", [])
    resting = data.get("resting_heart_rate_samples", [])
    sleep = data.get("sleep_stages", [])

    lines = [f"*Datos del {data.get('date', '?')}*", ""]
    lines.append(f"• Frecuencia cardíaca: {len(hr)} muestras")
    if hr:
        bpms = [s["bpm"] for s in hr]
        lines.append(f"  min {min(bpms)} / media {round(sum(bpms) / len(bpms))} / max {max(bpms)} bpm")

    if resting:
        rbpms = [s["resting_bpm"] for s in resting]
        lines.append(f"• RHR: {round(sum(rbpms) / len(rbpms))} bpm ({len(resting)} muestras)")
    else:
        lines.append("• RHR: sin datos")

    if spo2:
        pcts = [float(s["percentage"]) for s in spo2]
        lines.append(f"• SpO2: media {round(sum(pcts) / len(pcts), 1)}% ({len(spo2)} muestras)")
    else:
        lines.append("• SpO2: sin datos")

    lines.append(f"• Etapas de sueño: {len(sleep)} tramos")
    return "\n".join(lines)
