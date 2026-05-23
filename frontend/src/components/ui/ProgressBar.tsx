import type { Tone } from "../../lib/risk";

const fillToneClass: Record<Tone, string> = {
  neutral: "bg-slate-700",
  danger: "bg-rose-500",
  warning: "bg-amber-500",
  success: "bg-emerald-500",
  info: "bg-sky-500",
};

interface ProgressBarProps {
  value: number;
  max?: number;
  tone?: Tone;
  /** Доступная подпись для скринридера (например, «Готовность 64%»). */
  ariaLabel: string;
}

/**
 * Полоса прогресса с корректной семантикой `role="progressbar"` и
 * aria-атрибутами вместо нативного `<progress>` — так мы полностью управляем
 * цветом и доступностью.
 */
export function ProgressBar({
  value,
  max = 100,
  tone = "neutral",
  ariaLabel,
}: ProgressBarProps) {
  const percent = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div
      role="progressbar"
      aria-label={ariaLabel}
      aria-valuenow={Math.round(value)}
      aria-valuemin={0}
      aria-valuemax={max}
      className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"
    >
      <div
        className={`h-full rounded-full transition-[width] ${fillToneClass[tone]}`}
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}
