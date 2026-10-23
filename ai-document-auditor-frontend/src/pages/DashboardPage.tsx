import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { deleteAudit, listAudits } from "../lib/api.ts";
import { overallStatus, relativeTime } from "../lib/format.ts";
import type { JobSummary } from "../lib/types";

const POLL_INTERVAL_MS = 4000;
const IN_PROGRESS_STATUSES = new Set(["queued", "processing"]);

export default function DashboardPage() {
  const [audits, setAudits] = useState<JobSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await listAudits();
        if (cancelled) return;
        setAudits(data);
        setError(null);
        if (data.some((a) => IN_PROGRESS_STATUSES.has(a.status))) {
          timerRef.current = setTimeout(load, POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      }
    }

    load();
    return () => {
      cancelled = true;
      clearTimeout(timerRef.current);
    };
  }, []);

  async function handleDelete(e: React.MouseEvent, audit: JobSummary) {
    e.preventDefault();
    e.stopPropagation();

    if (!window.confirm(`Delete the audit for "${audit.document}"? This can't be undone.`)) {
      return;
    }

    setDeletingId(audit.job_id);
    try {
      await deleteAudit(audit.job_id);
      setAudits((prev) => prev && prev.filter((a) => a.job_id !== audit.job_id));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="dashboard-page">
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p className="subtitle">Recent audits and their status at a glance.</p>
        </div>
        <Link to="/new" className="primary-button-link">
          + New Audit
        </Link>
      </div>

      {error && <div className="job-error-banner">{error}</div>}

      {audits === null && !error && <p className="dashboard-loading">Loading…</p>}

      {audits && audits.length === 0 && (
        <div className="empty-state">
          <p>No audits yet.</p>
          <Link to="/new" className="primary-button-link">Run your first audit</Link>
        </div>
      )}

      {audits && audits.length > 0 && (
        <div className="audit-grid">
          {audits.map((audit) => {
            const status = overallStatus(audit);
            const isRunning = IN_PROGRESS_STATUSES.has(audit.status);
            return (
              <Link key={audit.job_id} to={`/audits/${audit.job_id}`} className="audit-card">
                <div className="audit-card-top">
                  <span className={`status-dot status-dot-${status.tone}`} aria-hidden="true" />
                  <span className="audit-card-doc" title={audit.document}>{audit.document}</span>
                  <button
                    type="button"
                    className="audit-card-delete"
                    onClick={(e) => handleDelete(e, audit)}
                    disabled={isRunning || deletingId === audit.job_id}
                    title={isRunning ? "Can't delete an audit that's still running" : "Delete this audit"}
                    aria-label={`Delete audit for ${audit.document}`}
                  >
                    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M5 7h14M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2m-8 0v13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V7"
                        stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                      <path d="M10 11v6M14 11v6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                    </svg>
                  </button>
                </div>
                <div className="audit-card-status">{status.label}</div>
                <div className="audit-card-meta">
                  <span>{audit.done_count}/{audit.item_count} checks</span>
                  <span aria-hidden="true">·</span>
                  <span>{relativeTime(audit.created_at)}</span>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
