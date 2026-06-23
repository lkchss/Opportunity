"""Provider-agnostic LLM layer for the Opportunity Finder.

The finder separates SEARCH (DuckDuckGo — universal, no key) from REASON (this
module — pluggable). That split is what makes the tool backend-agnostic: the
model never needs a built-in web-search tool, so any chat model can rank the
DuckDuckGo candidates.

Three backends, selected entirely by environment variables:

    LLM_PROVIDER = anthropic | openai | none   (default: auto-detected, see below)
    LLM_MODEL    = model id (provider-specific; see defaults below)
    LLM_BASE_URL = override base URL — this is the lever for local / alternative hosts
    LLM_API_KEY  = api key (falls back to ANTHROPIC_API_KEY / OPENAI_API_KEY)

The `openai` provider speaks the OpenAI-compatible /v1/chat/completions API, so a
single code path covers OpenAI, OpenRouter, Groq, Together, DeepSeek, **Ollama**
(LLM_BASE_URL=http://localhost:11434/v1), **LM Studio**, vLLM, and llama.cpp — set
LLM_BASE_URL to point at whichever one you run.

    none  → no model at all; the pipeline returns DuckDuckGo results unranked.

SDKs are imported lazily, so a user who only wants Ollama never has to install
`anthropic`, and vice versa.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

# How many web-search rounds Claude may run in the native-discovery path.
WEB_SEARCH_TOOL = "web_search_20260209"  # Opus 4.8 / 4.7 / 4.6, Sonnet 4.6
DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-8"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

Card = dict[str, str]


@dataclass
class LLMConfig:
    provider: str  # "anthropic" | "openai" | "none"
    model: str
    base_url: str | None
    api_key: str | None
    warning: str | None = None  # set when config was coerced (e.g. unknown provider)

    @property
    def enabled(self) -> bool:
        return self.provider != "none"


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
        # Don't hard-crash on a typo or stale value — degrade to keyword-only.
        warning = (
            f"Unknown LLM_PROVIDER={provider!r}; using keyword search only. "
            "Set LLM_PROVIDER to anthropic, openai, or none."
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
    else:  # none
        model, api_key = "", None

    return LLMConfig(
        provider=provider, model=model, base_url=base_url, api_key=api_key, warning=warning
    )


SYSTEM = (
    "You are an opportunity-matching assistant. Given a user's background, goals, and "
    "category, and a list of candidate web results, select the ones that genuinely fit "
    "the user and explain why. Prefer official sources (employer career pages, "
    "university admissions, program sites) over aggregators. "
    'Return ONLY a JSON array. Each item: {"title": str, "url": str, "summary": str, '
    '"why_match": str}. No prose outside the JSON.'
)

DISCOVER_SYSTEM = (
    "You are an opportunity-matching assistant. Given a user's background, goals, and "
    "category, use web search to find concrete, currently-open opportunities that fit "
    "them. Prefer official sources over aggregators. "
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


def _extract_str_list(text: str) -> list[str]:
    """Pull a JSON array of strings (search queries) out of a model reply."""
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
    return [str(q).strip() for q in data if isinstance(q, (str, int, float)) and str(q).strip()]


QUERIES_SYSTEM = (
    "You write web-search queries that will surface concrete, currently-open "
    "opportunities for a person. Given their profile and any context document, "
    "output the search queries most likely to find real, official listings. "
    "Keep each query short and natural (the words a person would type). Cover the "
    "distinct angles implied by their background and goals. "
    "Return ONLY a JSON array of query strings — no prose."
)


def _candidate_block(candidates: list[dict[str, Any]], limit: int) -> str:
    lines = []
    for i, c in enumerate(candidates[:limit], 1):
        title = c.get("title", "")
        url = c.get("url", "")
        snippet = c.get("snippet", "")
        lines.append(f"[{i}] {title}\n    {url}\n    {snippet}")
    return "\n".join(lines)


# --- Anthropic ---------------------------------------------------------------

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


def _anthropic_text(response: Any) -> str:
    return "\n".join(
        b.text for b in response.content if getattr(b, "type", None) == "text"
    )


def _anthropic_rank(cfg: LLMConfig, profile: dict, candidates: list[dict], max_results: int) -> list[Card]:
    client = _anthropic_client(cfg)
    prompt = (
        f"{_profile_block(profile)}\n\nCandidate results:\n"
        f"{_candidate_block(candidates, max_results * 4)}\n\n"
        f"Pick up to {max_results} that best fit the user. Return JSON array only."
    )
    response = client.messages.create(
        model=cfg.model,
        max_tokens=4096,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return _extract_json(_anthropic_text(response))[:max_results]


def _anthropic_discover(cfg: LLMConfig, profile: dict, max_results: int) -> list[Card]:
    client = _anthropic_client(cfg)
    prompt = (
        f"{_profile_block(profile)}\n\nFind up to {max_results} currently-open "
        f"opportunities. Return JSON array only."
    )
    response = client.messages.create(
        model=cfg.model,
        max_tokens=4096,
        system=DISCOVER_SYSTEM,
        tools=[{"type": WEB_SEARCH_TOOL, "name": "web_search", "max_uses": 5}],
        messages=[{"role": "user", "content": prompt}],
    )
    return _extract_json(_anthropic_text(response))[:max_results]


def _anthropic_queries(cfg: LLMConfig, profile: dict, n: int) -> list[str]:
    client = _anthropic_client(cfg)
    prompt = f"{_profile_block(profile)}\n\nWrite up to {n} search queries. Return a JSON array of strings only."
    response = client.messages.create(
        model=cfg.model,
        max_tokens=1024,
        system=QUERIES_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return _extract_str_list(_anthropic_text(response))[:n]


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


def _openai_rank(cfg: LLMConfig, profile: dict, candidates: list[dict], max_results: int) -> list[Card]:
    client = _openai_client(cfg)
    prompt = (
        f"{_profile_block(profile)}\n\nCandidate results:\n"
        f"{_candidate_block(candidates, max_results * 4)}\n\n"
        f"Pick up to {max_results} that best fit the user. Return JSON array only."
    )
    # No response_format / json_object: many local servers (Ollama, llama.cpp)
    # reject it. Instruct + parse defensively instead.
    response = client.chat.completions.create(
        model=cfg.model,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
    )
    return _extract_json(response.choices[0].message.content or "")[:max_results]


def _openai_queries(cfg: LLMConfig, profile: dict, n: int) -> list[str]:
    client = _openai_client(cfg)
    prompt = f"{_profile_block(profile)}\n\nWrite up to {n} search queries. Return a JSON array of strings only."
    response = client.chat.completions.create(
        model=cfg.model,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": QUERIES_SYSTEM},
            {"role": "user", "content": prompt},
        ],
    )
    return _extract_str_list(response.choices[0].message.content or "")[:n]


# --- Public API --------------------------------------------------------------


def generate_queries(
    profile: dict[str, Any],
    *,
    cfg: LLMConfig | None = None,
    n: int = 6,
) -> list[str]:
    """Have the model author the web-search queries from the profile + context."""
    cfg = cfg or load_config()
    if cfg.provider == "anthropic":
        return _anthropic_queries(cfg, profile, n)
    if cfg.provider == "openai":
        return _openai_queries(cfg, profile, n)
    raise RuntimeError("generate_queries called with provider=none")

def rank_opportunities(
    candidates: list[dict[str, Any]],
    profile: dict[str, Any],
    *,
    cfg: LLMConfig | None = None,
    max_results: int = 8,
) -> list[Card]:
    """Rank DuckDuckGo candidates into curated opportunity cards via the LLM."""
    cfg = cfg or load_config()
    if cfg.provider == "anthropic":
        return _anthropic_rank(cfg, profile, candidates, max_results)
    if cfg.provider == "openai":
        return _openai_rank(cfg, profile, candidates, max_results)
    raise RuntimeError("rank_opportunities called with provider=none")


def discover_opportunities(
    profile: dict[str, Any],
    *,
    cfg: LLMConfig | None = None,
    max_results: int = 8,
) -> list[Card]:
    """Anthropic-only: let Claude run native web_search and curate directly."""
    cfg = cfg or load_config()
    if cfg.provider != "anthropic":
        raise RuntimeError("Native web-search discovery requires the anthropic provider.")
    return _anthropic_discover(cfg, profile, max_results)
