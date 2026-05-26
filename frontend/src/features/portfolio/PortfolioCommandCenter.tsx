import { AlertTriangle, Banknote, Clock3, ShieldAlert } from "lucide-react";
import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";

import { fetchProjectSummary } from "../../api/client";
import { queryKeys } from "../../hooks/queryKeys";
import type {
  PortfolioAttentionProject,
  PortfolioAttentionSummary,
  PortfolioProjectSummary,
  PortfolioSummary,
  ProjectSummary,
} from "../../api/types";
import { AS_OF_DATE } from "../../lib/constants";
import { formatPercent } from "../../lib/format";
import type { RiskLevel } from "../../api/types";
import { riskLabel } from "../../lib/risk";
import { Badge, Card } from "../../components/ui";
import type { ReactNode } from "react";

interface PortfolioCommandCenterProps {
  portfolio: PortfolioSummary;
  attention: PortfolioAttentionSummary | undefined;
  onSelectProject: (projectId: string) => void;
}

interface Driver {
  label: string;
  value: number;
  hint: string;
  accent: DriverAccent;
  icon: ReactNode;
}

interface TaskDistribution {
  totalTasks: number;
  normalTasks: number;
  overdueTasks: number;
  blockedTasks: number;
  isReady: boolean;
  hasErrors: boolean;
  isLoading: boolean;
}

type DriverAccent = "amber" | "rose" | "sky" | "violet";
type SummaryTone = "danger" | "warning" | "neutral";

export function PortfolioCommandCenter({
  portfolio,
  attention,
  onSelectProject,
}: PortfolioCommandCenterProps) {
  const totalBlocked = portfolio.projects.reduce(
    (sum, project) => sum + project.blocked_tasks_count,
    0,
  );
  const totalOverdue = portfolio.projects.reduce(
    (sum, project) => sum + project.overdue_tasks_count,
    0,
  );
  const totalHighRisks = portfolio.projects.reduce(
    (sum, project) => sum + project.high_risk_count,
    0,
  );
  const budgetRiskProjects = portfolio.projects.filter(
    (project) => (project.budget_deviation_percent ?? 0) > 10,
  ).length;
  const focusProjects = buildFocusProjects(portfolio.projects, attention);
  const projectDetailQueries = useQueries({
    queries: portfolio.projects.map((project) => ({
      queryKey: queryKeys.project(project.project_id, AS_OF_DATE),
      queryFn: ({ signal }: { signal?: AbortSignal }) =>
        fetchProjectSummary(project.project_id, AS_OF_DATE, signal),
      staleTime: 30_000,
    })),
  });
  const projectDetailData = useMemo(
    () =>
      projectDetailQueries
        .map((query) => query.data)
        .filter((value): value is ProjectSummary => Boolean(value)),
    [projectDetailQueries],
  );
  const taskDistribution = useMemo<TaskDistribution>(() => {
    let totalTasks = 0;
    const overdueTaskIds = new Set<string>();
    const blockedTaskIds = new Set<string>();

    for (const summary of projectDetailData) {
      totalTasks += summary.total_tasks_count;
      const prefix = `${summary.project_id}:`;
      summary.overdue_tasks.forEach((task) => {
        overdueTaskIds.add(`${prefix}${task.id}`);
      });
      summary.blocked_tasks.forEach((task) => {
        blockedTaskIds.add(`${prefix}${task.id}`);
      });
    }

    const overlap = [...overdueTaskIds].reduce(
      (sum, taskId) => sum + (blockedTaskIds.has(taskId) ? 1 : 0),
      0,
    );
    const overdueExclusive = Math.max(0, overdueTaskIds.size - overlap);
    const unionSize = overdueTaskIds.size + blockedTaskIds.size - overlap;
    const normal = Math.max(totalTasks - unionSize, 0);

    return {
      totalTasks,
      normalTasks: normal,
      overdueTasks: overdueExclusive,
      blockedTasks: blockedTaskIds.size,
      isReady: projectDetailData.length === portfolio.projects.length,
      hasErrors: projectDetailQueries.some((query) => query.isError),
      isLoading: projectDetailQueries.some((query) => query.isPending),
    };
  }, [projectDetailData, portfolio.projects.length, projectDetailQueries]);
  const drivers: Driver[] = [
    {
      label: "Просрочены",
      value: totalOverdue,
      hint: "задач вышли за срок",
      accent: "amber",
      icon: <Clock3 className="size-4" />,
    },
    {
      label: "Блокируют",
      value: totalBlocked,
      hint: "задач остановлены",
      accent: "rose",
      icon: <AlertTriangle className="size-4" />,
    },
    {
      label: "Высокие риски",
      value: totalHighRisks,
      hint: "высоких и критичных",
      accent: "sky",
      icon: <ShieldAlert className="size-4" />,
    },
    {
      label: "Бюджет > 10%",
      value: budgetRiskProjects,
      hint: "проектов выше плана",
      accent: "violet",
      icon: <Banknote className="size-4" />,
    },
  ];

  return (
    <div className="space-y-4">
      <ExecutiveSummary
        portfolio={portfolio}
        attention={attention}
        totalBlocked={totalBlocked}
        budgetRiskProjects={budgetRiskProjects}
      />

      <InterventionList
        projects={focusProjects}
        onSelectProject={onSelectProject}
      />

      <div className="grid gap-4 xl:grid-cols-2">
        {taskDistribution.isReady && !taskDistribution.hasErrors ? (
          <TaskStateSummary distribution={taskDistribution} />
        ) : taskDistribution.isLoading ? (
          <Card className="p-4 text-sm text-slate-500 dark:text-slate-400">
            Загрузка состояния задач...
          </Card>
        ) : (
          <Card className="border-rose-200 bg-rose-50 p-4 text-sm text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-200">
            Не удалось загрузить детальные задачи.
          </Card>
        )}
        <SignalDrivers drivers={drivers} />
      </div>
    </div>
  );
}

