import { Link, useParams } from "react-router-dom";

import { useDayDetail, useSleepNight } from "../api/hooks";
import Hypnogram from "../components/Hypnogram";
import { HeartIcon, MoonIcon, PulseMonitorIcon } from "../components/Icons";
import IntradayChart from "../components/IntradayChart";
import StatCard from "../components/StatCard";
import { CHART_COLORS } from "../lib/chartTheme";
import { formatoDuracion } from "../lib/format";

/** "2026-08-31" -> "lunes, 31 de agosto de 2026".
 *
 *  Se formatea en UTC a propósito: `new Date("2026-08-31")` es medianoche UTC,
 *  y dejar que el navegador lo pase a su huso adelantaría o atrasaría el día
 *  entero según dónde se abra la web. */
function fechaLarga(iso: string): string {
  return new Intl.DateTimeFormat("es-ES", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(iso));
}

function numero(valor: number | null | undefined, sufijo: string, decimales = 0): string {
  if (valor == null) return "—";
  return `${valor.toLocaleString("es-ES", { maximumFractionDigits: decimales })} ${sufijo}`;
}

/** Flecha a otro día. Deshabilitada si no hay día con datos en esa dirección:
 *  navegar por días naturales llevaría a pantallas vacías. */
function Vecino({ fecha, children }: { fecha: string | null; children: React.ReactNode }) {
  const clases =
    "rounded-lg px-2.5 py-1.5 text-sm font-medium transition-colors " +
    (fecha
      ? "text-ink-soft hover:bg-raised hover:text-ink"
      : "cursor-not-allowed text-ink-muted/50");
  if (!fecha) {
    return (
      <span className={clases} aria-disabled="true">
        {children}
      </span>
    );
  }
  return (
    <Link to={`/dia/${fecha}`} className={clases}>
      {children}
    </Link>
  );
}

export default function DayDetail() {
  const { fecha } = useParams<{ fecha: string }>();
  const dia = useDayDetail(fecha);
  const noche = useSleepNight(fecha);

  if (dia.isLoading) {
    return <div className="h-40 animate-pulse rounded-card bg-surface" />;
  }
  if (dia.isError || !dia.data) {
    return (
      <div className="space-y-4">
        <Link to="/" className="text-sm text-ink-soft hover:text-ink">
          ← Volver al dashboard
        </Link>
        <p className="text-sm text-coral">No se pudieron cargar los datos de ese día.</p>
      </div>
    );
  }

  const { date, prev_date, next_date, summary } = dia.data;

  return (
    <div className="space-y-8">
      <div>
        <Link to="/" className="text-sm text-ink-soft hover:text-ink">
          ← Volver al dashboard
        </Link>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-3xl font-bold tracking-tight text-ink first-letter:uppercase">
            {fechaLarga(date)}
          </h1>
          <div className="flex items-center gap-1">
            <Vecino fecha={prev_date}>← Día anterior</Vecino>
            <Vecino fecha={next_date}>Día siguiente →</Vecino>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="FC en reposo"
          value={numero(summary.resting_heart_rate, "bpm")}
          icon={<HeartIcon />}
          tone="coral"
        />
        <StatCard
          label="FC media"
          value={numero(summary.heart_rate_avg, "bpm")}
          icon={<HeartIcon />}
        />
        <StatCard
          label="SpO₂ media"
          value={numero(summary.oxygen_saturation_avg, "%", 1)}
          icon={<PulseMonitorIcon />}
          tone="violet"
        />
        <StatCard
          label="Sueño"
          value={formatoDuracion(summary.sleep_minutes)}
          icon={<MoonIcon />}
          tone="cyan"
        />
      </div>

      <Hypnogram query={noche} title="Fases del sueño — esa noche" />

      <IntradayChart
        title="Frecuencia cardíaca a lo largo del día"
        date={date}
        points={dia.data.heart_rate}
        unit="bpm"
        color={CHART_COLORS.coral}
      />

      <IntradayChart
        title="SpO₂ a lo largo del día"
        date={date}
        points={dia.data.oxygen_saturation}
        unit="%"
        color={CHART_COLORS.violet}
      />
    </div>
  );
}
