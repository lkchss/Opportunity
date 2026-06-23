# Getting started

You ran the Opportunity Finder without enough information about you. Here's how
to give it what it needs.

## 1. Install the dependencies

```
pip install -r requirements.txt
```

That's the core (search + report). For ranking + explanations, add **one** model
backend - or skip it and use keyword-only mode:

| Backend | Install | Configure |
|---|---|---|
| Claude (Anthropic) | `pip install "anthropic>=0.40.0"` | `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=...` |
| OpenAI | `pip install "openai>=1.0.0"` | `LLM_PROVIDER=openai`, `OPENAI_API_KEY=...` |
| Local model (Ollama) | `pip install "openai>=1.0.0"` | `LLM_PROVIDER=openai`, `LLM_BASE_URL=http://localhost:11434/v1`, `LLM_MODEL=llama3.1` |
| Local model (LM Studio) | `pip install "openai>=1.0.0"` | `LLM_PROVIDER=openai`, `LLM_BASE_URL=http://localhost:1234/v1`, `LLM_MODEL=<loaded-model>` |
| No model (keyword only) | nothing extra | pass `--no-llm` |

Put the configuration in a `.env` file (copy `.env.example`) or your shell
environment. With no backend configured the finder still runs in keyword mode.

## 2. Tell the finder about you - pick one

**A. A context file (easiest).** Write a paragraph about yourself in a plain-text
file and drop it next to where you run the command. The finder auto-detects
`context.txt`, `context.md`, or `profile.json` in the current folder:

```
# context.txt
I'm a recent economics grad in Chicago with Python and SQL. Looking for an
entry-level, remote data-analyst role. Open to relocating to the Bay Area.
```

```
python -m finder.cli --category Jobs
```

Or point at any file explicitly: `--context path/to/you.txt` (`.txt`, `.md`, or `.pdf`).

**B. Command-line flags.** Spell it out inline:

```
python -m finder.cli --category Jobs --role "data analyst" --location Remote \
  --background "economics grad, Python/SQL" --goals "entry-level remote data role"
```

You need at least `--goals`, `--background`, `--context`, or `--resume`.

**C. A saved profile.** Build one in the browser, then reuse it:

```
streamlit run finder/portal.py        # fill the form, saves profile.json
python -m finder.cli --profile profile.json
```

## 3. Useful options

```
--category   Jobs | Internships | Graduate school | Fellowships / Scholarships | Gap year programs | Travel / Volunteer
--resume     path to a resume (.pdf or .txt) to add to your context
--max N      number of results (default 8)
--provider / --model / --base-url   override the backend for this run
--no-llm     skip the model; return DuckDuckGo keyword results
--json       also write results as JSON
--no-open    don't open the report in a browser
--out DIR    where to write the report (default: ./output)
```

Prefer a form over the terminal? Run the web app instead:

```
streamlit run finder/app.py
```

Full flag list: `python -m finder.cli -h`.
