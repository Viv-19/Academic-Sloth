"""
prompts/rag_prompt.py — Production RAG Prompt with Token Budgeting
=====================================================================
Improvements over the original prompt:

1. TOKEN BUDGETING: Counts tokens and enforces a max context budget.
   Prevents exceeding the LLM's context window on long papers.

2. CHUNK DEDUPLICATION: Removes near-identical overlapping chunks
   that waste token budget without adding new information.

3. CONVERSATION-AWARE: Includes recent chat history when available,
   enabling follow-up questions.

4. AGENT-SPECIFIC PROMPTS: Different prompt templates for different
   agent types (factual, summary, deep dive, compare, critique).
"""

import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# Approximate tokens per character for English text
# GPT/Llama tokenizers average ~4 chars per token
CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    """Rough token count estimate without requiring tiktoken."""
    return len(text) // CHARS_PER_TOKEN


def _deduplicate_chunks(chunks: list, similarity_threshold: float = 0.85) -> list:
    """
    Removes near-duplicate chunks that share too much overlapping text.
    Uses Jaccard similarity on word sets as a fast heuristic.
    """
    if not chunks:
        return []

    unique_chunks = [chunks[0]]

    for candidate in chunks[1:]:
        is_duplicate = False
        candidate_words = set(candidate.text.lower().split())

        for existing in unique_chunks:
            existing_words = set(existing.text.lower().split())

            if not candidate_words or not existing_words:
                continue

            # Jaccard similarity
            intersection = len(candidate_words & existing_words)
            union = len(candidate_words | existing_words)
            similarity = intersection / union if union > 0 else 0

            if similarity >= similarity_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            unique_chunks.append(candidate)

    if len(unique_chunks) < len(chunks):
        logger.info(
            f"[PROMPT] Deduplication: {len(chunks)} → {len(unique_chunks)} chunks "
            f"({len(chunks) - len(unique_chunks)} duplicates removed)"
        )

    return unique_chunks


def _trim_chunks_to_budget(chunks: list, max_tokens: int) -> list:
    """
    Trims the chunk list to fit within the token budget.
    Keeps chunks in order (most relevant first from reranking).
    """
    trimmed = []
    total_tokens = 0

    for chunk in chunks:
        chunk_tokens = _estimate_tokens(chunk.text)
        if total_tokens + chunk_tokens > max_tokens:
            # Try to include a truncated version of this chunk
            remaining_tokens = max_tokens - total_tokens
            if remaining_tokens > 50:  # Only include if at least 50 tokens fit
                truncated_chars = remaining_tokens * CHARS_PER_TOKEN
                chunk.text = chunk.text[:truncated_chars] + "..."
                trimmed.append(chunk)
            break
        trimmed.append(chunk)
        total_tokens += chunk_tokens

    if len(trimmed) < len(chunks):
        logger.info(
            f"[PROMPT] Token budget: kept {len(trimmed)}/{len(chunks)} chunks "
            f"(~{total_tokens} tokens, budget={max_tokens})"
        )

    return trimmed


def build_rag_prompt(
    question: str,
    context_chunks: list,
    conversation_context: str = "",
    agent_type: str = "factual",
) -> str:
    """
    Builds a grounded RAG prompt with token-budgeted context.

    Args:
        question:             The user's question
        context_chunks:       List of RetrievedChunk objects (already re-ranked)
        conversation_context: Recent chat history string (for follow-ups)
        agent_type:           Which agent is using this prompt

    Returns:
        A complete prompt string ready to send to the LLM
    """
    # Step 1: Deduplicate near-identical chunks
    chunks = _deduplicate_chunks(context_chunks)

    # Step 2: Trim to token budget
    chunks = _trim_chunks_to_budget(chunks, settings.MAX_CONTEXT_TOKENS)

    # Step 3: Format excerpts
    formatted_excerpts = ""
    for i, chunk in enumerate(chunks):
        section_label = ""
        if hasattr(chunk, "section_title") and chunk.section_title != "Unknown":
            section_label = f" | Section: {chunk.section_title}"

        formatted_excerpts += (
            f"\n[Excerpt {i} | Page {chunk.page_number}{section_label}]\n"
            f"{chunk.text}\n"
            f"{'─' * 60}\n"
        )

    # Step 4: Get agent-specific instructions
    agent_instructions = _get_agent_instructions(agent_type)

    # Step 5: Build conversation context section
    history_section = ""
    if conversation_context:
        history_section = f"""
─────────────────────── CONVERSATION HISTORY ───────────────────────
{conversation_context}
────────────────────────────────────────────────────────────────────

Consider the conversation history above when answering. The user may be asking a follow-up question.
"""

    prompt = f"""{agent_instructions}

STRICT RULES:
1. Base your answer EXCLUSIVELY on the excerpts provided below.
2. Do NOT use any prior knowledge or information not found in the excerpts.
3. If the excerpts do not contain enough information to answer the question, respond: "The provided excerpts do not contain enough information to answer this question."
4. Be precise, concise, and academic in tone.
5. Do NOT mention the words "Excerpt", "Source", or their indices in your conversational text. Speak naturally as if you read the paper directly.
6. At the END of your response, include a JSON citation block in this exact format:
   ```json
   {{"sources": [{{"excerpt_index": 0, "page": 1}}, {{"excerpt_index": 2, "page": 5}}]}}
   ```
   List only the excerpt indices you actually used in your answer.
{history_section}
─────────────────────── PAPER EXCERPTS ───────────────────────
{formatted_excerpts}
──────────────────────────────────────────────────────────────

QUESTION: {question}

ANSWER (remember to include the JSON citation block at the end):"""

    return prompt


def _get_agent_instructions(agent_type: str) -> str:
    """Returns agent-specific system instructions for the prompt."""
    instructions = {
        "factual": (
            "You are an expert academic research assistant. Your task is to answer "
            "a specific factual question about a research paper using ONLY the provided excerpts. "
            "Be precise and cite specific numbers, names, or findings."
        ),
        "summary": (
            "You are an expert academic research assistant. Your task is to provide "
            "a comprehensive summary of the research paper using ONLY the provided excerpts. "
            "Structure your summary with: (1) Main objective, (2) Key methodology, "
            "(3) Principal findings, (4) Main conclusions."
        ),
        "deep_dive": (
            "You are an expert academic research assistant. Your task is to provide "
            "a detailed technical explanation of the topic asked about, using ONLY the "
            "provided excerpts. Go deep into the methodology, architecture, or technical details. "
            "Use precise terminology and explain complex concepts clearly."
        ),
        "compare": (
            "You are an expert academic research assistant. Your task is to compare "
            "and contrast the elements asked about, using ONLY the provided excerpts. "
            "Structure your response as a clear comparison with specific differences "
            "and similarities. Use a table format if appropriate."
        ),
        "critique": (
            "You are an expert academic research assistant. Your task is to provide "
            "a critical analysis of the aspects asked about, using ONLY the provided excerpts. "
            "Identify strengths, limitations, potential improvements, and future directions "
            "mentioned by the authors."
        ),
    }
    return instructions.get(agent_type, instructions["factual"])
