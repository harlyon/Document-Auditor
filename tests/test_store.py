# tests/test_store.py
import importlib

import src.store as store


def _fresh_store(monkeypatch, tmp_path):
    """Points src.store at a fresh on-disk DB and resets its module-level
    connection cache -- store.py opens one connection lazily and caches it in
    a module global, so each test needs its own file and a reloaded module
    state to avoid bleeding into other tests."""
    db_path = tmp_path / "jobs.db"
    monkeypatch.setattr(store, "DB_PATH", db_path)
    monkeypatch.setattr(store, "_conn", None)
    return store


def make_job(job_id, status):
    return {
        "job_id": job_id,
        "status": status,
        "document": "contract.txt",
        "file_path": "/uploads/x/contract.txt",
        "created_at": "2026-01-01T00:00:00+00:00",
        "error": None,
        "items": [
            {"id": "a", "label": "A", "checklist_item": "Q?", "status": "queued", "result": None, "error": None},
        ],
    }


def test_save_and_load_round_trips_a_job(monkeypatch, tmp_path):
    s = _fresh_store(monkeypatch, tmp_path)
    job = make_job("job-1", "completed")

    s.save_job(job)
    loaded = s.load_all_jobs()

    assert loaded == {"job-1": job}


def test_save_job_overwrites_existing_entry(monkeypatch, tmp_path):
    s = _fresh_store(monkeypatch, tmp_path)
    job = make_job("job-1", "processing")
    s.save_job(job)

    job["status"] = "completed"
    s.save_job(job)

    loaded = s.load_all_jobs()
    assert loaded["job-1"]["status"] == "completed"
    assert len(loaded) == 1


def test_delete_job_removes_only_the_targeted_row(monkeypatch, tmp_path):
    s = _fresh_store(monkeypatch, tmp_path)
    s.save_job(make_job("job-1", "completed"))
    s.save_job(make_job("job-2", "completed"))

    s.delete_job("job-1")

    loaded = s.load_all_jobs()
    assert "job-1" not in loaded
    assert "job-2" in loaded


def test_delete_job_on_unknown_id_is_a_no_op(monkeypatch, tmp_path):
    s = _fresh_store(monkeypatch, tmp_path)
    s.save_job(make_job("job-1", "completed"))

    s.delete_job("does-not-exist")  # must not raise

    assert "job-1" in s.load_all_jobs()


def test_load_all_jobs_survives_a_fresh_connection(monkeypatch, tmp_path):
    # Simulates a real restart: save through one connection, then force a new
    # one (as happens when the process restarts and _conn is None again) and
    # confirm the data is actually on disk, not just cached in memory.
    s = _fresh_store(monkeypatch, tmp_path)
    s.save_job(make_job("job-1", "completed"))

    monkeypatch.setattr(s, "_conn", None)  # forces _get_conn() to reopen the file
    loaded = s.load_all_jobs()

    assert "job-1" in loaded
    assert loaded["job-1"]["status"] == "completed"


def test_reconcile_interrupted_jobs_fails_queued_and_processing_jobs(monkeypatch, tmp_path):
    s = _fresh_store(monkeypatch, tmp_path)
    jobs = {
        "queued-job": make_job("queued-job", "queued"),
        "processing-job": make_job("processing-job", "processing"),
        "completed-job": make_job("completed-job", "completed"),
        "failed-job": make_job("failed-job", "failed"),
    }

    s.reconcile_interrupted_jobs(jobs)

    assert jobs["queued-job"]["status"] == "failed"
    assert jobs["processing-job"]["status"] == "failed"
    assert "restart" in jobs["queued-job"]["error"]
    # Untouched: already-terminal jobs aren't rewritten.
    assert jobs["completed-job"]["status"] == "completed"
    assert jobs["completed-job"]["error"] is None
    assert jobs["failed-job"]["status"] == "failed"


def test_reconcile_interrupted_jobs_persists_the_correction(monkeypatch, tmp_path):
    s = _fresh_store(monkeypatch, tmp_path)
    jobs = {"job-1": make_job("job-1", "processing")}

    s.reconcile_interrupted_jobs(jobs)

    monkeypatch.setattr(s, "_conn", None)
    reloaded = s.load_all_jobs()
    assert reloaded["job-1"]["status"] == "failed"
