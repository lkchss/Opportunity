do not generate additional .md files unless asked to.

read README.md for context on the project.

## Tech Stack
- Python 3.11+
- Streamlit (UI — runs in the browser, all Python)
- Anthropic Python SDK (Claude integration)
- python-dotenv (environment variable management)

## Directory Structure
```
app/
  main.py          # Streamlit entry point — run this to launch the app
  claude_client.py # All Claude API calls live here
tests/             # Test files
.github/
  ISSUE_TEMPLATE/  # Templates for GitHub issues
requirements.txt
.env.example       # Copy to .env and add ANTHROPIC_API_KEY
```

## Running the App
```bash
pip install -r requirements.txt
cp .env.example .env   # then open .env and add your Anthropic API key
streamlit run app/main.py
```

## Working on GitHub Issues
When assigned a GitHub issue:
1. Read the issue title, description, and acceptance criteria carefully.
2. Identify which files need to change (start by reading them before editing).
3. Implement only what the acceptance criteria describe — no extra features.
4. Commit with a message referencing the issue, e.g. `fix #12: add resume upload`.
5. Push to the feature branch.

## Code Conventions
- Use type hints on all function signatures.
- Keep functions small and single-purpose.
- All Claude API calls go through `app/claude_client.py`.
- All Streamlit UI code goes in `app/main.py` (or new files under `app/` for larger features).
- Never commit `.env` or API keys.
