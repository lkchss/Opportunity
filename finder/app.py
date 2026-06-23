"""Streamlit entry point for the Opportunity Finder.

Bring your own backend: the sidebar offers presets for Claude, OpenAI, local
servers (Ollama / LM Studio), OpenRouter, or any custom OpenAI-compatible
endpoint — or no model at all. Defaults come from the environment
(LLM_PROVIDER / LLM_MODEL / LLM_BASE_URL), so a configured .env preselects the
right preset.

    streamlit run finder/app.py
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pypdf
import streamlit as st
from dotenv import load_dotenv

from finder import llm
from finder.pipeline import find_opportunities

load_dotenv()

# Type + voice borrowed from "Opportunity: Law" (Source Serif 4 display over IBM
# Plex Sans), but black & white.
STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap');

:root { --ink:#111111; --soft:#555555; --paper:#ffffff; }

.stApp { background: var(--paper); }
html, body, .stApp, [class*="st-"], button, input, textarea, select {
  font-family: 'IBM Plex Sans', -apple-system, "Segoe UI", sans-serif;
}
h1, h2, h3 {
  font-family: 'Source Serif 4', Georgia, serif !important;
  font-weight: 700; letter-spacing: -0.015em; color: var(--ink);
}

.op-brand { font-family: 'Source Serif 4', Georgia, serif; font-weight: 700;
  font-size: 20px; letter-spacing: -0.01em; color: var(--ink); }
.op-display { font-family: 'Source Serif 4', Georgia, serif; font-weight: 700;
  font-size: 40px; line-height: 1.1; letter-spacing: -0.02em; color: var(--ink);
  margin: 6px 0 10px; }
.op-lede { font-size: 15px; line-height: 1.55; color: var(--soft);
  max-width: 660px; margin: 0; }

.stButton > button { border-radius: 8px; font-weight: 600; }
</style>
"""

MASTHEAD = """
<div class="op-brand">Opportunity</div>
<div class="op-display">What should you do next</div>
<p class="op-lede">Tell us a little about yourself. We'll search the web and rank
real, currently-open opportunities by how well they fit your background and goals —
and tell you why each one makes the list.</p>
"""

CATEGORIES = [
    "Jobs",
    "Internships",
    "Graduate school",
    "Fellowships / Scholarships",
    "Gap year programs",
    "Travel / Volunteer",
]

# Which of role / field / location to show per category, with category-specific
# labels + placeholders. "Role / title" only makes sense for jobs & internships.
FIELD_SPECS: dict[str, dict[str, tuple[str, str]]] = {
    "Jobs": {
        "role": ("Role / title", "e.g. Data Analyst"),
        "field": ("Field / industry", "e.g. Fintech"),
        "location": ("Location", "e.g. Remote, Bay Area"),
    },
    "Internships": {
        "role": ("Role / title", "e.g. Software Engineering Intern"),
        "field": ("Field / industry", "e.g. Robotics"),
        "location": ("Location", "e.g. Remote, NYC"),
    },
    "Graduate school": {
        "field": ("Field of study", "e.g. Public Policy"),
        "location": ("Location", "e.g. US, Europe"),
    },
    "Fellowships / Scholarships": {
        "field": ("Field / focus", "e.g. Climate, Journalism"),
        "location": ("Location / eligibility", "e.g. US citizens, global"),
    },
    "Gap year programs": {
        "field": ("Interests / focus", "e.g. Conservation, Language"),
        "location": ("Location", "e.g. Latin America, anywhere"),
    },
    "Travel / Volunteer": {
        "field": ("Cause / interest", "e.g. Wildlife, Teaching"),
        "location": ("Destination / region", "e.g. Southeast Asia"),
    },
}

# Sidebar backend presets. Each maps to a provider (+ base_url / default model
# for OpenAI-compatible servers). `local` servers don't need an API key.
PRESETS: dict[str, dict] = {
    "Claude (Anthropic)": {"provider": "anthropic"},
    "OpenAI": {"provider": "openai", "base_url": None},
    "Ollama (local)": {"provider": "openai", "base_url": "http://localhost:11434/v1",
                       "model": "llama3.1", "local": True},
    "LM Studio (local)": {"provider": "openai", "base_url": "http://localhost:1234/v1",
                          "local": True},
    "OpenRouter": {"provider": "openai", "base_url": "https://openrouter.ai/api/v1"},
    "Custom (OpenAI-compatible)": {"provider": "openai", "base_url": ""},
}

MODEL_HINTS = {
    "Ollama (local)": "llama3.1, qwen2.5, glm4, mistral …",
    "LM Studio (local)": "the model id loaded in LM Studio",
    "OpenRouter": "openai/gpt-4o-mini, z-ai/glm-4.6, anthropic/claude-3.5-sonnet …",
    "OpenAI": "gpt-4o-mini, gpt-4o …",
    "Custom (OpenAI-compatible)": "model id your endpoint expects",
}


def _preset_for(cfg: llm.LLMConfig) -> str:
    """Best-guess preset for the environment-derived config."""
    if cfg.provider == "anthropic" or cfg.provider == "none":
        return "Claude (Anthropic)"
    b = (cfg.base_url or "").lower()
    if "11434" in b:
        return "Ollama (local)"
    if "1234" in b:
        return "LM Studio (local)"
    if "openrouter" in b:
        return "OpenRouter"
    if not b:
        return "OpenAI"
    return "Custom (OpenAI-compatible)"


