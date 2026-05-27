import {
  ArrowRight,
  ArrowUp,
  Bot,
  Copy,
  Database,
  Eye,
  Sparkles,
  X,
} from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";

import type {
  PortfolioProjectSummary,
  ProjectChatContextMessage,
  ProjectEvidenceSource,
  ProjectQuestionAnswer,
} from "../../api/types";
import { Badge } from "../../components/ui";
import { useProjectQuestion } from "../../hooks/useProjectQuestion";
import { MarkdownContent } from "./MarkdownContent";

type ChatMessage =
  | {
      id: string;
      role: "assistant";
      content: string;
      evidenceIds?: string[];
      evidenceSources?: ProjectEvidenceSource[];
      suggestedQuestions?: string[];
    }
  | {
      id: string;
      role: "user";
      content: string;
    };

const CONTEXT_MESSAGE_LIMIT = 6;
const CONTEXT_CHARS_PER_MESSAGE = 500;
const CONTEXT_TOTAL_CHARS = 2200;
const CHAT_STORAGE_PREFIX = "sdm-hack.project-chat";

interface ProjectChatPageProps {
  projects: PortfolioProjectSummary[];
  selectedProjectId: string | null;
  asOfDate: string;
  clearRequest: number;
  onBusyChange: (isBusy: boolean) => void;
}

