import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createAudit, getTemplates } from "../lib/api.ts";
import type { AuditRunOptions, ChecklistTemplate, ResultsLocationState } from "../lib/types";

const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".txt"];
const CUSTOM_KEY = "__custom__";

function extensionOf(filename: string): string {
  const idx = filename.lastIndexOf(".");
  return idx === -1 ? "" : filename.slice(idx).toLowerCase();
}

export default function UploadPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const [templates, setTemplates] = useState<ChecklistTemplate[]>([]);
  const [templatesError, setTemplatesError] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [checklistText, setChecklistText] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    getTemplates()
      .then((list) => {
        setTemplates(list);
        const general = list.find((t) => t.key === "general_contract");
        setSelectedKey((general || list[0])?.key ?? CUSTOM_KEY);
      })
      .catch((err: Error) => setTemplatesError(err.message));
  }, []);

  function handleFileChosen(chosenFile: File | null | undefined) {
    setError(null);
    if (!chosenFile) return;
    const ext = extensionOf(chosenFile.name);
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      setError(`Unsupported file type '${ext}'. Supported: ${ACCEPTED_EXTENSIONS.join(", ")}`);
      return;
    }
    setFile(chosenFile);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!file) {
      setError("Choose a document first.");
      return;
    }

    let auditOptions: AuditRunOptions;
    if (selectedKey === CUSTOM_KEY) {
      const checklistItems = checklistText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
      if (checklistItems.length === 0) {
        setError("Enter at least one checklist question, or pick a template instead.");
        return;
      }
      auditOptions = { checklistItems };
    } else {
      auditOptions = { templateKey: selectedKey ?? undefined };
    }

    setSubmitting(true);
    setError(null);
    try {
      const { job_id } = await createAudit(file, auditOptions);
      const locationState: ResultsLocationState = { file, auditOptions };
      navigate(`/audits/${job_id}`, { state: locationState });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  }

  const selectedTemplate = templates.find((t) => t.key === selectedKey);

  return (
    <div className="page">
      <Link to="/dashboard" className="back-link">&larr; Dashboard</Link>
      <h1>New Audit</h1>
      <p className="subtitle">
        Upload a contract or policy document and get a citation-backed compliance audit.
      </p>

      <form onSubmit={handleSubmit} className="upload-form">
        <label
          className={`dropzone ${dragActive ? "dropzone-active" : ""} ${file ? "dropzone-has-file" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragActive(false);
            handleFileChosen(e.dataTransfer.files?.[0]);
          }}
        >
          <input
            type="file"
            accept={ACCEPTED_EXTENSIONS.join(",")}
            onChange={(e) => handleFileChosen(e.target.files?.[0])}
            hidden
          />
          {file ? (
            <span>{file.name}</span>
          ) : (
            <span>Drop a .pdf, .docx, or .txt file here, or click to choose one</span>
          )}
        </label>

        <span className="field-label">Checklist</span>

        {templatesError && (
          <div className="form-error">Couldn't load templates: {templatesError}</div>
        )}

        <div className="template-picker">
          {templates.map((t) => (
            <label
              key={t.key}
              className={`template-option ${selectedKey === t.key ? "template-option-selected" : ""}`}
            >
              <input
                type="radio"
                name="template"
                value={t.key}
                checked={selectedKey === t.key}
                onChange={() => setSelectedKey(t.key)}
                hidden
              />
              <span className="template-option-name">{t.name}</span>
              <span className="template-option-count">{t.items.length} checks</span>
            </label>
          ))}
          <label
            className={`template-option ${selectedKey === CUSTOM_KEY ? "template-option-selected" : ""}`}
          >
            <input
              type="radio"
              name="template"
              value={CUSTOM_KEY}
              checked={selectedKey === CUSTOM_KEY}
              onChange={() => setSelectedKey(CUSTOM_KEY)}
              hidden
            />
            <span className="template-option-name">Custom</span>
          </label>
        </div>

        {selectedKey === CUSTOM_KEY ? (
          <textarea
            id="checklist"
            rows={5}
            placeholder="Identify the governing law state and verify if conflicts exist.&#10;Check if there is an explicit limitation of liability cap."
            value={checklistText}
            onChange={(e) => setChecklistText(e.target.value)}
          />
        ) : (
          selectedTemplate && (
            <ul className="template-preview">
              {selectedTemplate.items.map((item) => (
                <li key={item.id}>{item.label}</li>
              ))}
            </ul>
          )
        )}

        {error && <div className="form-error">{error}</div>}

        <button type="submit" disabled={submitting}>
          {submitting ? "Starting audit…" : "Run audit"}
        </button>
      </form>
    </div>
  );
}
