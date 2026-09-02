import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { IntradayPoint } from "../api/types";
import { CHART_CHROME } from "../lib/chartTheme";
import { horaLocalServidor } from "../lib/format";
import Card from "./Card";

const HORA = 3_600_000;

interface Props {
  title: string;
  /** Día que se dibuja (`YYYY-MM-DD`), para fijar el eje a las 24 horas. */
  date: string;
  points: IntradayPoint[];
  unit: string;
  color: string;
  decimals?: number;
}

function IntradayTooltip({
  active,
  payload,
  unit,
  color,
  decimals = 0,
}: {
  active?: boolean;
  payload?: Array<{ payload?: { ts: number; v: number } }>;
  unit: string;
  color: string;
  decimals?: number;
}) {
  const punto = payload?.[0]?.payload;
  if (!active || !punto) return null;
  const d = new Date(punto.ts);
  const hhmm = `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
  return (
    <div className="rounded-xl bg-navbar px-3 py-2 text-white shadow-lg">
      <div className="text-[11px] text-white/60">{hhmm}</div>
      <div className="text-sm font-semibold tabular-nums" style={{ color }}>
        {punto.v.toLocaleString("es-ES", { maximumFractionDigits: decimals })} {unit}
      </div>
    </div>
  );
}

export default function IntradayChart({ title, date, points, unit, color, decimals = 0 }: Props) {
  // El eje cubre siempre las 24 horas del día, aunque solo haya muestras en
  // una franja: así se ve de un vistazo cuándo NO midió el reloj, que con este
  // sync es tan informativo como los propios datos.
  const inicioDia = horaLocalServidor(`${date}T00:00:00`).getTime();
  const finDia = inicioDia + 24 * HORA;

  const datos = points.map((p) => ({ ts: horaLocalServidor(p.t).getTime(), v: p.v }));

  const marcas = [];
  for (let t = inicioDia; t <= finDia; t += 3 * HORA) marcas.push(t);

  // Dominio redondeado a decenas. Dejando que Recharts derive las marcas de
  // un `dataMin - 5` crudo salen valores como 37, 62, 87 y 127, que se leen
  // mucho peor que 40, 60, 80, 120.
  const valores = datos.map((d) => d.v);
  const minY = Math.floor((Math.min(...valores) - 2) / 10) * 10;
  const maxY = Math.ceil((Math.max(...valores) + 2) / 10) * 10;

  const gradientId = `intra-${unit}-${date}`;

  return (
    <Card className="p-6">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink-soft">{title}</h2>
        <span className="text-xs text-ink-muted tabular-nums">{points.length} muestras</span>
      </div>
      {datos.length === 0 ? (
        <p className="py-20 text-center text-sm text-ink-muted">Sin muestras ese día.</p>
      ) : (
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={datos} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.28} />
                  <stop offset="100%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} stroke={CHART_CHROME.grid} />
              {/* Eje numérico, no de categorías: una pausa de 3 horas entre
                  muestras tiene que ocupar 3 horas de ancho, no un hueco de un
                  punto. */}
              <XAxis
                dataKey="ts"
                type="number"
                domain={[inicioDia, finDia]}
                ticks={marcas}
                tickLine={false}
                axisLine={false}
                tickMargin={10}
                tick={{ fontSize: 11, fill: CHART_CHROME.axis }}
                tickFormatter={(t: number) =>
                  `${String(new Date(t).getUTCHours()).padStart(2, "0")}:00`
                }
              />
              <YAxis
                domain={[minY, maxY]}
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
                content={<IntradayTooltip unit={unit} color={color} decimals={decimals} />}
              />
              <Area
                type="monotone"
                dataKey="v"
                stroke={color}
                strokeWidth={1.5}
                fill={`url(#${gradientId})`}
                dot={false}
                activeDot={{ r: 4, strokeWidth: 2, stroke: CHART_CHROME.dotRing }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}
