# Architecture

This covers the system as it actually exists today: a React frontend, a
FastAPI job-based API, and the ingestion/audit pipeline underneath it. If
you're looking for the original single-script demo, that's still there —
`main.py` runs the same pipeline directly against a local file, no API or
frontend required (`python main.py [document] [--template KEY]`).

The frontend is a separate repository (`ai-document-auditor-frontend/`, a
sibling to this one) — deployed independently of the API (a static host,
not this project's `Dockerfile`), described here only for how it fits into
the overall request flow.

## System diagram

```
┌───────────────────────────────────────────────────────────────────────┐
│  FRONTEND  (React + Vite -- separate repo: ai-document-auditor-frontend)│
│                                                                          │
│   DashboardPage.tsx  ──polls GET /audits──▶      UploadPage.tsx         │
│   lists every job, most recent first              ──POST /audits──▶     │
│                                                    ResultsPage.tsx       │
│                                                    polls GET /audits/:id │
│                                                    every 2s until done   │
└──────────────────────────┬──────────────────────────────┬──────────────┘
                            │                              ▲
                            ▼                              │
┌───────────────────────────────────────────────────────────────────────┐
│  API  (FastAPI -- api.py)                                               │
│                                                                          │
│   GET  /audits       every job, most recent first -- status + a         │
│                       verdict-count breakdown per job, not full items   │
│                       (that's GET /audits/{id}, once a job is opened)   │
│   POST /audits       resolve template/checklist → ChecklistItem[],      │
│                       save the upload, start the job as a background    │
│                       asyncio task, return {job_id, status} immediately │
│   GET  /audits/{id}  current job status + each item's own status/result │
│                       as it lands, plus the aggregated report once done │
│   DELETE /audits/{id}  delete a finished job's record + uploaded file -- │
│                       409 if it's still queued/processing (see below)   │
│   GET  /audits/{id}/document  the raw uploaded file, served back as-is  │
│   GET  /templates    lists src/templates.py's ChecklistTemplates        │
│                                                                          │
│   Every route but /health requires src/auth.py's shared API key         │
│   (X-API-Key header, or ?api_key= for the document endpoint's           │
│   header-less <iframe src>). Unset API_KEY disables auth for local dev. │
│                                                                          │
│   Job store: {status, items: [{id, label, checklist_item, status,       │
│   result, error}], report} per job, held in memory and written through  │
│   to a local SQLite file (src/store.py) on every change -- survives a   │
│   restart; see "Known limitations" below for what it still doesn't do.  │
└──────────────────────────┬──────────────────────────────────────────────┘
                            │ per job: file path + resolved question list
                            ▼
┌───────────────────────────────────────────────────────────────────────┐
│  INGESTION  (src/ingestion.py)                                          │
│                                                                          │
│   load_document(path)  dispatches by extension:                         │
│     .pdf   pypdf -- one Document per real page (accurate, free)         │
│     .docx  python-docx -- pages only from explicit manual page breaks;  │
│            Word has no fixed pagination otherwise, so an unmarked file  │
│            returns one unpaginated chunk rather than guessing           │
│     .txt   a "[PAGE N]" marker convention; unmarked files also fall     │
│            back to one unpaginated chunk                                │
│                            │                                            │
│                            ▼                                            │
│   RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100,     │
│     separators=["\n\n","\n",". "," ",""])                              │
│     -- overlap and the sentence separator exist because a real          │
│        contradiction was silently missed once: chunk_overlap=50 let a   │
│        single load-bearing clause split across a chunk boundary, and    │
│        the LLM never saw the half that mattered                         │
│                            │                                            │
│                            ▼                                            │
│   create_hybrid_retriever(documents, k=4)                               │
│     ┌───────────────────────┐        ┌────────────────────────────┐   │
│     │ BM25Retriever          │        │ Chroma + MiniLMEmbeddings   │   │
│     │ (sparse keyword, k=4)  │        │ (local sentence-transformers│   │
│     │                        │        │  /all-MiniLM-L6-v2, k=4 --  │   │
│     │                        │        │  no network/API dependency  │   │
│     │                        │        │  for ingestion at all)       │   │
│     └───────────┬────────────┘        └──────────────┬───────────────┘   │
│                 └──────────────┬───────────────────┘                   │
│                     EnsembleRetriever, weights [0.5, 0.5]                │
│     -- k defaults to 4, not 2: a too-narrow top-k can exclude the       │
│        chunk holding the operative half of a split clause, independent │
│        of the chunking fix above (confirmed both matter via testing)    │
└──────────────────────────┬──────────────────────────────────────────────┘
                            │ retriever, reused across all checklist items
                            ▼
┌───────────────────────────────────────────────────────────────────────┐
│  ENGINE  (src/engine.py) -- one pass per checklist item, throttled to  │
│  MAX_CONCURRENT_AUDITS=2 concurrent items via an asyncio.Semaphore      │
│  (the free-tier Gemini quota rejects bursts above that)                 │
│                                                                          │
│    ┌──────────────────────────────────────────────────────────────┐    │
│    │ LAYER 1  retrieve top-k chunks for this item's question,       │◀─┐│
│    │          ask Gemini (gemini-flash-lite-latest) for a           │  ││
│    │          structured AuditLog (verdict, statement, citations,   │  ││
│    │          page numbers, contradiction flag)                     │  ││
│    └──────────────────────────┬───────────────────────────────────┘  ││
│                                ▼                                       ││
│    ┌──────────────────────────────────────────────────────────────┐  ││
│    │ LAYER 2 & 3  guardrails.py -- a SEPARATE Gemini call checks     │  ││
│    │              the AuditLog against the raw source text for:     │  ││
│    │                is_hallucinated   (a fact not in the source)    │  ││
│    │                missing_evidence  (a citation not verbatim in   │  ││
│    │                                    the source)                 │  ││
│    └──────────────────────────┬───────────────────────────────────┘  ││
│                    hallucinated or missing evidence?                  ││
│                        │ yes                    │ no                  ││
│                        ▼                         └── AuditLog returned│
│    ┌──────────────────────────────┐                  to the API job   │
│    │ LAYER 4  feed the guardrail's │                                  │
│    │ critique back into the prompt,│──────────────────────────────────┘
│    │ retry (max 3 attempts)        │
│    └──────────────────────────────┘
│         exhausted 3 attempts → that item alone becomes an "error"
│         entry; the rest of the batch keeps running (see
│         run_parallel_due_diligence_with_progress)
└───────────────────────────────────────────────────────────────────────┘
```

## How verification actually works (and what it doesn't prove)

The four layers above exist to answer one question: "does this claim and
its citation genuinely exist in the text that was retrieved." That's a
real, meaningful check — it's caught real bugs during development, not
just a theoretical safeguard — but it's worth being precise about what it
does and doesn't guarantee, since the honest answer is more useful than
the reassuring one.

**What each layer actually checks:**

1. **Schema-forced evidence, not just a schema-forced answer.**
   `AuditLog.exact_quote_citations` (`src/schemas.py`) requires *verbatim*
   text snippets, not a paraphrase or summary. The model can't just assert
   a conclusion — it has to produce the literal sentence it's claiming that
   from.
2. **A second, independent model call checks the first one's work**
   (`src/guardrails.py`). It's not the same call grading itself — it's a
   fresh Gemini call given only the raw source text and the first model's
   claimed statement + citations, asked two specific questions:
   `is_hallucinated` (does the statement contain anything not explicitly in
   the source?) and `missing_evidence` (do the claimed citations exist
   word-for-word in the source?).
3. **A failure doesn't get silently accepted.** A guardrail flag feeds its
   critique back into the prompt for a corrected retry — up to 3 attempts,
   hard-capped (`max_retries=3`, enforced and regression-tested). Exhausting
   all 3 makes that item an explicit `error`, not a confident-looking wrong
   answer — see `run_parallel_due_diligence_with_progress`'s per-item error
   isolation.
4. **Contradiction detection** checks the document against *itself* across
   pages, not just each checklist question in isolation.

**What this does NOT verify:**

- **External truth.** This checks internal consistency — does the claim
  match the retrieved text — not whether the source document itself is
  accurate, current, or genuine. A confidently wrong source document
  produces a confidently-reported wrong (but internally consistent) audit.
  This system has no way to detect that, because that's not the question
  it's answering.
- **Nothing here is deterministic.** Every layer, including the "does this
  citation exist word-for-word" check, is an LLM judgment call — there is
  no programmatic string-matching anywhere verifying a citation against the
  source text in code. The guardrail reduces hallucination risk; it does
  not make it zero, and it can itself be wrong in either direction (a false
  reject costs an extra retry; a false accept lets something bad through).
  Neither failure mode is currently measured — see "Known limitations."
- **Retrieval quality is a precondition, not something these 4 layers
  check.** If the hybrid retriever never surfaces the relevant chunk, the
  generator correctly can't cite it (usually surfacing as `NOT_FOUND`,
  which is the system behaving correctly) — but if retrieval surfaces a
  *plausible but wrong* chunk, hallucination-layer defenses don't catch
  that; only retrieval quality (chunking, k, and — not yet built —
  reranking/an eval harness) would.

