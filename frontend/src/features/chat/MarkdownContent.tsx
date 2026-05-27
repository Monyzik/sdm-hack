import type { ReactNode } from "react";

type MarkdownBlock =
  | { type: "paragraph"; text: string }
  | { type: "heading"; level: 1 | 2 | 3; text: string }
  | { type: "list"; ordered: boolean; items: string[] }
  | { type: "table"; headers: string[]; rows: string[][] }
  | { type: "code"; language?: string; code: string }
  | { type: "quote"; text: string };

interface MarkdownContentProps {
  content: string;
}

export function MarkdownContent({ content }: MarkdownContentProps) {
  const blocks = parseBlocks(content);

  return (
    <div className="space-y-3 text-base leading-7 text-slate-800 dark:text-slate-200">
      {blocks.map((block, index) => renderBlock(block, index))}
    </div>
  );
}

function parseBlocks(content: string): MarkdownBlock[] {
  const lines = normalizeCompactMarkdown(content)
    .replace(/\r\n/g, "\n")
    .split("\n");
  const blocks: MarkdownBlock[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index] ?? "";
    const trimmed = line.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    const codeFence = trimmed.match(/^```([\w-]+)?$/);
    if (codeFence) {
      const codeLines: string[] = [];
      index += 1;
      while (
        index < lines.length &&
        !(lines[index] ?? "").trim().startsWith("```")
      ) {
        codeLines.push(lines[index] ?? "");
        index += 1;
      }
      if (index < lines.length) index += 1;
      blocks.push({
        type: "code",
        language: codeFence[1],
        code: codeLines.join("\n"),
      });
      continue;
    }

    const heading = trimmed.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      blocks.push({
        type: "heading",
        level: heading[1].length as 1 | 2 | 3,
        text: heading[2],
      });
      index += 1;
      continue;
    }

    if (isTableStart(lines, index)) {
      const headers = splitTableRow(lines[index] ?? "");
      const rows: string[][] = [];
      index += 2;

      while (index < lines.length && isTableRow(lines[index] ?? "")) {
        const cells = splitTableRow(lines[index] ?? "");
        rows.push(normalizeTableRow(cells, headers.length));
        index += 1;
      }

      blocks.push({ type: "table", headers, rows });
      continue;
    }

    if (/^\s*[-*•]\s+/.test(line) || /^\s*\d+[.)]\s+/.test(line)) {
      const ordered = /^\s*\d+[.)]\s+/.test(line);
      const items: string[] = [];
      while (index < lines.length) {
        const current = lines[index] ?? "";
        const unorderedMatch = current.match(/^\s*[-*•]\s+(.+)$/);
        const orderedMatch = current.match(/^\s*\d+[.)]\s+(.+)$/);
        if (ordered && orderedMatch) {
          items.push(orderedMatch[1]);
          index += 1;
          continue;
        }
        if (!ordered && unorderedMatch) {
          items.push(unorderedMatch[1]);
          index += 1;
          continue;
        }
        break;
      }
      blocks.push({ type: "list", ordered, items });
      continue;
    }

    if (trimmed.startsWith(">")) {
      const quoteLines: string[] = [];
      while (
        index < lines.length &&
        (lines[index] ?? "").trim().startsWith(">")
      ) {
        quoteLines.push((lines[index] ?? "").trim().replace(/^>\s?/, ""));
        index += 1;
      }
      blocks.push({ type: "quote", text: quoteLines.join(" ") });
      continue;
    }

    const paragraphLines: string[] = [];
    while (index < lines.length && !isBlockBoundary(lines, index)) {
      paragraphLines.push((lines[index] ?? "").trim());
      index += 1;
    }
    blocks.push({ type: "paragraph", text: paragraphLines.join(" ") });
  }

  return blocks;
}

