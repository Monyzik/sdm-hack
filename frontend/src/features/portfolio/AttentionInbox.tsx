import { BellDot, ChevronRight, CircleAlert } from "lucide-react";

import type { PortfolioAttentionSummary } from "../../api/types";
import { Badge, Card, EmptyState } from "../../components/ui";
import type { Tone } from "../../lib/risk";

interface AttentionInboxProps {
  attention: PortfolioAttentionSummary;
  onSelectProject: (projectId: string) => void;
}

const severityTone: Record<string, Tone> = {
  critical: "danger",
  warning: "warning",
  info: "info",
};

export function AttentionInbox({
  attention,
  onSelectProject,
}: AttentionInboxProps) {
  return (
    <Card>
      <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-4 py-3 dark:border-slate-800">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-950 dark:text-slate-50">
            <BellDot aria-hidden className="size-4 text-slate-400" />
            Что изменилось
          </h2>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            За {attention.lookback_days} дней
          </p>
        </div>
        <Badge tone={attention.critical_signals_count ? "danger" : "neutral"}>
          {attention.critical_signals_count} крит.
        </Badge>
      </div>

      {attention.projects_to_watch.length ? (
        <ul className="divide-y divide-slate-100 dark:divide-slate-800">
          {attention.projects_to_watch.slice(0, 5).map((project) => (
            <li key={project.project_id}>
              <button
                type="button"
                onClick={() => onSelectProject(project.project_id)}
                className="flex w-full items-start gap-3 px-4 py-3 text-left transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:hover:bg-slate-800/50"
              >
                <CircleAlert
                  aria-hidden
                  className="mt-0.5 size-4 shrink-0 text-amber-500"
                />
                <span className="min-w-0 flex-1">
                  <span className="flex items-start justify-between gap-2">
                    <span className="line-clamp-1 text-sm font-semibold text-slate-950 dark:text-slate-50">
                      {project.project_name}
                    </span>
                    <Badge tone="warning">{project.urgent_signals_count}</Badge>
                  </span>
                  <span className="mt-1 block text-xs font-medium text-slate-500 dark:text-slate-400">
                    {project.top_reason}
                  </span>
                  <span className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600 dark:text-slate-300">
                    {project.next_action}
                  </span>
                </span>
                <ChevronRight
                  aria-hidden
                  className="mt-1 size-4 shrink-0 text-slate-400"
                />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState message="Новых сигналов по портфелю нет" />
      )}

      {attention.signals.length ? (
        <div className="border-t border-slate-100 p-4 dark:border-slate-800">
          <div className="mb-2 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
            Последние события
          </div>
          <div className="space-y-2">
            {attention.signals.slice(0, 4).map((signal) => (
              <button
                key={signal.id}
                type="button"
                onClick={() => onSelectProject(signal.project_id)}
                className="flex w-full items-start justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-left transition hover:bg-white focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:border-slate-800 dark:bg-slate-950/40 dark:hover:bg-slate-900"
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium text-slate-900 dark:text-slate-100">
                    {signal.title}
                  </span>
                  <span className="mt-1 block truncate text-xs text-slate-500 dark:text-slate-400">
                    {signal.project_name}
                  </span>
                </span>
                <Badge tone={severityTone[signal.severity] ?? "neutral"}>
                  {signal.severity === "critical" ? "крит." : "важно"}
                </Badge>
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </Card>
  );
}
