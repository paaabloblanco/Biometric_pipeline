import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./client";
import type {
  Analysis,
  DayDetail,
  ConsumeResult,
  Ingrediente,
  ItemPropuesto,
  LastDay,
  NeveraItem,
  NeveraItemUpdate,
  Recomendacion,
  Serie,
  SleepNight,
  Suggestions,
  SuggestionsRequest,
} from "./types";

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

/** `fecha` undefined = el último día con datos (lo que hace el dashboard). */
export function useSleepNight(fecha?: string) {
  return useQuery({
    queryKey: ["health", "sleep-night", fecha ?? "ultimo"],
    queryFn: () =>
      apiFetch<SleepNight>(
        fecha ? `/api/health/sleep-night?date=${fecha}` : "/api/health/sleep-night",
      ),
  });
}

export function useDayDetail(fecha?: string) {
  return useQuery({
    queryKey: ["health", "day", fecha ?? "ultimo"],
    queryFn: () => apiFetch<DayDetail>(fecha ? `/api/health/day?date=${fecha}` : "/api/health/day"),
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
    mutationFn: (id: number) => apiFetch<void>(`/api/nevera/items/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nevera"] }),
  });
}

// --- Lanzar un análisis nuevo (SDD-web fase 6) -----------------------------

/**
 * `POST /api/analyses`: dispara `run_analysis` con Gemini, igual que
 * `/analisis` en Telegram.
 *
 * Dos cosas la hacen distinta del resto de mutaciones de la app:
 *
 * - **Tarda 15-30 s.** La petición es síncrona: no responde hasta que Gemini
 *   contesta. Por eso la pantalla tiene que enseñar el estado de carga de
 *   forma prominente y no solo deshabilitar el botón.
 * - **Puede devolver 409.** Si el bot (otro proceso) ya está analizando, el
 *   `pg_advisory_lock` de `health_ai/locks.py` rechaza esta segunda llamada.
 *   No es un error del cliente: es el estado del sistema, y se cuenta como
 *   tal en la interfaz.
 *
 * Al terminar invalida el histórico: el análisis del día se sobrescribe, así
 * que la lista tiene que releerse en vez de parchearse con lo que enviamos.
 */
export function useLanzarAnalisis() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (instruction: string) =>
      apiFetch<Analysis>("/api/analyses", {
        method: "POST",
        body: JSON.stringify(instruction.trim() ? { instruction: instruction.trim() } : {}),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["analyses"] }),
  });
}

// --- Alta de nevera con IA, en dos pasos sin estado (SDD-web fase 6.b) ------
//
// El bot hace esto guardando lo entendido en `_pending_altas`, un diccionario
// en memoria de su proceso, y esperando un /confirmar. La web no puede ni
// quiere: cada petición es independiente. El estado intermedio —los items
// propuestos— lo tiene el cliente, en el estado de React, y vuelve entero en
// la segunda llamada. El servidor no guarda nada entre las dos.

/** Paso 1: texto libre -> items propuestos. No escribe en la BD. */
export function useParseCompra() {
  return useMutation({
    mutationFn: (text: string) =>
      apiFetch<ItemPropuesto[]>("/api/nevera/parse", {
        method: "POST",
        body: JSON.stringify({ text }),
      }),
  });
}

/** Paso 2: items ya confirmados (y editados) -> filas en la nevera. */
export function useAltaItems() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (items: ItemPropuesto[]) =>
      apiFetch<NeveraItem[]>("/api/nevera/items", {
        method: "POST",
        body: JSON.stringify({ items }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nevera"] }),
  });
}

// --- Sugerencias de comida y consumo (SDD-web fase 6.c) --------------------
//
// Mismo patrón sin estado que el alta: `suggestions` no guarda las recetas en
// ninguna parte, así que al confirmar se mandan los ingredientes y no un
// "número de receta" que el servidor tendría que recordar.

/** Paso 1: inventario + último análisis -> recetas. No escribe en la BD. */
export function useSugerencias() {
  return useMutation({
    mutationFn: (body: SuggestionsRequest) =>
      apiFetch<Suggestions>("/api/nevera/suggestions", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  });
}

/** Paso 2: descuenta del inventario los ingredientes de la comida hecha. */
export function useConsumir() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ingredients: Ingrediente[]) =>
      apiFetch<ConsumeResult>("/api/nevera/consume", {
        method: "POST",
        body: JSON.stringify({ ingredients }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nevera"] }),
  });
}

// --- Ofertas del supermercado (SDD-web fase 6.d) ---------------------------

/** Cruza el texto de la gazetka con la nevera. No escribe nada. */
export function useAnalizarOfertas() {
  return useMutation({
    mutationFn: (text: string) =>
      apiFetch<Recomendacion[]>("/api/ofertas/analyze", {
        method: "POST",
        body: JSON.stringify({ text }),
      }),
  });
}
