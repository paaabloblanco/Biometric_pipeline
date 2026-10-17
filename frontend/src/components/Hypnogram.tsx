import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useState } from "react";

import type { SleepNight, SleepSegment, SleepStageName } from "../api/types";
import { SLEEP_COLORS } from "../lib/chartTheme";
import { formatoDuracion, horaLocalServidor, soloHora } from "../lib/format";
import Card from "./Card";

/** Fases ordenadas de más superficial a más profunda: es el orden vertical
 *  clásico de un hipnograma y hace que el dibujo "baje" al dormir hondo.
 *  Ese orden es también el que se pasó al validador de paleta (los pares que
 *  se comparan de un vistazo son las filas contiguas), así que no lo cambies
 *  sin revalidar. Además, cada fila lleva su etiqueta escrita: la identidad de
 *  una fase nunca depende solo del color. */
const FASES: { stage: SleepStageName; label: string; color: string }[] = [
  { stage: "despierto", label: "Despierto", color: SLEEP_COLORS.awake },
  { stage: "despierto_en_cama", label: "En cama", color: SLEEP_COLORS.awake },
  { stage: "fuera_de_cama", label: "Fuera de cama", color: SLEEP_COLORS.unknown },
  { stage: "rem", label: "REM", color: SLEEP_COLORS.rem },
  { stage: "ligero", label: "Ligero", color: SLEEP_COLORS.light },
  { stage: "dormido", label: "Dormido", color: SLEEP_COLORS.light },
  { stage: "profundo", label: "Profundo", color: SLEEP_COLORS.deep },
  { stage: "desconocido", label: "Sin clasificar", color: SLEEP_COLORS.unknown },
];

function faseDe(stage: SleepStageName) {
  return FASES.find((f) => f.stage === stage);
}
const etiquetaDe = (stage: SleepStageName) => faseDe(stage)?.label ?? stage;
const colorDe = (stage: SleepStageName) => faseDe(stage)?.color ?? SLEEP_COLORS.unknown;

const ANCHO_ETIQUETAS = 96;
const ALTO_FILA = 30;

/** Un segmento ya proyectado sobre el ancho de la noche, en porcentajes. */
interface Bloque {
  seg: SleepSegment;
  izquierda: number;
  ancho: number;
  centro: number;
}

function marcasHorarias(desde: Date, hasta: Date): { pct: number; etiqueta: string }[] {
  const span = hasta.getTime() - desde.getTime();
  const marcas = [];
  const cursor = new Date(desde);
  cursor.setUTCMinutes(0, 0, 0);
  cursor.setUTCHours(cursor.getUTCHours() + 1);
  while (cursor < hasta) {
    marcas.push({
      pct: ((cursor.getTime() - desde.getTime()) / span) * 100,
      etiqueta: `${String(cursor.getUTCHours()).padStart(2, "0")}:00`,
    });
    cursor.setUTCHours(cursor.getUTCHours() + 1);
  }
  return marcas;
}

function Marco({
  children,
  extra,
  title,
}: {
  children: ReactNode;
  extra?: ReactNode;
  title: string;
}) {
  return (
    <Card className="p-6">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink-soft">{title}</h2>
        {extra}
      </div>
      {children}
    </Card>
  );
}

