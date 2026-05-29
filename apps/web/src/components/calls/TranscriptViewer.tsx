"use client";

import type { TranscriptTurn } from "@gpt-realtime-2-customer-support-voice-agent/shared";

interface Props {
  turns: TranscriptTurn[];
}

export function TranscriptViewer({ turns }: Props) {
  if (turns.length === 0) {
    return <div className="text-xs text-muted-foreground">No transcript captured.</div>;
  }
  return (
    <div className="space-y-2 text-sm">
      {turns.map((t, i) => (
        <div key={i} className="flex gap-2">
          <span
            className={`shrink-0 inline-block px-1.5 py-0.5 rounded text-[10px] uppercase font-semibold ${
              t.speaker === "agent"
                ? "bg-primary/10 text-primary"
                : "bg-muted text-muted-foreground"
            }`}
          >
            {t.speaker}
          </span>
          <span>{t.text}</span>
        </div>
      ))}
    </div>
  );
}
