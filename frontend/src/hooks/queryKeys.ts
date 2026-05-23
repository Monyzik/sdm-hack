/**
 * Централизованные ключи кэша TanStack Query. Держим их в одном месте, чтобы
 * избежать рассинхрона строк между хуками и инвалидацией.
 */
export const queryKeys = {
  portfolio: (asOf: string) => ["portfolio", asOf] as const,
  project: (projectId: string, asOf: string) =>
    ["project", projectId, asOf] as const,
};
