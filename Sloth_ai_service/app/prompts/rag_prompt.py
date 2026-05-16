"""
prompts/rag_prompt.py — The Grounded Generation Prompt
=======================================================
🎓 LEARNING: Prompt engineering is critical for production RAG.
A poorly designed prompt leads to hallucinations (making things up).
Our prompt enforces THREE key rules:

  1. GROUNDING: "Answer ONLY from the excerpts below"
     → If the answer isn't in the chunks, the AI says "I don't know"
     → Prevents the model from mixing in outside knowledge

  2. CITATION: Include a JSON block with source page numbers
     → This is how the frontend knows which page to highlight!
     → Structured output makes parsing reliable

  3. TONE: Academic and precise
     → Appropriate for research paper analysis
"""


def build_rag_prompt(question: str, context_chunks: list) -> str:
    """
    Builds a grounded RAG prompt with retrieved context.
    
    🎓 LEARNING: This prompt uses a technique called "context stuffing" —
    we literally paste the retrieved text chunks into the prompt and tell
    the LLM to ONLY answer from those passages. This is the core of RAG.
    
    The JSON at the end of instructions is the key to source highlighting:
    the LLM is instructed to return which chunk indices it used, and we
    map those back to page numbers for the frontend.
    
    Args:
        question:       The user's question
        context_chunks: List of RetrievedChunk objects (already re-ranked)
    
    Returns:
        A complete prompt string ready to send to Gemini
    """
    # Format each chunk with its source label
    # 🎓 LEARNING: We number the excerpts so the LLM can reference them
    # in its JSON citation block (e.g., "I used excerpts [0] and [2]")
    formatted_excerpts = ""
    for i, chunk in enumerate(context_chunks):
        formatted_excerpts += (
            f"\n[Excerpt {i} | Page {chunk.page_number}]\n"
            f"{chunk.text}\n"
            f"{'─' * 60}\n"
        )
    
    prompt = f"""You are an expert academic research assistant. Your task is to answer questions about a specific research paper, using ONLY the provided excerpts from that paper.

STRICT RULES:
1. Base your answer EXCLUSIVELY on the excerpts provided below.
2. Do NOT use any prior knowledge or information not found in the excerpts.
3. If the excerpts do not contain enough information to answer the question, respond: "The provided excerpts do not contain enough information to answer this question."
4. Be precise, concise, and academic in tone.
5. At the END of your response, include a JSON citation block in this exact format:
   ```json
   {{"sources": [{{"excerpt_index": 0, "page": 1}}, {{"excerpt_index": 2, "page": 5}}]}}
   ```
   List only the excerpt indices you actually used in your answer.

─────────────────────────── PAPER EXCERPTS ───────────────────────────
{formatted_excerpts}
──────────────────────────────────────────────────────────────────────

QUESTION: {question}

ANSWER (remember to include the JSON citation block at the end):"""

    return prompt
