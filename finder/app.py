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
    "None (keyword only)": {"provider": "none"},
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
    if cfg.provider == "anthropic":
        return "Claude (Anthropic)"
    if cfg.provider == "none":
        return "None (keyword only)"
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

    if provider == "none":
        st.sidebar.caption("No model — results are raw DuckDuckGo hits.")
        return llm.LLMConfig("none", "", None, None)

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
    st.set_page_config(page_title="Opportunity Finder", layout="wide")
    st.title("Opportunity Finder")
    st.caption("Tell us about you — the more detail you give, the better the matches.")

    cfg = _backend_sidebar()

    # Category lives OUTSIDE the form so changing it re-renders the right fields.
    category = st.selectbox("What are you looking for?", CATEGORIES, key="category")
    specs = FIELD_SPECS[category]

    with st.form("profile"):
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
        resume_file = st.file_uploader("Resume (optional PDF)", type=["pdf"])
        max_results = st.slider("Number of results", 3, 30, 8)

        submitted = st.form_submit_button("Find opportunities", type="primary")

    if submitted:
        resume_text = ""
        if resume_file is not None:
            reader = pypdf.PdfReader(io.BytesIO(resume_file.read()))
            resume_text = "\n".join(page.extract_text() or "" for page in reader.pages)

        if not (goals or background or resume_text):
            st.warning("Add at least your goals plus some background (or a resume).")
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
                "resume_text": resume_text,
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
        st.caption(f"Source: {result.mode}")
        st.subheader(f"Top {len(result.cards)} matches")
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
