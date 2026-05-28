/**
 * Централизованные ключи кэша TanStack Query. Держим их в одном месте, чтобы
 * избежать рассинхрона строк между хуками и инвалидацией.
 */
export const queryKeys = {
  portfolio: (asOf: string) => ["portfolio", asOf] as const,
  portfolioAttention: (asOf: string, lookbackDays: number) =>
    ["portfolio-attention", asOf, lookbackDays] as const,
  project: (projectId: string, asOf: string) =>
    ["project", projectId, asOf] as const,
  projectProblemContext: (projectId: string, asOf: string, maxDepth: number) =>
    ["project-problem-context", projectId, asOf, maxDepth] as const,
  projectTrends: (projectId: string, asOf: string, points: number) =>
    ["project-trends", projectId, asOf, points] as const,
};
