"""
UrbanPulse Ollama Client — Dynamic Model Resolution & Three-Level Answering Strategy.

Level 1: Verified UrbanPulse Data  (handled upstream by EvidenceRetriever)
Level 2: Primary model (qwen3:4b) — preferred general + hybrid reasoning
Level 3: Fallback model (mistral or whatever is installed) — if Level 2 fails

Model tags are discovered dynamically from /api/tags so no hardcoded assumptions are made.
"""

import json
import re
import time
import logging
import requests
from typing import Dict, Any, List, Optional, Tuple, Iterator

from backend.app.core.config import settings

logger = logging.getLogger("urbanpulse.intelligence.ollama")

# ── Answer Mode Labels ──────────────────────────────────────────────────────
MODE_VERIFIED   = "Verified UrbanPulse Data"
MODE_HYBRID     = "UrbanPulse Data + AI Analysis"
MODE_GENERAL_AI = "General AI Answer"
MODE_DATA_ONLY  = "Verified UrbanPulse Data (AI Unavailable)"


def _strip_thinking_tags(text: str) -> str:
    """Remove <think>…</think> blocks emitted by Qwen3 in thinking mode."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


class OllamaClient:
    """
    Wraps the Ollama REST API with:
    - Dynamic installed-model discovery
    - Primary → Fallback model selection
    - Per-request timeout (30s)
    - Fallback skipped on primary timeout
    - Streaming response support
    - Graceful degradation when Ollama is offline
    """

    def __init__(self):
        self._installed_models: Optional[List[str]] = None
        self._last_model_refresh: float = 0.0
        self._model_cache_ttl: float = 60.0   # refresh list every 60 s

    # ── Model Discovery ────────────────────────────────────────────────────

    def get_installed_models(self, force_refresh: bool = False) -> List[str]:
        """Returns list of installed model tags from Ollama, with 60-second cache."""
        now = time.time()
        if (
            not force_refresh
            and self._installed_models is not None
            and (now - self._last_model_refresh) < self._model_cache_ttl
        ):
            return self._installed_models

        try:
            resp = requests.get(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags",
                timeout=3
            )
            if resp.status_code == 200:
                models = [m.get("name", "") for m in resp.json().get("models", [])]
                self._installed_models = models
                self._last_model_refresh = now
                logger.debug(f"[OllamaClient] Discovered models: {models}")
                return models
        except Exception as e:
            logger.warning(f"[OllamaClient] Could not reach Ollama: {e}")

        return self._installed_models or []

    def resolve_model(self, preferred: str) -> Optional[str]:
        """
        Finds the best matching installed model for a preferred tag.
        E.g. "qwen3:4b" matches "qwen3:4b", "mistral" matches "mistral:7b", etc.
        Returns None if no suitable model found.
        """
        installed = self.get_installed_models()
        # Exact match first
        if preferred in installed:
            return preferred
        # Prefix match (e.g. "mistral" → "mistral:latest", "mistral:7b")
        base = preferred.split(":")[0].lower()
        for m in installed:
            if m.lower().startswith(base):
                return m
        return None

    def resolve_primary(self) -> Optional[str]:
        """Resolves the configured primary model."""
        return self.resolve_model(settings.OLLAMA_PRIMARY_MODEL)

    def resolve_fallback(self) -> Optional[str]:
        """Resolves the configured fallback model (only if different from primary)."""
        primary = self.resolve_primary()
        fb = self.resolve_model(settings.OLLAMA_FALLBACK_MODEL)
        if fb and fb != primary:
            return fb
        return None

    # ── Chat Call ──────────────────────────────────────────────────────────

    def _chat_internal(
        self,
        model: str,
        system: str,
        user: str,
        temperature: float = 0.3,
        top_p: float = 0.9,
        timeout: Optional[int] = None
    ) -> Tuple[Optional[str], str, bool]:
        """
        Internal chat call returning (clean_text, model, is_timed_out).
        """
        timeout = timeout or settings.OLLAMA_TIMEOUT_SECONDS
        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "stream": False,
            "think": False,
            "keep_alive": "30m",
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_predict": 220,
                "num_ctx": 4096,
            },
        }
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            if resp.status_code == 200:
                raw = resp.json().get("message", {}).get("content", "")
                clean = _strip_thinking_tags(raw)
                return clean, model, False
        except requests.exceptions.Timeout:
            logger.warning(f"[OllamaClient] Timeout calling model '{model}' (>{timeout}s)")
            return None, model, True
        except Exception as e:
            logger.warning(f"[OllamaClient] Chat call failed for model '{model}': {e}")
        return None, model, False

    def chat(
        self,
        model: str,
        system: str,
        user: str,
        temperature: float = 0.3,
        top_p: float = 0.9,
        timeout: Optional[int] = None
    ) -> Tuple[Optional[str], str]:
        """
        Calls Ollama /api/chat with the given model.
        Returns (clean_text, model_used) or (None, model) on failure.
        """
        text, mod, _ = self._chat_internal(model, system, user, temperature, top_p, timeout)
        return text, mod

    def chat_with_fallback(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        top_p: float = 0.9,
    ) -> Tuple[Optional[str], str, str]:
        """
        Tries primary model.
        If primary model times out, skips fallback to minimize latency.
        Otherwise falls back if primary fails or is not found.
        Returns (response_text, model_used, fail_reason).
        """
        primary = self.resolve_primary()
        if primary:
            text, model, timed_out = self._chat_internal(primary, system, user, temperature, top_p)
            if text:
                return text, model, ""
            if timed_out:
                logger.warning(f"[OllamaClient] Primary '{primary}' timed out. Skipping fallback model.")
                return None, "none", "primary_timed_out"

        fallback = self.resolve_fallback()
        if fallback:
            logger.info(f"[OllamaClient] Primary unavailable or failed, trying fallback '{fallback}'")
            text, model, _ = self._chat_internal(fallback, system, user, temperature, top_p)
            if text:
                return text, model, "primary_failed"

        logger.error("[OllamaClient] Both primary and fallback models unavailable")
        return None, "none", "ollama_unavailable"

    # ── Streaming ──────────────────────────────────────────────────────────

    def stream_chat(
        self,
        model: str,
        system: str,
        user: str,
        temperature: float = 0.3,
        top_p: float = 0.9,
        timeout: Optional[int] = None
    ) -> Iterator[str]:
        """
        Streams token deltas from Ollama /api/chat.
        Yields clean delta strings.
        """
        timeout = timeout or settings.OLLAMA_TIMEOUT_SECONDS
        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "stream": True,
            "think": False,
            "keep_alive": "30m",
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_predict": 220,
                "num_ctx": 4096,
            },
        }

        in_think_block = False
        try:
            resp = requests.post(url, json=payload, timeout=timeout, stream=True)
            if resp.status_code != 200:
                logger.warning(f"[OllamaClient] Stream chat non-200: {resp.status_code}")
                return

            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    delta = data.get("message", {}).get("content", "")
                    if not delta:
                        continue

                    # Filter <think> blocks if present in stream
                    if "<think>" in delta:
                        in_think_block = True
                        delta = delta.split("<think>", 1)[0]
                    if in_think_block:
                        if "</think>" in delta:
                            in_think_block = False
                            delta = delta.split("</think>", 1)[1]
                        else:
                            continue

                    if delta:
                        yield delta

                    if data.get("done", False):
                        break
                except Exception:
                    continue
        except requests.exceptions.Timeout:
            logger.warning(f"[OllamaClient] Stream timeout calling model '{model}' (>{timeout}s)")
        except Exception as e:
            logger.warning(f"[OllamaClient] Stream failed for model '{model}': {e}")

    # ── Embedding ──────────────────────────────────────────────────────────

    def embed(self, text: str) -> List[float]:
        """Generates a text embedding using the configured embed model."""
        try:
            resp = requests.post(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/embeddings",
                json={"model": settings.OLLAMA_EMBED_MODEL, "prompt": text},
                timeout=10
            )
            if resp.status_code == 200:
                return resp.json().get("embedding") or []
        except Exception as e:
            logger.debug(f"[OllamaClient] Embedding failed: {e}")
        return []

    # ── Status & Verification ──────────────────────────────────────────────

    def verify_connection(self) -> Tuple[bool, str, Optional[str]]:
        """
        Verifies live connection to Ollama and confirms whether a usable model is present.
        Returns (is_ready, message, active_model_tag).
        """
        try:
            models = self.get_installed_models(force_refresh=True)
            if not models:
                return (
                    False,
                    f"Connected to Ollama at {settings.OLLAMA_BASE_URL}, but no models are installed.",
                    None,
                )

            primary = self.resolve_primary()
            if primary:
                return True, f"Ollama operational. Active model: '{primary}'", primary

            fallback = self.resolve_fallback()
            if fallback:
                return (
                    True,
                    f"Primary model '{settings.OLLAMA_PRIMARY_MODEL}' not found. Using fallback: '{fallback}'",
                    fallback,
                )

            return (
                False,
                f"Neither primary '{settings.OLLAMA_PRIMARY_MODEL}' nor fallback '{settings.OLLAMA_FALLBACK_MODEL}' is installed. Available: {models}",
                None,
            )
        except Exception as e:
            return False, f"Could not reach Ollama at {settings.OLLAMA_BASE_URL}: {e}", None

    def status(self) -> Dict[str, Any]:
        """Returns connection status and model availability."""
        is_ready, verify_msg, active_model = self.verify_connection()
        installed = self.get_installed_models()
        primary   = self.resolve_primary()
        fallback  = self.resolve_fallback()
        return {
            "connected":             is_ready,
            "url":                   settings.OLLAMA_BASE_URL,
            "installed_models":      installed,
            "active_model":          active_model,
            "primary_model":         primary,
            "primary_model_config":  settings.OLLAMA_PRIMARY_MODEL,
            "fallback_model":        fallback,
            "fallback_model_config": settings.OLLAMA_FALLBACK_MODEL,
            "embed_model":           settings.OLLAMA_EMBED_MODEL,
            "timeout_seconds":       settings.OLLAMA_TIMEOUT_SECONDS,
            "verification_message":  verify_msg,
        }


# Module-level singleton
ollama_client = OllamaClient()
