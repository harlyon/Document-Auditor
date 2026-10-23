import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { createAudit, deleteAudit, getAudit, getDocumentUrl } from "../lib/api.ts";
import ChecklistItemCard from "../components/ChecklistItemCard.tsx";
import HealthScoreCard from "../components/HealthScoreCard.tsx";
import RiskSummaryCard from "../components/RiskSummaryCard.tsx";
import DocumentViewerModal from "../components/DocumentViewerModal.tsx";
import { computeHealthScore, getRiskItems } from "../lib/scoring.ts";
import { buildMarkdownReport, downloadTextFile } from "../lib/exportReport.ts";
import type { Job, ResultsLocationState } from "../lib/types";

const POLL_INTERVAL_MS = 2000;
const TERMINAL_STATUSES = new Set(["completed", "failed"]);

export default function ResultsPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const [job, setJob] = useState<Job | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const [rerunning, setRerunning] = useState(false);
  const [deleting, setDeleting] = useState(false);
  // undefined = closed; a number|null = open (null = no specific page).
  const [viewerPage, setViewerPage] = useState<number | null | undefined>(undefined);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // Only present if we navigated here from UploadPage in this browser session
  // (react-router state doesn't survive a hard reload) -- see
  // ResultsLocationState's docstring in lib/types.ts for why.
  const runState = location.state as ResultsLocationState | null;

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;

    async function poll() {
      try {
        const data = await getAudit(jobId!);
        if (cancelled) return;
        setJob(data);
        setPollError(null);
        if (!TERMINAL_STATUSES.has(data.status)) {
          timerRef.current = setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (cancelled) return;
        setPollError(err instanceof Error ? err.message : String(err));
        // Back off and keep trying -- a transient network hiccup shouldn't
        // strand the user on a dead page.
        timerRef.current = setTimeout(poll, POLL_INTERVAL_MS);
      }
    }

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timerRef.current);
    };
  }, [jobId]);

  // Browsers suggest document.title as the default filename in the print/
  // "Save as PDF" dialog -- without this every export would default to the
  // app's generic tab title regardless of which document was audited.
  useEffect(() => {
    const documentName = job?.document;
    if (!documentName) return;
    const previousTitle = document.title;
    document.title = `${documentName} - Audit Report`;
    return () => {
      document.title = previousTitle;
    };
  }, [job?.document]);

  async function handleRerun() {
    if (!runState) return;
    setRerunning(true);
    try {
      const { job_id } = await createAudit(runState.file, runState.auditOptions);
      navigate(`/audits/${job_id}`, { state: runState });
    } catch (err) {
      setPollError(err instanceof Error ? err.message : String(err));
      setRerunning(false);
    }
  }

  async function handleDelete() {
    if (!job) return;
    if (!window.confirm(`Delete the audit for "${job.document}"? This can't be undone.`)) {
      return;
    }
    setDeleting(true);
    try {
      await deleteAudit(job.job_id);
      navigate("/dashboard");
    } catch (err) {
      setPollError(err instanceof Error ? err.message : String(err));
      setDeleting(false);
    }
  }

  function handleExport() {
    if (!job) return;
    const markdown = buildMarkdownReport(job);
    const safeName = job.document.replace(/\.[^.]+$/, "");
    downloadTextFile(`${safeName}-audit-report.md`, markdown);
  }

  if (!job) {
    return (
      <div className="page">
        <Link to="/dashboard" className="back-link">&larr; Dashboard</Link>
        <p>{pollError ? `Couldn't reach the server: ${pollError}` : "Loading…"}</p>
      </div>
    );
  }

  const doneCount = job.items.filter((i) => i.status !== "queued").length;
  const health = computeHealthScore(job.items);
  const riskItems = getRiskItems(job.items);
  const isTerminal = TERMINAL_STATUSES.has(job.status);
  const documentUrl = getDocumentUrl(job.job_id);
  const isPdf = job.document.toLowerCase().endsWith(".pdf");

  return (
    <div className="page">
      <Link to="/dashboard" className="back-link">&larr; Dashboard</Link>
      <h1>{job.document}</h1>

      <div className="action-bar">
        {isPdf ? (
          <button type="button" className="secondary-button" onClick={() => setViewerPage(null)}>
            View Document
          </button>
        ) : (
          <a
            className="secondary-button secondary-button-link"
            href={documentUrl}
            target="_blank"
            rel="noreferrer"
            title="This file type has no in-app preview yet -- opens via the browser's default handling"
          >
            Download Document
          </a>
        )}
        <button
          type="button"
          className="secondary-button"
          onClick={handleRerun}
          disabled={!runState || rerunning}
          title={runState ? undefined : "Re-run isn't available after a page reload -- start a new audit instead"}
        >
          {rerunning ? "Starting new run…" : "Re-run Audit"}
        </button>
        <button
          type="button"
          className="secondary-button danger-button"
          onClick={handleDelete}
          disabled={!isTerminal || deleting}
          title={isTerminal ? undefined : "Can't delete an audit that's still running"}
        >
          {deleting ? "Deleting…" : "Delete"}
        </button>
        <button
          type="button"
          className="secondary-button"
          onClick={handleExport}
          disabled={!isTerminal}
          title={isTerminal ? undefined : "Export becomes available once the audit finishes"}
        >
          Export Report
        </button>
        <button
          type="button"
          className="secondary-button"
          onClick={() => window.print()}
          disabled={!isTerminal}
          title={isTerminal ? undefined : "PDF export becomes available once the audit finishes"}
        >
          Download PDF
        </button>
      </div>

      {doneCount > 0 && <HealthScoreCard health={health} />}
      <RiskSummaryCard items={riskItems} />

      {job.status !== "completed" && job.status !== "failed" && (
        <div className="progress-banner">
          Auditing… {doneCount} of {job.items.length} checks complete
        </div>
      )}

      {job.status === "failed" && (
        <div className="job-error-banner">
          Audit failed: {job.error}
        </div>
      )}

      {pollError && <div className="job-error-banner">{pollError}</div>}

      <div className="item-list">
        {job.items.map((item) => (
          <ChecklistItemCard
            key={item.id}
            item={item}
            onViewPage={isPdf ? (page) => setViewerPage(page) : undefined}
          />
        ))}
      </div>

      {viewerPage !== undefined && (
        <DocumentViewerModal
          documentUrl={documentUrl}
          page={viewerPage ?? undefined}
          onClose={() => setViewerPage(undefined)}
        />
      )}
    </div>
  );
}
