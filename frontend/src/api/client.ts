/**
 * Тонкий HTTP-клиент над эндпоинтами summary.
 *
 * Здесь сосредоточена вся работа с сетью: построение URL, разбор ответа и
 * единообразная обработка ошибок. Компоненты и хуки не знают про `fetch`.
 * Контракты эндпоинтов не меняются.
 */
import { AGENTS_API_URL, API_URL } from "../lib/constants";
import type {
  InternalNotification,
  NotificationList,
  PortfolioAttentionSummary,
  PortfolioSummary,
  ProjectManagerBrief,
  ProjectQuestionAnswer,
  ProjectSummary,
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
    response = await fetch(`${baseUrl}${path}`, { ...init, signal });
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

export function fetchNotifications(
  options: {
    projectId?: string;
    asOfDate?: string;
    unreadOnly?: boolean;
    limit?: number;
  } = {},
  signal?: AbortSignal,
): Promise<NotificationList> {
  const query = new URLSearchParams();
  if (options.projectId) {
    query.set("project_id", options.projectId);
  }
  if (options.asOfDate) {
    query.set("as_of_date", options.asOfDate);
  }
  if (options.unreadOnly) {
    query.set("unread_only", "true");
  }
  if (options.limit) {
    query.set("limit", options.limit.toString());
  }

  const queryString = query.toString();
  const suffix = queryString ? `?${queryString}` : "";
  return request<NotificationList>(`/api/v1/notifications${suffix}`, signal);
}

export function markNotificationRead(
  notificationId: string,
  signal?: AbortSignal,
): Promise<InternalNotification> {
  return request<InternalNotification>(
    `/api/v1/notifications/${encodeURIComponent(notificationId)}/read`,
    signal,
    { method: "PATCH" },
  );
}

export function fetchProjectBrief(
  projectId: string,
  asOf: string,
  signal?: AbortSignal,
): Promise<ProjectManagerBrief> {
  const query = new URLSearchParams({ as_of: asOf, max_depth: "2" });
  return requestFrom<ProjectManagerBrief>(
    AGENTS_API_URL,
    `/api/v1/agents/projects/${encodeURIComponent(projectId)}/brief?${query.toString()}`,
    signal,
  );
}

export function askProjectAgent(
  projectId: string,
  question: string,
  asOf: string,
  signal?: AbortSignal,
): Promise<ProjectQuestionAnswer> {
  return requestFrom<ProjectQuestionAnswer>(
    AGENTS_API_URL,
    `/api/v1/agents/projects/${encodeURIComponent(projectId)}/ask`,
    signal,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, as_of: asOf, max_depth: 2 }),
    },
  );
}
