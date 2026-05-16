"""
services/chunking/semantic_chunker.py — Step 2: Chunking
==========================================================
🎓 LEARNING: Chunking is arguably the most important step in RAG.
The goal is to split the paper text into segments that are:
  1. Small enough to fit into the LLM's prompt context window
  2. Large enough to contain a complete, meaningful idea
  3. Overlapping so answers aren't accidentally split between two chunks

We use LangChain's RecursiveCharacterTextSplitter which tries to split on:
  paragraph → sentence → word → character (in that priority order)
This is much smarter than a naive "split every N characters" approach.

CHUNK METADATA:
Every chunk we produce carries metadata:
  - doc_id: Which document it belongs to
  - page_number: Which page it came from
  - chunk_index: Its position in the document (0, 1, 2, ...)
This metadata is stored alongside the vector in ChromaDB, and is
what allows us to tell the frontend "the answer came from page 7".
"""

import logging
from dataclasses import dataclass
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.services.ingestion.pdf_extractor import ExtractionResult
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    """
    A single chunk of text ready for embedding.
    Carries its source metadata so we can trace it back to the PDF.
    """
    chunk_id: str          # Unique ID: "{doc_id}_chunk_{index}"
    doc_id: str
    text: str              # The actual text content of this chunk
    page_number: int       # Which page this chunk came from
    chunk_index: int       # Position in the document (0-based)
    char_count: int


def chunk_document(extraction: ExtractionResult) -> list[TextChunk]:
    """
    Splits an extracted document into overlapping text chunks.
    
    🎓 LEARNING: Why overlap?
    Imagine a key sentence sits at the end of page 3 and continues
    on page 4. Without overlap, it would be split across two chunks
    and neither chunk contains the complete idea. With 100-token
    overlap, both adjacent chunks include this boundary content.
    
    Think of it like a sliding window over the text.
    
    Args:
        extraction: The result from pdf_extractor.extract_pdf()
    
    Returns:
        List of TextChunk objects ready for embedding
    """
    
    # 🎓 LEARNING: RecursiveCharacterTextSplitter tries to split text
    # using a priority list of separators:
    # ["\n\n", "\n", " ", ""] — paragraphs first, then sentences, then words.
    # `chunk_overlap` means adjacent chunks share N characters of text.
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,         # Target chars per chunk (from .env)
        chunk_overlap=settings.CHUNK_OVERLAP,   # Overlap between chunks (from .env)
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    
    all_chunks: list[TextChunk] = []
    global_chunk_index = 0
    
    for page in extraction.pages:
        if not page.text.strip():
            continue
        
        # Split this page's text into chunks
        # LangChain returns plain strings here
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
            )
            all_chunks.append(chunk)
            global_chunk_index += 1
    
    logger.info(
        f"[CHUNKER] '{extraction.title}': "
        f"{len(extraction.pages)} pages → {len(all_chunks)} chunks "
        f"(size={settings.CHUNK_SIZE}, overlap={settings.CHUNK_OVERLAP})"
    )
    
    return all_chunks
