"""
services/rag/grounding_guard.py — Post-Generation Hallucination Check
=======================================================================
The most critical production RAG improvement.

PROBLEM: The prompt tells the LLM "only answer from the excerpts",
but nothing VERIFIES it actually did. LLMs can still hallucinate
or introduce outside knowledge despite instructions.

SOLUTION: After generation, we check each sentence of the response
against the source chunks using the cross-encoder. Any claim that
doesn't match any chunk above the threshold is flagged as
"potentially unsupported".

This is the same approach used by:
- Google's SAFE (Search Augmented Factuality Evaluator)
- Anthropic's Citation Verification
- Microsoft's Groundedness Detection

OUTPUT:
- grounding_score: 0.0-1.0 (what % of claims are grounded)
- flagged_claims: list of sentences with low grounding scores
- is_grounded: True if grounding_score >= threshold
"""

import re
import logging
from dataclasses import dataclass
from functools import lru_cache
from sentence_transformers import CrossEncoder
from app.services.retrieval.retriever import RetrievedChunk
from app.core.config import settings

logger = logging.getLogger(__name__)

GROUNDING_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@lru_cache(maxsize=1)
def _get_grounding_model() -> CrossEncoder:
    """Load the cross-encoder model for grounding checks (cached)."""
    logger.info(f"[GROUNDING] Loading grounding model: {GROUNDING_MODEL}")
    model = CrossEncoder(GROUNDING_MODEL, max_length=512)
    logger.info("[GROUNDING] Model loaded.")
    return model


@dataclass
class GroundingResult:
    """Result of a grounding check on an LLM response."""
    is_grounded: bool           # True if the response is sufficiently grounded
    grounding_score: float      # 0.0 to 1.0 (fraction of grounded claims)
    total_claims: int           # Number of sentences checked
    grounded_claims: int        # Number of claims with sufficient support
    flagged_claims: list[dict]  # Claims with low grounding scores
    details: list[dict]         # Per-claim grounding details


def check_grounding(
    response_text: str,
    source_chunks: list[RetrievedChunk],
    threshold: float | None = None,
) -> GroundingResult:
    """
    Checks whether each claim in the LLM response is grounded
    in the source chunks.

    Args:
        response_text:  The LLM's full response text
        source_chunks:  The chunks that were used as context
        threshold:      Min score for a claim to be considered grounded
                        (defaults to settings.GROUNDING_THRESHOLD)

    Returns:
        GroundingResult with per-claim analysis
    """
    if not settings.GROUNDING_ENABLED:
        return GroundingResult(
            is_grounded=True, grounding_score=1.0,
            total_claims=0, grounded_claims=0,
            flagged_claims=[], details=[],
        )

    threshold = threshold or settings.GROUNDING_THRESHOLD

    # Extract claims (sentences) from the response
    claims = _extract_claims(response_text)

    if not claims:
        return GroundingResult(
            is_grounded=True, grounding_score=1.0,
            total_claims=0, grounded_claims=0,
            flagged_claims=[], details=[],
        )

    if not source_chunks:
        return GroundingResult(
            is_grounded=False, grounding_score=0.0,
            total_claims=len(claims), grounded_claims=0,
            flagged_claims=[{"claim": c, "max_score": 0.0} for c in claims],
            details=[],
        )

    model = _get_grounding_model()

    # Concatenate all source chunks into one reference text
    source_texts = [chunk.text for chunk in source_chunks]

    details = []
    flagged = []
    grounded_count = 0

    for claim in claims:
        # Score this claim against each source chunk
        pairs = [(claim, source) for source in source_texts]
        scores = model.predict(pairs)

        max_score = float(max(scores)) if len(scores) > 0 else 0.0
        best_chunk_idx = int(scores.argmax()) if len(scores) > 0 else -1
        is_claim_grounded = max_score >= threshold

        if is_claim_grounded:
            grounded_count += 1
        else:
            flagged.append({
                "claim": claim,
                "max_score": round(max_score, 3),
            })

        details.append({
            "claim": claim,
            "max_score": round(max_score, 3),
            "best_chunk_idx": best_chunk_idx,
            "is_grounded": is_claim_grounded,
        })

    grounding_score = grounded_count / len(claims) if claims else 1.0
    is_grounded = grounding_score >= 0.6  # At least 60% of claims must be grounded

    logger.info(
        f"[GROUNDING] Score: {grounding_score:.2f} "
        f"({grounded_count}/{len(claims)} claims grounded). "
        f"Flagged: {len(flagged)}"
    )

    return GroundingResult(
        is_grounded=is_grounded,
        grounding_score=round(grounding_score, 3),
        total_claims=len(claims),
        grounded_claims=grounded_count,
        flagged_claims=flagged,
        details=details,
    )


def _extract_claims(text: str) -> list[str]:
    """
    Extracts individual claims (sentences) from LLM response text.
    Filters out:
    - Very short sentences (likely fragments or headers)
    - JSON citation blocks
    - Boilerplate phrases ("Based on the excerpts...", "According to...")
    """
    # Remove JSON citation blocks
    cleaned = re.sub(r'```json[\s\S]*?```', '', text)
    cleaned = re.sub(r'\{"sources":\s*\[.*?\]\}', '', cleaned, flags=re.DOTALL)

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', cleaned)

    claims = []
    skip_patterns = [
        r"^based on (?:the )?(?:provided )?excerpts?",
        r"^according to the (?:provided )?",
        r"^the (?:provided )?excerpts? (?:do not|don't)",
        r"^I (?:cannot|can't|don't)",
        r"^note:",
        r"^sources?:",
    ]

    for sentence in sentences:
        sentence = sentence.strip()

        # Skip very short sentences
        if len(sentence) < 20:
            continue

        # Skip boilerplate
        is_boilerplate = False
        for pattern in skip_patterns:
            if re.match(pattern, sentence, re.IGNORECASE):
                is_boilerplate = True
                break

        if not is_boilerplate:
            claims.append(sentence)

    return claims
