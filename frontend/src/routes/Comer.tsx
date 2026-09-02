import { useState } from "react";

import { ApiError } from "../api/client";
import { useConsumir, useSugerencias } from "../api/hooks";
import type { ConsumeResult, Receta } from "../api/types";
import Card from "../components/Card";
import { BOTON_PRIMARIO, INPUT } from "../lib/ui";

function mensajeDeError(e: unknown, porDefecto: string): string {
  if (e instanceof ApiError) return e.message;
  return porDefecto;
}

/** "pollo, huevos" -> ["pollo", "huevos"]. Se separa por comas y no por
 *  espacios para que "salmón ahumado" sea un término y no dos. */
function parseExclusiones(texto: string): string[] {
  return texto
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
}

function ResumenConsumo({ resultado }: { resultado: ConsumeResult }) {
  return (
    <div className="space-y-1 text-sm">
      <p className="font-semibold text-cyan">Nevera actualizada.</p>
      {resultado.aplicados.length > 0 && (
        <p className="text-ink-soft">
          Descontado:{" "}
          {resultado.aplicados
            .map((a) => `${a.nombre} (quedan ${a.restante} ${a.unidad})`)
            .join(", ")}
        </p>
      )}
      {/* Los básicos y los que faltaban se cuentan, pero no como errores: son
          el comportamiento correcto y explicarlo evita que parezca un fallo. */}
      {resultado.basicos.length > 0 && (
        <p className="text-ink-muted">
          Sin descontar (básicos de despensa): {resultado.basicos.map((b) => b.nombre).join(", ")}
        </p>
      )}
      {resultado.no_encontrados.length > 0 && (
        <p className="text-ink-muted">
          Ya no estaban en la nevera:{" "}
          {resultado.no_encontrados.map((n) => n.nombre).join(", ")}
        </p>
      )}
    </div>
  );
}

function RecetaCard({
  receta,
  onHecho,
  guardando,
}: {
  receta: Receta;
  onHecho: () => void;
  guardando: boolean;
}) {
  return (
    <Card className="space-y-3 p-5">
      <div>
        <h3 className="text-sm font-semibold text-ink">{receta.nombre}</h3>
        <p className="text-sm text-ink-soft">{receta.descripcion}</p>
      </div>
      <ul className="space-y-0.5 text-sm text-ink-soft">
        {receta.ingredientes.map((ing, i) => (
          <li key={i}>
            {ing.nombre} — {ing.cantidad} {ing.unidad}
          </li>
        ))}
      </ul>
      <button className={BOTON_PRIMARIO} onClick={onHecho} disabled={guardando}>
        {guardando ? "Descontando…" : "La he hecho"}
      </button>
    </Card>
  );
}

/**
 * Sugerencias de comida (SDD-web fase 6.c). Equivale a `/comer` + `/hecho`.
 *
 * Igual que el alta con IA, el estado intermedio vive aquí y no en el
 * servidor: las recetas propuestas solo existen en esta pantalla. Al marcar
 * una como hecha se mandan **sus ingredientes**, no "la receta número 2", que
 * es lo que obligaría al servidor a recordar lo que propuso.
 */
export default function Comer() {
  const [exclusiones, setExclusiones] = useState("");
  const [hecha, setHecha] = useState<ConsumeResult | null>(null);
  const sugerir = useSugerencias();
  const consumir = useConsumir();

  const sugerencias = sugerir.data;

  function pedir() {
    setHecha(null);
    consumir.reset();
    sugerir.mutate({ exclude: parseExclusiones(exclusiones) });
  }

  function marcarHecha(receta: Receta) {
    consumir.mutate(receta.ingredientes, {
      onSuccess: (resultado) => {
        setHecha(resultado);
        // Las demás sugerencias dejan de valer: se han gastado ingredientes y
        // las cantidades que las sostenían ya no son las de la nevera.
        sugerir.reset();
      },
    });
  }

  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold tracking-tight text-ink">Qué comer</h1>

      <Card className="space-y-3 p-5">
        <p className="text-xs text-ink-muted">
          Cruza lo que hay en la nevera (priorizando lo que caduca antes) con tu último análisis de
          recuperación. Equivale a <code>/comer</code> en Telegram.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <input
            className={`${INPUT} max-w-xs`}
            placeholder="Sin… (pollo, huevos)"
            aria-label="Ingredientes a excluir, separados por comas"
            value={exclusiones}
            onChange={(e) => setExclusiones(e.target.value)}
            disabled={sugerir.isPending}
          />
          <button className={BOTON_PRIMARIO} onClick={pedir} disabled={sugerir.isPending}>
            {sugerir.isPending ? "Pensando…" : "Sugerir"}
          </button>
          {sugerir.isPending && (
            <span className="text-xs text-ink-muted">Gemini está mirando la nevera…</span>
          )}
        </div>
        {sugerir.isError && (
          <p className="text-sm text-coral">
            {mensajeDeError(sugerir.error, "No se pudo generar una sugerencia.")}
          </p>
        )}
        {consumir.isError && (
          <p className="text-sm text-coral">
            {mensajeDeError(consumir.error, "No se pudo actualizar la nevera.")}
          </p>
        )}
        {hecha && <ResumenConsumo resultado={hecha} />}
      </Card>

      {sugerencias && (
        <>
          {sugerencias.excluded.length > 0 && (
            <p className="text-xs text-ink-muted">Sin: {sugerencias.excluded.join(", ")}</p>
          )}
          {sugerencias.not_found.length > 0 && (
            <p className="text-xs text-coral">
              No encontré en la nevera: {sugerencias.not_found.join(", ")}. Repasa cómo lo has
              escrito: si no casa con nada, no se ha excluido.
            </p>
          )}
          {sugerencias.analysis_date && (
            <p className="text-xs text-ink-muted">
              Ajustado a tu análisis del {sugerencias.analysis_date}.
            </p>
          )}
          <div className="grid gap-4 md:grid-cols-2">
            {sugerencias.recipes.map((receta, i) => (
              <RecetaCard
                key={i}
                receta={receta}
                guardando={consumir.isPending}
                onHecho={() => marcarHecha(receta)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
