import type { Verdict } from "../lib/types";

const VERDICT_STYLES: Record<Verdict, { label: string; className: string }> = {
  PASSED: { label: "Passed", className: "badge badge-passed" },
  FAILED: { label: "Failed", className: "badge badge-failed" },
  CONTRADICTORY: { label: "Contradictory", className: "badge badge-contradictory" },
  NOT_FOUND: { label: "Not found", className: "badge badge-not-found" },
};

export default function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const style = VERDICT_STYLES[verdict] ?? { label: verdict, className: "badge" };
  return <span className={style.className}>{style.label}</span>;
}
