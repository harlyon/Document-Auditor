# src/schemas.py
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

class AuditLog(BaseModel):
    verdict: Literal["PASSED", "FAILED", "CONTRADICTORY", "NOT_FOUND"] = Field(
        description="The final evaluation outcome."
    )
    checklist_item: str = Field(description="The exact rule being audited.")
    raw_statement: str = Field(description="The primary assertion or summary answer being evaluated.")
    exact_quote_citations: List[str] = Field(description="Verbatim text snippets extracted exactly from the source material.")
    page_citations: List[int] = Field(description="Exact page numbers where the text snippets reside.")
    contradiction_detected: bool = Field(description="True if text fragments within the document conflict with each other.")
    contradiction_notes: Optional[str] = Field(description="Specific details on what clauses or pages conflict.")

class GuardrailVerdict(BaseModel):
    is_hallucinated: bool = Field(description="True if the Statement contains facts NOT written in the raw source text.")
    missing_evidence: bool = Field(description="True if the claimed verbatim citations are missing or altered from the source text.")
    critique_justification: str = Field(description="Step-by-step reasoning proving or disproving hallucination.")

class DueDiligenceReport(BaseModel):
    checklist_results: List[AuditLog]
