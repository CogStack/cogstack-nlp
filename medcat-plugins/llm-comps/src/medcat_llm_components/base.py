"""LLM-based entity provider components for MedCAT (proof of concept).

Targets the OpenAI-compatible chat-completions wire format
(`POST {base_url}/chat/completions`), since that's the lowest common
denominator for locally-hosted LLM servers - Ollama, vLLM, llama.cpp's
server, LM Studio, TGI, text-generation-webui - either natively or via
an OpenAI-compat mode. It also happens to cover hosted providers
(OpenAI, Groq, Together, OpenRouter, ...) for free, but that's a
secondary benefit, not the design target.

Layout:
    LLMConnectionConfig / AbstractLLMEntityComponent
        - shared: client construction, retries, structured-output
          negotiation with fallback, response-text cleanup
    LLMNERConfig / MyLLMNER
        - NER step (ents=None): freeform CSV prompt + span
          reconciliation against the doc
    LLMLinkConfig / MyLLMLinker
        - linking step (ents given): structured-output-first, since
          constraining the model to a candidate list is exactly what
          it's good at
"""
# from __future__ import annotations

import logging
import re
import time
from abc import ABC
from typing import Any

from medcat.components.types import AbstractEntityProvidingComponent
from medcat.config.config import ComponentConfig
from openai import APIConnectionError, APIError, APITimeoutError, OpenAI

logger = logging.getLogger(__name__)


class UnknownSpanException(ValueError):
    """Raised when an LLM-reported span can't be reconciled with the source text."""


class _StructuredOutputUnsupported(Exception):
    """Internal signal: backend rejected response_format; retry freeform."""


def _looks_like_unsupported_response_format(exc: Exception) -> bool:
    # NOTE: heuristic. Backends don't agree on a dedicated error type for
    # "I don't support response_format" - they just 400 with varying
    # messages. This is best-effort, not a contract; if you hit a backend
    # that phrases it differently, structured output will look like a
    # hard failure instead of falling back. Worth tightening once you
    # know which backends you actually need to support.
    msg = str(exc).lower()
    return any(s in msg for s in (
        "response_format", "json_schema", "unsupported", "not supported"))


# ---------------------------------------------------------------------------
# Shared plumbing
# ---------------------------------------------------------------------------

class LLMConnectionConfig(ComponentConfig):
    """Everything needed to talk to an OpenAI-compatible chat endpoint.

    Shared by every LLM-based component regardless of task. Task
    configs (LLMNERConfig, LLMLinkConfig) inherit from this.
    """
    base_url: str
    api_key: str = "not-needed"  # most local servers ignore it, but the SDK requires a non-empty string
    model: str
    timeout: float = 60.0
    retries: int = 1
    retry_backoff_seconds: float = 1.0
    temperature: float = 0.0
    use_structured_output: bool = True


class AbstractLLMEntityComponent(AbstractEntityProvidingComponent, ABC):
    """Shared connection / chat / cleanup plumbing for LLM-based components.

    Subclasses own the prompt, the (optional) response schema, and
    turning the model's response into MedCAT entities.
    """

    def __init__(self, cnf: LLMConnectionConfig) -> None:
        super().__init__()
        self.cnf = cnf
        self._client = OpenAI(base_url=cnf.base_url, api_key=cnf.api_key)
        # once a backend tells us it doesn't support structured output,
        # don't keep paying a failed round-trip to rediscover that
        self._structured_output_supported = cnf.use_structured_output

    def _chat(self, prompt: str, schema: dict[str, Any] | None = None) -> str:
        """Send `prompt` as a single user message, return the raw text
        response. `schema`, if given, requests structured output for
        this call specifically (falls back to freeform if the backend
        rejects it). Retries transient connection/timeout failures."""
        use_schema = schema if self._structured_output_supported else None

        last_exc: Exception | None = None
        for attempt in range(self.cnf.retries + 1):
            try:
                return self._one_call(prompt, use_schema)
            except _StructuredOutputUnsupported:
                logger.warning(
                    "%s: backend rejected structured output, falling "
                    "back to freeform for the rest of this session",
                    self.cnf.comp_name)
                self._structured_output_supported = False
                use_schema = None
                continue  # retry immediately, don't burn a retry slot on this
            except (APIConnectionError, APITimeoutError, APIError) as exc:
                last_exc = exc
                logger.warning(
                    "%s: LLM call failed (attempt %d/%d): %s",
                    self.cnf.comp_name, attempt + 1, self.cnf.retries + 1, exc)
                if attempt < self.cnf.retries:
                    time.sleep(self.cnf.retry_backoff_seconds)
        assert last_exc is not None
        raise last_exc

    def _one_call(self, prompt: str, schema: dict[str, Any] | None) -> str:
        kwargs: dict[str, Any] = {
            "model": self.cnf.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.cnf.temperature,
            "timeout": self.cnf.timeout,
        }
        if schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": schema, "strict": True},
            }
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except APIError as exc:
            if schema is not None and _looks_like_unsupported_response_format(exc):
                raise _StructuredOutputUnsupported from exc
            raise
        return resp.choices[0].message.content or ""

    _FENCE_RE = re.compile(r"^```[a-zA-Z]*\n|\n```$")

    def _clean_response(self, raw: str) -> str:
        text = raw.strip()
        # models wrap output in ```csv/```json fences despite instructions not to
        text = self._FENCE_RE.sub("", text).strip()
        return text

class MisconfiguredComponentException(ValueError):
    pass
