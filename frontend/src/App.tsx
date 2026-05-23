import {
  AlertTriangle,
  ArrowDownUp,
  Banknote,
  CalendarClock,
  CheckCircle2,
  CircleAlert,
  Clock3,
  Loader2,
  MessageSquareWarning,
  RefreshCw,
  ShieldAlert,
  UsersRound,
} from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

type RiskLevel = "green" | "yellow" | "red";

type BudgetSummary = {
  planned_budget: number;
  actual_spent: number;
  forecast_total_spent: number;
  expected_economic_effect: number;
  cost_of_delay_per_day: number;
  currency: string;
  budget_deviation_percent: number;
  roi_percent: number;
  risk_adjusted_roi_percent: number;
};

type TaskSignal = {
  id: string;
  title: string;
  status: string;
  priority: string;
  planned_due_date: string;
  overdue_days: number;
  assignee_name: string;
  blocker_reason: string | null;
};

type RiskSignal = {
  id: string;
  risk_type: string;
  description: string;
  score: number;
  status: string;
  owner_name: string;
};

type CommunicationSignal = {
  id: string;
  from_team: string;
  to_team: string;
  topic: string;
  status: string;
  importance: string;
  delay_days: number;
};

type ResourceSignal = {
  resource_id: string;
  full_name: string;
  role: string;
  team: string;
  total_allocation_percent: number;
  overload_percent: number;
};

type PortfolioProject = {
  project_id: string;
  project_name: string;
  owner_name: string;
  status: string;
  priority: string;
  project_health_score: number;
  risk_level: RiskLevel;
  completion_percent: number;
  overdue_tasks_count: number;
  blocked_tasks_count: number;
  high_risk_count: number;
  budget_deviation_percent: number | null;
  resource_overload_percent: number;
  top_signals: string[];
};

type PortfolioSummary = {
  as_of_date: string;
  projects_count: number;
  red_projects_count: number;
  yellow_projects_count: number;
  green_projects_count: number;
  portfolio_health_score: number;
  top_portfolio_signals: string[];
  projects: PortfolioProject[];
};

type ProjectSummary = {
  project_id: string;
  project_name: string;
  owner_name: string;
  status: string;
  priority: string;
  as_of_date: string;
  completion_percent: number;
  overdue_tasks_count: number;
  blocked_tasks_count: number;
  high_risk_count: number;
  dependency_risk_count: number;
  pending_decision_count: number;
  open_change_request_count: number;
  budget: BudgetSummary | null;
  resource_overload_percent: number;
  max_communication_delay_days: number;
  project_health_score: number;
  risk_level: RiskLevel;
  executive_summary: string;
  key_signals: string[];
  blocked_tasks: TaskSignal[];
  overdue_tasks: TaskSignal[];
  top_risks: RiskSignal[];
  delayed_communications: CommunicationSignal[];
  overloaded_resources: ResourceSignal[];
};

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const AS_OF = "2026-06-19";

