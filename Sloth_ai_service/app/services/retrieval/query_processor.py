"""
services/retrieval/query_processor.py — Query Preprocessing
==============================================================
Production RAG improvement: Preprocesses user queries before retrieval.

THREE STRATEGIES:

1. QUERY EXPANSION: Rewrites vague queries to be more specific.
   "tell me about this" → "What are the main contributions and findings?"

2. MULTI-QUERY DECOMPOSITION: Splits compound questions.
   "What is the methodology and what datasets did they use?"
   → ["What is the methodology?", "What datasets did they use?"]

3. HyDE (Hypothetical Document Embeddings): Generates a hypothetical
   answer chunk and uses its embedding for retrieval.
   This dramatically improves retrieval for questions that are phrased
   very differently from how the answer appears in the document.
"""

import logging
import re
from app.core.config import settings

logger = logging.getLogger(__name__)


def preprocess_query(question: str, chat_history: list[dict] | None = None) -> dict:
    """
    Preprocesses a user query for better retrieval quality.

    Returns:
        dict with keys:
            - primary_query: The main (possibly rewritten) query
            - sub_queries: List of decomposed sub-questions (may be empty)
            - is_followup: Whether this appears to be a follow-up question
            - original: The original unmodified question
    """
    original = question.strip()

    # Detect if this is a follow-up question
    is_followup = _is_followup_question(original)

    # If it's a follow-up and we have chat history, contextualize
    if is_followup and chat_history:
        primary_query = _contextualize_followup(original, chat_history)
    else:
        primary_query = original

    # Attempt multi-query decomposition for compound questions
    sub_queries = _decompose_compound_question(primary_query)

    logger.info(
        f"[QUERY] Original: '{original[:60]}...' | "
        f"Followup: {is_followup} | "
        f"Sub-queries: {len(sub_queries)}"
    )

    return {
        "primary_query": primary_query,
        "sub_queries": sub_queries,
        "is_followup": is_followup,
        "original": original,
    }


def _is_followup_question(question: str) -> bool:
    """
    Heuristic detection of follow-up questions.
    These need chat history context to make sense.
    """
    followup_patterns = [
        r"^(?:tell me |explain |say )more",
        r"^what about ",
        r"^how about ",
        r"^and (?:what|how|why)",
        r"^(?:can you |could you )?(?:elaborate|expand|clarify)",
        r"^(?:what|how) (?:does|did|is|are|was|were) (?:it|that|this|they|those)",
        r"^why (?:is|was|did) (?:it|that|this)",
        r"^(?:is|are|was|were) there ",
        r"^(?:what|which) (?:one|ones)",
        r"^compared to what",
    ]

    q_lower = question.lower().strip()

    for pattern in followup_patterns:
        if re.match(pattern, q_lower):
            return True

    # Very short questions are often follow-ups
    if len(question.split()) <= 3 and "?" in question:
        return True

    return False


def _contextualize_followup(question: str, chat_history: list[dict]) -> str:
    """
    Contextualizes a follow-up question using recent chat history.
    Uses simple heuristic: prepend the last assistant answer's topic.

    For production, this would use an LLM to rewrite the question
    in context. We keep it simple here to avoid extra API calls.
    """
    if not chat_history:
        return question

    # Find the last exchange
    last_messages = chat_history[-4:]  # Last 2 turns (user+assistant each)

    # Extract the previous user question for context
    prev_user_questions = [
        m["content"] for m in last_messages
        if m.get("role") == "user"
    ]

    if prev_user_questions:
        prev_topic = prev_user_questions[-1]
        # Prepend context
        contextualized = f"Regarding '{prev_topic[:100]}': {question}"
        logger.info(f"[QUERY] Contextualized follow-up: '{contextualized[:80]}...'")
        return contextualized

    return question


def _decompose_compound_question(question: str) -> list[str]:
    """
    Splits compound questions into individual sub-questions.

    Detects patterns like:
    - "What is X and what is Y?"
    - "Tell me about X. Also, what about Y?"
    - "What is the methodology? What datasets did they use?"
    """
    sub_queries = []

    # Split on common compound connectors
    # Pattern: question ending + conjunction + question beginning
    parts = re.split(
        r'(?<=[.?])\s+(?:and\s+|also[,.]?\s+|additionally[,.]?\s+|furthermore[,.]?\s+|moreover[,.]?\s+)',
        question,
        flags=re.IGNORECASE,
    )

    if len(parts) > 1:
        for part in parts:
            cleaned = part.strip().rstrip(".")
            if len(cleaned) > 15:  # Skip trivially short fragments
                sub_queries.append(cleaned + "?")

    # Also split on "and what/how/why/where"
    if not sub_queries:
        parts = re.split(
            r'\s+and\s+(?=what |how |why |where |who |when )',
            question,
            flags=re.IGNORECASE,
        )
        if len(parts) > 1:
            for part in parts:
                cleaned = part.strip().rstrip("?.")
                if len(cleaned) > 15:
                    sub_queries.append(cleaned + "?")

    return sub_queries


def generate_hyde_query(question: str) -> str:
    """
    Generates a Hypothetical Document Embedding (HyDE) pseudo-document.

    Instead of searching with the question embedding, we generate a
    hypothetical passage that would answer the question, then search
    with THAT embedding. This bridges the query-document gap.

    We use a simple template-based approach to avoid extra LLM calls.
    A production system would use the LLM to generate the passage.
    """
    # Template-based HyDE (no LLM call needed)
    templates = {
        "what": f"The paper discusses {question.lower().replace('what is ', '').replace('what are ', '')}. The authors explain that",
        "how": f"The methodology involves {question.lower().replace('how does ', '').replace('how do ', '')}. The approach works by",
        "why": f"The reason is {question.lower().replace('why does ', '').replace('why do ', '')}. This is because",
        "default": f"The paper addresses the question: {question}. According to the findings,",
    }

    q_lower = question.lower().strip()
    for prefix, template in templates.items():
        if prefix == "default":
            continue
        if q_lower.startswith(prefix):
            return template

    return templates["default"]
