"""
core/llm_client.py — Groq Client with Automatic Key Rotation
=============================================================
🎓 LEARNING: This implements two important production patterns:

1. API KEY ROTATION
   When you have multiple free-tier API keys, you can spread requests
   across them to stay within each account's rate limits.
   
   We use a round-robin strategy — cycle through keys in order.
   On a 429 (rate limit) error, we immediately try the next key.
   This is exactly how production systems like Vercel handle API limits.

2. FALLBACK MODEL
   If the primary model (70B, higher quality) is rate-limited on ALL keys,
   we fall back to the faster/smaller model (8B, lower rate limits).
   
   This is the "graceful degradation" principle:
   better to give a slightly lower-quality answer than no answer at all.

CIRCUIT BREAKER:
   After trying all keys with all models and still failing,
   we raise a clear error. The user sees a friendly message
   instead of a timeout or crash.

HOW RATE LIMITS WORK ON GROQ FREE TIER:
   Each key has limits like: 6000 tokens/min, 500 requests/day
   By rotating across 3 keys, you effectively get:
   18000 tokens/min, 1500 requests/day — 3x the capacity!
"""

import time
import logging
from groq import Groq, RateLimitError, APIStatusError
from app.core.config import settings

logger = logging.getLogger(__name__)


class GroqRotatingClient:
    """
    A Groq client that automatically rotates through multiple API keys
    when rate limits are hit, and falls back to a smaller model if needed.
    
    🎓 LEARNING: This is a wrapper class — it wraps the official Groq SDK
    and adds our rotation logic on top. The rest of the app doesn't need
    to know that rotation is happening — it just calls .stream() and gets
    tokens back.
    
    This is the "Decorator Pattern" in software engineering.
    """
    
    def __init__(self):
        keys = settings.groq_keys_list
        
        if not keys:
            raise ValueError(
                "No Groq API keys configured! "
                "Add GROQ_API_KEYS=key1,key2,key3 to your .env file. "
                "Get free keys at https://console.groq.com"
            )
        
        # Create one Groq client instance per key
        # 🎓 LEARNING: Creating clients upfront is faster than creating them
        # on each request. This is called "connection pooling" — we reuse
        # established clients rather than creating new ones every time.
        self._clients = [Groq(api_key=key) for key in keys]
        self._current_index = 0
        self._key_count = len(self._clients)
        
        logger.info(
            f"[GROQ] Initialized with {self._key_count} API key(s). "
            f"Primary model: {settings.GROQ_PRIMARY_MODEL}"
        )
    
    def _advance_key(self):
        """Move to the next API key (round-robin)."""
        self._current_index = (self._current_index + 1) % self._key_count
    
    def _current_client(self) -> Groq:
        return self._clients[self._current_index]
    
    def stream(self, messages: list[dict], model: str = None) -> any:
        """
        Sends a chat completion request and returns a streaming iterator.
        Automatically rotates keys on RateLimitError (HTTP 429).
        
        🎓 LEARNING: The caller uses this like:
            for chunk in llm_client.stream(messages):
                token = chunk.choices[0].delta.content
        
        We try each key once. If ALL keys for the primary model are
        rate-limited, we retry with the fallback (smaller) model.
        
        Args:
            messages: List of {"role": "user"/"system", "content": "..."} dicts
            model:    Override model (optional; defaults to primary model)
        
        Returns:
            A Groq streaming iterator
        
        Raises:
            RuntimeError: If all keys and all models are exhausted
        """
        primary = model or settings.GROQ_PRIMARY_MODEL
        
        # --- Try primary model, rotating through all keys ---
        result = self._try_all_keys(messages, primary)
        if result is not None:
            return result
        
        # --- All keys rate-limited on primary model; try fallback model ---
        if settings.GROQ_FALLBACK_MODEL != primary:
            logger.warning(
                f"[GROQ] All {self._key_count} keys rate-limited on '{primary}'. "
                f"Falling back to '{settings.GROQ_FALLBACK_MODEL}'..."
            )
            result = self._try_all_keys(messages, settings.GROQ_FALLBACK_MODEL)
            if result is not None:
                return result
        
        raise RuntimeError(
            "All Groq API keys are rate-limited on all models. "
            "Please wait a minute before retrying, or add more API keys."
        )
    
    def _try_all_keys(self, messages: list[dict], model: str) -> any:
        """
        Tries every available key once for the given model.
        Returns the stream on success, None if all keys are rate-limited.
        """
        start_index = self._current_index
        
        for attempt in range(self._key_count):
            key_num = self._current_index + 1  # 1-indexed for human-readable logs
            try:
                logger.info(f"[GROQ] Trying key {key_num}/{self._key_count}, model={model}")
                
                stream = self._current_client().chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True,
                    temperature=0.1,     # Low temperature = more factual, less creative
                    max_tokens=2048,
                )
                
                logger.info(f"[GROQ] ✅ Success with key {key_num}, model={model}")
                return stream
                
            except RateLimitError:
                logger.warning(
                    f"[GROQ] ⚠️ Key {key_num} rate-limited on model={model}. "
                    f"Rotating to next key..."
                )
                self._advance_key()
                
            except APIStatusError as e:
                # Non-rate-limit API errors (e.g. invalid key, model not found)
                # These won't be fixed by rotating keys, so raise immediately
                logger.error(f"[GROQ] API error on key {key_num}: {e.status_code} {e.message}")
                raise
        
        # All keys tried for this model — return None to signal exhaustion
        return None


# ============================================================
# Module-level singleton
# 🎓 LEARNING: We create ONE instance of GroqRotatingClient
# when the module is first imported. All parts of the app
# share this same instance, so the key rotation state
# (self._current_index) is preserved across requests.
# If each request created its own client, rotation would reset every time!
# ============================================================
llm_client = GroqRotatingClient()
