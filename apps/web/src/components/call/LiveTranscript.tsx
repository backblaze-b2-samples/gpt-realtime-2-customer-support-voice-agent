"use client";

import type { TranscriptTurn } from "@gpt-realtime-2-customer-support-voice-agent/shared";

interface Props {
  turns: TranscriptTurn[];
}

export function LiveTranscript({ turns }: Props) {
  if (turns.length === 0) {
    return (
      <div className="text-sm text-muted-foreground py-6 text-center border border-dashed rounded-md">
        Waiting for audio…
      </div>
    );
  }
  return (
    <div className="space-y-3 max-h-[400px] overflow-y-auto pr-1">
      {turns.map((t, i) => (
        <div key={i} className="text-sm">
          <span
            className={`mr-2 inline-block px-1.5 py-0.5 rounded text-[10px] uppercase font-semibold ${
              t.speaker === "agent"
                ? "bg-primary/10 text-primary"
                : "bg-muted text-muted-foreground"
            }`}
          >
            {t.speaker}
          </span>
          {t.text}
        </div>
      ))}
    </div>
  );
}
