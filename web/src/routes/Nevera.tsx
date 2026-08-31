import { useNevera } from "../api/hooks";

const DIAS_ALERTA = 3;

function diasHasta(fecha: string | null): number | null {
  if (!fecha) return null;
  const ms = new Date(`${fecha}T00:00:00`).getTime() - Date.now();
  return Math.ceil(ms / 86_400_000);
}

export default function Nevera() {
  const { data, isLoading, isError } = useNevera();

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Nevera</h1>
      {isLoading && <p className="text-sm text-slate-500">Cargando…</p>}
      {isError && <p className="text-sm text-red-600">No se pudo cargar la nevera.</p>}
      {data && data.length === 0 && <p className="text-sm text-slate-500">La nevera está vacía.</p>}

      {data && data.length > 0 && (
        <div className="overflow-x-auto rounded-lg border bg-white">
          <table className="w-full text-sm">
            <thead className="border-b bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2">Nombre</th>
                <th className="px-3 py-2">Cantidad</th>
                <th className="px-3 py-2">Categoría</th>
                <th className="px-3 py-2">Caduca</th>
              </tr>
            </thead>
            <tbody>
              {data.map((item) => {
                const dias = diasHasta(item.fecha_caducidad);
                const alerta = dias !== null && dias <= DIAS_ALERTA;
                return (
                  <tr key={item.id} className="border-b last:border-0">
                    <td className="px-3 py-2">{item.nombre}</td>
                    <td className="px-3 py-2">
                      {item.cantidad} {item.unidad}
                    </td>
                    <td className="px-3 py-2 text-slate-500">{item.categoria ?? "—"}</td>
                    <td
                      className={`px-3 py-2 ${
                        alerta ? "font-semibold text-red-600" : "text-slate-500"
                      }`}
                    >
                      {item.fecha_caducidad ?? "—"}
                      {alerta && dias !== null && (
                        <span className="ml-1">({dias <= 0 ? "caducado" : `${dias} d`})</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
