import { useQuery } from "@tanstack/react-query";

import { fetchNotifications } from "../api/client";
import { queryKeys } from "./queryKeys";

export function useNotifications(
  projectId: string | null = null,
  unreadOnly = false,
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.notifications(projectId, unreadOnly),
    queryFn: ({ signal }) =>
      fetchNotifications(
        {
          projectId: projectId ?? undefined,
          unreadOnly,
        },
        signal,
      ),
    enabled,
  });
}
