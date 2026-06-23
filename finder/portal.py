"""Profile portal — saves user context to profile.json for Claude Code to consume."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pypdf
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

PROFILE_PATH = Path(__file__).parent.parent / "profile.json"

CATEGORIES = [
    "Jobs",
    "Internships",
    "Graduate school",
    "Fellowships / Scholarships",
    "Gap year programs",
    "Travel / Volunteer",
]


def load_profile() -> dict:
    if PROFILE_PATH.exists():
        return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    return {}


def save_profile(data: dict) -> None:
    PROFILE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def run() -> None:
    st.set_page_config(page_title="Opportunity Portal", layout="centered")
    st.title("Opportunity Portal")
    st.caption("Fill in your profile, then run `python -m finder.cli --profile profile.json`.")

    existing = load_profile()

    category = st.selectbox(
        "What are you looking for?",
        CATEGORIES,
        index=CATEGORIES.index(existing.get("category", CATEGORIES[0])),
    )
    role = st.text_input(
        "Role / job title",
        value=existing.get("role", ""),
        placeholder="e.g. Software Engineer, Product Manager",
    )
    field = st.text_input(
        "Field / discipline",
        value=existing.get("field", ""),
        placeholder="e.g. Computer Science, Public Policy, Biology",
    )
    location = st.text_input(
        "Preferred location",
        value=existing.get("location", ""),
        placeholder="e.g. New York, Remote, USA",
    )
    background = st.text_area(
        "Background",
        value=existing.get("background", ""),
        height=160,
        placeholder="Education, experience, skills — anything relevant.",
    )
    goals = st.text_area(
        "Goals",
        value=existing.get("goals", ""),
        height=120,
        placeholder="What you're looking for, constraints, ideal outcome.",
    )

    resume_text = existing.get("resume_text", "")
    resume_file = st.file_uploader("Resume (optional PDF)", type=["pdf"])
    if resume_file is not None:
        reader = pypdf.PdfReader(io.BytesIO(resume_file.read()))
        resume_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        st.success(f"Resume loaded — {len(reader.pages)} page(s)")
    elif resume_text:
        st.info("Resume loaded from saved profile.")

    if st.button("Save profile", type="primary"):
        profile = {
            "category": category,
            "role": role,
            "field": field,
            "location": location,
            "background": background,
            "goals": goals,
            "resume_text": resume_text,
        }
        save_profile(profile)
        st.success(
            f"Profile saved to `{PROFILE_PATH.name}`. "
            "Run `python -m finder.cli --profile profile.json`."
        )
        st.json(profile)


if __name__ == "__main__":
    run()
