import { Activity } from "lucide-react";

import { EmptyState, Panel } from "../../../components/ui";

/** Список ключевых текстовых сигналов, сформированных backend. */
export function KeySignalsPanel({ signals }: { signals: string[] }) {
  return (
    <Panel title="Ключевые сигналы" icon={<Activity className="size-4" />}>
      {signals.length === 0 ? (
        <EmptyState message="Сигналов нет" />
      ) : (
        <ul className="space-y-2">
          {signals.map((signal, index) => (
            <li
              key={`${index}-${signal}`}
              className="flex gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300"
            >
              <span
                aria-hidden
                className="mt-1.5 size-1.5 shrink-0 rounded-full bg-slate-400 dark:bg-slate-500"
              />
              <span>{signal}</span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
