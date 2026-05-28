import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { streamProjectAgent } from "../api/client";
import type {
  ProjectChatContextMessage,
  ProjectStreamEvent,
} from "../api/types";

export function useProjectQuestion(projectId: string | null, asOf: string) {
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), [projectId, asOf]);
  return useMutation({
    retry: false,
    mutationFn: ({
      question,
      conversationContext,
      verifyClaims,
      onEvent,
    }: {
      question: string;
      conversationContext?: ProjectChatContextMessage[];
      verifyClaims: boolean;
      onEvent: (event: ProjectStreamEvent) => void;
    }) => {
      if (!projectId) {
        throw new Error("Проект не выбран");
      }
      controller.current?.abort();
      controller.current = new AbortController();
      return streamProjectAgent(
        projectId,
        question,
        asOf,
        conversationContext,
        onEvent,
        controller.current.signal,
        verifyClaims,
      );
    },
  });
}
