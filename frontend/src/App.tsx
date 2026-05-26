import { useQueryClient } from "@tanstack/react-query";
import {
  BarChart3,
  Bell,
  CalendarDays,
  ClipboardList,
  Gauge,
  MessageCircle,
  Moon,
  Sun,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";

import { ApiError } from "./api/client";
import {
  AppNavigation,
  Card,
  ErrorState,
  LoadingState,
  type NavigationPage,
} from "./components/ui";
import { ProjectChatPage } from "./features/chat/ProjectChatPage";
import { NotificationsPage } from "./features/notifications/NotificationsPage";
import { PortfolioCommandCenter } from "./features/portfolio/PortfolioCommandCenter";
import { PortfolioSidebar } from "./features/portfolio/PortfolioSidebar";
import { ProjectView } from "./features/project/ProjectView";
import { TaskTrackerPage } from "./features/tasks/TaskTrackerPage";
import { usePortfolio } from "./hooks/usePortfolio";
import { usePortfolioAttention } from "./hooks/usePortfolioAttention";
import { useProjectSummary } from "./hooks/useProjectSummary";
import { AS_OF_DATE } from "./lib/constants";

/** Превращает любую ошибку запроса в человекочитаемое сообщение. */
function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return "Проект не найден.";
    return error.message;
  }
  return "Не удалось загрузить данные.";
}

type AppPage = "overview" | "analysis" | "tasks" | "chat" | "notifications";

const appPages: NavigationPage<AppPage>[] = [
  {
    id: "overview" as const,
    label: "Обзор",
    description: "Сводка портфеля",
    icon: Gauge,
  },
  {
    id: "analysis" as const,
    label: "Анализ",
    description: "Выбранный проект",
    icon: BarChart3,
  },
  {
    id: "tasks" as const,
    label: "Задачи",
    description: "Трекер задач",
    icon: ClipboardList,
  },
  {
    id: "chat" as const,
    label: "Чат",
    description: "Вопросы по проекту",
    icon: MessageCircle,
  },
  {
    id: "notifications" as const,
    label: "Уведомления",
    description: "Внутренний inbox",
    icon: Bell,
  },
];

