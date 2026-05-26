/**
 * Локализация значений, приходящих от backend. Бэкенд оперирует англоязычными
 * статусами/приоритетами, а пользователь читает русский интерфейс — все
 * переводы собраны здесь, чтобы панели не повторяли одни и те же словари.
 */

type LabelMap = Record<string, string>;

const STATUS_LABELS: LabelMap = {
  // задачи и общие
  blocked: "Заблокирована",
  in_progress: "В работе",
  in_review: "На ревью",
  done: "Готово",
  resolved: "Решено",
  approved: "Одобрено",
  rejected: "Отклонено",
  cancelled: "Отменено",
  open: "Открыта",
  closed: "Закрыта",
  // риски / зависимости
  escalated: "Эскалировано",
  mitigated: "Снижено",
  active: "Активен",
  pending: "Ожидает",
  under_review: "На рассмотрении",
  // коммуникации
  awaiting_reply: "Ждёт ответа",
  delayed: "Задержано",
  responded: "Получен ответ",
};

const PRIORITY_LABELS: LabelMap = {
  critical: "Критический",
  high: "Высокий",
  medium: "Средний",
  low: "Низкий",
};

const IMPORTANCE_LABELS: LabelMap = {
  ...PRIORITY_LABELS,
  urgent: "Срочно",
};

const CRITICALITY_LABELS: LabelMap = {
  ...PRIORITY_LABELS,
  blocker: "Блокер",
};

/** Универсальный фоллбек: подставляет первую заглавную, заменяет _ на пробел. */
function humanize(value: string): string {
  if (!value) return value;
  const cleaned = value.replace(/_/g, " ").trim();
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}

function lookup(map: LabelMap, value: string): string {
  if (!value) return "—";
  return map[value.toLowerCase()] ?? humanize(value);
}

export function statusLabel(value: string): string {
  return lookup(STATUS_LABELS, value);
}

export function priorityLabel(value: string): string {
  return lookup(PRIORITY_LABELS, value);
}

export function importanceLabel(value: string): string {
  return lookup(IMPORTANCE_LABELS, value);
}

export function criticalityLabel(value: string): string {
  return lookup(CRITICALITY_LABELS, value);
}
