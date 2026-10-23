import type { MouseEvent } from "react";
import type { JobItem } from "../lib/types";
import VerdictBadge from "./VerdictBadge.tsx";

export default function RiskSummaryCard({ items }: { items: JobItem[] }) {
  if (items.length === 0) return null;

  function handleClick(e: MouseEvent<HTMLAnchorElement>, anchorId: string) {
    e.preventDefault();
    document.getElementById(anchorId)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <div className="risk-summary-card">
      <div className="risk-summary-title">
        {items.length} item{items.length !== 1 ? "s" : ""} need{items.length === 1 ? "s" : ""} attention
      </div>
      <ul className="risk-summary-list">
        {items.map((item) => {
          const anchorId = `item-${item.id}`;
          return (
            <li key={item.id}>
              <a
                href={`#${anchorId}`}
                className="risk-summary-link"
                onClick={(e) => handleClick(e, anchorId)}
              >
                <VerdictBadge verdict={item.result!.verdict} />
                <span>{item.label}</span>
              </a>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
