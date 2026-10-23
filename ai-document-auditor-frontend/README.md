# AI Document Auditor — Frontend

A React + TypeScript + Vite single-page app for the AI Document Auditor.
Upload a contract or policy document, pick a checklist template (or write a
custom one), and watch a citation-backed compliance audit come back per item
as it completes.

This is a separate project from the backend (`ai-document-auditor`, a
sibling repo) — there's no shared codebase or build step between them.
Types for the API's response shapes live in `src/lib/types.ts`,
hand-mirrored from that repo's `src/schemas.py` and `src/templates.py` —
there's no shared/generated schema, so if a backend field changes shape,
update `types.ts` to match by hand.

This talks to the FastAPI backend in the `ai-document-auditor` repo's
`api.py` — see that repo's `ARCHITECTURE.md` for how the two fit together
and how the whole pipeline works end to end.

## Running it

The backend must be running first (from the repo root, with its own venv activated):

```bash
uvicorn api:app --reload
```

Then, from this directory:

```bash
npm install
npm run dev
```

Open `http://localhost:5173`. The dev server is hardcoded to call the API at
`http://localhost:8000` (see `src/lib/api.ts`) — no env var or proxy config
needed for local development.

**If the backend has `API_KEY` set** (its minimal shared-secret auth — see
that repo's `src/auth.py`), copy `.env.example` to `.env.local` and set
`VITE_API_KEY` to the same value; `api.ts` sends it back as an `X-API-Key`
header on every request, and as a `?api_key=` query param on the one
endpoint that's opened as a plain URL (the document viewer, which can't
attach a custom header). Leave it unset when the backend has no `API_KEY`
either — that's the local-dev default on both sides.

To type-check without running a dev server: `npm run typecheck`. `npm run
build` type-checks (`tsc -b`) before bundling, so a type error fails the
build rather than shipping silently.

## How it works

**Landing page** (`src/pages/LandingPage.tsx`, route `/`)
Standalone, no sidebar — a first-time visitor's entry point (e.g. a CV/
portfolio link), not a working view of the app. Explains what the project
is and why (the anti-hallucination pipeline, in brief) with a single CTA
into the actual app at `/dashboard`.

