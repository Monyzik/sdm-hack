import type { HTMLAttributes, ReactNode } from "react";

interface CardProps extends HTMLAttributes<HTMLElement> {
  children: ReactNode;
  className?: string;
}

/** Базовая «карточка»: белый фон, тонкая граница, скруглённые углы. */
export function Card({ children, className = "", ...props }: CardProps) {
  return (
    <section
      {...props}
      className={`rounded-xl border border-slate-200 bg-white shadow-sm shadow-slate-200/40 dark:border-slate-800 dark:bg-slate-900/80 dark:shadow-black/20 ${className}`}
    >
      {children}
    </section>
  );
}

interface PanelProps {
  title: string;
  icon?: ReactNode;
  /** Необязательный элемент в правой части шапки (счётчик, действие). */
  action?: ReactNode;
  children: ReactNode;
}

/**
 * Карточка с заголовком-секцией. Заголовок — настоящий `<h3>`, что даёт
 * корректную иерархию для скринридеров.
 */
export function Panel({ title, icon, action, children }: PanelProps) {
  return (
    <Card>
      <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-3 dark:border-slate-800">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-slate-100">
          {icon ? (
            <span aria-hidden className="text-slate-400 dark:text-slate-500">
              {icon}
            </span>
          ) : null}
          {title}
        </h3>
        {action}
      </div>
      <div className="p-4">{children}</div>
    </Card>
  );
}
