import streamlit as st

st.title("Oportunity")

with st.form("profile_form"):
    lsat = st.number_input("LSAT Score", min_value=120, max_value=180, value=150)
    gpa = st.number_input("Undergraduate GPA", min_value=0.0, max_value=4.0, value=3.5, step=0.01)
    goal = st.selectbox(
        "Primary Career Goal",
        ["BigLaw", "Federal Clerkship", "Public Interest", "Government", "In-house", "Academia", "Unsure"],
    )
    submitted = st.form_submit_button("Find Schools")

if submitted:
    st.write("Profile submitted:")
    st.json({"lsat": lsat, "gpa": gpa, "goal": goal})
