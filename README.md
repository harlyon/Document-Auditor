# AI Document Auditor

An asynchronous Retrieval-Augmented Generation (RAG) system that turns
unstructured legal, financial, and employment documents into citation-backed
compliance audits — via a CLI, an HTTP API, or a React frontend.

Unlike naive RAG pipelines that hallucinate freely and lose track of where a
claim came from, this system runs a **4-layer anti-hallucination pipeline**
(generate → adversarial verify → retry-with-critique) behind a **hybrid
BM25 + vector retriever**, and forces every result through a strict Pydantic
schema requiring exact verbatim citations mapped to real page numbers.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system diagram and how
the CLI, API, and frontend fit together. The React frontend is a separate
project — see `ai-document-auditor-frontend/README.md` there for its setup
and specifics; this repo is the CLI + API backend only.

## Core capabilities

* **Multi-format ingestion** — `.pdf` (native per-page accuracy via `pypdf`),
  `.docx` (page-aware where the source uses explicit manual page breaks),
  and `.txt` (a `[PAGE N]` marker convention, or plain text).
* **Layered anti-hallucination framework** — a self-correcting loop that
  runs every generated finding back through an adversarial judge before
  it's accepted, retrying with the judge's critique on failure.
* **Hybrid retrieval** — BM25 keyword matching combined with local dense
  vector search (`sentence-transformers/all-MiniLM-L6-v2` via Chroma — no
  network dependency or API quota consumed just to ingest a document).
* **Checklist templates** — General Contract, M&A Contract, Financial
  Report, and Employment Contract templates ship out of the box
  (`src/templates.py`), or write a fully custom checklist per run.
* **Page-level auditable citations** — every finding requires an exact
  verbatim quote mapped to a real page number, not a paraphrase.
* **Asynchronous concurrency** — checklist items run concurrently (throttled
  to stay within free-tier rate limits) via `asyncio`.
* **Three ways to run it** — a one-shot CLI script, an HTTP API with
  job polling for a real frontend, or the React app itself.
* **Audit history** — `GET /audits` lists every job that's been run, most
  recent first, powering the frontend's dashboard view.
* **Persistent job store** — audit jobs are written through to a local
  SQLite file (`src/store.py`) on every state change, so they survive an API
  restart instead of vanishing with an in-memory dict.
* **Minimal API-key auth** — every API route but `/health` requires a shared
  secret (`src/auth.py`, `API_KEY` env var), off by default for local dev.

---

## 📁 Repository Structure

```text
ai-document-auditor/
│
├── tests/
│   └── test_engine.py           # Guardrail retry loop, ingestion, page-citation tests
│
├── src/
│   ├── schemas.py                # Pydantic models: AuditLog, GuardrailVerdict, DueDiligenceReport
│   ├── templates.py              # Checklist templates (ChecklistItem / ChecklistTemplate)
│   ├── ingestion.py               # Multi-format loaders, chunking, hybrid BM25+MiniLM retriever
│   ├── guardrails.py             # Adversarial QA verification layer
│   ├── engine.py                 # Throttled concurrent audit loop with retry-on-failure
│   ├── store.py                  # SQLite-backed job persistence (jobs.db)
│   └── auth.py                   # Minimal shared-API-key auth dependency
│
├── data/                         # Sample documents for local testing
├── main.py                       # CLI entrypoint — runs the pipeline against a local file
├── api.py                        # FastAPI job-based API for the frontend
├── Dockerfile                    # Backend API image — see the file itself for deployment constraints
└── requirements.txt
```

The React frontend lives in its own sibling project,
`ai-document-auditor-frontend/` — not part of this repository, deployed
independently (a static host, not this Dockerfile). See that project's own
README for setup.

---

## 🛠️ Local Installation & Quickstart

### 1. Set Up Environment
Requires Python 3.10+.

```bash
git clone <this-repo>
cd ai-document-auditor
python -m venv .venv && source .venv/bin/activate   # or your preferred venv tool
pip install -r requirements.txt
```

### 2. Configure Your API Token
The audit and guardrail models use Gemini (embeddings run locally and need
no key). Get a key from [Google AI Studio](https://aistudio.google.com/apikey)
and put it in a `.env` file at the repo root:

```
GEMINI_API_KEY="your-actual-gemini-api-key-here"

# Optional: protects the HTTP API (src/auth.py) with a shared secret clients
# must send back as an `X-API-Key` header (or `?api_key=` for the document
# viewer). Only relevant if you're running api.py, not the CLI. Leave unset
# for local dev -- the API allows every request when API_KEY isn't set.
API_KEY="a-secret-you-choose"
```

### 3a. Run the CLI
```bash
python main.py                                    # prompts you for a document path
python main.py path/to/contract.pdf                # any .pdf / .docx / .txt
python main.py path/to/contract.pdf --template mna_contract
```
Running without a document path drops you into an interactive prompt (with a
sample contract at `data/contract.txt` if you just want to try it). In a
non-interactive context (CI, a script, piped input) it fails immediately
with a usage message instead of hanging.

### 3b. Run the API + Frontend
```bash
uvicorn api:app --reload
```
The frontend is a separate project (`ai-document-auditor-frontend/`, a
sibling directory to this repo) — see its own README for `npm install`/
`npm run dev`. It expects this API at `http://localhost:8000` by default.

### 4. Execute the Test Suite
```bash
pytest -v
```

---

## ☁️ Deploying

`render.yaml` at the repo root is a [Render Blueprint](https://render.com/docs/blueprint-spec)
provisioning both services: this API as a Docker web service (with a
persistent disk for `jobs.db` + `uploads/`), and the frontend as a static
site (with the rewrite rule client-side routing needs). Requires this repo
pushed to a GitHub/GitLab remote first — Render deploys from Git, not local
disk. See the comment at the top of `render.yaml` for the two-pass deploy
order (the two services need each other's URL, which can't be pre-wired).

Env vars the backend reads in production (all optional for local dev, all
documented inline in `api.py`/`src/auth.py`/`src/store.py`):
`GEMINI_API_KEY`, `API_KEY`, `CORS_ORIGINS`, `JOBS_DB_PATH`, `UPLOAD_DIR`.

Any other Docker-friendly host (Fly.io, Railway, Cloud Run, …) works too —
`render.yaml` is specific to Render, but the `Dockerfile` itself isn't tied
to it; it already respects `$PORT` rather than assuming 8000.

---

## 🏆 Sample Output

Every checklist item resolves to a strictly-typed `AuditLog`, aggregated
into a `DueDiligenceReport`:

```json
{
  "checklist_results": [
    {
      "verdict": "CONTRADICTORY",
      "checklist_item": "Identify the governing law state and verify if conflicts exist.",
      "raw_statement": "The document contains directly conflicting governing law designations.",
      "exact_quote_citations": [
        "shall be governed exclusively by... the laws of the State of New York",
        "shall be governed exclusively by the laws of the United Kingdom"
      ],
      "page_citations": [2, 5],
      "contradiction_detected": true,
      "contradiction_notes": "Page 2 designates New York law; Page 5's integration clause designates UK law instead."
    }
  ]
}
```
