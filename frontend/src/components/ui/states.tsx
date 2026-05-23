import { Inbox, Loader2, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

/** Центрированный спиннер для состояния загрузки крупного блока. */
export function LoadingState({ label = "Загрузка…" }: { label?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex h-72 flex-col items-center justify-center gap-3 text-slate-500 dark:text-slate-400"
    >
      <Loader2 aria-hidden className="size-7 animate-spin" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

/** Сообщение об ошибке с возможностью повторить запрос. */
export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center gap-3 rounded-xl border border-rose-200 bg-rose-50 p-8 text-center text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-100"
    >
      <TriangleAlert aria-hidden className="size-7" />
      <p className="max-w-md text-sm">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-lg border border-rose-300 bg-white px-3 py-1.5 text-sm font-medium text-rose-700 transition hover:bg-rose-100 dark:border-rose-800 dark:bg-slate-950 dark:text-rose-200 dark:hover:bg-rose-950/40"
        >
          Повторить
        </button>
      ) : null}
    </div>
  );
}

interface EmptyStateProps {
  /** Краткое сообщение об отсутствии данных. */
  message: string;
  icon?: ReactNode;
}

/** Аккуратное «пусто» вместо схлопнувшегося пустого блока. */
export function EmptyState({ message, icon }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-8 text-center text-slate-400 dark:text-slate-500">
      <span aria-hidden>{icon ?? <Inbox className="size-6" />}</span>
      <p className="text-sm">{message}</p>
    </div>
  );
}
