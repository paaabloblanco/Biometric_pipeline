import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./client";
import type { Analysis, LastDay, NeveraItem, NeveraItemUpdate, Serie } from "./types";

export function useLastDay() {
  return useQuery({
    queryKey: ["health", "last-day"],
    queryFn: () => apiFetch<LastDay>("/api/health/last-day"),
  });
}

export function useSeries(metric: string) {
  return useQuery({
    queryKey: ["health", "series", metric],
    queryFn: () => apiFetch<Serie>(`/api/health/series?metric=${encodeURIComponent(metric)}`),
  });
}

export function useAnalyses(limit = 10) {
  return useQuery({
    queryKey: ["analyses", limit],
    queryFn: () => apiFetch<Analysis[]>(`/api/analyses?limit=${limit}`),
  });
}

export function useNevera() {
  return useQuery({
    queryKey: ["nevera"],
    queryFn: () => apiFetch<NeveraItem[]>("/api/nevera"),
  });
}

// --- Escrituras sobre la nevera (SDD-web fase 4) ---------------------------
//
// Las dos mutaciones invalidan la query "nevera" al terminar. Invalidar en vez
// de parchear la caché a mano deja que el servidor tenga la última palabra:
// `edit_item` normaliza el nombre y convierte la unidad, así que lo guardado
// casi nunca es literalmente lo que enviamos. Cuesta una petición extra y a
// cambio la tabla nunca miente.

export function useEditarItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, cambios }: { id: number; cambios: NeveraItemUpdate }) =>
      apiFetch<NeveraItem>(`/api/nevera/items/${id}`, {
        method: "PATCH",
        body: JSON.stringify(cambios),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nevera"] }),
  });
}

export function useBorrarItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<void>(`/api/nevera/items/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nevera"] }),
  });
}
