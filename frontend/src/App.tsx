import { useQueryClient } from "@tanstack/react-query";
import {
  BarChart3,
  ChevronLeft,
  ChevronRight,
  Gauge,
  LayoutDashboard,
  Moon,
  RefreshCw,
  Sun,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";

import { ApiError } from "./api/client";
import { Card, ErrorState, LoadingState } from "./components/ui";
import { PortfolioSidebar } from "./features/portfolio/PortfolioSidebar";
import { PortfolioStats } from "./features/portfolio/PortfolioStats";
import { ProjectView } from "./features/project/ProjectView";
import { usePortfolio } from "./hooks/usePortfolio";
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

type AppPage = "overview" | "analysis";

const appPages = [
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
];

export default function App() {
  const queryClient = useQueryClient();
  const [isNavCollapsed, setIsNavCollapsed] = useState(false);
  const [activePage, setActivePage] = useState<AppPage>("overview");
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

  const portfolioQuery = usePortfolio(AS_OF_DATE);
  const projectQuery = useProjectSummary(selectedProjectId, AS_OF_DATE);
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
            ? "lg:grid-cols-[84px_minmax(0,1fr)]"
            : "lg:grid-cols-[320px_minmax(0,1fr)]"
        }`}
      >
        <nav className="relative border-b border-slate-200 bg-white/90 px-4 py-3 shadow-sm shadow-slate-200/40 backdrop-blur dark:border-slate-800 dark:bg-slate-950/90 dark:shadow-black/20 lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col lg:overflow-y-auto lg:border-b-0 lg:border-r lg:px-3 lg:py-4">
          <div
            className={`flex items-center justify-between gap-3 ${
              isNavCollapsed ? "lg:flex-col lg:justify-start" : ""
            }`}
          >
            <div className="flex min-w-0 items-center gap-3 px-1">
              {isNavCollapsed ? (
                <button
                  type="button"
                  title="Показать navbar"
                  onClick={() => setIsNavCollapsed(false)}
                  className="hidden size-14 shrink-0 place-items-center rounded-xl border border-slate-300 bg-white text-slate-600 transition hover:bg-slate-50 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100 lg:grid"
                >
                  <ChevronRight aria-hidden className="size-4" />
                  <span className="sr-only">Показать navbar</span>
                </button>
              ) : (
                <div className="grid size-10 shrink-0 place-items-center rounded-xl border border-slate-200 bg-slate-100 text-slate-800 dark:border-slate-800 dark:bg-slate-800 dark:text-slate-100">
                  <LayoutDashboard aria-hidden className="size-5" />
                </div>
              )}
              <div className={`min-w-0 ${isNavCollapsed ? "lg:hidden" : ""}`}>
                <p className="truncate text-sm font-semibold text-slate-950 dark:text-slate-50">
                  Control Tower
                </p>
                <p className="truncate text-xs text-slate-500 dark:text-slate-400">
                  AI Portfolio
                </p>
              </div>
            </div>

            <button
              type="button"
              title="Скрыть navbar"
              onClick={() => setIsNavCollapsed((value) => !value)}
              className={`hidden size-9 shrink-0 place-items-center rounded-lg border border-slate-200 bg-white text-slate-500 transition hover:bg-slate-50 hover:text-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100 lg:inline-grid ${
                isNavCollapsed ? "lg:hidden" : ""
              }`}
            >
              <ChevronLeft aria-hidden className="size-4" />
              <span className="sr-only">Скрыть navbar</span>
            </button>

            <div className="flex items-center gap-2 lg:hidden">
              <button
                type="button"
                title={
                  theme === "dark"
                    ? "Включить светлую тему"
                    : "Включить тёмную тему"
                }
                onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                className="inline-grid size-10 place-items-center rounded-lg border border-slate-200 bg-white text-slate-600 transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                {theme === "dark" ? (
                  <Sun aria-hidden className="size-4" />
                ) : (
                  <Moon aria-hidden className="size-4" />
                )}
                <span className="sr-only">Переключить тему</span>
              </button>
              <button
                type="button"
                onClick={handleRefresh}
                className="inline-grid size-10 place-items-center rounded-lg border border-slate-200 bg-white text-slate-700 transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                <RefreshCw
                  aria-hidden
                  className={`size-4 ${portfolioQuery.isFetching ? "animate-spin" : ""}`}
                />
                <span className="sr-only">Обновить</span>
              </button>
            </div>
          </div>

          <div className="mt-4 flex-1 space-y-4">
            <div className="space-y-2">
              {appPages.map((page) => {
                const Icon = page.icon;
                const isActive = page.id === activePage;

                return (
                  <button
                    key={page.id}
                    type="button"
                    aria-current={isActive ? "page" : undefined}
                    title={page.label}
                    onClick={() => setActivePage(page.id)}
                    className={`flex w-full items-center gap-3 rounded-xl border px-3 py-3 text-left transition focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 ${
                      isActive
                        ? "border-slate-300 bg-slate-200 text-slate-950 dark:border-slate-700 dark:!bg-slate-900 dark:text-slate-50"
                        : "border-transparent text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-900"
                    } ${isNavCollapsed ? "lg:grid lg:size-14 lg:place-items-center lg:p-0" : ""}`}
                  >
                    <Icon aria-hidden className="size-4 shrink-0" />
                    <span className={isNavCollapsed ? "lg:sr-only" : ""}>
                      <span className="block text-sm font-semibold">
                        {page.label}
                      </span>
                      <span className="block text-xs text-slate-500 dark:text-slate-400">
                        {page.description}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="mt-4 hidden space-y-2 lg:block">
            <button
              type="button"
              onClick={handleRefresh}
              className="inline-flex w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              <span className={isNavCollapsed ? "lg:sr-only" : ""}>
                Обновить
              </span>
              <RefreshCw
                aria-hidden
                className={`size-4 ${portfolioQuery.isFetching ? "animate-spin" : ""}`}
              />
            </button>
          </div>
        </nav>

        <div className="min-w-0">
          <div className="mx-auto flex max-w-[1480px] flex-col gap-4 px-4 py-4 sm:px-6">
            <header
              id="overview"
              className="flex flex-col gap-3 border-b border-slate-200 pb-4 dark:border-slate-800 lg:flex-row lg:items-center lg:justify-between"
            >
              <div>
                <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
                  AI Project Control Tower
                </p>
                <h1 className="text-2xl font-semibold text-slate-950 dark:text-slate-50">
                  {activePage === "overview"
                    ? "Обзор портфеля проектов"
                    : "Анализ проекта"}
                </h1>
              </div>
              <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-center">
                <button
                  type="button"
                  title={
                    theme === "dark"
                      ? "Включить светлую тему"
                      : "Включить тёмную тему"
                  }
                  onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                  className="inline-grid size-10 place-items-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
                >
                  {theme === "dark" ? (
                    <Sun aria-hidden className="size-4" />
                  ) : (
                    <Moon aria-hidden className="size-4" />
                  )}
                  <span className="sr-only">Переключить тему</span>
                </button>
                {activePage === "analysis" ? (
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
                  <div className="grid grid-cols-1 gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
                    <div className="flex flex-col gap-4">
                      <PortfolioStats portfolio={portfolioQuery.data} />
                      <Card className="p-4">
                        <h2 className="text-sm font-semibold text-slate-950 dark:text-slate-50">
                          Главные сигналы портфеля
                        </h2>
                        <ul className="mt-3 space-y-2">
                          {portfolioQuery.data.top_portfolio_signals.map(
                            (signal, index) => (
                              <li
                                key={`${index}-${signal}`}
                                className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300"
                              >
                                {signal}
                              </li>
                            ),
                          )}
                        </ul>
                      </Card>
                    </div>
                    <PortfolioSidebar
                      projects={portfolioQuery.data.projects}
                      selectedProjectId={selectedProjectId}
                      onSelect={setPreviewProjectId}
                    />
                  </div>
                )
              ) : projectQuery.isError ? (
                <ErrorState
                  message={describeError(projectQuery.error)}
                  onRetry={() => projectQuery.refetch()}
                />
              ) : projectQuery.data ? (
                <ProjectView project={projectQuery.data} />
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
                  {previewProject.owner_name} · {previewProject.priority}
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
                  Health
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
                  Блокеры
                </p>
                <p className="mt-1 text-xl font-semibold tabular-nums">
                  {previewProject.blocked_tasks_count}
                </p>
              </div>
              <div className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Просрочки
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
