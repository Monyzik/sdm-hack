import { AlertTriangle, Clock3 } from "lucide-react";
import { useMemo, useState } from "react";

import { ApiError } from "../../api/client";
import type { ProjectSummary } from "../../api/types";
import { useProjectProblemContext } from "../../hooks/useProjectProblemContext";
import { useProjectTrends } from "../../hooks/useProjectTrends";
import { ProjectHeader } from "./ProjectHeader";
import { BudgetPanel } from "./panels/BudgetPanel";
import { ChangeRequestsPanel } from "./panels/ChangeRequestsPanel";
import { CommunicationsPanel } from "./panels/CommunicationsPanel";
import { DecisionsPanel } from "./panels/DecisionsPanel";
import { DependenciesPanel } from "./panels/DependenciesPanel";
import { KeySignalsPanel } from "./panels/KeySignalsPanel";
import { ProjectTrendsPanel } from "./panels/ProjectTrendsPanel";
import { ResourcesPanel } from "./panels/ResourcesPanel";
import { RisksPanel } from "./panels/RisksPanel";
import { TaskDependencyGraphPanel } from "./panels/TaskDependencyGraphPanel";
import { TasksPanel } from "./panels/TasksPanel";

/**
 * Детальное представление проекта. Здесь только композиция: каждый блок —
 * самостоятельный компонент-панель, отвечающий за свой кусок данных.
 */
export function ProjectView({
  project,
  asOfDate,
}: {
  project: ProjectSummary;
  asOfDate: string;
}) {
  const [activeTab, setActiveTab] = useState<
    "summary" | "work" | "coordination"
  >("summary");
  const problemContextQuery = useProjectProblemContext(
    project.project_id,
    asOfDate,
    2,
    activeTab === "work",
  );
  const trendsQuery = useProjectTrends(
    project.project_id,
    asOfDate,
    60,
    activeTab === "summary",
  );

  const problemContextErrorMessage = useMemo(() => {
    if (!problemContextQuery.isError) {
      return null;
    }
    if (
      problemContextQuery.error instanceof ApiError &&
      problemContextQuery.error.message
    ) {
      return problemContextQuery.error.message;
    }
    return "Не удалось загрузить граф зависимостей";
  }, [problemContextQuery.error, problemContextQuery.isError]);

  const workTasks = useMemo(() => {
    const blockedTaskIds = new Set(
      project.blocked_tasks.map((task) => task.id),
    );
    const overdueOnlyTasks = project.overdue_tasks.filter(
      (task) => !blockedTaskIds.has(task.id),
    );
    return {
      blocked: project.blocked_tasks,
      overdueOnly: overdueOnlyTasks,
      uniqueCount: project.blocked_tasks.length + overdueOnlyTasks.length,
    };
  }, [project.blocked_tasks, project.overdue_tasks]);

  const tabs = useMemo(
    () => [
      { id: "summary" as const, label: "Обзор" },
      {
        id: "work" as const,
        label: "Работа",
        counterLabel: "задач",
        count: workTasks.uniqueCount,
      },
      {
        id: "coordination" as const,
        label: "Координация",
        counterLabel: "событий",
        count:
          project.dependency_risk_count +
          project.pending_decision_count +
          project.open_change_request_count +
          project.delayed_communications.length +
          project.overloaded_resources.length,
      },
    ],
    [project, workTasks.uniqueCount],
  );

  return (
    <div className="flex flex-col gap-4">
      <ProjectHeader project={project} />

      <div className="flex rounded-xl border border-slate-200 bg-white p-1 shadow-sm dark:border-slate-800 dark:bg-slate-900/80">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`flex min-w-0 flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 ${
              activeTab === tab.id
                ? "bg-indigo-50 text-indigo-700 shadow-sm dark:bg-indigo-950/40 dark:text-indigo-300"
                : "text-slate-500 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800"
            }`}
          >
            <span className="truncate">{tab.label}</span>
            {tab.count ? (
              <span
                className={`rounded-full px-1.5 text-xs ${
                  activeTab === tab.id
                    ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/50 dark:text-indigo-200"
                    : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                }`}
              >
                {tab.count} {tab.counterLabel}
              </span>
            ) : null}
          </button>
        ))}
      </div>

      {activeTab === "summary" ? (
        <div className="flex flex-col gap-4">
          <KeySignalsPanel signals={project.key_signals.slice(0, 5)} />
          <ProjectTrendsPanel
            trends={trendsQuery.data}
            isLoading={trendsQuery.isFetching}
          />
          <BudgetPanel budget={project.budget} />
          <RisksPanel risks={project.top_risks.slice(0, 5)} />

        </div>
      ) : null}

      {activeTab === "work" ? (
        <div className="flex flex-col gap-4">
          <TaskDependencyGraphPanel
            context={problemContextQuery.data}
            isLoading={problemContextQuery.isFetching}
            errorMessage={problemContextErrorMessage}
          />
          <TasksPanel
            title="Блокируют"
            icon={<AlertTriangle className="size-4" />}
            tasks={workTasks.blocked}
            emptyMessage="Заблокированных задач нет"
          />
          <TasksPanel
            title="Просрочены"
            icon={<Clock3 className="size-4" />}
            tasks={workTasks.overdueOnly}
            emptyMessage="Просроченных задач нет"
          />
        </div>
      ) : null}

      {activeTab === "coordination" ? (
        <div className="flex flex-col gap-4">
          <CommunicationsPanel
            communications={project.delayed_communications}
          />
          <DependenciesPanel dependencies={project.risky_dependencies} />
          <ResourcesPanel resources={project.overloaded_resources} />
          <DecisionsPanel decisions={project.pending_decisions} />
          <ChangeRequestsPanel changeRequests={project.open_change_requests} />
        </div>
      ) : null}
    </div>
  );
}
