"use client";

interface Props {
  markdown: string;
}

/** Lightweight Markdown renderer — headings and paragraphs only.
 * Heavier Markdown features aren't needed for the summary format the
 * orchestrator emits (`## Caller intent` / `## What the agent did` / `## Resolution`).
 */
export function SummaryCard({ markdown }: Props) {
  if (!markdown.trim()) {
    return <div className="text-xs text-muted-foreground">No summary yet.</div>;
  }
  const blocks = markdown.split(/\n{2,}/).map((b, i) => {
    if (b.startsWith("# ")) {
      return (
        <h2 key={i} className="text-lg font-semibold mt-3">
          {b.slice(2).trim()}
        </h2>
      );
    }
    if (b.startsWith("## ")) {
      return (
        <h3 key={i} className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mt-3">
          {b.slice(3).trim()}
        </h3>
      );
    }
    return (
      <p key={i} className="text-sm leading-relaxed">
        {b}
      </p>
    );
  });
  return <div className="space-y-2">{blocks}</div>;
}
