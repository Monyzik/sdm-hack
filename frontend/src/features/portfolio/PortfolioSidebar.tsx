import type { PortfolioProjectSummary } from "../../api/types";
import { Badge, Card, RiskBadge } from "../../components/ui";
import { formatPercent } from "../../lib/format";

interface PortfolioSidebarProps {
  projects: PortfolioProjectSummary[];
  selectedProjectId: string | null;
  onSelect?: (projectId: string) => void;
}

/** Компактный список проектов без дублирующих индикаторов и прогресс-метрик. */
export function PortfolioSidebar({
  projects,
  selectedProjectId,
  onSelect,
}: PortfolioSidebarProps) {
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3 dark:border-slate-800">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          Проекты
        </h2>
        <span className="text-xs tabular-nums text-slate-500 dark:text-slate-400">
          {projects.length}
        </span>
      </div>
      <ul className="divide-y divide-slate-100 dark:divide-slate-800">
        {projects.map((project) => {
          const isActive = project.project_id === selectedProjectId;
          const rowClasses = `w-full px-4 py-3 text-left transition ${
            isActive
              ? "bg-indigo-50 dark:bg-indigo-950/30"
              : "hover:bg-slate-50 dark:hover:bg-slate-800/50"
          }`;

          return (
            <li key={project.project_id}>
              {onSelect ? (
                <button
                  type="button"
                  aria-current={isActive ? "true" : undefined}
                  onClick={() => onSelect(project.project_id)}
                  className={`${rowClasses} focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400`}
                >
                  <ProjectRow project={project} />
                </button>
              ) : (
                <div
                  aria-current={isActive ? "true" : undefined}
                  className={rowClasses}
                >
                  <ProjectRow project={project} />
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function ProjectRow({ project }: { project: PortfolioProjectSummary }) {
  const totalSignals =
    project.overdue_tasks_count + project.blocked_tasks_count + project.high_risk_count;
  const problem = getProjectProblem(project);
  const completion = Math.round(project.completion_percent);

  return (
    <div className="min-w-0 space-y-2">
      <div className="min-w-0">
        <p className="line-clamp-1 text-sm font-semibold text-slate-950 dark:text-slate-50">
          {project.project_name}
        </p>
        <p className="mt-0.5 truncate text-xs text-slate-500 dark:text-slate-400">
          {project.priority}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
          <div
            className="h-full rounded-full bg-indigo-500 transition-all duration-500"
            style={{ width: `${completion}%` }}
          />
        </div>
        <span className="shrink-0 text-xs tabular-nums text-slate-500 dark:text-slate-400">
          {completion}%
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        <RiskBadge level={project.risk_level} />
        {totalSignals > 0 ? (
          <Badge tone="neutral">{totalSignals} сигналов</Badge>
        ) : null}
      </div>
      <p className="line-clamp-2 text-xs leading-5 text-slate-600 dark:text-slate-300">
        {problem}
      </p>
    </div>
  );
}

function getProjectProblem(project: PortfolioProjectSummary) {
  if (project.blocked_tasks_count > 0) {
    return "Блокируют задачи";
  }
  if ((project.budget_deviation_percent ?? 0) > 10) {
    return `Бюджет выше плана на ${formatPercent(project.budget_deviation_percent ?? 0)}`;
  }
  if (project.overdue_tasks_count > 0) {
    return "Просрочены задачи";
  }
  if (project.high_risk_count > 0) {
    return "Высокие риски";
  }
  return project.top_signals[0] ?? "Критичных проблем нет";
}
