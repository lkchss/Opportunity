import streamlit as st
from app.data_loader import load_law_schools, DataValidationError
from app.matcher import rank_schools
# LLM narratives disabled for v1 (will add in v2)
# from app.llm_client import generate_narrative, RateLimitError, LLMProviderError


@st.cache_data
def get_schools() -> list[dict]:
    """Load and cache law schools for the session."""
    return load_law_schools()


# Load schools at startup
try:
    schools = get_schools()
except FileNotFoundError:
    st.error("Error: law_schools.json not found. Please ensure app/data/law_schools.json exists.")
    st.stop()
except DataValidationError as e:
    st.error(f"Error: Invalid law school data - {e}")
    st.stop()


st.set_page_config(page_title="Opportunity - Law School Match", layout="wide")

st.title("Opportunity")
st.markdown("*Find your best-fit law schools based on your profile and goals.*")

with st.form("profile_form"):

    st.subheader("Academic Profile")
    no_lsat = st.checkbox("I haven't taken the LSAT yet")
    lsat = st.number_input("LSAT Score", min_value=120, max_value=180, value=150, disabled=no_lsat)
    gpa = st.number_input("Undergraduate GPA", min_value=0.0, max_value=4.0, value=3.5, step=0.01)
    undergrad_school = st.text_input("Undergraduate School (optional)", placeholder="e.g. University of Michigan")
    undergrad_major = st.text_input("Undergraduate Major", placeholder="e.g. Political Science")

    st.subheader("Career Goals")
    goal = st.selectbox(
        "Primary Career Goal",
        ["BigLaw", "Federal Clerkship", "Public Interest", "Government", "In-house", "Academia", "Solo/Small Firm", "Unsure"],
    )
    practice_areas = st.multiselect(
        "Practice Area Interests",
        ["Corporate", "Litigation", "IP", "Tax", "Constitutional", "Environmental", "International", "Criminal", "Family", "Health", "Employment", "Antitrust"],
    )

    st.subheader("Preferences")
    geography = st.multiselect(
        "Geographic Preferences",
        ["Northeast", "Southeast", "Midwest", "Southwest", "West Coast", "Anywhere"],
    )
    scholarship = st.radio(
        "Scholarship Importance",
        ["Must have significant scholarship", "Prefer but not required", "Cost is not a factor"],
    )
    reach = st.radio(
        "Willingness to Apply to Reach Schools",
        ["Only schools where I'm a strong candidate", "Willing to apply to reaches", "Want a balanced list"],
    )

    st.subheader("Background (Optional)")
    work_experience = st.text_area("Work Experience", placeholder="Briefly describe any relevant work experience...")
    achievements = st.text_area("Notable Achievements / Softs", placeholder="Awards, publications, leadership roles...")
    personal_statement = st.text_area("Personal Statement Themes", placeholder="What story do you want to tell?")

    submitted = st.form_submit_button("Find Schools")

