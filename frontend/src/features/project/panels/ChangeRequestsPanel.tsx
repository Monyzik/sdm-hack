import { FilePlus2 } from "lucide-react";

import type { ChangeRequestSignal } from "../../../api/types";
import { Badge, EmptyState, Panel } from "../../../components/ui";
import { formatDays, formatMoney } from "../../../lib/format";
import { severityTone } from "../../../lib/risk";

/** Открытые запросы на изменение с запрошенными дельтами бюджета и сроков. */
export function ChangeRequestsPanel({
  changeRequests,
}: {
  changeRequests: ChangeRequestSignal[];
}) {
  return (
    <Panel
      title="Запросы на изменение"
      icon={<FilePlus2 className="size-4" />}
      action={
        changeRequests.length > 0 ? (
          <Badge>{changeRequests.length}</Badge>
        ) : undefined
      }
    >
      {changeRequests.length === 0 ? (
        <EmptyState message="Открытых запросов нет" />
      ) : (
        <ul className="space-y-3">
          {changeRequests.map((request) => (
            <li
              key={request.id}
              className="rounded-lg border border-slate-200 p-3 dark:border-slate-800"
            >
              <div className="flex items-start justify-between gap-3">
                <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  {request.change_type}
                </span>
                <Badge tone={severityTone(request.status)}>
                  {request.status}
                </Badge>
              </div>
              <p className="line-clamp-2 mt-1 text-sm text-slate-600 dark:text-slate-300">
                {request.description}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                <span>Инициатор: {request.requested_by}</span>
                {request.requested_budget_delta !== 0 ? (
                  <Badge tone="warning">
                    {formatMoney(request.requested_budget_delta)}
                  </Badge>
                ) : null}
                {request.requested_timeline_delta_days !== 0 ? (
                  <Badge tone="warning">
                    {formatDays(request.requested_timeline_delta_days)}
                  </Badge>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
