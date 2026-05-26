import { useMutation } from "@tanstack/react-query";

import { askProjectAgent } from "../api/client";
import type { ProjectChatContextMessage } from "../api/types";

export function useProjectQuestion(projectId: string | null, asOf: string) {
  return useMutation({
    mutationFn: ({
      question,
      conversationContext,
    }: {
      question: string;
      conversationContext?: ProjectChatContextMessage[];
    }) => {
      if (!projectId) {
        throw new Error("Проект не выбран");
      }
      return askProjectAgent(projectId, question, asOf, conversationContext);
    },
  });
}
