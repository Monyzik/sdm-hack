import { Banknote } from "lucide-react";

import type { BudgetSummary } from "../../../api/types";
import { EmptyState, Panel } from "../../../components/ui";
import { formatMoney, formatPercent } from "../../../lib/format";
import type { Tone } from "../../../lib/risk";

interface BudgetTileProps {
  label: string;
  value: string;
  hint: string;
  tone?: Tone;
}

const tileToneClass: Record<Tone, string> = {
  neutral:
    "border-slate-200 bg-slate-50 text-slate-950 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-50",
  danger:
    "border-rose-200 bg-rose-50 text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-100",
  warning:
    "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-100",
  success:
    "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-100",
  info: "border-sky-200 bg-sky-50 text-sky-900 dark:border-sky-900/60 dark:bg-sky-950/30 dark:text-sky-100",
};

function BudgetTile({ label, value, hint, tone = "neutral" }: BudgetTileProps) {
  return (
    <div className={`min-h-28 rounded-lg border px-3 py-3 ${tileToneClass[tone]}`}>
      <div className="text-xs font-medium uppercase text-slate-500 dark:text-slate-400">
        {label}
      </div>
      <div className="mt-2 text-2xl font-semibold tabular-nums tracking-normal">
        {value}
      </div>
      <div className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500 dark:text-slate-400">
        {hint}
      </div>
    </div>
  );
}

/** Сводка по бюджету: входной план/факт и расчетные forecast/ROI. */
export function BudgetPanel({ budget }: { budget: BudgetSummary | null }) {
  return (
    <Panel title="Бюджет" icon={<Banknote className="size-4" />}>
      {budget ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <BudgetTile
            label="План"
            value={formatMoney(budget.planned_budget, budget.currency)}
            hint="Базовый лимит проекта"
          />
          <BudgetTile
            label="Факт"
            value={formatMoney(budget.actual_spent, budget.currency)}
            hint="Уже потрачено"
            tone={budget.actual_spent > budget.planned_budget ? "danger" : "neutral"}
          />
          <BudgetTile
            label="Прогноз"
            value={formatMoney(budget.forecast_total_spent, budget.currency)}
            hint="Расчетные ожидаемые затраты"
            tone={
              budget.forecast_total_spent > budget.planned_budget
                ? "warning"
                : "success"
            }
          />
          <BudgetTile
            label="Исполнено"
            value={formatPercent(
              (budget.actual_spent / Math.max(budget.planned_budget, 1)) * 100,
            )}
            hint="Факт к плану"
            tone={budget.actual_spent > budget.planned_budget ? "danger" : "info"}
          />
          <BudgetTile
            label="Прогноз / план"
            value={formatPercent(
              (budget.forecast_total_spent /
                Math.max(budget.planned_budget, 1)) *
                100,
            )}
            hint="Будет потрачено к лимиту"
            tone={
              budget.forecast_total_spent > budget.planned_budget
                ? "warning"
                : "success"
            }
          />
          <BudgetTile
            label="Отклонение"
            value={formatPercent(budget.budget_deviation_percent, true)}
            hint="Расчетный forecast минус plan"
            tone={budget.budget_deviation_percent > 0 ? "danger" : "success"}
          />
          <BudgetTile
            label="ROI"
            value={formatPercent(budget.roi_percent, true)}
            hint="Экономический смысл"
            tone={budget.roi_percent < 0 ? "danger" : "success"}
          />
          <BudgetTile
            label="Risk-adjusted ROI"
            value={formatPercent(budget.risk_adjusted_roi_percent, true)}
            hint="С учетом рисков"
            tone={budget.risk_adjusted_roi_percent < 0 ? "danger" : "success"}
          />
        </div>
      ) : (
        <EmptyState message="Бюджет не задан" />
      )}
    </Panel>
  );
}
