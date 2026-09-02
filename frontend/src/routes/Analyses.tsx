import Card from "../components/Card";
import { useAnalyses } from "../api/hooks";

export default function Analyses() {
  const { data, isLoading, isError } = useAnalyses(20);

  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold tracking-tight text-ink">Histórico de análisis</h1>
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
