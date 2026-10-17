/**
 * Colores de las gráficas, en hexadecimal.
 *
 * ¿Por qué duplicar aquí lo que ya está en `index.css`? Recharts pinta SVG y
 * escribe los colores como atributos de presentación (`stroke`, `fill`), no
 * como clases: no entiende utilidades de Tailwind, y `var(--color-cyan)` en un
 * atributo SVG no resuelve de forma fiable en todos los navegadores. Así que
 * los valores viajan como props en hex.
 *
 * La regla para que la duplicación no se descuadre: este fichero es el ÚNICO
 * sitio del código con hex de gráfica, y cada constante apunta al token de
 * `index.css` del que sale. Si cambias la paleta, cambias los dos y revalidas.
 */

/** Series de datos. Un color por métrica, fijo: el mismo tono significa
 *  siempre lo mismo en toda la app (la FC es coral en el dashboard y en el
 *  detalle del día). Nunca se asignan por orden ni se rotan. */
export const CHART_COLORS = {
  coral: "#e5484d", // --color-coral · frecuencia cardíaca
  cyan: "#17a0c4", // --color-cyan · sueño
  violet: "#9b51c9", // --color-violet · SpO2
} as const;

/** Fases del sueño, en orden de profundidad (el orden de filas del
 *  hipnograma, que es el que se validó). */
export const SLEEP_COLORS = {
  awake: "#c98500", // --color-sleep-awake
  rem: "#9b51c9", // --color-sleep-rem
  light: "#17a0c4", // --color-sleep-light
  deep: "#5f6ce8", // --color-sleep-deep
  unknown: "#7d8b9c", // --color-ink-muted · neutro deliberado, no es una serie
} as const;

/** El "cromo" de la gráfica: todo lo que no son datos. Recesivo por
 *  definición — si la rejilla compite con la línea, la gráfica está mal. */
export const CHART_CHROME = {
  /** Rejilla horizontal. --color-line */
  grid: "#2a3542",
  /** Texto de los ejes. --color-ink-muted */
  axis: "#7d8b9c",
  /** Línea vertical que sigue al cursor. Un paso por encima de la rejilla. */
  cursor: "#3a4757",
  /** Aro del punto activo: es el color de la tarjeta, no blanco, para que
   *  recorte el marcador contra el fondo en vez de brillar. --color-surface */
  dotRing: "#182029",
} as const;