function isBlockBoundary(lines: string[], index: number) {
  const line = lines[index] ?? "";
  const trimmed = line.trim();
  return (
    !trimmed ||
    trimmed.startsWith("```") ||
    /^(#{1,3})\s+/.test(trimmed) ||
    /^\s*[-*•]\s+/.test(line) ||
    /^\s*\d+[.)]\s+/.test(line) ||
    isTableStart(lines, index) ||
    trimmed.startsWith(">")
  );
}

function renderBlock(block: MarkdownBlock, index: number) {
  if (block.type === "heading") {
    const className =
      block.level === 1
        ? "text-base font-semibold text-slate-950 dark:text-slate-50"
        : "text-sm font-semibold text-slate-950 dark:text-slate-50";

    if (block.level === 1) {
      return (
        <h3 key={index} className={className}>
          {renderInline(block.text, `h-${index}`)}
        </h3>
      );
    }
    return (
      <h4 key={index} className={className}>
        {renderInline(block.text, `h-${index}`)}
      </h4>
    );
  }

  if (block.type === "list") {
    const ListTag = block.ordered ? "ol" : "ul";
    return (
      <ListTag
        key={index}
        className={
          block.ordered
            ? "ml-5 list-decimal space-y-1.5 marker:text-slate-400"
            : "ml-5 list-disc space-y-1.5 marker:text-slate-400"
        }
      >
        {block.items.map((item, itemIndex) => (
          <li key={`${index}-${itemIndex}`} className="pl-1">
            {renderInline(item, `${index}-${itemIndex}`)}
          </li>
        ))}
      </ListTag>
    );
  }

  if (block.type === "table") {
    const numericColumns = block.headers.map(
      (_, columnIndex) =>
        block.rows.length > 0 &&
        block.rows.every((row) => isNumericCell(row[columnIndex] ?? "")),
    );

    return (
      <div
        key={index}
        className="overflow-x-auto rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950"
      >
        <table className="min-w-full border-collapse text-left text-[13px] leading-5">
          <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500 dark:bg-slate-900 dark:text-slate-400">
            <tr>
              {block.headers.map((header, headerIndex) => (
                <th
                  key={`${index}-h-${headerIndex}`}
                  scope="col"
                  className={[
                    "whitespace-nowrap border-b border-slate-200 px-3 py-2 dark:border-slate-800",
                    numericColumns[headerIndex] ? "text-right" : "text-left",
                  ].join(" ")}
                >
                  {renderInline(header, `${index}-h-${headerIndex}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {block.rows.map((row, rowIndex) => (
              <tr
                key={`${index}-r-${rowIndex}`}
                className="border-b border-slate-100 last:border-b-0 dark:border-slate-800/80"
              >
                {block.headers.map((_, cellIndex) => (
                  <td
                    key={`${index}-r-${rowIndex}-c-${cellIndex}`}
                    className={[
                      "max-w-72 px-3 py-2 align-top text-slate-800 dark:text-slate-200",
                      numericColumns[cellIndex]
                        ? "whitespace-nowrap text-right tabular-nums"
                        : "",
                    ].join(" ")}
                  >
                    {renderInline(
                      row[cellIndex] ?? "",
                      `${index}-${rowIndex}-${cellIndex}`,
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (block.type === "code") {
    return (
      <div
        key={index}
        className="overflow-hidden rounded-lg border border-slate-200 dark:border-slate-800"
      >
        {block.language ? (
          <div className="border-b border-slate-200 bg-slate-50 px-3 py-1 text-[11px] font-medium uppercase text-slate-500 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400">
            {block.language}
          </div>
        ) : null}
        <pre className="overflow-x-auto bg-slate-950 p-3 text-xs leading-6 text-slate-100">
          <code>{block.code}</code>
        </pre>
      </div>
    );
  }

  if (block.type === "quote") {
    return (
      <blockquote
        key={index}
        className="border-l-2 border-slate-300 pl-3 text-slate-600 dark:border-slate-700 dark:text-slate-300"
      >
        {renderInline(block.text, `q-${index}`)}
      </blockquote>
    );
  }

  return <p key={index}>{renderInline(block.text, `p-${index}`)}</p>;
}

function normalizeCompactMarkdown(content: string) {
  return normalizeCompactLists(normalizeCompactTables(content));
}

function normalizeCompactLists(content: string) {
  return content
    .replace(/\r\n/g, "\n")
    .split("\n")
    .flatMap((line) => expandCompactListLine(line))
    .join("\n");
}

function expandCompactListLine(line: string): string[] {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith("|") || trimmed.startsWith("```")) {
    return [line];
  }

  const ordered = splitCompactListLine(line, /(^|\s)(\d{1,2}[.)])\s+/g);
  if (ordered) return ordered;

  const unordered = splitCompactListLine(line, /(^|\s)([-*•])\s+/g);
  return unordered ?? [line];
}

function splitCompactListLine(line: string, markerPattern: RegExp) {
  const matches = [...line.matchAll(markerPattern)].map((match) => ({
    markerStart: match.index + (match[1]?.length ?? 0),
  }));
  if (!matches.length) return null;

  const firstMarkerStart = matches[0].markerStart;
  const prefix = line.slice(0, firstMarkerStart).trim();
  const hasInlinePrefix = firstMarkerStart > 0;
  const shouldSplit =
    matches.length > 1 || (hasInlinePrefix && /[:：]\s*$/.test(prefix));

  if (!shouldSplit) return null;

  const items = matches
    .map((match, index) => {
      const nextMatch = matches[index + 1];
      return line
        .slice(match.markerStart, nextMatch?.markerStart ?? line.length)
        .trim();
    })
    .filter(Boolean);

  return [prefix, ...items].filter(Boolean);
}

function normalizeCompactTables(content: string) {
  return content
    .replace(/\r\n/g, "\n")
    .split("\n")
    .flatMap((line) => expandCompactTableLine(line))
    .join("\n");
}

function expandCompactTableLine(line: string): string[] {
  if (!/\|\s*:?-{3,}:?\s*\|/.test(line)) {
    return [line];
  }

  const parts = line.split("|");
  const separatorStart = parts.findIndex((part) => isTableSeparatorCell(part));
  if (separatorStart < 0) {
    return [line];
  }

  let separatorEnd = separatorStart;
  while (
    separatorEnd < parts.length &&
    isTableSeparatorCell(parts[separatorEnd] ?? "")
  ) {
    separatorEnd += 1;
  }

  const columnCount = separatorEnd - separatorStart;
  if (columnCount < 2) {
    return [line];
  }

  let headerEnd = separatorStart - 1;
  while (headerEnd >= 0 && (parts[headerEnd] ?? "").trim() === "") {
    headerEnd -= 1;
  }

  const headerStart = headerEnd - columnCount + 1;
  if (headerStart < 0) {
    return [line];
  }

  const prefixFromParts = parts.slice(0, headerStart).join("|").trim();
  let headers = parts
    .slice(headerStart, headerEnd + 1)
    .map((cell) => cell.trim());
  const { prefix: prefixFromHeader, firstHeader } = splitPrefixFromFirstHeader(
    headers[0] ?? "",
  );
  if (prefixFromHeader) {
    headers = [firstHeader, ...headers.slice(1)];
  }
  if (headers.some((header) => !header)) {
    return [line];
  }

  const rows: string[][] = [];
  let cursor = separatorEnd;
  while (cursor < parts.length && (parts[cursor] ?? "").trim() === "") {
    cursor += 1;
  }

  while (cursor + columnCount <= parts.length) {
    const row = parts
      .slice(cursor, cursor + columnCount)
      .map((cell) => cell.trim());
    if (row.every((cell) => !cell)) {
      break;
    }
    rows.push(row);
    cursor += columnCount;
    while (cursor < parts.length && (parts[cursor] ?? "").trim() === "") {
      cursor += 1;
    }
  }

  if (rows.length === 0) {
    return [line];
  }

  const prefix = [prefixFromParts, prefixFromHeader]
    .filter(Boolean)
    .join(" ")
    .trim();
  const suffix = parts.slice(cursor).join("|").trim();
  const expanded = [
    prefix,
    formatTableRow(headers),
    formatTableRow(headers.map(() => "---")),
    ...rows.map((row) => formatTableRow(row)),
    ...expandCompactTableLine(suffix),
  ];

  return expanded.filter((part) => part.trim().length > 0);
}

function isTableSeparatorCell(value: string) {
  return /^:?-{3,}:?$/.test(value.replace(/\s+/g, ""));
}

function formatTableRow(cells: string[]) {
  return `| ${cells.join(" | ")} |`;
}

function splitPrefixFromFirstHeader(value: string) {
  const separatorIndex = value.lastIndexOf(":");
  if (separatorIndex < 0) {
    return { prefix: "", firstHeader: value };
  }

  const prefix = value.slice(0, separatorIndex + 1).trim();
  const firstHeader = value.slice(separatorIndex + 1).trim();
  if (!prefix || !isLikelyTableHeader(firstHeader)) {
    return { prefix: "", firstHeader: value };
  }

  return { prefix, firstHeader };
}

function isLikelyTableHeader(value: string) {
  const normalized = value.trim().toLocaleLowerCase("ru-RU");
  return [
    "блокер",
    "бюджет",
    "владелец",
    "дата",
    "задача",
    "приоритет",
    "просрочка",
    "риск",
    "срок",
    "статус",
    "сумма",
  ].includes(normalized);
}

function isTableStart(lines: string[], index: number) {
  return (
    isTableRow(lines[index] ?? "") && isTableSeparator(lines[index + 1] ?? "")
  );
}

function isTableRow(line: string) {
  const trimmed = line.trim();
  return trimmed.includes("|") && splitTableRow(trimmed).length >= 2;
}

function isTableSeparator(line: string) {
  const cells = splitTableRow(line);
  return cells.length >= 2 && cells.every((cell) => isTableSeparatorCell(cell));
}

function splitTableRow(line: string) {
  const trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  return trimmed.split("|").map((cell) => cell.trim());
}

function normalizeTableRow(cells: string[], size: number) {
  const normalized = cells.slice(0, size);
  while (normalized.length < size) {
    normalized.push("");
  }
  return normalized;
}

function isNumericCell(value: string) {
  const compact = value.replace(/\s+/g, "");
  return /^[-+]?[\d.,]+(%|₽|млн₽|тыс\.?₽|дн\.?|день|дня|дней)?$/i.test(compact);
}

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const pattern =
    /(\[[^\]]+\]\(([^)\s]+)\)|`([^`]+)`|\*\*([^*]+)\*\*|\*([^*]+)\*)/g;
  const nodes: ReactNode[] = [];
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) {
      nodes.push(text.slice(cursor, match.index));
    }

    const [raw, , href, code, bold, italic] = match;
    const key = `${keyPrefix}-${match.index}`;

    if (href) {
      const label = raw.slice(1, raw.indexOf("]"));
      nodes.push(
        <a
          key={key}
          href={href}
          target="_blank"
          rel="noreferrer"
          className="font-medium text-sky-700 underline decoration-sky-300 underline-offset-4 hover:text-sky-900 dark:text-sky-300 dark:decoration-sky-700 dark:hover:text-sky-200"
        >
          {label}
        </a>,
      );
    } else if (code) {
      nodes.push(
        <code
          key={key}
          className="rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-[0.86em] text-slate-900 dark:bg-slate-800 dark:text-slate-100"
        >
          {code}
        </code>,
      );
    } else if (bold) {
      nodes.push(
        <strong
          key={key}
          className="font-semibold text-slate-950 dark:text-slate-50"
        >
          {bold}
        </strong>,
      );
    } else if (italic) {
      nodes.push(
        <em key={key} className="text-slate-700 dark:text-slate-300">
          {italic}
        </em>,
      );
    } else {
      nodes.push(raw);
    }

    cursor = match.index + raw.length;
  }

  if (cursor < text.length) {
    nodes.push(text.slice(cursor));
  }

  return nodes;
}
