/** Accepts tool artifacts as well as the typed retrieval endpoint response. */
export function RetrievalProvenance({ value }: { value: unknown }) {
  if (!value || typeof value !== "object") return null;
  const data = value as Record<string, unknown>;
  const number = (key: string, decimals = 4) => {
    const item = data[key];
    return typeof item === "number" && Number.isFinite(item)
      ? decimals === 0
        ? String(item)
        : item.toFixed(decimals)
      : "—";
  };
  return (
    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs tabular-nums text-slate-500 dark:text-slate-400">
      <span>
        BM25: место {number("bm25_rank", 0)} · score {number("bm25_score")}
      </span>
      <span>
        Dense: место {number("dense_rank", 0)} · cosine {number("dense_score")}
      </span>
      <span>RRF: {number("fusion_score", 6)}</span>
      {typeof data.rerank_rank === "number" &&
      Number.isFinite(data.rerank_rank) ? (
        <span>После оценки LLM: место {number("rerank_rank", 0)}</span>
      ) : null}
    </div>
  );
}
