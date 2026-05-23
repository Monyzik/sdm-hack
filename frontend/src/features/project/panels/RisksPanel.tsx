import { ShieldAlert } from "lucide-react";

import type { RiskSignal } from "../../../api/types";
import { Badge, EmptyState, Panel } from "../../../components/ui";
import { severityTone } from "../../../lib/risk";

/** Топ рисков с вероятностью, импактом и итоговым score. */
export function RisksPanel({ risks }: { risks: RiskSignal[] }) {
  return (
    <Panel
      title="Риски"
      icon={<ShieldAlert className="size-4" />}
      action={risks.length > 0 ? <Badge>{risks.length}</Badge> : undefined}
    >
      {risks.length === 0 ? (
        <EmptyState message="Высоких рисков нет" />
      ) : (
        <ul className="space-y-3">
          {risks.map((risk) => (
            <li
              key={risk.id}
              className="rounded-lg border border-slate-200 p-3 dark:border-slate-800"
            >
              <div className="flex items-start justify-between gap-3">
                <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  {risk.risk_type}
                </span>
                <Badge tone="danger" title="Вероятность × Влияние">
                  score {risk.score}
                </Badge>
              </div>
              <p className="line-clamp-2 mt-1 text-sm text-slate-600 dark:text-slate-300">
                {risk.description}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                <Badge tone={severityTone(risk.status)}>{risk.status}</Badge>
                <span>Вероятность {risk.probability}/5</span>
                <span>Влияние {risk.impact}/5</span>
                <span>· {risk.owner_name}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
