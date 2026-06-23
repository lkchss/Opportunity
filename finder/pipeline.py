"""Profile -> ranked, explained opportunity cards. Shared by the web app and CLI.

The model is the engine (see finder.llm): Claude finds opportunities with its
native web search; an OpenAI-compatible model discovers from its knowledge. A
model is required — there is no keyword-scrape fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from finder import llm

Card = dict[str, str]


@dataclass
class PipelineResult:
    cards: list[Card]
    mode: str  # human-readable backend label, e.g. "Claude web search"


def find_opportunities(
    profile: dict[str, Any],
    *,
    cfg: llm.LLMConfig | None = None,
    max_results: int = 8,
) -> PipelineResult:
    cfg = cfg or llm.load_config()
    cards = llm.discover_opportunities(profile, cfg=cfg, max_results=max_results)
    mode = "Claude web search" if cfg.provider == "anthropic" else (cfg.model or cfg.provider)
    return PipelineResult(cards=cards, mode=mode)
