import type { RiskLevel } from "../../api/types";
import { riskLabel, riskTone } from "../../lib/risk";
import { Badge } from "./Badge";

/**
 * Бейдж зоны риска. Кроме цвета всегда выводит текстовую подпись
 * («Красная зона» и т.д.) — цвет не единственный носитель смысла,
 * что важно для доступности.
 */
export function RiskBadge({ level }: { level: RiskLevel }) {
  return (
    <Badge tone={riskTone(level)}>
      <span aria-hidden className="size-1.5 rounded-full bg-current" />
      {riskLabel(level)}
    </Badge>
  );
}
