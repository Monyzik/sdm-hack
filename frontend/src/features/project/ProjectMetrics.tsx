import {
  AlertTriangle,
  Clock3,
  FileClock,
  GitBranch,
  ShieldAlert,
  UsersRound,
} from "lucide-react";

import type { ProjectSummary } from "../../api/types";
import { MetricTile } from "../../components/ui";
import type { Tone } from "../../lib/risk";

/** Тон счётчика: 0 — нейтрально, иначе — тревожный тон. */
function countTone(count: number, tone: Tone): Tone {
  return count > 0 ? tone : "neutral";
}

/** Сетка ключевых метрик проекта. */
export function ProjectMetrics({ project }: { project: ProjectSummary }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      <MetricTile
        label="Просрочено"
        value={project.overdue_tasks_count}
        tone={countTone(project.overdue_tasks_count, "danger")}
        icon={<Clock3 className="size-4" />}
      />
      <MetricTile
        label="Блокеры"
        value={project.blocked_tasks_count}
        tone={countTone(project.blocked_tasks_count, "danger")}
        icon={<AlertTriangle className="size-4" />}
      />
      <MetricTile
        label="High risks"
        value={project.high_risk_count}
        tone={countTone(project.high_risk_count, "warning")}
        icon={<ShieldAlert className="size-4" />}
      />
      <MetricTile
        label="Зависимости"
        value={project.dependency_risk_count}
        tone={countTone(project.dependency_risk_count, "warning")}
        icon={<GitBranch className="size-4" />}
      />
      <MetricTile
        label="Решения"
        value={project.pending_decision_count}
        tone={countTone(project.pending_decision_count, "warning")}
        icon={<FileClock className="size-4" />}
      />
      <MetricTile
        label="Перегруз"
        value={`${Math.round(project.resource_overload_percent)}%`}
        tone={countTone(project.resource_overload_percent, "warning")}
        icon={<UsersRound className="size-4" />}
      />
    </div>
  );
}
