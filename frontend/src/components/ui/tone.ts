import type { Tone } from "../../lib/risk";

/**
 * Единые наборы Tailwind-классов для каждого семантического тона.
 * Все цветные элементы интерфейса берут цвета отсюда, что гарантирует
 * визуальную согласованность.
 */
export const surfaceToneClass: Record<Tone, string> = {
  neutral:
    "border-slate-200 bg-white text-slate-900 dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-100",
  danger:
    "border-rose-200 bg-rose-50 text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-100",
  warning:
    "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-100",
  success:
    "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-100",
  info: "border-sky-200 bg-sky-50 text-sky-900 dark:border-sky-900/60 dark:bg-sky-950/30 dark:text-sky-100",
};

export const badgeToneClass: Record<Tone, string> = {
  neutral: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  danger: "bg-rose-100 text-rose-700 dark:bg-rose-950/70 dark:text-rose-300",
  warning:
    "bg-amber-100 text-amber-800 dark:bg-amber-950/70 dark:text-amber-300",
  success:
    "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/70 dark:text-emerald-300",
  info: "bg-sky-100 text-sky-700 dark:bg-sky-950/70 dark:text-sky-300",
};

export const accentTextClass: Record<Tone, string> = {
  neutral: "text-slate-900 dark:text-slate-100",
  danger: "text-rose-700 dark:text-rose-300",
  warning: "text-amber-700 dark:text-amber-300",
  success: "text-emerald-700 dark:text-emerald-300",
  info: "text-sky-700 dark:text-sky-300",
};
