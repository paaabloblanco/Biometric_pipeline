import { useLastDay, useSeries } from "../api/hooks";
import HealthChart from "../components/HealthChart";

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border bg-white p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}

export default function Dashboard() {
  const lastDay = useLastDay();
  const heartRate = useSeries("heart_rate");
  const sleep = useSeries("sleep");

  return (
    <div className="space-y-8">
      <section>
        <h1 className="mb-3 text-lg font-semibold">Último día</h1>
        {lastDay.isLoading && <p className="text-sm text-slate-500">Cargando…</p>}
        {lastDay.isError && <p className="text-sm text-red-600">No se pudieron cargar los datos.</p>}
        {lastDay.data && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Fecha" value={lastDay.data.date} />
            <Stat label="Muestras FC" value={lastDay.data.heart_rate_samples.length} />
            <Stat label="Muestras SpO₂" value={lastDay.data.oxygen_saturation_samples.length} />
            <Stat label="Fases de sueño" value={lastDay.data.sleep_stages.length} />
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-700">
          Frecuencia cardíaca — media diaria (últimos 30 días)
        </h2>
        <HealthChart query={heartRate} dataKey="avg" unit="bpm" />
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-700">
          Sueño — minutos por día (últimos 30 días)
        </h2>
        <HealthChart query={sleep} dataKey="minutes" unit="min" />
      </section>
    </div>
  );
}
