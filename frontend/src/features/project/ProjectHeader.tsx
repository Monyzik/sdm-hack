import { CheckCircle2 } from "lucide-react";

import type { ProjectSummary } from "../../api/types";
import {
  Card,
  CircularGauge,
  MetricTile,
  RiskBadge,
} from "../../components/ui";
import { healthTone } from "../../lib/risk";

/**
 * Шапка карточки проекта: название, зона риска, владелец, executive summary
 * и две главные метрики (health и готовность).
 */
export function ProjectHeader({ project }: { project: ProjectSummary }) {
  return (
    <Card className="overflow-hidden">
      <div className="grid gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_330px] xl:items-center">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-2xl font-semibold text-slate-950 dark:text-slate-50">
              {project.project_name}
            </h2>
            <RiskBadge level={project.risk_level} />
          </div>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Владелец: {project.owner_name} · Статус: {project.status} ·
            Приоритет: {project.priority}
          </p>
          <p className="line-clamp-2 mt-3 max-w-4xl text-sm leading-6 text-slate-700 dark:text-slate-300">
            {project.executive_summary}
          </p>
        </div>
        <div className="grid grid-cols-[110px_minmax(0,1fr)] items-center gap-3">
          <CircularGauge
            value={project.project_health_score}
            label="health"
            tone={healthTone(project.project_health_score)}
          />
          <MetricTile
            label="Готовность"
            value={`${Math.round(project.completion_percent)}%`}
            icon={<CheckCircle2 className="size-4" />}
            hint={`${project.completed_tasks_count} из ${project.total_tasks_count} задач`}
          />
        </div>
      </div>
      <div className="grid grid-cols-3 border-t border-slate-100 bg-slate-50/70 dark:border-slate-800 dark:bg-slate-950/30">
        <div className="px-5 py-3">
          <p className="text-xs text-slate-500 dark:text-slate-400">Блокеры</p>
          <p className="mt-1 text-lg font-semibold tabular-nums text-slate-950 dark:text-slate-50">
            {project.blocked_tasks_count}
          </p>
        </div>
        <div className="border-x border-slate-100 px-5 py-3 dark:border-slate-800">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Просрочки
          </p>
          <p className="mt-1 text-lg font-semibold tabular-nums text-slate-950 dark:text-slate-50">
            {project.overdue_tasks_count}
          </p>
        </div>
        <div className="px-5 py-3">
          <p className="text-xs text-slate-500 dark:text-slate-400">Риски</p>
          <p className="mt-1 text-lg font-semibold tabular-nums text-slate-950 dark:text-slate-50">
            {project.high_risk_count}
          </p>
        </div>
      </div>
    </Card>
  );
}
