"""
services/agents/router_agent.py — Intent Classification Agent
================================================================
The first node in the LangGraph pipeline. Classifies the user's
question into one of 5 intent categories to determine which
specialized agent should handle it.

Uses the FAST (8B) model since routing doesn't need quality —
just speed and reliable classification.

Intents:
    factual   → Specific factual questions ("What accuracy did they achieve?")
    summary   → Paper overview requests ("Summarize this paper")
    deep_dive → Technical detail requests ("Explain the methodology in detail")
    compare   → Comparison questions ("How does this compare to previous work?")
    critique  → Critical analysis ("What are the limitations?")
"""

import re
import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.langchain_llm import get_fast_llm
from app.services.agents.state import AgentState

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = """You are a query classifier for an academic paper research assistant.
Your job is to classify the user's question into exactly ONE of these categories:

1. "factual" — Specific factual questions about data, numbers, names, dates, or specific findings.
   Examples: "What accuracy did they achieve?", "How many layers?", "What dataset?", "Who are the authors?"

2. "summary" — Requests for paper overview, abstract, or general understanding.
   Examples: "Summarize this paper", "What is this paper about?", "Give me an overview", "Key findings?"

3. "deep_dive" — Requests for detailed technical explanations of methodology, architecture, or algorithms.
   Examples: "Explain the attention mechanism", "How does the model work?", "Describe the training process"

4. "compare" — Comparison or contrast questions between methods, models, or approaches.
   Examples: "How does this compare to BERT?", "Difference between method A and B?", "Advantages over previous work?"

5. "critique" — Critical analysis, limitations, weaknesses, or future work questions.
   Examples: "What are the limitations?", "What could be improved?", "Any weaknesses?", "Future work?"

6. "conversational" — Casual greetings, small talk, or questions completely unrelated to the paper.
   Examples: "hi", "hello", "thanks", "how are you", "who are you"

Respond with ONLY a JSON object in this exact format:
{"intent": "factual", "confidence": 0.9}

Do NOT include any other text, explanation, or markdown. Just the JSON object."""


def route_query(state: AgentState) -> AgentState:
    """
    LangGraph node: Classifies the user's question into an intent category.

    Reads: question
    Writes: intent, intent_confidence, steps_completed
    """
    question = state["question"]
    logger.info(f"[ROUTER] Classifying: '{question[:60]}...'")

    # First try rule-based classification (fast, no API call)
    rule_result = _rule_based_classify(question)
    if rule_result:
        logger.info(f"[ROUTER] Rule-based classification: {rule_result['intent']} (confidence: {rule_result['confidence']})")
        state["intent"] = rule_result["intent"]
        state["intent_confidence"] = rule_result["confidence"]
        state["steps_completed"] = state.get("steps_completed", []) + ["router"]
        return state

    # Fall back to LLM classification
    try:
        llm = get_fast_llm()
        response = llm.invoke([
            SystemMessage(content=ROUTER_SYSTEM_PROMPT),
            HumanMessage(content=f"Classify this question: {question}"),
        ])

        # Parse the JSON response
        result = _parse_router_response(response.content)
        state["intent"] = result["intent"]
        state["intent_confidence"] = result["confidence"]

        logger.info(f"[ROUTER] LLM classification: {result['intent']} (confidence: {result['confidence']})")

    except Exception as e:
        logger.warning(f"[ROUTER] Classification failed: {e}. Defaulting to 'factual'.")
        state["intent"] = "factual"
        state["intent_confidence"] = 0.5

    state["steps_completed"] = state.get("steps_completed", []) + ["router"]
    return state


def _rule_based_classify(question: str) -> dict | None:
    """
    Fast rule-based classification using keyword patterns.
    Returns None if no confident match, triggering LLM fallback.
    """
    q_lower = question.lower().strip()

    # Summary patterns
    summary_patterns = [
        r"^summar",
        r"^what is this paper about",
        r"^(?:give|provide) (?:me )?(?:a |an )?(?:overview|summary|brief)",
        r"^(?:key|main) (?:findings|contributions|results|points|takeaways)",
        r"^what (?:are|were) the (?:main|key|primary) (?:findings|contributions|results)",
        r"^(?:tldr|tl;dr)",
        r"^overview",
    ]
    for pattern in summary_patterns:
        if re.match(pattern, q_lower):
            return {"intent": "summary", "confidence": 0.95}

    # Critique patterns
    critique_patterns = [
        r"(?:limitation|weakness|drawback|shortcoming)",
        r"(?:could be |should be |need.* to be )?improve",
        r"^what (?:are|were) the (?:limitation|weakness|problem)",
        r"future work",
        r"(?:flaw|gap|issue|concern|criticism)",
    ]
    for pattern in critique_patterns:
        if re.search(pattern, q_lower):
            return {"intent": "critique", "confidence": 0.90}

    # Compare patterns
    compare_patterns = [
        r"(?:compar|contrast|differ|versus|vs\.?|advantage|disadvantage)",
        r"how (?:does|do|did) .+ (?:compar|differ|stack up)",
        r"(?:better|worse|superior|inferior) (?:than|to|compared)",
        r"(?:pros? and cons?|trade.?off)",
    ]
    for pattern in compare_patterns:
        if re.search(pattern, q_lower):
            return {"intent": "compare", "confidence": 0.90}

    # Deep dive patterns
    deep_dive_patterns = [
        r"^explain (?:the |how )",
        r"^(?:describe|detail|elaborate on) (?:the )?(?:method|approach|algorithm|archit[a-z]+|model|training|process)",
        r"(?:in detail|step by step|in depth|technical)",
        r"^how (?:does|do|did) (?:the |their |this )?(?:model|method|approach|system|archit[a-z]+|algorithm)",
        r"what is the (?:main |core |primary )?archit[a-z]+",
    ]
    for pattern in deep_dive_patterns:
        if re.search(pattern, q_lower):
            return {"intent": "deep_dive", "confidence": 0.85}

    # Conversational patterns
    conversational_patterns = [
        r"^(?:hi|hello|hey|greetings|good morning|good evening|good afternoon)",
        r"^(?:thanks|thank you|appreciate it|awesome|great|good job)",
        r"^(?:how are you|who are you|what are you)",
    ]
    for pattern in conversational_patterns:
        if re.search(pattern, q_lower):
            return {"intent": "conversational", "confidence": 0.95}

    # No confident match — fall back to LLM
    return None


def _parse_router_response(response_text: str) -> dict:
    """Parse the LLM's JSON classification response."""
    valid_intents = {"factual", "summary", "deep_dive", "compare", "critique", "conversational"}

    try:
        # Try to find JSON in the response
        match = re.search(r'\{[^}]+\}', response_text)
        if match:
            data = json.loads(match.group())
            intent = data.get("intent", "factual")
            confidence = float(data.get("confidence", 0.7))

            if intent not in valid_intents:
                intent = "factual"

            return {"intent": intent, "confidence": min(confidence, 1.0)}
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: look for intent keywords in raw text
    response_lower = response_text.lower()
    for intent in valid_intents:
        if intent in response_lower:
            return {"intent": intent, "confidence": 0.6}

    return {"intent": "factual", "confidence": 0.5}
