import { useMutation } from "@tanstack/react-query";

import { askProjectAgent } from "../api/client";

export function useProjectQuestion(projectId: string | null, asOf: string) {
  return useMutation({
    mutationFn: ({ question }: { question: string }) => {
      if (!projectId) {
        throw new Error("Проект не выбран");
      }
      return askProjectAgent(projectId, question, asOf);
    },
  });
}
