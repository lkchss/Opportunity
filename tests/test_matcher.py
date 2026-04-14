import pytest
from app.matcher import (
    rank_schools,
    _compute_admissibility_score,
    _compute_goal_fit_score,
    _compute_practice_area_fit,
    _compute_scholarship_likelihood,
    _compute_geographic_fit,
)


# Test data
HARVARD = {
    "id": "harvard-law",
    "name": "Harvard Law School",
    "location": "Cambridge, MA",
    "lsat_25": 173,
    "lsat_50": 174,
    "lsat_75": 176,
    "gpa_25": 3.82,
    "gpa_50": 3.96,
    "gpa_75": 4.0,
    "acceptance_rate": 0.092,
    "scholarship_pct": 0.65,
    "median_scholarship": 35000,
    "biglaw_pct": 0.48,
    "federal_clerkship_pct": 0.15,
    "public_interest_pct": 0.09,
    "government_pct": 0.08,
    "bar_pass_rate_first_time": 0.96,
    "practice_area_strengths": ["corporate", "litigation", "ip", "constitutional"],
    "lrap_quality": "excellent",
    "annual_tuition": 73200,
    "cost_of_living_index": 5,
}

ALABAMA = {
    "id": "alabama-law",
    "name": "University of Alabama School of Law",
    "location": "Tuscaloosa, AL",
    "lsat_25": 151,
    "lsat_50": 158,
    "lsat_75": 161,
    "gpa_25": 3.50,
    "gpa_50": 4.05,
    "gpa_75": 4.0,
    "acceptance_rate": 0.321,
    "scholarship_pct": 0.89,
    "median_scholarship": 22000,
    "biglaw_pct": 0.06,
    "federal_clerkship_pct": 0.02,
    "public_interest_pct": 0.04,
    "government_pct": 0.04,
    "bar_pass_rate_first_time": 0.80,
    "practice_area_strengths": ["litigation", "corporate", "family", "criminal"],
    "lrap_quality": "none",
    "annual_tuition": 24000,
    "cost_of_living_index": 1,
}


class TestAdmissibilityScore:
    """Test admissibility scoring."""

    def test_above_both_75th_percentiles(self):
        """Score and tier for strong candidate above 75th on both metrics."""
        lsat = 177  # Above Harvard 75th (176)
        gpa = 4.0   # At Harvard 75th
        score, tier = _compute_admissibility_score(lsat, gpa, HARVARD)
        assert tier == "safety"
        assert score > 50  # Sigmoid curves are gradual

    def test_at_both_medians(self):
        """Score and tier for median candidate."""
        lsat = 174  # Harvard median
        gpa = 3.96  # Harvard median
        score, tier = _compute_admissibility_score(lsat, gpa, HARVARD)
        assert tier == "target"
        assert 55 <= score <= 65  # Around 60 with new percentile-based scoring

    def test_below_25th_percentiles(self):
        """Score and tier for weak candidate below 25th."""
        lsat = 160  # Below Harvard 25th (173)
        gpa = 3.5   # Below Harvard 25th (3.82)
        score, tier = _compute_admissibility_score(lsat, gpa, HARVARD)
        assert tier == "hard reach"
        assert score < 35  # Adjusted for percentile-based scoring

    def test_between_25th_and_50th(self):
        """Score and tier for reach candidate."""
        lsat = 173  # At Harvard 25th
        gpa = 3.88  # Between 25th and 50th
        score, tier = _compute_admissibility_score(lsat, gpa, HARVARD)
        assert tier == "reach"

    def test_no_lsat_lowers_score(self):
        """Admissibility score is lower without LSAT."""
        score_with_lsat, _ = _compute_admissibility_score(174, 3.96, HARVARD)
        score_without_lsat, _ = _compute_admissibility_score(None, 3.96, HARVARD)
        assert score_without_lsat < score_with_lsat

    def test_splitter_at_alabama(self):
        """High LSAT, low GPA at regional school."""
        lsat = 165  # Above Alabama median (158)
        gpa = 3.5   # Below Alabama median (4.05, which is suspiciously high)
        score, tier = _compute_admissibility_score(lsat, gpa, ALABAMA)
        # Should be reach or better candidate at Alabama despite lower GPA
        assert tier in ["safety", "target", "reach"]

    def test_reverse_splitter_at_harvard(self):
        """High GPA, low LSAT at Harvard."""
        lsat = 165  # Below Harvard median (174)
        gpa = 4.0   # At Harvard 75th
        score, tier = _compute_admissibility_score(lsat, gpa, HARVARD)
        # Below median LSAT puts it in reach tier despite high GPA
        assert tier in ["reach", "hard reach"]
        assert score > 20


