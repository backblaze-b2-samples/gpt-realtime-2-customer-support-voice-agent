"use client";

interface Props {
  active: boolean;
}

/** Tiny rolling-bars indicator. v1 is just an animation hint — wiring it
 * up to actual `AnalyserNode` RMS data is a follow-up. */
export function MicLevelIndicator({ active }: Props) {
  return (
    <div className="flex items-end gap-0.5 h-3" aria-hidden>
      {[0, 1, 2, 3].map((i) => (
        <span
          key={i}
          className={`block w-1 rounded-sm transition-all ${
            active
              ? "bg-emerald-500 animate-pulse"
              : "bg-muted-foreground/30"
          }`}
          style={{ height: `${4 + i * 3}px`, animationDelay: `${i * 80}ms` }}
        />
      ))}
    </div>
  );
}
