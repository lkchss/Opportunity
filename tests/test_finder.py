"""Unit tests that touch no network and no model API."""
from __future__ import annotations

import pytest

from finder import llm
from finder.queries import build_queries
from finder.report import render

ENV_KEYS = [
    "LLM_PROVIDER",
    "LLM_MODEL",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in ENV_KEYS:
        monkeypatch.delenv(k, raising=False)


def test_detect_none_when_unconfigured():
    assert llm.load_config().provider == "none"


def test_detect_anthropic_from_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    cfg = llm.load_config()
    assert cfg.provider == "anthropic"
    assert cfg.model == llm.DEFAULT_ANTHROPIC_MODEL
    assert cfg.enabled


def test_openai_local_uses_placeholder_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "llama3.1")
    cfg = llm.load_config()
    assert cfg.provider == "openai"
    assert cfg.base_url.endswith("11434/v1")
    assert cfg.api_key == "not-needed"
    assert cfg.model == "llama3.1"


def test_unknown_provider_degrades_to_none(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "google")
    cfg = llm.load_config()
    assert cfg.provider == "none"
    assert not cfg.enabled
    assert cfg.warning


def test_extract_json_from_chatty_output():
    msg = (
        'Sure! Here are the matches:\n```json\n'
        '[{"title":"Analyst","url":"http://x","summary":"s","why_match":"w"},{"bad":1}]\n'
        '```\nHope that helps!'
    )
    cards = llm._extract_json(msg)
    assert len(cards) == 1
    assert cards[0]["title"] == "Analyst"
    assert cards[0]["why_match"] == "w"


def test_extract_json_drops_items_without_url():
    assert llm._extract_json('[{"title":"x"}]') == []


def test_extract_json_handles_garbage():
    assert llm._extract_json("no json here") == []


def test_build_queries_fills_templates():
    qs = build_queries(category="Jobs", role="data analyst", location="Remote", year=2026)
    assert qs and all(isinstance(q, str) and q for q in qs)
    assert any("data analyst" in q for q in qs)


def test_report_render_escapes_html(tmp_path):
    cards = [
        {
            "title": "Acme <Analyst>",
            "url": "https://acme.test/jobs",
            "summary": "A & B",
            "why_match": "fits <you>",
        }
    ]
    out = render(cards, "Jobs", "ctx", tmp_path / "r.html", mode="ddg-keyword")
    html = out.read_text(encoding="utf-8")
    assert "&lt;Analyst&gt;" in html  # title escaped
    assert "<Analyst>" not in html
    assert "ddg-keyword" in html
