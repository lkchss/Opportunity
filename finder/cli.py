"""Opportunity Finder — command-line interface.

Bring your own backend. Pick how the model side runs entirely from the
environment (or the matching flags below):

  # Claude API
  LLM_PROVIDER=anthropic  ANTHROPIC_API_KEY=sk-ant-...   python -m finder.cli --category Jobs ...

  # OpenAI
  LLM_PROVIDER=openai     OPENAI_API_KEY=sk-...          python -m finder.cli ...

  # Local open-source model via Ollama (no key, no cloud)
  LLM_PROVIDER=openai  LLM_BASE_URL=http://localhost:11434/v1  LLM_MODEL=llama3.1  python -m finder.cli ...

  # Local via LM Studio
  LLM_PROVIDER=openai  LLM_BASE_URL=http://localhost:1234/v1   LLM_MODEL=<loaded-model>  python -m finder.cli ...

  # No model at all — DuckDuckGo keyword results only
  LLM_PROVIDER=none       python -m finder.cli ...

A saved profile (profile.json from the Streamlit portal) works too:
  python -m finder.cli --profile profile.json
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from finder import llm
from finder.pipeline import find_opportunities
from finder.report import render

CATEGORIES = [
    "Jobs",
    "Internships",
    "Graduate school",
    "Fellowships / Scholarships",
    "Gap year programs",
    "Travel / Volunteer",
]


def _read_resume(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Resume not found: {path}")
    if p.suffix.lower() == ".pdf":
        import pypdf

        reader = pypdf.PdfReader(str(p))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return p.read_text(encoding="utf-8")


def _load_profile(args: argparse.Namespace) -> dict:
    profile: dict = {}
    if args.profile:
        profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    # Flags override saved-profile fields when provided.
    for key in ("category", "role", "field", "location", "background", "goals"):
        val = getattr(args, key, None)
        if val:
            profile[key] = val
    if args.resume:
        profile["resume_text"] = _read_resume(args.resume)
    profile.setdefault("category", "Jobs")
    return profile


def _apply_backend_overrides(args: argparse.Namespace) -> None:
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider
    if args.model:
        os.environ["LLM_MODEL"] = args.model
    if args.base_url:
        os.environ["LLM_BASE_URL"] = args.base_url
    if args.no_llm:
        os.environ["LLM_PROVIDER"] = "none"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="finder.cli",
        description="Find ranked opportunities. Bring your own LLM backend (or none).",
    )
    p.add_argument("--profile", help="Path to a saved profile.json")
    p.add_argument("--category", choices=CATEGORIES, help="What you're looking for")
    p.add_argument("--role", help="Role / job title")
    p.add_argument("--field", help="Field / discipline")
    p.add_argument("--location", help="Preferred location")
    p.add_argument("--background", help="Your background")
    p.add_argument("--goals", help="What you want")
    p.add_argument("--resume", help="Path to a resume (.pdf or .txt)")
    p.add_argument("--max", type=int, default=8, help="Max results (default 8)")

    p.add_argument("--provider", choices=["anthropic", "openai", "none"],
                   help="Override LLM_PROVIDER")
    p.add_argument("--model", help="Override LLM_MODEL")
    p.add_argument("--base-url", dest="base_url",
                   help="Override LLM_BASE_URL (e.g. http://localhost:11434/v1 for Ollama)")
    p.add_argument("--no-llm", action="store_true",
                   help="Skip the model; return DuckDuckGo keyword results")

    p.add_argument("--out", help="Output directory (default: <repo>/output)")
    p.add_argument("--json", action="store_true", help="Also write results as JSON")
    p.add_argument("--no-open", action="store_true", help="Do not open the report in a browser")
    return p


def run(argv: list[str] | None = None) -> Path:
    load_dotenv()
    args = build_parser().parse_args(argv)
    _apply_backend_overrides(args)

    profile = _load_profile(args)
    if not profile.get("goals") and not profile.get("background") and not profile.get("resume_text"):
        print("Provide at least --goals plus --background/--resume (or a --profile).", file=sys.stderr)
        sys.exit(2)

    cfg = llm.load_config()
    if cfg.warning:
        print(f"Note: {cfg.warning}", file=sys.stderr)
    print(f"Backend: {cfg.provider}" + (f" ({cfg.model})" if cfg.enabled else ""))

    result = find_opportunities(profile, cfg=cfg, max_results=args.max)
    print(f"Mode: {result.mode}")
    if result.queries:
        print(f"Searched {len(result.queries)} queries -> {result.candidate_count} candidates")
    print(f"Found {len(result.cards)} opportunities.\n")

    out_dir = Path(args.out) if args.out else Path(__file__).parent.parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    context = profile.get("goals", "")
    if profile.get("background"):
        context = f"{profile['background']} | Goals: {context}"
    out_path = out_dir / f"results_{stamp}.html"
    render(result.cards, profile.get("category", "Jobs"), context, out_path, mode=result.mode)
    print(f"Report saved: {out_path}")

    if args.json:
        json_path = out_dir / f"results_{stamp}.json"
        json_path.write_text(json.dumps(result.cards, indent=2), encoding="utf-8")
        print(f"JSON saved:   {json_path}")

    if not args.no_open:
        webbrowser.open(out_path.as_uri())
    return out_path


if __name__ == "__main__":
    run()
