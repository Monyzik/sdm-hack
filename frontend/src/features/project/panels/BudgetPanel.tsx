import { Banknote } from "lucide-react";

import type { BudgetSummary } from "../../../api/types";
import { Badge, EmptyState, Panel } from "../../../components/ui";
import { formatMoney, formatPercent } from "../../../lib/format";

/** Сводка бюджета: план, факт, прогноз, отклонение и ROI в деталях. */
export function BudgetPanel({ budget }: { budget: BudgetSummary | null }) {
  if (!budget) {
    return (
      <Panel title="Бюджет" icon={<Banknote className="size-4" />}>
        <EmptyState message="Бюджет не задан" />
      </Panel>
    );
  }

  const overrunAmount = budget.forecast_total_spent - budget.planned_budget;
  const isOverrun = overrunAmount > 0;
  const burnRate = (budget.actual_spent / Math.max(budget.planned_budget, 1)) * 100;
  const forecastRate =
    (budget.forecast_total_spent / Math.max(budget.planned_budget, 1)) * 100;

  return (
    <Panel
      title="Бюджет"
      icon={<Banknote className="size-4" />}
      action={
        <Badge tone={isOverrun ? "danger" : "success"}>
          {formatPercent(budget.budget_deviation_percent, true)}
        </Badge>
      }
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <BudgetFact
          label="План"
          value={formatMoney(budget.planned_budget, budget.currency)}
          hint="Базовый лимит"
        />
        <BudgetFact
          label="Факт"
          value={formatMoney(budget.actual_spent, budget.currency)}
          hint="Уже потрачено"
          danger={budget.actual_spent > budget.planned_budget}
        />
        <BudgetFact
          label="Прогноз"
          value={formatMoney(budget.forecast_total_spent, budget.currency)}
          hint="Ожидаемые затраты"
          danger={isOverrun}
        />
        <BudgetFact
          label="Отклонение"
          value={`${isOverrun ? "+" : ""}${formatMoney(overrunAmount, budget.currency)}`}
          hint="Прогноз минус план"
          danger={isOverrun}
        />
      </div>

      <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-300">
        {isOverrun
          ? `Прогноз выше плана на ${formatPercent(budget.budget_deviation_percent)}. Сверить причину с открытыми change requests и рисками.`
          : "Прогноз бюджета укладывается в текущий лимит."}
      </p>

      <details className="mt-3 rounded-lg border border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-950/40">
        <summary className="cursor-pointer list-none px-3 py-2 text-sm font-semibold text-slate-700 outline-none transition hover:bg-white focus-visible:ring-2 focus-visible:ring-slate-400 dark:text-slate-200 dark:hover:bg-slate-900">
          Детали бюджета
        </summary>
        <div className="grid grid-cols-1 gap-2 border-t border-slate-200 p-3 text-sm dark:border-slate-800 md:grid-cols-4">
          <BudgetFact label="Исполнено" value={formatPercent(burnRate)} />
          <BudgetFact label="Прогноз / план" value={formatPercent(forecastRate)} />
          <BudgetFact
            label="ROI"
            value={formatPercent(budget.roi_percent, true)}
            danger={budget.roi_percent < 0}
          />
          <BudgetFact
            label="ROI с учетом рисков"
            value={formatPercent(budget.risk_adjusted_roi_percent, true)}
            danger={budget.risk_adjusted_roi_percent < 0}
          />
        </div>
      </details>
    </Panel>
  );
}

function BudgetFact({
  label,
  value,
  hint,
  danger = false,
}: {
  label: string;
  value: string;
  hint?: string;
  danger?: boolean;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 dark:border-slate-800 dark:bg-slate-950/30">
      <div className="text-xs text-slate-500 dark:text-slate-400">{label}</div>
      <div
        className={`mt-1 text-base font-semibold tabular-nums ${
          danger
            ? "text-rose-700 dark:text-rose-300"
            : "text-slate-950 dark:text-slate-50"
        }`}
      >
        {value}
      </div>
      {hint ? (
        <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
          {hint}
        </div>
      ) : null}
    </div>
  );
}
