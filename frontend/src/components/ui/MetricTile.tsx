import type { ReactNode } from "react";

import type { Tone } from "../../lib/risk";
import { surfaceToneClass } from "./tone";

interface MetricTileProps {
  label: string;
  value: string | number;
  icon?: ReactNode;
  tone?: Tone;
  /** Необязательная подпись под значением (например, контекст метрики). */
  hint?: string;
}

/** Плитка ключевой метрики: подпись, иконка и крупное значение. */
export function MetricTile({
  label,
  value,
  icon,
  tone = "neutral",
  hint,
}: MetricTileProps) {
  return (
    <div className={`rounded-xl border p-3 ${surfaceToneClass[tone]}`}>
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-medium uppercase text-slate-500 dark:text-slate-400">
          {label}
        </span>
        {icon ? (
          <span aria-hidden className="opacity-70">
            {icon}
          </span>
        ) : null}
      </div>
      <div className="mt-2 text-2xl font-semibold tabular-nums">{value}</div>
      {hint ? (
        <div className="mt-1 truncate text-xs text-slate-500 dark:text-slate-400">
          {hint}
        </div>
      ) : null}
    </div>
  );
}
