# src/store.py
"""
SQLite-backed persistence for audit jobs.

Replaces api.py's old `_JOBS: dict` in-memory store, which lost every job on
restart and couldn't be shared across worker processes. This is deliberately
NOT a full ORM/migration setup -- a job is a single JSON blob keyed by
job_id, written through on every state change. That's enough to survive a
restart, which is the actual problem being solved; it does not make jobs
resumable mid-flight (see `reconcile_interrupted_jobs`) or make it safe to
run more than one uvicorn worker against the same file (SQLite serializes
writes from a single process fine, but this module opens one connection
with `check_same_thread=False` and a lock, not a connection pool -- multiple
processes hitting the same file will contend and are not the target use
case; that still needs Postgres/Redis, per ARCHITECTURE.md).

DB_PATH defaults to ./jobs.db (relative to the working directory, same
convention as UPLOAD_DIR in api.py). Mount a persistent volume over it in
Docker, same as uploads/ -- see the Dockerfile.
"""
import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Dict, Optional

DB_PATH = Path(os.environ.get("JOBS_DB_PATH", "jobs.db"))

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.execute(
            "CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, data TEXT NOT NULL)"
        )
        _conn.commit()
    return _conn


def save_job(job: dict) -> None:
    """Writes (inserts or replaces) the full job dict as a JSON blob."""
    conn = _get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO jobs (job_id, data) VALUES (?, ?) "
            "ON CONFLICT(job_id) DO UPDATE SET data = excluded.data",
            (job["job_id"], json.dumps(job)),
        )
        conn.commit()


def delete_job(job_id: str) -> None:
    """Permanently removes a job's persisted record. Callers are responsible
    for also removing its uploaded file and its entry in the in-memory
    _JOBS dict (see api.py's delete_audit) -- this only touches the DB row."""
    conn = _get_conn()
    with _lock:
        conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        conn.commit()


def load_all_jobs() -> Dict[str, dict]:
    """Loads every persisted job into a {job_id: job} dict, in insertion order."""
    conn = _get_conn()
    with _lock:
        rows = conn.execute("SELECT data FROM jobs").fetchall()
    jobs: Dict[str, dict] = {}
    for (data,) in rows:
        job = json.loads(data)
        jobs[job["job_id"]] = job
    return jobs


def reconcile_interrupted_jobs(jobs: Dict[str, dict]) -> None:
    """
    Called once at startup, right after load_all_jobs(). A job left in
    `queued` or `processing` means the process died mid-audit -- the
    asyncio task that was running it is gone, and nothing will ever move
    that job forward. This is NOT a resumable-jobs feature: it just marks
    those jobs `failed` with an honest reason instead of leaving them
    stuck "processing" forever, and persists that correction back to disk.
    """
    for job in jobs.values():
        if job["status"] in ("queued", "processing"):
            job["status"] = "failed"
            job["error"] = "Interrupted by a server restart before the audit finished. Please re-run it."
            save_job(job)
