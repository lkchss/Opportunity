"""Flask web app for the Opportunity Finder.

    python -m finder.server      # http://127.0.0.1:5000

Serves the static frontend in web/ and exposes POST /api/find, which runs the
same pipeline as the CLI. The model backend is configured server-side via the
environment (LLM_PROVIDER / LLM_MODEL / LLM_BASE_URL / API keys); with none set
it falls back to keyword-only DuckDuckGo results.
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

from finder.pipeline import find_opportunities

load_dotenv()

WEB = Path(__file__).parent / "web"
MAX_RESULTS = 30

app = Flask(__name__, static_folder=None)


def _doc_text(file_storage) -> str:
    """Extract text from an uploaded résumé/context file (PDF or plain text)."""
    if not file_storage or not file_storage.filename:
        return ""
    data = file_storage.read()
    if file_storage.filename.lower().endswith(".pdf"):
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return data.decode("utf-8", errors="replace")


@app.get("/")
def index():
    return send_from_directory(WEB, "index.html")


@app.get("/<path:path>")
def static_files(path):
    return send_from_directory(WEB, path)


@app.post("/api/find")
def api_find():
    form = request.form
    profile = {
        "category": form.get("category", "Jobs"),
        "role": form.get("role", ""),
        "field": form.get("field", ""),
        "location": form.get("location", ""),
        "background": form.get("background", ""),
        "goals": form.get("goals", ""),
        "context": _doc_text(request.files.get("doc")),
    }
    if not (profile["goals"] or profile["background"] or profile["context"]):
        return jsonify({"error": "Tell us your goals plus some background, or upload a document."}), 400

    try:
        max_results = min(max(int(form.get("max", 8)), 1), MAX_RESULTS)
    except (TypeError, ValueError):
        max_results = 8

    try:
        result = find_opportunities(profile, max_results=max_results)
    except Exception as e:  # backend / network failure -> surface to the UI
        return jsonify({"error": str(e)}), 502

    return jsonify(
        {"cards": result.cards, "mode": result.mode, "candidates": result.candidate_count}
    )


def main() -> None:
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)


if __name__ == "__main__":
    main()
