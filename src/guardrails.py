# pyrefly: ignore [missing-import]
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from src.schemas import AuditLog, GuardrailVerdict

def run_guardrail_verification(context: str, generated_output: AuditLog) -> GuardrailVerdict:
    """Acts as a separate Adversarial Judge to trap fabrications or metadata errors using Gemini."""
    guard_llm = ChatGoogleGenerativeAI(model="gemini-flash-lite-latest", temperature=0).with_structured_output(GuardrailVerdict)

    guardrail_prompt = ChatPromptTemplate.from_template("""
    You are an adversarial Quality Assurance Judge. Your job is to catch hallucinations, fabrications, or over-extrapolations.
    Compare the Evaluated Assertion and its provided Citations against the Raw Source Text context.

    [RAW SOURCE TEXT CONTEXT]
    {context}

    [EVALUATED ASSERTION]
    Statement: {statement}
    Claimed Verbatim Citations: {citations}
    Claimed Pages: {pages}

    CRITERIA:
    1. If the Statement contains ANY fact, date, name, or parameter not explicitly found in the Raw Source Text, flag as IS_HALLUCINATED = True.
    2. Check if the 'Claimed Verbatim Citations' exist EXACTLY word-for-word in the Raw Source Text. If they are modified or missing, flag MISSING_EVIDENCE = True.
    """)

    formatted = guardrail_prompt.format(
        context=context,
        statement=generated_output.raw_statement,
        citations=generated_output.exact_quote_citations,
        pages=generated_output.page_citations
    )

    return guard_llm.invoke(formatted)
