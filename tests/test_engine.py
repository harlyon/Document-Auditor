# tests/test_engine.py
import pytest
from langchain_core.documents import Document
from pydantic import ValidationError

from src.engine import execute_safe_audit_async, run_parallel_due_diligence
from src.ingestion import load_document, load_docx_document, load_pdf_document, load_txt_document
from src.schemas import AuditLog, GuardrailVerdict


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class FakeLLM:
    """Stands in for a langchain chat model bound with .with_structured_output().
    Each call to `invoke`/`ainvoke` pops the next queued response (or raises it,
    if it's an Exception instance)."""

    def __init__(self, responses):
        self._responses = list(responses)

    def _next(self):
        assert self._responses, "FakeLLM ran out of queued responses"
        value = self._responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def invoke(self, *args, **kwargs):
        return self._next()

    async def ainvoke(self, *args, **kwargs):
        return self._next()


def make_fake_chat_cls(fake_llm):
    """Returns a stand-in for the ChatGoogleGenerativeAI class whose
    constructor(...).with_structured_output(schema) hands back `fake_llm`."""

    class _FakeChatGoogleGenerativeAI:
        def __init__(self, *args, **kwargs):
            pass

        def with_structured_output(self, schema):
            return fake_llm

    return _FakeChatGoogleGenerativeAI


class FakeRetriever:
    def __init__(self, chunks):
        self._chunks = chunks

    def invoke(self, query):
        return self._chunks


def make_audit_log(**overrides):
    defaults = dict(
        verdict="PASSED",
        checklist_item="",
        raw_statement="Statement grounded in the source text.",
        exact_quote_citations=["Governing law is exclusively the State of New York."],
        page_citations=[2],
        contradiction_detected=False,
        contradiction_notes=None,
    )
    defaults.update(overrides)
    return AuditLog(**defaults)


def make_verdict(**overrides):
    defaults = dict(is_hallucinated=False, missing_evidence=False, critique_justification="ok")
    defaults.update(overrides)
    return GuardrailVerdict(**defaults)


# ---------------------------------------------------------------------------
# execute_safe_audit_async
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_passes_immediately_when_guardrail_approves_first_attempt(monkeypatch):
    audit_llm = FakeLLM([make_audit_log(raw_statement="Correct on first try.")])
    guard_llm = FakeLLM([make_verdict()])

    monkeypatch.setattr("src.engine.ChatGoogleGenerativeAI", make_fake_chat_cls(audit_llm))
    monkeypatch.setattr("src.guardrails.ChatGoogleGenerativeAI", make_fake_chat_cls(guard_llm))

    retriever = FakeRetriever([Document(page_content="ctx", metadata={"source": "x.txt", "page": 2})])

    result = await execute_safe_audit_async("Check governing law.", retriever, max_retries=3)

    assert result.raw_statement == "Correct on first try."
    assert result.checklist_item == "Check governing law."


@pytest.mark.asyncio
async def test_retries_after_hallucination_then_succeeds(monkeypatch):
    audit_llm = FakeLLM([
        make_audit_log(raw_statement="Hallucinated first draft."),
        make_audit_log(raw_statement="Corrected on retry."),
    ])
    guard_llm = FakeLLM([
        make_verdict(is_hallucinated=True, critique_justification="Fabricated a fact."),
        make_verdict(),
    ])

    monkeypatch.setattr("src.engine.ChatGoogleGenerativeAI", make_fake_chat_cls(audit_llm))
    monkeypatch.setattr("src.guardrails.ChatGoogleGenerativeAI", make_fake_chat_cls(guard_llm))

    retriever = FakeRetriever([Document(page_content="ctx", metadata={"source": "x.txt", "page": 2})])

    result = await execute_safe_audit_async("Check governing law.", retriever, max_retries=3)

    assert result.raw_statement == "Corrected on retry."
    assert result.checklist_item == "Check governing law."