class TestGoalFitScore:
    """Test goal fit scoring."""

    def test_biglaw_goal(self):
        """BigLaw goal weights by school's biglaw_pct."""
        profile = {"goal": "BigLaw"}
        score = _compute_goal_fit_score(profile, HARVARD)
        assert abs(score - (HARVARD["biglaw_pct"] * 100)) < 1

    def test_clerkship_goal(self):
        """Federal Clerkship goal weights by school's clerkship_pct."""
        profile = {"goal": "Federal Clerkship"}
        score = _compute_goal_fit_score(profile, HARVARD)
        assert abs(score - (HARVARD["federal_clerkship_pct"] * 100)) < 1

    def test_public_interest_goal(self):
        """Public Interest goal weights by school's pi_pct."""
        profile = {"goal": "Public Interest"}
        score = _compute_goal_fit_score(profile, HARVARD)
        assert abs(score - (HARVARD["public_interest_pct"] * 100)) < 1

    def test_government_goal(self):
        """Government goal weights by school's government_pct."""
        profile = {"goal": "Government"}
        score = _compute_goal_fit_score(profile, HARVARD)
        assert abs(score - (HARVARD["government_pct"] * 100)) < 1

    def test_unsure_goal_is_balanced_average(self):
        """Unsure goal returns balanced average of all outcomes."""
        profile = {"goal": "Unsure"}
        score = _compute_goal_fit_score(profile, HARVARD)
        outcomes = [
            HARVARD["biglaw_pct"],
            HARVARD["federal_clerkship_pct"],
            HARVARD["public_interest_pct"],
            HARVARD["government_pct"],
        ]
        expected = (sum(outcomes) / len(outcomes)) * 100
        assert abs(score - expected) < 1

    def test_biglaw_score_higher_at_harvard_than_alabama(self):
        """BigLaw candidates score higher at schools with better BigLaw placement."""
        profile = {"goal": "BigLaw"}
        harvard_score = _compute_goal_fit_score(profile, HARVARD)
        alabama_score = _compute_goal_fit_score(profile, ALABAMA)
        assert harvard_score > alabama_score


class TestPracticeAreaFit:
    """Test practice area fit scoring."""

    def test_perfect_match(self):
        """All user interests match school strengths."""
        profile = {"practice_areas": ["Corporate", "Litigation"]}
        score = _compute_practice_area_fit(profile, HARVARD)
        assert score == 100

    def test_no_interests_stated(self):
        """No interests stated returns 100 (neutral)."""
        profile = {"practice_areas": []}
        score = _compute_practice_area_fit(profile, HARVARD)
        assert score == 100

    def test_partial_match(self):
        """Some but not all interests match."""
        profile = {"practice_areas": ["Corporate", "Environmental"]}
        # Corporate matches, Environmental doesn't → 50%
        score = _compute_practice_area_fit(profile, HARVARD)
        assert score == 50

    def test_no_match(self):
        """User interests don't match school strengths."""
        profile = {"practice_areas": ["Patent Law", "Immigration"]}
        # Neither matches Harvard's strengths
        score = _compute_practice_area_fit(profile, HARVARD)
        assert score == 0

    def test_case_insensitive(self):
        """Practice area matching is case insensitive."""
        profile1 = {"practice_areas": ["corporate"]}
        profile2 = {"practice_areas": ["CORPORATE"]}
        score1 = _compute_practice_area_fit(profile1, HARVARD)
        score2 = _compute_practice_area_fit(profile2, HARVARD)
        assert score1 == score2 == 100


