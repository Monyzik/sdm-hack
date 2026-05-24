import type { ReactNode } from "react";

type MarkdownBlock =
  | { type: "paragraph"; text: string }
  | { type: "heading"; level: 1 | 2 | 3; text: string }
  | { type: "list"; ordered: boolean; items: string[] }
  | { type: "code"; language?: string; code: string }
  | { type: "quote"; text: string };

interface MarkdownContentProps {
  content: string;
}

export function MarkdownContent({ content }: MarkdownContentProps) {
  const blocks = parseBlocks(content);

  return (
    <div className="space-y-3 text-sm leading-7 text-slate-800 dark:text-slate-200">
      {blocks.map((block, index) => renderBlock(block, index))}
    </div>
  );
}

function parseBlocks(content: string): MarkdownBlock[] {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
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
      while (index < lines.length && !(lines[index] ?? "").trim().startsWith("```")) {
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
      while (index < lines.length && (lines[index] ?? "").trim().startsWith(">")) {
        quoteLines.push((lines[index] ?? "").trim().replace(/^>\s?/, ""));
        index += 1;
      }
      blocks.push({ type: "quote", text: quoteLines.join(" ") });
      continue;
    }

    const paragraphLines: string[] = [];
    while (index < lines.length && !isBlockBoundary(lines[index] ?? "")) {
      paragraphLines.push((lines[index] ?? "").trim());
      index += 1;
    }
    blocks.push({ type: "paragraph", text: paragraphLines.join(" ") });
  }

  return blocks;
}

function isBlockBoundary(line: string) {
  const trimmed = line.trim();
  return (
    !trimmed ||
    trimmed.startsWith("```") ||
    /^(#{1,3})\s+/.test(trimmed) ||
    /^\s*[-*•]\s+/.test(line) ||
    /^\s*\d+[.)]\s+/.test(line) ||
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

  if (block.type === "code") {
    return (
      <div key={index} className="overflow-hidden rounded-lg border border-slate-200 dark:border-slate-800">
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

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const pattern = /(\[[^\]]+\]\(([^)\s]+)\)|`([^`]+)`|\*\*([^*]+)\*\*|\*([^*]+)\*)/g;
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
        <strong key={key} className="font-semibold text-slate-950 dark:text-slate-50">
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
