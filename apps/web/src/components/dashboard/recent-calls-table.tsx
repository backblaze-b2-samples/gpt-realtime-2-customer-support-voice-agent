"use client";

import Link from "next/link";
import { ArrowRight, Inbox } from "lucide-react";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { useCalls } from "@/lib/queries";
import { formatDate } from "@/lib/utils";

export function RecentCallsTable() {
  const { data: calls = [], isLoading, error, refetch } = useCalls(10);

  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">Recent Calls</CardTitle>
        <CardAction className="self-center">
          <Link
            href="/calls"
            className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            View all
            <ArrowRight className="h-3 w-3" />
          </Link>
        </CardAction>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <div className="p-4 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : error ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : calls.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title="No calls yet"
            description="Start your first call from the Call screen."
          />
        ) : (
          <Table className="table-fixed">
            <TableHeader>
              <TableRow className="bg-muted/40 hover:bg-muted/40">
                <TableHead className="w-[42%] text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Summary
                </TableHead>
                <TableHead className="w-[14%] text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Duration
                </TableHead>
                <TableHead className="w-[12%] text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Tools
                </TableHead>
                <TableHead className="w-[18%] text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Date
                </TableHead>
                <TableHead className="w-[14%] text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Outcome
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {calls.map((call) => (
                <TableRow key={call.call_id} className="table-row-hover">
                  <TableCell>
                    <Link href={`/calls?id=${call.call_id}`} className="font-medium hover:underline">
                      <div className="truncate">{call.summary_line}</div>
                    </Link>
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground tabular-nums whitespace-nowrap">
                    {call.duration_seconds.toFixed(0)}s
                  </TableCell>
                  <TableCell className="text-muted-foreground whitespace-nowrap">
                    {call.tool_count}
                  </TableCell>
                  <TableCell className="text-muted-foreground whitespace-nowrap">
                    {formatDate(call.started_at)}
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${
                          call.deflected ? "bg-[var(--success)]" : "bg-amber-500"
                        }`}
                      />
                      {call.deflected ? "Resolved" : "Ticketed"}
                    </span>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
