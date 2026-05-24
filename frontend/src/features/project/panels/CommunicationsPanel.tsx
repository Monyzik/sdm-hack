import { ArrowRight, MessageSquareWarning } from "lucide-react";

import type { CommunicationSignal } from "../../../api/types";
import { Badge, EmptyState, Panel } from "../../../components/ui";
import { formatDate, formatDays } from "../../../lib/format";
import { severityTone } from "../../../lib/risk";

/** Задержанные коммуникации между командами. */
export function CommunicationsPanel({
  communications,
}: {
  communications: CommunicationSignal[];
}) {
  return (
    <Panel
      title="Коммуникации"
      icon={<MessageSquareWarning className="size-4" />}
      action={
        communications.length > 0 ? (
          <Badge>{communications.length}</Badge>
        ) : undefined
      }
    >
      {communications.length === 0 ? (
        <EmptyState message="Задержек в коммуникациях нет" />
      ) : (
        <ul className="space-y-3">
          {communications.map((item) => (
            <li
              key={item.id}
              className="rounded-lg border border-slate-200 p-3 dark:border-slate-800"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex flex-wrap items-center gap-1.5 text-sm font-medium text-slate-900 dark:text-slate-100">
                  <span>{item.from_team}</span>
                  <ArrowRight
                    aria-hidden
                    className="size-3.5 text-slate-400 dark:text-slate-500"
                  />
                  <span>{item.to_team}</span>
                </div>
                <Badge tone="warning">{formatDays(item.delay_days)}</Badge>
              </div>
              <p className="line-clamp-2 mt-1 text-sm text-slate-600 dark:text-slate-300">
                {item.topic}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                <Badge tone={severityTone(item.importance)}>
                  {item.importance}
                </Badge>
                <Badge tone={severityTone(item.status)}>{item.status}</Badge>
                <span>
                  Ожидался ответ: {formatDate(item.expected_response_date)}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
