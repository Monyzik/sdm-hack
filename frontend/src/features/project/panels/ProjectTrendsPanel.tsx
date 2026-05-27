import { Activity } from "lucide-react";

import type { ProjectTrendPoint, ProjectTrends } from "../../../api/types";
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
  const readinessPoints = trimLeadingZeroPoints(
    points,
    (point) => point.completion_percent,
  );
  const riskPoints = trimLeadingZeroPoints(points, (point) =>
    Math.max(point.risk_pressure_score, point.resource_overload_percent),
  );

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
                Доля задач, завершенных к каждому дневному срезу
              </div>
            </div>
            {readinessPoints.length < 2 ? (
              <EmptyState message="Нет ненулевой динамики готовности" />
            ) : (
              <TrendLineChart
                labels={readinessPoints.map((point) =>
                  shortDate(point.as_of_date),
                )}
                series={[
                  {
                    label: "Готовность",
                    values: readinessPoints.map(
                      (point) => point.completion_percent,
                    ),
                    tone: "success",
                    suffix: "%",
                  },
                ]}
              />
            )}
          </div>

          <div>
            <div className="mb-3">
              <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Риски
              </div>
              <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Давление рисков и перегрузка ресурсов по дням
              </div>
            </div>
            {riskPoints.length < 2 ? (
              <EmptyState message="Нет ненулевой динамики рисков" />
            ) : (
              <TrendLineChart
                labels={riskPoints.map((point) => shortDate(point.as_of_date))}
                series={[
                  {
                    label: "Риск-давление",
                    values: riskPoints.map(
                      (point) => point.risk_pressure_score,
                    ),
                    tone: "danger",
                  },
                  {
                    label: "Перегрузка ресурсов",
                    values: riskPoints.map(
                      (point) => point.resource_overload_percent,
                    ),
                    tone: "warning",
                    suffix: "%",
                  },
                ]}
              />
            )}
          </div>
        </div>
      )}
    </Panel>
  );
}

function trimLeadingZeroPoints(
  points: ProjectTrendPoint[],
  value: (point: ProjectTrendPoint) => number,
) {
  const firstMeaningfulIndex = points.findIndex((point) => value(point) > 0);
  if (firstMeaningfulIndex < 0) return [];
  return points.slice(firstMeaningfulIndex);
}

function shortDate(value: string) {
  const [, month, day] = value.split("-");
  return `${day}.${month}`;
}
