/** Minutos -> "8h 20m". Devuelve "—" si no hay dato. */
export function formatoDuracion(minutos: number | null | undefined): string {
  if (minutos == null) return "—";
  const h = Math.floor(minutos / 60);
  const m = minutos % 60;
  return h === 0 ? `${m}m` : `${h}h ${String(m).padStart(2, "0")}m`;
}

/** Instante ISO con offset -> Date con la hora local del *servidor*.
 *
 *  `new Date(iso)` convertiría a la zona del navegador: la misma noche se
 *  dibujaría desplazada al abrir la web desde otro huso. Quitando el offset y
 *  marcándolo como UTC, la hora de pared que guardó el backend se conserva y
 *  se lee con los getters `getUTC*`.
 */
export function horaLocalServidor(iso: string): Date {
  return new Date(`${iso.slice(0, 19)}Z`);
}

/** "2026-08-31T01:24:00+02:00" -> "01:24". */
export function soloHora(iso: string): string {
  return iso.slice(11, 16);
}
