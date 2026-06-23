"""Generate an HTML report from ranked opportunity cards."""
from __future__ import annotations

import datetime
import html
from pathlib import Path
from typing import Any

STYLE = """
  body { font-family: system-ui, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; color: #1a1a1a; }
  h1 { font-size: 1.8rem; margin-bottom: 4px; }
  .meta { color: #666; font-size: 0.9rem; margin-bottom: 32px; }
  .card { border: 1px solid #e0e0e0; border-radius: 8px; padding: 18px 22px; margin-bottom: 16px; }
  .card:hover { border-color: #999; }
  .card h2 { margin: 0 0 6px; font-size: 1.1rem; }
  .card h2 a { color: #1a56db; text-decoration: none; }
  .card h2 a:hover { text-decoration: underline; }
  .url { font-size: 0.8rem; color: #666; margin-bottom: 8px; word-break: break-all; }
  .summary { font-size: 0.95rem; line-height: 1.5; margin: 0; }
  .why { font-size: 0.9rem; line-height: 1.5; margin: 10px 0 0; color: #333; }
  .why strong { color: #1a1a1a; }
  .section { font-size: 0.8rem; color: #888; margin: 28px 0 8px; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #eee; padding-bottom: 4px; }
"""


def _card(c: dict[str, Any]) -> str:
    title = html.escape(c.get("title", ""))
    url = html.escape(c.get("url", ""))
    summary = html.escape(c.get("summary", ""))
    why = c.get("why_match", "")
    why_html = (
        f'<p class="why"><strong>Why this fits:</strong> {html.escape(why)}</p>'
        if why
        else ""
    )
    return f"""
    <div class="card">
      <h2><a href="{url}" target="_blank" rel="noopener">{title}</a></h2>
      <div class="url">{url}</div>
      <p class="summary">{summary}</p>
      {why_html}
    </div>"""


def render(
    cards: list[dict[str, Any]],
    category: str,
    context_summary: str,
    output_path: Path,
    *,
    mode: str = "",
) -> Path:
    now = datetime.datetime.now().strftime("%B %d, %Y %H:%M")
    cards_html = "\n".join(_card(c) for c in cards)
    mode_tag = f" &nbsp;·&nbsp; <strong>via:</strong> {html.escape(mode)}" if mode else ""
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Opportunity Results — {html.escape(category)}</title>
  <style>{STYLE}</style>
</head>
<body>
  <h1>Opportunity Results</h1>
  <div class="meta">
    <strong>Category:</strong> {html.escape(category)} &nbsp;·&nbsp;
    <strong>Generated:</strong> {now} &nbsp;·&nbsp;
    <strong>{len(cards)} results</strong>{mode_tag}
  </div>
  <div class="section">Context</div>
  <p style="font-size:0.95rem; color:#444; margin-bottom:24px;">{html.escape(context_summary)}</p>
  <div class="section">Results</div>
  {cards_html}
</body>
</html>"""
    output_path.write_text(page, encoding="utf-8")
    return output_path
