# AGENTS.md — Opportunity Finder

Guidance for agentic CLIs (Codex CLI, Claude Code, and any agent that can run a
shell and search the web). This repo is a small Python tool; you can run it
normally **or** drive it as a skill where *you* are the model.

## The `/opportunity` command (no API key)

The canonical workflow lives in **`prompts/opportunity.md`** — one self-contained
prompt that makes you (the agent) act as the Opportunity Finder using your own
web search + reasoning. No model API key or backend needed.

Summon it explicitly with **`/opportunity`** (not by phrasing). Each CLI loads the
same prompt from its own command directory:

| CLI | Command file (→ `/opportunity`) |
|---|---|
| **Claude Code** | `.claude/commands/opportunity.md` (in-repo, already here) |
| **opencode** | `.opencode/command/opportunity.md` (in-repo, already here) |
| **Codex CLI** | copy `prompts/opportunity.md` → `~/.codex/prompts/opportunity.md` |
| **Other agent CLIs** | point a custom command/prompt at `prompts/opportunity.md`, or just tell the agent: "follow prompts/opportunity.md" |

The launchers are thin — they read `prompts/opportunity.md` and follow it, so there
is one source of truth. If your CLI has no slash-command system, open it in this
repo and say *"read `prompts/opportunity.md` and follow it."*

The workflow uses two keyless helper commands: `python -m finder.cli --brief`
(emit the normalized profile as JSON) and `python -m finder.cli --render cards.json`
(write the standard HTML report from your picks).

## Run it normally (its own backend)

The tool can also do the model work itself via a configured backend
(`LLM_PROVIDER` = anthropic / openai-compatible / local). See `README.md`.
`python -m finder.cli -h` lists every flag.

## Conventions

- Python 3.11+. Type hints on function signatures; small, single-purpose functions.
- Never commit `.env`, API keys, or a user's `profile.json` / `context.txt`
  (already in `.gitignore`).
- Tests: `python -m pytest -q` (no network, no API).
