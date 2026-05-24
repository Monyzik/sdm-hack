import { ArrowUp, Bot, Copy, Sparkles } from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import type { PortfolioProjectSummary, ProjectQuestionAnswer } from "../../api/types";
import { Badge } from "../../components/ui";
import { useProjectQuestion } from "../../hooks/useProjectQuestion";
import { AS_OF_DATE } from "../../lib/constants";
import { MarkdownContent } from "./MarkdownContent";

type ChatMessage =
  | {
      id: string;
      role: "assistant";
      content: string;
      evidenceIds?: string[];
      suggestedQuestions?: string[];
    }
  | {
      id: string;
      role: "user";
      content: string;
    };

interface ProjectChatPageProps {
  projects: PortfolioProjectSummary[];
  selectedProjectId: string | null;
  onSelectProject: (projectId: string) => void;
}

export function ProjectChatPage({
  projects,
  selectedProjectId,
  onSelectProject,
}: ProjectChatPageProps) {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    {
      id: "welcome",
      role: "assistant",
      content:
        "Спросите меня по выбранному проекту. Я смотрю summary, проблемный context, задачи, риски, бюджет, коммуникации, решения и зависимости.",
    },
  ]);
  const selectedProject = projects.find(
    (project) => project.project_id === selectedProjectId,
  );
  const selectedProjectName = selectedProject?.project_name;
  const questionMutation = useProjectQuestion(selectedProjectId, AS_OF_DATE);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const canSubmit = draft.trim().length > 0 && Boolean(selectedProjectId);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, questionMutation.isPending]);

  useEffect(() => {
    setMessages([
      {
        id: `welcome-${selectedProjectId ?? "none"}`,
        role: "assistant",
        content: selectedProjectName
          ? `Выбран проект «${selectedProjectName}». Задайте вопрос по статусу, срокам, рискам, бюджету или блокерам.`
          : "Выберите проект, чтобы задать вопрос.",
      },
    ]);
  }, [selectedProjectId, selectedProjectName]);

  const compactProjectOptions = useMemo(
    () =>
      projects.map((project) => ({
        id: project.project_id,
        label: project.project_name,
      })),
    [projects],
  );

  function sendQuestion(question: string) {
    const value = question.trim();
    if (!value || !selectedProjectId) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: value,
    };
    setMessages((items) => [...items, userMessage]);
    setDraft("");

    questionMutation.mutate(
      { question: value },
      {
        onSuccess: (answer: ProjectQuestionAnswer) => {
          setMessages((items) => [
            ...items,
            {
              id: `assistant-${Date.now()}`,
              role: "assistant",
              content: answer.answer,
              evidenceIds: answer.evidence_ids,
              suggestedQuestions: answer.suggested_questions,
            },
          ]);
        },
        onError: (error) => {
          setMessages((items) => [
            ...items,
            {
              id: `assistant-error-${Date.now()}`,
              role: "assistant",
              content: formatAgentError(error),
            },
          ]);
        },
      },
    );
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    sendQuestion(draft);
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-132px)] w-full max-w-5xl flex-col">
      <div className="mb-4 flex flex-col gap-3 border-b border-slate-200 pb-4 dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-950 dark:text-slate-50">
            Чат по проекту
          </h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Ответы строятся по фактам проекта и возвращают evidence ids.
          </p>
        </div>
        <select
          value={selectedProjectId ?? ""}
          onChange={(event) => onSelectProject(event.target.value)}
          className="h-10 min-w-0 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-800 shadow-sm outline-none transition hover:bg-slate-50 focus:border-slate-400 focus:ring-2 focus:ring-slate-200 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800 dark:focus:border-slate-600 dark:focus:ring-slate-800 sm:min-w-80"
        >
          {compactProjectOptions.map((project) => (
            <option key={project.id} value={project.id}>
              {project.label}
            </option>
          ))}
        </select>
      </div>

      <div className="flex-1 space-y-8 pb-32">
        {messages.map((message) => (
          <ChatBubble
            key={message.id}
            message={message}
            onAsk={sendQuestion}
            disabled={questionMutation.isPending}
          />
        ))}
        {questionMutation.isPending ? <TypingBubble /> : null}
        <div ref={bottomRef} />
      </div>

      <div className="sticky bottom-0 border-t border-transparent bg-slate-50/95 py-4 backdrop-blur dark:bg-[#080c14]/95">
        <form
          onSubmit={handleSubmit}
          className="mx-auto flex max-w-3xl items-end gap-2 rounded-3xl border border-slate-200 bg-white p-2 shadow-lg shadow-slate-200/60 dark:border-slate-800 dark:bg-slate-900 dark:shadow-black/30"
        >
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                sendQuestion(draft);
              }
            }}
            placeholder="Спросите по проекту"
            rows={1}
            className="max-h-32 min-h-10 flex-1 resize-none bg-transparent px-3 py-2 text-sm leading-6 text-slate-900 outline-none placeholder:text-slate-400 dark:text-slate-100 dark:placeholder:text-slate-500"
          />
          <button
            type="submit"
            disabled={!canSubmit || questionMutation.isPending}
            className="grid size-10 shrink-0 place-items-center rounded-full bg-slate-950 text-white transition hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:cursor-not-allowed disabled:bg-slate-300 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white dark:disabled:bg-slate-700"
          >
            <ArrowUp aria-hidden className="size-4" />
            <span className="sr-only">Отправить</span>
          </button>
        </form>
      </div>
    </div>
  );
}

function formatAgentError(error: unknown) {
  if (error instanceof Error && error.message) {
    return `Не смог получить ответ агента: ${error.message}`;
  }
  return "Не смог получить ответ агента. Проверьте agents API, backend и настройки LLM.";
}

function ChatBubble({
  message,
  onAsk,
  disabled,
}: {
  message: ChatMessage;
  onAsk: (question: string) => void;
  disabled: boolean;
}) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[76%] rounded-3xl bg-slate-950 px-4 py-2.5 text-sm leading-6 text-white dark:bg-slate-100 dark:text-slate-950">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-3xl gap-3">
      <div className="mt-1 grid size-7 shrink-0 place-items-center rounded-full border border-slate-200 bg-white text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
        <Bot aria-hidden className="size-4" />
      </div>
      <div className="min-w-0 flex-1">
        <MarkdownContent content={message.content} />
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {message.evidenceIds?.length ? (
            <Badge tone="neutral">evidence: {message.evidenceIds.join(", ")}</Badge>
          ) : null}
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-slate-500 transition hover:bg-slate-100 hover:text-slate-800 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100"
          >
            <Copy aria-hidden className="size-3.5" />
            Копировать
          </button>
        </div>
        {message.suggestedQuestions?.length ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {message.suggestedQuestions.map((question) => (
              <button
                key={question}
                type="button"
                disabled={disabled}
                onClick={() => onAsk(question)}
                className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                {question}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function TypingBubble() {
  return (
    <div className="mx-auto flex max-w-3xl gap-3">
      <div className="mt-1 grid size-7 shrink-0 place-items-center rounded-full border border-slate-200 bg-white text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
        <Sparkles aria-hidden className="size-4" />
      </div>
      <div className="flex items-center gap-1 rounded-2xl bg-slate-100 px-3 py-2 dark:bg-slate-900">
        <span className="size-1.5 animate-pulse rounded-full bg-slate-400" />
        <span className="size-1.5 animate-pulse rounded-full bg-slate-400 [animation-delay:120ms]" />
        <span className="size-1.5 animate-pulse rounded-full bg-slate-400 [animation-delay:240ms]" />
      </div>
    </div>
  );
}
