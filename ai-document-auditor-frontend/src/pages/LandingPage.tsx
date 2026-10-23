import { Link } from "react-router-dom";

const PIPELINE_STEPS = [
  { label: "Hybrid retrieval", detail: "BM25 keyword search + local dense vector search, combined" },
  { label: "Structured generation", detail: "Gemini forced through a strict schema requiring real citations" },
  { label: "Adversarial guardrail", detail: "A separate model call checks the result against the raw source text" },
  { label: "Retry with critique", detail: "A hallucination or unverifiable citation triggers a corrected retry" },
];

const FEATURES = [
  {
    title: "Citation-backed, not just confident",
    body: "Every finding requires an exact verbatim quote mapped to a real page number -- a paraphrase isn't accepted as evidence.",
  },
  {
    title: "Contradiction detection",
    body: "Checks a document against itself, not just against a checklist -- catches conflicting clauses a single-pass read misses.",
  },
  {
    title: "Multi-format ingestion",
    body: ".pdf, .docx, and .txt, with page-accurate citations wherever the format allows it.",
  },
  {
    title: "Four checklist templates",
    body: "General contract, M&A, financial report, and employment -- or write a fully custom checklist per run.",
  },
];

const STACK = [
  "React", "TypeScript", "FastAPI", "LangChain", "Gemini", "Chroma", "SQLite",
];

export default function LandingPage() {
  return (
    <div className="landing">
      <header className="landing-hero">
        <div className="landing-hero-inner landing-hero-split">
          <div className="landing-hero-text">
            <span className="landing-brand-mark" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path
                  d="M6 3.5h9l4.5 4.5v12.5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1Z"
                  stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"
                />
                <path d="M15 3.5V8h4.5" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
                <path d="M8.5 13.5l2.4 2.4 4.6-4.9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>

            <h1>AI Document Auditor</h1>
            <p className="landing-hook">
              AI that argues with itself before it tells you anything.
            </p>
            <p className="landing-tagline">
              Turns a contract, policy, or financial document into a
              citation-backed compliance audit. Every finding has to survive a
              second, adversarial model pass before it ships -- an unverified
              claim gets retried, not reported.
            </p>

            <Link to="/dashboard" className="landing-cta">
              Open Dashboard
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </Link>

            <div className="landing-stack">
              {STACK.map((s) => (
                <span key={s} className="landing-stack-chip">{s}</span>
              ))}
            </div>
          </div>
          <div className="landing-hero-visual" aria-hidden="true">
            <div className="landing-mock-card">
              <div className="landing-mock-card-header">
                <span className="landing-mock-doc">employment_contract.pdf</span>
                <span className="landing-mock-score">76%</span>
              </div>

              <div className="landing-mock-item">
                <div className="landing-mock-item-top">
                  <span className="badge badge-contradictory">Contradictory</span>
                  <span className="landing-mock-item-label">Governing law specified</span>
                </div>
                <div className="landing-mock-citation">
                  <span className="landing-mock-citation-page">Page 2</span>
                  "...governed exclusively by the laws of the State of New York."
                </div>
                <div className="landing-mock-citation">
                  <span className="landing-mock-citation-page">Page 5</span>
                  "...governed exclusively by the laws of the United Kingdom."
                </div>
              </div>

              <div className="landing-mock-item">
                <div className="landing-mock-item-top">
                  <span className="badge badge-passed">Passed</span>
                  <span className="landing-mock-item-label">Liability cap specified</span>
                </div>
                <div className="landing-mock-citation">
                  <span className="landing-mock-citation-page">Page 4</span>
                  "...liability shall not exceed $50,000 in aggregate."
                </div>
              </div>

              <div className="landing-mock-item landing-mock-item-muted">
                <div className="landing-mock-item-top">
                  <span className="badge badge-not-found">Not found</span>
                  <span className="landing-mock-item-label">Non-compete clause</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      <section className="landing-section">
        <h2>Four layers between a claim and the audit log</h2>
        <div className="landing-pipeline">
          {PIPELINE_STEPS.map((step, i) => (
            <div key={step.label} className="landing-pipeline-step">
              <span className="landing-pipeline-num">{i + 1}</span>
              <div>
                <div className="landing-pipeline-label">{step.label}</div>
                <div className="landing-pipeline-detail">{step.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="landing-section">
        <h2>What it actually checks for</h2>
        <div className="landing-feature-grid">
          {FEATURES.map((f) => (
            <div key={f.title} className="landing-feature-card">
              <h3>{f.title}</h3>
              <p>{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="landing-footer">
        <Link to="/dashboard" className="landing-cta landing-cta-secondary">
          Open Dashboard
        </Link>
      </footer>
    </div>
  );
}
