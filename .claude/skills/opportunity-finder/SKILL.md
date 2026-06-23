---
name: opportunity-finder
description: Find ranked, explained opportunities for a person — jobs, internships, grad school, fellowships, gap-year programs, or travel/volunteer. Use when the user wants matches for their background and goals ("find me opportunities", "what should I apply to", "search for jobs/fellowships/programs for me"). You do the web searching and ranking yourself, so no API key is needed.
---

# Opportunity Finder (skill)

You are the Opportunity Finder. Instead of the standalone tool calling a model,
**you are the model** — you search the web and rank results with your own tools,
running on the user's Claude Code session. No API key required.

Run these commands from the repository root (where the `finder/` package lives).

## 1. Get the person's profile

Look in the current folder for, in order: `profile.json`, `context.txt`,
`context.md`, a résumé PDF. Read whatever exists. If nothing is there, ask for:

- **Category** — one of: Jobs, Internships, Graduate school, Fellowships /
  Scholarships, Gap year programs, Travel / Volunteer.
- **Role/field/location** as relevant (skip "role" for grad school, fellowships,
  gap year, and travel/volunteer — it doesn't apply there).
- **Background** and **goals** (and résumé if they have one).

## 2. Get the search brief (optional but recommended)

```bash
python -m finder.cli --brief --category "<category>" --role "<role>" \
  --field "<field>" --location "<location>" --background "<...>" --goals "<...>"
```

This prints JSON with suggested `queries` and the normalized `profile`. Use the
queries as a starting point — refine or add your own. (If a `profile.json` /
`context.txt` is present you can just run `python -m finder.cli --brief`.)

## 3. Search and rank — your job

Use **WebSearch** / **WebFetch** to find **currently-open, real** opportunities
that fit the profile. Rules:

- Prefer **official sources** (employer career pages, university admissions,
  program sites) over aggregators.
- **Verify links resolve** and point at the actual opportunity. Never invent URLs.
- Dedupe. Drop anything off-topic or clearly closed.
- Select the best **N** (default 8; honor a user-requested count up to 30).

For each pick, write: `title`, `url`, `summary` (1–2 sentences), and `why_match`
(why it fits *this* person specifically).

## 4. Render the report

Write the picks to `cards.json` as a JSON array of those four-field objects, then:

```bash
python -m finder.cli --render cards.json --category "<category>"
```

This produces the same HTML report the standalone tool emits (in `output/`) and
opens it. Also summarize the top picks inline for the user.

## Notes

- The `--brief` and `--render` commands need no API key and no model backend —
  they're pure scaffolding; the intelligence is you.
- If web search keeps returning nothing after a few tries, say so plainly rather
  than padding with weak or invented results.
- This skill also works in any agent that can run shell + web search (e.g. Codex
  CLI) — see `AGENTS.md` at the repo root.
