import type { UseQueryResult } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { Serie } from "../api/types";
import { CHART_CHROME } from "../lib/chartTheme";
import Card from "./Card";

interface Props {
  title: string;
  query: UseQueryResult<Serie>;
  dataKey: "avg" | "minutes";
  unit: string;
  color: string;
  /** Divisor aplicado antes de pintar. 60 convierte minutos en horas: la API
   *  devuelve siempre minutos (entero, sin pérdida) y la conversión a la
   *  unidad legible es decisión de presentación, no del backend. */
  scale?: number;
  /** Decimales del valor ya escalado. */
  decimals?: number;
  /** Si se pasa, pulsar un punto abre el detalle de ese día. */
  onSelectDay?: (fecha: string) => void;
}

/** Tooltip propio: el de Recharts por defecto trae borde duro y tipografía
 *  ajena al resto de la interfaz. */
function ChartTooltip({
  active,
  payload,
  label,
  unit,
  color,
  decimals = 0,
}: {
  active?: boolean;
  payload?: Array<{ value?: number | string }>;
  label?: string | number;
  unit: string;
  color: string;
  decimals?: number;
}) {
  if (!active || !payload?.length) return null;
  const value = payload[0]?.value;
  if (value == null) return null;
  return (
    <div className="rounded-xl bg-navbar px-3 py-2 text-white shadow-lg">
      <div className="text-[11px] text-white/60">{label}</div>
      <div className="text-sm font-semibold tabular-nums" style={{ color }}>
        {typeof value === "number"
          ? value.toLocaleString("es-ES", { maximumFractionDigits: decimals })
          : value}{" "}
        {unit}
      </div>
    </div>
  );
}

function Frame({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card className="p-6">
      <h2 className="mb-4 text-sm font-semibold text-ink-soft">{title}</h2>
      {children}
    </Card>
  );
}

export default function HealthChart({
  title,
  query,
  dataKey,
  unit,
  color,
  scale = 1,
  decimals = 0,
  onSelectDay,
}: Props) {
  if (query.isLoading) {
    return (
      <Frame title={title}>
        <div className="h-64 animate-pulse rounded-xl bg-canvas" />
      </Frame>
    );
  }
  if (query.isError) {
    return (
      <Frame title={title}>
        <p className="py-20 text-center text-sm text-coral">No se pudo cargar la gráfica.</p>
      </Frame>
    );
  }

  const points = query.data?.points ?? [];
  if (points.length === 0) {
    return (
      <Frame title={title}>
        <p className="py-20 text-center text-sm text-ink-muted">Sin datos en el rango.</p>
      </Frame>
    );
  }

  // Un id único por gráfica: dos <linearGradient> con el mismo id en el
  // documento colisionan y la segunda área hereda el degradado de la primera.
  const gradientId = `grad-${dataKey}`;

  // Eje temporal continuo: la API solo devuelve los días que tienen dato, y
  // pintarlos seguidos haría que un hueco de 17 días ocupase lo mismo que uno
  // de un día. Se rellenan los días vacíos con null y `connectNulls={false}`
  // corta la línea, de forma que un hueco de datos se vea como un hueco.
  const porFecha = new Map(
    points.map((p) => [p.date, p[dataKey] == null ? null : (p[dataKey] as number) / scale]),
  );
  const dia = 86_400_000;
  const primero = Date.parse(points[0].date);
  const ultimo = Date.parse(points[points.length - 1].date);
  const datos = [];
  for (let t = primero; t <= ultimo; t += dia) {
    const fecha = new Date(t).toISOString().slice(0, 10);
    datos.push({ date: fecha, [dataKey]: porFecha.get(fecha) ?? null });
  }

  // Con pocos puntos y huecos, un día suelto sin marcador sería invisible.
  const conMarcadores = points.length <= 40;

  return (
    <Frame title={title}>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={datos}
            margin={{ top: 8, right: 16, bottom: 0, left: -16 }}
            // `activeLabel` es el valor del eje X bajo el cursor, o sea la fecha
            // del punto. Solo se navega si ese día tiene dato: los huecos que
            // rellenamos con null no llevan a ninguna parte.
            onClick={(estado) => {
              const fecha = estado?.activeLabel;
              if (onSelectDay && typeof fecha === "string" && porFecha.get(fecha) != null) {
                onSelectDay(fecha);
              }
            }}
            className={onSelectDay ? "cursor-pointer" : undefined}
          >
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.28} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            {/* Rejilla recesiva: solo horizontal y casi invisible. */}
            <CartesianGrid vertical={false} stroke={CHART_CHROME.grid} strokeDasharray="0" />
            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={false}
              tickMargin={10}
              minTickGap={28}
              tick={{ fontSize: 11, fill: CHART_CHROME.axis }}
              tickFormatter={(d: string) => d.slice(5)}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              width={52}
              tick={{ fontSize: 11, fill: CHART_CHROME.axis }}
              tickFormatter={(v: number) =>
                v.toLocaleString("es-ES", { maximumFractionDigits: decimals })
              }
            />
            <Tooltip
              cursor={{ stroke: CHART_CHROME.cursor, strokeWidth: 1 }}
              content={<ChartTooltip unit={unit} color={color} decimals={decimals} />}
            />
            <Area
              type="monotone"
              dataKey={dataKey}
              stroke={color}
              strokeWidth={2}
              fill={`url(#${gradientId})`}
              connectNulls={false}
              dot={conMarcadores ? { r: 3, fill: color, strokeWidth: 0 } : false}
              activeDot={{ r: 5, strokeWidth: 2, stroke: CHART_CHROME.dotRing }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Frame>
  );
}
