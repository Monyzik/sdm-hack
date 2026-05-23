import { useQuery } from "@tanstack/react-query";

import { fetchProjectSummary } from "../api/client";
import { queryKeys } from "./queryKeys";

/**
 * Загрузка детальной сводки одного проекта.
 *
 * `enabled` защищает от запроса с пустым id. Прошлые данные сохраняются между
 * переключениями проектов (`placeholderData`), чтобы интерфейс не «мигал»
 * пустотой при каждом клике в списке портфеля.
 */
export function useProjectSummary(projectId: string | null, asOf: string) {
  return useQuery({
    queryKey: queryKeys.project(projectId ?? "", asOf),
    queryFn: ({ signal }) =>
      fetchProjectSummary(projectId as string, asOf, signal),
    enabled: Boolean(projectId),
    placeholderData: (previous) => previous,
  });
}
