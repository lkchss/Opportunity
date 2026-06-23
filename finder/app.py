"""Streamlit entry point for the Opportunity Finder.

Bring your own backend: the sidebar picks Claude, an OpenAI-compatible endpoint
(including local Ollama / LM Studio), or no model at all. Defaults come from the
environment (LLM_PROVIDER / LLM_MODEL / LLM_BASE_URL), so a configured .env just
works without touching the sidebar.

    streamlit run finder/app.py
"""
from __future__ import annotations

import io
import os
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


def _backend_sidebar() -> llm.LLMConfig:
    st.sidebar.header("Model backend")
    env_cfg = llm.load_config()
    if env_cfg.warning:
        st.sidebar.warning(env_cfg.warning)
    providers = ["anthropic", "openai", "none"]
    provider = st.sidebar.selectbox(
        "Provider",
        providers,
        index=providers.index(env_cfg.provider) if env_cfg.provider in providers else 2,
        help="anthropic = Claude API · openai = OpenAI or any compatible endpoint "
        "(OpenRouter, Groq, Ollama, LM Studio) · none = keyword search only",
    )

    model = env_cfg.model
    base_url = env_cfg.base_url
    api_key = env_cfg.api_key

    if provider == "anthropic":
        model = st.sidebar.text_input("Model", value=model or llm.DEFAULT_ANTHROPIC_MODEL)
        api_key = st.sidebar.text_input(
            "ANTHROPIC_API_KEY", value=api_key or "", type="password"
        ) or api_key
    elif provider == "openai":
        model = st.sidebar.text_input("Model", value=model or llm.DEFAULT_OPENAI_MODEL)
        base_url = st.sidebar.text_input(
            "Base URL (optional)",
            value=base_url or "",
            help="Leave blank for OpenAI. For Ollama use http://localhost:11434/v1, "
            "for LM Studio http://localhost:1234/v1.",
        ) or None
        api_key = st.sidebar.text_input(
            "API key", value=api_key or "", type="password",
            help="Not needed for most local servers.",
        ) or api_key
        if not api_key and base_url:
            api_key = "not-needed"
    else:
        st.sidebar.caption("No model — results are raw DuckDuckGo hits.")

    return llm.LLMConfig(provider=provider, model=model or "", base_url=base_url, api_key=api_key)


def run() -> None:
    st.set_page_config(page_title="Opportunity Finder", layout="wide")
    st.title("Opportunity Finder")
    st.caption("Tell us about you. We'll search for matching opportunities.")

    cfg = _backend_sidebar()

    category = st.selectbox("What are you looking for?", CATEGORIES)

    resume_file = st.file_uploader("Resume (optional PDF)", type=["pdf"])
    resume_text: str = ""
    if resume_file is not None:
        reader = pypdf.PdfReader(io.BytesIO(resume_file.read()))
        resume_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        st.success(f"Resume loaded — {len(reader.pages)} page(s)")

    background = st.text_area(
        "Your background",
        height=180,
        placeholder="Education, work experience, skills, location, anything relevant.",
    )
    goals = st.text_area(
        "What you want",
        height=120,
        placeholder="What kind of opportunity, ideal outcome, constraints (timing, location, compensation).",
    )

    ready = bool(goals and (background or resume_text))
    if st.button("Find opportunities", type="primary", disabled=not ready):
        profile = {
            "category": category,
            "background": background,
            "goals": goals,
            "resume_text": resume_text,
        }
        with st.spinner("Searching..."):
            try:
                result = find_opportunities(profile, cfg=cfg)
            except RuntimeError as e:
                st.error(str(e))
                return
        st.session_state["result"] = result

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
    elif result is not None:
        st.warning("No results found. Try adding more detail to your background or goals.")


if __name__ == "__main__":
    run()
