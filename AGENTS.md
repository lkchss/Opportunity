# AGENTS.md — Opportunity Finder

Guidance for agentic CLIs (Codex CLI, Claude Code, and any agent that can run a
shell and search the web). This repo is a small Python tool; you can run it
normally **or** drive it as a skill where *you* are the model.

## Run it as a skill (no API key)

When the user asks you to find opportunities (jobs, internships, grad school,
fellowships, gap-year programs, travel/volunteer), act as the Opportunity Finder
using your own web-search and reasoning — no model API key needed.

1. **Profile.** Read `profile.json` / `context.txt` / `context.md` / a résumé in
   the working folder, or ask for: category, role/field/location (skip "role" for
   grad school, fellowships, gap year, and travel/volunteer), background, goals.
2. **Brief (optional).** `python -m finder.cli --brief [--category ... --role ... --goals ...]`
   prints suggested search `queries` + the normalized profile as JSON. Refine them.
3. **Search + rank — your job.** Use your web tools to find currently-open, real
   opportunities. Prefer official sources over aggregators, verify links resolve,
   never invent URLs, dedupe. Pick the best N (default 8, up to 30). For each:
   `title`, `url`, `summary`, `why_match`.
4. **Render.** Write the picks to `cards.json` (a JSON array of those objects),
   then `python -m finder.cli --render cards.json --category "<category>"` to
   produce the standard HTML report in `output/`. Summarize the top picks inline.

`--brief` and `--render` need no API key or model backend — they're pure
scaffolding; the intelligence is the agent.

## Run it normally (its own backend)

The tool can also do the model work itself via a configured backend
(`LLM_PROVIDER` = anthropic / openai-compatible / local / none). See `README.md`.
`python -m finder.cli -h` lists every flag.

## Conventions

- Python 3.11+. Type hints on function signatures; small, single-purpose functions.
- Never commit `.env`, API keys, or a user's `profile.json` / `context.txt`
  (already in `.gitignore`).
- Tests: `python -m pytest -q` (no network, no API).
