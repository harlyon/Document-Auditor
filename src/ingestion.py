import os
import re
from typing import List
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import Chroma
from langchain.retrievers import EnsembleRetriever
from pypdf import PdfReader
from docx import Document as DocxFile
from docx.oxml.ns import qn
from sentence_transformers import SentenceTransformer

_PAGE_MARKER = re.compile(r"\[PAGE\s+(\d+)\]")

class MiniLMEmbeddings(Embeddings):
    """
    Local sentence-transformers embeddings (all-MiniLM-L6-v2), used instead of
    Gemini's embedding API so document ingestion has no network/API-key dependency
    and doesn't compete with the audit/guardrail calls for the same Gemini quota.

    Deliberately hand-rolled rather than using langchain-huggingface: that package
    pulls in langchain-core>=1.0, which conflicts with this project's pinned
    langchain==0.3.0 / langchain-community==0.3.0 / langchain-google-genai==2.0.1
    (all require langchain-core<0.4). This wrapper is the whole integration surface
    langchain_core.embeddings.Embeddings needs, so it avoids that conflict entirely.

    Verified via direct comparison against gemini-embedding-001 on this project's
    test document: identical verdicts across all 4 checklist items (contradiction,
    pass, fail, not-found), including retrieving the same chunks for the one case
    known to be retrieval-sensitive (a contradiction split across a chunk boundary).
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self._model = SentenceTransformer(model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._model.encode(texts, convert_to_numpy=True).tolist()

    def embed_query(self, text: str) -> List[float]:
        return self._model.encode([text], convert_to_numpy=True)[0].tolist()

def load_txt_document(path: str, encoding: str = "utf-8") -> List[Document]:
    """
    Reads a .txt file and splits it on '[PAGE X]' markers so each resulting Document
    carries an accurate `page` metadata field. Plain text has no inherent pagination,
    so files without that marker convention are returned as a single unpaginated chunk.
    """
    with open(path, "r", encoding=encoding) as f:
        raw_text = f.read()

    matches = list(_PAGE_MARKER.finditer(raw_text))
    if not matches:
        return [Document(page_content=raw_text, metadata={"source": path})]

    documents = []
    for i, match in enumerate(matches):
        page_num = int(match.group(1))
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
        content = raw_text[start:end].strip()
        if content:
            documents.append(Document(page_content=content, metadata={"source": path, "page": page_num}))
    return documents

def load_pdf_document(path: str) -> List[Document]:
    """
    Reads a .pdf file with one Document per page, using pypdf's native page
    boundaries -- accurate page metadata comes for free, no marker parsing needed.
    """
    reader = PdfReader(path)
    documents = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            documents.append(Document(page_content=text, metadata={"source": path, "page": i}))
    return documents

def _paragraph_has_page_break(paragraph) -> bool:
    for run in paragraph.runs:
        for br in run._element.findall(qn("w:br")):
            if br.get(qn("w:type")) == "page":
                return True
    return False

def load_docx_document(path: str) -> List[Document]:
    """
    Reads a .docx file. Unlike PDF, Word stores no fixed page boundaries --
    pagination is computed at render time from fonts, margins, and content flow --
    so this only captures *explicit* manual page breaks (Ctrl+Enter in Word).
    If none are present, the whole document is returned as a single chunk with
    no page metadata, same as an unmarked .txt file, rather than guessing.
    """
    doc = DocxFile(path)
    pages: List[Document] = []
    current_lines: List[str] = []
    current_page = 1
    saw_any_break = False

    def flush(page_num):
        text = "\n".join(current_lines).strip()
        if text:
            pages.append(Document(page_content=text, metadata={"source": path, "page": page_num}))

    for paragraph in doc.paragraphs:
        current_lines.append(paragraph.text)
        if _paragraph_has_page_break(paragraph):
            saw_any_break = True
            flush(current_page)
            current_lines = []
            current_page += 1

    flush(current_page)

    if not saw_any_break:
        full_text = "\n".join(p.page_content for p in pages)
        return [Document(page_content=full_text, metadata={"source": path})] if full_text.strip() else []

    return pages

_LOADERS = {
    ".pdf": load_pdf_document,
    ".docx": load_docx_document,
    ".txt": load_txt_document,
}

# Single source of truth for supported file types -- api.py and main.py both
# import this rather than hardcoding their own copy (they used to, and it's
# exactly the kind of thing that quietly drifts, like the old duplicated
# DEFAULT_CHECKLIST constants did before src/templates.py consolidated them).
SUPPORTED_EXTENSIONS = frozenset(_LOADERS)

def load_document(path: str) -> List[Document]:
    """Dispatches to the right loader based on file extension (.pdf, .docx, .txt)."""
    ext = os.path.splitext(path)[1].lower()
    loader = _LOADERS.get(ext)
    if loader is None:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Unsupported file type '{ext}' for '{path}'. Supported types: {supported}")
    return loader(path)

def create_hybrid_retriever(documents: List[Document], k: int = 4) -> EnsembleRetriever:
    """
    Blends Dense Vector Embeddings (local MiniLM) with Sparse BM25 Keyword Matching
    to pull both semantic meaning and specific phrase matches.

    k defaults to 4 (not 2): fixed-size chunking can split a single legally-critical
    sentence across two neighboring chunks (see load_document/text_splitter), and a
    too-narrow top-k can silently exclude the chunk holding the operative half of a
    clause -- confirmed via testing that k=2 missed a real contradiction whose second
    half didn't rank in the top 2 results for the checklist item's query.
    """
    print("🧠 Initializing Hybrid Retrieval Layer...")

    # 1. Setup Sparse Retriever (BM25 Keyword Matching)
    bm25_retriever = BM25Retriever.from_documents(documents)
    bm25_retriever.k = k

    # 2. Setup Dense Retriever (local MiniLM embeddings -- no Gemini API dependency
    #    for ingestion; see MiniLMEmbeddings docstring for why and how it was chosen)
    embeddings = MiniLMEmbeddings()
    vector_store = Chroma.from_documents(documents, embeddings)
    vector_retriever = vector_store.as_retriever(search_kwargs={"k": k})

    # 3. Combine both with equal weights
    hybrid_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, vector_retriever],
        weights=[0.5, 0.5]
    )

    print("✅ Hybrid BM25 + Vector Retriever successfully initialized.")
    return hybrid_retriever
