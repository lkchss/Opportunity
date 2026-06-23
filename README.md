# Opportunity

Ironically, finding ways to spend your time is time-intensive. Opportunity allows for a reduction in search-costs.

Describe yourself; get ranked, explained opportunities.

## How it works

1. **You describe yourself:** a few fields, a document (PDF or text), or both.
2. **The model finds the matches:** Claude searches the live web; other models draw
   on what they know. The model is the engine — there's no keyword scrape.
3. **It explains each pick:** why this opportunity fits *you*, with a link.
4. **Results:** ranked opportunity cards in the web app, or an HTML report.

## Two ways to run

- **Web app** — a form in your browser, with a sidebar to pick the
  model.
- **CLI** — `python -m finder.cli`. Best for quick runs, scripting, or
  staying in the terminal.

Jump to: [Install](#1-install) · [Choose a backend](#2-choose-a-backend) ·
[Web app](#3a-run-the-web-app) · [Command line](#3b-run-the-cli)

---

## 1. Install

```bash
pip install -r requirements.txt   # core + web app
```

Then add **one** model backend — a model is required:

```bash
pip install "anthropic>=0.40.0"   # Claude API (recommended — native web search)
pip install "openai>=1.0.0"       # OpenAI, OpenRouter, Groq, Ollama, LM Studio, ...
```

## 2. Choose a backend

| You want… | Settings |
|---|---|
| **Claude** | `LLM_PROVIDER=anthropic` `ANTHROPIC_API_KEY=sk-ant-...` |
| **OpenAI** | `LLM_PROVIDER=openai` `OPENAI_API_KEY=sk-...` |
| **Local model (Ollama)** | `LLM_PROVIDER=openai` `LLM_BASE_URL=http://localhost:11434/v1` `LLM_MODEL=llama3.1` |
| **Local model (LM Studio)** | `LLM_PROVIDER=openai` `LLM_BASE_URL=http://localhost:1234/v1` `LLM_MODEL=<loaded-model>` |

- **Web app:** pick the backend in the page (it pre-fills from `.env`).
- **CLI:** put these in a `.env` file (copy `.env.example`), your shell environment,
  or pass `--provider/--model/--base-url` on the command.

Claude searches the live web for real, currently-open listings. Other models
discover from their training knowledge, so they can be less current — Claude (or an
agent CLI with its own web access) is recommended for live results.

---

## 3a. Run the web app

```bash
python -m finder.server          # http://127.0.0.1:5000
```

Pick the model under **Model** (the picker pre-fills from the server's `.env`),
upload a context document (PDF or text) **and/or** fill in the details — they count
equally — and click **Find opportunities**. The fields adapt to what you're looking
for (no "role/title" for grad school, fellowships, gap years, or travel).

Frontend lives in `finder/web/` (plain HTML/CSS/JS); the API is `POST /api/find`.
Deploy with `gunicorn finder.server:app` (honors `$PORT`).

> A Streamlit UI (`streamlit run finder/app.py`, with an in-app backend picker) is
> also included as an alternative; the Flask app above is the primary, styled one.

## 3b. Run the CLI

```bash
python -m finder.cli --category Jobs --role "data analyst" --location Remote \
  --goals "entry-level remote data role" --max 8
```

The backend comes from your environment (`.env` / shell) or `--provider/--model/--base-url`.

**Don't want to type flags?** Write a paragraph about yourself in `context.txt`
(or save a `profile.json`) and just run `python -m finder.cli` — it auto-detects
either in the current folder. Or point at any file with `--context path/to/you.txt`.

Other flags: `--field`, `--background`, `--resume path.pdf`, `--profile profile.json`,
`--provider/--model/--base-url` (override the backend), `--json`, `--no-open`,
`--out DIR`. Run `python -m finder.cli -h` for the full list, or see
[GETTING_STARTED.md](GETTING_STARTED.md) (also shown if you run the CLI with no
input). Output is an HTML report (and optional JSON) written to `output/`.

---

## Use it from any agent CLI — `/opportunity` (no API key)

Run the finder inside an agentic CLI; summon it explicitly with **`/opportunity`** —
pass a context file, a freeform request, or both:

```
/opportunity [context-file]  [what you're looking for]

/opportunity remote data-analyst roles for an econ grad with Python/SQL
/opportunity profile.md ways to spend a gap year
/opportunity resume.pdf software internships in NYC
/opportunity                       # reads context.txt / profile.json, or asks you
```

The agent reads any file you name as your profile/context, then searches and ranks
with its own tools.

The workflow is one prompt — [`prompts/opportunity.md`](prompts/opportunity.md) —
that each CLI loads from its own command directory:

| CLI | `/opportunity` lives at |
|---|---|
| **Claude Code** | `.claude/commands/opportunity.md` — already in the repo |
| **opencode** | `.opencode/command/opportunity.md` — already in the repo |
| **Codex CLI** | copy `prompts/opportunity.md` → `~/.codex/prompts/opportunity.md` |
| **Other / open-source CLIs** | point a custom command at `prompts/opportunity.md`, or just tell the agent: *"read `prompts/opportunity.md` and follow it"* |

The in-repo files expose `/opportunity` only when the CLI is opened in this repo.
To get it in **every** project, copy the launcher into your personal command dir too
— `~/.claude/commands/` (Claude Code) or `~/.config/opencode/command/` (opencode).

Under the hood the agent uses two helper commands — `python -m finder.cli --brief`
(prints your profile as JSON) and `python -m finder.cli --render cards.json` (writes
the standard HTML report from the agent's picks).

## Layout

```
finder/
  server.py     # Flask web app — python -m finder.server (serves web/ + POST /api/find)
  web/          # frontend: index.html, styles.css, app.js (black & white)
  cli.py        # command-line entry — python -m finder.cli
  app.py        # alternative Streamlit UI (in-app backend picker)
  portal.py     # Streamlit profile builder -> profile.json
  run.py        # convenience: run the CLI from a saved profile.json
  pipeline.py   # profile -> ranked cards (shared by web app + CLI)
  llm.py        # the engine — finds + explains opportunities (anthropic / openai-compatible)
  report.py     # renders the HTML report
tests/
```

## License

[MIT](LICENSE) — free to use, modify, and distribute.
