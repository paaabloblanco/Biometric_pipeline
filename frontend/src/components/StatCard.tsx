import type { ReactNode } from "react";

import Card from "./Card";

/** Tono de la métrica. El color se elige aquí y no en el llamador para que la
 *  paleta viva en un solo sitio (la validada en index.css / lib/chartTheme.ts). */
export type StatTone = "neutral" | "coral" | "violet" | "cyan";

const tones: Record<StatTone, { icon: string; value: string }> = {
  neutral: { icon: "bg-raised text-ink-muted", value: "text-ink" },
  coral: { icon: "bg-coral/10 text-coral", value: "text-coral" },
  violet: { icon: "bg-violet/10 text-violet", value: "text-violet" },
  cyan: { icon: "bg-cyan/10 text-cyan", value: "text-cyan" },
};

interface Props {
  label: string;
  value: string | number;
  icon: ReactNode;
  tone?: StatTone;
  /** Valor largo no numérico (una fecha): baja un escalón para no competir
   *  visualmente con los KPI numéricos. */
  compact?: boolean;
}

export default function StatCard({ label, value, icon, tone = "neutral", compact }: Props) {
  const t = tones[tone];
  return (
    <Card className="flex items-center gap-4 p-5 transition-shadow hover:shadow-card-hover">
      <span className={`flex size-11 shrink-0 items-center justify-center rounded-2xl ${t.icon}`}>
        <span className="block size-[22px]">{icon}</span>
      </span>
      <div className="min-w-0">
        <div className="text-xs font-medium tracking-wide text-ink-muted uppercase">{label}</div>
        <div
          className={`truncate font-bold tabular-nums ${compact ? "text-xl" : "text-2xl"} ${t.value}`}
        >
          {value}
        </div>
      </div>
    </Card>
  );
}
