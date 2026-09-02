// Formas que devuelve la API (api/serializers.py y api/views.py del backend).

export interface NeveraItem {
  id: number;
  nombre: string;
  cantidad: string; // DecimalField serializado como string
  unidad: string;
  categoria: string | null;
  fecha_caducidad: string | null; // ISO YYYY-MM-DD
  fecha_añadido: string; // ISO datetime
  origen: string;
  es_basico: boolean;
}

/** Cuerpo de PATCH /api/nevera/items/{id}: parcial, solo lo que cambia. */
export type NeveraItemUpdate = Partial<{
  nombre: string;
  cantidad: string;
  unidad: string;
  categoria: string | null;
  fecha_caducidad: string | null;
  es_basico: boolean;
}>;

export interface Analysis {
  analysis_date: string;
  user_instruction: string | null;
  analysis_text: string;
}

export interface SeriePunto {
  date: string;
  min?: number | null;
  max?: number | null;
  avg?: number | null;
  count?: number;
  minutes?: number;
}

export interface Serie {
  metric: string;
  points: SeriePunto[];
}

/** KPIs ya calculados por el backend (`build_day_summary`).
 *  No se recalculan aquí a propósito: si la SPA promediase por su cuenta, la
 *  web y el bot podrían enseñar números distintos del mismo dato. */
export interface DaySummary {
  heart_rate_avg: number | null;
  heart_rate_min: number | null;
  heart_rate_max: number | null;
  resting_heart_rate: number | null;
  oxygen_saturation_avg: number | null;
  oxygen_saturation_min: number | null;
  sleep_minutes: number | null;
}

export interface LastDay {
  date: string;
  heart_rate_samples: unknown[];
  oxygen_saturation_samples: unknown[];
  resting_heart_rate_samples: unknown[];
  sleep_stages: unknown[];
  summary: DaySummary;
}

/** Una muestra dentro del día: instante local (ISO con offset) y valor. */
export interface IntradayPoint {
  t: string;
  v: number;
}

/** Respuesta de GET /api/health/day: la página de un día concreto.
 *  `prev_date`/`next_date` son días CON datos, no el día natural anterior. */
export interface DayDetail {
  date: string;
  prev_date: string | null;
  next_date: string | null;
  summary: DaySummary;
  heart_rate: IntradayPoint[];
  oxygen_saturation: IntradayPoint[];
}

/** Nombres de fase que devuelve la API (`SLEEP_STAGE_NAMES` del backend). */
export type SleepStageName =
  | "profundo"
  | "rem"
  | "ligero"
  | "despierto"
  | "despierto_en_cama"
  | "fuera_de_cama"
  | "dormido"
  | "desconocido";

export interface SleepSegment {
  stage: SleepStageName;
  start: string; // ISO con offset local
  end: string;
  minutes: number;
}

/** Respuesta de GET /api/health/sleep-night: la noche para el hipnograma. */
export interface SleepNight {
  date: string;
  start: string | null;
  end: string | null;
  total_minutes: number;
  segments: SleepSegment[];
  totals: { stage: SleepStageName; minutes: number }[];
}
