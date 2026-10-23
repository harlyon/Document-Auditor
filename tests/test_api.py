# tests/test_api.py
import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, tmp_path):
    # Point the app at a scratch DB so this test never touches the real
    # jobs.db, then reload api.py fresh so its module-level _JOBS is
    # rebuilt from that empty DB rather than whatever's already imported.
    #
    # Setting API_KEY to "" rather than deleting it matters here: api.py's
    # reload re-runs load_dotenv(), which (with its default override=False)
    # leaves an already-present env var alone but happily fills in an absent
    # one from the real repo-root .env -- which, on this machine, now has a
    # real API_KEY in it. An empty string is still present, so dotenv leaves
    # it alone, and it's still falsy to auth.require_api_key's `if not
    # expected` check -- auth stays off for this fixture either way.
    monkeypatch.setenv("JOBS_DB_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.setenv("API_KEY", "")

    import src.store as store
    importlib.reload(store)

    import api
    importlib.reload(api)

    return api


def done_item(verdict):
    return {
        "id": "a", "label": "A", "checklist_item": "Q?", "status": "done",
        "result": {"verdict": verdict}, "error": None,
    }


def queued_item():
    return {"id": "b", "label": "B", "checklist_item": "Q2?", "status": "queued", "result": None, "error": None}


def test_list_audits_summarizes_verdict_counts(client):
    client._JOBS["job-1"] = {
        "job_id": "job-1",
        "status": "completed",
        "document": "contract.txt",
        "file_path": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "error": None,
        "items": [done_item("PASSED"), done_item("FAILED"), queued_item()],
    }

    with TestClient(client.app) as http:
        response = http.get("/audits")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    summary = body[0]
    assert summary["job_id"] == "job-1"
    assert summary["item_count"] == 3
    assert summary["done_count"] == 2
    assert summary["verdict_counts"] == {"PASSED": 1, "FAILED": 1, "CONTRADICTORY": 0, "NOT_FOUND": 0}


def test_list_audits_sorts_most_recent_first(client):
    client._JOBS["older"] = {
        "job_id": "older", "status": "completed", "document": "a.txt", "file_path": None,
        "created_at": "2026-01-01T00:00:00+00:00", "error": None, "items": [],
    }
    client._JOBS["newer"] = {
        "job_id": "newer", "status": "completed", "document": "b.txt", "file_path": None,
        "created_at": "2026-06-01T00:00:00+00:00", "error": None, "items": [],
    }

    with TestClient(client.app) as http:
        response = http.get("/audits")

    job_ids = [row["job_id"] for row in response.json()]
    assert job_ids == ["newer", "older"]


def test_delete_audit_removes_job_and_uploaded_file(client, tmp_path):
    job_dir = tmp_path / "uploads" / "job-1"
    job_dir.mkdir(parents=True)
    file_path = job_dir / "contract.txt"
    file_path.write_text("hello")

    client._JOBS["job-1"] = {
        "job_id": "job-1", "status": "completed", "document": "contract.txt",
        "file_path": str(file_path), "created_at": "2026-01-01T00:00:00+00:00",
        "error": None, "items": [done_item("PASSED")],
    }

    with TestClient(client.app) as http:
        response = http.delete("/audits/job-1")

    assert response.status_code == 204
    assert "job-1" not in client._JOBS
    assert not job_dir.exists()

    # Persisted deletion, not just removed from the in-memory cache.
    import src.store as store
    assert "job-1" not in store.load_all_jobs()


def test_delete_audit_refuses_a_running_job(client):
    client._JOBS["job-1"] = {
        "job_id": "job-1", "status": "processing", "document": "contract.txt",
        "file_path": None, "created_at": "2026-01-01T00:00:00+00:00",
        "error": None, "items": [queued_item()],
    }

    with TestClient(client.app) as http:
        response = http.delete("/audits/job-1")

    assert response.status_code == 409
    assert "job-1" in client._JOBS


def test_delete_audit_404s_for_unknown_job(client):
    with TestClient(client.app) as http:
        response = http.delete("/audits/does-not-exist")

    assert response.status_code == 404


def test_list_audits_requires_api_key_when_configured(monkeypatch, tmp_path):
    monkeypatch.setenv("JOBS_DB_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.setenv("API_KEY", "secret123")

    import src.store as store
    importlib.reload(store)
    import api
    importlib.reload(api)

    with TestClient(api.app) as http:
        unauthenticated = http.get("/audits")
        authenticated = http.get("/audits", headers={"X-API-Key": "secret123"})

    assert unauthenticated.status_code == 401
    assert authenticated.status_code == 200
