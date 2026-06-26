import os
from dataclasses import dataclass

DEFAULT_OPENAI_MODEL = ""
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"


@dataclass(frozen=True)
class AgentLLMSettings:
    provider: str
    openai_api_key: str | None
    openai_model: str
    anthropic_api_key: str | None
    anthropic_model: str
    max_tokens: int
    temperature: float | None


class AgentLLMConfigError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def get_agent_llm_settings() -> AgentLLMSettings:
    return AgentLLMSettings(
        provider=os.environ.get("AGENT_LLM_PROVIDER", "mock").strip().lower(),
        openai_api_key=_blank_to_none(os.environ.get("OPENAI_API_KEY")),
        openai_model=_env_str("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        anthropic_api_key=_blank_to_none(os.environ.get("ANTHROPIC_API_KEY")),
        anthropic_model=_env_str("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL),
        # 1800 だと出力JSONが後方フィールドで切れる(truncation)ため余裕を持たせる
        max_tokens=_env_int("AGENT_LLM_MAX_TOKENS", 4096),
        temperature=_env_float("AGENT_LLM_TEMPERATURE"),
    )


def _blank_to_none(value: str | None) -> str | None:
    if value is None or value.strip() == "":
        return None
    return value.strip()


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        raise AgentLLMConfigError("agent_llm_numeric_env_invalid") from None


def _env_float(name: str) -> float | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        raise AgentLLMConfigError("agent_llm_numeric_env_invalid") from None
