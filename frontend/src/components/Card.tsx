import type { ReactNode } from "react";

/** Superficie base: esquinas redondeadas, sombra suave y sin bordes sólidos.
 *  Centraliza la elevación para no repetir las clases en cada tarjeta. */
export default function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`rounded-card bg-surface shadow-card ${className}`}>{children}</div>;
}
