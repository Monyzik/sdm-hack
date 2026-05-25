import {
  Bell,
  BellDot,
  CheckCircle2,
  CheckCheck,
  CircleAlert,
  Clock3,
  RefreshCw,
} from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import type {
  InternalNotification,
  NotificationSeverity,
  PortfolioProjectSummary,
} from "../../api/types";
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
  asOfDate: string;
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
  asOfDate,
  onSelectProject,
}: NotificationsPageProps) {
  const [projectFilter, setProjectFilter] = useState<ProjectFilter>(
    selectedProjectId ?? "all",
  );
  const [unreadOnly, setUnreadOnly] = useState(false);
  const projectId = projectFilter === "all" ? null : projectFilter;
  const notificationsQuery = useNotifications(asOfDate, projectId, unreadOnly);
  const markReadMutation = useMarkNotificationRead();

  useEffect(() => {
    if (selectedProjectId && projectFilter !== "all") {
      setProjectFilter(selectedProjectId);
    }
  }, [projectFilter, selectedProjectId]);

  const selectedProjectName = useMemo(() => {
    if (projectFilter === "all") return "Все проекты";
    return (
      projects.find((project) => project.project_id === projectFilter)
        ?.project_name ?? projectFilter
    );
  }, [projectFilter, projects]);

  function handleProjectChange(value: string) {
    setProjectFilter(value);
    if (value !== "all") {
      onSelectProject(value);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-4">
      <Card className="p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-950 dark:text-slate-50">
              <BellDot aria-hidden className="size-4 text-slate-400" />
              Центр уведомлений
            </div>
            <p className="mt-1 max-w-2xl text-sm text-slate-500 dark:text-slate-400">
              Внутренние уведомления monitoring graph на выбранную дату среза.
            </p>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
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
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <SummaryTile
              icon={<Bell className="size-4" />}
              label="Всего"
              value={notificationsQuery.data.total}
              hint={selectedProjectName}
              tone="neutral"
            />
            <SummaryTile
              icon={<CircleAlert className="size-4" />}
              label="Непрочитанные"
              value={notificationsQuery.data.unread_count}
              hint={unreadOnly ? "активный фильтр" : "требуют внимания"}
              tone={
                notificationsQuery.data.unread_count ? "warning" : "success"
              }
            />
            <SummaryTile
              icon={<Clock3 className="size-4" />}
              label="Показано"
              value={notificationsQuery.data.items.length}
              hint="последние сверху"
              tone="info"
            />
          </div>

          {notificationsQuery.data.items.length ? (
            <div className="space-y-3">
              {notificationsQuery.data.items.map((notification) => (
                <NotificationRow
                  key={notification.id}
                  notification={notification}
                  isMarkingRead={
                    markReadMutation.isPending &&
                    markReadMutation.variables === notification.id
                  }
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
    </div>
  );
}

function SummaryTile({
  icon,
  label,
  value,
  hint,
  tone,
}: {
  icon: ReactNode;
  label: string;
  value: number;
  hint: string;
  tone: Tone;
}) {
  const toneClass: Record<Tone, string> = {
    neutral: "text-slate-500 dark:text-slate-400",
    danger: "text-rose-600 dark:text-rose-300",
    warning: "text-amber-600 dark:text-amber-300",
    success: "text-emerald-600 dark:text-emerald-300",
    info: "text-sky-600 dark:text-sky-300",
  };

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-medium uppercase text-slate-500 dark:text-slate-400">
          {label}
        </span>
        <span aria-hidden className={toneClass[tone]}>
          {icon}
        </span>
      </div>
      <div className="mt-2 text-2xl font-semibold tabular-nums text-slate-950 dark:text-slate-50">
        {value}
      </div>
      <div className="mt-1 truncate text-xs text-slate-500 dark:text-slate-400">
        {hint}
      </div>
    </Card>
  );
}

function NotificationRow({
  notification,
  isMarkingRead,
  onMarkRead,
  onSelectProject,
}: {
  notification: InternalNotification;
  isMarkingRead: boolean;
  onMarkRead: (notificationId: string) => void;
  onSelectProject: (projectId: string) => void;
}) {
  return (
    <Card className="p-4">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_180px]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={severityTone[notification.severity]}>
              {severityLabel[notification.severity]}
            </Badge>
            <Badge tone={notification.is_read ? "neutral" : "info"}>
              {notification.is_read ? "Прочитано" : "Новое"}
            </Badge>
            {notification.requires_acknowledgement ? (
              <Badge tone="warning">Нужно подтверждение</Badge>
            ) : null}
          </div>

          <h2 className="mt-3 text-base font-semibold text-slate-950 dark:text-slate-50">
            {notification.title}
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">
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
              {formatNotificationDate(notification.created_at)}
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