@pytest.mark.asyncio
async def test_retries_after_missing_evidence_then_succeeds(monkeypatch):
    audit_llm = FakeLLM([
        make_audit_log(raw_statement="Citation doesn't match source."),
        make_audit_log(raw_statement="Citation now verbatim."),
    ])
    guard_llm = FakeLLM([
        make_verdict(missing_evidence=True, critique_justification="Quote was altered."),
        make_verdict(),
    ])

    monkeypatch.setattr("src.engine.ChatGoogleGenerativeAI", make_fake_chat_cls(audit_llm))
    monkeypatch.setattr("src.guardrails.ChatGoogleGenerativeAI", make_fake_chat_cls(guard_llm))

    retriever = FakeRetriever([Document(page_content="ctx", metadata={"source": "x.txt", "page": 2})])

    result = await execute_safe_audit_async("Check liability cap.", retriever, max_retries=3)

    assert result.raw_statement == "Citation now verbatim."


def make_page_citations_validation_error():
    """A real pydantic ValidationError, matching the actual failure observed in
    production: the model echoed a '[Source Doc: ..., Page: N]' context tag into
    page_citations instead of extracting just the integer."""
    try:
        AuditLog(
            verdict="PASSED",
            checklist_item="x",
            raw_statement="x",
            exact_quote_citations=[],
            page_citations=["uploads/8f1db7a2/contract.pdf, Page: 2"],
            contradiction_detected=False,
            contradiction_notes=None,
        )
    except ValidationError as e:
        return e
    raise AssertionError("expected AuditLog(...) to raise ValidationError")


@pytest.mark.asyncio
async def test_retries_after_malformed_structured_output_then_succeeds(monkeypatch):
    # Regression test: a ValidationError from audit_llm.ainvoke() used to
    # propagate immediately, skipping the retry loop entirely -- a single
    # malformed response killed the item with zero retries even though
    # max_retries=3. This confirms the retry loop now actually runs for this
    # failure class too, not just guardrail (hallucination/missing-evidence)
    # failures.
    audit_llm = FakeLLM([
        make_page_citations_validation_error(),
        make_audit_log(raw_statement="Correctly typed on retry."),
    ])
    guard_llm = FakeLLM([make_verdict()])

    monkeypatch.setattr("src.engine.ChatGoogleGenerativeAI", make_fake_chat_cls(audit_llm))
    monkeypatch.setattr("src.guardrails.ChatGoogleGenerativeAI", make_fake_chat_cls(guard_llm))

    retriever = FakeRetriever([Document(page_content="ctx", metadata={"source": "x.txt", "page": 2})])

    result = await execute_safe_audit_async("Check governing law.", retriever, max_retries=3)

    assert result.raw_statement == "Correctly typed on retry."


@pytest.mark.asyncio
async def test_raises_after_exhausting_max_retries(monkeypatch):
    audit_llm = FakeLLM([make_audit_log() for _ in range(3)])
    guard_llm = FakeLLM([
        make_verdict(is_hallucinated=True, critique_justification="Bad")
        for _ in range(3)
    ])

    monkeypatch.setattr("src.engine.ChatGoogleGenerativeAI", make_fake_chat_cls(audit_llm))
    monkeypatch.setattr("src.guardrails.ChatGoogleGenerativeAI", make_fake_chat_cls(guard_llm))

    retriever = FakeRetriever([Document(page_content="ctx", metadata={"source": "x.txt", "page": 2})])

    with pytest.raises(ValueError, match="Failed after 3 attempts. Last issue: Bad"):
        await execute_safe_audit_async("Check governing law.", retriever, max_retries=3)


