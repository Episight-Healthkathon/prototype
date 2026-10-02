"""LLM configuration (D-18). Keys come only from the environment and are never logged or committed.

Provider resolution with EPISIGHT_LLM_PROVIDER=auto (default): Anthropic if ANTHROPIC_API_KEY is set, else OpenAI
if OPENAI_API_KEY is set, else no LLM (FULL mode then uses the deterministic rule fallback for every step).
"""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Provider(StrEnum):
    AUTO = "auto"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    NONE = "none"


DEFAULT_MODELS = {
    Provider.ANTHROPIC: "claude-opus-5-5",
    # Override with EPISIGHT_LLM_MODEL to any chat model your OpenAI account can use.
    Provider.OPENAI: "gpt-4o",
}


class LlmSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    provider: Provider = Field(default=Provider.AUTO, validation_alias="EPISIGHT_LLM_PROVIDER")
    model: str | None = Field(default=None, validation_alias="EPISIGHT_LLM_MODEL")
    # Anthropic only: thinking depth / cost control. "low" suits a per-step planner.
    effort: str = Field(default="low", validation_alias="EPISIGHT_LLM_EFFORT")
    timeout_s: float = Field(default=30.0, validation_alias="EPISIGHT_LLM_TIMEOUT_S")
    # "off": call the model and record responses; "replay": answer only from recordings (D-21).
    replay: str = Field(default="off", validation_alias="EPISIGHT_LLM_REPLAY")
    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY", repr=False)
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY", repr=False)

    def resolved_provider(self) -> Provider:
        if self.provider == Provider.AUTO:
            if self.anthropic_api_key:
                return Provider.ANTHROPIC
            if self.openai_api_key:
                return Provider.OPENAI
            return Provider.NONE
        if self.provider == Provider.ANTHROPIC and not self.anthropic_api_key and self.replay != "replay":
            return Provider.NONE
        if self.provider == Provider.OPENAI and not self.openai_api_key and self.replay != "replay":
            return Provider.NONE
        return self.provider

    def resolved_model(self, provider: Provider) -> str:
        return self.model or DEFAULT_MODELS.get(provider, "")


@lru_cache
def get_llm_settings() -> LlmSettings:
    return LlmSettings()
