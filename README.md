# Opportunity Finder

Describe yourself, get ranked, explained opportunities — jobs, internships, grad
school, fellowships, gap years, travel. **Bring your own model**: Claude, an
OpenAI-compatible API, a local open-source model, or no model at all.

The finder separates **search** from **reasoning**:

- **Search** uses DuckDuckGo — no API key, works everywhere.
- **Reasoning** (ranking + "why it fits") is a model *you* choose. Because the
  model never needs a built-in web-search tool, any chat model can do it.

That makes it robust to how you want to run it: a hosted API, a local model on
your own machine, or pure keyword search with no model and no key.

## Install

```bash
pip install -r requirements.txt   # core: search + report (+ optional Streamlit)
```

Then add **one** backend (or none):

```bash
pip install "anthropic>=0.40.0"   # Claude API
pip install "openai>=1.0.0"       # OpenAI, OpenRouter, Groq, Ollama, LM Studio, ...
# or install nothing → keyword-only mode
```

## Configure the backend

Copy `.env.example` to `.env` and set what you need, or pass flags. Backends:

| You want… | Set |
|---|---|
| **Claude** | `LLM_PROVIDER=anthropic` `ANTHROPIC_API_KEY=sk-ant-...` |
| **OpenAI** | `LLM_PROVIDER=openai` `OPENAI_API_KEY=sk-...` |
| **Local model (Ollama)** | `LLM_PROVIDER=openai` `LLM_BASE_URL=http://localhost:11434/v1` `LLM_MODEL=llama3.1` |
| **Local model (LM Studio)** | `LLM_PROVIDER=openai` `LLM_BASE_URL=http://localhost:1234/v1` `LLM_MODEL=<loaded-model>` |
| **No model** (keyword only) | `LLM_PROVIDER=none` |

The `openai` provider speaks the OpenAI-compatible `/v1/chat/completions` API, so
`LLM_BASE_URL` covers OpenAI, OpenRouter, Groq, Together, DeepSeek, Ollama,
LM Studio, vLLM, and llama.cpp. With `anthropic`, Claude also runs its own native
web search (set `ANTHROPIC_WEB_SEARCH=0` to rank DuckDuckGo results instead).

## Run — CLI

```bash
python -m finder.cli --category Jobs --role "data analyst" --location Remote \
  --goals "entry-level remote data role" --max 8
```

No backend configured? It still runs in keyword-only mode:

```bash
python -m finder.cli --no-llm --category Jobs --goals "remote entry-level data role"
```

Don't want to type flags? Write a paragraph about yourself in `context.txt` (or
`profile.json`) and just run `python -m finder.cli` — it auto-detects either in the
current folder. Or point at any file with `--context path/to/you.txt`.

Other flags: `--field`, `--background`, `--resume path.pdf`, `--profile profile.json`,
`--provider/--model/--base-url` (override env), `--json`, `--no-open`, `--out DIR`.
Run `python -m finder.cli -h` for the full list, or [GETTING_STARTED.md](GETTING_STARTED.md)
for a walkthrough (also shown if you run the CLI with no input). Output is an HTML
report (and optional JSON) written to `output/`.

## Run — web UI

```bash
streamlit run finder/app.py      # form + sidebar backend picker
streamlit run finder/portal.py   # save a reusable profile.json, then use --profile
```

## Layout

```
finder/
  cli.py        # command-line entry — python -m finder.cli
  app.py        # Streamlit app (backend picker in the sidebar)
  portal.py     # Streamlit profile builder -> profile.json
  run.py        # convenience: run from a saved profile.json
  pipeline.py   # profile -> ranked cards (shared by CLI + GUI)
  llm.py        # provider-agnostic model layer (anthropic / openai-compatible / none)
  scraper.py    # DuckDuckGo search (the keyless universal backend)
  queries.py    # builds search queries from the profile
  report.py     # renders the HTML report
tests/
```

Python 3.11+. Never commit `.env` or API keys.
