"""Unit tests that touch no network and no model API."""
from __future__ import annotations

import json

import pytest

from finder import cli, llm
from finder.queries import build_queries
from finder.report import render

ENV_KEYS = [
    "LLM_PROVIDER", "LLM_MODEL", "LLM_BASE_URL", "LLM_API_KEY",
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in ENV_KEYS:
        monkeypatch.delenv(k, raising=False)


# --- config -----------------------------------------------------------------

def test_detect_none_when_unconfigured():
    assert llm.load_config().provider == "none"
    assert not llm.load_config().enabled


def test_detect_anthropic_from_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    cfg = llm.load_config()
    assert cfg.provider == "anthropic" and cfg.enabled
    assert cfg.model == llm.DEFAULT_ANTHROPIC_MODEL


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
    assert cfg.provider == "none" and not cfg.enabled and cfg.warning


# --- parsing ----------------------------------------------------------------

def test_extract_json_from_chatty_output():
    msg = (
        'Sure!\n```json\n'
        '[{"title":"Analyst","url":"http://x","summary":"s","why_match":"w"},{"bad":1}]\n```'
    )
    cards = llm._extract_json(msg)
    assert len(cards) == 1 and cards[0]["title"] == "Analyst" and cards[0]["why_match"] == "w"


def test_extract_json_drops_items_without_url():
    assert llm._extract_json('[{"title":"x"}]') == []


def test_extract_json_handles_garbage():
    assert llm._extract_json("no json here") == []


def test_extract_str_list():
    assert llm._extract_str_list('here: ["a b", "c", 3] thanks') == ["a b", "c", "3"]
    assert llm._extract_str_list("no array") == []


def test_profile_block_includes_context():
    block = llm._profile_block({"category": "Jobs", "context": "I love wildlife conservation"})
    assert "Context document:" in block and "wildlife conservation" in block


def test_generate_queries_requires_backend():
    cfg = llm.LLMConfig("none", "", None, None)
    with pytest.raises(RuntimeError):
        llm.generate_queries({"goals": "x"}, cfg=cfg)


def test_rank_requires_backend():
    cfg = llm.LLMConfig("none", "", None, None)
    with pytest.raises(RuntimeError):
        llm.rank_opportunities([], {"goals": "x"}, cfg=cfg)


# --- query templates --------------------------------------------------------

def test_build_queries_fills_templates():
    qs = build_queries(category="Jobs", role="data analyst", location="Remote", year=2026)
    assert qs and all(isinstance(q, str) and q for q in qs)
    assert any("data analyst" in q for q in qs)


# --- scraper (DuckDuckGo wrapper) -------------------------------------------

class _FakeDDGS:
    pages: dict = {}
    calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def text(self, query, max_results):
        type(self).calls += 1
        return self.pages.get(query, [])


def test_search_stops_after_consecutive_empty(monkeypatch):
    from finder import scraper

    _FakeDDGS.pages = {}
    _FakeDDGS.calls = 0
    monkeypatch.setattr(scraper, "DDGS", _FakeDDGS)
    assert scraper.search(["a", "b", "c", "d", "e"]) == []
    assert _FakeDDGS.calls == scraper.MAX_EMPTY_STREAK  # stopped early


def test_search_collects_and_dedupes(monkeypatch):
    from finder import scraper

    _FakeDDGS.pages = {
        "a": [{"href": "http://x", "title": "X", "body": "b"}],
        "b": [],
        "c": [{"href": "http://x"}, {"href": "http://y", "title": "Y", "body": ""}],
    }
    _FakeDDGS.calls = 0
    monkeypatch.setattr(scraper, "DDGS", _FakeDDGS)
    assert [r.url for r in scraper.search(["a", "b", "c"])] == ["http://x", "http://y"]


# --- CLI --------------------------------------------------------------------

def test_cli_context_flag_routes_to_context_field(tmp_path):
    doc = tmp_path / "me.txt"
    doc.write_text("Economics grad, Python and SQL.", encoding="utf-8")
    args = cli.build_parser().parse_args(["--context", str(doc)])
    profile, src = cli._load_profile(args)
    assert profile["context"].startswith("Economics grad")
    assert not profile.get("background")
    assert src == str(doc)


def test_cli_render_agent_cards(tmp_path):
    cards = tmp_path / "cards.json"
    cards.write_text(json.dumps(
        [{"title": "Analyst", "url": "https://x.test", "summary": "s", "why_match": "w"}]
    ), encoding="utf-8")
    out = cli.run(["--render", str(cards), "--no-open", "--out", str(tmp_path), "--category", "Jobs"])
    assert out.exists() and out.suffix == ".html"
    assert "Analyst" in out.read_text(encoding="utf-8")


def test_cli_brief_emits_profile(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.run(["--brief", "--category", "Jobs", "--role", "data analyst", "--goals", "x"])
    assert exc.value.code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["category"] == "Jobs"
    assert data["profile"]["role"] == "data analyst"


# --- web app ----------------------------------------------------------------

def test_server_serves_page_and_api(monkeypatch):
    from finder import server
    from finder.pipeline import PipelineResult

    client = server.app.test_client()

    r = client.get("/")
    assert r.status_code == 200 and b"Opportunity" in r.data

    # missing profile input -> 400
    assert client.post("/api/find", data={"category": "Jobs"}).status_code == 400

    # input present but no backend chosen -> 400
    assert client.post("/api/find", data={"category": "Jobs", "goals": "x"}).status_code == 400

    # valid input + backend -> cards (pipeline stubbed, no network)
    monkeypatch.setattr(
        server, "find_opportunities",
        lambda profile, cfg=None, max_results=8: PipelineResult(
            cards=[{"title": "X", "url": "http://x", "summary": "s", "why_match": "w"}],
            mode="test",
        ),
    )
    r = client.post("/api/find", data={
        "category": "Jobs", "goals": "remote data role",
        "provider": "anthropic", "model": "claude-opus-4-8", "api_key": "sk-test",
    })
    assert r.status_code == 200
    body = r.get_json()
    assert body["mode"] == "test" and body["cards"][0]["title"] == "X"


# --- report -----------------------------------------------------------------

def test_report_render_escapes_html(tmp_path):
    cards = [{"title": "Acme <Analyst>", "url": "https://acme.test/jobs",
              "summary": "A & B", "why_match": "fits <you>"}]
    out = render(cards, "Jobs", "ctx", tmp_path / "r.html", mode="web search")
    html = out.read_text(encoding="utf-8")
    assert "&lt;Analyst&gt;" in html and "<Analyst>" not in html
    assert "web search" in html
