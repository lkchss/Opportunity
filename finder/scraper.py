"""DuckDuckGo-based opportunity scraper — the universal (keyless) search backend.

Prefers the maintained `ddgs` package and falls back to the older
`duckduckgo_search`. A single rate-limited/failed query degrades gracefully
instead of aborting the whole run.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:  # the package was renamed `duckduckgo_search` -> `ddgs`
    from ddgs import DDGS  # type: ignore
except ImportError:  # pragma: no cover - fallback for older installs
    from duckduckgo_search import DDGS  # type: ignore

# page-1-only (5) missed everything below the fold; 25 reaches lower-SEO hits
MAX_RESULTS_PER_QUERY = 25


@dataclass
class Result:
    title: str
    url: str
    snippet: str
    query: str


def search(queries: list[str]) -> list[Result]:
    results: list[Result] = []
    seen: set[str] = set()
    with DDGS() as ddgs:
        for query in queries:
            try:
                hits: list[dict[str, Any]] = list(
                    ddgs.text(query, max_results=MAX_RESULTS_PER_QUERY)
                )
            except Exception:
                # Rate limit, transient bot-wall, or network blip — skip this
                # query rather than losing every other query's results.
                continue
            for h in hits:
                url = h.get("href") or h.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    results.append(
                        Result(
                            title=h.get("title", ""),
                            url=url,
                            snippet=h.get("body", ""),
                            query=query,
                        )
                    )
    return results
