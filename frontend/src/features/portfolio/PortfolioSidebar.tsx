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
      <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-900 dark:border-slate-800 dark:text-slate-100">
        Портфель проектов
      </h2>
      <ul className="space-y-3 bg-slate-50 p-4 dark:bg-transparent">
        {projects.map((project) => {
          const isActive = project.project_id === selectedProjectId;
          const content = (
            <>
              <div className="flex items-start justify-between gap-2">
                <span className="line-clamp-2 text-sm font-semibold text-slate-900 dark:text-slate-100">
                  {project.project_name}
                </span>
                <span className="text-sm font-semibold tabular-nums text-slate-950 dark:text-slate-50">
                  {project.project_health_score}
                </span>
              </div>
              <div className="flex items-center justify-between gap-2 text-xs text-slate-500 dark:text-slate-400">
                <span className="truncate">{project.owner_name}</span>
                <RiskBadge level={project.risk_level} />
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                <span className="tabular-nums">
                  {Math.round(project.completion_percent)}%
                </span>
                <span className="tabular-nums">
                  {project.overdue_tasks_count + project.blocked_tasks_count}{" "}
                  сигн.
                </span>
              </div>
              <ProgressBar
                value={project.completion_percent}
                tone={healthTone(project.project_health_score)}
                ariaLabel={`Готовность проекта ${project.project_name}: ${Math.round(
                  project.completion_percent,
                )}%`}
              />
            </>
          );

          return (
            <li key={project.project_id}>
              {onSelect ? (
                <button
                  type="button"
                  aria-current={isActive ? "true" : undefined}
                  onClick={() => onSelect(project.project_id)}
                  className={`flex w-full flex-col gap-2 rounded-xl border px-4 py-3 text-left shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 ${
                    isActive
                      ? "border-slate-300 bg-white shadow-slate-200/60 dark:border-slate-700 dark:bg-slate-800/70 dark:shadow-none"
                      : "border-slate-200 bg-white shadow-slate-200/50 hover:border-slate-300 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900/60 dark:shadow-none dark:hover:bg-slate-800/50"
                  }`}
                >
                  {content}
                </button>
              ) : (
                <div
                  aria-current={isActive ? "true" : undefined}
                  className={`flex w-full flex-col gap-2 rounded-xl border px-4 py-3 shadow-sm ${
                    isActive
                      ? "border-slate-300 bg-white shadow-slate-200/60 dark:border-slate-700 dark:bg-slate-800/70 dark:shadow-none"
                      : "border-slate-200 bg-white shadow-slate-200/50 dark:border-slate-800 dark:bg-slate-900/60 dark:shadow-none"
                  }`}
                >
                  {content}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
