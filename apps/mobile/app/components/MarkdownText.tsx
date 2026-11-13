import React from "react";
import { Text, TextStyle, StyleSheet } from "react-native";

interface MarkdownTextProps {
  content: string;
  style?: TextStyle | TextStyle[];
  isUser?: boolean;
}

/**
 * Parses lightweight Markdown (bold **text**, bullets * / -, headers #, inline code `code`)
 * into native React Native <Text> elements without raw formatting symbols like **.
 */
export function MarkdownText({
  content,
  style,
  isUser = false,
}: MarkdownTextProps) {
  if (!content) return null;

  const lines = content.split("\n");

  return (
    <Text style={style}>
      {lines.map((rawLine, lineIndex) => {
        let line = rawLine;
        let isHeader = false;
        let headerLevel = 0;
        let isBullet = false;

        // Check for Markdown headers: #, ##, ###
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
          // Check for bullet items: "* " or "- "
          isBullet = true;
          line = "• " + line.replace(/^(\*|-)\s+/, "");
        }

        // Split line by bold (**text** or __text__) and inline code (`code`)
        // Regex matches **...**, __...__, or `...`
        const parts = line.split(/(\*\*[^*]+?\*\*|__[^_]+?__|`[^`]+?`)/g);

        return (
          <React.Fragment key={`line-${lineIndex}`}>
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
                  <Text
                    key={`part-${partIndex}`}
                    style={[
                      isUser ? styles.boldUser : styles.boldAgent,
                      isHeader && styles.headerText,
                    ]}
                  >
                    {boldContent}
                  </Text>
                );
              }

              if (
                part.startsWith("`") &&
                part.endsWith("`") &&
                part.length >= 2
              ) {
                const codeContent = part.slice(1, -1);
                return (
                  <Text
                    key={`part-${partIndex}`}
                    style={[
                      styles.code,
                      isUser && {
                        backgroundColor: "rgba(255,255,255,0.2)",
                        color: "#ffffff",
                      },
                    ]}
                  >
                    {codeContent}
                  </Text>
                );
              }

              return (
                <Text
                  key={`part-${partIndex}`}
                  style={[
                    isHeader && styles.headerText,
                    isHeader && headerLevel === 1 && styles.h1,
                    isHeader && headerLevel === 2 && styles.h2,
                    isBullet && styles.bulletText,
                  ]}
                >
                  {part}
                </Text>
              );
            })}
            {lineIndex < lines.length - 1 ? "\n" : null}
          </React.Fragment>
        );
      })}
    </Text>
  );
}

const styles = StyleSheet.create({
  boldAgent: {
    fontWeight: "700",
    color: "#0f172a",
  },
  boldUser: {
    fontWeight: "700",
    color: "#ffffff",
  },
  headerText: {
    fontWeight: "700",
  },
  bulletText: {
    paddingLeft: 4,
  },
  h1: {
    fontSize: 16,
  },
  h2: {
    fontSize: 15,
  },
  code: {
    fontFamily: "monospace",
    backgroundColor: "#f1f5f9",
    color: "#0f172a",
    paddingHorizontal: 4,
    borderRadius: 4,
    fontSize: 12,
  },
});