export default function App() {
  const queryClient = useQueryClient();
  const [isNavCollapsed, setIsNavCollapsed] = useState(true);
  const [activePage, setActivePage] = useState<AppPage>("overview");
  const [asOfDate, setAsOfDate] = useState(AS_OF_DATE);
  const [previewProjectId, setPreviewProjectId] = useState<string | null>(null);
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    if (typeof window === "undefined") return "light";
    const stored = window.localStorage.getItem("theme");
    if (stored === "dark" || stored === "light") return stored;
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  });
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(
    null,
  );

  const portfolioQuery = usePortfolio(asOfDate);
  const attentionQuery = usePortfolioAttention(
    asOfDate,
    7,
    activePage === "overview",
  );
  const projectQuery = useProjectSummary(
    selectedProjectId,
    asOfDate,
    activePage === "analysis",
  );
  const previewProject = portfolioQuery.data?.projects.find(
    (project) => project.project_id === previewProjectId,
  );

  // Как только портфель загружен, выбираем первый проект, если выбора ещё нет
  // или текущий проект исчез из списка.
  useEffect(() => {
    const projects = portfolioQuery.data?.projects;
    if (!projects?.length) return;
    const exists = projects.some((p) => p.project_id === selectedProjectId);
    if (!exists) {
      setSelectedProjectId(projects[0].project_id);
    }
  }, [portfolioQuery.data, selectedProjectId]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    window.localStorage.setItem("theme", theme);
  }, [theme]);

  function handleRefresh() {
    queryClient.invalidateQueries();
  }

  function handleProjectSelect(projectId: string) {
    setSelectedProjectId(projectId);
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-[#080c14] dark:text-slate-100">
      <div
        className={`grid min-h-screen grid-cols-1 ${
          isNavCollapsed
            ? "lg:grid-cols-[72px_minmax(0,1fr)]"
            : "lg:grid-cols-[280px_minmax(0,1fr)]"
        }`}
      >
        <AppNavigation
          pages={appPages}
          activePage={activePage}
          isCollapsed={isNavCollapsed}
          isRefreshing={portfolioQuery.isFetching}
          theme={theme}
          onCollapsedChange={setIsNavCollapsed}
          onPageChange={setActivePage}
          onRefresh={handleRefresh}
          onThemeToggle={() => setTheme(theme === "dark" ? "light" : "dark")}
        />

        <div className="min-w-0">
          <div className="mx-auto flex w-full max-w-none flex-col gap-4 px-4 py-4 sm:px-6">
            <header
              id="overview"
              className="flex flex-col gap-3 border-b border-slate-200 pb-4 dark:border-slate-800 lg:flex-row lg:items-center lg:justify-between"
            >
              <div>
                <h1 className="text-2xl font-semibold text-slate-950 dark:text-slate-50">
                  {activePage === "overview"
                    ? "Обзор портфеля проектов"
                    : activePage === "analysis"
                      ? "Анализ проекта"
                      : activePage === "tasks"
                        ? "Задачи"
                        : activePage === "chat"
                          ? "Чат по проекту"
                          : "Уведомления"}
                </h1>
              </div>
              <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
                {activePage !== "notifications" ? (
                  <>
                    <label className="sr-only" htmlFor="as-of-date">
                      Дата среза
                    </label>
                    <div className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-slate-600 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
                      <CalendarDays aria-hidden className="size-3.5" />
                      <input
                        id="as-of-date"
                        type="date"
                        value={asOfDate}
                        onChange={(event) =>
                          setAsOfDate(event.target.value || AS_OF_DATE)
                        }
                        className="min-w-0 bg-transparent text-sm font-medium text-slate-800 outline-none dark:text-slate-100"
                      />
                    </div>
                  </>
                ) : null}
                <button
                  type="button"
                  title={
                    theme === "dark"
                      ? "Включить светлую тему"
                      : "Включить тёмную тему"
                  }
                  onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                  className="hidden size-9 place-items-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 lg:inline-grid"
                >
                  {theme === "dark" ? (
                    <Sun aria-hidden className="size-3.5" />
                  ) : (
                    <Moon aria-hidden className="size-3.5" />
                  )}
                  <span className="sr-only">Переключить тему</span>
                </button>
                {activePage === "chat" || activePage === "analysis" ? (
                  <>
                    <label className="sr-only" htmlFor="project-select">
                      Выбрать проект
                    </label>
                    <select
                      id="project-select"
                      value={selectedProjectId ?? ""}
                      onChange={(event) =>
                        handleProjectSelect(event.target.value)
                      }
                      disabled={!portfolioQuery.data?.projects.length}
                      className="h-10 min-w-0 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-800 shadow-sm outline-none transition hover:bg-slate-50 focus:border-slate-400 focus:ring-2 focus:ring-slate-200 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800 dark:focus:border-slate-600 dark:focus:ring-slate-800 sm:min-w-72"
                    >
                      {portfolioQuery.data?.projects.map((project) => (
                        <option
                          key={project.project_id}
                          value={project.project_id}
                        >
                          {project.project_name}
                        </option>
                      ))}
                    </select>
                  </>
                ) : null}
              </div>
            </header>

            <main id="metrics" className="min-w-0">
              {activePage === "overview" ? (
                portfolioQuery.isPending ? (
                  <LoadingState label="Загрузка портфеля…" />
                ) : portfolioQuery.isError ? (
                  <ErrorState
                    message={describeError(portfolioQuery.error)}
                    onRetry={() => portfolioQuery.refetch()}
                  />
                ) : (
                  <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
                    <div className="min-w-0">
                      {attentionQuery.isPending ? (
                        <LoadingState label="Загрузка портфеля…" />
                      ) : attentionQuery.isError ? (
                        <ErrorState
                          message={describeError(attentionQuery.error)}
                          onRetry={() => attentionQuery.refetch()}
                        />
                      ) : (
                        <PortfolioCommandCenter
                          portfolio={portfolioQuery.data}
                          attention={attentionQuery.data}
                          onSelectProject={(projectId) => {
                            setSelectedProjectId(projectId);
                            setActivePage("analysis");
                          }}
                        />
                      )}
                    </div>
                    <PortfolioSidebar
                      projects={portfolioQuery.data.projects}
                      selectedProjectId={selectedProjectId}
                      onSelect={setPreviewProjectId}
                    />
                  </div>
                )
              ) : activePage === "tasks" ? (
                portfolioQuery.isPending ? (
                  <LoadingState label="Загрузка проектов…" />
                ) : portfolioQuery.isError ? (
                  <ErrorState
                    message={describeError(portfolioQuery.error)}
                    onRetry={() => portfolioQuery.refetch()}
                  />
                ) : (
                  <TaskTrackerPage
                    projects={portfolioQuery.data.projects}
                    asOf={asOfDate}
                    enabled={activePage === "tasks"}
                    onOpenProject={(projectId) => {
                      setSelectedProjectId(projectId);
                      setActivePage("analysis");
                    }}
                  />
                )
              ) : activePage === "chat" ? (
                portfolioQuery.isPending ? (
                  <LoadingState label="Загрузка проектов…" />
                ) : portfolioQuery.isError ? (
                  <ErrorState
                    message={describeError(portfolioQuery.error)}
                    onRetry={() => portfolioQuery.refetch()}
                  />
                ) : (
                  <ProjectChatPage
                    projects={portfolioQuery.data.projects}
                    selectedProjectId={selectedProjectId}
                    asOfDate={asOfDate}
                  />
                )
              ) : activePage === "notifications" ? (
                portfolioQuery.isPending ? (
                  <LoadingState label="Загрузка проектов…" />
                ) : portfolioQuery.isError ? (
                  <ErrorState
                    message={describeError(portfolioQuery.error)}
                    onRetry={() => portfolioQuery.refetch()}
                  />
                ) : (
                  <NotificationsPage
                    projects={portfolioQuery.data.projects}
                    selectedProjectId={selectedProjectId}
                    onSelectProject={setSelectedProjectId}
                  />
                )
              ) : projectQuery.isError ? (
                <ErrorState
                  message={describeError(projectQuery.error)}
                  onRetry={() => projectQuery.refetch()}
                />
              ) : projectQuery.data ? (
                <ProjectView project={projectQuery.data} asOfDate={asOfDate} />
              ) : (
                <LoadingState label="Загрузка проекта…" />
              )}
            </main>
          </div>
        </div>
      </div>
      {previewProject ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="project-preview-title"
          className="fixed inset-0 z-50 grid place-items-center bg-slate-950/40 p-4 backdrop-blur-sm"
          onClick={() => setPreviewProjectId(null)}
        >
          <Card
            className="w-full max-w-xl p-5"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-medium uppercase text-slate-500 dark:text-slate-400">
                  Проект
                </p>
                <h2
                  id="project-preview-title"
                  className="mt-1 text-xl font-semibold text-slate-950 dark:text-slate-50"
                >
                  {previewProject.project_name}
                </h2>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  {previewProject.priority}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setPreviewProjectId(null)}
                className="inline-grid size-9 place-items-center rounded-lg border border-slate-200 text-slate-500 transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:border-slate-800 dark:text-slate-400 dark:hover:bg-slate-800"
              >
                <X aria-hidden className="size-4" />
                <span className="sr-only">Закрыть</span>
              </button>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Здоровье
                </p>
                <p className="mt-1 text-xl font-semibold tabular-nums">
                  {previewProject.project_health_score}
                </p>
              </div>
              <div className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Готовность
                </p>
                <p className="mt-1 text-xl font-semibold tabular-nums">
                  {Math.round(previewProject.completion_percent)}%
                </p>
              </div>
              <div className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Блокируют
                </p>
                <p className="mt-1 text-xl font-semibold tabular-nums">
                  {previewProject.blocked_tasks_count}
                </p>
              </div>
              <div className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Просрочены
                </p>
                <p className="mt-1 text-xl font-semibold tabular-nums">
                  {previewProject.overdue_tasks_count}
                </p>
              </div>
            </div>

            {previewProject.top_signals.length ? (
              <ul className="mt-4 space-y-2">
                {previewProject.top_signals.slice(0, 3).map((signal, index) => (
                  <li
                    key={`${index}-${signal}`}
                    className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:bg-slate-950/50 dark:text-slate-300"
                  >
                    {signal}
                  </li>
                ))}
              </ul>
            ) : null}

            <div className="mt-5 flex justify-end">
              <button
                type="button"
                onClick={() => {
                  setSelectedProjectId(previewProject.project_id);
                  setPreviewProjectId(null);
                  setActivePage("analysis");
                }}
                className="rounded-lg border border-slate-300 bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-900 transition hover:bg-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-50 dark:hover:bg-slate-700"
              >
                Подробнее
              </button>
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
