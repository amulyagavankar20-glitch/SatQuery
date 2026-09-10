import React from "react";
import { cn } from "@/lib/utils";

type MarkdownViewProps = {
  content: string;
  className?: string;
};

function formatInline(text: string): React.ReactNode {
  // Split by bold patterns **bold**
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      const inner = part.slice(2, -2);
      return (
        <strong key={i} className="font-semibold text-ink">
          {inner}
        </strong>
      );
    }
    // Highlight inline code `code`
    const codeParts = part.split(/(`[^`]+`)/g);
    if (codeParts.length > 1) {
      return (
        <span key={i}>
          {codeParts.map((cp, j) => {
            if (cp.startsWith("`") && cp.endsWith("`")) {
              return (
                <code key={j} className="rounded bg-white/10 px-1 py-0.5 font-mono text-[12px] text-primary">
                  {cp.slice(1, -1)}
                </code>
              );
            }
            return cp;
          })}
        </span>
      );
    }
    return part;
  });
}

export function MarkdownView({ content, className }: MarkdownViewProps) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  let currentList: string[] = [];

  const flushList = () => {
    if (currentList.length > 0) {
      elements.push(
        <ul key={`list-${elements.length}`} className="my-2.5 space-y-1.5 pl-4 text-[14px] leading-relaxed text-ink/90">
          {currentList.map((item, idx) => (
            <li key={idx} className="list-disc pl-1 text-ink/90">
              {formatInline(item)}
            </li>
          ))}
        </ul>
      );
      currentList = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const line = rawLine.trim();

    if (!line) {
      flushList();
      continue;
    }

    if (line.startsWith("### ")) {
      flushList();
      const title = line.replace(/^###\s+/, "");
      elements.push(
        <h3
          key={`h3-${i}`}
          className="mt-4 mb-2 flex items-center gap-2 border-b border-white/5 pb-1 font-mono text-[13px] font-medium tracking-wide text-primary uppercase"
        >
          <span className="inline-block size-1.5 rounded-full bg-primary/70" />
          {title}
        </h3>
      );
    } else if (line.startsWith("## ")) {
      flushList();
      const title = line.replace(/^##\s+/, "");
      elements.push(
        <h2
          key={`h2-${i}`}
          className="mt-5 mb-2 font-mono text-[14px] font-semibold tracking-wider text-ink uppercase"
        >
          {title}
        </h2>
      );
    } else if (line.startsWith("- ") || line.startsWith("* ")) {
      const itemText = line.replace(/^[-*]\s+/, "");
      currentList.push(itemText);
    } else if (line.startsWith("> ")) {
      flushList();
      const quoteText = line.replace(/^>\s+/, "");
      elements.push(
        <div
          key={`quote-${i}`}
          className="my-2 rounded-r-lg border-l-2 border-primary/60 bg-primary/5 px-3 py-2 text-[13px] text-ink/80 italic"
        >
          {formatInline(quoteText)}
        </div>
      );
    } else {
      flushList();
      elements.push(
        <p key={`p-${i}`} className="my-1.5 text-[14.5px] leading-relaxed text-ink/90">
          {formatInline(line)}
        </p>
      );
    }
  }

  flushList();

  return <div className={cn("space-y-0.5", className)}>{elements}</div>;
}
