import { type KeyboardEvent, useState } from "react";

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
  height = 208,
}: TrendLineChartProps) {
  const width = 640;
  const paddingX = 36;
  const paddingY = 24;
  const allValues = series.flatMap((item) => item.values);
  const maxValue = Math.max(1, ...allValues);
  const minValue = Math.min(0, ...allValues);
  const span = Math.max(1, maxValue - minValue);
  const plotWidth = width - paddingX * 2;
  const plotHeight = height - paddingY * 2;
  const [activeIndex, setActiveIndex] = useState(labels.length - 1);
  const selectedIndex = Math.min(
    Math.max(activeIndex, 0),
    Math.max(labels.length - 1, 0),
  );
  const selectedLabel =
    labels[selectedIndex] ?? labels[labels.length - 1] ?? "";

  function point(value: number, index: number) {
    const x =
      paddingX +
      (labels.length <= 1 ? 0 : (plotWidth * index) / (labels.length - 1));
    const y = paddingY + plotHeight - ((value - minValue) / span) * plotHeight;
    return { x, y };
  }

  function pointPath(values: number[]) {
    return values
      .map((value, index) => {
        const { x, y } = point(value, index);
        return `${index === 0 ? "M" : "L"} ${x} ${y}`;
      })
      .join(" ");
  }

  function formatValue(value: number, suffix = "") {
    const rounded =
      Math.abs(value) >= 10 ? Math.round(value) : Math.round(value * 10) / 10;
    return `${rounded}${suffix}`;
  }

  function handlePointKeyDown(
    event: KeyboardEvent<SVGRectElement>,
    index: number,
  ) {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    setActiveIndex(index);
  }

  const selectedPoint = point(
    series[0]?.values[selectedIndex] ?? 0,
    selectedIndex,
  );
  const labelStep = Math.max(1, Math.ceil(labels.length / 4));

  if (!labels.length || !series.length) {
    return null;
  }

  return (
    <div className="w-full overflow-hidden rounded-lg border border-slate-100 bg-gradient-to-b from-slate-50 to-white p-3 dark:border-slate-800 dark:from-slate-950 dark:to-slate-900/60">
      <svg
        aria-label="График тренда"
        viewBox={`0 0 ${width} ${height}`}
        className="h-52 w-full"
        preserveAspectRatio="none"
      >
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const y = paddingY + plotHeight * ratio;
          return (
            <line
              key={ratio}
              x1={paddingX}
              x2={width - paddingX}
              y1={y}
              y2={y}
              className="stroke-slate-200/80 dark:stroke-slate-800"
              strokeWidth="1"
            />
          );
        })}
        {labels.map((label, index) => {
          if (
            index !== 0 &&
            index !== labels.length - 1 &&
            index % labelStep !== 0
          ) {
            return null;
          }
          const { x } = point(0, index);
          return (
            <line
              key={label}
              x1={x}
              x2={x}
              y1={paddingY}
              y2={height - paddingY}
              className="stroke-slate-200/50 dark:stroke-slate-800/70"
              strokeWidth="1"
            />
          );
        })}
        <line
          x1={selectedPoint.x}
          x2={selectedPoint.x}
          y1={paddingY}
          y2={height - paddingY}
          className="stroke-slate-400/70 dark:stroke-slate-500/70"
          strokeDasharray="4 4"
          strokeWidth="1.5"
        />
        {series.map((item) => (
          <path
            key={item.label}
            d={pointPath(item.values)}
            fill="none"
            className={`${toneStroke[item.tone ?? "neutral"]} opacity-25`}
            strokeWidth="8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}
        {series.map((item) => (
          <path
            key={item.label}
            d={pointPath(item.values)}
            fill="none"
            className={toneStroke[item.tone ?? "neutral"]}
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}
        {series.map((item) => {
          const { x, y } = point(
            item.values[selectedIndex] ?? 0,
            selectedIndex,
          );
          return (
            <circle
              key={`${item.label}-${selectedIndex}`}
              cx={x}
              cy={y}
              r="5.5"
              className={`${toneStroke[item.tone ?? "neutral"]} fill-white dark:fill-slate-950`}
              strokeWidth="2"
            />
          );
        })}
        {labels.map((label, index) => {
          const { x } = point(0, index);
          const previousX = index === 0 ? paddingX : point(0, index - 1).x;
          const nextX =
            index === labels.length - 1
              ? width - paddingX
              : point(0, index + 1).x;
          const hitX = index === 0 ? paddingX : (previousX + x) / 2;
          const hitWidth =
            index === labels.length - 1
              ? width - paddingX - hitX
              : (nextX + x) / 2 - hitX;

          return (
            <rect
              key={`hit-${label}-${index}`}
              role="button"
              aria-label={`Показать срез ${label}`}
              tabIndex={0}
              x={hitX}
              y={paddingY}
              width={Math.max(8, hitWidth)}
              height={plotHeight}
              fill="transparent"
              className="cursor-pointer outline-none"
              onClick={() => setActiveIndex(index)}
              onFocus={() => setActiveIndex(index)}
              onKeyDown={(event) => handlePointKeyDown(event, index)}
              onMouseEnter={() => setActiveIndex(index)}
            />
          );
        })}
      </svg>
      <div className="mt-2 flex items-center justify-between gap-3 text-xs text-slate-500 dark:text-slate-400">
        <span>{labels[0]}</span>
        <span className="font-semibold tabular-nums text-slate-700 dark:text-slate-200">
          {selectedLabel}
        </span>
        <span>{labels[labels.length - 1]}</span>
      </div>
      <div className="mt-3 grid gap-2 rounded-lg border border-slate-100 bg-white/80 px-3 py-2 dark:border-slate-800 dark:bg-slate-950/50 sm:grid-cols-2">
        {series.map((item) => {
          const selectedValue = item.values[selectedIndex] ?? 0;
          return (
            <div
              key={item.label}
              className="flex min-w-0 items-center justify-between gap-3 text-xs text-slate-600 dark:text-slate-300"
            >
              <span className="inline-flex min-w-0 items-center gap-2">
                <span
                  className={`size-2 rounded-full ${toneFill[item.tone ?? "neutral"]}`}
                />
                <span className="truncate">{item.label}</span>
              </span>
              <span className="shrink-0 font-semibold tabular-nums text-slate-900 dark:text-slate-100">
                {formatValue(selectedValue, item.suffix)}
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
