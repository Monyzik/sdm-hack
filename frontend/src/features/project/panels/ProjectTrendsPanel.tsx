import { Activity } from "lucide-react";

import type { ProjectTrends } from "../../../api/types";
import { TrendLineChart } from "../../../components/ui/Charts";
import { EmptyState, LoadingState, Panel } from "../../../components/ui";

export function ProjectTrendsPanel({
  trends,
  isLoading,
}: {
  trends?: ProjectTrends;
  isLoading: boolean;
}) {
  const points = trends?.points ?? [];
  const labels = points.map((point) => shortDate(point.as_of_date));

  return (
    <Panel title="Тренды проекта" icon={<Activity className="size-4" />}>
      {isLoading ? (
        <LoadingState label="Загрузка трендов…" />
      ) : points.length < 2 ? (
        <EmptyState message="Недостаточно данных для тренда" />
      ) : (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <div>
            <div className="mb-3">
              <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Готовность
              </div>
              <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Доля задач, завершенных к каждому срезу
              </div>
            </div>
            <TrendLineChart
              labels={labels}
              series={[
                {
                  label: "Готовность",
                  values: points.map((point) => point.completion_percent),
                  tone: "success",
                  suffix: "%",
                },
              ]}
            />
          </div>

          <div>
            <div className="mb-3">
              <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Риски
              </div>
              <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Давление рисков с учетом high risks, SLA breach и просрочек
              </div>
            </div>
            <TrendLineChart
              labels={labels}
              series={[
                {
                  label: "Risk pressure",
                  values: points.map((point) => point.risk_pressure_score),
                  tone: "danger",
                },
                {
                  label: "SLA breach",
                  values: points.map((point) => point.dependency_sla_breach_count),
                  tone: "warning",
                },
              ]}
            />
          </div>
        </div>
      )}
    </Panel>
  );
}

function shortDate(value: string) {
  const [, month, day] = value.split("-");
  return `${day}.${month}`;
}