if submitted:
    # Validation
    if not no_lsat and (lsat < 120):
        st.warning("Please enter your LSAT score or check 'I haven't taken the LSAT yet'.")
    elif gpa == 0.0:
        st.warning("Please enter your GPA.")
    else:
        # Build profile dict
        profile = {
            "lsat": None if no_lsat else lsat,
            "gpa": gpa,
            "undergrad_school": undergrad_school,
            "undergrad_major": undergrad_major,
            "goal": goal,
            "practice_areas": practice_areas,
            "geography": geography,
            "scholarship": scholarship,
            "reach_preference": reach,
            "work_experience": work_experience,
            "achievements": achievements,
            "personal_statement": personal_statement,
        }

        # Display summary
        lsat_display = "Not yet taken" if no_lsat else str(lsat)
        st.markdown(f"### You submitted LSAT: {lsat_display} | GPA: {gpa} | Goal: {goal}")
        st.markdown(f"Matching against {len(schools)} ABA-accredited law schools...")
        st.divider()

        # Rank schools
        st.info("🔍 Ranking schools by fit...")
        try:
            ranked = rank_schools(profile, schools, top_n=20)
        except ValueError as e:
            st.error(f"Error ranking schools: {e}")
            st.stop()

        if not ranked:
            st.warning("No schools matched your criteria. Try adjusting your preferences.")
            st.stop()

        # LLM narratives disabled for v1 (will add in v2)
        narratives_available = False
        narratives_dict = {}

        # Display school cards
        st.success("✓ Done! Here are your top 10 matches:")
        st.divider()

        for idx, school in enumerate(ranked[:10], 1):
            # Card container
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"### {idx}. {school['name']}")
                st.markdown(f"**{school['location']}** • [Visit Website →]({school['website_url']})")

            with col2:
                # Tier badge with color
                tier_colors = {
                    "safety": "🟢",
                    "target": "🔵",
                    "reach": "🟠",
                    "hard reach": "🔴",
                }
                tier_icon = tier_colors.get(school["admissibility_tier"], "⚪")
                st.markdown(f"**{tier_icon} {school['admissibility_tier'].title()}**")

            # Composite score progress bar
            composite = school["composite_score"]
            st.progress(min(composite / 100, 1.0))
            st.caption(f"Match Score: {composite:.0f}/100")

            # Key stats in columns
            stat_cols = st.columns(6)
            stat_cols[0].metric("LSAT Median", school["lsat_50"])
            stat_cols[1].metric("GPA Median", f"{school['gpa_50']:.2f}")

            # User's percentile (maps 25th-75th percentile range to 25-75)
            if profile["lsat"]:
                if profile["lsat"] < school["lsat_25"]:
                    lsat_pct = 10  # Below 25th
                elif profile["lsat"] >= school["lsat_75"]:
                    # Above 75th: estimate based on how far above
                    overage = (profile["lsat"] - school["lsat_75"]) / (school["lsat_75"] - school["lsat_50"]) * 10
                    lsat_pct = min(75 + overage, 99)
                else:
                    # Between 25th and 75th
                    lsat_pct = 25 + ((profile["lsat"] - school["lsat_25"]) / (school["lsat_75"] - school["lsat_25"])) * 50
                stat_cols[2].metric("Your LSAT %ile", f"{lsat_pct:.0f}%")
            else:
                stat_cols[2].metric("Your LSAT %ile", "N/A")

            stat_cols[3].metric("BigLaw %", f"{school['biglaw_pct']*100:.0f}%")
            stat_cols[4].metric("Clerkships %", f"{school['federal_clerkship_pct']*100:.0f}%")
            stat_cols[5].metric("Bar Pass %", f"{school['bar_pass_rate_first_time']*100:.0f}%")

            # Goal fit
            goal_fit = school["goal_fit_score"]
            st.markdown(f"**Goal Fit: {goal_fit:.0f}%** — Matches your {goal} career goal based on this school's employment outcomes.")

            # Scholarship
            scholarship_score = school["scholarship_likelihood_score"]
            if scholarship_score >= 65:
                scholarship_text = "🟢 Likely merit aid"
            elif scholarship_score >= 50:
                scholarship_text = "🟡 Possible merit aid"
            else:
                scholarship_text = "🔴 Unlikely merit aid"
            st.markdown(f"**Scholarship:** {scholarship_text}")

            # LLM Narratives (if available)
            if narratives_available and school["id"] in narratives_dict:
                narrative = narratives_dict[school["id"]]
                st.markdown("**Why This Fits You:**")
                st.markdown(narrative.get("why_it_fits", ""))

                st.markdown("**Things to Consider:**")
                st.markdown(narrative.get("concerns", ""))

                st.markdown("**Next Step:**")
                st.info(narrative.get("next_step", ""))
            elif not narratives_available:
                st.caption("*(Personalized narratives unavailable; check back later)*")

            st.divider()
