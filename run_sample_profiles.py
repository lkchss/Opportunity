"""Run 10 sample profiles through matching algorithm."""

from app.data_loader import load_law_schools
from app.matcher import rank_schools


SAMPLE_PROFILES = [
    {
        "name": "Splitter (High LSAT, Low GPA)",
        "lsat": 173,
        "gpa": 3.0,
        "goal": "BigLaw",
        "practice_areas": ["Corporate", "M&A"],
        "geography": ["Northeast"],
        "scholarship": 7,
        "reach_preference": 5,
    },
    {
        "name": "Reverse Splitter (High GPA, Low LSAT)",
        "lsat": 150,
        "gpa": 3.9,
        "goal": "Public Interest",
        "practice_areas": ["Environmental", "Criminal"],
        "geography": ["West Coast", "Northeast"],
        "scholarship": 8,
        "reach_preference": 3,
    },
    {
        "name": "Balanced Applicant (Mid-High Stats)",
        "lsat": 165,
        "gpa": 3.7,
        "goal": "Federal Clerkship",
        "practice_areas": ["Constitutional", "Litigation"],
        "geography": ["Anywhere"],
        "scholarship": 5,
        "reach_preference": 5,
    },
    {
        "name": "Safety School Focus",
        "lsat": 155,
        "gpa": 3.5,
        "goal": "Government",
        "practice_areas": ["Tax", "Administrative"],
        "geography": ["Midwest"],
        "scholarship": 6,
        "reach_preference": 9,
    },
    {
        "name": "Elite Candidate (T14 Range)",
        "lsat": 172,
        "gpa": 3.85,
        "goal": "BigLaw",
        "practice_areas": ["Corporate", "IP", "International"],
        "geography": ["Northeast", "West Coast"],
        "scholarship": 4,
        "reach_preference": 2,
    },
    {
        "name": "Reach Seeker",
        "lsat": 168,
        "gpa": 3.6,
        "goal": "Academia",
        "practice_areas": ["Constitutional", "International"],
        "geography": ["Anywhere"],
        "scholarship": 3,
        "reach_preference": 1,
    },
    {
        "name": "Career Changer (Mixed Goals)",
        "lsat": 161,
        "gpa": 3.4,
        "goal": "In-house",
        "practice_areas": ["Corporate", "IP"],
        "geography": ["West Coast", "Southwest"],
        "scholarship": 7,
        "reach_preference": 6,
    },
    {
        "name": "No LSAT Yet",
        "lsat": None,
        "gpa": 3.8,
        "goal": "Unsure",
        "practice_areas": [],
        "geography": ["Northeast"],
        "scholarship": 5,
        "reach_preference": 5,
    },
    {
        "name": "Solo/Small Firm Aspirant",
        "lsat": 153,
        "gpa": 3.3,
        "goal": "Solo/Small Firm",
        "practice_areas": ["Litigation", "Family"],
        "geography": ["Southeast", "Midwest"],
        "scholarship": 9,
        "reach_preference": 7,
    },
    {
        "name": "Selective + Scholarship Focused",
        "lsat": 158,
        "gpa": 3.6,
        "goal": "BigLaw",
        "practice_areas": ["Corporate", "Litigation"],
        "geography": ["Anywhere"],
        "scholarship": 10,
        "reach_preference": 8,
    },
]


def main():
    """Run sample profiles and display results."""
    print("=" * 80)
    print("RUNNING 10 SAMPLE PROFILES THROUGH MATCHING ALGORITHM")
    print("=" * 80)

    # Load schools
    try:
        schools = load_law_schools()
        print(f"\n[OK] Loaded {len(schools)} law schools\n")
    except Exception as e:
        print(f"[ERROR] Error loading schools: {e}")
        return

    # Run each profile
    for i, profile_template in enumerate(SAMPLE_PROFILES, 1):
        profile_name = profile_template["name"]
        lsat_display = profile_template["lsat"] or "Not yet taken"

        print(f"\n{'=' * 80}")
        print(f"Profile {i}: {profile_name}")
        print(f"{'=' * 80}")
        print(f"LSAT: {lsat_display} | GPA: {profile_template['gpa']}")
        print(f"Goal: {profile_template['goal']}")
        print(f"Practice Areas: {', '.join(profile_template['practice_areas']) or 'None specified'}")
        print(f"Geography: {', '.join(profile_template['geography'])}")
        print(f"Scholarship Importance: {profile_template['scholarship']}/10")
        print(f"Reach Preference: {profile_template['reach_preference']}/10 (0=love reaches, 10=only safe)")

        # Run ranking
        try:
            ranked = rank_schools(profile_template, schools, top_n=10)

            print(f"\nTop 10 Matches:")
            print("-" * 80)

            for rank, school in enumerate(ranked, 1):
                tier_short = {
                    "safety": "SAFE",
                    "target": "TARGET",
                    "reach": "REACH",
                    "hard reach": "HARD",
                }.get(school["admissibility_tier"], "?")

                print(
                    f"{rank:2d}. {school['name']:40s} "
                    f"Score: {school['composite_score']:5.1f} "
                    f"{tier_short:6s} "
                    f"Goal Fit: {school['goal_fit_score']:5.1f}"
                )

        except ValueError as e:
            print(f"[ERROR] Error ranking schools: {e}")


if __name__ == "__main__":
    main()
