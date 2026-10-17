import { useState } from "react";

import { ApiError } from "../api/client";
import { useAnalizarOfertas } from "../api/hooks";
import Card from "../components/Card";
import { BOTON_PRIMARIO, INPUT } from "../lib/ui";

/** Mismo tope que `MAX_OFERTAS_CHARS` en el backend (nevera/ofertas.py). Más
 *  holgado que el del alta: una gazetka entera son varias páginas. */
const MAX_TEXTO = 12000;

/**
 * Ofertas del supermercado (SDD-web fase 6.d). Equivale a `/comprar`.
 *
 * Es la función que mejor encaja en la web y peor en el bot (decisión §7-G del
 * SDD): la entrada es un bloque largo pegado del folleto, que aquí entra de una
 * vez y en Telegram habría que trocear en varios mensajes. Por eso el textarea
 * es el elemento dominante de la pantalla.
 */
export default function Comprar() {
  const [texto, setTexto] = useState("");
  const analizar = useAnalizarOfertas();

  const recomendaciones = analizar.data;

  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold tracking-tight text-ink">Ofertas</h1>

      <Card className="space-y-3 p-5">
        <p className="text-xs text-ink-muted">
          Pega el texto de la gazetka (de la app del súper, de Blix o de donde la mires) y te digo
          qué merece la pena según lo que ya tienes en la nevera. Equivale a{" "}
          <code>/comprar</code> en Telegram.
        </p>

        <textarea
          className={`${INPUT} font-mono`}
          rows={12}
          maxLength={MAX_TEXTO}
          placeholder="Pechuga de pollo 5,99 zł/kg — Salmón fresco -30% — Yogur natural 2x1…"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          disabled={analizar.isPending}
        />

        <div className="flex items-center gap-3">
          <button
            className={BOTON_PRIMARIO}
            onClick={() => analizar.mutate(texto)}
            disabled={analizar.isPending || !texto.trim()}
          >
            {analizar.isPending ? "Analizando…" : "Analizar ofertas"}
          </button>
          {analizar.isPending && (
            <span className="text-xs text-ink-muted">Gemini está cruzando con la nevera…</span>
          )}
          <span className="ml-auto text-xs text-ink-muted">
            {texto.length}/{MAX_TEXTO}
          </span>
        </div>

        {analizar.isError && (
          <p className="text-sm text-coral">
            {analizar.error instanceof ApiError
              ? analizar.error.message
              : "No se pudo analizar las ofertas."}
          </p>
        )}
      </Card>

      {/* Lista vacía es una respuesta, no un fallo: significa que con la nevera
          de ahora no compensa ninguna. Se dice con palabras en vez de dejar la
          pantalla en blanco, que se leería como que algo se rompió. */}
      {recomendaciones && recomendaciones.length === 0 && (
        <p className="text-sm text-ink-muted">
          Ninguna oferta parece merecer la pena con lo que tienes ahora mismo en la nevera.
        </p>
      )}

      {recomendaciones && recomendaciones.length > 0 && (
        <ul className="space-y-3">
          {recomendaciones.map((r, i) => (
            <li key={i}>
              <Card className="p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="text-sm font-semibold text-ink">{r.nombre}</span>
                  {r.precio && <span className="text-sm font-semibold text-cyan">{r.precio}</span>}
                </div>
                {r.motivo && <p className="mt-1 text-sm text-ink-soft">{r.motivo}</p>}
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
