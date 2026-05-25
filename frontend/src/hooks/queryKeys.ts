/**
 * Централизованные ключи кэша TanStack Query. Держим их в одном месте, чтобы
 * избежать рассинхрона строк между хуками и инвалидацией.
 */
export const queryKeys = {
  portfolio: (asOf: string) => ["portfolio", asOf] as const,
  portfolioAttention: (asOf: string, lookbackDays: number) =>
    ["portfolio-attention", asOf, lookbackDays] as const,
  notifications: (
    projectId: string | null,
    unreadOnly: boolean,
    asOfDate: string,
  ) => ["notifications", projectId ?? "all", unreadOnly, asOfDate] as const,
  project: (projectId: string, asOf: string) =>
    ["project", projectId, asOf] as const,
  projectBrief: (projectId: string, asOf: string) =>
    ["project-brief", projectId, asOf] as const,
};
