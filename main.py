# main.py
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.documents import Document
from src.ingestion import SUPPORTED_EXTENSIONS, create_hybrid_retriever, load_document
from src.engine import run_parallel_due_diligence
from src.schemas import DueDiligenceReport
from src.templates import DEFAULT_TEMPLATE_KEY, TEMPLATES

from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()
# langchain_google_genai reads GOOGLE_API_KEY; this project's .env uses GEMINI_API_KEY.
if not os.environ.get("GOOGLE_API_KEY") and os.environ.get("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

def parse_args():
    parser = argparse.ArgumentParser(description="Run the AI Document Auditor against a document.")
    parser.add_argument(
        "document",
        nargs="?",
        default=None,
        help="Path to a .pdf, .docx, or .txt document to audit. If omitted, you'll be prompted for one."
    )
    parser.add_argument(
        "--template",
        default=DEFAULT_TEMPLATE_KEY,
        choices=sorted(TEMPLATES),
        help=f"Checklist template to run (default: {DEFAULT_TEMPLATE_KEY})"
    )
    return parser.parse_args()

def prompt_for_document() -> str:
    """
    Interactively asks for a document path when none was given on the command line.
    TTY-aware: in a non-interactive context (piped input, a CI job, a background
    process with no attached terminal), input() would otherwise just hang waiting
    on stdin -- that's a worse failure mode than a clear error, so this fails fast
    instead. Re-prompts on a missing file or unsupported extension rather than
    exiting on the first typo, matching this project's general retry-before-giving-up
    approach elsewhere (the guardrail loop, the malformed-output retry in engine.py).
    """
    supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))

    if not sys.stdin.isatty():
        print("Error: no document given, and there's no interactive terminal to prompt on.", file=sys.stderr)
        print(f"Usage: python main.py <document> [--template {{{','.join(sorted(TEMPLATES))}}}]", file=sys.stderr)
        print(f"Supported document types: {supported}", file=sys.stderr)
        sys.exit(1)

    while True:
        raw = input(f"Enter path to a document ({supported}): ").strip()
        if not raw:
            print("Please enter a path.")
            continue
        path = Path(raw)
        if not path.is_file():
            print(f"'{raw}' doesn't exist. Try again.")
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            print(f"Unsupported file type '{path.suffix}'. Supported: {supported}")
            continue
        return str(path)

async def main():
    args = parse_args()
    document_path = args.document or prompt_for_document()

    print("====================================================")
    print("🚀 Initializing Gemini Async Portfolio Demonstration...")
    print(f"📄 Document: {document_path}")

    raw_docs = load_document(document_path)

    # Split into chunks; page metadata set by load_document is preserved on every chunk.
    # A larger overlap (and a sentence-boundary separator) keeps a single clause from
    # being severed across a chunk seam -- confirmed via testing that a 50-char overlap
    # could silently drop the operative half of a contradictory clause from retrieval.
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    documents = text_splitter.split_documents(raw_docs)

    retriever = create_hybrid_retriever(documents)

    checklist = [item.question for item in TEMPLATES[args.template].items]

    print(f"📋 Template: {args.template} ({len(checklist)} items)")
    print(f"⚡ Launching {len(checklist)} audit threads through Gemini...")
    results = await run_parallel_due_diligence(checklist, retriever)

    final_report = DueDiligenceReport(checklist_results=results)

    print("\n====================================================")
    print("🏆 GEMINI CONCURRENT RUN COMPLETED. PARSED DATA RESULTS:")
    print("====================================================")
    print(json.dumps(final_report.model_dump(), indent=2))

if __name__ == "__main__":
    asyncio.run(main())
