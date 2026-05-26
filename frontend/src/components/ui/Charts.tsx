import type { Tone } from "../../lib/risk";

const toneStroke: Record<Tone, string> = {
  neutral: "stroke-slate-700 dark:stroke-slate-300",
  danger: "stroke-rose-500 dark:stroke-rose-400",
  warning: "stroke-amber-500 dark:stroke-amber-400",
  success: "stroke-emerald-500 dark:stroke-emerald-400",
  info: "stroke-sky-500 dark:stroke-sky-400",
};

const toneFill: Record<Tone, string> = {
  neutral: "bg-slate-700 dark:bg-slate-300",
  danger: "bg-rose-500 dark:bg-rose-400",
  warning: "bg-amber-500 dark:bg-amber-400",
  success: "bg-emerald-500 dark:bg-emerald-400",
  info: "bg-sky-500 dark:bg-sky-400",
};

interface CircularGaugeProps {
  value: number;
  label: string;
  tone?: Tone;
}

export function CircularGauge({
  value,
  label,
  tone = "neutral",
}: CircularGaugeProps) {
  const percent = Math.max(0, Math.min(100, value));
  const radius = 34;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percent / 100) * circumference;

  return (
    <div className="grid place-items-center">
      <div className="relative size-24">
        <svg aria-hidden viewBox="0 0 88 88" className="-rotate-90">
          <circle
            cx="44"
            cy="44"
            r={radius}
            className="fill-none stroke-slate-100 dark:stroke-slate-800"
            strokeWidth="9"
          />
          <circle
            cx="44"
            cy="44"
            r={radius}
            className={`fill-none ${toneStroke[tone]}`}
            strokeLinecap="round"
            strokeWidth="9"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
          />
        </svg>
        <div className="absolute inset-0 grid place-items-center">
          <span className="text-2xl font-semibold tabular-nums text-slate-950 dark:text-slate-50">
            {Math.round(value)}
          </span>
        </div>
      </div>
      <p className="mt-1 text-xs font-medium text-slate-500 dark:text-slate-400">
        {label}
      </p>
    </div>
  );
}

interface MiniBarProps {
  label: string;
  value: number;
  tone?: Tone;
}

export function MiniBar({ label, value, tone = "neutral" }: MiniBarProps) {
  const percent = Math.max(0, Math.min(100, value));

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-3 text-xs">
        <span className="font-medium text-slate-600 dark:text-slate-300">
          {label}
        </span>
        <span className="tabular-nums text-slate-500 dark:text-slate-400">
          {Math.round(value)}%
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        <div
          className={`h-full rounded-full ${toneFill[tone]}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

interface LineSeries {
  label: string;
  values: number[];
  tone?: Tone;
  suffix?: string;
}

interface TrendLineChartProps {
  labels: string[];
  series: LineSeries[];
  height?: number;
}

export function TrendLineChart({
  labels,
  series,
  height = 180,
}: TrendLineChartProps) {
  const width = 640;
  const paddingX = 28;
  const paddingY = 18;
  const allValues = series.flatMap((item) => item.values);
  const maxValue = Math.max(1, ...allValues);
  const minValue = Math.min(0, ...allValues);
  const span = Math.max(1, maxValue - minValue);
  const plotWidth = width - paddingX * 2;
  const plotHeight = height - paddingY * 2;

  function point(value: number, index: number) {
    const x =
      paddingX +
      (labels.length <= 1 ? 0 : (plotWidth * index) / (labels.length - 1));
    const y = paddingY + plotHeight - ((value - minValue) / span) * plotHeight;
    return { x, y };
  }

  return (
    <div className="w-full overflow-hidden">
      <svg
        aria-hidden
        viewBox={`0 0 ${width} ${height}`}
        className="h-44 w-full"
        preserveAspectRatio="none"
      >
        {[0, 0.5, 1].map((ratio) => {
          const y = paddingY + plotHeight * ratio;
          return (
            <line
              key={ratio}
              x1={paddingX}
              x2={width - paddingX}
              y1={y}
              y2={y}
              className="stroke-slate-100 dark:stroke-slate-800"
              strokeWidth="1"
            />
          );
        })}
        {series.map((item) => {
          const d = item.values
            .map((value, index) => {
              const { x, y } = point(value, index);
              return `${index === 0 ? "M" : "L"} ${x} ${y}`;
            })
            .join(" ");
          return (
            <path
              key={item.label}
              d={d}
              fill="none"
              className={toneStroke[item.tone ?? "neutral"]}
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          );
        })}
        {series.map((item) =>
          item.values.map((value, index) => {
            const { x, y } = point(value, index);
            return (
              <circle
                key={`${item.label}-${index}`}
                cx={x}
                cy={y}
                r="3.5"
                className={`${toneStroke[item.tone ?? "neutral"]} fill-white dark:fill-slate-950`}
                strokeWidth="2"
              />
            );
          }),
        )}
      </svg>
      <div className="mt-2 flex items-center justify-between gap-2 text-xs text-slate-500 dark:text-slate-400">
        {labels.map((label) => (
          <span key={label} className="truncate">
            {label}
          </span>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-3">
        {series.map((item) => {
          const latest = item.values[item.values.length - 1] ?? 0;
          return (
            <div
              key={item.label}
              className="inline-flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300"
            >
              <span className={`size-2 rounded-full ${toneFill[item.tone ?? "neutral"]}`} />
              <span>{item.label}</span>
              <span className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">
                {Math.round(latest)}
                {item.suffix ?? ""}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

interface HorizontalBarDatum {
  label: string;
  value: number;
  hint?: string;
  tone?: Tone;
}

export function HorizontalBarChart({ data }: { data: HorizontalBarDatum[] }) {
  return (
    <div className="space-y-3">
      {data.map((item) => {
        const percent = Math.max(0, Math.min(140, item.value));
        return (
          <div key={item.label} className="space-y-1.5">
            <div className="flex items-center justify-between gap-3 text-xs">
              <span className="min-w-0 truncate font-medium text-slate-700 dark:text-slate-200">
                {item.label}
              </span>
              <span className="shrink-0 tabular-nums text-slate-500 dark:text-slate-400">
                {Math.round(item.value)}%
              </span>
            </div>
            <div className="h-2.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
              <div
                className={`h-full rounded-full ${toneFill[item.tone ?? "neutral"]}`}
                style={{ width: `${Math.min(100, percent)}%` }}
              />
            </div>
            {item.hint ? (
              <div className="truncate text-xs text-slate-500 dark:text-slate-400">
                {item.hint}
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
