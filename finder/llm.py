"""Provider-agnostic LLM layer for the Opportunity Finder.

The model IS the engine: given a person's profile, it finds and explains
opportunities directly. There is no separate web-scrape step — the value is the
model's reasoning, not a keyword dump.

  anthropic → Claude runs its native `web_search` tool (real, currently-open
              listings) and curates them.
  openai    → any OpenAI-compatible chat model (OpenAI, OpenRouter, Groq, Ollama,
              LM Studio, vLLM, llama.cpp via LLM_BASE_URL) discovers from its
              knowledge. Without live web access it can be less current, so it is
              told to prefer real, official sources and never fabricate URLs.

Config comes from the environment (or is passed in explicitly):

    LLM_PROVIDER = anthropic | openai      (auto-detected from whichever key is set)
    LLM_MODEL    = model id (provider-specific defaults below)
    LLM_BASE_URL = base URL override — the lever for local / alternative hosts
    LLM_API_KEY  = api key (falls back to ANTHROPIC_API_KEY / OPENAI_API_KEY)

SDKs are imported lazily, so a user who only wants Ollama never installs
`anthropic`, and vice versa.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

WEB_SEARCH_TOOL = "web_search_20260209"  # Claude native web search (Opus 4.6+/Sonnet 4.6)
DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-8"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

Card = dict[str, str]


@dataclass
class LLMConfig:
    provider: str  # "anthropic" | "openai" | "none" (none = unconfigured)
    model: str
    base_url: str | None
    api_key: str | None
    warning: str | None = None  # set when config was coerced (e.g. unknown provider)

    @property
    def enabled(self) -> bool:
        return self.provider in ("anthropic", "openai")


def _detect_provider() -> str:
    """Pick a provider when LLM_PROVIDER is unset: prefer whatever key is present."""
    explicit = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if explicit:
        return explicit
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_BASE_URL"):
        return "openai"
    return "none"


def load_config() -> LLMConfig:
    provider = _detect_provider()
    warning: str | None = None
    if provider not in ("anthropic", "openai", "none"):
        warning = (
            f"Unknown LLM_PROVIDER={provider!r}. Set it to anthropic or openai."
        )
        provider = "none"

    base_url = os.environ.get("LLM_BASE_URL") or None
    explicit_key = os.environ.get("LLM_API_KEY") or None

    if provider == "anthropic":
        model = os.environ.get("LLM_MODEL") or DEFAULT_ANTHROPIC_MODEL
        api_key = explicit_key or os.environ.get("ANTHROPIC_API_KEY")
    elif provider == "openai":
        model = os.environ.get("LLM_MODEL") or DEFAULT_OPENAI_MODEL
        # Local OpenAI-compatible servers ignore the key but the SDK requires a
        # non-empty string — fall back to a placeholder when a base_url is set.
        api_key = explicit_key or os.environ.get("OPENAI_API_KEY")
        if not api_key and base_url:
            api_key = "not-needed"
    else:  # none — unconfigured
        model, api_key = "", None

    return LLMConfig(
        provider=provider, model=model, base_url=base_url, api_key=api_key, warning=warning
    )


DISCOVER_SYSTEM = (
    "You are an opportunity-matching assistant. Given a person's background, goals, "
    "and category, find concrete, currently-open opportunities that genuinely fit "
    "them — jobs, internships, graduate programs, fellowships, gap-year programs, or "
    "travel/volunteer programs as the category dictates. Prefer official sources "
    "(employer career pages, university admissions, program sites) over aggregators. "
    "If you are not certain a specific posting is currently open, name the program or "
    "organization and link its official site rather than inventing a deep link. "
    "Never fabricate URLs. For each pick, explain why it fits this person specifically. "
    'Return ONLY a JSON array. Each item: {"title": str, "url": str, "summary": str, '
    '"why_match": str}. No prose outside the JSON.'
)


def _profile_block(profile: dict[str, Any]) -> str:
    parts = [f"Category: {profile.get('category', 'Opportunities')}"]
    if profile.get("role"):
        parts.append(f"Role: {profile['role']}")
    if profile.get("field"):
        parts.append(f"Field: {profile['field']}")
    if profile.get("location"):
        parts.append(f"Location: {profile['location']}")
    if profile.get("resume_text"):
        parts.append(f"Resume:\n{profile['resume_text']}")
    if profile.get("context"):
        parts.append(f"Context document:\n{profile['context']}")
    if profile.get("background"):
        parts.append(f"Background:\n{profile['background']}")
    if profile.get("goals"):
        parts.append(f"Goals:\n{profile['goals']}")
    return "\n\n".join(parts)


def _extract_json(text: str) -> list[Card]:
    """Pull the first JSON array out of a model reply. Robust to chatty local models."""
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[Card] = []
    for item in data:
        if isinstance(item, dict) and item.get("title") and item.get("url"):
            out.append(
                {
                    "title": str(item.get("title", "")),
                    "url": str(item.get("url", "")),
                    "summary": str(item.get("summary", "")),
                    "why_match": str(item.get("why_match", "")),
                }
            )
    return out


def _prompt(profile: dict, max_results: int) -> str:
    return (
        f"{_profile_block(profile)}\n\nFind up to {max_results} opportunities that fit. "
        f"Return a JSON array only."
    )


# --- Anthropic (native web search) -------------------------------------------

def _anthropic_client(cfg: LLMConfig):
    try:
        from anthropic import Anthropic
    except ImportError as e:  # pragma: no cover - install-time guidance
        raise RuntimeError(
            'Anthropic backend selected but the SDK is missing. Run: pip install "anthropic>=0.40.0"'
        ) from e
    if not cfg.api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY missing. Set it in .env or export ANTHROPIC_API_KEY."
        )
    return Anthropic(api_key=cfg.api_key)


def _anthropic_discover(cfg: LLMConfig, profile: dict, max_results: int) -> list[Card]:
    client = _anthropic_client(cfg)
    response = client.messages.create(
        model=cfg.model,
        max_tokens=4096,
        system=DISCOVER_SYSTEM,
        tools=[{"type": WEB_SEARCH_TOOL, "name": "web_search", "max_uses": 5}],
        messages=[{"role": "user", "content": _prompt(profile, max_results)}],
    )
    text = "\n".join(
        b.text for b in response.content if getattr(b, "type", None) == "text"
    )
    return _extract_json(text)[:max_results]


# --- OpenAI-compatible (covers local OSS models too) -------------------------

def _openai_client(cfg: LLMConfig):
    try:
        from openai import OpenAI
    except ImportError as e:  # pragma: no cover - install-time guidance
        raise RuntimeError(
            'OpenAI-compatible backend selected but the SDK is missing. Run: pip install "openai>=1.0.0"'
        ) from e
    if not cfg.api_key:
        raise RuntimeError(
            "No API key. Set LLM_API_KEY / OPENAI_API_KEY, or LLM_BASE_URL for a local server."
        )
    return OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)


def _openai_discover(cfg: LLMConfig, profile: dict, max_results: int) -> list[Card]:
    client = _openai_client(cfg)
    # No response_format / json_object: many local servers (Ollama, llama.cpp)
    # reject it. Instruct + parse defensively instead.
    response = client.chat.completions.create(
        model=cfg.model,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": DISCOVER_SYSTEM},
            {"role": "user", "content": _prompt(profile, max_results)},
        ],
    )
    return _extract_json(response.choices[0].message.content or "")[:max_results]


# --- Public API --------------------------------------------------------------

def discover_opportunities(
    profile: dict[str, Any],
    *,
    cfg: LLMConfig | None = None,
    max_results: int = 8,
) -> list[Card]:
    """Find + explain opportunities with the configured model."""
    cfg = cfg or load_config()
    if cfg.provider == "anthropic":
        return _anthropic_discover(cfg, profile, max_results)
    if cfg.provider == "openai":
        return _openai_discover(cfg, profile, max_results)
    raise RuntimeError(
        "No model configured. Choose a backend (Claude, OpenAI, or a local model) — "
        "the finder needs an LLM."
    )
