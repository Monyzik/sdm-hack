/**
 * Тонкий HTTP-клиент над эндпоинтами summary.
 *
 * Здесь сосредоточена вся работа с сетью: построение URL, разбор ответа и
 * единообразная обработка ошибок. Компоненты и хуки не знают про `fetch`.
 * Контракты эндпоинтов не меняются.
 */
import { AGENTS_API_URL, API_URL } from "../lib/constants";
import type {
  PortfolioAttentionSummary,
  PortfolioSummary,
  ProjectChatContextMessage,
  ProjectProblemContext,
  ProjectQuestionAnswer,
  ProjectStreamEvent,
  ProjectSummary,
  ProjectTrends,
} from "./types";

/** Ошибка запроса с сохранённым HTTP-статусом — удобно различать 404 и прочее. */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(
  path: string,
  signal?: AbortSignal,
  init?: RequestInit,
): Promise<T> {
  return requestFrom<T>(API_URL, path, signal, init);
}

async function requestFrom<T>(
  baseUrl: string,
  path: string,
  signal?: AbortSignal,
  init?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiUrl(baseUrl, path), { ...init, signal });
  } catch {
    throw new ApiError(
      "Не удалось связаться с сервером. Проверьте, что сервис запущен.",
      0,
    );
  }

  if (!response.ok) {
    let message = `Запрос завершился с ошибкой ${response.status}`;
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") {
        message = payload.detail;
      }
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}

function apiUrl(baseUrl: string, path: string): string {
  const base = baseUrl.replace(/\/+$/, "");
  if (!base) {
    return path;
  }
  if (base.endsWith("/api") && path.startsWith("/api/")) {
    return `${base}${path.slice("/api".length)}`;
  }
  return `${base}${path}`;
}

export function fetchPortfolioSummary(
  asOf: string,
  signal?: AbortSignal,
): Promise<PortfolioSummary> {
  const query = new URLSearchParams({ as_of: asOf });
  return request<PortfolioSummary>(
    `/api/v1/summaries/portfolio?${query.toString()}`,
    signal,
  );
}

export function fetchPortfolioAttention(
  asOf: string,
  lookbackDays = 7,
  signal?: AbortSignal,
): Promise<PortfolioAttentionSummary> {
  const query = new URLSearchParams({
    as_of: asOf,
    lookback_days: lookbackDays.toString(),
  });
  return request<PortfolioAttentionSummary>(
    `/api/v1/summaries/portfolio/attention?${query.toString()}`,
    signal,
  );
}

export function fetchProjectSummary(
  projectId: string,
  asOf: string,
  signal?: AbortSignal,
): Promise<ProjectSummary> {
  const query = new URLSearchParams({ as_of: asOf });
  return request<ProjectSummary>(
    `/api/v1/summaries/projects/${encodeURIComponent(projectId)}?${query.toString()}`,
    signal,
  );
}

export function fetchProjectProblemContext(
  projectId: string,
  asOf: string,
  maxDepth = 2,
  signal?: AbortSignal,
): Promise<ProjectProblemContext> {
  const query = new URLSearchParams({
    as_of: asOf,
    max_depth: maxDepth.toString(),
  });
  return request<ProjectProblemContext>(
    `/api/v1/summaries/projects/${encodeURIComponent(projectId)}/problem-context?${query.toString()}`,
    signal,
  );
}

export function fetchProjectTrends(
  projectId: string,
  asOf: string,
  points = 8,
  signal?: AbortSignal,
): Promise<ProjectTrends> {
  const query = new URLSearchParams({
    as_of: asOf,
    points: points.toString(),
  });
  return request<ProjectTrends>(
    `/api/v1/summaries/projects/${encodeURIComponent(projectId)}/trends?${query.toString()}`,
    signal,
  );
}

export async function streamProjectAgent(
  projectId: string,
  question: string,
  asOf: string,
  conversationContext: ProjectChatContextMessage[] | undefined,
  onEvent: (event: ProjectStreamEvent) => void,
  signal: AbortSignal,
  verifyClaims = true,
): Promise<ProjectQuestionAnswer> {
  let response: Response;
  try {
    response = await fetch(
      apiUrl(
        AGENTS_API_URL,
        `/api/v1/agents/projects/${encodeURIComponent(projectId)}/ask/stream`,
      ),
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({
          question,
          as_of: asOf,
          max_depth: 2,
          verify_claims: verifyClaims,
          conversation_context: conversationContext ?? [],
        }),
        signal,
      },
    );
  } catch {
    signal.throwIfAborted();
    throw new ApiError(
      "Не удалось подключиться к агенту. Проверьте соединение и отправьте вопрос ещё раз.",
      0,
    );
  }
  if (!response.ok)
    throw new ApiError(
      `Запрос завершился с ошибкой ${response.status}`,
      response.status,
    );
  if (!response.body) throw new Error("Сервер не вернул поток ответа");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let answer: ProjectQuestionAnswer | undefined;
  const dispatch = (frame: string) => {
    let eventName = "message";
    const data: string[] = [];
    for (const line of frame.split(/\r?\n/)) {
      if (line.startsWith("event:")) eventName = line.slice(6).trim();
      if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
    }
    if (!data.length) return;
    const payload = JSON.parse(data.join("\n")) as ProjectStreamEvent;
    const event = {
      ...payload,
      type: eventName === "message" ? payload.type : eventName,
    } as ProjectStreamEvent;
    onEvent(event);
    if (event.type === "error") throw new Error(event.message);
    if (event.type === "final") answer = event.answer;
  };
  try {
    while (true) {
      let chunk: ReadableStreamReadResult<Uint8Array>;
      try {
        chunk = await reader.read();
      } catch {
        signal.throwIfAborted();
        throw new ApiError(
          "Соединение с агентом прервалось до завершения ответа. Отправьте вопрос ещё раз.",
          0,
        );
      }
      const { value, done } = chunk;
      buffer += decoder.decode(value, { stream: !done });
      let boundary: RegExpExecArray | null;
      while ((boundary = /\r?\n\r?\n/.exec(buffer))) {
        dispatch(buffer.slice(0, boundary.index));
        buffer = buffer.slice(boundary.index + boundary[0].length);
        if (answer) return answer;
      }
      if (done) break;
    }
    if (buffer.trim()) dispatch(buffer);
    if (!answer)
      throw new Error(
        "Поток прервался до завершения ответа. Попробуйте ещё раз.",
      );
    return answer;
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
