import { Banknote } from "lucide-react";

import type { BudgetSummary } from "../../../api/types";
import { EmptyState, MiniBar, Panel } from "../../../components/ui";
import { accentTextClass } from "../../../components/ui/tone";
import { formatMoney, formatPercent } from "../../../lib/format";
import type { Tone } from "../../../lib/risk";

interface BudgetRowProps {
  label: string;
  value: string;
  tone?: Tone;
}

function BudgetRow({ label, value, tone = "neutral" }: BudgetRowProps) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-slate-100 py-2 last:border-b-0 last:pb-0 dark:border-slate-800">
      <dt className="text-sm text-slate-500 dark:text-slate-400">{label}</dt>
      <dd
        className={`text-sm font-semibold tabular-nums ${accentTextClass[tone]}`}
      >
        {value}
      </dd>
    </div>
  );
}

/** Сводка по бюджету: план, прогноз, отклонение и оба варианта ROI. */
export function BudgetPanel({ budget }: { budget: BudgetSummary | null }) {
  return (
    <Panel title="Бюджет" icon={<Banknote className="size-4" />}>
      {budget ? (
        <div>
          <div className="mb-4 space-y-3">
            <MiniBar
              label="Исполнено бюджета"
              value={
                (budget.actual_spent / Math.max(budget.planned_budget, 1)) * 100
              }
              tone={
                budget.actual_spent > budget.planned_budget ? "danger" : "info"
              }
            />
            <MiniBar
              label="Прогноз к плану"
              value={
                (budget.forecast_total_spent /
                  Math.max(budget.planned_budget, 1)) *
                100
              }
              tone={
                budget.forecast_total_spent > budget.planned_budget
                  ? "warning"
                  : "success"
              }
            />
          </div>
          <dl>
            <BudgetRow
              label="План"
              value={formatMoney(budget.planned_budget, budget.currency)}
            />
            <BudgetRow
              label="Факт"
              value={formatMoney(budget.actual_spent, budget.currency)}
            />
            <BudgetRow
              label="Прогноз"
              value={formatMoney(budget.forecast_total_spent, budget.currency)}
            />
            <BudgetRow
              label="Отклонение"
              value={formatPercent(budget.budget_deviation_percent)}
              tone={budget.budget_deviation_percent > 0 ? "danger" : "success"}
            />
            <BudgetRow
              label="ROI"
              value={formatPercent(budget.roi_percent, true)}
              tone={budget.roi_percent < 0 ? "danger" : "success"}
            />
            <BudgetRow
              label="Risk-adjusted ROI"
              value={formatPercent(budget.risk_adjusted_roi_percent, true)}
              tone={budget.risk_adjusted_roi_percent < 0 ? "danger" : "success"}
            />
          </dl>
        </div>
      ) : (
        <EmptyState message="Бюджет не задан" />
      )}
    </Panel>
  );
}
