# api.py
"""
First-pass HTTP API for the AI Document Auditor.

Wraps the existing ingestion + engine pipeline behind:
  GET  /audits              list every job, most recent first (lightweight summaries)
  POST /audits              upload a document (+ optional template or custom checklist), starts a job
  GET  /audits/{id}         poll job status; includes per-item results as they land
  DELETE /audits/{id}       delete a finished job's record and uploaded file
  GET  /audits/{id}/document  serve the originally uploaded file back (Tier 0 document viewer)
  GET  /templates           list available checklist templates (id/label/question per item)
  GET  /health               liveness check

Known scope limits (fine for a first API layer, not for production):
  - Jobs are persisted to a local SQLite file (src/store.py, ./jobs.db by
    default) so they survive a restart -- but a job that was still
    `queued`/`processing` when the process died is marked `failed` on the
    next startup rather than resumed (see reconcile_interrupted_jobs). This
    still isn't shared across worker processes -- run with a single uvicorn
    worker for now.
  - Auth is a single shared API key (src/auth.py), not user accounts -- see
    that module's docstring.
  - Item progress only distinguishes queued -> done/error (no "running" state),
    since MAX_CONCURRENT_AUDITS throttles how many run at once and this layer
    doesn't yet track exactly which ones are mid-flight.
  - Uploaded files are written to ./uploads/{job_id}/ and never cleaned up.
"""
import asyncio
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.auth import require_api_key
from src.engine import run_parallel_due_diligence_with_progress
from src.ingestion import SUPPORTED_EXTENSIONS, create_hybrid_retriever, load_document
from src.schemas import DueDiligenceReport
from src import store
from src.templates import DEFAULT_TEMPLATE_KEY, TEMPLATES, ChecklistItem

load_dotenv()
if not os.environ.get("GOOGLE_API_KEY") and os.environ.get("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

app = FastAPI(title="AI Document Auditor API")

# CORS_ORIGINS: a comma-separated allowlist, e.g.
# "https://my-frontend.onrender.com,https://my-custom-domain.com". Defaults
# to the Vite dev server's own origins so local dev needs no setup -- set
# this explicitly in any real deployment, since the deployed frontend's
# origin is never localhost.
_default_origins = "http://localhost:5173,http://127.0.0.1:5173"
_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# UPLOAD_DIR: override to put uploads under a mounted persistent-disk path in
# production (e.g. "/app/data/uploads" on Render) -- see Dockerfile.
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "uploads"))
TERMINAL_STATUSES = {"completed", "failed"}

# Jobs live in SQLite (src/store.py), loaded into memory as a working cache
# and written back through on every state change -- see module docstring.
_JOBS: dict = store.load_all_jobs()
store.reconcile_interrupted_jobs(_JOBS)


def _resolve_checklist(template: Optional[str], checklist: Optional[str]) -> List[ChecklistItem]:
    """
    Resolves the request's checklist source into a List[ChecklistItem]:
      - `template`: a key into TEMPLATES, resolved server-side.
      - `checklist`: a JSON array of custom question strings, each wrapped into a
        ChecklistItem with a generated id (no separate short label exists for
        freely-typed questions, so label falls back to the question itself).
      - neither: falls back to TEMPLATES[DEFAULT_TEMPLATE_KEY].
    Providing both is rejected as ambiguous rather than silently preferring one.
    """
    if template and checklist:
        raise HTTPException(status_code=400, detail="Provide either 'template' or 'checklist', not both")

    if template:
        matched = TEMPLATES.get(template)
        if matched is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown template '{template}'. Available: {', '.join(sorted(TEMPLATES))}"
            )
        return matched.items

    if checklist:
        try:
            raw_items = json.loads(checklist)
            if not isinstance(raw_items, list) or not all(isinstance(i, str) for i in raw_items):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(status_code=400, detail="checklist must be a JSON array of strings")
        return [
            ChecklistItem(id=f"custom-{i}", label=question, question=question)
            for i, question in enumerate(raw_items)
        ]

    return TEMPLATES[DEFAULT_TEMPLATE_KEY].items


def _new_job(document_name: str, checklist_items: List[ChecklistItem]) -> dict:
    return {
        "job_id": str(uuid.uuid4()),
        "status": "queued",  # queued -> processing -> completed | failed
        "document": document_name,
        "file_path": None,  # set once the upload is written to disk, see create_audit
        "created_at": datetime.now(timezone.utc).isoformat(),
        "error": None,
        "items": [
            {
                "id": item.id,
                "label": item.label,
                "checklist_item": item.question,
                "status": "queued",
                "result": None,
                "error": None,
            }
            for item in checklist_items
        ],
    }


async def _run_job(job_id: str, file_path: Path):
    job = _JOBS[job_id]
    job["status"] = "processing"
    store.save_job(job)

    try:
        raw_docs = load_document(str(file_path))
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        documents = text_splitter.split_documents(raw_docs)
        retriever = create_hybrid_retriever(documents)

        checklist = [item["checklist_item"] for item in job["items"]]

        def on_item_done(index, checklist_item, result, error):
            entry = job["items"][index]
            if error is not None:
                entry["status"] = "error"
                entry["error"] = str(error)
            else:
                entry["status"] = "done"
                entry["result"] = result.model_dump()
            store.save_job(job)

        await run_parallel_due_diligence_with_progress(checklist, retriever, on_item_done=on_item_done)
        job["status"] = "completed"
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)
    finally:
        store.save_job(job)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/templates", dependencies=[Depends(require_api_key)])
