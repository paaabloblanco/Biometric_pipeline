import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "./client";
import type { Analysis, LastDay, NeveraItem, Serie } from "./types";

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
