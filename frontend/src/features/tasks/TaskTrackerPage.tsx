import { useQueries } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  CircleDashed,
  Filter,
  Search,
} from "lucide-react";
import { useMemo, useState } from "react";

import { fetchProjectSummary } from "../../api/client";
import type {
  PortfolioProjectSummary,
  ProjectSummary,
  RiskLevel,
  TaskSignal,
} from "../../api/types";
import { Badge, ErrorState, LoadingState, MetricTile, ProgressBar } from "../../components/ui";
import { formatDate, formatDays } from "../../lib/format";
import {
  healthTone,
  riskLabel,
  riskTone,
  severityTone,
  statusLabel,
} from "../../lib/risk";
import { queryKeys } from "../../hooks/queryKeys";

type TaskMode = "all" | "blocked" | "overdue";
type SortMode = "attention" | "overdue" | "project";

interface TaskTrackerPageProps {
  projects: PortfolioProjectSummary[];
  asOf: string;
  enabled: boolean;
  onOpenProject: (projectId: string) => void;
}

interface TrackerTask extends TaskSignal {
  project_id: string;
  project_name: string;
  project_owner_name: string;
  project_risk_level: RiskLevel;
  project_health_score: number;
  is_blocked: boolean;
  is_overdue: boolean;
  attention_score: number;
}