function ExecutiveSummary({
  portfolio,
  attention,
  totalBlocked,
  budgetRiskProjects,
}: {
  portfolio: PortfolioSummary;
  attention: PortfolioAttentionSummary | undefined;
  totalBlocked: number;
  budgetRiskProjects: number;
}) {
  const redProjects = portfolio.red_projects_count;
  const criticalSignals = attention?.critical_signals_count ?? 0;
  const newSignals = attention?.total_signals_count ?? 0;
  const lookbackDays = attention?.lookback_days ?? 7;
  const headline =
    redProjects > 0
      ? `${redProjects} ${pluralize(redProjects, ["проект", "проекта", "проектов"])} требуют внимания`
      : "Красных проектов нет";
  const facts = [
    {
      label: "Блокируют",
      value: totalBlocked,
      detail: "задач остановлены",
      tone: totalBlocked ? "danger" : "neutral",
    },
    {
      label: "Бюджет",
      value: budgetRiskProjects,
      detail: "проектов выше плана",
      tone: budgetRiskProjects ? "warning" : "neutral",
    },
    {
      label: "Критичные события",
      value: criticalSignals,
      detail: `за ${lookbackDays} дней`,
      tone: criticalSignals ? "danger" : "neutral",
    },
    {
      label: "Динамика",
      value: newSignals ? `+${newSignals}` : "0",
      detail: "новых сигналов",
      tone: newSignals ? "warning" : "neutral",
    },
  ] satisfies Array<{
    label: string;
    value: number | string;
    detail: string;
    tone: SummaryTone;
  }>;

  return (
    <Card className="p-4">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase text-slate-500 dark:text-slate-400">
            Краткое состояние портфеля
          </p>
          <h2 className="mt-1 text-xl font-semibold text-slate-950 dark:text-slate-50">
            {headline}
          </h2>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {facts.map((fact) => (
            <SummaryFact key={fact.label} fact={fact} />
          ))}
        </div>
      </div>
    </Card>
  );
}

function SummaryFact({
  fact,
}: {
  fact: {
    label: string;
    value: number | string;
    detail: string;
    tone: SummaryTone;
  };
}) {
  return (
    <div className="min-w-36 border-l border-slate-200 pl-3 dark:border-slate-800">
      <p className="text-xs text-slate-500 dark:text-slate-400">{fact.label}</p>
      <p className={`mt-1 text-lg font-semibold tabular-nums ${summaryToneClass[fact.tone]}`}>
        {fact.value}
      </p>
      <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
        {fact.detail}
      </p>
    </div>
  );
}

function InterventionList({
  projects,
  onSelectProject,
}: {
  projects: Array<{
    project: PortfolioProjectSummary;
    attentionProject: PortfolioAttentionProject | undefined;
  }>;
  onSelectProject: (projectId: string) => void;
}) {
  return (
    <Card className="p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-950 dark:text-slate-50">
            Требуют решения сегодня
          </h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Проекты, где есть риск для сроков, бюджета или критичного пути.
          </p>
        </div>
        <Badge tone={projects.length ? "warning" : "neutral"}>
          {projects.length} в фокусе
        </Badge>
      </div>

      <div className="mt-4 space-y-3">
        {projects.length ? (
          projects.map(({ project, attentionProject }) => (
            <InterventionItem
              key={project.project_id}
              project={project}
              attentionProject={attentionProject}
              onSelectProject={onSelectProject}
            />
          ))
        ) : (
          <p className="rounded-lg bg-slate-50 px-3 py-6 text-center text-sm text-slate-500 dark:bg-slate-950/40 dark:text-slate-400">
            На сегодня нет проектов, требующих отдельного решения.
          </p>
        )}
      </div>
    </Card>
  );
}

