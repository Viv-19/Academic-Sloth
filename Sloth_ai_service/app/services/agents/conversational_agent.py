"""
services/agents/conversational_agent.py — General Chat Agent
================================================================
Handles casual conversation, greetings, and small talk:
- "Hi"
- "Hello"
- "Thanks for the help"

This agent skips the entire RAG pipeline (no retrieval, no grounding)
and just responds politely, reminding the user it's an academic assistant.
"""

import logging
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.langchain_llm import get_fast_llm
from app.services.agents.state import AgentState

logger = logging.getLogger(__name__)

def run_conversational_agent(state: AgentState) -> AgentState:
    """
    LangGraph node: Generates a casual conversation response.
    Skips retrieval completely.
    """
    question = state["question"]
    conversation_context = state.get("conversation_context", "")
    logger.info(f"[CHAT] Processing casual conversation: '{question[:60]}...'")

    llm = get_fast_llm()
    
    system_prompt = (
        "You are 'Academic Sloth', a friendly and intelligent academic research assistant AI. "
        "The user is engaging in casual conversation or asking a question totally unrelated to the paper. "
        "Respond politely, naturally, and concisely. If appropriate, gently remind them that your main "
        "purpose is to help them read, analyze, and understand the research paper they are currently viewing."
    )
    
    user_prompt = f"Conversation History:\n{conversation_context}\n\nUser: {question}\nAcademic Sloth:"

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])

    state["response"] = response.content
    state["agent_name"] = "conversational"
    state["retrieved_chunks"] = []
    state["reranked_chunks"] = []
    state["is_grounded"] = True  # It's a general chat, so we don't need to flag it as ungrounded
    state["grounding_score"] = 1.0
    state["steps_completed"] = state.get("steps_completed", []) + ["conversational_agent"]

    logger.info(f"[CHAT] Generated response for casual conversation.")
    return state
