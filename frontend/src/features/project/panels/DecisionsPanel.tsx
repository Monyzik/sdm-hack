import { FileClock } from "lucide-react";

import type { DecisionSignal } from "../../../api/types";
import { Badge, EmptyState, Panel } from "../../../components/ui";
import { formatDate } from "../../../lib/format";
import { severityTone } from "../../../lib/risk";

/** Ожидающие управленческие решения. */
export function DecisionsPanel({ decisions }: { decisions: DecisionSignal[] }) {
  return (
    <Panel
      title="Ожидают решения"
      icon={<FileClock className="size-4" />}
      action={
        decisions.length > 0 ? <Badge>{decisions.length}</Badge> : undefined
      }
    >
      {decisions.length === 0 ? (
        <EmptyState message="Открытых решений нет" />
      ) : (
        <ul className="space-y-3">
          {decisions.map((decision) => (
            <li
              key={decision.id}
              className="rounded-lg border border-slate-200 p-3 dark:border-slate-800"
            >
              <div className="flex items-start justify-between gap-3">
                <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  {decision.decision_type}
                </span>
                <Badge tone={severityTone(decision.status)}>
                  {decision.status}
                </Badge>
              </div>
              <p className="line-clamp-2 mt-1 text-sm text-slate-600 dark:text-slate-300">
                {decision.description}
              </p>
              <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                {decision.decision_owner} · до{" "}
                {formatDate(decision.decision_date)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
