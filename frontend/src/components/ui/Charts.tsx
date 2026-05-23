import type { Tone } from "../../lib/risk";

const toneStroke: Record<Tone, string> = {
  neutral: "stroke-slate-700 dark:stroke-slate-300",
  danger: "stroke-rose-500 dark:stroke-rose-400",
  warning: "stroke-amber-500 dark:stroke-amber-400",
  success: "stroke-emerald-500 dark:stroke-emerald-400",
  info: "stroke-sky-500 dark:stroke-sky-400",
};

const toneFill: Record<Tone, string> = {
  neutral: "bg-slate-700 dark:bg-slate-300",
  danger: "bg-rose-500 dark:bg-rose-400",
  warning: "bg-amber-500 dark:bg-amber-400",
  success: "bg-emerald-500 dark:bg-emerald-400",
  info: "bg-sky-500 dark:bg-sky-400",
};

interface CircularGaugeProps {
  value: number;
  label: string;
  tone?: Tone;
}

export function CircularGauge({
  value,
  label,
  tone = "neutral",
}: CircularGaugeProps) {
  const percent = Math.max(0, Math.min(100, value));
  const radius = 34;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percent / 100) * circumference;

  return (
    <div className="grid place-items-center">
      <div className="relative size-24">
        <svg aria-hidden viewBox="0 0 88 88" className="-rotate-90">
          <circle
            cx="44"
            cy="44"
            r={radius}
            className="fill-none stroke-slate-100 dark:stroke-slate-800"
            strokeWidth="9"
          />
          <circle
            cx="44"
            cy="44"
            r={radius}
            className={`fill-none ${toneStroke[tone]}`}
            strokeLinecap="round"
            strokeWidth="9"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
          />
        </svg>
        <div className="absolute inset-0 grid place-items-center">
          <span className="text-2xl font-semibold tabular-nums text-slate-950 dark:text-slate-50">
            {Math.round(value)}
          </span>
        </div>
      </div>
      <p className="mt-1 text-xs font-medium text-slate-500 dark:text-slate-400">
        {label}
      </p>
    </div>
  );
}

interface MiniBarProps {
  label: string;
  value: number;
  tone?: Tone;
}

export function MiniBar({ label, value, tone = "neutral" }: MiniBarProps) {
  const percent = Math.max(0, Math.min(100, value));

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-3 text-xs">
        <span className="font-medium text-slate-600 dark:text-slate-300">
          {label}
        </span>
        <span className="tabular-nums text-slate-500 dark:text-slate-400">
          {Math.round(value)}%
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        <div
          className={`h-full rounded-full ${toneFill[tone]}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
