import type { ChecklistTemplate, Job, JobSummary } from "./types";


const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) || "http://localhost:8000";


const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;

const AUTH_HEADERS: HeadersInit = API_KEY ? { "X-API-Key": API_KEY } : {};


async function apiFetch(path: string, init: RequestInit, errorFallback: string): Promise<Response> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...AUTH_HEADERS, ...init.headers },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${errorFallback} (${res.status})`);
  }
  return res;
}

export async function getTemplates(): Promise<ChecklistTemplate[]> {
  const res = await apiFetch("/templates", {}, "Failed to load templates");
  return res.json();
}

interface CreateAuditOptions {
  templateKey?: string;
  checklistItems?: string[];
}

interface CreateAuditResponse {
  job_id: string;
  status: string;
}

export async function createAudit(
  file: File,
  { templateKey, checklistItems }: CreateAuditOptions = {}
): Promise<CreateAuditResponse> {
  const form = new FormData();
  form.append("file", file);
  if (templateKey) {
    form.append("template", templateKey);
  } else if (checklistItems && checklistItems.length > 0) {
    form.append("checklist", JSON.stringify(checklistItems));
  }

  const res = await apiFetch("/audits", { method: "POST", body: form }, "Upload failed");
  return res.json();
}

export async function listAudits(): Promise<JobSummary[]> {
  const res = await apiFetch("/audits", {}, "Failed to load audits");
  return res.json();
}

export async function deleteAudit(jobId: string): Promise<void> {
  await apiFetch(`/audits/${jobId}`, { method: "DELETE" }, "Failed to delete audit");
}

export async function getAudit(jobId: string): Promise<Job> {
  const res = await apiFetch(`/audits/${jobId}`, {}, "Failed to fetch job");
  return res.json();
}

export function getDocumentUrl(jobId: string): string {
  const base = `${API_BASE}/audits/${jobId}/document`;
  return API_KEY ? `${base}?api_key=${encodeURIComponent(API_KEY)}` : base;
}
