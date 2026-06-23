"""Convenience entry point: run the finder from a saved profile.json.

Equivalent to `python -m finder.cli --profile profile.json`. For the full set of
flags (category, backend overrides, output options) use `python -m finder.cli`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from finder.cli import run as cli_run

PROFILE_PATH = Path(__file__).parent.parent / "profile.json"


def run(profile: dict | None = None, open_browser: bool = True) -> Path:
    argv = ["--profile", str(PROFILE_PATH)]
    if not open_browser:
        argv.append("--no-open")
    return cli_run(argv)


if __name__ == "__main__":
    if not PROFILE_PATH.exists():
        raise SystemExit(
            "profile.json not found. Open the portal "
            "(streamlit run finder/portal.py) and save your profile first, "
            "or use `python -m finder.cli` with flags."
        )
    run()