export function TaskTrackerPage({
  projects,
  asOf,
  enabled,
  onOpenProject,
}: TaskTrackerPageProps) {
  const [mode, setMode] = useState<TaskMode>("all");
  const [sortMode, setSortMode] = useState<SortMode>("attention");
  const [query, setQuery] = useState("");

  const projectQueries = useQueries({
    queries: projects.map((project) => ({
      queryKey: queryKeys.project(project.project_id, asOf),
      queryFn: ({ signal }: { signal?: AbortSignal }) =>
        fetchProjectSummary(project.project_id, asOf, signal),
      enabled,
      staleTime: 30_000,
    })),
  });

  const summaries = projectQueries
    .map((item) => item.data)
    .filter((item): item is ProjectSummary => Boolean(item));
  const isPending = projectQueries.some((item) => item.isPending);
  const isError = projectQueries.some((item) => item.isError);
  const isFetching = projectQueries.some((item) => item.isFetching);

  const tasks = useMemo(() => buildTrackerTasks(summaries), [summaries]);
  const filteredTasks = useMemo(
    () => filterTasks(tasks, mode, query, sortMode),
    [mode, query, sortMode, tasks],
  );

  const totalBlocked = tasks.filter((task) => task.is_blocked).length;
  const totalOverdue = tasks.filter((task) => task.is_overdue).length;
  const maxOverdue = Math.max(0, ...tasks.map((task) => task.overdue_days));
  const criticalTasks = tasks.filter(
    (task) => task.priority === "critical" || task.project_risk_level === "red",
  ).length;

  if (isPending && !summaries.length) {
    return <LoadingState label="Загрузка задач…" />;
  }

  if (isError && !summaries.length) {
    return (
      <ErrorState
        message="Не удалось загрузить задачи проектов."
        onRetry={() => projectQueries.forEach((item) => item.refetch())}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        <MetricTile
          label="В фокусе"
          value={filteredTasks.length}
          tone={filteredTasks.length ? "danger" : "success"}
          icon={<AlertCircle className="size-4" />}
          hint={isFetching ? "Обновление…" : `${tasks.length} задач в датасете`}
        />
        <MetricTile
          label="Блокируют"
          value={totalBlocked}
          tone={totalBlocked ? "danger" : "success"}
          icon={<CircleDashed className="size-4" />}
        />
        <MetricTile
          label="Просрочены"
          value={totalOverdue}
          tone={totalOverdue ? "warning" : "success"}
          icon={<ArrowDown className="size-4" />}
          hint={maxOverdue ? `макс. ${formatDays(maxOverdue)}` : "нет просроченных"}
        />
        <MetricTile
          label="Критичность"
          value={criticalTasks}
          tone={criticalTasks ? "danger" : "neutral"}
          icon={<ArrowUp className="size-4" />}
          hint="critical priority или red проект"
        />
      </div>

      <div className="flex flex-col gap-3 border-b border-slate-200 pb-4 dark:border-slate-800 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <Filter aria-hidden className="size-4 text-slate-400" />
          <SegmentButton active={mode === "all"} onClick={() => setMode("all")}>
            Все
          </SegmentButton>
          <SegmentButton
            active={mode === "blocked"}
            onClick={() => setMode("blocked")}
          >
            Блокируют
          </SegmentButton>
          <SegmentButton
            active={mode === "overdue"}
            onClick={() => setMode("overdue")}
          >
            Просрочены
          </SegmentButton>
          <select
            value={sortMode}
            onChange={(event) => setSortMode(event.target.value as SortMode)}
            className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100 dark:focus:border-slate-600 dark:focus:ring-slate-800"
          >
            <option value="attention">Сначала критичные</option>
            <option value="overdue">Сначала просроченные</option>
            <option value="project">По проектам</option>
          </select>
        </div>

        <label className="relative block w-full xl:w-80">
          <Search
            aria-hidden
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400"
          />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Поиск по задаче, проекту, владельцу"
            className="h-9 w-full rounded-lg border border-slate-200 bg-white pl-9 pr-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-slate-400 focus:ring-2 focus:ring-slate-200 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:border-slate-600 dark:focus:ring-slate-800"
          />
        </label>
      </div>

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="grid grid-cols-[minmax(320px,1.5fr)_minmax(180px,0.8fr)_minmax(150px,0.6fr)_minmax(190px,0.8fr)] border-b border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold uppercase text-slate-500 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400">
          <span>Задача</span>
          <span>Проект</span>
          <span>Срок</span>
          <span>Состояние</span>
        </div>
        {filteredTasks.length ? (
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {filteredTasks.map((task) => (
              <li
                key={`${task.project_id}-${task.id}`}
                className="grid grid-cols-1 gap-3 px-4 py-4 transition hover:bg-slate-50 dark:hover:bg-slate-950/60 lg:grid-cols-[minmax(320px,1.5fr)_minmax(180px,0.8fr)_minmax(150px,0.6fr)_minmax(190px,0.8fr)] lg:items-center"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={severityTone(task.priority)}>
                      {statusLabel(task.priority)}
                    </Badge>
                    {task.is_blocked ? (
                      <Badge tone="danger">заблокировано</Badge>
                    ) : null}
                    {task.is_overdue ? (
                      <Badge tone="warning">просрочено</Badge>
                    ) : null}
                  </div>
                  <p className="mt-2 line-clamp-2 text-sm font-semibold text-slate-950 dark:text-slate-50">
                    {task.title}
                  </p>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    {task.external_id} · {task.assignee_name}
                  </p>
                  {task.blocker_reason ? (
                    <p className="mt-2 rounded-md bg-rose-50 px-2 py-1.5 text-xs text-rose-800 dark:bg-rose-950/40 dark:text-rose-200">
                      {task.blocker_reason}
                    </p>
                  ) : null}
                </div>

                <button
                  type="button"
                  onClick={() => onOpenProject(task.project_id)}
                  className="min-w-0 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
                >
                  <p className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">
                    {task.project_name}
                  </p>
                  <p className="mt-0.5 truncate text-xs text-slate-500 dark:text-slate-400">
                    {task.project_owner_name}
                  </p>
                  <div className="mt-2 max-w-40">
                    <ProgressBar
                      value={task.project_health_score}
                      tone={healthTone(task.project_health_score)}
                      ariaLabel={`Здоровье ${task.project_name}`}
                    />
                  </div>
                  <div className="mt-2">
                    <Badge tone={riskTone(task.project_risk_level)}>
                      {riskLabel(task.project_risk_level)}
                    </Badge>
                  </div>
                </button>

                <div>
                  <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
                    {formatDate(task.planned_due_date)}
                  </p>
                  {task.overdue_days > 0 ? (
                    <p className="mt-1 text-xs font-medium text-rose-600 dark:text-rose-300">
                      {formatDays(task.overdue_days)}
                    </p>
                  ) : (
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                      не просрочена
                    </p>
                  )}
                </div>

                <div className="flex flex-wrap gap-2">
                  <Badge tone={severityTone(task.status)}>
                    {statusLabel(task.status)}
                  </Badge>
                  <Badge tone="neutral">score {task.attention_score}</Badge>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <div className="px-4 py-12 text-center text-sm text-slate-500 dark:text-slate-400">
            По текущим фильтрам задач нет.
          </div>
        )}
      </div>
    </div>
  );
}

function SegmentButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`h-9 rounded-lg px-3 text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 ${
        active
          ? "bg-slate-950 text-white dark:bg-slate-100 dark:text-slate-950"
          : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
      }`}
    >
      {children}
    </button>
  );
}

function buildTrackerTasks(summaries: ProjectSummary[]): TrackerTask[] {
  const result = new Map<string, TrackerTask>();

  for (const project of summaries) {
    for (const task of project.blocked_tasks) {
      upsertTask(result, project, task, { isBlocked: true, isOverdue: false });
    }
    for (const task of project.overdue_tasks) {
      upsertTask(result, project, task, { isBlocked: false, isOverdue: true });
    }
  }

  return Array.from(result.values()).map((task) => ({
    ...task,
    attention_score:
      (task.is_blocked ? 60 : 0) +
      Math.min(task.overdue_days * 2, 60) +
      priorityWeight(task.priority) +
      (task.project_risk_level === "red" ? 20 : task.project_risk_level === "yellow" ? 10 : 0),
  }));
}

function upsertTask(
  result: Map<string, TrackerTask>,
  project: ProjectSummary,
  task: TaskSignal,
  flags: { isBlocked: boolean; isOverdue: boolean },
) {
  const key = `${project.project_id}-${task.id}`;
  const existing = result.get(key);
  if (existing) {
    existing.is_blocked = existing.is_blocked || flags.isBlocked;
    existing.is_overdue = existing.is_overdue || flags.isOverdue;
    return;
  }

  result.set(key, {
    ...task,
    project_id: project.project_id,
    project_name: project.project_name,
    project_owner_name: `${project.lifecycle_status} · ${project.priority}`,
    project_risk_level: project.risk_level,
    project_health_score: project.project_health_score,
    is_blocked: flags.isBlocked,
    is_overdue: flags.isOverdue,
    attention_score: 0,
  });
}

function filterTasks(
  tasks: TrackerTask[],
  mode: TaskMode,
  query: string,
  sortMode: SortMode,
) {
  const normalizedQuery = query.trim().toLowerCase();
  const filtered = tasks.filter((task) => {
    if (mode === "blocked" && !task.is_blocked) return false;
    if (mode === "overdue" && !task.is_overdue) return false;
    if (!normalizedQuery) return true;
    return [
      task.title,
      task.external_id,
      task.assignee_name,
      task.project_name,
      task.project_owner_name,
      task.status,
      task.priority,
      task.blocker_reason ?? "",
    ].some((value) => value.toLowerCase().includes(normalizedQuery));
  });

  return filtered.sort((left, right) => {
    if (sortMode === "overdue") {
      return right.overdue_days - left.overdue_days;
    }
    if (sortMode === "project") {
      return left.project_name.localeCompare(right.project_name, "ru");
    }
    return right.attention_score - left.attention_score;
  });
}

function priorityWeight(priority: string) {
  const normalized = priority.toLowerCase();
  if (normalized === "critical") return 40;
  if (normalized === "high") return 25;
  if (normalized === "medium") return 10;
  return 0;
}
