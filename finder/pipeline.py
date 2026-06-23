"""Profile -> ranked opportunity cards. Shared by the CLI and the Streamlit app.

One flow, three behaviors depending on the configured backend:

  anthropic (+ native web search)  → Claude searches the web and curates directly.
  any LLM backend                  → DuckDuckGo finds candidates, the LLM ranks them.
  none                             → DuckDuckGo results, unranked (keyword only).
"""
from __future__ import annotations

import datetime
import os
from dataclasses import dataclass, field
from typing import Any

from finder import llm
from finder.queries import build_queries
from finder.scraper import search as ddg_search

Card = dict[str, str]


@dataclass
class PipelineResult:
    cards: list[Card]
    mode: str  # "anthropic-web-search" | "ddg+llm-rank" | "ddg-keyword"
    queries: list[str] = field(default_factory=list)
    candidate_count: int = 0


def _want_native_web_search(cfg: llm.LLMConfig) -> bool:
    """Use Claude's native web_search unless explicitly turned off."""
    if cfg.provider != "anthropic":
        return False
    return os.environ.get("ANTHROPIC_WEB_SEARCH", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def find_opportunities(
    profile: dict[str, Any],
    *,
    cfg: llm.LLMConfig | None = None,
    max_results: int = 8,
    force_keyword: bool = False,
) -> PipelineResult:
    cfg = cfg or llm.load_config()

    # Path 1: Claude does its own searching + curation.
    if not force_keyword and _want_native_web_search(cfg):
        cards = llm.discover_opportunities(profile, cfg=cfg, max_results=max_results)
        return PipelineResult(cards=cards, mode="anthropic-web-search")

    # Path 2 & 3: DuckDuckGo finds candidates first.
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

    if cfg.enabled and not force_keyword:
        cards = llm.rank_opportunities(
            candidates, profile, cfg=cfg, max_results=max_results
        )
        return PipelineResult(
            cards=cards,
            mode="ddg+llm-rank",
            queries=queries,
            candidate_count=len(candidates),
        )

    # Path 3: no LLM — surface the raw DuckDuckGo hits as cards.
    cards = [
        {
            "title": c["title"],
            "url": c["url"],
            "summary": c["snippet"],
            "why_match": "",
        }
        for c in candidates[:max_results]
    ]
    return PipelineResult(
        cards=cards,
        mode="ddg-keyword",
        queries=queries,
        candidate_count=len(candidates),
    )
