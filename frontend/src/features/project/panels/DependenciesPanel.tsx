import { GitBranch } from "lucide-react";

import type { DependencySignal } from "../../../api/types";
import { Badge, EmptyState, Panel } from "../../../components/ui";
import { formatDate, formatDays } from "../../../lib/format";
import { severityTone } from "../../../lib/risk";

/** Рискованные внешние зависимости проекта. */
export function DependenciesPanel({
  dependencies,
}: {
  dependencies: DependencySignal[];
}) {
  return (
    <Panel
      title="Зависимости"
      icon={<GitBranch className="size-4" />}
      action={
        dependencies.length > 0 ? (
          <Badge>{dependencies.length}</Badge>
        ) : undefined
      }
    >
      {dependencies.length === 0 ? (
        <EmptyState message="Рискованных зависимостей нет" />
      ) : (
        <ul className="space-y-3">
          {dependencies.map((dependency) => (
            <li
              key={dependency.id}
              className="rounded-lg border border-slate-200 p-3 dark:border-slate-800"
            >
              <div className="flex items-start justify-between gap-3">
                <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  {dependency.depends_on}
                </span>
                {dependency.delay_days > 0 ? (
                  <Badge tone="danger">
                    {formatDays(dependency.delay_days)}
                  </Badge>
                ) : null}
              </div>
              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                {dependency.dependency_type} · {dependency.owner_team}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                <Badge tone={severityTone(dependency.criticality)}>
                  {dependency.criticality}
                </Badge>
                <Badge tone={severityTone(dependency.status)}>
                  {dependency.status}
                </Badge>
                <span>Ожидается: {formatDate(dependency.expected_date)}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
