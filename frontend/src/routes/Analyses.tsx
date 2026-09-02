import { useState } from "react";

import { ApiError } from "../api/client";
import { useAnalyses, useLanzarAnalisis } from "../api/hooks";
import Card from "../components/Card";

/** Mismo tope que `MAX_INSTRUCTION_CHARS` en el backend (health_ai/config.py).
 *  Aquí solo evita el viaje de ida y vuelta para un 400 evidente; la
 *  validación que cuenta es la del servidor, que es la que no se puede saltar
 *  desde la consola del navegador. */
const MAX_INSTRUCCION = 500;

function LanzarAnalisis() {
  const [instruccion, setInstruccion] = useState("");
  const lanzar = useLanzarAnalisis();

  function mensajeDeError(e: unknown): string {
    if (e instanceof ApiError) {
      // 409 no es un fallo del usuario: el bot está analizando en su propio
      // proceso y el advisory lock de Postgres rechaza el segundo intento.
      if (e.status === 409) return "El bot ya está analizando ahora mismo. Prueba en un minuto.";
      return e.message;
    }
    return "No se pudo lanzar el análisis.";
  }

  return (
    <Card className="space-y-3 p-5">
      <div>
        <h2 className="text-sm font-semibold text-ink">Lanzar un análisis nuevo</h2>
        <p className="text-xs text-ink-muted">
          Sin instrucción se usa la de por defecto, igual que <code>/analisis</code> en Telegram. Se
          sobrescribe el análisis de hoy si ya existe.
        </p>
      </div>

      <textarea
        className="w-full rounded border border-line bg-raised px-3 py-2 text-sm text-ink placeholder:text-ink-muted disabled:opacity-50"
        rows={3}
        maxLength={MAX_INSTRUCCION}
        placeholder="Qué quieres que analice (opcional)"
        value={instruccion}
        onChange={(e) => setInstruccion(e.target.value)}
        disabled={lanzar.isPending}
      />

      <div className="flex items-center gap-3">
        <button
          className="rounded bg-cyan px-3 py-1.5 text-xs font-semibold text-navbar disabled:opacity-50"
          onClick={() => lanzar.mutate(instruccion)}
          disabled={lanzar.isPending}
        >
          {lanzar.isPending ? "Analizando…" : "Lanzar análisis"}
        </button>
        {/* El estado de carga se cuenta con palabras y no solo deshabilitando
            el botón: la llamada a Gemini tarda 15-30 s y sin aviso parece que
            la web se ha colgado. */}
        {lanzar.isPending && (
          <span className="text-xs text-ink-muted">
            Gemini tarda entre 15 y 30 s. No cierres la pestaña.
          </span>
        )}
        <span className="ml-auto text-xs text-ink-muted">
          {instruccion.length}/{MAX_INSTRUCCION}
        </span>
      </div>

      {lanzar.isError && <p className="text-sm text-coral">{mensajeDeError(lanzar.error)}</p>}
      {lanzar.isSuccess && (
        <p className="text-sm text-cyan">Análisis guardado. Lo tienes el primero de la lista.</p>
      )}
    </Card>
  );
}

export default function Analyses() {
  const { data, isLoading, isError } = useAnalyses(20);

  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold tracking-tight text-ink">Histórico de análisis</h1>

      <LanzarAnalisis />

      {isLoading && <p className="text-sm text-ink-muted">Cargando…</p>}
      {isError && <p className="text-sm text-coral">No se pudo cargar el histórico.</p>}
      {data && data.length === 0 && (
        <p className="text-sm text-ink-muted">Todavía no hay análisis guardados.</p>
      )}
      <ul className="space-y-4">
        {data?.map((a) => (
          <li key={a.analysis_date}>
            <Card className="p-5">
              <div className="mb-1 text-sm font-semibold text-ink">{a.analysis_date}</div>
              {a.user_instruction && (
                <div className="mb-2 text-xs italic text-ink-muted">{a.user_instruction}</div>
              )}
              <p className="whitespace-pre-wrap text-sm text-ink-soft">{a.analysis_text}</p>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
