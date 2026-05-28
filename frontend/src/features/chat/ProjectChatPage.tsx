import { ArrowRight, ArrowUp, Bot, Copy, Database, Eye, X } from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";

import type {
  PortfolioProjectSummary,
  ProjectAnswerClaim,
  ProjectAnswerVerification,
  ProjectChatContextMessage,
  ProjectEvidenceSource,
  ProjectQuestionAnswer,
  ProjectRunMetrics,
  ProjectStreamEvent,
} from "../../api/types";
import { Badge } from "../../components/ui";
import { useProjectQuestion } from "../../hooks/useProjectQuestion";
import { MarkdownContent } from "./MarkdownContent";
import { RetrievalProvenance } from "./RetrievalProvenance";

type ChatMessage =
  | {
      id: string;
      role: "assistant";
      content: string;
      evidenceIds?: string[];
      evidenceSources?: ProjectEvidenceSource[];
      suggestedQuestions?: string[];
      streaming?: boolean;
      failed?: boolean;
      reasoning?: string;
      progress?: {
        key?: string;
        text: string;
        done?: boolean;
        args?: Record<string, unknown>;
      }[];
      startedAt?: number;
      metrics?: ProjectRunMetrics;
      verification?: ProjectAnswerVerification;
      claims?: ProjectAnswerClaim[];
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
const VERIFY_CLAIMS_STORAGE_KEY = "sdm-hack.verify-claims";
const STREAM_PROGRESS_LIMIT = 80;

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
  const [verifyClaims, setVerifyClaims] = useState(() => {
    try {
      return window.localStorage.getItem(VERIFY_CLAIMS_STORAGE_KEY) === "true";
    } catch {
      return false;
    }
  });
  useEffect(() => {
    try {
      window.localStorage.setItem(
        VERIFY_CLAIMS_STORAGE_KEY,
        String(verifyClaims),
      );
    } catch {
      // Настройка продолжает работать, если сохранение недоступно.
    }
  }, [verifyClaims]);
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
        messages: messages.slice(-20).map(prepareStoredMessage),
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
    const assistantId = `assistant-${Date.now()}`;
    setMessages((items) => [
      ...items,
      userMessage,
      {
        id: assistantId,
        role: "assistant",
        content: "",
        streaming: true,
        startedAt: Date.now(),
        progress: [{ text: "Подключаюсь к агенту…" }],
      },
    ]);
    setDraft("");
    const conversationContext = buildConversationContext(messages);

    questionMutation.mutate(
      {
        question: value,
        verifyClaims,
        conversationContext,
        onEvent: (event) => {
          setMessages((items) =>
            items.map((item) =>
              item.id === assistantId && item.role === "assistant"
                ? applyStreamEvent(item, event)
                : item,
            ),
          );
        },
      },
      {
        onSuccess: (answer: ProjectQuestionAnswer) => {
          setMessages((items) =>
            items.map((item) =>
              item.id === assistantId && item.role === "assistant"
                ? {
                    ...item,
                    streaming: false,
                    metrics: {
                      ...item.metrics,
                      duration_ms:
                        item.metrics?.duration_ms ??
                        Date.now() - (item.startedAt ?? Date.now()),
                    },
                    content: answer.answer,
                    evidenceIds: answer.evidence_ids,
                    evidenceSources: answer.evidence_sources,
                    suggestedQuestions: answer.suggested_questions,
                    verification: answer.verification,
                    claims: answer.claims,
                  }
                : item,
            ),
          );
        },
        onError: (error) => {
          setMessages((items) =>
            items.map((item) =>
              item.id === assistantId && item.role === "assistant"
                ? {
                    ...item,
                    streaming: false,
                    metrics: {
                      ...item.metrics,
                      duration_ms: Date.now() - (item.startedAt ?? Date.now()),
                    },
                    content: formatAgentError(error),
                    failed: true,
                  }
                : item,
            ),
          );
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
        <div ref={bottomRef} />
        {messages.every((message) => message.id.startsWith("welcome")) ? (
          <div className="mx-auto flex max-w-3xl flex-wrap gap-2">
            {(selectedProjectId === "P007"
              ? [
                  "При каких условиях можно начать пилот?",
                  "Утверждён ли резерв 600 тыс рублей?",
                  "Кто подписал промышленный ввод?",
                ]
              : ["Что мешает завершить проект и какие данные это подтверждают?"]
            ).map((question) => (
              <button
                key={question}
                type="button"
                disabled={!selectedProjectId || questionMutation.isPending}
                onClick={() => sendQuestion(question)}
                className="rounded-xl border border-indigo-200 bg-indigo-50 px-3 py-2 text-left text-sm text-indigo-700 hover:bg-indigo-100 disabled:opacity-50 dark:border-indigo-800 dark:bg-indigo-950/40 dark:text-indigo-200"
              >
                {question}
              </button>
            ))}
          </div>
        ) : null}
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
        <div className="mx-auto flex w-full max-w-3xl min-w-0 items-center px-3 py-2">
          <button
            type="button"
            role="switch"
            aria-checked={verifyClaims}
            disabled={questionMutation.isPending}
            onClick={() => setVerifyClaims((enabled) => !enabled)}
            title="Проверить каждый тезис по источникам. Ответ займёт больше времени."
            className="flex items-center gap-2 rounded-md text-xs text-slate-600 outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 disabled:cursor-not-allowed disabled:opacity-50 dark:text-slate-300"
          >
            <span
              aria-hidden="true"
              className={`inline-flex h-5 w-9 shrink-0 items-center rounded-full p-0.5 transition-colors ${verifyClaims ? "bg-indigo-600 dark:bg-indigo-500" : "bg-slate-300 dark:bg-slate-600"}`}
            >
              <span
                className={`size-4 rounded-full bg-white shadow-sm transition-transform ${verifyClaims ? "translate-x-4" : "translate-x-0"}`}
              />
            </span>
            Доп. проверка тезисов
          </button>
        </div>
      </div>
    </div>
  );
}

function formatAgentError(error: unknown) {
  if (error instanceof Error && error.name === "AbortError") {
    return "Запрос отменён. Отправьте вопрос ещё раз, если ответ ещё нужен.";
  }
  if (error instanceof Error && error.message) return error.message;
  return "Не удалось получить ответ агента. Отправьте вопрос ещё раз.";
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
        {message.startedAt ? <StreamProgress message={message} /> : null}
        <MarkdownContent content={message.content} />
        {!message.streaming && !message.failed && message.verification ? (
          <VerificationSummary verification={message.verification} />
        ) : null}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {message.evidenceSources?.length || message.claims?.length ? (
            <button
              type="button"
              onClick={() => setIsSourcesOpen(true)}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 transition hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-indigo-800 dark:hover:bg-indigo-950/40 dark:hover:text-indigo-200"
            >
              <Eye aria-hidden className="size-3.5" />
              Источники ({message.evidenceSources?.length ?? 0})
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => {
              void navigator.clipboard
                .writeText(message.content)
                .catch(() => undefined);
            }}
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
      {isSourcesOpen &&
      (message.evidenceSources?.length || message.claims?.length) ? (
        <EvidenceSourcesModal
          sources={message.evidenceSources ?? []}
          claims={message.claims}
          onClose={() => setIsSourcesOpen(false)}
        />
      ) : null}
    </div>
  );
}

function EvidenceSourcesModal({
  sources,
  claims,
  onClose,
}: {
  sources: ProjectEvidenceSource[];
  claims?: ProjectAnswerClaim[];
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
              Фрагменты документов и записи проекта, использованные в ответе.
              Сопоставьте их с утверждениями агента.
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
          {claims?.length ? (
            <ClaimEvidence claims={claims} sources={sources} />
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
                    {source.reference ? (
                      <Badge tone="neutral">{source.reference}</Badge>
                    ) : null}
                  </div>
                </div>
              </div>
              <RetrievalProvenance value={source.data.retrieval} />
              {source.excerpt ? (
                <p className="mt-3 whitespace-pre-wrap break-words rounded-lg border border-slate-200 bg-white p-3 text-sm leading-6 text-slate-700 [overflow-wrap:anywhere] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200">
                  {source.excerpt}
                </p>
              ) : null}
              <details className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                <summary className="cursor-pointer">
                  Исходная запись (JSON)
                </summary>
                <pre className="mt-2 max-h-72 max-w-full overflow-auto rounded-lg bg-slate-950 p-3 text-xs leading-5 text-slate-100">
                  {formatSourceData(source.data)}
                </pre>
              </details>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}

function ClaimEvidence({
  claims,
  sources,
}: {
  claims: ProjectAnswerClaim[];
  sources: ProjectEvidenceSource[];
}) {
  const sourceById = new Map(sources.map((source) => [source.id, source]));
  return (
    <section aria-label="Утверждения и подтверждения" className="space-y-3">
      <h3 className="text-sm font-semibold text-slate-950 dark:text-slate-50">
        Утверждения и подтверждения
      </h3>
      {claims.map((claim, index) => (
        <article
          key={index}
          className="rounded-xl border border-indigo-100 p-3 text-sm [overflow-wrap:anywhere] dark:border-indigo-900/60"
        >
          <p className="font-medium text-slate-900 dark:text-slate-100">
            {claim.text}
          </p>
          {claim.evidence?.length ? (
            <div className="mt-2 space-y-3">
              {claim.evidence.slice(0, 4).map((evidence, evidenceIndex) => (
                <figure key={evidenceIndex}>
                  <blockquote className="border-l-2 border-indigo-200 pl-3 whitespace-pre-wrap text-slate-700 dark:border-indigo-800 dark:text-slate-300">
                    {evidence.quote}
                  </blockquote>
                  <figcaption className="mt-1 pl-3 text-xs text-slate-500 dark:text-slate-400">
                    {sourceById.get(evidence.source_id)?.title ??
                      "Источник не включён в ответ"}
                  </figcaption>
                </figure>
              ))}
            </div>
          ) : (
            <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              <p>Точная цитата для этого утверждения не предоставлена.</p>
              {claim.evidence_ids.length ? (
                <p className="mt-1">
                  Связанные источники:{" "}
                  {claim.evidence_ids
                    .map(
                      (id) =>
                        sourceById.get(id)?.title ??
                        "Источник не включён в ответ",
                    )
                    .join("; ")}
                </p>
              ) : null}
            </div>
          )}
        </article>
      ))}
    </section>
  );
}

function formatSourceData(data: Record<string, unknown>) {
  return JSON.stringify(data, null, 2);
}

type AssistantMessage = Extract<ChatMessage, { role: "assistant" }>;

function VerificationSummary({
  verification,
}: {
  verification: ProjectAnswerVerification;
}) {
  const status = {
    passed: "Подтверждения найдены в доступных источниках.",
    partial:
      verification.supported_claims === verification.checked_claims
        ? "Все утверждения ответа прошли проверку, но вопрос раскрыт не полностью."
        : "Частичный ответ: утверждения, не прошедшие проверку, исключены.",
    abstained: "Недостаточно данных для обоснованного ответа.",
    unavailable: "Проверка подтверждений недоступна.",
    not_checked:
      "Ответ по источникам. Дополнительная проверка тезисов выключена.",
  }[verification.status];
  return (
    <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600 dark:bg-slate-900 dark:text-slate-300">
      <p>{status}</p>
      {verification.status !== "unavailable" &&
      verification.status !== "not_checked" ? (
        <p>
          Подтверждено: {verification.supported_claims} из{" "}
          {verification.checked_claims} проверенных утверждений. Дополнительных
          раундов поиска: {verification.recovery_rounds}.
        </p>
      ) : null}
    </div>
  );
}

function stageLabel(stage: string): string {
  const labels: Record<string, string> = {
    request_project_context: "Загрузка контекста проекта",
    route_request: "Определение типа вопроса",
    select_tools: "Выбор источников",
    run_tools: "Поиск данных",
    draft_answer: "Подготовка предварительного ответа",
    verify_answer: "Проверка подтверждений в источниках",
    recover_evidence: "Подготовка дополнительного поиска",
    run_recovery_tools: "Дополнительный поиск подтверждений",
    finalize_answer: "Подготовка ответа с источниками",
    rerank_evidence: "Оценка релевантности источников моделью",
    rerank: "Оценка релевантности источников моделью",
  };
  return labels[stage] ?? "Обработка вопроса";
}

function modelOperationLabel(operation: string): string {
  const labels: Record<string, string> = {
    RequestRoute: "Определение типа вопроса",
    tool_selection: "Выбор инструментов",
    GroundedAnswerDraft: "Подготовка тезисов",
    GroundedProjectQuestionLLMAnswer: "Подготовка ответа по источникам",
    ClaimSupport: "Проверка отдельного тезиса",
    EvidenceReview: "Проверка полноты и противоречий",
    EvidenceReranking: "Ранжирование источников",
    ProjectQuestionLLMAnswer: "Подготовка короткого ответа",
  };
  return labels[operation] ?? "Обработка данных моделью";
}

function applyStreamEvent(
  message: AssistantMessage,
  event: ProjectStreamEvent,
): AssistantMessage {
  if (event.type === "llm_progress") {
    if (event.operation !== "EvidenceReranking") return message;
    const prefix = "Модель формирует порядок источников · получено ";
    const detail = `${prefix}${event.received_characters} символов`;
    const progress = [...(message.progress ?? [])];
    const existing = progress.findIndex((line) => line.text.startsWith(prefix));
    if (existing >= 0) progress[existing] = { text: detail };
    else progress.push({ text: detail });
    return { ...message, progress: progress.slice(-STREAM_PROGRESS_LIMIT) };
  }
  if (event.type === "reasoning_delta") return message;
  if (event.type === "answer_delta")
    return { ...message, content: message.content + event.text };
  if (event.type === "final")
    return {
      ...message,
      metrics: event.metrics,
      verification: event.answer.verification,
      claims: event.answer.claims,
    };
  if (event.type === "usage")
    return {
      ...message,
      metrics: {
        ...message.metrics,
        input_tokens: event.input_tokens ?? undefined,
        output_tokens: event.output_tokens ?? undefined,
        total_tokens: event.total_tokens ?? undefined,
      },
    };
  let detail: string | undefined;
  let progressKey: string | undefined;
  let finished = false;
  if (event.type === "verification_failed")
    detail = "Не удалось завершить проверку подтверждений в источниках";
  if (event.type === "recovery_skipped")
    detail =
      event.reason === "answer_supported"
        ? "Все тезисы подтверждены. Завершаю ответ с оговоркой о непокрытых частях вопроса."
        : "Дополнительный поиск пропущен: времени на повторную проверку недостаточно.";
  if (event.type === "draft_reused")
    detail =
      "Новый черновик не получен. Повторно проверяю прежние тезисы по обновлённым источникам.";
  if (event.type === "evidence_review") {
    detail = `Проверка ${event.round}: найдены подтверждения для ${event.supported} из ${event.claims_total} утверждений`;
    if (event.unsupported > 0)
      detail += ` · без подтверждений: ${event.unsupported}`;
    if (event.contradicted > 0)
      detail += ` · противоречия в источниках: ${event.contradicted}`;
    if (event.recovery_available) detail += " · доступен дополнительный поиск";
  }
  if (event.type === "evidence_recovery") {
    detail = `Дополнительный поиск ${event.round}${event.queries.length ? `: ${event.queries.join("; ")}` : ": уточняю данные в источниках"}`;
  }
  if (event.type === "run_started") detail = "Агент начал анализ";
  if (event.type === "llm_retry")
    detail = `${modelOperationLabel(event.operation)}: исправляю структуру ответа модели · попытка ${event.attempt} из ${event.max_attempts}`;
  if (
    event.type === "rerank_started" ||
    event.type === "rerank_completed" ||
    event.type === "rerank_failed"
  ) {
    const facts = [
      event.candidate_count != null
        ? `кандидатов: ${event.candidate_count}`
        : "",
      event.returned_count != null ? `отобрано: ${event.returned_count}` : "",
      event.model ? `модель: ${event.model}` : "",
      event.duration_ms != null
        ? `${(event.duration_ms / 1000).toFixed(1)} с`
        : "",
    ].filter(Boolean);
    const status =
      event.type === "rerank_started"
        ? "LLM оценивает релевантность найденных источников"
        : event.type === "rerank_completed"
          ? "✓ LLM завершила упорядочивание источников"
          : "Оценка источников через LLM не удалась — используем исходный порядок RRF";
    detail = [status, ...facts].join(" · ");
  }
  if (event.type === "stage_started" || event.type === "stage_finished") {
    progressKey = `stage:${event.stage}`;
    finished = event.type === "stage_finished";
    detail = finished
      ? `${event.status === "error" ? "Ошибка" : "✓"} ${stageLabel(event.stage)}${event.duration_ms == null ? "" : ` · ${(event.duration_ms / 1000).toFixed(1)} с`}`
      : stageLabel(event.stage);
  }
  if (event.type === "llm_started" || event.type === "llm_finished") {
    // Эти вызовы уже отображаются как этапы графа или события ранжирования.
    const stages: Record<string, string> = {
      RequestRoute: "route_request",
      tool_selection: "select_tools",
      GroundedAnswerDraft: "draft_answer",
      GroundedProjectQuestionLLMAnswer: "finalize_answer",
      ProjectQuestionLLMAnswer: "finalize_answer",
    };
    const stage = stages[event.operation];
    if (
      event.operation === "EvidenceReranking" ||
      (stage &&
        message.progress?.some(
          (entry) => entry.key === `stage:${stage}` && !entry.done,
        ))
    )
      return message;
    progressKey = `llm:${event.operation}`;
    finished = event.type === "llm_finished";
    if (event.type === "llm_finished") {
      const status =
        event.status === "incomplete"
          ? "Ответ модели не завершён"
          : event.status === "refused"
            ? "Модель отказалась отвечать"
            : "✓";
      detail = `${status} ${modelOperationLabel(event.operation)} · ${(event.duration_ms / 1000).toFixed(1)} с`;
    } else {
      detail = modelOperationLabel(event.operation);
    }
  }
  if (event.type === "tool_started" || event.type === "tool_finished") {
    progressKey = `tool:${event.call_id}`;
    finished = event.type === "tool_finished";
    detail =
      event.type === "tool_started"
        ? `Инструмент: ${event.name}`
        : `${event.status === "error" ? "Ошибка" : "✓"} ${event.name} · ${(event.duration_ms / 1000).toFixed(1)} с${event.summary ? ` · ${event.summary}` : ""}`;
  }
  if (!detail) return message;
  const progress = [...(message.progress ?? [])];
  const pending =
    finished && progressKey
      ? progress.findIndex((entry) => entry.key === progressKey && !entry.done)
      : -1;
  const entry = {
    key: progressKey,
    text: detail,
    done: finished,
    args: event.type === "tool_started" ? event.args : progress[pending]?.args,
  };
  if (pending >= 0) progress[pending] = entry;
  else progress.push(entry);
  return { ...message, progress: progress.slice(-STREAM_PROGRESS_LIMIT) };
}

function prepareStoredMessage(message: ChatMessage): ChatMessage {
  if (message.role !== "assistant") return message;
  const stored: AssistantMessage = { ...message };
  delete stored.reasoning;
  delete stored.progress;
  if (!message.streaming) return stored;
  return {
    ...stored,
    streaming: false,
    failed: true,
    content: message.content || "Ответ был прерван. Отправьте вопрос ещё раз.",
    metrics: {
      ...message.metrics,
      duration_ms: Date.now() - (message.startedAt ?? Date.now()),
    },
  };
}

function StreamProgress({ message }: { message: AssistantMessage }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!message.streaming) return;
    const timer = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(timer);
  }, [message.streaming]);
  const seconds = (
    (message.metrics?.duration_ms ??
      Math.max(0, now - (message.startedAt ?? now))) / 1000
  ).toFixed(1);
  return (
    <div className="mb-3 text-xs text-slate-500 dark:text-slate-400">
      <div role="status" className="mb-2">
        {message.streaming
          ? "Анализирую"
          : message.failed
            ? "Ответ не получен"
            : "Завершено"}{" "}
        · {seconds} с
        {message.metrics?.ttft_ms != null
          ? ` · первый токен ${(message.metrics.ttft_ms / 1000).toFixed(1)} с`
          : ""}
        {message.metrics?.total_tokens != null
          ? ` · ${message.metrics.total_tokens} токенов`
          : ""}
      </div>
      <details className="rounded-xl border border-slate-200 p-3 dark:border-slate-800">
        <summary className="cursor-pointer">
          Ход анализа
          {message.streaming && message.progress?.length
            ? ` · ${message.progress[message.progress.length - 1].text}`
            : ""}
        </summary>
        <div className="mt-2 max-h-72 space-y-1 overflow-auto whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
          {message.progress?.map((line, index) => (
            <div key={index}>
              {line.text}
              {line.args ? ` · ${JSON.stringify(line.args)}` : ""}
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
