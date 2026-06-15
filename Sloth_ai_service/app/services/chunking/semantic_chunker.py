"""
services/chunking/semantic_chunker.py — Enhanced Semantic Chunking
====================================================================
Improvements over the original chunker:

1. SECTION DETECTION: Identifies section headers (Abstract, Introduction,
   Methodology, Results, Conclusion, References) and attaches them as
   metadata to every chunk. This lets agents know which part of the paper
   a chunk belongs to — critical for the Summary and Deep Dive agents.

2. REFERENCE FILTERING: Chunks from the References/Bibliography section
   are flagged so agents can exclude them (they add noise to RAG).

3. METADATA ENRICHMENT: Each chunk now carries:
   - section_title: which section it belongs to
   - is_abstract: True if from the abstract
   - is_conclusion: True if from the conclusion/discussion
   - is_references: True if from the bibliography section

4. IMPROVED SEPARATORS: Better separator hierarchy that respects
   academic paper structure (section breaks, paragraphs, sentences).
"""

import re
import logging
from dataclasses import dataclass
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.services.ingestion.pdf_extractor import ExtractionResult
from app.core.config import settings

logger = logging.getLogger(__name__)

# Common section header patterns in academic papers
SECTION_PATTERNS = [
    (r"^\s*abstract\s*$", "Abstract"),
    (r"^\s*\d+\.?\s*introduction\s*$", "Introduction"),
    (r"^\s*introduction\s*$", "Introduction"),
    (r"^\s*\d+\.?\s*related\s+work", "Related Work"),
    (r"^\s*\d+\.?\s*background", "Background"),
    (r"^\s*\d+\.?\s*method(?:ology|s)?\s*$", "Methodology"),
    (r"^\s*\d+\.?\s*(?:proposed\s+)?(?:approach|framework|model|system|architecture)", "Methodology"),
    (r"^\s*\d+\.?\s*experiment(?:s|al)?\s*(?:setup|results)?", "Experiments"),
    (r"^\s*\d+\.?\s*results?\s*(?:and\s+discussion)?", "Results"),
    (r"^\s*\d+\.?\s*(?:evaluation|analysis)", "Evaluation"),
    (r"^\s*\d+\.?\s*discussion", "Discussion"),
    (r"^\s*\d+\.?\s*conclusion(?:s)?\s*(?:and\s+future\s+work)?", "Conclusion"),
    (r"^\s*\d+\.?\s*future\s+work", "Future Work"),
    (r"^\s*\d+\.?\s*limitations?", "Limitations"),
    (r"^\s*references?\s*$", "References"),
    (r"^\s*bibliography\s*$", "References"),
    (r"^\s*appendix", "Appendix"),
    (r"^\s*acknowledgment", "Acknowledgments"),
]


@dataclass
class TextChunk:
    """
    A single chunk of text ready for embedding.
    Carries its source metadata so we can trace it back to the PDF.
    Enhanced with section-level metadata for agent routing.
    """
    chunk_id: str          # Unique ID: "{doc_id}_chunk_{index}"
    doc_id: str
    text: str              # The actual text content of this chunk
    page_number: int       # Which page this chunk came from
    chunk_index: int       # Position in the document (0-based)
    char_count: int
    # --- New metadata fields ---
    section_title: str = "Unknown"      # Which section (e.g., "Methodology")
    is_abstract: bool = False
    is_conclusion: bool = False
    is_references: bool = False


def _detect_section(text: str) -> str | None:
    """
    Checks if a line of text is a section header.
    Returns the normalized section name if it matches, None otherwise.
    """
    stripped = text.strip()
    if len(stripped) > 80:
        # Section headers are typically short
        return None

    for pattern, section_name in SECTION_PATTERNS:
        if re.match(pattern, stripped, re.IGNORECASE):
            return section_name

    return None


def _detect_sections_in_pages(pages: list) -> dict[int, str]:
    """
    Scans all pages to build a map of page_number → section_title.
    When a section header is detected on a page, all subsequent pages
    inherit that section until a new header is found.

    Returns:
        Dict mapping page_number → section_title
    """
    page_sections: dict[int, str] = {}
    current_section = "Unknown"

    for page in pages:
        lines = page.text.split("\n")

        for line in lines:
            detected = _detect_section(line)
            if detected:
                current_section = detected
                break  # Use first header found on this page

        page_sections[page.page_number] = current_section

    return page_sections


def chunk_document(extraction: ExtractionResult) -> list[TextChunk]:
    """
    Splits an extracted document into overlapping text chunks with
    section-level metadata enrichment.

    Enhanced with:
    - Section detection (tracks which section each chunk belongs to)
    - Reference filtering flag (chunks from bibliography are flagged)
    - Abstract/Conclusion flags (useful for summary agents)
    - Improved separators for academic text structure

    Args:
        extraction: The result from pdf_extractor.extract_pdf()

    Returns:
        List of TextChunk objects ready for embedding
    """

    # Use separators optimized for academic papers:
    # Section breaks → paragraph breaks → sentence boundaries → word boundaries
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,         # Target chars per chunk (from .env)
        chunk_overlap=settings.CHUNK_OVERLAP,   # Overlap between chunks (from .env)
        length_function=len,
        separators=[
            "\n\n\n",   # Section breaks (triple newline)
            "\n\n",      # Paragraph breaks
            "\n",        # Line breaks
            ". ",        # Sentence boundaries
            "; ",        # Semicolon boundaries
            ", ",        # Clause boundaries
            " ",         # Word boundaries
            "",          # Character-level (last resort)
        ],
    )

    # Build section map: page_number → section_title
    page_sections = _detect_sections_in_pages(extraction.pages)

    all_chunks: list[TextChunk] = []
    global_chunk_index = 0

    for page in extraction.pages:
        if not page.text.strip():
            continue

        section = page_sections.get(page.page_number, "Unknown")

        # Split this page's text into chunks
        raw_chunks = splitter.split_text(page.text)

        for raw_text in raw_chunks:
            cleaned = raw_text.strip()
            if len(cleaned) < 50:
                # Skip very short chunks (often just headers or page numbers)
                continue

            chunk = TextChunk(
                chunk_id=f"{extraction.doc_id}_chunk_{global_chunk_index}",
                doc_id=extraction.doc_id,
                text=cleaned,
                page_number=page.page_number,
                chunk_index=global_chunk_index,
                char_count=len(cleaned),
                section_title=section,
                is_abstract=(section == "Abstract"),
                is_conclusion=(section in ("Conclusion", "Discussion", "Future Work")),
                is_references=(section == "References"),
            )
            all_chunks.append(chunk)
            global_chunk_index += 1

    # Log section distribution
    section_counts: dict[str, int] = {}
    for c in all_chunks:
        section_counts[c.section_title] = section_counts.get(c.section_title, 0) + 1

    non_ref_count = sum(1 for c in all_chunks if not c.is_references)

    logger.info(
        f"[CHUNKER] '{extraction.title}': "
        f"{len(extraction.pages)} pages → {len(all_chunks)} chunks "
        f"({non_ref_count} content + {len(all_chunks) - non_ref_count} reference) "
        f"(size={settings.CHUNK_SIZE}, overlap={settings.CHUNK_OVERLAP})"
    )
    logger.info(f"[CHUNKER] Section distribution: {section_counts}")

    return all_chunks
