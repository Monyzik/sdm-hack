import type { ComponentType, ReactNode } from "react";
import { useEffect, useState } from "react";
import type { LucideProps } from "lucide-react";
import {
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,
  Menu,
  Moon,
  RefreshCw,
  Sun,
  X,
} from "lucide-react";

export interface NavigationPage<T extends string> {
  id: T;
  label: string;
  description: string;
  icon: ComponentType<LucideProps>;
}

interface AppNavigationProps<T extends string> {
  pages: NavigationPage<T>[];
  activePage: T;
  isCollapsed: boolean;
  isRefreshing: boolean;
  theme: "light" | "dark";
  onCollapsedChange: (value: boolean) => void;
  onPageChange: (page: T) => void;
  onRefresh: () => void;
  onThemeToggle: () => void;
}

export function AppNavigation<T extends string>({
  pages,
  activePage,
  isCollapsed,
  isRefreshing,
  theme,
  onCollapsedChange,
  onPageChange,
  onRefresh,
  onThemeToggle,
}: AppNavigationProps<T>) {
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const activePageLabel =
    pages.find((page) => page.id === activePage)?.label ?? "Раздел";

  useEffect(() => {
    if (!isMobileOpen) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isMobileOpen]);

  useEffect(() => {
    if (!isMobileOpen) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsMobileOpen(false);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isMobileOpen]);

  useEffect(() => {
    const desktopQuery = window.matchMedia("(min-width: 1024px)");
    if (desktopQuery.matches) {
      setIsMobileOpen(false);
    }

    function handleViewportChange(event: MediaQueryListEvent) {
      if (event.matches) {
        setIsMobileOpen(false);
      }
    }

    desktopQuery.addEventListener("change", handleViewportChange);
    return () =>
      desktopQuery.removeEventListener("change", handleViewportChange);
  }, []);

  function handlePageChange(page: T) {
    onPageChange(page);
    setIsMobileOpen(false);
  }

  return (
    <>
      <nav className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 px-4 py-3 shadow-sm shadow-slate-200/40 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95 dark:shadow-black/20 lg:top-0 lg:flex lg:h-screen lg:flex-col lg:overflow-y-auto lg:border-b-0 lg:border-r lg:px-3 lg:py-4">
        <div className="flex items-center justify-between gap-3 lg:hidden">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              aria-expanded={isMobileOpen}
              aria-controls="mobile-primary-nav"
              title={isMobileOpen ? "Свернуть меню" : "Открыть меню"}
              onClick={() => setIsMobileOpen((value) => !value)}
              className="grid size-10 shrink-0 place-items-center rounded-lg text-slate-700 transition hover:bg-slate-100 hover:text-slate-950 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:text-slate-200 dark:hover:bg-slate-900 dark:hover:text-slate-50"
            >
              <Menu aria-hidden strokeWidth={2.25} className="size-5" />
              <span className="sr-only">
                {isMobileOpen ? "Свернуть меню" : "Открыть меню"}
              </span>
            </button>
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-slate-950 dark:text-slate-50">
                {activePageLabel}
              </div>
              <div className="text-xs text-slate-500 dark:text-slate-400">
                SDM
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1">
            <IconButton
              title={
                theme === "dark"
                  ? "Включить светлую тему"
                  : "Включить тёмную тему"
              }
              onClick={onThemeToggle}
              className="text-slate-600 dark:text-slate-300"
            >
              {theme === "dark" ? (
                <Sun aria-hidden strokeWidth={2.25} className="size-4" />
              ) : (
                <Moon aria-hidden strokeWidth={2.25} className="size-4" />
              )}
              <span className="sr-only">Переключить тему</span>
            </IconButton>
            <IconButton
              title="Обновить"
              onClick={onRefresh}
              className="text-slate-700 dark:text-slate-300"
            >
              <RefreshCw
                aria-hidden
                strokeWidth={2.25}
                className={`size-4 ${isRefreshing ? "animate-spin" : ""}`}
              />
              <span className="sr-only">Обновить</span>
            </IconButton>
          </div>
        </div>

        <div className="hidden h-full flex-col lg:flex">
          <div
            className={`flex items-center justify-between gap-3 ${
              isCollapsed ? "lg:flex-col lg:justify-start" : ""
            }`}
          >
            <div className="flex min-w-0 items-center gap-3 px-1">
              {isCollapsed ? (
                <button
                  type="button"
                  title="Показать меню"
                  onClick={() => onCollapsedChange(false)}
                  className="hidden h-9 w-9 shrink-0 items-center justify-center text-slate-500 transition hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 dark:text-slate-400 dark:hover:text-slate-100 lg:grid"
                >
                  <ChevronRight
                    aria-hidden
                    strokeWidth={2.25}
                    className="size-5"
                  />
                  <span className="sr-only">Показать меню</span>
                </button>
              ) : (
                <div className="flex min-w-0 items-center gap-2.5">
                  <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-indigo-600 text-white shadow-sm">
                    <LayoutDashboard
                      aria-hidden
                      strokeWidth={2.25}
                      className="size-4"
                    />
                  </div>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-bold leading-tight text-slate-950 dark:text-slate-50">
                      Control Tower
                    </div>
                    <div className="text-xs leading-tight text-slate-400 dark:text-slate-500">
                      SDM
                    </div>
                  </div>
                </div>
              )}
            </div>

            <button
              type="button"
              title="Скрыть меню"
              onClick={() => onCollapsedChange(!isCollapsed)}
              className={`hidden h-9 w-9 shrink-0 items-center justify-center text-slate-500 transition hover:text-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:text-slate-400 dark:hover:text-slate-100 lg:inline-flex ${
                isCollapsed ? "lg:hidden" : ""
              }`}
            >
              <ChevronLeft aria-hidden strokeWidth={2.25} className="size-5" />
              <span className="sr-only">Скрыть меню</span>
            </button>
          </div>

          <div className="mt-4 flex-1 space-y-2">
            <NavigationItems
              pages={pages}
              activePage={activePage}
              isCollapsed={isCollapsed}
              onPageChange={handlePageChange}
            />
          </div>

          <div className="mt-4 space-y-2">
            <button
              type="button"
              onClick={onRefresh}
              className={`inline-flex w-full items-center ${
                isCollapsed
                  ? "lg:justify-center lg:px-0 lg:py-2"
                  : "justify-between"
              } px-3 py-2.5 text-sm font-medium text-slate-700 transition hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:text-slate-300 dark:hover:text-slate-100`}
            >
              <span className={isCollapsed ? "lg:sr-only" : ""}>Обновить</span>
              <RefreshCw
                aria-hidden
                strokeWidth={2.25}
                className={`size-4 ${isRefreshing ? "animate-spin" : ""}`}
              />
            </button>
          </div>
        </div>
      </nav>

      {isMobileOpen ? (
        <div
          aria-modal="true"
          role="dialog"
          aria-label="Основное меню"
          className="fixed inset-0 z-50 lg:hidden"
        >
          <button
            type="button"
            aria-label="Закрыть меню"
            onClick={() => setIsMobileOpen(false)}
            className="absolute inset-0 bg-slate-950/35 backdrop-blur-sm"
          />
          <div
            id="mobile-primary-nav"
            className="absolute bottom-0 left-0 top-0 flex w-[min(86vw,336px)] flex-col border-r border-slate-200 bg-white px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-[max(1rem,env(safe-area-inset-top))] text-slate-950 shadow-2xl shadow-slate-950/20 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-50 dark:shadow-black/40"
          >
            <div className="flex items-center justify-between gap-3 border-b border-slate-100 pb-3 dark:border-slate-800">
              <div>
                <div className="text-sm font-semibold">Разделы</div>
                <div className="text-xs text-slate-500 dark:text-slate-400">
                  SDM
                </div>
              </div>
              <button
                type="button"
                title="Закрыть меню"
                onClick={() => setIsMobileOpen(false)}
                className="grid size-10 place-items-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-950 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-50"
              >
                <X aria-hidden strokeWidth={2.25} className="size-5" />
                <span className="sr-only">Закрыть меню</span>
              </button>
            </div>

            <div className="mt-4 flex-1 space-y-2 overflow-y-auto overscroll-contain">
              <NavigationItems
                pages={pages}
                activePage={activePage}
                onPageChange={handlePageChange}
              />
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

interface NavigationItemsProps<T extends string> {
  pages: NavigationPage<T>[];
  activePage: T;
  isCollapsed?: boolean;
  onPageChange: (page: T) => void;
}

function NavigationItems<T extends string>({
  pages,
  activePage,
  isCollapsed = false,
  onPageChange,
}: NavigationItemsProps<T>) {
  return (
    <>
      {pages.map((page) => {
        const Icon = page.icon;
        const isActive = page.id === activePage;

        return (
          <button
            key={page.id}
            type="button"
            aria-current={isActive ? "page" : undefined}
            title={page.label}
            onClick={() => onPageChange(page.id)}
            className={`flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left transition focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 ${
              isActive
                ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300"
                : "text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-900/60"
            } ${isCollapsed ? "lg:grid lg:size-12 lg:place-items-center lg:justify-items-center lg:p-0" : ""}`}
          >
            <Icon
              aria-hidden
              strokeWidth={2.25}
              className={`${isCollapsed ? "lg:size-6" : "size-5"} shrink-0`}
            />
            <span className={isCollapsed ? "lg:sr-only" : ""}>
              <span className="block text-sm font-semibold">{page.label}</span>
              <span className="block text-xs text-slate-500 dark:text-slate-400">
                {page.description}
              </span>
            </span>
          </button>
        );
      })}
    </>
  );
}

interface IconButtonProps {
  title: string;
  className?: string;
  children: ReactNode;
  onClick: () => void;
}

function IconButton({
  title,
  className = "",
  children,
  onClick,
}: IconButtonProps) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={`inline-grid size-10 place-items-center rounded-lg transition hover:bg-slate-100 hover:text-slate-950 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-50 ${className}`}
    >
      {children}
    </button>
  );
}