def _backend_sidebar() -> llm.LLMConfig:
    st.sidebar.header("Model backend")
    env_cfg = llm.load_config()
    if env_cfg.warning:
        st.sidebar.warning(env_cfg.warning)

    names = list(PRESETS)
    default = _preset_for(env_cfg)
    choice = st.sidebar.selectbox("Backend", names, index=names.index(default))
    preset = PRESETS[choice]
    provider = preset["provider"]

    if provider == "anthropic":
        model = st.sidebar.text_input(
            "Model", value=env_cfg.model or llm.DEFAULT_ANTHROPIC_MODEL,
            help="e.g. claude-opus-4-8, claude-sonnet-4-6, claude-haiku-4-5",
        )
        api_key = st.sidebar.text_input("ANTHROPIC_API_KEY", value=env_cfg.api_key or "", type="password")
        return llm.LLMConfig("anthropic", model or "", None, api_key or None)

    # OpenAI-compatible presets (OpenAI / Ollama / LM Studio / OpenRouter / custom)
    local = preset.get("local", False)
    base_url = preset.get("base_url")
    if choice == "Custom (OpenAI-compatible)":
        base_url = st.sidebar.text_input(
            "Base URL", value=env_cfg.base_url or "", placeholder="https://your-endpoint/v1"
        ) or None
    elif local:
        base_url = st.sidebar.text_input(
            "Base URL", value=base_url, help="Change only if your server uses a different port."
        )
    else:  # OpenAI / OpenRouter — fixed endpoint, just show it
        st.sidebar.caption(f"Endpoint: {base_url or 'https://api.openai.com/v1'}")

    default_model = preset.get("model") or (env_cfg.model if choice == _preset_for(env_cfg) else "")
    model = st.sidebar.text_input("Model", value=default_model, placeholder=MODEL_HINTS.get(choice, ""))

    if local:
        key_in = st.sidebar.text_input(
            "API key (optional)", value="", type="password",
            help="Most local servers don't need one.",
        )
        api_key = key_in or "not-needed"
    else:
        api_key = st.sidebar.text_input("API key", value=env_cfg.api_key or "", type="password")
        if not api_key and base_url:
            api_key = "not-needed"

    return llm.LLMConfig("openai", model or "", base_url, api_key or None)


def run() -> None:
    st.set_page_config(page_title="Opportunity", layout="wide")
    st.markdown(STYLE, unsafe_allow_html=True)
    st.markdown(MASTHEAD, unsafe_allow_html=True)

    cfg = _backend_sidebar()

    # Category lives OUTSIDE the form so changing it re-renders the right fields.
    category = st.selectbox("What are you looking for?", CATEGORIES, key="category")
    specs = FIELD_SPECS[category]

    with st.form("profile"):
        st.markdown("Tell us about yourself — upload a document, fill in the details, "
                    "or both. They count equally.")

        doc_file = st.file_uploader(
            "Upload a context document (PDF or text)",
            type=["pdf", "txt", "md"],
            help="A résumé, a bio, notes on what you want — anything. Weighted the "
            "same as the fields below; the model reads it to search and rank.",
        )

        keys = list(specs.keys())
        cols = st.columns(len(keys))
        values: dict[str, str] = {}
        for col, key in zip(cols, keys):
            label, placeholder = specs[key]
            values[key] = col.text_input(label, placeholder=placeholder)

        background = st.text_area(
            "Your background",
            height=150,
            placeholder="Education, work experience, skills — anything relevant.",
        )
        goals = st.text_area(
            "What you want",
            height=110,
            placeholder="Ideal outcome and constraints (timing, location, compensation).",
        )
        max_results = st.slider("Number of results", 3, 30, 8)

        submitted = st.form_submit_button("Find opportunities", type="primary")

    if submitted:
        context_text = ""
        if doc_file is not None:
            if doc_file.name.lower().endswith(".pdf"):
                reader = pypdf.PdfReader(io.BytesIO(doc_file.read()))
                context_text = "\n".join(page.extract_text() or "" for page in reader.pages)
            else:
                context_text = doc_file.read().decode("utf-8", errors="replace")
            st.caption(f"Loaded {doc_file.name} ({len(context_text):,} chars) as context.")

        if not (goals or background or context_text):
            st.warning("Upload a document, or fill in your goals plus some background.")
        elif cfg.enabled and not cfg.model:
            st.warning("Enter a model name for the selected backend in the sidebar.")
        else:
            profile = {
                "category": category,
                "role": values.get("role", ""),
                "field": values.get("field", ""),
                "location": values.get("location", ""),
                "background": background,
                "goals": goals,
                "context": context_text,
            }
            with st.spinner("Searching..."):
                try:
                    result = find_opportunities(profile, cfg=cfg, max_results=max_results)
                except Exception as e:  # surface backend/network errors in the UI
                    st.error(str(e))
                    return
            st.session_state["result"] = result
            st.session_state["profile"] = profile

    result = st.session_state.get("result")
    if result and result.cards:
        st.subheader("Your matches")
        st.caption(f"{len(result.cards)} opportunities · {result.mode}")
        for r in result.cards:
            with st.container(border=True):
                st.markdown(f"### [{r['title']}]({r['url']})")
                st.write(r.get("summary", ""))
                if r.get("why_match"):
                    st.markdown(f"**Why this fits:** {r['why_match']}")
        if st.session_state.get("profile"):
            st.download_button(
                "Save these inputs (profile.json)",
                data=json.dumps(st.session_state["profile"], indent=2),
                file_name="profile.json",
                mime="application/json",
                help="Reuse later with: python -m finder.cli --profile profile.json",
            )
    elif result is not None:
        st.warning("No results found. Try adding more detail to your background or goals.")


if __name__ == "__main__":
    run()
