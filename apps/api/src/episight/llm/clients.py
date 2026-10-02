"""Vendor adapters. The only provider-specific code: send (system, user, JSON schema), get JSON text back.

Both adapters ask for schema-constrained JSON (Anthropic structured outputs via output_config.format; OpenAI
response_format json_schema strict). The envelope validates the result again regardless.
"""

import time
from dataclasses import dataclass
from typing import Any, Protocol


class LlmError(Exception):
    """Any failure to obtain a usable answer. The planner falls back to the rule planner on it."""


class LlmRefusal(LlmError):
    pass


@dataclass
class LlmReply:
    text: str
    model: str
    latency_ms: int


class LlmClient(Protocol):
    provider: str
    model: str

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> LlmReply: ...


class AnthropicClient:
    provider = "anthropic"
    # Server-side refusal fallback: a declined request is re-run on Anthropic's recommended model in the same call.
    FALLBACK_BETA = "server-side-fallback-2026-07-01"

    def __init__(
        self,
        model: str,
        effort: str = "low",
        timeout_s: float = 30.0,
        api_key: str | None = None,
        sdk_client: Any = None,
    ):
        import anthropic

        self._anthropic = anthropic
        self.model = model
        self.effort = effort
        self.client = sdk_client or anthropic.Anthropic(api_key=api_key, timeout=timeout_s, max_retries=1)

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> LlmReply:
        a = self._anthropic
        started = time.perf_counter()
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=4096,
                betas=[self.FALLBACK_BETA],
                fallbacks="default",
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": schema}},
            )
        except a.AuthenticationError as exc:
            raise LlmError("Anthropic authentication failed (check ANTHROPIC_API_KEY)") from exc
        except a.NotFoundError as exc:
            raise LlmError(f"Anthropic model not found: {self.model} (check EPISIGHT_LLM_MODEL)") from exc
        except a.RateLimitError as exc:
            raise LlmError("Anthropic rate limit reached") from exc
        except (a.APIConnectionError, a.APITimeoutError) as exc:
            raise LlmError("Anthropic API unreachable or timed out") from exc
        except a.APIStatusError as exc:
            raise LlmError(f"Anthropic API error {exc.status_code}") from exc
        latency = int((time.perf_counter() - started) * 1000)
        if response.stop_reason == "refusal":
            raise LlmRefusal("Anthropic declined the request")
        if response.stop_reason == "max_tokens":
            raise LlmError("Anthropic response truncated (max_tokens)")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            raise LlmError("Anthropic returned no text block")
        return LlmReply(text=text, model=response.model or self.model, latency_ms=latency)


class OpenAIClient:
    provider = "openai"

    def __init__(self, model: str, timeout_s: float = 30.0, api_key: str | None = None, sdk_client: Any = None):
        import openai

        self._openai = openai
        self.model = model
        self.client = sdk_client or openai.OpenAI(api_key=api_key, timeout=timeout_s, max_retries=1)

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> LlmReply:
        o = self._openai
        started = time.perf_counter()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "planner_decision", "strict": True, "schema": schema},
                },
                max_completion_tokens=2000,
            )
        except o.AuthenticationError as exc:
            raise LlmError("OpenAI authentication failed (check OPENAI_API_KEY)") from exc
        except o.NotFoundError as exc:
            raise LlmError(f"OpenAI model not found: {self.model} (check EPISIGHT_LLM_MODEL)") from exc
        except o.RateLimitError as exc:
            raise LlmError("OpenAI rate limit reached") from exc
        except (o.APIConnectionError, o.APITimeoutError) as exc:
            raise LlmError("OpenAI API unreachable or timed out") from exc
        except o.APIStatusError as exc:
            raise LlmError(f"OpenAI API error {exc.status_code}") from exc
        latency = int((time.perf_counter() - started) * 1000)
        choice = response.choices[0]
        if getattr(choice.message, "refusal", None):
            raise LlmRefusal("OpenAI declined the request")
        if choice.finish_reason == "length":
            raise LlmError("OpenAI response truncated (length)")
        if not choice.message.content:
            raise LlmError("OpenAI returned no content")
        return LlmReply(text=choice.message.content, model=response.model or self.model, latency_ms=latency)
