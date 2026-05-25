import { Activity } from "lucide-react";

import { EmptyState, Panel } from "../../../components/ui";

/** Доказательства, почему проект требует внимания. */
export function KeySignalsPanel({ signals }: { signals: string[] }) {
  return (
    <Panel title="Почему это критично" icon={<Activity className="size-4" />}>
      {signals.length === 0 ? (
        <EmptyState message="Сигналов нет" />
      ) : (
        <ul className="space-y-1.5">
          {signals.map((signal, index) => (
            <li
              key={`${index}-${signal}`}
              className="flex gap-2 px-1 py-1 text-sm text-slate-700 dark:text-slate-300"
            >
              <span
                aria-hidden
                className="mt-2 size-1.5 shrink-0 rounded-full bg-slate-400 dark:bg-slate-500"
              />
              <span>{signal}</span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
