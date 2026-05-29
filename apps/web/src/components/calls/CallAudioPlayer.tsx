"use client";

import { useCallAudioUrl } from "@/lib/queries";

interface Props {
  callId: string;
}

export function CallAudioPlayer({ callId }: Props) {
  const { data, isLoading, error } = useCallAudioUrl(callId, true);
  if (isLoading) {
    return <div className="text-xs text-muted-foreground">Loading audio…</div>;
  }
  if (error || !data) {
    return <div className="text-xs text-destructive">Audio unavailable.</div>;
  }
  return <audio controls preload="metadata" src={data.url} className="w-full" />;
}
