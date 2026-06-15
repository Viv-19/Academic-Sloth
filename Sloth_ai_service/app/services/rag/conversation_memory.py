"""
services/rag/conversation_memory.py — Sliding Window Conversation Memory
==========================================================================
Implements conversation history management so users can ask follow-up
questions like "tell me more about that" or "what about the second method?"

Uses a simple in-memory sliding window per (user_session, doc_id) pair.
In production, this would be backed by Redis for persistence across restarts.

The conversation context is injected into the RAG prompt so the LLM
knows what was discussed previously.
"""

import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """A single turn in a conversation (user question + AI response)."""
    role: str       # "user" or "assistant"
    content: str


@dataclass
class ConversationSession:
    """Sliding window of conversation turns for a specific document."""
    doc_id: str
    turns: list[ConversationTurn] = field(default_factory=list)
    max_turns: int = 0  # Set from config

    def __post_init__(self):
        if self.max_turns == 0:
            self.max_turns = settings.CONVERSATION_WINDOW_SIZE * 2  # Each "turn" = user + assistant

    def add_user_message(self, content: str):
        """Add a user message to the conversation."""
        self.turns.append(ConversationTurn(role="user", content=content))
        self._trim()

    def add_assistant_message(self, content: str):
        """Add an assistant response to the conversation."""
        self.turns.append(ConversationTurn(role="assistant", content=content))
        self._trim()

    def _trim(self):
        """Keep only the last N turns (sliding window)."""
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]

    def get_history(self) -> list[dict]:
        """Returns the conversation history as a list of dicts for LLM consumption."""
        return [{"role": t.role, "content": t.content} for t in self.turns]

    def get_context_string(self) -> str:
        """
        Returns a formatted string of recent conversation for injection
        into the RAG prompt. Only includes the last 3 exchanges for brevity.
        """
        recent = self.turns[-6:]  # Last 3 user+assistant pairs
        if not recent:
            return ""

        lines = []
        for turn in recent:
            prefix = "User" if turn.role == "user" else "Assistant"
            # Truncate long responses to save tokens
            content = turn.content[:300] + "..." if len(turn.content) > 300 else turn.content
            lines.append(f"{prefix}: {content}")

        return "\n".join(lines)

    def is_empty(self) -> bool:
        return len(self.turns) == 0


class ConversationManager:
    """
    Manages multiple conversation sessions.

    Uses an LRU cache to prevent unbounded memory growth.
    Sessions are keyed by doc_id (since we chat per-document).

    In production, this would be backed by Redis with TTL expiry.
    """

    def __init__(self, max_sessions: int = 200):
        self._sessions: OrderedDict[str, ConversationSession] = OrderedDict()
        self._max_sessions = max_sessions

    def get_session(self, doc_id: str) -> ConversationSession:
        """Get or create a conversation session for a document."""
        if doc_id in self._sessions:
            # Move to end (LRU)
            self._sessions.move_to_end(doc_id)
            return self._sessions[doc_id]

        # Create new session
        session = ConversationSession(doc_id=doc_id)
        self._sessions[doc_id] = session

        # Evict oldest if at capacity
        while len(self._sessions) > self._max_sessions:
            evicted_key, _ = self._sessions.popitem(last=False)
            logger.info(f"[MEMORY] Evicted conversation session for doc {evicted_key}")

        return session

    def clear_session(self, doc_id: str):
        """Clear conversation history for a document."""
        if doc_id in self._sessions:
            del self._sessions[doc_id]
            logger.info(f"[MEMORY] Cleared session for doc {doc_id}")

    def get_active_session_count(self) -> int:
        return len(self._sessions)


# Module-level singleton
conversation_manager = ConversationManager()
