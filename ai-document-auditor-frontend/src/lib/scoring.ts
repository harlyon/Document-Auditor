import type { AuditLog, JobItem } from "./types";

export interface HealthScore {
  score: number | null;
  passed: number;
  failed: number;
  contradictory: number;
  notFound: number;
  applicableTotal: number;
}


export function computeHealthScore(items: JobItem[]): HealthScore {
  let passed = 0;
  let failed = 0;
  let contradictory = 0;
  let notFound = 0;

  for (const item of items) {
    if (item.status !== "done" || !item.result) continue;
    switch (item.result.verdict) {
      case "PASSED":
        passed++;
        break;
      case "FAILED":
        failed++;
        break;
      case "CONTRADICTORY":
        contradictory++;
        break;
      case "NOT_FOUND":
        notFound++;
        break;
    }
  }

  const applicableTotal = passed + failed + contradictory;
  const score = applicableTotal === 0 ? null : Math.round((passed / applicableTotal) * 100);

  return { score, passed, failed, contradictory, notFound, applicableTotal };
}


const SEVERITY_ORDER: Record<AuditLog["verdict"], number> = {
  CONTRADICTORY: 0,
  FAILED: 1,
  NOT_FOUND: 2,
  PASSED: 3,
};

export function getRiskItems(items: JobItem[]): JobItem[] {
  return items
    .filter((item) => item.status === "done" && item.result &&
      (item.result.verdict === "CONTRADICTORY" || item.result.verdict === "FAILED"))
    .sort((a, b) => SEVERITY_ORDER[a.result!.verdict] - SEVERITY_ORDER[b.result!.verdict]);
}
