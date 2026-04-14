import streamlit as st

st.title("Opportunity")

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
    if not no_lsat and (lsat < 120):
        st.warning("Please enter your LSAT score or check 'I haven't taken the LSAT yet'.")
    elif gpa == 0.0:
        st.warning("Please enter your GPA.")
    else:
        st.write("Profile submitted:")
        st.json({
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
        })
