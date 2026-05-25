import { ShieldAlert } from "lucide-react";

import type { RiskSignal } from "../../../api/types";
import { Badge, EmptyState, Panel } from "../../../components/ui";
import { severityTone, statusLabel } from "../../../lib/risk";

/** Компактный risk register для быстрого сканирования. */
export function RisksPanel({ risks }: { risks: RiskSignal[] }) {
  return (
    <Panel
      title="Топ рисков"
      icon={<ShieldAlert className="size-4" />}
      action={risks.length > 0 ? <Badge>{risks.length}</Badge> : undefined}
    >
      {risks.length === 0 ? (
        <EmptyState message="Высоких рисков нет" />
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-500 dark:text-slate-400">
              <tr className="border-b border-slate-200 dark:border-slate-800">
                <th className="py-2 pr-4 font-semibold">Риск</th>
                <th className="px-3 py-2 font-semibold">Вероятность</th>
                <th className="px-3 py-2 font-semibold">Влияние</th>
                <th className="px-3 py-2 font-semibold">Владелец</th>
                <th className="px-3 py-2 font-semibold">Статус</th>
                <th className="py-2 pl-3 font-semibold">Проблема</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {risks.map((risk) => (
                <tr key={risk.id}>
                  <td className="py-3 pr-4 align-top">
                    <div className="font-semibold text-slate-950 dark:text-slate-50">
                      {risk.risk_type}
                    </div>
                    <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                      score {risk.score}
                    </div>
                  </td>
                  <td className="px-3 py-3 align-top tabular-nums text-slate-700 dark:text-slate-300">
                    {risk.probability}/5
                  </td>
                  <td className="px-3 py-3 align-top tabular-nums text-slate-700 dark:text-slate-300">
                    {risk.impact}/5
                  </td>
                  <td className="px-3 py-3 align-top text-slate-700 dark:text-slate-300">
                    {risk.owner_name}
                  </td>
                  <td className="px-3 py-3 align-top">
                    <Badge tone={severityTone(risk.status)}>
                      {statusLabel(risk.status)}
                    </Badge>
                  </td>
                  <td className="py-3 pl-3 align-top text-slate-600 dark:text-slate-300">
                    <span className="line-clamp-2">{risk.description}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
