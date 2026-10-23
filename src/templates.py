# src/templates.py
"""
Named checklist templates for common document types, plus a general-purpose
default. Kept deliberately separate from src/schemas.py: ChecklistItem's id/label
are orchestration/UI metadata that the LLM never sees -- execute_safe_audit_async
and AuditLog only ever deal in a plain question string (see engine.py). Callers
(api.py, main.py) resolve a template to its list of questions before handing
anything to the engine.
"""
from typing import Dict, List
from pydantic import BaseModel


class ChecklistItem(BaseModel):
    id: str
    label: str
    question: str


class ChecklistTemplate(BaseModel):
    key: str
    name: str
    items: List[ChecklistItem]


TEMPLATES: Dict[str, ChecklistTemplate] = {
    "general_contract": ChecklistTemplate(
        key="general_contract",
        name="General Contract",
        items=[
            ChecklistItem(id="governing_law", label="Governing law specified",
                question="Identify the governing law state and verify if conflicts exist."),
            ChecklistItem(id="liability_cap", label="Liability cap specified",
                question="Check if there is an explicit limitation of liability cap."),
            ChecklistItem(id="non_compete", label="Non-compete period reasonable",
                question="Verify the non-compete restriction period does not exceed twelve (12) months."),
            ChecklistItem(id="data_breach_notification", label="Data breach notification deadline",
                question="Check if the agreement specifies a data breach notification deadline in hours."),
        ],
    ),
    "mna_contract": ChecklistTemplate(
        key="mna_contract",
        name="M&A Contract",
        items=[
            ChecklistItem(id="parties", label="Parties clearly identified",
                question="Who are the parties to this agreement?"),
            ChecklistItem(id="consideration", label="Consideration specified",
                question="What is the purchase price or consideration amount?"),
            ChecklistItem(id="closing_date", label="Closing date defined",
                question="What is the closing date or completion date?"),
            ChecklistItem(id="conditions_precedent", label="Conditions precedent listed",
                question="What conditions must be satisfied before closing?"),
            ChecklistItem(id="representations", label="Representations and warranties present",
                question="What representations and warranties are made by each party?"),
            ChecklistItem(id="indemnification", label="Indemnification clause present",
                question="What are the indemnification obligations?"),
            ChecklistItem(id="termination", label="Termination rights defined",
                question="Under what conditions can this agreement be terminated?"),
            ChecklistItem(id="liability_cap", label="Liability cap specified",
                question="Is there a cap on liability? What is the maximum liability amount?"),
            ChecklistItem(id="governing_law", label="Governing law specified",
                question="Which jurisdiction's law governs this agreement?"),
            ChecklistItem(id="dispute_resolution", label="Dispute resolution mechanism",
                question="How are disputes resolved -- arbitration, litigation, mediation?"),
            ChecklistItem(id="confidentiality", label="Confidentiality obligations",
                question="What confidentiality or non-disclosure obligations exist?"),
            ChecklistItem(id="non_compete", label="Non-compete or non-solicitation",
                question="Are there any non-compete or non-solicitation restrictions?"),
        ],
    ),
    "financial_report": ChecklistTemplate(
        key="financial_report",
        name="Financial Report",
        items=[
            ChecklistItem(id="revenue", label="Revenue figures disclosed",
                question="What are the total revenue figures reported?"),
            ChecklistItem(id="net_income", label="Net income / profit reported",
                question="What is the net income or net profit for the period?"),
            ChecklistItem(id="ebitda", label="EBITDA disclosed",
                question="Is EBITDA or operating profit disclosed?"),
            ChecklistItem(id="cash_flow", label="Cash flow statement present",
                question="What does the cash flow statement show?"),
            ChecklistItem(id="debt", label="Debt obligations disclosed",
                question="What are the total debt obligations and repayment terms?"),
            ChecklistItem(id="risk_factors", label="Risk factors disclosed",
                question="What risk factors are disclosed?"),
            ChecklistItem(id="auditor", label="Auditor opinion present",
                question="What is the auditor's opinion? Is it qualified or unqualified?"),
            ChecklistItem(id="going_concern", label="Going concern assessment",
                question="Is there any going concern doubt or qualification?"),
            ChecklistItem(id="related_party", label="Related party transactions disclosed",
                question="Are related party transactions disclosed?"),
            ChecklistItem(id="guidance", label="Forward guidance provided",
                question="Is there any forward-looking guidance or outlook for future periods?"),
        ],
    ),
    "employment_contract": ChecklistTemplate(
        key="employment_contract",
        name="Employment Contract",
        items=[
            ChecklistItem(id="role", label="Role and responsibilities defined",
                question="What is the employee's role, title, and responsibilities?"),
            ChecklistItem(id="compensation", label="Compensation specified",
                question="What is the base salary or compensation?"),
            ChecklistItem(id="benefits", label="Benefits outlined",
                question="What benefits are provided -- health, pension, equity?"),
            ChecklistItem(id="start_date", label="Start date specified",
                question="What is the employment start date?"),
            ChecklistItem(id="probation", label="Probation period defined",
                question="Is there a probation period? How long?"),
            ChecklistItem(id="notice_period", label="Notice period specified",
                question="What notice period is required for termination by either party?"),
            ChecklistItem(id="ip_assignment", label="IP assignment clause present",
                question="Is there an intellectual property assignment clause?"),
            ChecklistItem(id="non_compete_employment", label="Non-compete clause",
                question="Is there a non-compete restriction after employment ends?"),
            ChecklistItem(id="termination_grounds", label="Termination grounds specified",
                question="What are the grounds for termination with and without cause?"),
            ChecklistItem(id="governing_law_employment", label="Governing law specified",
                question="Which jurisdiction governs this employment contract?"),
        ],
    ),
}

DEFAULT_TEMPLATE_KEY = "general_contract"