function InterventionItem({
  project,
  attentionProject,
  onSelectProject,
}: {
  project: PortfolioProjectSummary;
  attentionProject: PortfolioAttentionProject | undefined;
  onSelectProject: (projectId: string) => void;
}) {
  const reason =
    attentionProject?.top_reason ??
    project.top_signals[0] ??
    "Проверить проектные сигналы";
  const nextAction =
    attentionProject?.next_action ??
    buildProjectNextAction(project);
  const signalCount =
    attentionProject?.urgent_signals_count ??
    project.blocked_tasks_count + project.overdue_tasks_count + project.high_risk_count;

  return (
    <article className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-950/30">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span
              aria-hidden
              className={`size-2.5 rounded-full ${riskDotClass[project.risk_level]}`}
            />
            <h3 className="text-base font-semibold text-slate-950 dark:text-slate-50">
              {project.project_name}
            </h3>
            <span className="text-xs text-slate-500 dark:text-slate-400">
              {project.priority}
            </span>
          </div>
          <p className="mt-2 text-sm font-medium text-slate-800 dark:text-slate-200">
            {reason}
          </p>
          <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">
            {nextAction}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2 lg:justify-end">
          <Badge tone={project.risk_level === "red" ? "danger" : "warning"}>
            {riskLabel(project.risk_level)}
          </Badge>
          <Badge tone="neutral">{signalCount} сигн.</Badge>
          <button
            type="button"
            onClick={() => onSelectProject(project.project_id)}
            className="rounded-lg bg-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-800 transition hover:bg-slate-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 dark:bg-slate-700 dark:text-slate-100 dark:hover:bg-slate-600"
          >
            Открыть проект
          </button>
        </div>
      </div>
    </article>
  );
}

function TaskStateSummary({ distribution }: { distribution: TaskDistribution }) {
  const segments = [
    {
      label: "В норме",
      value: distribution.normalTasks,
      className: "bg-emerald-500 dark:bg-emerald-400",
      textClassName: "text-emerald-700 dark:text-emerald-300",
    },
    {
      label: "Просрочены",
      value: distribution.overdueTasks,
      className: "bg-amber-500 dark:bg-amber-400",
      textClassName: "text-amber-700 dark:text-amber-300",
    },
    {
      label: "Блокируют",
      value: distribution.blockedTasks,
      className: "bg-rose-500 dark:bg-rose-400",
      textClassName: "text-rose-700 dark:text-rose-300",
    },
  ];

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-950 dark:text-slate-50">
            Состояние задач
          </h2>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            По активным задачам портфеля.
          </p>
        </div>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {segments.map((segment) => (
          <TaskStateMetric
            key={segment.label}
            segment={segment}
            total={distribution.totalTasks}
          />
        ))}
      </div>
      <div className="mt-4 flex h-3 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        {segments.map((segment) => {
          const width = getPercent(segment.value, distribution.totalTasks);
          return (
            <div
              key={segment.label}
              className={segment.className}
              style={{ width: `${width}%` }}
            />
          );
        })}
      </div>
    </Card>
  );
}

function TaskStateMetric({
  segment,
  total,
}: {
  segment: {
    label: string;
    value: number;
    className: string;
    textClassName: string;
  };
  total: number;
}) {
  const percent = getPercent(segment.value, total);

  return (
    <div className="rounded-lg bg-slate-50 px-3 py-3 dark:bg-slate-950/40">
      <div className="flex items-center gap-2">
        <span aria-hidden className={`size-2 rounded-full ${segment.className}`} />
        <span className="text-xs font-medium text-slate-600 dark:text-slate-300">
          {segment.label}
        </span>
      </div>
      <p className={`mt-2 text-2xl font-semibold tabular-nums ${segment.textClassName}`}>
        {formatPercent(percent)}
      </p>
    </div>
  );
}

