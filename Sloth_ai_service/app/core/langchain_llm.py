"""
core/langchain_llm.py — LangChain-Compatible Groq LLM Wrapper
================================================================
Wraps our existing GroqRotatingClient as a LangChain-compatible
ChatModel so all LangGraph agents can use our key rotation
transparently.

This is a lightweight adapter — it delegates all actual API calls
to the existing GroqRotatingClient which handles:
- Multi-key rotation (8 keys round-robin)
- Automatic fallback to smaller model on rate limits
- Circuit breaker when all keys exhausted

LangGraph requires LangChain-compatible LLM objects to work.
Rather than using `ChatGroq` from langchain-groq (which doesn't
support multi-key rotation), we wrap our own client.
"""

import logging
from typing import Any, Iterator
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    BaseMessage,
    AIMessage,
    HumanMessage,
    SystemMessage,
    AIMessageChunk,
)
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.callbacks import CallbackManagerForLLMRun

from app.core.llm_client import llm_client
from app.core.config import settings

logger = logging.getLogger(__name__)


def _convert_messages(messages: list[BaseMessage]) -> list[dict]:
    """Convert LangChain message objects to Groq API format."""
    converted = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            converted.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            converted.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            converted.append({"role": "assistant", "content": msg.content})
        else:
            # Default to user for unknown message types
            converted.append({"role": "user", "content": msg.content})
    return converted


class GroqLangChainLLM(BaseChatModel):
    """
    LangChain-compatible wrapper around our GroqRotatingClient.

    Usage:
        from app.core.langchain_llm import get_llm, get_fast_llm

        llm = get_llm()  # Primary model (70B)
        fast_llm = get_fast_llm()  # Fast model (8B) for routing

        # Use in LangGraph nodes:
        response = llm.invoke([HumanMessage(content="...")])
    """

    model_name: str = ""

    class Config:
        arbitrary_types_allowed = True

    @property
    def _llm_type(self) -> str:
        return "groq-rotating"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate a response using the GroqRotatingClient (non-streaming)."""
        groq_messages = _convert_messages(messages)
        model = self.model_name or None

        # Collect full response from stream
        full_content = ""
        try:
            stream = llm_client.stream(groq_messages, model=model)
            for chunk in stream:
                token = chunk.choices[0].delta.content
                if token:
                    full_content += token
        except RuntimeError as e:
            logger.error(f"[LANGCHAIN_LLM] Generation failed: {e}")
            full_content = f"Error: {str(e)}"

        message = AIMessage(content=full_content)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[AIMessageChunk]:
        """Stream tokens from the GroqRotatingClient."""
        groq_messages = _convert_messages(messages)
        model = self.model_name or None

        try:
            stream = llm_client.stream(groq_messages, model=model)
            for chunk in stream:
                token = chunk.choices[0].delta.content
                if token:
                    yield AIMessageChunk(content=token)
        except RuntimeError as e:
            logger.error(f"[LANGCHAIN_LLM] Stream failed: {e}")
            yield AIMessageChunk(content=f"\n\nError: {str(e)}")


def get_llm() -> GroqLangChainLLM:
    """
    Returns the primary LLM (large model) for specialized agents.
    Uses the 70B model for highest quality responses.
    """
    model = settings.AGENT_MODEL or settings.GROQ_PRIMARY_MODEL
    return GroqLangChainLLM(model_name=model)


def get_fast_llm() -> GroqLangChainLLM:
    """
    Returns the fast LLM (small model) for the router agent.
    Uses the 8B model for speed — routing doesn't need quality.
    """
    model = settings.ROUTER_MODEL or settings.GROQ_FALLBACK_MODEL
    return GroqLangChainLLM(model_name=model)
