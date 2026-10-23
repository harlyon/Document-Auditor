import { useState } from "react";
import VerdictBadge from "../VerdictBadge.tsx";
import SubQuestion from "./SubQuestion.tsx";
import type { AuditLog } from "../../lib/types";

function PageRef({
  page,
  onViewPage,
}: {
  page: number | undefined;
  onViewPage?: (page: number) => void;
}) {
  if (page == null) return <span className="citation-page">Page ?</span>;
  if (!onViewPage) return <span className="citation-page">Page {page}</span>;
  return (
    <button type="button" className="citation-page citation-page-link" onClick={() => onViewPage(page)}>
      Page {page} &#8599;
    </button>
  );
}

export default function DoneRow({
  id,
  label,
  question,
  result,
  onViewPage,
}: {
  id: string;
  label: string;
  question: string;
  result: AuditLog;
  onViewPage?: (page: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const citations = result.exact_quote_citations || [];
  const pages = result.page_citations || [];

  return (
    <div id={id} className="item-card item-done">
      <div className="item-header">
        <VerdictBadge verdict={result.verdict} />
        <span className="item-question">{label}</span>
      </div>
      <SubQuestion label={label} question={question} />
      <p className="item-statement">{result.raw_statement}</p>

      {result.contradiction_detected && (
        <div className="contradiction-note">
          <strong>Contradiction:</strong> {result.contradiction_notes}
        </div>
      )}

      {citations.length > 0 && (
        <div className="citations">
          <button className="link-button" onClick={() => setExpanded((v) => !v)}>
            {expanded ? "Hide" : "Show"} {citations.length} citation{citations.length !== 1 ? "s" : ""}
          </button>
          <ul className={`citation-list ${expanded ? "" : "citation-list-collapsed"}`}>
            {citations.map((quote, i) => (
              <li key={i}>
                <PageRef page={pages[i]} onViewPage={onViewPage} />
                <blockquote>&ldquo;{quote}&rdquo;</blockquote>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
