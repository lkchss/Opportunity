import streamlit as st
from claude_client import get_recommendations

st.set_page_config(page_title="Oportunity", page_icon="🔭", layout="centered")

st.title("Oportunity")
st.write("Tell us about yourself and what you're looking for — we'll find your next step.")

with st.form("profile_form"):
    background = st.text_area(
        "Your background",
        placeholder="Describe your education, work experience, skills, and interests...",
        height=150,
    )
    goals = st.text_area(
        "What are you looking for?",
        placeholder="Graduate school, a new job, a gap year, travel, something else?",
        height=100,
    )
    submitted = st.form_submit_button("Find Opportunities")

if submitted:
    if not background.strip() or not goals.strip():
        st.warning("Please fill in both fields before searching.")
    else:
        with st.spinner("Finding opportunities tailored for you..."):
            try:
                results = get_recommendations(background, goals)
                st.markdown("### Your Recommendations")
                st.markdown(results)
            except Exception as e:
                st.error(f"Something went wrong: {e}")
