import { useQuery } from "@tanstack/react-query";

import { fetchPortfolioAttention } from "../api/client";
import { queryKeys } from "./queryKeys";

export function usePortfolioAttention(asOf: string, lookbackDays = 7) {
  return useQuery({
    queryKey: queryKeys.portfolioAttention(asOf, lookbackDays),
    queryFn: ({ signal }) =>
      fetchPortfolioAttention(asOf, lookbackDays, signal),
  });
}