function SignalDrivers({ drivers }: { drivers: Driver[] }) {
  return (
    <Card className="p-4">
      <h2 className="text-sm font-semibold text-slate-950 dark:text-slate-50">
        Что тянет портфель вниз
      </h2>
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
        Основные причины давления на сроки и бюджет.
      </p>
      <div className="mt-4 space-y-3">
        {drivers.map((driver) => (
          <DriverRow key={driver.label} driver={driver} max={maxDriver(drivers)} />
        ))}
      </div>
    </Card>
  );
}

function DriverRow({ driver, max }: { driver: Driver; max: number }) {
  const width = max > 0 ? Math.max(6, (driver.value / max) * 100) : 0;
  const accent = driverAccentClass[driver.accent];

  return (
    <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3">
      <span className={`grid size-8 place-items-center rounded-lg ${accent.icon}`}>
        {driver.icon}
      </span>
      <div className="min-w-0">
        <div className="flex items-center justify-between gap-3">
          <span className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">
            {driver.label}
          </span>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {driver.hint}
          </span>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
          <div
            className={`h-full rounded-full ${accent.bar}`}
            style={{ width: `${width}%` }}
          />
        </div>
      </div>
      <span className={`text-xl font-semibold tabular-nums ${accent.value}`}>
        {driver.value}
      </span>
    </div>
  );
}

function buildFocusProjects(
  projects: PortfolioProjectSummary[],
  attention: PortfolioAttentionSummary | undefined,
) {
  const attentionByProject = new Map<string, PortfolioAttentionProject>();
  attention?.projects_to_watch.forEach((project) => {
    attentionByProject.set(project.project_id, project);
  });

  return [...projects]
    .sort((a, b) => {
      const aAttention = attentionByProject.get(a.project_id)?.urgent_signals_count ?? 0;
      const bAttention = attentionByProject.get(b.project_id)?.urgent_signals_count ?? 0;
      return (
        bAttention - aAttention ||
        a.project_health_score - b.project_health_score ||
        b.blocked_tasks_count + b.overdue_tasks_count - (a.blocked_tasks_count + a.overdue_tasks_count)
      );
    })
    .slice(0, 3)
    .map((project) => ({
      project,
      attentionProject: attentionByProject.get(project.project_id),
    }));
}

function buildProjectNextAction(project: PortfolioProjectSummary) {
  if (project.blocked_tasks_count > 0) {
    return "Назначить владельца блокировки и срок снятия зависимости.";
  }
  if ((project.budget_deviation_percent ?? 0) > 10) {
    return "Проверить прогноз бюджета и вынести решение по составу работ или резерву.";
  }
  if (project.overdue_tasks_count > 0) {
    return "Сверить влияние просрочек на ближайшую веху.";
  }
  return "Открыть проект и проверить ключевые сигналы.";
}

function maxDriver(drivers: Driver[]) {
  return Math.max(...drivers.map((driver) => driver.value), 1);
}

function getPercent(value: number, total: number) {
  if (total <= 0) return 0;
  return (value / total) * 100;
}

function pluralize(value: number, forms: [string, string, string]) {
  const abs = Math.abs(value) % 100;
  const last = abs % 10;
  if (abs > 10 && abs < 20) return forms[2];
  if (last === 1) return forms[0];
  if (last >= 2 && last <= 4) return forms[1];
  return forms[2];
}

const summaryToneClass: Record<SummaryTone, string> = {
  danger: "text-rose-600 dark:text-rose-300",
  warning: "text-amber-600 dark:text-amber-300",
  neutral: "text-slate-950 dark:text-slate-50",
};

const riskDotClass: Record<RiskLevel, string> = {
  red: "bg-rose-500",
  yellow: "bg-amber-500",
  green: "bg-emerald-500",
};

const driverAccentClass: Record<
  DriverAccent,
  {
    icon: string;
    value: string;
    bar: string;
  }
> = {
  amber: {
    icon: "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300",
    value: "text-amber-700 dark:text-amber-300",
    bar: "bg-amber-500 dark:bg-amber-400",
  },
  rose: {
    icon: "bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300",
    value: "text-rose-700 dark:text-rose-300",
    bar: "bg-rose-500 dark:bg-rose-400",
  },
  sky: {
    icon: "bg-sky-50 text-sky-700 dark:bg-sky-950/40 dark:text-sky-300",
    value: "text-sky-700 dark:text-sky-300",
    bar: "bg-sky-500 dark:bg-sky-400",
  },
  violet: {
    icon: "bg-violet-50 text-violet-700 dark:bg-violet-950/40 dark:text-violet-300",
    value: "text-violet-700 dark:text-violet-300",
    bar: "bg-violet-500 dark:bg-violet-400",
  },
};