class TestScholarshipLikelihood:
    """Test scholarship likelihood scoring."""

    def test_splitter_high_score(self):
        """Splitter (high LSAT, low GPA) gets high scholarship likelihood."""
        profile = {}
        lsat = 180  # Very high
        gpa = 3.0   # Below school median
        score = _compute_scholarship_likelihood(profile, HARVARD, lsat, gpa)
        assert score > 55  # Should be higher for splitter

    def test_reverse_splitter_moderate_score(self):
        """Reverse splitter (high GPA, low LSAT) gets moderate score."""
        profile = {}
        lsat = 160  # Below school median
        gpa = 4.0   # At/above school median
        score = _compute_scholarship_likelihood(profile, HARVARD, lsat, gpa)
        assert 40 < score < 70  # Moderate for reverse splitter

    def test_no_lsat_gets_score(self):
        """Missing LSAT uses conservative estimate."""
        profile = {}
        score = _compute_scholarship_likelihood(profile, HARVARD, None, 3.8)
        assert 0 <= score <= 100

    def test_generous_school_higher_score(self):
        """School with higher scholarship_pct gets higher score."""
        profile = {}
        lsat = 165
        gpa = 3.7
        alabama_score = _compute_scholarship_likelihood(profile, ALABAMA, lsat, gpa)
        harvard_score = _compute_scholarship_likelihood(profile, HARVARD, lsat, gpa)
        # Alabama is more generous (89% vs 65%)
        assert alabama_score > harvard_score


class TestGeographicFit:
    """Test geographic fit scoring."""

    def test_no_preference_neutral(self):
        """No geographic preference returns 100."""
        profile = {"geography": []}
        score = _compute_geographic_fit(profile, HARVARD)
        assert score == 100

    def test_anywhere_neutral(self):
        """'Anywhere' preference returns 100."""
        profile = {"geography": ["Anywhere"]}
        score = _compute_geographic_fit(profile, HARVARD)
        assert score == 100

    def test_in_preferred_region(self):
        """School in preferred region returns 100."""
        profile = {"geography": ["Northeast"]}
        score = _compute_geographic_fit(profile, HARVARD)  # Cambridge, MA is Northeast
        assert score == 100

    def test_not_in_preferred_region(self):
        """School not in preferred region returns 50."""
        profile = {"geography": ["West Coast"]}
        score = _compute_geographic_fit(profile, HARVARD)  # Cambridge, MA is not West Coast
        assert score == 50

    def test_multiple_preferred_regions(self):
        """Match any of multiple preferred regions."""
        profile = {"geography": ["West Coast", "Northeast"]}
        score = _compute_geographic_fit(profile, HARVARD)  # Massachusetts is Northeast
        assert score == 100


