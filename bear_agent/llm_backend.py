"""
LLM backend adapter for Bear Agent.

The agent only needs a chat-completions style interface. Keeping that boundary
small lets us switch from DashScope cloud to a board-local OpenAI-compatible
service without touching the perception, memory, parser, or game-state code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def _env_str(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _env_float(name: str, default: float) -> float:
    raw = _env_str(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = _env_str(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = _env_str(name).lower()
    if raw in TRUE_VALUES:
        return True
    if raw in FALSE_VALUES:
        return False
    return default


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    api_key: str
    base_url: str
    model: str
    temperature: float
    max_tokens: int
    timeout_sec: float
    debug_prompt: bool
    enable_thinking: bool
    send_enable_thinking: bool


def load_llm_settings(config: dict[str, Any]) -> LLMSettings:
    """Merge config.py defaults with environment overrides."""
    provider = _env_str("BEAR_LLM_PROVIDER", str(config.get("provider", "openai_compatible")))
    default_api_key = str(config.get("api_key", ""))
    if provider.lower() == "dashscope":
        default_api_key = _env_str("DASHSCOPE_API_KEY", default_api_key)
    enable_thinking_in_config = "enable_thinking" in config
    send_enable_thinking_default = provider.lower() == "dashscope" or enable_thinking_in_config
    return LLMSettings(
        provider=provider or "openai_compatible",
        api_key=_env_str("BEAR_LLM_API_KEY", default_api_key),
        base_url=_env_str("BEAR_LLM_BASE_URL", str(config.get("base_url", ""))),
        model=_env_str("BEAR_LLM_MODEL", str(config.get("model", ""))),
        temperature=_env_float("BEAR_LLM_TEMPERATURE", float(config.get("temperature", 0.4))),
        max_tokens=_env_int("BEAR_LLM_MAX_TOKENS", int(config.get("max_tokens", 500))),
        timeout_sec=_env_float("BEAR_LLM_TIMEOUT_SEC", float(config.get("timeout_sec", 30.0))),
        debug_prompt=_env_bool("BEAR_LLM_DEBUG_PROMPT", bool(config.get("debug_prompt", False))),
        enable_thinking=_env_bool("BEAR_LLM_ENABLE_THINKING", bool(config.get("enable_thinking", False))),
        send_enable_thinking=_env_bool("BEAR_LLM_SEND_ENABLE_THINKING", send_enable_thinking_default),
    )


class LLMBackend:
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError


class DisabledLLMBackend(LLMBackend):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise RuntimeError("LLM backend is disabled")


class OpenAICompatibleBackend(LLMBackend):
    def __init__(self, settings: LLMSettings) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is required for OpenAI-compatible LLM backend") from exc

        if not settings.base_url:
            raise RuntimeError("BEAR_LLM_BASE_URL or LLM_CONFIG['base_url'] is required")
        if not settings.model:
            raise RuntimeError("BEAR_LLM_MODEL or LLM_CONFIG['model'] is required")

        # Local inference services often accept any non-empty key.
        api_key = settings.api_key or "EMPTY"
        self.settings = settings
        self.client = OpenAI(
            base_url=settings.base_url,
            api_key=api_key,
            timeout=settings.timeout_sec,
        )

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        kwargs: dict[str, Any] = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_tokens,
        }
        if self.settings.send_enable_thinking:
            kwargs["extra_body"] = {"enable_thinking": self.settings.enable_thinking}

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content.strip()


def build_llm_backend(config: dict[str, Any]) -> tuple[LLMSettings, LLMBackend]:
    settings = load_llm_settings(config)
    provider = settings.provider.lower()
    if provider in {"none", "disabled", "rules_only"}:
        return settings, DisabledLLMBackend()
    if provider in {"openai", "openai_compatible", "dashscope", "board_http"}:
        return settings, OpenAICompatibleBackend(settings)
    raise RuntimeError(f"unsupported LLM provider: {settings.provider}")