export default function Hypnogram({
  query,
  title = "Fases del sueño — última noche",
}: {
  query: UseQueryResult<SleepNight>;
  title?: string;
}) {
  const [activo, setActivo] = useState<number | null>(null);

  if (query.isLoading) {
    return (
      <Marco title={title}>
        <div className="h-40 animate-pulse rounded-xl bg-canvas" />
      </Marco>
    );
  }
  if (query.isError) {
    return (
      <Marco title={title}>
        <p className="py-14 text-center text-sm text-coral">No se pudo cargar la noche.</p>
      </Marco>
    );
  }

  const noche = query.data;
  if (!noche?.start || !noche.end || noche.segments.length === 0) {
    return (
      <Marco title={title}>
        <p className="py-14 text-center text-sm text-ink-muted">
          No hay fases de sueño registradas para esa noche.
        </p>
      </Marco>
    );
  }

  const desde = horaLocalServidor(noche.start);
  const span = horaLocalServidor(noche.end).getTime() - desde.getTime();

  // La geometría se calcula una vez: las filas y el tooltip leen el mismo
  // array, así no puede desalinearse un bloque respecto a su etiqueta.
  const bloques: Bloque[] = noche.segments.map((seg) => {
    const ini = horaLocalServidor(seg.start).getTime() - desde.getTime();
    const dur = horaLocalServidor(seg.end).getTime() - horaLocalServidor(seg.start).getTime();
    const izquierda = (ini / span) * 100;
    const ancho = (dur / span) * 100;
    return { seg, izquierda, ancho, centro: izquierda + ancho / 2 };
  });

  // Solo se dibujan las filas de las fases que hubo: reservar una fila vacía
  // para "Fuera de cama" cada noche sería ruido.
  const presentes = FASES.filter((f) => noche.segments.some((s) => s.stage === f.stage));
  const minutosPorFase = new Map(noche.totals.map((t) => [t.stage, t.minutes]));
  const marcas = marcasHorarias(desde, horaLocalServidor(noche.end));
  const destacado = activo === null ? null : bloques[activo];

  return (
    <Marco
      title={title}
      extra={
        destacado ? (
          <span className="text-xs text-ink-soft">
            <span
              className="mr-1.5 inline-block size-2.5 translate-y-px rounded-sm"
              style={{ backgroundColor: colorDe(destacado.seg.stage) }}
            />
            <span className="font-semibold text-ink">{etiquetaDe(destacado.seg.stage)}</span> ·{" "}
            {soloHora(destacado.seg.start)}–{soloHora(destacado.seg.end)} ·{" "}
            <span className="tabular-nums">{destacado.seg.minutes} min</span>
          </span>
        ) : (
          <span className="text-xs text-ink-muted">
            {soloHora(noche.start)} – {soloHora(noche.end)} ·{" "}
            <span className="font-semibold text-ink">{formatoDuracion(noche.total_minutes)}</span>{" "}
            dormidos
          </span>
        )
      }
    >
      <div className="overflow-x-auto">
        <div className="flex min-w-[520px]">
          {/* Columna de etiquetas: la identidad de cada fase nunca depende
              solo del color. */}
          <div style={{ width: ANCHO_ETIQUETAS }} className="shrink-0">
            {presentes.map((f) => (
              <div
                key={f.stage}
                style={{ height: ALTO_FILA }}
                className="flex items-center gap-2 pr-3 text-xs text-ink-soft"
              >
                <span
                  className="size-2.5 shrink-0 rounded-sm"
                  style={{ backgroundColor: f.color }}
                />
                <span className="truncate">{f.label}</span>
              </div>
            ))}
          </div>

          {/* Pista temporal. Cada bloque se posiciona en porcentaje sobre el
              intervalo de la noche: responsive sin medir anchos en JS. */}
          <div className="relative grow">
            {marcas.map((m) => (
              <span
                key={m.etiqueta}
                className="absolute top-0 w-px bg-line"
                style={{
                  left: `${m.pct}%`,
                  height: presentes.length * ALTO_FILA,
                }}
              />
            ))}

            {presentes.map((f) => (
              <div key={f.stage} style={{ height: ALTO_FILA }} className="relative">
                {bloques.map((b, i) =>
                  b.seg.stage !== f.stage ? null : (
                    <button
                      key={i}
                      type="button"
                      onMouseEnter={() => setActivo(i)}
                      onMouseLeave={() => setActivo(null)}
                      onFocus={() => setActivo(i)}
                      onBlur={() => setActivo(null)}
                      aria-label={`${f.label}, de ${soloHora(b.seg.start)} a ${soloHora(b.seg.end)}, ${b.seg.minutes} minutos`}
                      className={`absolute top-1 bottom-1 rounded-[3px] transition-opacity ${
                        activo === i ? "opacity-100 ring-2 ring-ink/40" : "hover:opacity-75"
                      }`}
                      style={{
                        left: `${b.izquierda}%`,
                        // Mínimo de 3px: una fase de 3 min sería invisible.
                        width: `max(3px, ${b.ancho}%)`,
                        backgroundColor: f.color,
                      }}
                    />
                  ),
                )}
              </div>
            ))}

            <div className="relative mt-1 h-4">
              {marcas.map((m) => (
                <span
                  key={m.etiqueta}
                  className="absolute -translate-x-1/2 text-[11px] text-ink-muted"
                  style={{ left: `${m.pct}%` }}
                >
                  {m.etiqueta}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Reparto de la noche: lo que se mira después de la forma general. */}
      <div className="mt-5 flex flex-wrap gap-x-6 gap-y-2 border-t border-line pt-4">
        {presentes.map((f) => {
          const min = minutosPorFase.get(f.stage) ?? 0;
          return (
            <div key={f.stage} className="flex items-center gap-2">
              <span className="size-2.5 rounded-sm" style={{ backgroundColor: f.color }} />
              <span className="text-xs text-ink-muted">{f.label}</span>
              <span className="text-xs font-semibold text-ink tabular-nums">
                {formatoDuracion(min)}
              </span>
              <span className="text-[11px] text-ink-muted tabular-nums">
                {Math.round((min / noche.total_minutes) * 100)}%
              </span>
            </div>
          );
        })}
      </div>
    </Marco>
  );
}
