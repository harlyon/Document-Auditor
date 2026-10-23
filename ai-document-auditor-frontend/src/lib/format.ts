import type { JobSummary } from "./types";

export function relativeTime(isoString: string): string {
  const then = new Date(isoString).getTime();
  const diffMs = Date.now() - then;
  const diffSec = Math.round(diffMs / 1000);

  if (diffSec < 5) return "just now";
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHour = Math.round(diffMin / 60);
  if (diffHour < 24) return `${diffHour}h ago`;
  const diffDay = Math.round(diffHour / 24);
  if (diffDay < 7) return `${diffDay}d ago`;

  return new Date(isoString).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export type StatusTone = "good" | "warn" | "bad" | "pending";

export interface OverallStatus {
  label: string;
  tone: StatusTone;
}


export function overallStatus(summary: JobSummary): OverallStatus {
  if (summary.status === "failed") {
    return { label: "Failed", tone: "bad" };
  }
  if (summary.status !== "completed") {
    return { label: "In progress", tone: "pending" };
  }
  const { FAILED, CONTRADICTORY } = summary.verdict_counts;
  if (CONTRADICTORY > 0) {
    return { label: "Contradictions found", tone: "bad" };
  }
  if (FAILED > 0) {
    return { label: "Needs attention", tone: "warn" };
  }
  return { label: "All clear", tone: "good" };
}
