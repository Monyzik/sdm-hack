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
  if (["critical", "high", "escalated", "blocked"].includes(normalized)) {
    return "danger";
  }
  if (["medium", "under_review", "pending"].includes(normalized)) {
    return "warning";
  }
  if (["low", "resolved", "approved", "done"].includes(normalized)) {
    return "success";
  }
  return "neutral";
}
