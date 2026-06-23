# Opportunity Finder

Describe yourself, get ranked, explained opportunities — jobs, internships, grad
school, fellowships, gap years, travel. **Bring your own model**: Claude, an
OpenAI-compatible API, a local open-source model, or no model at all.

The finder separates **search** from **reasoning**:

- **Search** uses DuckDuckGo — no API key, works everywhere.
- **Reasoning** (ranking + "why it fits") is a model *you* choose. Because the
  model never needs a built-in web-search tool, any chat model can do it.

## Two ways to run

You can use the finder either way — they share the same engine and the same model
backends, so results are identical:

- **🖥️ Web app (Streamlit)** — a form in your browser, with a sidebar to pick the
  model. Best if you'd rather click than type.
- **⌨️ Command line** — `python -m finder.cli`. Best for quick runs, scripting, or
  staying in the terminal.

> **Does the web app use the model too?** Yes. Both the web app and the CLI use
> whichever backend you choose (Claude / OpenAI-compatible / local / none) for
> ranking and explanations. The only difference is *how you select it*: the web
> app has a sidebar picker; the CLI reads environment variables or flags. With no
> backend, both fall back to keyword-only search.

Jump to: [Install](#1-install) · [Choose a backend](#2-choose-a-backend) ·
[Web app](#3a-run-the-web-app) · [Command line](#3b-run-the-cli)

---

## 1. Install

```bash
pip install -r requirements.txt   # core: search + report (Streamlit included)
```

Then add **one** model backend (or none):

```bash
pip install "anthropic>=0.40.0"   # Claude API
pip install "openai>=1.0.0"       # OpenAI, OpenRouter, Groq, Ollama, LM Studio, ...
# or install nothing → keyword-only mode
```

## 2. Choose a backend

This applies to **both** the web app and the CLI. The `openai` provider speaks the
OpenAI-compatible `/v1/chat/completions` API, so `LLM_BASE_URL` covers OpenAI,
OpenRouter, Groq, Together, DeepSeek, Ollama, LM Studio, vLLM, and llama.cpp.

| You want… | Settings |
|---|---|
| **Claude** | `LLM_PROVIDER=anthropic` `ANTHROPIC_API_KEY=sk-ant-...` |
| **OpenAI** | `LLM_PROVIDER=openai` `OPENAI_API_KEY=sk-...` |
| **Local model (Ollama)** | `LLM_PROVIDER=openai` `LLM_BASE_URL=http://localhost:11434/v1` `LLM_MODEL=llama3.1` |
| **Local model (LM Studio)** | `LLM_PROVIDER=openai` `LLM_BASE_URL=http://localhost:1234/v1` `LLM_MODEL=<loaded-model>` |
| **No model** (keyword only) | `LLM_PROVIDER=none` |

- **Web app:** set these in the sidebar at run time (or in `.env` as defaults).
- **CLI:** put them in a `.env` file (copy `.env.example`), your shell environment,
  or pass `--provider/--model/--base-url` on the command.

With `anthropic`, Claude also runs its own native web search; set
`ANTHROPIC_WEB_SEARCH=0` to rank DuckDuckGo results instead.

---

## 3a. Run the web app

```bash
streamlit run finder/app.py
```

Fill in the form (what you're looking for, role/field/location, background, goals,
optional résumé), pick a model in the sidebar, and click **Find opportunities**.
You can download your inputs as `profile.json` to reuse later.

Prefer to build a reusable profile first? `streamlit run finder/portal.py` saves a
`profile.json` you can feed to the CLI with `--profile`.

## 3b. Run the CLI

```bash
python -m finder.cli --category Jobs --role "data analyst" --location Remote \
  --goals "entry-level remote data role" --max 8
```

No backend configured? It still runs in keyword-only mode:

```bash
python -m finder.cli --no-llm --category Jobs --goals "remote entry-level data role"
```

**Don't want to type flags?** Write a paragraph about yourself in `context.txt`
(or save a `profile.json`) and just run `python -m finder.cli` — it auto-detects
either in the current folder. Or point at any file with `--context path/to/you.txt`.

Other flags: `--field`, `--background`, `--resume path.pdf`, `--profile profile.json`,
`--provider/--model/--base-url` (override the backend), `--json`, `--no-open`,
`--out DIR`. Run `python -m finder.cli -h` for the full list, or see
[GETTING_STARTED.md](GETTING_STARTED.md) (also shown if you run the CLI with no
input). Output is an HTML report (and optional JSON) written to `output/`.

---

## Layout

```
finder/
  app.py        # Streamlit web app (backend picker in the sidebar)
  cli.py        # command-line entry — python -m finder.cli
  portal.py     # Streamlit profile builder -> profile.json
  run.py        # convenience: run the CLI from a saved profile.json
  pipeline.py   # profile -> ranked cards (shared by web app + CLI)
  llm.py        # provider-agnostic model layer (anthropic / openai-compatible / none)
  scraper.py    # DuckDuckGo search (the keyless universal backend)
  queries.py    # builds search queries from the profile
  report.py     # renders the HTML report
tests/
```

Python 3.11+. Never commit `.env` or API keys.
