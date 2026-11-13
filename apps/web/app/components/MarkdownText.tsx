import React from "react";

interface MarkdownTextProps {
  content: string;
  className?: string;
  isUser?: boolean;
}

/**
 * Lightweight Markdown renderer for Web (bold **text**, bullets * / -, headers #, inline code `code`).
 */
export function MarkdownText({
  content,
  className = "",
  isUser = false,
}: MarkdownTextProps) {
  if (!content) return null;

  const lines = content.split("\n");

  return (
    <div className={`space-y-1 ${className}`}>
      {lines.map((rawLine, lineIndex) => {
        let line = rawLine;
        let isHeader = false;
        let headerLevel = 0;
        let isBullet = false;

        if (line.startsWith("### ")) {
          isHeader = true;
          headerLevel = 3;
          line = line.slice(4);
        } else if (line.startsWith("## ")) {
          isHeader = true;
          headerLevel = 2;
          line = line.slice(3);
        } else if (line.startsWith("# ")) {
          isHeader = true;
          headerLevel = 1;
          line = line.slice(2);
        } else if (/^(\*|-)\s+/.test(line)) {
          isBullet = true;
          line = "• " + line.replace(/^(\*|-)\s+/, "");
        }

        const parts = line.split(/(\*\*[^*]+?\*\*|__[^_]+?__|`[^`]+?`)/g);

        return (
          <p
            key={`line-${lineIndex}`}
            className={`${
              isHeader
                ? headerLevel === 1
                  ? "text-base font-bold"
                  : headerLevel === 2
                    ? "text-sm font-bold"
                    : "text-xs font-bold"
                : ""
            } ${isBullet ? "pl-2" : ""}`}
          >
            {parts.map((part, partIndex) => {
              if (
                (part.startsWith("**") &&
                  part.endsWith("**") &&
                  part.length >= 4) ||
                (part.startsWith("__") &&
                  part.endsWith("__") &&
                  part.length >= 4)
              ) {
                const boldContent = part.slice(2, -2);
                return (
                  <strong
                    key={`part-${partIndex}`}
                    className={
                      isUser
                        ? "font-bold text-white"
                        : "font-bold text-slate-900"
                    }
                  >
                    {boldContent}
                  </strong>
                );
              }

              if (
                part.startsWith("`") &&
                part.endsWith("`") &&
                part.length >= 2
              ) {
                const codeContent = part.slice(1, -1);
                return (
                  <code
                    key={`part-${partIndex}`}
                    className={`rounded px-1 py-0.5 font-mono text-xs ${
                      isUser
                        ? "bg-white/20 text-white"
                        : "bg-slate-100 text-slate-800"
                    }`}
                  >
                    {codeContent}
                  </code>
                );
              }

              return <span key={`part-${partIndex}`}>{part}</span>;
            })}
          </p>
        );
      })}
    </div>
  );
}