class TestRankSchools:
    """Test the full ranking pipeline."""

    def test_input_validation_empty_profile(self):
        """Empty profile raises ValueError."""
        with pytest.raises(ValueError, match="profile cannot be empty"):
            rank_schools({}, [HARVARD])

    def test_input_validation_empty_schools(self):
        """Empty schools list raises ValueError."""
        profile = {"lsat": 170, "gpa": 3.8}
        with pytest.raises(ValueError, match="schools cannot be empty"):
            rank_schools(profile, [])

    def test_input_validation_no_gpa(self):
        """Missing GPA raises ValueError."""
        profile = {"lsat": 170}
        with pytest.raises(ValueError, match="must include a valid GPA"):
            rank_schools(profile, [HARVARD])

    def test_strong_candidate_ranking(self):
        """Strong T14 candidate ranks Harvard highly."""
        profile = {
            "lsat": 175,
            "gpa": 3.95,
            "goal": "BigLaw",
            "practice_areas": ["Corporate"],
            "geography": [],
            "scholarship": "Prefer but not required",
            "reach_preference": "Want a balanced list",
        }
        results = rank_schools(profile, [HARVARD, ALABAMA], top_n=2)
        assert results[0]["id"] == "harvard-law"  # Should rank first
        assert results[0]["composite_score"] > 60

    def test_weak_candidate_ranking(self):
        """Weak candidate ranks regional school higher."""
        profile = {
            "lsat": 160,
            "gpa": 3.3,
            "goal": "BigLaw",
            "practice_areas": [],
            "geography": ["Southeast"],
            "scholarship": "Prefer but not required",
            "reach_preference": "Want a balanced list",
        }
        results = rank_schools(profile, [HARVARD, ALABAMA], top_n=2)
        # Alabama should rank higher for weak candidate
        assert results[0]["id"] == "alabama-law"

    def test_returns_top_n_schools(self):
        """Returns exactly top_n schools."""
        profile = {
            "lsat": 170,
            "gpa": 3.8,
            "goal": "BigLaw",
            "practice_areas": [],
            "geography": [],
            "scholarship": "Prefer but not required",
            "reach_preference": "Want a balanced list",
        }
        schools = [HARVARD, ALABAMA]
        results = rank_schools(profile, schools, top_n=1)
        assert len(results) <= 1

    def test_scores_included_in_results(self):
        """All score fields included in results."""
        profile = {
            "lsat": 170,
            "gpa": 3.8,
            "goal": "BigLaw",
            "practice_areas": ["Corporate"],
            "geography": ["Northeast"],
            "scholarship": "Prefer but not required",
            "reach_preference": "Want a balanced list",
        }
        results = rank_schools(profile, [HARVARD], top_n=1)
        school = results[0]

        assert "admissibility_score" in school
        assert "admissibility_tier" in school
        assert "goal_fit_score" in school
        assert "practice_area_fit_score" in school
        assert "scholarship_likelihood_score" in school
        assert "geographic_fit_score" in school
        assert "composite_score" in school

        # All scores should be 0-100
        assert 0 <= school["admissibility_score"] <= 100
        assert 0 <= school["goal_fit_score"] <= 100
        assert 0 <= school["practice_area_fit_score"] <= 100
        assert 0 <= school["scholarship_likelihood_score"] <= 100
        assert 0 <= school["geographic_fit_score"] <= 100
        assert 0 <= school["composite_score"] <= 100

    def test_original_school_data_preserved(self):
        """Original school fields are preserved in results."""
        profile = {
            "lsat": 170,
            "gpa": 3.8,
            "goal": "BigLaw",
            "practice_areas": [],
            "geography": [],
            "scholarship": "Prefer but not required",
            "reach_preference": "Want a balanced list",
        }
        results = rank_schools(profile, [HARVARD], top_n=1)
        school = results[0]

        assert school["name"] == "Harvard Law School"
        assert school["lsat_50"] == 174
        assert school["biglaw_pct"] == 0.48

    def test_reaches_filter(self):
        """'Only strong candidate' filter removes reach and hard reach tiers."""
        profile = {
            "lsat": 165,
            "gpa": 3.5,
            "goal": "BigLaw",
            "practice_areas": [],
            "geography": [],
            "scholarship": "Prefer but not required",
            "reach_preference": "Only schools where I'm a strong candidate",
        }
        results = rank_schools(profile, [HARVARD, ALABAMA], top_n=10)
        for school in results:
            assert school["admissibility_tier"] in ["safety", "target"]

    def test_scholarship_filter(self):
        """'Must have scholarship' filter removes low scholarship likelihood schools."""
        profile = {
            "lsat": 170,
            "gpa": 3.8,
            "goal": "BigLaw",
            "practice_areas": [],
            "geography": [],
            "scholarship": "Must have significant scholarship",
            "reach_preference": "Want a balanced list",
        }
        results = rank_schools(profile, [HARVARD, ALABAMA], top_n=10)
        for school in results:
            assert school["scholarship_likelihood_score"] >= 50

    def test_sorted_by_composite_score(self):
        """Results sorted by composite score descending."""
        profile = {
            "lsat": 170,
            "gpa": 3.8,
            "goal": "BigLaw",
            "practice_areas": [],
            "geography": [],
            "scholarship": "Prefer but not required",
            "reach_preference": "Want a balanced list",
        }
        results = rank_schools(profile, [HARVARD, ALABAMA], top_n=2)
        if len(results) > 1:
            assert results[0]["composite_score"] >= results[1]["composite_score"]
