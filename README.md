# Opportunity

Ironically, finding ways to spend your time is time-intensive. Opportunity allows for a reduction in search-costs.

Describe yourself, get ranked, explained opportunities.

## How it works

1. **You describe yourself** — a few fields, a document (PDF or text), or both.
2. **The model writes the searches.** It reads your profile + context and decides
   what to query; DuckDuckGo runs them (no API key). With no model, templates do this.
3. **The model ranks** the candidates against your profile and explains each pick.
4. **Results.** Ranked opportunity cards in the web app, or an HTML report.

## Two ways to run

- **Web app** — a form in your browser, with a sidebar to pick the
  model. Best if you'd rather click than type.
- **CLI** — `python -m finder.cli`. Best for quick runs, scripting, or
  staying in the terminal.

Jump to: [Install](#1-install) · [Choose a backend](#2-choose-a-backend) ·
[Web app](#3a-run-the-web-app) · [Command line](#3b-run-the-cli)

---

## 1. Install

```bash
pip install -r requirements.txt   # core: search + report
```

Then add **one** model backend (or none):

```bash
pip install "anthropic>=0.40.0"   # Claude API
pip install "openai>=1.0.0"       # OpenAI, OpenRouter, Groq, Ollama, LM Studio, ...
```

## 2. Choose a backend

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

Upload a context document (PDF or text) **and/or** fill in the details (category,
role/field/location, background, goals) — they count equally. Pick a model in the
sidebar, then click **Find opportunities**. You can download your inputs as
`profile.json` to reuse later.

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
with its own tools — on whatever subscription you're already in, so no API key is
needed.

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

Under the hood the agent uses two keyless helper commands — `python -m finder.cli
--brief` (prints the search queries + your profile as JSON) and `python -m finder.cli
--render cards.json` (writes the standard HTML report from the agent's picks).

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

## License

[MIT](LICENSE) — free to use, modify, and distribute.
