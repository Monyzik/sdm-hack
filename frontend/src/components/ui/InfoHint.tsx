import { Info } from "lucide-react";
import type { ReactNode } from "react";

interface InfoHintProps {
  /** Текст подсказки. Показывается во встроенном tooltip и читается голосом скринридером. */
  text: string;
  /** Опционально — собственная иконка (по умолчанию знак вопроса/информации). */
  children?: ReactNode;
  className?: string;
}

/**
 * Маленький значок «i» рядом с термином. По наведению/фокусу показывает
 * нативный tooltip, а текст также доступен скринридеру через `aria-label`.
 *
 * Использовать там, где пользователь может не понимать жаргон («Индекс состояния»,
 * «Окупаемость с учётом риска» и т.п.), но не каждый раз пихать длинное пояснение
 * в макет.
 */
export function InfoHint({ text, children, className = "" }: InfoHintProps) {
  return (
    <span
      role="img"
      aria-label={text}
      title={text}
      tabIndex={0}
      className={`inline-flex size-4 cursor-help items-center justify-center rounded-full text-slate-400 transition hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:text-slate-500 dark:hover:text-slate-200 ${className}`}
    >
      {children ?? <Info aria-hidden className="size-3.5" />}
    </span>
  );
}
