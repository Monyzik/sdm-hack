import { AlertTriangle, Banknote, BellDot, ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";

import type {
  PortfolioAttentionProject,
  PortfolioAttentionSummary,
  PortfolioProjectSummary,
  PortfolioSummary,
} from "../../api/types";
import { Badge, Card } from "../../components/ui";
import { formatPercent } from "../../lib/format";
import type { Tone } from "../../lib/risk";

interface PortfolioCommandCenterProps {
  portfolio: PortfolioSummary;
  attention: PortfolioAttentionSummary | undefined;
  onSelectProject: (projectId: string) => void;
}

interface Driver {
  label: string;
  value: number;
  tone: Tone;
}

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
  const drivers: Driver[] = [
    { label: "Просрочки", value: totalOverdue, tone: "danger" },
    { label: "Блокеры", value: totalBlocked, tone: "danger" },
    { label: "Высокие риски", value: totalHighRisks, tone: "warning" },
    { label: "Бюджет > 10%", value: budgetRiskProjects, tone: "warning" },
  ];

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
          <Kpi
            label="Красная зона"
            value={portfolio.red_projects_count}
            meta={`${formatPercent((portfolio.red_projects_count / Math.max(portfolio.projects_count, 1)) * 100)} портфеля`}
            tone={portfolio.red_projects_count ? "danger" : "success"}
            icon={<AlertTriangle className="size-3.5" />}
          />
          <Kpi
            label="Крит. события"
            value={attention?.critical_signals_count ?? 0}
            meta={`за ${attention?.lookback_days ?? 7} дней`}
            tone={attention?.critical_signals_count ? "danger" : "neutral"}
            icon={<BellDot className="size-3.5" />}
          />
          <Kpi
            label="Блокеры"
            value={totalBlocked}
            meta={`${totalOverdue} просрочек`}
            tone={totalBlocked ? "danger" : "neutral"}
            icon={<ShieldAlert className="size-3.5" />}
          />
          <Kpi
            label="Бюджетный риск"
            value={budgetRiskProjects}
            meta="проектов выше плана"
            tone={budgetRiskProjects ? "warning" : "neutral"}
            icon={<Banknote className="size-3.5" />}
          />
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <Card className="p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-950 dark:text-slate-50">
                Куда смотреть
              </h2>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Топ проблем портфеля
              </p>
            </div>
            <Badge tone={focusProjects.length ? "warning" : "neutral"}>
              {focusProjects.length}
            </Badge>
          </div>
          <div className="mt-3 divide-y divide-slate-100 dark:divide-slate-800">
            {focusProjects.map(({ project, attentionProject }) => (
              <button
                key={project.project_id}
                type="button"
                onClick={() => onSelectProject(project.project_id)}
                className="grid w-full grid-cols-[minmax(0,1fr)_auto] gap-3 py-3 text-left transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:hover:bg-slate-900/70"
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold text-slate-950 dark:text-slate-50">
                    {project.project_name}
                  </span>
                  <span className="mt-1 line-clamp-1 text-xs text-slate-500 dark:text-slate-400">
                    {attentionProject?.top_reason ??
                      project.top_signals[0] ??
                      "Проверить проектные сигналы"}
                  </span>
                </span>
                <span className="flex shrink-0 items-center gap-2">
                  <MetricPill value={project.project_health_score} label="health" />
                  <MetricPill
                    value={project.blocked_tasks_count + project.overdue_tasks_count}
                    label="сигн."
                  />
                </span>
              </button>
            ))}
          </div>
        </Card>

        <Card className="p-4">
          <h2 className="text-sm font-semibold text-slate-950 dark:text-slate-50">
            Состояние портфеля
          </h2>
          <RiskDistribution portfolio={portfolio} />
          <div className="mt-5 space-y-3">
            {drivers.map((driver) => (
              <DriverBar key={driver.label} driver={driver} max={maxDriver(drivers)} />
            ))}
          </div>
        </Card>
      </div>
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

function Kpi({
  label,
  value,
  meta,
  tone,
  icon,
}: {
  label: string;
  value: number;
  meta: string;
  tone: Tone;
  icon: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 dark:border-slate-800 dark:bg-slate-950/40">
      <div className="flex items-center justify-between gap-2 text-slate-500 dark:text-slate-400">
        <span className="text-xs font-medium">{label}</span>
        <span className={toneClass[tone]}>{icon}</span>
      </div>
      <div className="mt-2 text-2xl font-semibold tabular-nums text-slate-950 dark:text-slate-50">
        {value}
      </div>
      <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
        {meta}
      </div>
    </div>
  );
}

function RiskDistribution({ portfolio }: { portfolio: PortfolioSummary }) {
  const total = Math.max(portfolio.projects_count, 1);
  const segments = [
    {
      label: "Красная",
      value: portfolio.red_projects_count,
      className: "bg-rose-500 dark:bg-rose-400",
    },
    {
      label: "Желтая",
      value: portfolio.yellow_projects_count,
      className: "bg-amber-500 dark:bg-amber-400",
    },
    {
      label: "Зеленая",
      value: portfolio.green_projects_count,
      className: "bg-emerald-500 dark:bg-emerald-400",
    },
  ];

  return (
    <div className="mt-4">
      <div className="flex h-3 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        {segments.map((segment) => (
          <div
            key={segment.label}
            className={segment.className}
            style={{ width: `${(segment.value / total) * 100}%` }}
          />
        ))}
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-slate-500 dark:text-slate-400">
        {segments.map((segment) => (
          <div key={segment.label} className="flex items-center gap-1.5">
            <span
              aria-hidden
              className={`size-2 rounded-full ${segment.className}`}
            />
            <span className="truncate">
              {segment.label}: {segment.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function DriverBar({ driver, max }: { driver: Driver; max: number }) {
  const width = max > 0 ? Math.max(6, (driver.value / max) * 100) : 0;

  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-3 text-xs">
        <span className="font-medium text-slate-600 dark:text-slate-300">
          {driver.label}
        </span>
        <span className="tabular-nums text-slate-500 dark:text-slate-400">
          {driver.value}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        <div
          className={`h-full rounded-full ${barClass[driver.tone]}`}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}

function MetricPill({ value, label }: { value: number; label: string }) {
  return (
    <span className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs tabular-nums text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
      {value} {label}
    </span>
  );
}

function maxDriver(drivers: Driver[]) {
  return Math.max(...drivers.map((driver) => driver.value), 1);
}

const toneClass: Record<Tone, string> = {
  neutral: "text-slate-400",
  danger: "text-rose-500 dark:text-rose-400",
  warning: "text-amber-500 dark:text-amber-400",
  success: "text-emerald-500 dark:text-emerald-400",
  info: "text-sky-500 dark:text-sky-400",
};

const barClass: Record<Tone, string> = {
  neutral: "bg-slate-400 dark:bg-slate-500",
  danger: "bg-rose-500 dark:bg-rose-400",
  warning: "bg-amber-500 dark:bg-amber-400",
  success: "bg-emerald-500 dark:bg-emerald-400",
  info: "bg-sky-500 dark:bg-sky-400",
};
