import { CheckCircle2, TriangleAlert } from "lucide-react";

import type { PortfolioSummary } from "../../api/types";
import { Card, CircularGauge, MiniBar } from "../../components/ui";
import { healthTone } from "../../lib/risk";

/** Сводные плитки по всему портфелю: число проектов, индекс состояния, красные/зелёные. */
export function PortfolioStats({ portfolio }: { portfolio: PortfolioSummary }) {
  const total = Math.max(portfolio.projects_count, 1);

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase text-slate-500 dark:text-slate-400">
            Портфель
          </p>
          <p className="mt-1 text-2xl font-semibold text-slate-950 dark:text-slate-50">
            {portfolio.projects_count} проектов
          </p>
        </div>
        <CircularGauge
          value={portfolio.portfolio_health_score}
          label="Индекс состояния"
          tone={healthTone(portfolio.portfolio_health_score)}
        />
      </div>
      <div className="mt-4 flex items-center gap-2">
        <div
          className="inline-flex flex-1 items-center justify-between rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-200"
          title="Проекты, требующие внимания"
        >
          <TriangleAlert aria-hidden className="size-4" />
          <span className="text-lg font-semibold tabular-nums">
            {portfolio.red_projects_count}
          </span>
        </div>
        <div
          className="inline-flex flex-1 items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-200"
          title="Проекты без критичных сигналов"
        >
          <CheckCircle2 aria-hidden className="size-4" />
          <span className="text-lg font-semibold tabular-nums">
            {portfolio.green_projects_count}
          </span>
        </div>
      </div>
      <div className="mt-4 space-y-3">
        <MiniBar
          label="Требуют внимания"
          value={(portfolio.red_projects_count / total) * 100}
          tone="danger"
        />
        <MiniBar
          label="В норме"
          value={(portfolio.green_projects_count / total) * 100}
          tone="success"
        />
      </div>
    </Card>
  );
}