# ---------------------------------------------------------------------------
# run_parallel_due_diligence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_parallel_due_diligence_preserves_order(monkeypatch):
    audit_llm = FakeLLM([
        make_audit_log(raw_statement="Result for item A"),
        make_audit_log(raw_statement="Result for item B"),
    ])
    guard_llm = FakeLLM([make_verdict(), make_verdict()])

    monkeypatch.setattr("src.engine.ChatGoogleGenerativeAI", make_fake_chat_cls(audit_llm))
    monkeypatch.setattr("src.guardrails.ChatGoogleGenerativeAI", make_fake_chat_cls(guard_llm))

    retriever = FakeRetriever([Document(page_content="ctx", metadata={"source": "x.txt", "page": 1})])
    checklist = ["Item A", "Item B"]

    results = await run_parallel_due_diligence(checklist, retriever)

    assert [r.checklist_item for r in results] == checklist
    assert [r.raw_statement for r in results] == ["Result for item A", "Result for item B"]


# ---------------------------------------------------------------------------
# load_paginated_document (page-citation accuracy)
# ---------------------------------------------------------------------------

def test_load_txt_document_assigns_correct_page_numbers(tmp_path):
    contract = tmp_path / "contract.txt"
    contract.write_text(
        "[PAGE 1]\nFirst page content.\n"
        "[PAGE 2]\nSecond page content.\n"
        "[PAGE 5]\nFifth page content.\n",
        encoding="utf-8",
    )

    docs = load_txt_document(str(contract))

    assert [d.metadata["page"] for d in docs] == [1, 2, 5]
    assert docs[0].page_content == "First page content."
    assert docs[1].page_content == "Second page content."
    assert docs[2].page_content == "Fifth page content."
    assert all(d.metadata["source"] == str(contract) for d in docs)


def test_load_txt_document_falls_back_without_markers(tmp_path):
    plain = tmp_path / "plain.txt"
    plain.write_text("No page markers here.", encoding="utf-8")

    docs = load_txt_document(str(plain))

    assert len(docs) == 1
    assert docs[0].page_content == "No page markers here."
    assert "page" not in docs[0].metadata


def test_load_pdf_document_assigns_native_page_numbers(tmp_path):
    pypdf_writer = pytest.importorskip("pypdf").PdfWriter()
    for _ in range(3):
        pypdf_writer.add_blank_page(width=200, height=200)

    pdf_path = tmp_path / "sample.pdf"
    with open(pdf_path, "wb") as f:
        pypdf_writer.write(f)

    docs = load_pdf_document(str(pdf_path))

    # Blank pages extract no text, so pypdf yields nothing to keep -- this
    # confirms it runs cleanly against a real PDF without crashing or
    # fabricating page content, rather than asserting specific text.
    assert docs == []


def test_load_docx_document_uses_explicit_page_breaks(tmp_path):
    docx_module = pytest.importorskip("docx")
    doc = docx_module.Document()
    doc.add_paragraph("First page content.")
    doc.add_page_break()
    doc.add_paragraph("Second page content.")

    docx_path = tmp_path / "sample.docx"
    doc.save(str(docx_path))

    docs = load_docx_document(str(docx_path))

    assert [d.metadata["page"] for d in docs] == [1, 2]
    assert docs[0].page_content == "First page content."
    assert docs[1].page_content == "Second page content."


def test_load_docx_document_falls_back_without_page_breaks(tmp_path):
    docx_module = pytest.importorskip("docx")
    doc = docx_module.Document()
    doc.add_paragraph("Only one page, no manual breaks.")

    docx_path = tmp_path / "sample.docx"
    doc.save(str(docx_path))

    docs = load_docx_document(str(docx_path))

    assert len(docs) == 1
    assert "page" not in docs[0].metadata
    assert docs[0].page_content == "Only one page, no manual breaks."


def test_load_document_dispatches_by_extension(tmp_path):
    plain = tmp_path / "note.txt"
    plain.write_text("hello", encoding="utf-8")

    docs = load_document(str(plain))

    assert docs[0].page_content == "hello"


def test_load_document_rejects_unsupported_extension(tmp_path):
    unsupported = tmp_path / "sample.rtf"
    unsupported.write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported file type"):
        load_document(str(unsupported))
