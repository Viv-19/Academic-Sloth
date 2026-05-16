"""
services/ingestion/pdf_extractor.py — Step 1: PDF Text Extraction
===================================================================
🎓 LEARNING: PyMuPDF (imported as `fitz`) is the gold standard for
PDF parsing. It extracts text page-by-page, which is critical for us
because we need to store the page_number with every chunk. This is
what will later allow the frontend to highlight the exact page.

Why not just extract all text as one string?
→ Because when the AI answers "see page 5", we need to know which
  chunk came from page 5. Without per-page tracking, we lose that.
"""

import fitz  # PyMuPDF — the package is 'pymupdf' but it imports as 'fitz'
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PageContent:
    """
    Represents the extracted content of a single PDF page.
    
    🎓 LEARNING: Python @dataclass is like a lightweight class that
    automatically generates __init__, __repr__ etc. It's perfect for
    simple data containers — similar to TypeScript interfaces.
    """
    page_number: int       # 1-indexed page number (human-readable)
    text: str              # Raw extracted text from this page
    char_count: int        # How many characters on this page


@dataclass
class ExtractionResult:
    """The full result of extracting a PDF document."""
    doc_id: str
    title: str
    total_pages: int
    pages: list[PageContent]
    metadata: dict         # PDF metadata (author, creation date, etc.)


def extract_pdf(file_path: str, doc_id: str, title: str) -> ExtractionResult:
    """
    Extracts text from every page of a PDF, preserving page numbers.
    
    🎓 LEARNING: We open the PDF with fitz.open(), iterate through
    each page, and call .get_text("text") to get plain text.
    The "text" argument means we want plain text — other options are
    "html", "dict" (rich layout info), or "blocks" (text blocks with coordinates).
    
    Args:
        file_path: Absolute path to the PDF on disk
        doc_id:    The document's database ID
        title:     The paper title (for logging)
    
    Returns:
        ExtractionResult with per-page content
    
    Raises:
        FileNotFoundError: If the PDF doesn't exist at the given path
        ValueError: If the PDF is empty or unreadable
    """
    logger.info(f"[EXTRACTOR] Opening PDF: {file_path}")
    
    try:
        doc = fitz.open(file_path)
    except Exception as e:
        raise FileNotFoundError(f"Could not open PDF at {file_path}: {e}")
    
    if doc.page_count == 0:
        raise ValueError(f"PDF has no pages: {file_path}")
    
    # Extract PDF metadata (embedded title, author, etc.)
    # These are often unreliable for arXiv papers, so we don't rely on them
    raw_metadata = doc.metadata or {}
    metadata = {
        "pdf_title": raw_metadata.get("title", ""),
        "pdf_author": raw_metadata.get("author", ""),
        "pdf_subject": raw_metadata.get("subject", ""),
        "total_pages": doc.page_count,
    }
    
    pages: list[PageContent] = []
    
    for page_num in range(doc.page_count):
        page = doc[page_num]
        
        # get_text("text") extracts plain text, joining lines naturally
        # get_text("blocks") would give us bounding boxes — useful for future layout analysis
        text = page.get_text("text")
        
        # Clean up excessive whitespace while preserving paragraph structure
        cleaned_text = _clean_text(text)
        
        if cleaned_text.strip():  # Skip completely empty pages (e.g. cover images)
            pages.append(PageContent(
                page_number=page_num + 1,  # Convert from 0-indexed to 1-indexed
                text=cleaned_text,
                char_count=len(cleaned_text),
            ))
    
    # ─────────────────────────────────────────────────────────
    # BUG FIX: save total_pages BEFORE calling doc.close()!
    # Once close() is called, accessing ANY attribute on `doc`
    # raises "ValueError: document closed". This is the root cause
    # of the ingestion pipeline crash.
    # 🎓 LEARNING: Always read what you need from an object BEFORE
    # releasing/closing it. This applies to file handles, DB cursors,
    # and PDF documents alike.
    # ─────────────────────────────────────────────────────────
    total_pages = doc.page_count  # ← Read this BEFORE close()
    doc.close()
    
    total_chars = sum(p.char_count for p in pages)
    logger.info(
        f"[EXTRACTOR] Extracted {len(pages)} pages, "
        f"{total_chars:,} characters from '{title}'"
    )
    
    return ExtractionResult(
        doc_id=doc_id,
        title=title,
        total_pages=total_pages,   # ← Use the saved value, not doc.page_count
        pages=pages,
        metadata=metadata,
    )


def _clean_text(text: str) -> str:
    """
    Cleans extracted PDF text by normalising whitespace.
    
    🎓 LEARNING: PDF text extraction often produces artefacts like
    excessive newlines, hyphenated words split across lines, and
    ligature characters. This function handles the most common cases.
    """
    import re
    
    # Remove null bytes and other control characters that fitz sometimes emits
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    
    # Collapse more than 2 consecutive newlines into exactly 2 (preserve paragraphs)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove lines that are just page numbers (single digits or "Page X of Y")
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
    
    return text.strip()