def list_templates():
    return [t.model_dump() for t in TEMPLATES.values()]


@app.get("/audits", dependencies=[Depends(require_api_key)])
def list_audits():
    """
    Lists every known job, most recent first -- powers the dashboard's
    "Recent Audits" view. Deliberately lightweight: full per-item results
    stay behind GET /audits/{id} (fetched only once a specific job is
    opened); this just returns enough to render a row -- status, and a
    verdict breakdown for whatever items have finished so far.
    """
    summaries = []
    for job in _JOBS.values():
        verdict_counts = {"PASSED": 0, "FAILED": 0, "CONTRADICTORY": 0, "NOT_FOUND": 0}
        done_count = 0
        for item in job["items"]:
            if item["status"] == "done" and item["result"]:
                done_count += 1
                verdict = item["result"].get("verdict")
                if verdict in verdict_counts:
                    verdict_counts[verdict] += 1
        summaries.append({
            "job_id": job["job_id"],
            "document": job["document"],
            "status": job["status"],
            "created_at": job["created_at"],
            "error": job["error"],
            "item_count": len(job["items"]),
            "done_count": done_count,
            "verdict_counts": verdict_counts,
        })
    summaries.sort(key=lambda s: s["created_at"], reverse=True)
    return summaries


@app.post("/audits", status_code=202, dependencies=[Depends(require_api_key)])
async def create_audit(
    file: UploadFile = File(...),
    template: Optional[str] = Form(None),
    checklist: Optional[str] = Form(None),
):
    extension = Path(file.filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{extension}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    checklist_items = _resolve_checklist(template, checklist)

    job = _new_job(file.filename, checklist_items)
    job_dir = UPLOAD_DIR / job["job_id"]
    job_dir.mkdir(parents=True, exist_ok=True)
    file_path = job_dir / file.filename
    file_path.write_bytes(await file.read())
    job["file_path"] = str(file_path)

    _JOBS[job["job_id"]] = job
    store.save_job(job)

    asyncio.create_task(_run_job(job["job_id"], file_path))

    return {"job_id": job["job_id"], "status": job["status"]}


@app.get("/audits/{job_id}", dependencies=[Depends(require_api_key)])
def get_audit(job_id: str):
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No audit job with that id")

    response = {
        "job_id": job["job_id"],
        "status": job["status"],
        "document": job["document"],
        "created_at": job["created_at"],
        "error": job["error"],
        "items": job["items"],
    }

    if job["status"] == "completed":
        results = [item["result"] for item in job["items"] if item["result"] is not None]
        response["report"] = DueDiligenceReport(checklist_results=results).model_dump()

    return JSONResponse(response)


@app.delete("/audits/{job_id}", status_code=204, dependencies=[Depends(require_api_key)])
def delete_audit(job_id: str):
    """
    Permanently deletes a finished job's record and its uploaded file.

    Refuses to delete a job that's still `queued`/`processing` (409) rather
    than allowing it: the background asyncio task running it (see _run_job)
    holds its own reference to this exact job dict and will keep calling
    store.save_job on it as items complete, regardless of what api.py does
    to _JOBS -- deleting mid-flight would just have the job silently
    reappear in SQLite the next time an item finishes.
    """
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No audit job with that id")
    if job["status"] not in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="Can't delete an audit that's still running")

    file_path = job.get("file_path")
    if file_path:
        shutil.rmtree(Path(file_path).parent, ignore_errors=True)

    del _JOBS[job_id]
    store.delete_job(job_id)


@app.get("/audits/{job_id}/document", dependencies=[Depends(require_api_key)])
def get_audit_document(job_id: str):
    """
    Serves the originally uploaded file back, so the frontend can offer a "view
    source document" link (Tier 0 of the document-viewer roadmap item: no citation
    highlighting -- see ARCHITECTURE.md -- just the ability to open the real file
    and, for PDFs, jump straight to the page a citation came from via the
    browser's native viewer and a `#page=N` URL fragment).

    This is the one endpoint where require_api_key's query-param fallback
    actually matters: it's opened directly as an <iframe src="..."> / browser
    URL by the frontend, which can't attach a custom header -- see
    src/auth.py's docstring.
    """
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No audit job with that id")

    file_path = job.get("file_path")
    if not file_path or not Path(file_path).is_file():
        raise HTTPException(status_code=404, detail="The uploaded file is no longer available")

    # content_disposition_type defaults to "attachment" in Starlette's
    # FileResponse, which makes the browser download the file instead of
    # rendering it -- confirmed directly as the cause of "View Document"
    # downloading a PDF instead of opening it. "inline" is what actually
    # lets the browser's native PDF viewer render it in place.
    return FileResponse(file_path, filename=job["document"], content_disposition_type="inline")
