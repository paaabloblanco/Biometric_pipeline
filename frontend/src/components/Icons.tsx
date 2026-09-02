// Iconos como SVG inline: cuatro trazos no justifican una dependencia
// (lucide-react, react-icons). `currentColor` hace que hereden el color del
// contenedor, así el color vive en Tailwind y no duplicado dentro del SVG.

type IconProps = { className?: string };

const base = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function CalendarIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className} aria-hidden="true">
      <rect x="3" y="5" width="18" height="16" rx="3" />
      <path d="M3 10h18M8 3v4M16 3v4" />
    </svg>
  );
}

export function HeartIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className} aria-hidden="true">
      <path d="M20.4 5.9a5 5 0 0 0-7.1 0L12 7.2l-1.3-1.3a5 5 0 1 0-7.1 7.1l8.4 8.4 8.4-8.4a5 5 0 0 0 0-7.1Z" />
    </svg>
  );
}

export function PulseMonitorIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className} aria-hidden="true">
      <rect x="2.5" y="4" width="19" height="13" rx="2.5" />
      <path d="M6 11h2.5l1.5-3 2 6 1.5-3H18M9 21h6M12 17v4" />
    </svg>
  );
}

export function MoonIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className} aria-hidden="true">
      <path d="M20 14.5A8.2 8.2 0 0 1 9.5 4a8.3 8.3 0 1 0 10.5 10.5Z" />
      <path d="M18 3.5v3M16.5 5h3" />
    </svg>
  );
}
