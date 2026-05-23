import { useQuery } from "@tanstack/react-query";

import { fetchPortfolioSummary } from "../api/client";
import { queryKeys } from "./queryKeys";

/**
 * Загрузка сводки портфеля на указанную дату среза.
 *
 * TanStack Query берёт на себя кэширование, дедупликацию запросов, отмену по
 * `signal` и состояния loading/error, поэтому компонентам остаётся только
 * отрисовать результат.
 */
export function usePortfolio(asOf: string) {
  return useQuery({
    queryKey: queryKeys.portfolio(asOf),
    queryFn: ({ signal }) => fetchPortfolioSummary(asOf, signal),
  });
}
