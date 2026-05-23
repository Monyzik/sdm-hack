/**
 * Тонкий HTTP-клиент над эндпоинтами summary.
 *
 * Здесь сосредоточена вся работа с сетью: построение URL, разбор ответа и
 * единообразная обработка ошибок. Компоненты и хуки не знают про `fetch`.
 * Контракты эндпоинтов не меняются.
 */
import { API_URL } from "../lib/constants";
import type { PortfolioSummary, ProjectSummary } from "./types";

/** Ошибка запроса с сохранённым HTTP-статусом — удобно различать 404 и прочее. */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { signal });
  } catch {
    throw new ApiError(
      "Не удалось связаться с сервером. Проверьте, что backend запущен.",
      0,
    );
  }

  if (!response.ok) {
    throw new ApiError(
      `Запрос завершился с ошибкой ${response.status}`,
      response.status,
    );
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
