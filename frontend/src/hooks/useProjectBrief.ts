import { useQuery } from "@tanstack/react-query";

import { fetchProjectBrief } from "../api/client";
import { queryKeys } from "./queryKeys";

export function useProjectBrief(projectId: string | null, asOf: string) {
  return useQuery({
    queryKey: projectId
      ? queryKeys.projectBrief(projectId, asOf)
      : ["project-brief", "none", asOf],
    queryFn: ({ signal }) => fetchProjectBrief(projectId ?? "", asOf, signal),
    enabled: Boolean(projectId),
    retry: 1,
  });
}
