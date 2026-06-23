# Getting started

You ran Opportunity without enough information about you. Lets fix that.

## 1. Install the dependencies

```
pip install -r requirements.txt
```

| Backend | Install | Configure |
|---|---|---|
| Claude (Anthropic) | `pip install "anthropic>=0.40.0"` | `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=...` |
| OpenAI | `pip install "openai>=1.0.0"` | `LLM_PROVIDER=openai`, `OPENAI_API_KEY=...` |
| Local model (Ollama) | `pip install "openai>=1.0.0"` | `LLM_PROVIDER=openai`, `LLM_BASE_URL=http://localhost:11434/v1`, `LLM_MODEL=llama3.1` |
| Local model (LM Studio) | `pip install "openai>=1.0.0"` | `LLM_PROVIDER=openai`, `LLM_BASE_URL=http://localhost:1234/v1`, `LLM_MODEL=<loaded-model>` |

Put the configuration in a `.env` file (copy `.env.example`) or your shell
environment. A model is required — DuckDuckGo finds candidate listings and your
model ranks + explains them (the raw results are never shown).

## 2. Tell the finder about you  **pick one**

**A. Context file** Write a paragraph about yourself in a plain-text
file and drop it next to where you run the command. The finder auto-detects
`context.txt`, `context.md`, or `profile.json` in the current folder:

```
# context.txt
I'm a recent economics grad in Chicago with experience using Python and SQL. Looking for an
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
--json       also write results as JSON
--no-open    don't open the report in a browser
--out DIR    where to write the report (default: ./output)
```

Prefer a form over the terminal? Run the web app instead:

```
python -m finder.server      # http://127.0.0.1:5000
```

Full flag list: `python -m finder.cli -h`.