**What lets a human verify it, beyond trusting the pipeline:** every
citation carries a real page number, and the Tier 0 document viewer jumps
straight to that page so the primary source can be read directly — this is
deliberate: the product's own answer to "how do I know this is right" is
"don't just trust it, go look," not "trust the AI."

## Request lifecycle (a single audit, start to finish)

1. User picks a file and a checklist template (or types a custom one) in
   `UploadPage`, which `POST`s to `/audits` with an `X-API-Key` header (see
   "Auth" below).
2. `api.py` resolves the checklist source into a `List[ChecklistItem]`
   (`_resolve_checklist`), writes the upload to `uploads/{job_id}/`, creates
   a job record with every item in `queued` state, persists it via
   `store.save_job` (SQLite), and kicks off `_run_job` as a background
   `asyncio` task — the response returns immediately with just
   `{job_id, status: "queued"}`.
3. `_run_job` loads the document, chunks it, builds the hybrid retriever
   once, then runs every checklist item's question through
   `run_parallel_due_diligence_with_progress` — throttled to 2 at a time,
   reporting each item's outcome via a callback as soon as it lands rather
   than waiting for the whole batch. Every callback invocation and every
   status transition (`queued → processing → completed/failed`) calls
   `store.save_job` again, so a mid-audit crash never leaves the on-disk
   record more than one item behind the in-memory one.
