"use client";

import { Phone, Clock, Wrench, Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { useCallStats } from "@/lib/queries";

function fmtDuration(seconds: number) {
  if (!seconds) return "0s";
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

export function StatsCards() {
  const { data: stats, isLoading, error, refetch } = useCallStats();

  if (error) {
    return (
      <Card>
        <CardContent className="p-0">
          <ErrorState error={error} onRetry={() => refetch()} />
        </CardContent>
      </Card>
    );
  }

  const cards = [
    { title: "Calls Today", value: stats?.calls_today ?? 0, icon: Phone },
    { title: "Calls This Week", value: stats?.calls_this_week ?? 0, icon: Phone },
    { title: "Avg Duration", value: fmtDuration(stats?.avg_duration_seconds ?? 0), icon: Clock },
    {
      title: "Deflection Rate",
      value: `${Math.round((stats?.deflection_rate ?? 0) * 100)}%`,
      icon: Sparkles,
    },
    { title: "Tool Calls", value: stats?.total_tool_calls ?? 0, icon: Wrench },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {cards.map((card, i) => (
        <Card key={card.title} className={`card-hover animate-fade-in-up stagger-${i + 1}`}>
          <CardHeader className="flex flex-row items-center justify-between pt-4 pb-2 px-4 space-y-0">
            <CardTitle className="text-xs font-semibold text-muted-foreground">
              {card.title}
            </CardTitle>
            <div className="stat-icon-wrap">
              <card.icon className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent className="pb-5 px-4">
            {isLoading ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <div className="stat-value">{card.value}</div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
