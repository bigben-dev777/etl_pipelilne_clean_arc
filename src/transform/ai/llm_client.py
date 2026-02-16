"""LLM client wrapper with caching, retry, and cost control."""

import hashlib
import json
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

# Try to import LLM libraries
try:
    import openai

    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import anthropic

    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    from google import genai

    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def complete(self, prompt: str, **kwargs) -> str:
        """Send a completion request."""
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    def __init__(
        self, api_key: str, model: str = "gpt-4o-mini", temperature: float = 0.0
    ):
        if not HAS_OPENAI:
            raise ImportError("openai package not installed")

        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.total_tokens = 0

    def complete(self, prompt: str, max_tokens: int = 4000, **kwargs) -> str:
        """Send completion request to OpenAI."""
        logger.info(f"🌐 Call OpenAI with model {self.model}")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_completion_tokens=max_tokens,
            **kwargs,
        )

        self.total_tokens += response.usage.total_tokens
        logger.info(
            f"🚀    {self.client._base_url} - {self.model} - {self.temperature}"
        )
        logger.info(
            f"🚀    OpenAI call successful: {response.usage.total_tokens} tokens used"
        )

        return response.choices[0].message.content

    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken."""
        try:
            import tiktoken

            encoding = tiktoken.encoding_for_model(self.model)
            return len(encoding.encode(text))
        except:
            # Fallback: rough estimate
            return int(len(text.split()) * 1.3)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-haiku-20240307",
        temperature: float = 0.0,
    ):
        if not HAS_ANTHROPIC:
            raise ImportError("anthropic package not installed")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.total_tokens = 0

    def complete(self, prompt: str, max_tokens: int = 4000, **kwargs) -> str:
        """Send completion request to Anthropic."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )

        self.total_tokens += response.usage.input_tokens + response.usage.output_tokens

        return response.content[0].text

    def count_tokens(self, text: str) -> int:
        """Count tokens (rough estimate)."""
        return int(len(text.split()) * 1.3)


class GeminiProvider(LLMProvider):
    """Google Gemini provider using google-genai SDK."""

    def __init__(
        self, api_key: str, model: str = "gemini-1.5-flash", temperature: float = 0.0
    ):
        if not HAS_GEMINI:
            raise ImportError("google-genai package not installed")

        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.total_tokens = 0

    def complete(self, prompt: str, max_tokens: int = 4000, **kwargs) -> str:
        """Send completion request to Gemini."""
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=self.temperature, max_output_tokens=max_tokens, **kwargs
            ),
        )

        # Token tracking (if usage metadata available)
        usage = getattr(response, "usage_metadata", None)
        if usage:
            self.total_tokens += getattr(usage, "prompt_token_count", 0) + getattr(
                usage, "candidates_token_count", 0
            )

        if response.text == None:
            return ""
        return response.text

    def count_tokens(self, text: str) -> int:
        """Count tokens using Gemini tokenizer if available."""
        try:
            response = self.client.models.count_tokens(model=self.model, contents=text)

            if response.total_tokens is None:
                return 0
            else:
                return response.total_tokens
        except Exception:
            return int(len(text.split()) * 1.3)


class LocalProvider(LLMProvider):
    """Local GPT-OSS provider via OpenAI-compatible vLLM."""

    def __init__(
        self,
        base_url: str = "http://172.20.1.106:8000/v1",
        model: str = "Qwen3-4B",
        temperature: float = 0.0,
    ):
        self.client = openai.OpenAI(
            base_url=base_url,
            api_key="EMPTY",  # required but ignored
        )
        self.model = model
        self.temperature = temperature
        self.total_tokens = 0

    def complete(self, prompt: str, max_tokens: int = 3000, **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_completion_tokens=max_tokens,
            **kwargs,
        )
        # Remove <think> tags if present in response
        if hasattr(response, "choices") and response.choices:
            content = response.choices[0].message.content
            if "<think>" in content:
                content = content.split("</think>")[-1].strip()
                response.choices[0].message.content = content
        if response.usage:
            self.total_tokens += response.usage.total_tokens

        return response.choices[0].message.content

    def count_tokens(self, text: str) -> int:
        return int(len(text.split()) * 1.3)


