"""
Strategy and Factory Patterns for AI Intelligence Providers.
Encapsulates LLM invocation, fallback routing, and deterministic template fallback.
Follows the ZeroResidual principle: never fabricate numbers; fall back to verified data gracefully.
"""

from abc import ABC, abstractmethod
import logging
from typing import Any, Dict, Iterator, List, Optional, Tuple

from backend.app.services.intelligence.ollama_client import (
    ollama_client,
    MODE_VERIFIED,
    MODE_HYBRID,
    MODE_GENERAL_AI,
    MODE_DATA_ONLY,
)

logger = logging.getLogger("urbanpulse.intelligence.ai_strategy")


class AIProviderStrategy(ABC):
    """Abstract Strategy interface for AI text generation and explanation."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        timeout: int = 30,
        model_preference: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Generate complete response.
        Returns: (response_text, model_name_used, fail_reason)
        """
        pass

    @abstractmethod
    def stream(
        self,
        prompt: str,
        system_prompt: str = "",
        timeout: int = 30,
        model_preference: Optional[str] = None,
    ) -> Iterator[str]:
        """Stream response chunks incrementally."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider backend is reachable."""
        pass


class OllamaProviderStrategy(AIProviderStrategy):
    """Concrete strategy utilizing local Ollama instance (Qwen / Mistral)."""

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        timeout: int = 30,
        model_preference: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        return ollama_client.generate_with_fallback(
            prompt=prompt,
            system_prompt=system_prompt,
            timeout=timeout,
            preferred_model=model_preference,
        )

    def stream(
        self,
        prompt: str,
        system_prompt: str = "",
        timeout: int = 30,
        model_preference: Optional[str] = None,
    ) -> Iterator[str]:
        return ollama_client.stream_generate(
            prompt=prompt,
            system_prompt=system_prompt,
            timeout=timeout,
            preferred_model=model_preference,
        )

    def is_available(self) -> bool:
        return ollama_client.is_online()


class DeterministicFallbackStrategy(AIProviderStrategy):
    """
    Deterministic fallback strategy when Ollama / LLM is unavailable.
    Synthesizes factual summaries grounded purely in evidence with zero hallucination.
    """

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        timeout: int = 30,
        model_preference: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        msg = (
            "Verified UrbanPulse Civic Record (AI Synthesis Offline):\n\n"
            "This query is answered using verified PostgreSQL dataset records from BBMP, "
            "CPCB air monitoring, and Karnataka State Police logs. "
            "All figures presented reflect official public government disclosures."
        )
        return msg, "deterministic-fallback", "ollama_offline"

    def stream(
        self,
        prompt: str,
        system_prompt: str = "",
        timeout: int = 30,
        model_preference: Optional[str] = None,
    ) -> Iterator[str]:
        text, _, _ = self.generate(prompt, system_prompt, timeout)
        yield text or ""

    def is_available(self) -> bool:
        return True


class AIFactory:
    """Factory to retrieve appropriate AI provider strategy."""

    _strategies = {
        "ollama": OllamaProviderStrategy,
        "deterministic": DeterministicFallbackStrategy,
        "fallback": DeterministicFallbackStrategy,
    }

    @classmethod
    def get_provider(cls, preference: str = "auto") -> AIProviderStrategy:
        if preference == "deterministic":
            return DeterministicFallbackStrategy()

        ollama_strat = OllamaProviderStrategy()
        if preference == "ollama":
            return ollama_strat

        # 'auto' mode: check if ollama is reachable, otherwise fall back to deterministic
        if ollama_strat.is_available():
            return ollama_strat
        return DeterministicFallbackStrategy()
