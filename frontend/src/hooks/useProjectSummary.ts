import { useQuery } from "@tanstack/react-query";

import { fetchProjectSummary } from "../api/client";
import { queryKeys } from "./queryKeys";

/**
 * Загрузка детальной сводки одного проекта.
 *
 * `enabled` защищает от запроса с пустым id. Данные не подменяются прошлым
 * срезом, чтобы при смене даты пользователь не видел устаревшие метрики.
 */
export function useProjectSummary(
  projectId: string | null,
  asOf: string,
  enabled = Boolean(projectId),
) {
  return useQuery({
    queryKey: queryKeys.project(projectId ?? "", asOf),
    queryFn: ({ signal }) =>
      fetchProjectSummary(projectId as string, asOf, signal),
    enabled: enabled && Boolean(projectId),
  });
}