**App shell** (`src/components/AppShell.tsx`)
Every *other* route renders inside a persistent sidebar + content layout
(see `main.tsx`'s route tree) — a dashboard shell with two nav
destinations, matching the app's two things to navigate to. Print/PDF
export hides the sidebar via `@media print` and collapses back to a single
full-width column (see `index.css`).

**Dashboard page** (`src/pages/DashboardPage.tsx`, route `/dashboard`)
Lists every audit that's been run, most recent first, via `GET /audits`
(`listAudits()` in `api.ts`) — a lightweight per-job summary (status, a
verdict-count breakdown, timestamps), not the full per-item results, which
stay behind `GET /audits/:jobId` until a specific job is opened. Polls every
4 seconds only while something is still `queued`/`processing`; an idle
dashboard doesn't keep hitting the API. Each card's status label/color
(`overallStatus` in `lib/format.ts`) collapses a job's own status plus its
verdict counts into one glance-able read: "In progress", "All clear",
"Needs attention" (a `FAILED` item), or "Contradictions found" (worse than a
plain failure — see `scoring.ts`'s severity ordering on the results page for
the same judgment call).

**Upload page** (`src/pages/UploadPage.tsx`, route `/new`)
Drag-and-drop or click to choose a `.pdf`, `.docx`, or `.txt` file. Pick one
of the checklist templates fetched from `GET /templates`, or switch to
"Custom" to type your own questions (one per line). Submitting calls
`POST /audits` and navigates to `/audits/:jobId`.

**Results page** (`src/pages/ResultsPage.tsx`)
Polls `GET /audits/:jobId` every 2 seconds until the job reaches a terminal
status (`completed` or `failed`). Audits aren't instant and items complete
out of order (throttled concurrency on the backend), so this is a real
polling loop, not a single fetch-and-render — each checklist item renders
independently based on its own `status` (`queued` / `done` / `error`).

**Checklist item card** (`src/components/ChecklistItemCard.tsx`, rows in
`src/components/checklist-item/`)
Renders a template item's short `label` as the heading and its full
`question` as secondary text (suppressed when they're the same, which
happens for custom/free-typed checklist items with no separate label).
A `done` item shows its verdict badge, summary statement, an expandable list
of verbatim citations paired with page numbers, and a contradiction callout
when one was detected. An `error` item shows a plain-language message
(`src/lib/errors.ts` maps the raw backend error into one) with the raw
detail behind a "technical details" toggle — this is a real, observed
failure mode (not just a designed-for one): the guardrail retry loop
exhausting its 3 attempts on one item renders as an isolated error card
without taking down the rest of the results.

**Health score & risk summary** (`src/components/HealthScoreCard.tsx`,
`RiskSummaryCard.tsx`, `src/lib/scoring.ts`)
Computed client-side from the job's items — no extra backend call.
`NOT_FOUND` items are deliberately excluded from the score rather than
counted as failures (folding them in would make a document look like it's
failing an audit just because a checklist template doesn't match its type —
we saw this directly running the M&A template against a non-M&A contract).
The risk summary lists `CONTRADICTORY`/`FAILED` items, ranked by severity,
and clicking one scrolls to its card (via `scrollIntoView`, not a plain
`<a href="#...">` — that was tried first and confirmed to silently wipe
react-router's navigation state, which "Re-run Audit" depends on).

**Document viewer** (`src/components/DocumentViewerModal.tsx`)
`GET /audits/:jobId/document` serves the original upload back
(`content_disposition_type="inline"` server-side — the Starlette default is
`"attachment"`, which downloads instead of rendering; hit directly, fixed).
For PDFs, clicking "View Document" or any citation's page number opens an
in-page modal with an `<iframe>` jumped to that page via the browser's
native PDF viewer and a `#page=N` fragment — no citation highlighting yet,
see the backend repo's `ARCHITECTURE.md` for why that's a bigger project.
Non-PDF files fall back to a plain download link.

**PDF export** (`window.print()` + the `@media print` rules in `index.css`)
No new dependency, no server round-trip — reuses the same styling as the
screen view. The one non-obvious piece: citations are collapsed by default
on screen via a CSS class (`citation-list-collapsed`), not by conditionally
unmounting them — they used to be conditionally rendered, which meant a
printed PDF would silently omit every citation the user hadn't manually
expanded. Print CSS forces that class visible regardless of on-screen state.

## Project structure

```text
frontend/
├── src/
│   ├── lib/
│   │   ├── api.ts                    # apiFetch + thin wrappers: getTemplates, createAudit, listAudits, getAudit, deleteAudit, getDocumentUrl
│   │   ├── types.ts                  # API response types, mirrored from the backend's pydantic schemas
│   │   ├── scoring.ts                # health score + risk-item ranking, computed client-side
│   │   ├── format.ts                 # relative timestamps + a job summary's glance-able overall status
│   │   ├── exportReport.ts           # Markdown report builder + download trigger
│   │   └── errors.ts                 # raw backend error string -> plain-language message
│   ├── pages/
│   │   ├── LandingPage.tsx           # standalone "/" entry point, no sidebar
│   │   ├── DashboardPage.tsx         # "/dashboard" -- lists every audit via GET /audits
│   │   ├── UploadPage.tsx            # "/new" -- file picker + template selector, POSTs /audits
│   │   └── ResultsPage.tsx           # "/audits/:jobId" -- polls the job, renders the checklist + action bar
│   ├── components/
│   │   ├── AppShell.tsx              # sidebar + content outlet, wraps every route except "/"
│   │   ├── ChecklistItemCard.tsx     # dispatches to the row for an item's status
│   │   ├── checklist-item/           # QueuedRow / ErrorRow / DoneRow / SubQuestion
│   │   ├── VerdictBadge.tsx          # PASSED / FAILED / CONTRADICTORY / NOT_FOUND badge
│   │   ├── HealthScoreCard.tsx
│   │   ├── RiskSummaryCard.tsx
│   │   └── DocumentViewerModal.tsx   # in-page PDF viewer, jumps to a citation's page
│   ├── main.tsx                      # router: "/", "/dashboard", "/new", "/audits/:jobId"
│   ├── vite-env.d.ts                 # Vite's ambient types (asset imports, import.meta.env)
│   └── index.css                     # includes the @media print rules for PDF export
├── tsconfig.json
├── index.html
└── package.json
```

## Known limits (first pass, not production-hardened)

- **No retry-a-single-item UI.** The backend already tracks each item's
  `id` and an independent `error` state specifically so this can be added
  without restructuring anything — it's just not wired up in the UI yet.
- **No citation highlighting in the document viewer.** It jumps to the right
  page; it doesn't highlight where on that page the cited text is. That
  needs page-layout coordinates the backend's PDF extraction doesn't capture
  today — see the backend repo's `ARCHITECTURE.md` for the known limitations.
- **Polling has no backoff.** A slow or rate-limited backend gets hit every
  2 seconds regardless; fine for local dev, not ideal under real load.
- **CORS is dev-only.** The backend's `CORSMiddleware` explicitly allows
  `localhost:5173` / `127.0.0.1:5173` — update that allowlist (and this
  app's `API_BASE`) before deploying either side anywhere else.
