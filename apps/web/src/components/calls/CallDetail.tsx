"use client";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { useCallDetail } from "@/lib/queries";
import { CallAudioPlayer } from "@/components/calls/CallAudioPlayer";
import { TranscriptViewer } from "@/components/calls/TranscriptViewer";
import { SummaryCard } from "@/components/calls/SummaryCard";
import { CheckCircle2, AlertCircle } from "lucide-react";

interface Props {
  callId: string;
}

export function CallDetail({ callId }: Props) {
  const { data, isLoading, error, refetch } = useCallDetail(callId, true);

  if (isLoading) {
    return (
      <Card className="p-5 space-y-3">
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </Card>
    );
  }
  if (error) {
    return <ErrorState error={error} onRetry={() => refetch()} />;
  }
  if (!data) return null;

  return (
    <Card className="p-5 space-y-6">
      <header>
        <div className="font-mono text-xs text-muted-foreground">{callId}</div>
        <div className="text-sm">
          {new Date(data.manifest.started_at).toLocaleString()} &middot;{" "}
          {data.manifest.duration_seconds.toFixed(0)}s &middot;{" "}
          {data.manifest.tool_count} tool calls
        </div>
      </header>
      <CallAudioPlayer callId={callId} />
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
          Summary
        </h3>
        <SummaryCard markdown={data.summary_markdown} />
      </section>
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
          Transcript
        </h3>
        <TranscriptViewer turns={data.transcript} />
      </section>
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
          Tool Trace
        </h3>
        <ol className="space-y-2 text-sm">
          {data.tools.map((t) => (
            <li key={t.tool_call_id} className="flex items-start gap-2 border-l-2 border-muted pl-3">
              {t.ok ? (
                <CheckCircle2 className="h-3.5 w-3.5 mt-1 text-emerald-500" />
              ) : (
                <AlertCircle className="h-3.5 w-3.5 mt-1 text-destructive" />
              )}
              <div className="flex-1">
                <div className="font-medium">{t.tool}</div>
                <pre className="mt-1 text-[11px] bg-muted/40 rounded p-2 overflow-x-auto">
                  {JSON.stringify(t.args, null, 2)}
                </pre>
                {t.error && <div className="text-xs text-destructive mt-1">{t.error}</div>}
              </div>
            </li>
          ))}
        </ol>
      </section>
    </Card>
  );
}
