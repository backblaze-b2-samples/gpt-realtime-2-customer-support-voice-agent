"use client";

import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Headphones } from "lucide-react";
import type { Call } from "@gpt-realtime-2-customer-support-voice-agent/shared";

interface Props {
  call: Call;
}

export function EndCallSummary({ call }: Props) {
  return (
    <Card className="p-5 space-y-3 border-primary/20 bg-primary/5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold">Call complete</h2>
        <Button asChild size="sm" variant="outline">
          <Link href={`/calls?id=${call.call_id}`}>
            <Headphones className="h-3.5 w-3.5" />
            Open bundle
          </Link>
        </Button>
      </div>
      <div className="grid grid-cols-3 gap-3 text-sm">
        <Stat label="Duration" value={`${call.duration_seconds.toFixed(0)}s`} />
        <Stat label="Tools" value={String(call.tool_count)} />
        <Stat label="Outcome" value={call.deflected ? "Resolved" : "Ticket created"} />
      </div>
      <p className="text-sm text-muted-foreground">{call.summary_line}</p>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="font-semibold">{value}</div>
    </div>
  );
}
