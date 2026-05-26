import {
  CheckCircle2,
  CheckCheck,
  Loader2,
  Play,
  RefreshCw,
  Trash2,
  XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import type {
  InternalNotification,
  NotificationSeverity,
  PortfolioProjectSummary,
  SimulationJob,
  SimulationStage,
  SimulationStageStatus,
} from "../../api/types";
import {
  clearControlEventSimulation,
  fetchControlEventSimulation,
  startControlEventSimulation,
} from "../../api/client";
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
} from "../../components/ui";
import { useMarkNotificationRead } from "../../hooks/useMarkNotificationRead";
import { useNotifications } from "../../hooks/useNotifications";
import { formatDate } from "../../lib/format";
import type { Tone } from "../../lib/risk";

interface NotificationsPageProps {
  projects: PortfolioProjectSummary[];
  selectedProjectId: string | null;
  onSelectProject: (projectId: string) => void;
}

type ProjectFilter = "all" | string;

const severityTone: Record<NotificationSeverity, Tone> = {
  critical: "danger",
  warning: "warning",
  info: "info",
};

const severityLabel: Record<NotificationSeverity, string> = {
  critical: "Критично",
  warning: "Важно",
  info: "Инфо",
};

export function NotificationsPage({
  projects,
  selectedProjectId,
  onSelectProject,
}: NotificationsPageProps) {
  const queryClient = useQueryClient();
  const [projectFilter, setProjectFilter] = useState<ProjectFilter>(
    "all",
  );
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [openNotificationId, setOpenNotificationId] = useState<string | null>(
    null,
  );
  const [simulationJob, setSimulationJob] = useState<SimulationJob | null>(
    null,
  );
  const [simulationError, setSimulationError] = useState<string | null>(null);
  const [isClearingSimulation, setIsClearingSimulation] = useState(false);
  const projectId = projectFilter === "all" ? null : projectFilter;
  const notificationsQuery = useNotifications(
    null,
    projectId,
    unreadOnly,
  );
  const markReadMutation = useMarkNotificationRead();
  const isSimulationRunning =
    simulationJob?.status === "queued" || simulationJob?.status === "running";

  useEffect(() => {
    if (selectedProjectId && projectFilter !== "all") {
      setProjectFilter(selectedProjectId);
    }
  }, [projectFilter, selectedProjectId]);

  useEffect(() => {
    if (!simulationJob || !isSimulationRunning) return;

    let isCancelled = false;
    const intervalId = window.setInterval(() => {
      fetchControlEventSimulation(simulationJob.job_id)
        .then((job) => {
          if (isCancelled) return;
          setSimulationJob(job);
          if (job.status === "completed" || job.status === "failed") {
            setProjectFilter("all");
            setUnreadOnly(false);
            void queryClient.invalidateQueries({ queryKey: ["notifications"] });
          }
        })
        .catch((error) => {
          if (isCancelled) return;
          setSimulationError(formatSimulationError(error));
        });
    }, 900);

    return () => {
      isCancelled = true;
      window.clearInterval(intervalId);
    };
  }, [isSimulationRunning, queryClient, simulationJob]);

  function handleProjectChange(value: string) {
    setProjectFilter(value);
    if (value !== "all") {
      onSelectProject(value);
    }
  }

  async function handleStartSimulation() {
    setSimulationError(null);
    try {
      const job = await startControlEventSimulation();
      setSimulationJob(job);
      if (job.status === "completed" || job.status === "failed") {
        setProjectFilter("all");
        setUnreadOnly(false);
        void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      }
    } catch (error) {
      setSimulationError(formatSimulationError(error));
    }
  }

  async function handleClearSimulation() {
    setSimulationError(null);
    setIsClearingSimulation(true);
    try {
      await clearControlEventSimulation();
      setSimulationJob(null);
      setProjectFilter("all");
      setUnreadOnly(false);
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    } catch (error) {
      setSimulationError(formatSimulationError(error));
    } finally {
      setIsClearingSimulation(false);
    }
  }

  return (
    <div className="flex w-full flex-col gap-4 px-1 sm:px-2">
      <Card className="p-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
          <button
            type="button"
            onClick={handleStartSimulation}
            disabled={isSimulationRunning || isClearingSimulation}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 text-sm font-semibold text-emerald-700 shadow-sm transition hover:bg-emerald-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-300 disabled:cursor-not-allowed disabled:opacity-60 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300 dark:hover:bg-emerald-950"
          >
            {isSimulationRunning ? (
              <Loader2 aria-hidden className="size-4 animate-spin" />
            ) : (
              <Play aria-hidden className="size-4" />
            )}
            Запустить симуляцию
          </button>

          <button
            type="button"
            onClick={handleClearSimulation}
            disabled={isSimulationRunning || isClearingSimulation}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            {isClearingSimulation ? (
              <Loader2 aria-hidden className="size-4 animate-spin" />
            ) : (
              <Trash2 aria-hidden className="size-4" />
            )}
            Очистить симуляцию
          </button>

          <label className="sr-only" htmlFor="notification-project-select">
            Фильтр проекта
          </label>
          <select
            id="notification-project-select"
            value={projectFilter}
            onChange={(event) => handleProjectChange(event.target.value)}
            className="h-10 min-w-0 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-800 shadow-sm outline-none transition hover:bg-slate-50 focus:border-slate-400 focus:ring-2 focus:ring-slate-200 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800 dark:focus:border-slate-600 dark:focus:ring-slate-800 sm:min-w-80"
          >
            <option value="all">Все проекты</option>
            {projects.map((project) => (
              <option key={project.project_id} value={project.project_id}>
                {project.project_name}
              </option>
            ))}
          </select>

          <label className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200">
            <input
              type="checkbox"
              checked={unreadOnly}
              onChange={(event) => setUnreadOnly(event.target.checked)}
              className="size-4 rounded border-slate-300 text-slate-900 focus:ring-slate-400 dark:border-slate-700"
            />
            Непрочитанные
          </label>

          <button
            type="button"
            title="Обновить уведомления"
            onClick={() => {
              void notificationsQuery.refetch();
            }}
            className="inline-grid size-10 place-items-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            <RefreshCw
              aria-hidden
              className={`size-4 ${notificationsQuery.isFetching ? "animate-spin" : ""}`}
            />
            <span className="sr-only">Обновить уведомления</span>
          </button>
        </div>
      </Card>

      {notificationsQuery.isPending ? (
        <LoadingState label="Загрузка уведомлений…" />
      ) : notificationsQuery.isError ? (
        <ErrorState
          message="Не удалось загрузить уведомления."
          onRetry={() => {
            void notificationsQuery.refetch();
          }}
        />
      ) : (
        <>
          {notificationsQuery.data.items.length ? (
            <div className="space-y-3">
              {notificationsQuery.data.items.map((notification) => (
                <NotificationRow
                  key={notification.id}
                  notification={notification}
                  isOpen={openNotificationId === notification.id}
                  isMarkingRead={
                    markReadMutation.isPending &&
                    markReadMutation.variables === notification.id
                  }
                  onToggleOpen={(notificationId) => {
                    setOpenNotificationId((current) =>
                      current === notificationId ? null : notificationId,
                    );
                  }}
                  onMarkRead={(notificationId) => {
                    markReadMutation.mutate(notificationId);
                  }}
                  onSelectProject={(projectId) => {
                    setProjectFilter(projectId);
                    onSelectProject(projectId);
                  }}
                />
              ))}
            </div>
          ) : (
            <Card>
              <EmptyState message="Уведомлений по выбранному фильтру нет" />
            </Card>
          )}
        </>
      )}
      {simulationError ? (
        <Card className="border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/30 dark:text-rose-200">
          {simulationError}
        </Card>
      ) : null}
      {simulationJob ? (
        <SimulationModal
          job={simulationJob}
          onClose={() => setSimulationJob(null)}
        />
      ) : null}
    </div>
  );
}

