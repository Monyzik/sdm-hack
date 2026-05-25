import type { ReactNode } from "react";

import type { TaskSignal } from "../../../api/types";
import { Badge, EmptyState, Panel } from "../../../components/ui";
import { formatDate, formatDays } from "../../../lib/format";
import { severityTone, statusLabel } from "../../../lib/risk";

interface TasksPanelProps {
  title: string;
  icon: ReactNode;
  tasks: TaskSignal[];
  emptyMessage: string;
}

function TaskItem({ task }: { task: TaskSignal }) {
  return (
    <li className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="line-clamp-2 text-sm font-semibold text-slate-900 dark:text-slate-100">
            {task.title}
          </p>
          <p className="mt-0.5 truncate text-xs text-slate-500 dark:text-slate-400">
            {task.external_id} · {task.assignee_name}
          </p>
        </div>
        {task.overdue_days > 0 ? (
          <Badge tone="danger">{formatDays(task.overdue_days)}</Badge>
        ) : null}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Badge tone={severityTone(task.priority)}>{statusLabel(task.priority)}</Badge>
        <Badge tone={severityTone(task.status)}>{statusLabel(task.status)}</Badge>
        <span className="text-xs text-slate-500 dark:text-slate-400">
          Срок: {formatDate(task.planned_due_date)}
        </span>
      </div>
      {task.blocker_reason ? (
        <p className="mt-2 rounded-md bg-rose-50 px-2 py-1.5 text-sm text-rose-800 dark:bg-rose-950/40 dark:text-rose-200">
          {task.blocker_reason}
        </p>
      ) : null}
    </li>
  );
}

/** Список задач: заблокированные и просроченные. */
export function TasksPanel({
  title,
  icon,
  tasks,
  emptyMessage,
}: TasksPanelProps) {
  return (
    <Panel
      title={title}
      icon={icon}
      action={
        tasks.length > 0 ? (
          <Badge tone="neutral">{tasks.length}</Badge>
        ) : undefined
      }
    >
      {tasks.length === 0 ? (
        <EmptyState message={emptyMessage} />
      ) : (
        <ul className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          {tasks.map((task) => (
            <TaskItem key={task.id} task={task} />
          ))}
        </ul>
      )}
    </Panel>
  );
}
