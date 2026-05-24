import type { PortfolioProjectSummary } from "../../api/types";
import { Card, ProgressBar, RiskBadge } from "../../components/ui";
import { healthTone } from "../../lib/risk";

interface PortfolioSidebarProps {
  projects: PortfolioProjectSummary[];
  selectedProjectId: string | null;
  onSelect?: (projectId: string) => void;
}

/**
 * Список проектов портфеля. Реализован как набор кнопок с явным состоянием
 * выбора (`aria-current`), что делает навигацию доступной с клавиатуры.
 */
export function PortfolioSidebar({
  projects,
  selectedProjectId,
  onSelect,
}: PortfolioSidebarProps) {
  return (
    <Card>
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
          const totalSignals =
            project.overdue_tasks_count + project.blocked_tasks_count;
          const rowClasses = `relative flex w-full items-center gap-3 px-3.5 py-2.5 text-left transition ${
            isActive
              ? "bg-slate-100 dark:bg-slate-800/70"
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
                  <span className="relative z-10 min-w-0 grid flex-1 gap-1">
                    <span className="line-clamp-1 text-sm font-semibold text-slate-900 dark:text-slate-100">
                      {project.project_name}
                    </span>
                    <span className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                      <span className="truncate">{project.owner_name}</span>
                      <span className="tabular-nums">
                        {Math.round(project.completion_percent)}%
                      </span>
                    </span>
                    <span className="flex items-center gap-1.5">
                      <RiskBadge level={project.risk_level} />
                      <span className="text-xs tabular-nums text-slate-500 dark:text-slate-400">
                        {totalSignals} сигн.
                      </span>
                    </span>
                    <ProgressBar
                      value={project.completion_percent}
                      tone={healthTone(project.project_health_score)}
                      ariaLabel={`Готовность проекта ${project.project_name}: ${Math.round(
                        project.completion_percent,
                      )}%`}
                    />
                  </span>
                  <span className="shrink-0 text-sm font-semibold tabular-nums text-slate-950 dark:text-slate-50">
                    <span className="inline-grid min-w-[2.5rem] justify-items-end">
                      {project.project_health_score}
                    </span>
                  </span>
                </button>
              ) : (
                <div
                  aria-current={isActive ? "true" : undefined}
                  className={`flex w-full items-center gap-3 px-3.5 py-2.5 ${
                    isActive ? "bg-slate-100 dark:bg-slate-800/70" : ""
                  }`}
                >
                  <span className="min-w-0 grid flex-1 gap-1">
                    <span className="line-clamp-1 text-sm font-semibold text-slate-900 dark:text-slate-100">
                      {project.project_name}
                    </span>
                    <span className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                      <span className="truncate">{project.owner_name}</span>
                      <span className="tabular-nums">
                        {Math.round(project.completion_percent)}%
                      </span>
                    </span>
                    <span className="flex items-center gap-1.5">
                      <RiskBadge level={project.risk_level} />
                      <span className="text-xs tabular-nums text-slate-500 dark:text-slate-400">
                        {totalSignals} сигн.
                      </span>
                    </span>
                    <ProgressBar
                      value={project.completion_percent}
                      tone={healthTone(project.project_health_score)}
                      ariaLabel={`Готовность проекта ${project.project_name}: ${Math.round(
                        project.completion_percent,
                      )}%`}
                    />
                  </span>
                  <span className="shrink-0 text-sm font-semibold tabular-nums text-slate-950 dark:text-slate-50">
                    <span className="inline-grid min-w-[2.5rem] justify-items-end">
                      {project.project_health_score}
                    </span>
                  </span>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
