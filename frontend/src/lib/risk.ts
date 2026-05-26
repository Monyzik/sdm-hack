import type { RiskLevel } from "../api/types";

/**
 * Семантические «тоны» интерфейса. Используются переиспользуемыми UI-примитивами
 * (MetricTile, Badge), чтобы цветовое кодирование было единым во всём приложении.
 */
export type Tone = "neutral" | "danger" | "warning" | "success" | "info";

/** Зона риска проекта -> тон + человекочитаемая подпись. */
const RISK_META: Record<RiskLevel, { tone: Tone; label: string }> = {
  red: { tone: "danger", label: "Красная зона" },
  yellow: { tone: "warning", label: "Жёлтая зона" },
  green: { tone: "success", label: "Зелёная зона" },
};

export function riskTone(level: RiskLevel): Tone {
  return RISK_META[level]?.tone ?? "neutral";
}

export function riskLabel(level: RiskLevel): string {
  return RISK_META[level]?.label ?? level;
}

/**
 * Тон для health score 0..100. Пороги совпадают с логикой зон риска backend
 * (это отображение, а не пересчёт метрики).
 */
export function healthTone(score: number): Tone {
  if (score < 50) return "danger";
  if (score < 70) return "warning";
  return "success";
}

/** Критичность/важность сущностей -> тон бейджа. */
export function severityTone(value: string): Tone {
  const normalized = value.toLowerCase();
  if (
    [
      "critical",
      "high",
      "escalated",
      "blocked",
      "критический",
      "критичная",
      "высокий",
      "высокая",
      "эскалировано",
      "заблокирована",
      "заблокировано",
    ].includes(normalized)
  ) {
    return "danger";
  }
  if (
    [
      "medium",
      "under_review",
      "pending",
      "средний",
      "средняя",
      "на рассмотрении",
      "ожидает",
      "задерживается",
      "под риском",
    ].includes(normalized)
  ) {
    return "warning";
  }
  if (
    [
      "low",
      "resolved",
      "approved",
      "done",
      "низкий",
      "низкая",
      "решено",
      "согласовано",
      "завершена",
      "завершено",
      "получен ответ",
    ].includes(normalized)
  ) {
    return "success";
  }
  return "neutral";
}

const STATUS_LABELS: Record<string, string> = {
  active: "активен",
  approved: "согласовано",
  blocked: "заблокировано",
  closed: "закрыто",
  completed: "завершено",
  critical: "критичный",
  delayed: "задержано",
  done: "готово",
  escalated: "требует решения",
  high: "высокий",
  in_progress: "в работе",
  low: "низкий",
  medium: "средний",
  mitigating: "снижается",
  open: "открыто",
  pending: "ожидает",
  proposed: "предложено",
  resolved: "решено",
  under_review: "на рассмотрении",
  warning: "важно",
  info: "информация",
};

export function statusLabel(value: string): string {
  const normalized = value.trim().toLowerCase();
  return STATUS_LABELS[normalized] ?? value;
}