export function ProjectChatPage({
  projects,
  selectedProjectId,
  asOfDate,
  clearRequest,
  onBusyChange,
}: ProjectChatPageProps) {
  const storageKey = chatStorageKey(selectedProjectId, asOfDate);
  const selectedProject = projects.find(
    (project) => project.project_id === selectedProjectId,
  );
  const selectedProjectName = selectedProject?.project_name;
  const [draft, setDraft] = useState(
    () => readStoredChat(storageKey, selectedProjectName).draft,
  );
  const [messages, setMessages] = useState<ChatMessage[]>(
    () => readStoredChat(storageKey, selectedProjectName).messages,
  );
  const questionMutation = useProjectQuestion(selectedProjectId, asOfDate);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const handledClearRequestRef = useRef(clearRequest);
  const canSubmit =
    draft.trim().length > 0 &&
    Boolean(selectedProjectId) &&
    !questionMutation.isPending;

  useEffect(() => {
    if (messages.length <= 1 && !questionMutation.isPending) return;
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, questionMutation.isPending]);

  useEffect(() => {
    const storedChat = readStoredChat(storageKey, selectedProjectName);
    setDraft(storedChat.draft);
    setMessages(storedChat.messages);
  }, [storageKey, selectedProjectName]);

  useEffect(() => {
    window.localStorage.setItem(
      storageKey,
      JSON.stringify({
        draft,
        messages: messages.slice(-20),
      }),
    );
  }, [draft, messages, storageKey]);

  useEffect(() => {
    if (clearRequest === handledClearRequestRef.current) return;
    handledClearRequestRef.current = clearRequest;
    window.localStorage.removeItem(storageKey);
    const emptyChat = createInitialChat(selectedProjectName);
    setDraft(emptyChat.draft);
    setMessages(emptyChat.messages);
  }, [clearRequest, selectedProjectName, storageKey]);

  useEffect(() => {
    onBusyChange(questionMutation.isPending);
    return () => onBusyChange(false);
  }, [onBusyChange, questionMutation.isPending]);

  useEffect(() => {
    if (!questionMutation.isPending) return undefined;
    const preventUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", preventUnload);
    return () => window.removeEventListener("beforeunload", preventUnload);
  }, [questionMutation.isPending]);

  function sendQuestion(question: string) {
    const value = question.trim();
    if (!value || !selectedProjectId || questionMutation.isPending) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: value,
    };
    setMessages((items) => [...items, userMessage]);
    setDraft("");
    const conversationContext = buildConversationContext(messages);

    questionMutation.mutate(
      { question: value, conversationContext },
      {
        onSuccess: (answer: ProjectQuestionAnswer) => {
          setMessages((items) => [
            ...items,
            {
              id: `assistant-${Date.now()}`,
              role: "assistant",
              content: answer.answer,
              evidenceIds: answer.evidence_ids,
              evidenceSources: answer.evidence_sources,
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
    <div className="mx-auto box-border flex h-full min-h-0 w-full max-w-5xl min-w-0 flex-col overflow-hidden overscroll-contain">
      <div className="min-h-0 w-full max-w-full min-w-0 flex-1 space-y-6 overflow-y-auto overflow-x-hidden overscroll-contain pb-3 pt-3 sm:space-y-8 sm:pb-4 sm:pt-0 sm:pr-1">
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

      <div className="chat-composer-shell box-border w-full max-w-full min-w-0 shrink-0 overflow-hidden border-t border-slate-200/70 bg-slate-50 px-2 pt-2 dark:border-slate-800 dark:bg-[#080c14] sm:px-0 sm:pt-4">
        <form
          onSubmit={handleSubmit}
          className="mx-auto box-border flex w-full max-w-3xl min-w-0 items-end gap-2 rounded-3xl border border-slate-200 bg-white p-2 shadow-lg shadow-slate-200/60 dark:border-slate-800 dark:bg-slate-900 dark:shadow-black/30"
        >
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                if (canSubmit) {
                  sendQuestion(draft);
                }
              }
            }}
            placeholder="Задайте вопрос о проекте"
            rows={1}
            className="max-h-32 min-h-10 min-w-0 flex-1 resize-none bg-transparent px-3 py-2 text-base leading-6 text-slate-900 outline-none placeholder:text-slate-400 dark:text-slate-100 dark:placeholder:text-slate-500"
          />
          <button
            type="submit"
            disabled={!canSubmit}
            className="grid size-10 shrink-0 place-items-center rounded-full bg-indigo-600 text-white transition hover:bg-indigo-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 disabled:cursor-not-allowed disabled:bg-slate-300 dark:bg-indigo-500 dark:hover:bg-indigo-400 dark:disabled:bg-slate-700"
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

function chatStorageKey(projectId: string | null, asOfDate: string) {
  return `${CHAT_STORAGE_PREFIX}.${projectId ?? "none"}.${asOfDate}`;
}

function readStoredChat(
  storageKey: string,
  selectedProjectName?: string,
): {
  draft: string;
  messages: ChatMessage[];
} {
  if (typeof window !== "undefined") {
    try {
      const rawValue = window.localStorage.getItem(storageKey);
      if (rawValue) {
        const parsed = JSON.parse(rawValue) as {
          draft?: unknown;
          messages?: unknown;
        };
        if (Array.isArray(parsed.messages) && parsed.messages.length > 0) {
          return {
            draft: typeof parsed.draft === "string" ? parsed.draft : "",
            messages: parsed.messages.filter(isChatMessage).slice(-20),
          };
        }
      }
    } catch {
      // Переходим к приветственному сообщению ниже.
    }
  }
  return createInitialChat(selectedProjectName);
}

function createInitialChat(selectedProjectName?: string): {
  draft: string;
  messages: ChatMessage[];
} {
  return {
    draft: "",
    messages: [
      {
        id: `welcome-${selectedProjectName ?? "none"}`,
        role: "assistant",
        content: selectedProjectName
          ? `Выбран проект «${selectedProjectName}». Задайте вопрос по статусу, срокам, рискам, бюджету или блокерам.`
          : "Выберите проект, чтобы задать вопрос.",
      },
    ],
  };
}

function isChatMessage(value: unknown): value is ChatMessage {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<ChatMessage>;
  return (
    typeof item.id === "string" &&
    typeof item.content === "string" &&
    (item.role === "assistant" || item.role === "user")
  );
}

function buildConversationContext(
  messages: ChatMessage[],
): ProjectChatContextMessage[] {
  const relevantMessages = messages
    .filter(
      (message) =>
        !message.id.startsWith("welcome") && message.content.trim().length > 0,
    )
    .slice(-CONTEXT_MESSAGE_LIMIT);

  const context: ProjectChatContextMessage[] = [];
  let remainingChars = CONTEXT_TOTAL_CHARS;

  for (const message of relevantMessages) {
    if (remainingChars <= 0) break;

    const content = trimForContext(
      message.content,
      Math.min(CONTEXT_CHARS_PER_MESSAGE, remainingChars),
    );
    if (!content) continue;

    context.push({ role: message.role, content });
    remainingChars -= content.length;
  }

  return context;
}

function trimForContext(value: string, limit: number) {
  const compact = value.replace(/\s+/g, " ").trim();
  if (compact.length <= limit) return compact;
  return `${compact.slice(0, Math.max(0, limit - 3)).trim()}...`;
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
  const [isSourcesOpen, setIsSourcesOpen] = useState(false);

  if (message.role === "user") {
    return (
      <div className="flex min-w-0 justify-end">
        <div className="max-w-[88%] break-words rounded-3xl bg-slate-200 px-4 py-2.5 text-base leading-6 text-slate-800 [overflow-wrap:anywhere] dark:bg-slate-700 dark:text-slate-100 sm:max-w-[76%]">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl min-w-0 gap-2 sm:gap-3">
      <div className="mt-1 grid size-7 shrink-0 place-items-center rounded-full border border-slate-200 bg-white text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
        <Bot aria-hidden className="size-4" />
      </div>
      <div className="min-w-0 flex-1">
        <MarkdownContent content={message.content} />
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {message.evidenceIds?.length ? (
            <span className="inline-flex max-w-full items-center overflow-hidden text-ellipsis whitespace-nowrap rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              evidence: {message.evidenceIds.join(", ")}
            </span>
          ) : null}
          {message.evidenceSources?.length ? (
            <button
              type="button"
              onClick={() => setIsSourcesOpen(true)}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 transition hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-indigo-800 dark:hover:bg-indigo-950/40 dark:hover:text-indigo-200"
            >
              <Eye aria-hidden className="size-3.5" />
              Источники ({message.evidenceSources.length})
            </button>
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
                className="inline-flex max-w-full min-w-0 items-center gap-1.5 whitespace-normal rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-left text-xs font-medium text-indigo-700 transition [overflow-wrap:anywhere] hover:border-indigo-300 hover:bg-indigo-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 disabled:cursor-not-allowed disabled:opacity-60 dark:border-indigo-800 dark:bg-indigo-950/40 dark:text-indigo-300 dark:hover:bg-indigo-950/70"
              >
                <span className="min-w-0">{question}</span>
                <ArrowRight aria-hidden className="size-3 shrink-0" />
              </button>
            ))}
          </div>
        ) : null}
      </div>
      {isSourcesOpen && message.evidenceSources?.length ? (
        <EvidenceSourcesModal
          sources={message.evidenceSources}
          evidenceIds={message.evidenceIds ?? []}
          onClose={() => setIsSourcesOpen(false)}
        />
      ) : null}
    </div>
  );
}

function EvidenceSourcesModal({
  sources,
  evidenceIds,
  onClose,
}: {
  sources: ProjectEvidenceSource[];
  evidenceIds: string[];
  onClose: () => void;
}) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="evidence-sources-title"
      className="fixed inset-0 z-50 grid place-items-center overflow-hidden bg-slate-950/50 p-3 backdrop-blur-sm sm:p-4"
      onClick={onClose}
    >
      <div
        className="flex max-h-[calc(100svh-1.5rem)] w-full max-w-4xl min-w-0 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl shadow-slate-950/20 dark:border-slate-800 dark:bg-slate-950 sm:max-h-[86vh]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 p-4 dark:border-slate-800">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Database
                aria-hidden
                className="size-4 text-indigo-600 dark:text-indigo-300"
              />
              <h2
                id="evidence-sources-title"
                className="text-base font-semibold text-slate-950 dark:text-slate-50"
              >
                Источники ответа
              </h2>
            </div>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Данные ниже взяты из реально выполненных tools. По ним можно
              проверить, откуда агент сформировал ответ.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid size-9 shrink-0 place-items-center rounded-lg border border-slate-200 bg-white text-slate-600 transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            <X aria-hidden className="size-4" />
            <span className="sr-only">Закрыть</span>
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
          {evidenceIds.length ? (
            <div className="break-words rounded-lg border border-indigo-100 bg-indigo-50 px-3 py-2 text-xs font-medium text-indigo-800 [overflow-wrap:anywhere] dark:border-indigo-900/60 dark:bg-indigo-950/40 dark:text-indigo-200">
              ID из ответа: {evidenceIds.join(", ")}
            </div>
          ) : null}
          {sources.map((source, index) => (
            <article
              key={`${source.id}-${index}`}
              className="rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-900/70"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <h3 className="break-words text-sm font-semibold text-slate-950 dark:text-slate-50">
                    {source.title}
                  </h3>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    <Badge tone="neutral">{source.tool}</Badge>
                    <Badge tone="neutral">{source.source_type}</Badge>
                    {source.reference ? (
                      <Badge tone="neutral">{source.reference}</Badge>
                    ) : null}
                  </div>
                </div>
              </div>
              {source.excerpt ? (
                <p className="mt-3 whitespace-pre-wrap break-words rounded-lg border border-slate-200 bg-white p-3 text-sm leading-6 text-slate-700 [overflow-wrap:anywhere] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200">
                  {source.excerpt}
                </p>
              ) : null}
              <pre className="mt-3 max-h-72 max-w-full overflow-auto rounded-lg bg-slate-950 p-3 text-xs leading-5 text-slate-100">
                {formatSourceData(source.data)}
              </pre>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}

function formatSourceData(data: Record<string, unknown>) {
  return JSON.stringify(data, null, 2);
}

function TypingBubble() {
  return (
    <div className="mx-auto flex w-full max-w-3xl min-w-0 gap-2 sm:gap-3">
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
