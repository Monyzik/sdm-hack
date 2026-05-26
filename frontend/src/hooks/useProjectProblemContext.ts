import { useQuery } from "@tanstack/react-query";

import { fetchProjectProblemContext } from "../api/client";
import { queryKeys } from "./queryKeys";

export function useProjectProblemContext(
  projectId: string | null,
  asOf: string,
  maxDepth = 2,
  enabled = Boolean(projectId),
) {
  return useQuery({
    queryKey: queryKeys.projectProblemContext(projectId ?? "", asOf, maxDepth),
    queryFn: ({ signal }) =>
      fetchProjectProblemContext(projectId as string, asOf, maxDepth, signal),
    enabled: enabled && Boolean(projectId),
  });
}