4. `ResultsPage` polls `GET /audits/{job_id}` every 2 seconds. Each
   checklist item independently renders as `queued` → `done` (with its
   `AuditLog`) or `error` (with a message), regardless of what state its
   siblings are in.
5. Once every item has resolved, the job flips to `completed` and the
   response gains a `report` field — the full `DueDiligenceReport`, ready
   to display or export as-is.

## Persistence (src/store.py)

Jobs are held in an in-memory dict during a process's lifetime (unchanged —
that's still what every request reads and writes), but every creation and
every state change is written through to a local SQLite file (`jobs.db` by
default, `JOBS_DB_PATH` to override) as a single JSON blob per job. At
startup, `api.py` calls `store.load_all_jobs()` to repopulate that dict from
disk before serving any request.

This solves the actual problem — jobs surviving a restart — without adding
a database server to run and operate. It deliberately does **not** solve a
different, harder problem: resuming a job that was still `queued` or
`processing` when the process died. The `asyncio` task that was running it
is gone with the process; there's nothing to resume it from. Rather than
leave such a job stuck showing "processing" forever, `reconcile_interrupted_jobs`
runs once at startup and flips any job still in a non-terminal state to
`failed`, with an explicit `error` message asking the user to re-run it —
verified directly by killing a server mid-audit and confirming the restart
reconciles it correctly (see the test suite's `tests/test_store.py`).

This is single-file, single-process persistence: it's why the Dockerfile
stays pinned to one `uvicorn` worker and one replica, same constraint as
before, just moved from "the dict is in-process memory" to "SQLite doesn't
arbitrate concurrent writers across processes." Multiple replicas need a
real shared store (Postgres/Redis) instead, which is a materially bigger
change than swapping the persistence layer — see "Known limitations."

**Deletion (`DELETE /audits/{id}`) is refused for a `queued`/`processing`
job, not just as a caution.** `_run_job`'s background `asyncio` task closes
over the exact same job `dict` object stored in `_JOBS`, not a fresh lookup
of it, and keeps calling `store.save_job(job)` on it as each item finishes.
If a job were removed from `_JOBS` and SQLite while that task were still
running, the very next item to finish would write it straight back to
disk — a "deleted" job silently resurrecting on its own. Only jobs already
in a terminal state (`completed`/`failed`, where that task has already
exited) are actually safe to delete.

## Auth (src/auth.py)

A single shared API key, not user accounts — there is no login, no session,
no per-user data. `require_api_key` is a FastAPI dependency on every route
except `/health` (left open for the Docker `HEALTHCHECK` and any platform's
liveness probe, which don't carry credentials): it compares an `X-API-Key`
header (or an `?api_key=` query param, for the one endpoint that's opened as
a plain URL rather than fetched — the document viewer's `<iframe src>`,
which can't attach a custom header) against the `API_KEY` environment
variable. If `API_KEY` is unset, the dependency is a no-op and every request
is allowed — frictionless for local dev, but it means a real deployment that
forgets to set `API_KEY` is silently wide open.

Real per-user accounts (individual logins, per-user job ownership) would
need a `users` table and session/token handling on top of this — a
materially bigger step than "minimal," and treated as a separate later
decision rather than something this layer grows into by accident.

## Schemas (src/schemas.py, src/templates.py)

- **`AuditLog`** — one checklist item's result: `verdict`
  (`PASSED`/`FAILED`/`CONTRADICTORY`/`NOT_FOUND`), `raw_statement`,
  `exact_quote_citations` + `page_citations` (paired positionally),
  `contradiction_detected` + `contradiction_notes`. This is what the LLM
  fills out directly via structured output — it never sees a template's
  `id`/`label`, only the plain question string.
- **`GuardrailVerdict`** — the adversarial judge's output: `is_hallucinated`,
  `missing_evidence`, `critique_justification`.
- **`DueDiligenceReport`** — `{checklist_results: List[AuditLog]}`, the
  full-batch aggregate.
- **`ChecklistItem`** / **`ChecklistTemplate`** — orchestration-layer-only
  metadata (`id`, `label`, `question`), deliberately kept out of the
  LLM-facing schemas above. `api.py` is the only place that resolves a
  template down to plain question strings before handing them to the engine
  and re-attaches `id`/`label` to the results afterward.

## Known limitations

- **The guardrail's own accuracy is unmeasured.** Every verification layer
  (see "How verification actually works" above) is an LLM judgment call,
  not a deterministic check — there's no tracking of how often the
  guardrail itself is wrong in either direction (a false reject just costs
  an extra retry; a false accept lets a bad result through silently). There
  is also no retrieval-quality eval harness (precision/recall@k against a
  labeled set) and no reranking step after the hybrid retriever — both
  would be the highest-leverage next additions for measuring, rather than
  just asserting, how well the anti-hallucination pipeline actually works.
- **SQLite job store is single-process.** Jobs now survive a restart (see
  "Persistence" above), but the store still isn't shared across worker
  processes or replicas — run the API with a single `uvicorn` worker for
  now. A job that was mid-flight when the process died is marked `failed`
  on the next startup, not resumed.
- **Auth is one shared key, not accounts.** `API_KEY` gates the whole API as
  a single secret; there's no per-user identity, no way to revoke one
  caller without rotating the key for everyone, and unset `API_KEY` means
  no auth at all. Fine for a single person or a small trusted group, not for
  a public deployment.
- **No "running" item state.** Progress only distinguishes
  `queued → done/error`; the throttle means just 2 items are ever actually
  in flight, but the API doesn't currently track which 2.
- **Uploaded files are only cleaned up on explicit delete.** `DELETE
  /audits/{id}` removes a finished job's record and its `uploads/{job_id}/`
  directory, but nothing removes them automatically — a completed job that's
  never deleted keeps its file on disk indefinitely. No retention policy or
  auto-expiry exists yet.
- **Free-tier Gemini rate limits are real and have been hit directly**
  during development — `MAX_CONCURRENT_AUDITS=2` exists specifically
  because a burst of 4 concurrent items tripped a 429. Larger checklists
  (the M&A template has 12 items) take correspondingly longer to run
  sequentially through the throttle.
- **`.docx` page numbers are best-effort.** Word stores no fixed pagination
  without a render engine, so citations are only page-accurate for
  documents that used explicit manual page breaks.
- **Document viewer is Tier 0 only: no citation highlighting.** `GET
  /audits/{id}/document` serves the original file back with
  `content_disposition_type="inline"` (the Starlette default is
  `"attachment"`, which silently forces a download instead of letting the
  browser render it -- hit directly, fixed). For PDFs, clicking a citation's
  page number opens an in-page modal (`DocumentViewerModal.tsx`) with an
  `<iframe>` jumped to that page via the browser's native viewer and a
  `#page=N` fragment — but nothing highlights *where on the page* the cited
  text is. That needs bounding-box
  coordinates the ingestion layer doesn't extract today (`pypdf`'s
  `extract_text()` returns flat text, no layout data), and a client-side
  text-search alternative would inherit the same extraction fragility
  (broken mid-word line-wraps, whitespace mismatches) already seen
  elsewhere in this project. `.docx`/`.txt` have no equivalent viewer at
  all — they can only be downloaded via the same endpoint.
- **No retry-a-single-item endpoint yet**, though the `id`-per-item design
  throughout the API and job store exists specifically to make that
  addable later without restructuring anything.
