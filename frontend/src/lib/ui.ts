/** Clases de Tailwind compartidas por los formularios de la app.
 *
 *  Viven aquí y no repetidas en cada pantalla porque la nevera tiene ya dos
 *  formularios (editar una fila y dar de alta con IA) que deben parecer el
 *  mismo formulario. Ningún color literal: todo sale de los tokens de
 *  `index.css`. */

/** Campo de texto sobre fondo oscuro: el relleno sube un escalón de elevación
 *  (--color-raised) en vez de bajar, que es como se lee "hueco" en oscuro. */
export const INPUT =
  "w-full rounded border border-line bg-raised px-2 py-1 text-sm text-ink " +
  "focus:border-cyan focus:outline-none";

/** Botón secundario (Editar, Cancelar, No): contorno, sin relleno. */
export const BOTON = "rounded border border-line px-2 py-1 text-xs text-ink-soft hover:text-ink";

/** Botón principal de una acción (Guardar, Confirmar): relleno de acento. */
export const BOTON_PRIMARIO =
  "rounded bg-cyan px-3 py-1.5 text-xs font-semibold text-navbar disabled:opacity-50";
