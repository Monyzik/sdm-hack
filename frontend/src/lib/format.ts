/**
 * Чистые функции форматирования. Никакой бизнес-логики и побочных эффектов —
 * только преобразование значений в строки для отображения.
 */

/** Маппинг ISO-кодов валют на символы. По умолчанию показываем сам код. */
const CURRENCY_SYMBOLS: Record<string, string> = {
  RUB: "₽",
  USD: "$",
  EUR: "€",
};

/**
 * Денежная сумма в компактном виде: крупные значения сворачиваются в
 * «млн»/«млрд», чтобы таблицы бюджета оставались читаемыми.
 */
export function formatMoney(value: number, currency = "RUB"): string {
  const symbol = CURRENCY_SYMBOLS[currency] ?? currency;
  const abs = Math.abs(value);

  let formatted: string;
  if (abs >= 1_000_000_000) {
    formatted = `${trimNumber(value / 1_000_000_000)} млрд`;
  } else if (abs >= 1_000_000) {
    formatted = `${trimNumber(value / 1_000_000)} млн`;
  } else {
    formatted = new Intl.NumberFormat("ru-RU", {
      maximumFractionDigits: 0,
    }).format(value);
  }

  return `${formatted} ${symbol}`;
}

/** Процент со знаком и одним знаком после запятой при необходимости. */
export function formatPercent(value: number, withSign = false): string {
  const formatted = trimNumber(value);
  if (withSign && value > 0) {
    return `+${formatted}%`;
  }
  return `${formatted}%`;
}

/** Дата в локальном коротком формате (например, «27 мая 2026»). */
export function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
}

/** Склонение слова «день» по числу. */
export function formatDays(days: number): string {
  const abs = Math.abs(days) % 100;
  const last = abs % 10;
  let word = "дней";
  if (abs < 11 || abs > 14) {
    if (last === 1) word = "день";
    else if (last >= 2 && last <= 4) word = "дня";
  }
  return `${days} ${word}`;
}

/** Убирает незначащие нули у дробной части (29.0 -> 29, 29.2 -> 29.2). */
function trimNumber(value: number): string {
  return Number(value.toFixed(1)).toString();
}
