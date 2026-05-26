import { useQuery } from "@tanstack/react-query";

import { fetchProjectTrends } from "../api/client";
import { queryKeys } from "./queryKeys";

export function useProjectTrends(
  projectId: string | null,
  asOf: string,
  points = 8,
  enabled = Boolean(projectId),
) {
  return useQuery({
    queryKey: queryKeys.projectTrends(projectId ?? "", asOf, points),
    queryFn: ({ signal }) =>
      fetchProjectTrends(projectId as string, asOf, points, signal),
    enabled: enabled && Boolean(projectId),
  });
}
