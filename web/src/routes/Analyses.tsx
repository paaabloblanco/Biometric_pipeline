import { useAnalyses } from "../api/hooks";

export default function Analyses() {
  const { data, isLoading, isError } = useAnalyses(20);

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Histórico de análisis</h1>
      {isLoading && <p className="text-sm text-slate-500">Cargando…</p>}
      {isError && <p className="text-sm text-red-600">No se pudo cargar el histórico.</p>}
      {data && data.length === 0 && (
        <p className="text-sm text-slate-500">Todavía no hay análisis guardados.</p>
      )}
      <ul className="space-y-4">
        {data?.map((a) => (
          <li key={a.analysis_date} className="rounded-lg border bg-white p-4">
            <div className="mb-1 text-sm font-semibold">{a.analysis_date}</div>
            {a.user_instruction && (
              <div className="mb-2 text-xs italic text-slate-500">{a.user_instruction}</div>
            )}
            <p className="whitespace-pre-wrap text-sm text-slate-700">{a.analysis_text}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
