export type Verdict = "PASSED" | "FAILED" | "CONTRADICTORY" | "NOT_FOUND";

export interface AuditLog {
  verdict: Verdict;
  checklist_item: string;
  raw_statement: string;
  exact_quote_citations: string[];
  page_citations: number[];
  contradiction_detected: boolean;
  contradiction_notes: string | null;
}

export type ItemStatus = "queued" | "done" | "error";

export interface JobItem {
  id: string;
  label: string;
  checklist_item: string;
  status: ItemStatus;
  result: AuditLog | null;
  error: string | null;
}

export type JobStatus = "queued" | "processing" | "completed" | "failed";

export interface DueDiligenceReport {
  checklist_results: AuditLog[];
}

export interface Job {
  job_id: string;
  status: JobStatus;
  document: string;
  created_at: string;
  error: string | null;
  items: JobItem[];
  report?: DueDiligenceReport;
}


export interface JobSummary {
  job_id: string;
  document: string;
  status: JobStatus;
  created_at: string;
  error: string | null;
  item_count: number;
  done_count: number;
  verdict_counts: Record<Verdict, number>;
}

export interface ChecklistItem {
  id: string;
  label: string;
  question: string;
}

export interface ChecklistTemplate {
  key: string;
  name: string;
  items: ChecklistItem[];
}

export interface AuditRunOptions {
  templateKey?: string;
  checklistItems?: string[];
}

export interface ResultsLocationState {
  file: File;
  auditOptions: AuditRunOptions;
}
