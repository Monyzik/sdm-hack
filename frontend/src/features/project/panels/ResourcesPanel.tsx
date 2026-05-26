import { UsersRound } from "lucide-react";

import type { ResourceLoadSignal } from "../../../api/types";
import { Badge, EmptyState, Panel } from "../../../components/ui";
import { HorizontalBarChart } from "../../../components/ui/Charts";
import { formatPercent } from "../../../lib/format";

/** Перегруженные ресурсы: суммарная аллокация и часы по проекту/всего. */
export function ResourcesPanel({
  resources,
}: {
  resources: ResourceLoadSignal[];
}) {
  return (
    <Panel
      title="Перегрузка ресурсов"
      icon={<UsersRound className="size-4" />}
      action={
        resources.length > 0 ? <Badge>{resources.length}</Badge> : undefined
      }
    >
      {resources.length === 0 ? (
        <EmptyState message="Перегруженных ресурсов нет" />
      ) : (
        <div className="space-y-4">
          <HorizontalBarChart
            data={resources.map((resource) => ({
              label: resource.full_name,
              value: resource.total_allocation_percent,
              tone:
                resource.total_allocation_percent >= 120
                  ? "danger"
                  : "warning",
              hint: `${resource.role} · ${resource.team} · ${resource.total_actual_hours_per_week} ч/нед`,
            }))}
          />
          <ul className="space-y-3">
            {resources.map((resource) => (
              <li
                key={resource.resource_id}
                className="rounded-lg border border-slate-200 p-3 dark:border-slate-800"
              >
                <div className="flex items-start justify-between gap-3">
                  <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                    {resource.full_name}
                  </span>
                  <Badge tone="warning">
                    {formatPercent(resource.total_allocation_percent)}
                  </Badge>
                </div>
                <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                  {resource.role} · {resource.team}
                </p>
                <p className="mt-1 text-xs text-slate-500 tabular-nums dark:text-slate-400">
                  {resource.total_actual_hours_per_week} ч/нед суммарно (из них{" "}
                  {resource.project_actual_hours_per_week} ч на проекте) при норме{" "}
                  {resource.available_hours_per_week} ч
                </p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Panel>
  );
}