class LLMClient:
    """
    LLM client wrapper with caching, retry, and cost control.

    Features:
    - Response caching by input hash
    - Automatic retry with exponential backoff
    - Token usage tracking and budget enforcement
    - Batch request support
    - Fallback to rule-based when LLM unavailable
    """

    def __init__(
        self,
        provider: str = "openai",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        enable_caching: bool = True,
        max_calls_per_run: int = 100,
        cache_ttl_seconds: int = 86400,  # 24 hours
    ):
        """
        Initialize the LLM client.

        Args:
            provider: LLM provider ("openai" or "anthropic")
            api_key: API key (defaults to env var)
            model: Model name (provider-specific default if None)
            temperature: Sampling temperature
            enable_caching: Whether to cache responses
            max_calls_per_run: Maximum API calls per run
            cache_ttl_seconds: Cache time-to-live in seconds
        """
        self.provider_name = provider
        self.enable_caching = enable_caching
        self.max_calls_per_run = max_calls_per_run
        self.cache_ttl_seconds = cache_ttl_seconds

        self._cache: Dict[str, Dict[str, Any]] = {}
        self._call_count = 0
        self._fallback_enabled = True

        # Initialize provider
        self.provider = self._create_provider(provider, api_key, model, temperature)

    def _create_provider(
        self,
        provider: str,
        api_key: Optional[str],
        model: Optional[str],
        temperature: float,
    ) -> Optional[LLMProvider]:
        """Create the LLM provider."""
        if provider == "openai":
            if not api_key:
                api_key = __import__("os").getenv("OPENAI_API_KEY")
            if not api_key:
                logger.warning("OpenAI API key not found")
                return None

            model = model or "gpt-4o-mini"
            return OpenAIProvider(api_key, model, temperature)

        elif provider == "anthropic":
            if not api_key:
                api_key = __import__("os").getenv("ANTHROPIC_API_KEY")
            if not api_key:
                logger.warning("Anthropic API key not found")
                return None

            model = model or "claude-3-haiku-20240307"
            return AnthropicProvider(api_key, model, temperature)

        elif provider == "gemini":
            if not api_key:
                api_key = __import__("os").getenv("GEMINI_API_KEY")
            if not api_key:
                logger.warning("Gemini API key not found")
                return None

            model = model or "gemini-1.5-flash"
            return GeminiProvider(api_key, model, temperature)

        elif provider == "local":
            model = model or "Qwen3-4B"
            return LocalProvider(model=model, temperature=temperature)

        else:
            raise ValueError(f"Unknown provider: {provider}")

    def complete(self, prompt: str, use_cache: bool = True, **kwargs) -> str:
        """
        Send a completion request with caching and retry.

        Args:
            prompt: The prompt to send
            use_cache: Whether to use caching for this call
            **kwargs: Additional provider-specific options

        Returns:
            LLM response text
        """
        # Check call limit
        if self._call_count >= self.max_calls_per_run:
            logger.warning(
                f"Max calls ({self.max_calls_per_run}) reached, using fallback"
            )
            return self._fallback_response(prompt)

        # Check cache
        if use_cache and self.enable_caching:
            cache_key = self._compute_cache_key(prompt)
            cached = self._get_from_cache(cache_key)
            if cached:
                logger.debug("Cache hit for prompt")
                return cached

        # Check if provider is available
        if not self.provider:
            logger.warning("LLM provider not available, using fallback")
            return self._fallback_response(prompt)

        # Make API call with retry
        try:
            response = self._call_with_retry(prompt, **kwargs)

            # Cache response
            if use_cache and self.enable_caching:
                self._add_to_cache(cache_key, response)

            self._call_count += 1

            return response

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            if self._fallback_enabled:
                return self._fallback_response(prompt)
            raise

    def _call_with_retry(self, prompt: str, max_retries: int = 3, **kwargs) -> str:
        """Call LLM with exponential backoff retry."""
        for attempt in range(max_retries):
            try:
                if self.provider is None:
                    raise Exception("LLM provider not initialized")

                return self.provider.complete(prompt, **kwargs)
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2**attempt  # Exponential backoff
                    logger.warning(f"LLM call failed, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    raise

        raise Exception("Max retries exceeded")

    def batch_complete(
        self, prompts: List[str], batch_size: int = 10, **kwargs
    ) -> List[str]:
        """
        Process multiple prompts efficiently.

        Args:
            prompts: List of prompts
            batch_size: Number of prompts to combine (if supported)
            **kwargs: Additional options

        Returns:
            List of responses
        """
        responses = []

        for prompt in prompts:
            response = self.complete(prompt, **kwargs)
            responses.append(response)

        return responses

    def _compute_cache_key(self, prompt: str) -> str:
        """Compute cache key for a prompt."""
        return hashlib.sha256(prompt.encode()).hexdigest()[:32]

    def _get_from_cache(self, key: str) -> Optional[str]:
        """Get cached response if not expired."""
        if key not in self._cache:
            return None

        entry = self._cache[key]
        if time.time() - entry["timestamp"] > self.cache_ttl_seconds:
            del self._cache[key]
            return None

        return entry["response"]

    def _add_to_cache(self, key: str, response: str) -> None:
        """Add response to cache."""
        self._cache[key] = {"response": response, "timestamp": time.time()}

    def _fallback_response(self, prompt: str) -> str:
        """Generate fallback response when LLM is unavailable."""
        logger.warning("Using fallback response")

        # Try to extract what kind of response is expected
        if '"mappings"' in prompt.lower():
            return '{"mappings": {}, "confidence": 0.0, "note": "fallback_response"}'
        elif '"category"' in prompt.lower():
            return '[{"index": 1, "category": "Other", "confidence": 0.5, "note": "fallback"}]'
        elif '"is_same"' in prompt.lower() or '"is_same_entity"' in prompt.lower():
            return '[{"pair_id": 1, "is_same": false, "confidence": 0.5, "note": "fallback"}]'

        return '{"note": "fallback_response", "data": []}'

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        stats = {
            "calls_made": self._call_count,
            "calls_remaining": self.max_calls_per_run - self._call_count,
            "cache_entries": len(self._cache),
        }

        if self.provider:
            stats["total_tokens"] = getattr(self.provider, "total_tokens", 0)

        return stats

    def clear_cache(self) -> None:
        """Clear the response cache."""
        self._cache.clear()


# Global client instance
_llm_client: Optional[LLMClient] = None


def get_llm_client(
    provider: str = "openai", api_key: Optional[str] = None, **kwargs
) -> LLMClient:
    """Get or create the global LLM client instance."""
    global _llm_client

    if _llm_client is None:
        _llm_client = LLMClient(provider=provider, api_key=api_key, **kwargs)

    return _llm_client
