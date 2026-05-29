"use client";

import Link from "next/link";
import { Mic, MicOff, PhoneOff, Phone, AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useRealtimeCall } from "@/hooks/use-realtime-call";
import { LiveTranscript } from "@/components/call/LiveTranscript";
import { ToolTracePanel } from "@/components/call/ToolTracePanel";
import { MicLevelIndicator } from "@/components/call/MicLevelIndicator";
import { EndCallSummary } from "@/components/call/EndCallSummary";

const STATE_LABELS: Record<string, string> = {
  idle: "Ready",
  connecting: "Setting up call...",
  connected: "Live",
  ending: "Wrapping up...",
  ended: "Call complete",
  error: "Error",
};

export function CallConsole() {
  const call = useRealtimeCall();
  const isLive = call.state === "connected";
  const canStart = call.state === "idle" || call.state === "ended" || call.state === "error";

  return (
    <div className="space-y-6">
      <Card className="p-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span
            className={`inline-flex h-2.5 w-2.5 rounded-full ${
              isLive ? "bg-emerald-500 animate-pulse" : "bg-muted-foreground/40"
            }`}
            aria-hidden
          />
          <div>
            <div className="text-sm font-semibold">{STATE_LABELS[call.state]}</div>
            {call.callId && (
              <div className="text-xs text-muted-foreground font-mono">{call.callId}</div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isLive && (
            <Button
              variant={call.muted ? "default" : "secondary"}
              size="sm"
              onClick={call.toggleMute}
            >
              {call.muted ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
              {call.muted ? "Unmute" : "Mute"}
            </Button>
          )}
          {canStart ? (
            <Button onClick={() => void call.start()}>
              <Phone className="h-4 w-4" />
              Start Call
            </Button>
          ) : (
            <Button variant="destructive" onClick={() => void call.end()} disabled={call.state === "ending"}>
              <PhoneOff className="h-4 w-4" />
              End Call
            </Button>
          )}
        </div>
      </Card>

      {call.error && (
        <Card className="p-4 flex items-start gap-3 border-destructive/30 bg-destructive/5">
          <AlertTriangle className="h-4 w-4 mt-0.5 text-destructive" />
          <div className="text-sm">{call.error}</div>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          <Card className="p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold">Live Transcript</h2>
              <MicLevelIndicator active={isLive && !call.muted} />
            </div>
            <LiveTranscript turns={call.transcript} />
          </Card>
          {call.finalized && (
            <EndCallSummary call={call.finalized} />
          )}
          {call.state === "idle" && (
            <div className="text-sm text-muted-foreground">
              Click <strong>Start Call</strong> to connect to the agent. After the call,
              browse the bundle in <Link href="/calls" className="underline">Calls</Link>.
            </div>
          )}
        </div>
        <ToolTracePanel events={call.tools} />
      </div>
    </div>
  );
}
