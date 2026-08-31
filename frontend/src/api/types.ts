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

export interface LastDay {
  date: string;
  heart_rate_samples: unknown[];
  oxygen_saturation_samples: unknown[];
  resting_heart_rate_samples: unknown[];
  sleep_stages: unknown[];
}
