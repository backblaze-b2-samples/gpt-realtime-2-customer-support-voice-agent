"use client";

import { Card } from "@/components/ui/card";
import { CheckCircle2, AlertCircle } from "lucide-react";
import type { ToolEvent } from "@gpt-realtime-2-customer-support-voice-agent/shared";

interface Props {
  events: ToolEvent[];
}

export function ToolTracePanel({ events }: Props) {
  return (
    <Card className="p-5 space-y-3 lg:max-h-[600px] lg:overflow-y-auto">
      <h2 className="text-sm font-semibold">Tool Trace</h2>
      {events.length === 0 ? (
        <div className="text-sm text-muted-foreground py-4">
          The agent hasn&apos;t called any tools yet.
        </div>
      ) : (
        <ol className="space-y-3 text-sm">
          {events.map((e) => (
            <li key={e.tool_call_id} className="border-l-2 border-muted pl-3">
              <div className="flex items-center gap-2 font-medium">
                {e.ok ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                ) : (
                  <AlertCircle className="h-3.5 w-3.5 text-destructive" />
                )}
                {e.tool}
                <span className="ml-auto text-xs text-muted-foreground">
                  {e.latency_ms.toFixed(0)} ms
                </span>
              </div>
              <pre className="mt-1 text-[11px] bg-muted/40 rounded p-2 overflow-x-auto">
                {JSON.stringify(e.args, null, 2)}
              </pre>
              {e.error && <div className="mt-1 text-xs text-destructive">{e.error}</div>}
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
