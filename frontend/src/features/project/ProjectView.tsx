import { AlertTriangle, Clock3 } from "lucide-react";
import { useMemo, useState } from "react";

import type { ProjectSummary } from "../../api/types";
import { ProjectHeader } from "./ProjectHeader";
import { ProjectMetrics } from "./ProjectMetrics";
import { BudgetPanel } from "./panels/BudgetPanel";
import { ChangeRequestsPanel } from "./panels/ChangeRequestsPanel";
import { CommunicationsPanel } from "./panels/CommunicationsPanel";
import { DecisionsPanel } from "./panels/DecisionsPanel";
import { DependenciesPanel } from "./panels/DependenciesPanel";
import { KeySignalsPanel } from "./panels/KeySignalsPanel";
import { ResourcesPanel } from "./panels/ResourcesPanel";
import { RisksPanel } from "./panels/RisksPanel";
import { TasksPanel } from "./panels/TasksPanel";

/**
 * Детальное представление проекта. Здесь только композиция: каждый блок —
 * самостоятельный компонент-панель, отвечающий за свой кусок данных.
 */
export function ProjectView({ project }: { project: ProjectSummary }) {
  const [activeTab, setActiveTab] = useState<
    "summary" | "work" | "coordination"
  >("summary");

  const tabs = useMemo(
    () => [
      { id: "summary" as const, label: "Обзор" },
      {
        id: "work" as const,
        label: "Работа",
        count: project.blocked_tasks_count + project.overdue_tasks_count,
      },
      {
        id: "coordination" as const,
        label: "Координация",
        count:
          project.dependency_risk_count +
          project.pending_decision_count +
          project.open_change_request_count +
          project.delayed_communications.length +
          project.overloaded_resources.length,
      },
    ],
    [project],
  );

  return (
    <div className="flex flex-col gap-4">
      <ProjectHeader project={project} />
      <ProjectMetrics project={project} />

      <div className="flex rounded-xl border border-slate-200 bg-white p-1 shadow-sm dark:border-slate-800 dark:bg-slate-900/80">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`flex min-w-0 flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 ${
              activeTab === tab.id
                ? "bg-slate-100 text-slate-950 shadow-sm dark:bg-slate-800 dark:text-slate-50"
                : "text-slate-500 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800"
            }`}
          >
            <span className="truncate">{tab.label}</span>
            {tab.count ? (
              <span
                className={`rounded-full px-1.5 text-xs tabular-nums ${
                  activeTab === tab.id
                    ? "bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-100"
                    : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                }`}
              >
                {tab.count}
              </span>
            ) : null}
          </button>
        ))}
      </div>

      {activeTab === "summary" ? (
        <div className="flex flex-col gap-4">
          <KeySignalsPanel signals={project.key_signals} />
          <BudgetPanel budget={project.budget} />
          <RisksPanel risks={project.top_risks} />
        </div>
      ) : null}

      {activeTab === "work" ? (
        <div className="flex flex-col gap-4">
          <TasksPanel
            title="Блокеры"
            icon={<AlertTriangle className="size-4" />}
            tasks={project.blocked_tasks}
            emptyMessage="Заблокированных задач нет"
          />
          <TasksPanel
            title="Просроченные задачи"
            icon={<Clock3 className="size-4" />}
            tasks={project.overdue_tasks}
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
