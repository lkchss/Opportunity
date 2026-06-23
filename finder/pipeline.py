"""Profile -> ranked, explained opportunity cards. Shared by the web app and CLI.

Web search (DuckDuckGo) finds candidates; the model **always** ranks and explains
them — the raw scrape is never published. The model also writes the search queries
(with a deterministic template fallback). A model is required.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any

from finder import llm
from finder.queries import build_queries
from finder.scraper import search as ddg_search

Card = dict[str, str]


@dataclass
class PipelineResult:
    cards: list[Card]
    mode: str  # human-readable, e.g. "web search · ranked by claude-opus-4-8"
    candidate_count: int = 0


def find_opportunities(
    profile: dict[str, Any],
    *,
    cfg: llm.LLMConfig | None = None,
    max_results: int = 8,
) -> PipelineResult:
    cfg = cfg or llm.load_config()
    if not cfg.enabled:
        raise RuntimeError(
            "No model configured. Choose a backend — Claude, OpenAI, or a local model."
        )

    # The model writes the search queries (deterministic templates as a fallback).
    try:
        queries = llm.generate_queries(profile, cfg=cfg)
    except Exception:
        queries = []
    if not queries:
        queries = build_queries(
            category=profile.get("category", "Jobs"),
            role=profile.get("role", ""),
            field=profile.get("field", ""),
            location=profile.get("location", ""),
            background=profile.get("background", ""),
            year=datetime.date.today().year,
        )

    results = ddg_search(queries)
    candidates = [
        {"title": r.title, "url": r.url, "snippet": r.snippet, "query": r.query}
        for r in results
    ]

    # Always curate through the model — never surface raw scrape results.
    cards = llm.rank_opportunities(candidates, profile, cfg=cfg, max_results=max_results)
    return PipelineResult(
        cards=cards,
        mode=f"web search · ranked by {cfg.model or cfg.provider}",
        candidate_count=len(candidates),
    )
