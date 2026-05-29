"use client";

import { useState } from "react";
import { Headphones, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useCalls, useDeleteCall } from "@/lib/queries";

interface Props {
  onSelect: (callId: string) => void;
  selectedId: string | null;
}

export function CallsList({ onSelect, selectedId }: Props) {
  const { data, isLoading, error, refetch } = useCalls();
  const deleter = useDeleteCall();
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  if (isLoading) {
    return (
      <Card className="p-4 space-y-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </Card>
    );
  }
  if (error) {
    return <ErrorState error={error} onRetry={() => refetch()} />;
  }
  if (!data || data.length === 0) {
    return (
      <EmptyState
        title="No calls yet"
        description="Start your first call from the Call screen — the bundle will appear here when it ends."
      />
    );
  }

  const confirmDelete = () => {
    if (!deleteTarget) return;
    deleter.mutate(deleteTarget, {
      onSettled: () => setDeleteTarget(null),
    });
  };

  return (
    <>
      <Card className="divide-y">
        {data.map((call) => (
          <div
            key={call.call_id}
            className={`p-4 flex items-center gap-4 cursor-pointer hover:bg-muted/40 ${
              selectedId === call.call_id ? "bg-muted/60" : ""
            }`}
            onClick={() => onSelect(call.call_id)}
          >
            <Headphones className="h-4 w-4 text-muted-foreground" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-muted-foreground truncate">
                  {call.call_id}
                </span>
                {!call.complete && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-600 uppercase font-semibold">
                    incomplete
                  </span>
                )}
              </div>
              <div className="text-sm truncate">{call.summary_line}</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                {call.duration_seconds.toFixed(0)}s &middot; {call.tool_count} tools &middot;{" "}
                {new Date(call.started_at).toLocaleString()}
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                setDeleteTarget(call.call_id);
              }}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        ))}
      </Card>

      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete call?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes every object under the bundle prefix
              {deleteTarget ? ` (${deleteTarget})` : ""} — audio, transcript,
              summary, and tool trace. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              disabled={deleter.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleter.isPending ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
