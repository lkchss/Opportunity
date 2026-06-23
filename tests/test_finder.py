"""Unit tests that touch no network and no model API."""
from __future__ import annotations

import json

import pytest

from finder import cli, llm
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


class _FakeDDGS:
    """Stand-in for ddgs.DDGS: returns canned pages and counts .text() calls."""

    pages: dict = {}
    calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def text(self, query, max_results):  # noqa: D401 - test stub
        type(self).calls += 1
        return self.pages.get(query, [])


def test_search_stops_after_consecutive_empty(monkeypatch):
    from finder import scraper

    _FakeDDGS.pages = {}
    _FakeDDGS.calls = 0
    monkeypatch.setattr(scraper, "DDGS", _FakeDDGS)
    out = scraper.search(["a", "b", "c", "d", "e"])
    assert out == []
    assert _FakeDDGS.calls == scraper.MAX_EMPTY_STREAK  # stopped early, didn't run all 5


def test_search_collects_and_dedupes(monkeypatch):
    from finder import scraper

    _FakeDDGS.pages = {
        "a": [{"href": "http://x", "title": "X", "body": "b"}],
        "b": [],  # one empty in the middle must not trip the early stop
        "c": [{"href": "http://x"}, {"href": "http://y", "title": "Y", "body": ""}],
    }
    _FakeDDGS.calls = 0
    monkeypatch.setattr(scraper, "DDGS", _FakeDDGS)
    out = scraper.search(["a", "b", "c"])
    assert [r.url for r in out] == ["http://x", "http://y"]  # deduped across queries


def test_profile_block_includes_context():
    block = llm._profile_block({"category": "Jobs", "context": "I love wildlife conservation"})
    assert "Context document:" in block
    assert "wildlife conservation" in block


def test_extract_str_list():
    assert llm._extract_str_list('here you go: ["a b", "c", 3] thanks') == ["a b", "c", "3"]
    assert llm._extract_str_list("no array here") == []


def test_generate_queries_requires_backend():
    cfg = llm.LLMConfig("none", "", None, None)
    with pytest.raises(RuntimeError):
        llm.generate_queries({"goals": "x"}, cfg=cfg)


def test_cli_context_flag_routes_to_context_field(tmp_path):
    doc = tmp_path / "me.txt"
    doc.write_text("Economics grad, Python and SQL.", encoding="utf-8")
    args = cli.build_parser().parse_args(["--context", str(doc)])
    profile, src = cli._load_profile(args)
    assert profile["context"].startswith("Economics grad")
    assert not profile.get("background")  # context is its own field, not background
    assert src == str(doc)


def test_cli_render_agent_cards(tmp_path):
    cards = tmp_path / "cards.json"
    cards.write_text(json.dumps(
        [{"title": "Analyst", "url": "https://x.test", "summary": "s", "why_match": "w"}]
    ), encoding="utf-8")
    out = cli.run(["--render", str(cards), "--no-open", "--out", str(tmp_path), "--category", "Jobs"])
    assert out.exists() and out.suffix == ".html"
    assert "Analyst" in out.read_text(encoding="utf-8")


def test_cli_brief_emits_queries(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.run(["--brief", "--category", "Jobs", "--role", "data analyst", "--goals", "x"])
    assert exc.value.code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["category"] == "Jobs"
    assert data["queries"]


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