export default function App() {
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState("P001");
  const [project, setProject] = useState<ProjectSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadPortfolio() {
    const response = await fetch(`${API_URL}/api/v1/summaries/portfolio?as_of=${AS_OF}`);
    if (!response.ok) {
      throw new Error(`Portfolio request failed: ${response.status}`);
    }
    const data = (await response.json()) as PortfolioSummary;
    setPortfolio(data);
    if (!data.projects.find((item) => item.project_id === selectedProjectId)) {
      setSelectedProjectId(data.projects[0]?.project_id ?? "P001");
    }
  }

  async function loadProject(projectId: string) {
    const response = await fetch(`${API_URL}/api/v1/summaries/projects/${projectId}?as_of=${AS_OF}`);
    if (!response.ok) {
      throw new Error(`Project request failed: ${response.status}`);
    }
    setProject((await response.json()) as ProjectSummary);
  }

  async function refresh() {
    setError(null);
    setLoading(true);
    try {
      await loadPortfolio();
      await loadProject(selectedProjectId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить данные");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    setLoading(true);
    loadProject(selectedProjectId)
      .catch((err) => setError(err instanceof Error ? err.message : "Не удалось загрузить проект"))
      .finally(() => setLoading(false));
  }, [selectedProjectId]);

  const selectedPortfolioProject = useMemo(
    () => portfolio?.projects.find((item) => item.project_id === selectedProjectId) ?? null,
    [portfolio, selectedProjectId]
  );

  return (
    <main className="min-h-screen bg-[#f6f7f9]">
      <div className="mx-auto flex max-w-[1440px] flex-col gap-5 px-5 py-5">
        <header className="flex flex-col gap-3 border-b border-slate-200 pb-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="text-sm font-medium text-slate-500">AI Project Control Tower</div>
            <h1 className="text-2xl font-semibold text-slate-950">Контроль портфеля проектов</h1>
          </div>
          <div className="flex items-center gap-3">
            <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600">
              Дата среза: <span className="font-medium text-slate-900">{AS_OF}</span>
            </div>
            <button className="btn btn-sm btn-neutral rounded-md" onClick={refresh}>
              <RefreshCw size={16} />
              Обновить
            </button>
          </div>
        </header>

        {error && (
          <div className="alert rounded-md border border-red-200 bg-red-50 text-red-900">
            <CircleAlert size={18} />
            <span>{error}</span>
          </div>
        )}

        <section className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
          <aside className="flex flex-col gap-4">
            {portfolio && (
              <div className="grid grid-cols-2 gap-3">
                <MetricTile label="Проекты" value={portfolio.projects_count} icon={<CheckCircle2 size={18} />} />
                <MetricTile label="Health" value={portfolio.portfolio_health_score} icon={<ShieldAlert size={18} />} />
                <MetricTile label="Красные" value={portfolio.red_projects_count} tone="red" icon={<AlertTriangle size={18} />} />
                <MetricTile label="Зелёные" value={portfolio.green_projects_count} tone="green" icon={<CheckCircle2 size={18} />} />
              </div>
            )}

            <div className="rounded-md border border-slate-200 bg-white">
              <div className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-900">
                Портфель
              </div>
              <div className="divide-y divide-slate-100">
                {portfolio?.projects.map((item) => (
                  <button
                    key={item.project_id}
                    className={`flex w-full flex-col gap-2 px-4 py-3 text-left transition ${
                      item.project_id === selectedProjectId ? "bg-slate-100" : "hover:bg-slate-50"
                    }`}
                    onClick={() => setSelectedProjectId(item.project_id)}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm font-semibold text-slate-950">{item.project_name}</span>
                      <RiskBadge level={item.risk_level} />
                    </div>
                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <span>{item.owner_name}</span>
                      <span>{item.project_health_score}/100</span>
                    </div>
                    <progress className="progress progress-neutral h-1.5" value={item.completion_percent} max="100" />
                  </button>
                ))}
              </div>
            </div>
          </aside>

          <section className="min-w-0">
            {loading && !project ? (
              <div className="flex h-96 items-center justify-center rounded-md border border-slate-200 bg-white">
                <Loader2 className="animate-spin text-slate-500" size={28} />
              </div>
            ) : project ? (
              <ProjectView project={project} portfolioProject={selectedPortfolioProject} />
            ) : null}
          </section>
        </section>
      </div>
    </main>
  );
}

function ProjectView({
  project,
  portfolioProject,
}: {
  project: ProjectSummary;
  portfolioProject: PortfolioProject | null;
}) {
  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-md border border-slate-200 bg-white p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="max-w-4xl">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-semibold text-slate-950">{project.project_name}</h2>
              <RiskBadge level={project.risk_level} />
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-600">{project.executive_summary}</p>
          </div>
          <div className="grid min-w-[280px] grid-cols-2 gap-2">
            <MetricTile label="Health" value={`${project.project_health_score}/100`} tone={toneByRisk(project.risk_level)} icon={<ShieldAlert size={18} />} />
            <MetricTile label="Готовность" value={`${project.completion_percent}%`} icon={<CheckCircle2 size={18} />} />
          </div>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <MetricTile label="Просрочено" value={project.overdue_tasks_count} tone="red" icon={<Clock3 size={18} />} />
        <MetricTile label="Блокеры" value={project.blocked_tasks_count} tone="red" icon={<AlertTriangle size={18} />} />
        <MetricTile label="High risks" value={project.high_risk_count} tone="amber" icon={<ShieldAlert size={18} />} />
        <MetricTile label="Перегруз" value={`${project.resource_overload_percent}%`} tone="amber" icon={<UsersRound size={18} />} />
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_360px]">
        <div className="flex flex-col gap-4">
          <Panel title="Ключевые сигналы" icon={<ArrowDownUp size={18} />}>
            <ul className="space-y-2">
              {project.key_signals.slice(0, 6).map((signal) => (
                <li key={signal} className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                  {signal}
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="Блокеры и просрочки" icon={<CalendarClock size={18} />}>
            <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
              {project.blocked_tasks.slice(0, 4).map((task) => (
                <TaskCard key={task.id} task={task} />
              ))}
            </div>
          </Panel>

          <Panel title="Коммуникации" icon={<MessageSquareWarning size={18} />}>
            <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
              {project.delayed_communications.slice(0, 4).map((item) => (
                <div key={item.id} className="rounded-md border border-slate-200 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium text-slate-900">{item.from_team} → {item.to_team}</div>
                    <span className="badge badge-warning rounded-md">{item.delay_days} дн.</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-600">{item.topic}</p>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <div className="flex flex-col gap-4">
          <Panel title="Бюджет" icon={<Banknote size={18} />}>
            {project.budget && (
              <div className="space-y-3">
                <BudgetRow label="План" value={formatMoney(project.budget.planned_budget)} />
                <BudgetRow label="Прогноз" value={formatMoney(project.budget.forecast_total_spent)} />
                <BudgetRow label="Отклонение" value={`${project.budget.budget_deviation_percent}%`} tone="red" />
                <BudgetRow label="ROI" value={`${project.budget.roi_percent}%`} tone={project.budget.roi_percent < 0 ? "red" : "green"} />
                <BudgetRow label="Risk adjusted ROI" value={`${project.budget.risk_adjusted_roi_percent}%`} tone={project.budget.risk_adjusted_roi_percent < 0 ? "red" : "green"} />
              </div>
            )}
          </Panel>

          <Panel title="Риски" icon={<ShieldAlert size={18} />}>
            <div className="space-y-3">
              {project.top_risks.slice(0, 4).map((risk) => (
                <div key={risk.id} className="rounded-md border border-slate-200 p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-slate-900">{risk.risk_type}</span>
                    <span className="badge badge-error rounded-md">score {risk.score}</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-600">{risk.description}</p>
                  <div className="mt-2 text-xs text-slate-500">{risk.owner_name}</div>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Ресурсы" icon={<UsersRound size={18} />}>
            <div className="space-y-3">
              {project.overloaded_resources.slice(0, 4).map((resource) => (
                <div key={resource.resource_id} className="rounded-md border border-slate-200 p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-slate-900">{resource.full_name}</span>
                    <span className="badge badge-warning rounded-md">{resource.total_allocation_percent}%</span>
                  </div>
                  <div className="mt-1 text-sm text-slate-600">{resource.role}, {resource.team}</div>
                </div>
              ))}
            </div>
          </Panel>

          {portfolioProject && (
            <Panel title="Сигналы портфеля" icon={<CircleAlert size={18} />}>
              <ul className="space-y-2">
                {portfolioProject.top_signals.map((signal) => (
                  <li key={signal} className="text-sm text-slate-600">{signal}</li>
                ))}
              </ul>
            </Panel>
          )}
        </div>
      </section>
    </div>
  );
}

function MetricTile({
  label,
  value,
  icon,
  tone = "slate",
}: {
  label: string;
  value: string | number;
  icon: ReactNode;
  tone?: "slate" | "red" | "amber" | "green";
}) {
  const toneClass = {
    slate: "border-slate-200 bg-white text-slate-900",
    red: "border-red-200 bg-red-50 text-red-900",
    amber: "border-amber-200 bg-amber-50 text-amber-900",
    green: "border-emerald-200 bg-emerald-50 text-emerald-900",
  }[tone];

  return (
    <div className={`rounded-md border p-3 ${toneClass}`}>
      <div className="flex items-center justify-between gap-3 text-xs font-medium uppercase text-slate-500">
        <span>{label}</span>
        {icon}
      </div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </div>
  );
}

function Panel({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-md border border-slate-200 bg-white">
      <div className="flex items-center gap-2 border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-900">
        {icon}
        {title}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

function TaskCard({ task }: { task: TaskSignal }) {
  return (
    <div className="rounded-md border border-slate-200 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-900">{task.title}</div>
          <div className="mt-1 text-xs text-slate-500">{task.assignee_name}</div>
        </div>
        <span className="badge badge-error rounded-md whitespace-nowrap">{task.overdue_days} дн.</span>
      </div>
      {task.blocker_reason && <p className="mt-2 text-sm text-slate-600">{task.blocker_reason}</p>}
    </div>
  );
}

function RiskBadge({ level }: { level: RiskLevel }) {
  const label = level === "red" ? "красная" : level === "yellow" ? "жёлтая" : "зелёная";
  const className = level === "red" ? "badge-error" : level === "yellow" ? "badge-warning" : "badge-success";
  return <span className={`badge ${className} rounded-md whitespace-nowrap`}>{label}</span>;
}

function BudgetRow({ label, value, tone = "slate" }: { label: string; value: string; tone?: "slate" | "red" | "green" }) {
  const color = tone === "red" ? "text-red-700" : tone === "green" ? "text-emerald-700" : "text-slate-900";
  return (
    <div className="flex items-center justify-between gap-4 border-b border-slate-100 pb-2 last:border-b-0 last:pb-0">
      <span className="text-sm text-slate-500">{label}</span>
      <span className={`text-sm font-semibold ${color}`}>{value}</span>
    </div>
  );
}

function toneByRisk(level: RiskLevel) {
  if (level === "red") {
    return "red";
  }
  if (level === "yellow") {
    return "amber";
  }
  return "green";
}

function formatMoney(value: number) {
  return new Intl.NumberFormat("ru-RU", {
    maximumFractionDigits: 0,
  }).format(value);
}
