import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Gauge,
  ShieldAlert,
} from "lucide-react";

import type { ProjectSummary } from "../../api/types";
import { Card, MetricTile, RiskBadge } from "../../components/ui";
import { healthTone } from "../../lib/risk";

/**
 * Шапка карточки проекта: название, зона риска, владелец и главные метрики.
 */
export function ProjectHeader({ project }: { project: ProjectSummary }) {
  return (
    <Card className="p-5">
      <div className="flex flex-col gap-5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-2xl font-semibold text-slate-950 dark:text-slate-50">
              {project.project_name}
            </h2>
            <RiskBadge level={project.risk_level} />
          </div>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {project.owner_name} · {project.priority}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <MetricTile
            label="Health"
            value={project.project_health_score}
            tone={healthTone(project.project_health_score)}
            icon={<Gauge className="size-4" />}
          />
          <MetricTile
            label="Готовность"
            value={`${Math.round(project.completion_percent)}%`}
            icon={<CheckCircle2 className="size-4" />}
            hint={`${project.completed_tasks_count} из ${project.total_tasks_count} задач`}
          />
          <MetricTile
            label="Блокеры"
            value={project.blocked_tasks_count}
            tone={project.blocked_tasks_count ? "danger" : "neutral"}
            icon={<AlertTriangle className="size-4" />}
          />
          <MetricTile
            label="Просрочки"
            value={project.overdue_tasks_count}
            tone={project.overdue_tasks_count ? "danger" : "neutral"}
            icon={<Clock3 className="size-4" />}
          />
          <MetricTile
            label="Риски"
            value={project.high_risk_count}
            tone={project.high_risk_count ? "warning" : "neutral"}
            icon={<ShieldAlert className="size-4" />}
          />
        </div>
      </div>
    </Card>
  );
}
