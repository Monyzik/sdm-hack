import { Activity, AlertTriangle, CheckCircle2, Clock3, ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";

import type { ProjectSummary } from "../../api/types";
import { Card, RiskBadge } from "../../components/ui";
import type { Tone } from "../../lib/risk";

/**
 * Шапка карточки проекта: название, зона риска, приоритет и главные метрики.
 */
export function ProjectHeader({ project }: { project: ProjectSummary }) {
  const status = humanProjectStatus(project);
  const budgetDeviation = project.budget
    ? Math.round(project.budget.budget_deviation_percent)
    : null;
  const mainProblem = project.key_signals[0] ?? "Критичных сигналов нет";

  return (
    <Card className="p-5">
      <div className="flex flex-col gap-5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-2xl font-semibold text-slate-950 dark:text-slate-50">
              {project.project_name}
            </h2>
            <RiskBadge level={project.risk_level} />
          </div>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Статус: {status.label} · Приоритет: {project.priority} · Готовность:{" "}
            {Math.round(project.completion_percent)}%
          </p>
          <p className="mt-4 max-w-4xl text-sm leading-6 text-slate-700 dark:text-slate-300">
            Главная проблема:{" "}
            <span className="font-medium text-slate-950 dark:text-slate-50">
              {mainProblem}
            </span>
          </p>
        </div>

        <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
          <ProjectKpi
            label="Health Score"
            value={`${project.project_health_score}/100`}
            hint={status.label}
            tone={status.tone}
            icon={<Activity className="size-4" />}
          />
          <ProjectKpi
            label="Готовность"
            value={`${Math.round(project.completion_percent)}%`}
            icon={<CheckCircle2 className="size-4" />}
            hint={`${project.completed_tasks_count} из ${project.total_tasks_count} задач`}
          />
          <ProjectKpi
            label="Блокеры"
            value={project.blocked_tasks_count}
            tone={project.blocked_tasks_count ? "danger" : "neutral"}
            hint={
              project.critical_path_delay_days > 0
                ? "есть влияние на путь"
                : "без критичного пути"
            }
            icon={<AlertTriangle className="size-4" />}
          />
          <ProjectKpi
            label="Просрочки"
            value={project.overdue_tasks_count}
            tone={project.overdue_tasks_count ? "danger" : "neutral"}
            hint={
              project.critical_path_delay_days > 0
                ? `путь +${project.critical_path_delay_days} дн.`
                : "сроки под контролем"
            }
            icon={<Clock3 className="size-4" />}
          />
          <ProjectKpi
            label={budgetDeviation === null ? "Риски" : "Бюджет"}
            value={
              budgetDeviation === null
                ? project.high_risk_count
                : `${budgetDeviation > 0 ? "+" : ""}${budgetDeviation}%`
            }
            tone={
              budgetDeviation !== null && budgetDeviation > 0
                ? "danger"
                : project.high_risk_count
                  ? "warning"
                  : "neutral"
            }
            hint={`${project.high_risk_count} риска`}
            icon={<ShieldAlert className="size-4" />}
          />
        </div>
      </div>
    </Card>
  );
}

function humanProjectStatus(project: ProjectSummary): {
  label: string;
  value: string;
  tone: Tone;
} {
  if (project.risk_level === "red") {
    return {
      label: "требуется решение",
      value: "решение",
      tone: "danger",
    };
  }
  if (project.risk_level === "yellow") {
    return {
      label: "под наблюдением",
      value: "контроль",
      tone: "warning",
    };
  }
  return {
    label: "в штатном режиме",
    value: "норма",
    tone: "success",
  };
}

function ProjectKpi({
  label,
  value,
  hint,
  tone = "neutral",
  icon,
}: {
  label: string;
  value: string | number;
  hint?: string;
  tone?: Tone;
  icon?: ReactNode;
}) {
  const dotClass = {
    neutral: "bg-slate-300 dark:bg-slate-600",
    danger: "bg-rose-500",
    warning: "bg-amber-500",
    success: "bg-emerald-500",
    info: "bg-sky-500",
  }[tone];

  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 dark:border-slate-800 dark:bg-slate-950/30">
      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400">
          <span className={`size-1.5 shrink-0 rounded-full ${dotClass}`} />
          <span className="truncate">{label}</span>
        </span>
        {icon ? <span className="shrink-0 text-slate-400">{icon}</span> : null}
      </div>
      <div className="mt-2 text-xl font-semibold tabular-nums text-slate-950 dark:text-slate-50">
        {value}
      </div>
      {hint ? (
        <div className="mt-0.5 truncate text-xs text-slate-500 dark:text-slate-400">
          {hint}
        </div>
      ) : null}
    </div>
  );
}
