import { useQuery } from "@tanstack/react-query";

import { fetchNotifications } from "../api/client";
import { queryKeys } from "./queryKeys";

export function useNotifications(
  asOfDate: string | null,
  projectId: string | null = null,
  unreadOnly = false,
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.notifications(projectId, unreadOnly, asOfDate),
    queryFn: ({ signal }) =>
      fetchNotifications(
        {
          projectId: projectId ?? undefined,
          asOfDate: asOfDate ?? undefined,
          unreadOnly,
        },
        signal,
      ),
    enabled,
  });
}
