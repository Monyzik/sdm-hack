import { Bot, Loader2, Sparkles } from "lucide-react";

import type { ProjectManagerBrief } from "../../../api/types";
import { Badge, Panel } from "../../../components/ui";
import { formatDays, formatMoney } from "../../../lib/format";

interface AgentBriefPanelProps {
  brief: ProjectManagerBrief | undefined;
  isLoading: boolean;
  errorMessage: string | null;
  hasRequested: boolean;
  onRequest: () => void;
}

const statusTone = {
  "в норме": "success",
  "под наблюдением": "warning",
  критично: "danger",
} as const;

export function AgentBriefPanel({
  brief,
  isLoading,
  errorMessage,
  hasRequested,
  onRequest,
}: AgentBriefPanelProps) {
  return (
    <Panel
      title="Вывод агента"
      icon={<Bot className="size-4" />}
      action={
        <button
          type="button"
          onClick={onRequest}
          disabled={isLoading}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200 dark:hover:bg-slate-800"
        >
          {isLoading ? (
            <Loader2 aria-hidden className="size-3.5 animate-spin" />
          ) : (
            <Sparkles aria-hidden className="size-3.5" />
          )}
          {hasRequested ? "Обновить" : "Сформировать"}
        </button>
      }
    >
      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
          <Loader2 aria-hidden className="size-4 animate-spin" />
          Агент формирует вывод
        </div>
      ) : errorMessage ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-100">
          {errorMessage}
        </div>
      ) : brief ? (
        <BriefContent brief={brief} />
      ) : (
        <div className="text-sm text-slate-500 dark:text-slate-400">
          Вывод агента не сформирован
        </div>
      )}
    </Panel>
  );
}

function BriefContent({ brief }: { brief: ProjectManagerBrief }) {
  const primaryAction = brief.next_actions[0];

  return (
    <div className="space-y-4">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={statusTone[brief.status]}>{brief.status}</Badge>
          <h3 className="text-base font-semibold text-slate-950 dark:text-slate-50">
            {brief.headline}
          </h3>
        </div>
      </div>

      <BriefImpact brief={brief} />
      <BriefBox title="Следующий ход" value={brief.recommended_move} />

      {primaryAction ? (
        <BriefAction
          title="Поручение"
          action={primaryAction.action}
          meta={`${primaryAction.owner_hint} · ${primaryAction.deadline}`}
          value={primaryAction.success_signal}
        />
      ) : null}

      <details className="rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950/40">
        <summary className="cursor-pointer list-none px-3 py-2 text-sm font-semibold text-slate-800 outline-none transition hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-slate-400 dark:text-slate-100 dark:hover:bg-slate-900">
          Обоснование и черновики
        </summary>
        <div className="space-y-4 border-t border-slate-100 p-3 dark:border-slate-800">
          <BriefBox title="Вопрос для решения" value={brief.management_question} />
          <BriefBox title="Диагноз" value={brief.diagnosis} />
          <BriefBox title="Узкое место" value={brief.bottleneck} />
          <BriefList title="Цепочка влияния" items={brief.critical_path} />

          <div>
            <div className="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
              Развилки решения
            </div>
            <div className="mt-2 grid grid-cols-1 gap-3 xl:grid-cols-2">
              {brief.decision_options.map((option) => (
                <div
                  key={option.option}
                  className="rounded-lg border border-slate-200 bg-white px-3 py-3 dark:border-slate-800 dark:bg-slate-950/40"
                >
                  <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                    {option.option}
                  </div>
                  <div className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">
                    {option.when_to_choose}
                  </div>
                  <div className="mt-2 rounded-lg bg-slate-50 px-2 py-2 text-xs leading-5 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                    {option.tradeoff}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
            <BriefBox
              title={`Сообщение: ${brief.draft_message.recipient_hint}`}
              value={`${brief.draft_message.subject}. ${brief.draft_message.body}`}
            />
            <BriefBox
              title={`Follow-up: ${brief.follow_up_check.check_after}`}
              value={`${brief.follow_up_check.success_condition} Если нет: ${brief.follow_up_check.escalation_condition}`}
            />
          </div>

          <BriefList title="Проверить перед решением" items={brief.watchouts} />
        </div>
      </details>
    </div>
  );
}

function BriefImpact({ brief }: { brief: ProjectManagerBrief }) {
  const impact = brief.business_impact;
  const items = [
    impact.delay_days !== null
      ? { label: "Срок", value: formatDays(impact.delay_days) }
      : null,
    impact.cost_of_delay !== null
      ? { label: "Цена задержки", value: formatMoney(impact.cost_of_delay) }
      : null,
    impact.budget_delta !== null
      ? { label: "Бюджет", value: formatMoney(impact.budget_delta) }
      : null,
  ].filter((item): item is { label: string; value: string } => item !== null);

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 dark:border-slate-800 dark:bg-slate-950/40">
      <div className="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
        Impact
      </div>
      {items.length ? (
        <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
          {items.map((item) => (
            <div
              key={item.label}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-800 dark:bg-slate-900"
            >
              <div className="text-xs text-slate-500 dark:text-slate-400">
                {item.label}
              </div>
              <div className="mt-1 text-sm font-semibold tabular-nums text-slate-900 dark:text-slate-100">
                {item.value}
              </div>
            </div>
          ))}
        </div>
      ) : null}
      <div className="mt-2 text-sm leading-6 text-slate-700 dark:text-slate-300">
        {impact.impact_summary}
      </div>
    </div>
  );
}

function BriefAction({
  title,
  action,
  meta,
  value,
}: {
  title: string;
  action: string;
  meta: string;
  value: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-3 dark:border-slate-800 dark:bg-slate-950/40">
      <div className="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
        {title}
      </div>
      <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-slate-100">
        {action}
      </div>
      <div className="mt-2 text-xs font-medium text-slate-500 dark:text-slate-400">
        {meta}
      </div>
      <div className="mt-2 rounded-lg bg-slate-50 px-2 py-2 text-xs leading-5 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
        {value}
      </div>
    </div>
  );
}

function BriefBox({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-800 dark:bg-slate-950/40">
      <div className="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
        {title}
      </div>
      <div className="mt-1 text-sm leading-6 text-slate-700 dark:text-slate-300">
        {value}
      </div>
    </div>
  );
}

function BriefList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;

  return (
    <div>
      <div className="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
        {title}
      </div>
      <ul className="mt-2 space-y-2">
        {items.map((item) => (
          <li
            key={item}
            className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300"
          >
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
