import type { UseQueryResult } from "@tanstack/react-query";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { Serie } from "../api/types";

interface Props {
  query: UseQueryResult<Serie>;
  dataKey: "avg" | "minutes";
  unit: string;
}

export default function HealthChart({ query, dataKey, unit }: Props) {
  if (query.isLoading) return <p className="text-sm text-slate-500">Cargando gráfica…</p>;
  if (query.isError) return <p className="text-sm text-red-600">No se pudo cargar la gráfica.</p>;

  const points = query.data?.points ?? [];
  if (points.length === 0) {
    return <p className="text-sm text-slate-500">Sin datos en el rango.</p>;
  }

  return (
    <div className="h-64 w-full rounded-lg border bg-white p-3">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 5, right: 12, bottom: 5, left: -8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} width={64} unit={` ${unit}`} />
          <Tooltip />
          <Line type="monotone" dataKey={dataKey} stroke="#0f172a" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
