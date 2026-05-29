"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";

import { CallsList } from "@/components/calls/CallsList";
import { CallDetail } from "@/components/calls/CallDetail";

function CallsPageInner() {
  const params = useSearchParams();
  const initial = params.get("id");
  const [selected, setSelected] = useState<string | null>(initial);

  return (
    <div className="space-y-6">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">Calls</h1>
        <p className="text-sm text-muted-foreground mt-1.5">
          Browse, play, and inspect per-call bundles in your B2 bucket
          (<code className="text-xs">calls/</code> prefix).
        </p>
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(320px,1fr)_2fr]">
        <CallsList onSelect={setSelected} selectedId={selected} />
        {selected && <CallDetail callId={selected} />}
      </div>
    </div>
  );
}

export default function CallsPage() {
  return (
    <Suspense fallback={<div className="text-sm text-muted-foreground">Loading…</div>}>
      <CallsPageInner />
    </Suspense>
  );
}