function SimulationModal({
  job,
  onClose,
}: {
  job: SimulationJob;
  onClose: () => void;
}) {
  const isRunning = job.status === "queued" || job.status === "running";
  const progress =
    job.total_events > 0
      ? Math.round((job.processed_events / job.total_events) * 100)
      : 0;
  const currentStage = getCurrentSimulationStage(job);
  const currentStageIndex = currentStage
    ? Math.max(0, job.stages.findIndex((stage) => stage === currentStage))
    : -1;
  const successfulResults = job.results.filter((result) => !result.error);
  const failedResults = job.results.filter((result) => result.error);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="simulation-modal-title"
      className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4 backdrop-blur-sm"
    >
      <div className="flex max-h-[86vh] w-full max-w-3xl flex-col rounded-xl border border-slate-200 bg-white shadow-2xl shadow-slate-950/20 dark:border-slate-800 dark:bg-slate-950">
        <div className="border-b border-slate-100 p-4 dark:border-slate-800">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                {isRunning ? (
                  <Loader2
                    aria-hidden
                    className="size-4 animate-spin text-emerald-600 dark:text-emerald-300"
                  />
                ) : job.status === "failed" ? (
                  <XCircle
                    aria-hidden
                    className="size-4 text-rose-600 dark:text-rose-300"
                  />
                ) : (
                  <CheckCircle2
                    aria-hidden
                    className="size-4 text-emerald-600 dark:text-emerald-300"
                  />
                )}
                <h2
                  id="simulation-modal-title"
                  className="text-base font-semibold text-slate-950 dark:text-slate-50"
                >
                  Симуляция control events
                </h2>
              </div>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                {job.processed_events}/{job.total_events || "?"} событий обработано
                {job.failed_events ? `, ошибок: ${job.failed_events}` : ""}
              </p>
            </div>

            {!isRunning ? (
              <button
                type="button"
                onClick={onClose}
                className="inline-flex h-9 items-center justify-center rounded-lg border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                Закрыть
              </button>
            ) : null}
          </div>

          <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
            <div
              className="h-full rounded-full bg-emerald-500 transition-all duration-500"
              style={{ width: `${Math.max(progress, isRunning ? 8 : 0)}%` }}
            />
          </div>
        </div>

        <div className="min-h-0 flex-1 p-4">
          {job.status === "completed" ? (
            <SimulationResultScreen
              createdCount={successfulResults.length}
              failedCount={failedResults.length}
              outputFile={job.output_file}
            />
          ) : job.status === "failed" ? (
            <SimulationFailureScreen error={job.error} stage={currentStage} />
          ) : currentStage ? (
            <SimulationStageScreen
              stage={currentStage}
              stageIndex={currentStageIndex}
              stagesCount={job.stages.length}
            />
          ) : (
            <SimulationStageScreen
              stage={{
                id: "queued",
                label: "Готовим симуляцию",
                detail: "Ожидаем запуск обработки событий.",
                status: "running",
                timestamp: "",
              }}
              stageIndex={0}
              stagesCount={1}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function SimulationStageScreen({
  stage,
  stageIndex,
  stagesCount,
}: {
  stage: SimulationStage;
  stageIndex: number;
  stagesCount: number;
}) {
  return (
    <div className="grid min-h-72 place-items-center rounded-xl border border-slate-200 bg-slate-50 p-6 text-center dark:border-slate-800 dark:bg-slate-900/60">
      <div
        className={`grid size-14 place-items-center rounded-full ${stageStatusClass(
          stage.status,
        )}`}
      >
        {stage.status === "running" ? (
          <Loader2 aria-hidden className="size-7 animate-spin" />
        ) : stage.status === "error" ? (
          <XCircle aria-hidden className="size-7" />
        ) : (
          <CheckCircle2 aria-hidden className="size-7" />
        )}
      </div>
      <div className="mt-5 max-w-xl">
        <div className="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
          Этап {Math.max(stageIndex + 1, 1)} из {Math.max(stagesCount, 1)}
        </div>
        <div className="mt-2 text-xl font-semibold text-slate-950 dark:text-slate-50">
          {stage.label}
        </div>
        <div className="mt-3 min-h-12 text-sm leading-6 text-slate-500 dark:text-slate-400">
          {stage.detail ?? "Выполняем действие симуляции."}
        </div>
      </div>
    </div>
  );
}

function SimulationResultScreen({
  createdCount,
  failedCount,
  outputFile,
}: {
  createdCount: number;
  failedCount: number;
  outputFile: string | null;
}) {
  return (
    <div className="grid min-h-72 place-items-center rounded-xl border border-emerald-200 bg-emerald-50 p-6 text-center dark:border-emerald-900/60 dark:bg-emerald-950/20">
      <div className="grid size-14 place-items-center rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-950/70 dark:text-emerald-300">
        <CheckCircle2 aria-hidden className="size-7" />
      </div>
      <div className="mt-5 max-w-xl">
        <div className="text-xs font-semibold uppercase text-emerald-700 dark:text-emerald-300">
          Симуляция завершена
        </div>
        <div className="mt-2 text-xl font-semibold text-slate-950 dark:text-slate-50">
          Создано уведомлений: {createdCount}
        </div>
        <div className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-300">
          {failedCount
            ? `Событий с ошибкой: ${failedCount}. Проверьте журнал agents API.`
            : "Все события обработаны, список уведомлений обновлён."}
        </div>
        {outputFile ? (
          <div className="mt-4 rounded-lg bg-white px-3 py-2 text-xs text-slate-500 dark:bg-slate-900 dark:text-slate-400">
            Результат сохранён: {outputFile}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function SimulationFailureScreen({
  error,
  stage,
}: {
  error: string | null;
  stage: SimulationStage | undefined;
}) {
  return (
    <div className="grid min-h-72 place-items-center rounded-xl border border-rose-200 bg-rose-50 p-6 text-center dark:border-rose-900/70 dark:bg-rose-950/20">
      <div className="grid size-14 place-items-center rounded-full bg-rose-100 text-rose-700 dark:bg-rose-950/70 dark:text-rose-300">
        <XCircle aria-hidden className="size-7" />
      </div>
      <div className="mt-5 max-w-xl">
        <div className="text-xs font-semibold uppercase text-rose-700 dark:text-rose-300">
          Симуляция остановлена
        </div>
        <div className="mt-2 text-xl font-semibold text-slate-950 dark:text-slate-50">
          {stage?.label ?? "Ошибка обработки"}
        </div>
        <div className="mt-3 text-sm leading-6 text-rose-700 dark:text-rose-200">
          {error ?? stage?.detail ?? "Не удалось завершить симуляцию."}
        </div>
      </div>
    </div>
  );
}

function getCurrentSimulationStage(job: SimulationJob) {
  const runningStage = [...job.stages].reverse().find((stage) => stage.status === "running");
  if (runningStage) return runningStage;
  const errorStage = [...job.stages].reverse().find((stage) => stage.status === "error");
  if (errorStage) return errorStage;
  const completedStage = [...job.stages].reverse().find((stage) => stage.status === "success");
  if (completedStage) return completedStage;
  return job.stages[0];
}

function stageStatusClass(status: SimulationStageStatus): string {
  if (status === "running") {
    return "bg-emerald-50 text-emerald-600 dark:bg-emerald-950/50 dark:text-emerald-300";
  }
  if (status === "error") {
    return "bg-rose-50 text-rose-600 dark:bg-rose-950/50 dark:text-rose-300";
  }
  if (status === "pending") {
    return "bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-500";
  }
  return "bg-sky-50 text-sky-600 dark:bg-sky-950/50 dark:text-sky-300";
}

function formatSimulationError(error: unknown) {
  if (error instanceof Error && error.message) {
    return `Симуляция недоступна: ${error.message}`;
  }
  return "Симуляция недоступна. Проверьте agents API и настройки LLM.";
}

function NotificationRow({
  notification,
  isOpen,
  isMarkingRead,
  onToggleOpen,
  onMarkRead,
  onSelectProject,
}: {
  notification: InternalNotification;
  isOpen: boolean;
  isMarkingRead: boolean;
  onToggleOpen: (notificationId: string) => void;
  onMarkRead: (notificationId: string) => void;
  onSelectProject: (projectId: string) => void;
}) {
  return (
    <Card className="overflow-hidden p-0">
      <button
        type="button"
        onClick={() => onToggleOpen(notification.id)}
        className={`grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-4 py-3 text-left transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:hover:bg-slate-900/60 ${
          notification.is_read ? "bg-white dark:bg-slate-950/30" : "bg-sky-50/60 dark:bg-sky-950/20"
        }`}
      >
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2">
            {!notification.is_read ? (
              <span className="size-2 shrink-0 rounded-full bg-sky-500" />
            ) : null}
            <span
              className={`truncate text-sm ${
                notification.is_read
                  ? "font-medium text-slate-700 dark:text-slate-300"
                  : "font-semibold text-slate-950 dark:text-slate-50"
              }`}
            >
              {notification.title}
            </span>
          </div>
          <div className="mt-1 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
            <span className="truncate">
              {notification.project_name ?? notification.project_id}
            </span>
            <span>{formatNotificationDate(notification.created_at)}</span>
            <Badge tone={severityTone[notification.severity]}>
              {severityLabel[notification.severity]}
            </Badge>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
            <Badge tone={notification.is_read ? "neutral" : "info"}>
              {notification.is_read ? "Прочитано" : "Новое"}
            </Badge>
          <span className="text-xs text-slate-400 dark:text-slate-500">
            {isOpen ? "Свернуть" : "Открыть"}
          </span>
        </div>
      </button>

      {isOpen ? (
        <div className="grid gap-4 border-t border-slate-100 p-4 dark:border-slate-800 lg:grid-cols-[minmax(0,1fr)_200px]">
          <div className="min-w-0">
            <p className="text-sm leading-6 text-slate-600 dark:text-slate-300">
              {notification.body}
            </p>

            {notification.action_items.length ? (
              <ul className="mt-3 space-y-2">
                {notification.action_items.map((item) => (
                  <li
                    key={item}
                    className="flex gap-2 text-sm text-slate-600 dark:text-slate-300"
                  >
                    <CheckCircle2
                      aria-hidden
                      className="mt-0.5 size-4 shrink-0 text-emerald-500"
                    />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            ) : null}

            <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-500 dark:bg-slate-950/50 dark:text-slate-400">
              {notification.reason}
            </div>
          </div>

          <div className="flex flex-col justify-between gap-3 border-t border-slate-100 pt-3 text-sm dark:border-slate-800 lg:border-l lg:border-t-0 lg:pl-4 lg:pt-0">
            <div className="space-y-2">
              <button
                type="button"
                onClick={() => onSelectProject(notification.project_id)}
                className="block max-w-full truncate text-left font-semibold text-slate-950 transition hover:text-sky-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:text-slate-50 dark:hover:text-sky-300"
                title={notification.project_name ?? notification.project_id}
              >
                {notification.project_name ?? notification.project_id}
              </button>
              <div className="text-xs text-slate-500 dark:text-slate-400">
                Создано: {formatNotificationDate(notification.created_at)}
              </div>
              {notification.as_of_date ? (
                <div className="text-xs text-slate-500 dark:text-slate-400">
                  Срез: {formatDate(notification.as_of_date)}
                </div>
              ) : null}
              {notification.trigger_event_label ? (
                <div className="rounded-lg bg-slate-50 px-2 py-1.5 text-xs leading-5 text-slate-600 dark:bg-slate-950/50 dark:text-slate-300">
                  После события: {notification.trigger_event_label}
                </div>
              ) : null}
              {notification.recipient_hint ? (
                <div className="text-xs text-slate-500 dark:text-slate-400">
                  {notification.recipient_hint}
                </div>
              ) : null}
              {notification.requires_acknowledgement ? (
                <Badge tone="warning">Нужно подтверждение</Badge>
              ) : null}
            </div>

            <div className="text-xs text-slate-400 dark:text-slate-500">
              {notification.source}
            </div>

            {!notification.is_read ? (
              <button
                type="button"
                disabled={isMarkingRead}
                onClick={() => onMarkRead(notification.id)}
                className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                <CheckCheck aria-hidden className="size-3.5" />
                {isMarkingRead ? "Сохраняю" : "Прочитано"}
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
    </Card>
  );
}

function formatNotificationDate(value: string): string {
  if (value.includes("T")) {
    const [datePart, timePart] = value.split("T");
    return `${formatDate(datePart)} ${timePart.slice(0, 5)}`;
  }
  return formatDate(value);
}
