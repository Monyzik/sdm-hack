import type { ReactNode } from "react";

import type { Tone } from "../../lib/risk";
import { badgeToneClass } from "./tone";

interface BadgeProps {
  children: ReactNode;
  tone?: Tone;
  title?: string;
}

/** Компактный цветной бейдж для статусов, критичности и числовых сигналов. */
export function Badge({ children, tone = "neutral", title }: BadgeProps) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ${badgeToneClass[tone]}`}
    >
      {children}
    </span>
  );
}
