import type { Job } from "./types";
import { computeHealthScore } from "./scoring";
import { friendlyErrorMessage } from "./errors";

function verdictLabel(verdict: string): string {
  return verdict.replace("_", " ");
}

export function buildMarkdownReport(job: Job): string {
  const items = job.items;
  const { score, passed, failed, contradictory, notFound, applicableTotal } = computeHealthScore(items);

  const lines: string[] = [];
  lines.push(`# Audit Report: ${job.document}`);
  lines.push("");
  lines.push(`Generated: ${new Date().toISOString()}`);
  lines.push("");
  lines.push("## Summary");
  lines.push("");
  lines.push(
    score === null
      ? "No scoreable checks (all items were not found in the document)."
      : `**Health score: ${score}%** (${passed} passed / ${applicableTotal} applicable checks)`
  );
  lines.push("");
  lines.push(`- Passed: ${passed}`);
  lines.push(`- Failed: ${failed}`);
  lines.push(`- Contradictory: ${contradictory}`);
  lines.push(`- Not found in document: ${notFound}`);
  lines.push("");
  lines.push("## Checklist Results");

  for (const item of items) {
    lines.push("");
    lines.push(`### ${item.label}`);
    lines.push("");
    lines.push(`*${item.checklist_item}*`);
    lines.push("");

    if (item.status === "error") {
      lines.push(`**Status: Could not be verified** -- ${item.error ? friendlyErrorMessage(item.error) : ""}`);
      if (item.error) {
        lines.push("");
        lines.push(`<details><summary>Technical details</summary>\n\n${item.error}\n\n</details>`);
      }
      continue;
    }
    if (item.status === "queued" || !item.result) {
      lines.push("**Status: Not completed**");
      continue;
    }

    const r = item.result;
    lines.push(`**Verdict: ${verdictLabel(r.verdict)}**`);
    lines.push("");
    lines.push(r.raw_statement);

    if (r.contradiction_detected && r.contradiction_notes) {
      lines.push("");
      lines.push(`**Contradiction:** ${r.contradiction_notes}`);
    }

    if (r.exact_quote_citations.length > 0) {
      lines.push("");
      lines.push("Citations:");
      r.exact_quote_citations.forEach((quote, i) => {
        const page = r.page_citations[i] ?? "?";
        lines.push(`- (Page ${page}) "${quote}"`);
      });
    }
  }

  return lines.join("\n");
}

export function downloadTextFile(filename: string, content: string, mimeType = "text/markdown") {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
