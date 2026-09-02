import { Link, useNavigate } from "react-router-dom";

import { useLastDay, useSeries, useSleepNight } from "../api/hooks";
import HealthChart from "../components/HealthChart";
import Hypnogram from "../components/Hypnogram";
import { CalendarIcon, HeartIcon, MoonIcon, PulseMonitorIcon } from "../components/Icons";
import StatCard from "../components/StatCard";
import { CHART_COLORS } from "../lib/chartTheme";
import { formatoDuracion } from "../lib/format";

/** Los KPIs vienen ya calculados en `summary` (servicio del backend), no se
 *  derivan aquí: así la web y el bot no pueden divergir en el mismo número. */
function numero(valor: number | null | undefined, sufijo: string, decimales = 0): string {
  if (valor == null) return "—";
  return `${valor.toLocaleString("es-ES", { maximumFractionDigits: decimales })} ${sufijo}`;
}

export default function Dashboard() {
  const navigate = useNavigate();
  const lastDay = useLastDay();
  const sleepNight = useSleepNight();
  const heartRate = useSeries("heart_rate");
  const sleep = useSeries("sleep");

  const resumen = lastDay.data?.summary;

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold tracking-tight text-ink">Último día</h1>

      {lastDay.isLoading && (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-[92px] animate-pulse rounded-card bg-surface" />
          ))}
        </div>
      )}
      {lastDay.isError && <p className="text-sm text-coral">No se pudieron cargar los datos.</p>}
      {lastDay.data && resumen && (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {/* La fecha es el enlace natural al detalle del día que se está
              resumiendo arriba. */}
          <Link to={`/dia/${lastDay.data.date}`} className="block">
            <StatCard label="Fecha" value={lastDay.data.date} icon={<CalendarIcon />} compact />
          </Link>
          <StatCard
            label="FC en reposo"
            value={numero(resumen.resting_heart_rate, "bpm")}
            icon={<HeartIcon />}
            tone="coral"
          />
          <StatCard
            label="SpO₂ media"
            value={numero(resumen.oxygen_saturation_avg, "%", 1)}
            icon={<PulseMonitorIcon />}
            tone="violet"
          />
          <StatCard
            label="Sueño"
            value={formatoDuracion(resumen.sleep_minutes)}
            icon={<MoonIcon />}
            tone="cyan"
          />
        </div>
      )}

      <Hypnogram query={sleepNight} />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <HealthChart
          title="Frecuencia cardíaca — media diaria (últimos 30 días)"
          query={heartRate}
          dataKey="avg"
          unit="bpm"
          color={CHART_COLORS.coral}
          onSelectDay={(fecha) => navigate(`/dia/${fecha}`)}
        />
        <HealthChart
          title="Sueño — horas por noche (últimos 30 días)"
          query={sleep}
          dataKey="minutes"
          unit="h"
          color={CHART_COLORS.cyan}
          scale={60}
          decimals={1}
          onSelectDay={(fecha) => navigate(`/dia/${fecha}`)}
        />
      </div>
    </div>
  );
}
