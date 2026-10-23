# src/engine.py
import asyncio
# pyrefly: ignore [missing-import]
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import ValidationError
from src.schemas import AuditLog
from src.guardrails import run_guardrail_verification

# Caps how many checklist items run their audit+guardrail calls concurrently.
# The free-tier Gemini quota can reject bursts from 4+ items firing at once
# (each retry attempt is 2 model calls), so this trades some wall-clock time
# for reliability rather than letting the whole batch fail under load.
MAX_CONCURRENT_AUDITS = 2

async def execute_safe_audit_async(checklist_item: str, retriever, max_retries: int = 3) -> AuditLog:
    """
    Asynchronously executes a 4-layer audit workflow for an individual item using Gemini.
    """
    # gemini-2.5-pro is unavailable on the free tier (quota limit 0), and gemini-flash-latest
    # is capped at 5 req/min there; gemini-flash-lite-latest has a far more usable free quota.
    audit_llm = ChatGoogleGenerativeAI(model="gemini-flash-lite-latest", temperature=0).with_structured_output(AuditLog)

    relevant_chunks = await asyncio.to_thread(retriever.invoke, checklist_item)

    context_str = ""
    for i, chunk in enumerate(relevant_chunks):
        context_str += f"\n[Source Doc: {chunk.metadata.get('source')}, Page: {chunk.metadata.get('page', 1)}]\n{chunk.page_content}\n"

    audit_prompt = ChatPromptTemplate.from_template("""
    Analyze the following document context and perform a hard compliance check for this item: "{checklist_item}"

    Document Context:
    {context}

    CRITICAL INSTRUCTION ON CONTRADICTION DETECTION:
    Scan all fragments across pages carefully. If Page X states one rule and Page Y states an opposing rule, you MUST set contradiction_detected to True and verdict to 'CONTRADICTORY'.
    """)

    attempts = 0
    feedback_loop_notes = ""
    last_failure_reason = "unknown error"

    while attempts < max_retries:
        attempts += 1

        full_context_input = context_str + f"\n{feedback_loop_notes}" if feedback_loop_notes else context_str
        formatted_audit = audit_prompt.format(checklist_item=checklist_item, context=full_context_input)

        try:
            # Async invoke to Gemini API endpoints
            audit_output = await audit_llm.ainvoke(formatted_audit)
        except ValidationError as exc:
            # The model occasionally mis-types a field -- e.g. echoing the
            # "[Source Doc: ..., Page: N]" context tag into page_citations
            # instead of extracting just the integer. Without this, that raw
            # pydantic error propagated on the FIRST attempt, skipping the
            # retry loop entirely (confirmed directly: a real page_citations
            # int-parsing failure killed the item with zero retries). Treat it
            # like a guardrail failure instead -- give the model another shot
            # with a corrective note. Scoped to ValidationError specifically so
            # a genuine API/rate-limit error still fails fast rather than
            # burning attempts on a note that can't fix it.
            last_failure_reason = "the model returned incorrectly formatted data"
            feedback_loop_notes = f"""
            --- CRITICAL RETRY NOTICE FROM AUDITOR SYSTEM ---
            Your previous response had invalid field types: {exc}
            page_citations must be a list of plain integers (e.g. [2, 5]), never
            source tags or other strings. Regenerate the payload with correctly
            typed fields.
            ------------------------------------------------
            """
            continue

        audit_output.checklist_item = checklist_item

        # Parallel thread routing for local guard execution check
        guard_result = await asyncio.to_thread(run_guardrail_verification, context_str, audit_output)

        if not guard_result.is_hallucinated and not guard_result.missing_evidence:
            return audit_output

        last_failure_reason = guard_result.critique_justification
        feedback_loop_notes = f"""
        --- CRITICAL RETRY NOTICE FROM AUDITOR SYSTEM ---
        Your previous generation failed quality assurance checks with the following error: {guard_result.critique_justification}.
        Regenerate the payload. You MUST copy snippets EXACTLY without stretching facts.
        ------------------------------------------------
        """

    raise ValueError(f"Failed after {max_retries} attempts. Last issue: {last_failure_reason}")

async def run_parallel_due_diligence(checklist: list, retriever) -> list:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_AUDITS)

    async def _run_throttled(item):
        async with semaphore:
            return await execute_safe_audit_async(item, retriever)

    tasks = [_run_throttled(item) for item in checklist]
    return await asyncio.gather(*tasks)

async def run_parallel_due_diligence_with_progress(checklist: list, retriever, on_item_done=None) -> list:
    """
    Same throttled concurrent audit as run_parallel_due_diligence, but:
    - reports each item's outcome via on_item_done(index, checklist_item, result, error)
      as soon as it finishes, instead of only after the whole batch completes.
    - one item exhausting its retries (e.g. persistent hallucination) does not abort
      the rest of the batch; its slot in the returned list is None and its error is
      passed to the callback instead of raised.
    Intended for API/job-status use, where a caller wants partial progress rather
    than an all-or-nothing await.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_AUDITS)
    results = [None] * len(checklist)

    async def _run_one(index, item):
        async with semaphore:
            try:
                result = await execute_safe_audit_async(item, retriever)
                results[index] = result
                error = None
            except Exception as exc:
                result = None
                error = exc
            if on_item_done:
                outcome = on_item_done(index, item, result, error)
                if asyncio.iscoroutine(outcome):
                    await outcome

    await asyncio.gather(*[_run_one(i, item) for i, item in enumerate(checklist)])
    return results
