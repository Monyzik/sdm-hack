import { Bot, Loader2 } from "lucide-react";

import type { ProjectManagerBrief } from "../../../api/types";
import { Badge, Panel } from "../../../components/ui";

interface AgentBriefPanelProps {
  brief: ProjectManagerBrief | undefined;
  isLoading: boolean;
  errorMessage: string | null;
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
}: AgentBriefPanelProps) {
  return (
    <Panel title="Вывод агента" icon={<Bot className="size-4" />}>
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
        <div className="space-y-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={statusTone[brief.status]}>{brief.status}</Badge>
              <h3 className="text-base font-semibold text-slate-950 dark:text-slate-50">
                {brief.headline}
              </h3>
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">
              {brief.diagnosis}
            </p>
          </div>

          <BriefBox title="Вопрос для решения" value={brief.management_question} />

          <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
            <BriefBox title="Узкое место" value={brief.bottleneck} />
            <BriefBox title="Следующий ход" value={brief.recommended_move} />
          </div>

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

          <BriefList title="Проверить перед решением" items={brief.watchouts} />
        </div>
      ) : (
        <div className="text-sm text-slate-500 dark:text-slate-400">
          Ответ агента пока не загружен
        </div>
      )}
    </Panel>
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
