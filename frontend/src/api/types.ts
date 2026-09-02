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

/** Un item tal y como lo entendió Gemini, antes de guardarse.
 *
 *  Es a la vez la salida de POST /api/nevera/parse y la entrada de
 *  POST /api/nevera/items: el mismo objeto sale, se edita en pantalla y vuelve.
 *  Aquí `cantidad`/`unidad` van como las dijo el usuario (1 l), no en la unidad
 *  base (1000 ml): la conversión la hace el servicio al guardar. */
export interface ItemPropuesto {
  nombre: string;
  cantidad: string; // DecimalField: viaja como string
  unidad: string;
  categoria: string | null;
  fecha_caducidad: string | null; // ISO YYYY-MM-DD
  es_basico: boolean;
}

/** Un ingrediente de receta. Es a la vez salida (dentro de una receta
 *  propuesta) y entrada de POST /api/nevera/consume. */
export interface Ingrediente {
  nombre: string;
  cantidad: string; // DecimalField: viaja como string
  unidad: string;
}

export interface Receta {
  nombre: string;
  descripcion: string;
  ingredientes: Ingrediente[];
}

export interface SuggestionsRequest {
  /** Términos de `/comer sin pollo, huevos`. */
  exclude?: string[];
}

/** Respuesta de POST /api/nevera/suggestions. `not_found` son los términos de
 *  exclusión que no casaron con nada: casi siempre una errata, y hay que
 *  avisar o parece que la exclusión se ignoró. */
export interface Suggestions {
  recipes: Receta[];
  excluded: string[];
  not_found: string[];
  analysis_date: string | null;
}

/** Respuesta de POST /api/nevera/consume. Ninguno de los tres bloques es un
 *  error: los básicos no se descuentan a propósito y un "no encontrado" solo
 *  significa que ese ingrediente ya no estaba. */
export interface ConsumeResult {
  aplicados: { nombre: string; unidad: string; restante: number }[];
  basicos: { nombre: string; unidad: string }[];
  no_encontrados: { nombre: string; cantidad: string; unidad: string }[];
}

/** Una oferta que merece la pena, según Gemini.
 *
 *  `precio` es texto y no un número a propósito: llega tal cual aparece en la
 *  oferta ("5,99 zł", "2x1", "-30%"), y muchas promociones no son un precio. */
export interface Recomendacion {
  nombre: string;
  motivo: string;
  precio: string | null;
}

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
