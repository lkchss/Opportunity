"""
Law school matching and ranking algorithm.

Deterministic, explainable scoring based on:
- Admissibility (LSAT/GPA fit)
- Goal fit (employment outcomes alignment)
- Practice area fit (interest overlap)
- Scholarship likelihood
- Geographic preference
"""

import math
from typing import Optional


def _sigmoid(x: float, midpoint: float = 0, scale: float = 1) -> float:
    """
    Sigmoid function for smooth scoring curves.

    Args:
        x: Input value
        midpoint: Center of curve (default 0)
        scale: Steepness of curve (default 1)

    Returns:
        Value between 0 and 1
    """
    try:
        return 1 / (1 + math.exp(-scale * (x - midpoint)))
    except OverflowError:
        return 1.0 if x > midpoint else 0.0


def _compute_admissibility_score(
    lsat: Optional[int],
    gpa: float,
    school: dict,
) -> tuple[float, str]:
    """
    Compute admissibility score and tier based on LSAT/GPA vs. school medians.

    LSAT is weighted 70% (law schools care more about LSAT for rankings).
    GPA is weighted 30%.

    Percentile-based scoring:
    - Above 75th percentile → 85-100
    - At median (50th) → 60-75
    - At 25th percentile → 40-55
    - Below 25th → 0-40

    Tier assignment (LSAT-weighted):
    - Safety: LSAT >= 75th OR (LSAT >= 50th AND GPA >= 75th)
    - Target: LSAT >= 50th OR (LSAT >= 25th AND GPA >= 50th)
    - Reach: LSAT >= 25th
    - Hard Reach: LSAT < 25th

    Args:
        lsat: User's LSAT score (or None if not taken)
        gpa: User's GPA
        school: School data dict with lsat_25/50/75, gpa_25/50/75

    Returns:
        (admissibility_score, tier_label) tuple
    """
    # LSAT scoring (percentile-based, more granular)
    if lsat is None:
        lsat_score = 30  # Conservative estimate
    elif lsat >= school["lsat_75"]:
        # Above 75th: map to 85-100 based on how far above
        overage = (lsat - school["lsat_75"]) / max(school["lsat_75"] - school["lsat_50"], 1)
        lsat_score = min(85 + overage * 15, 100)
    elif lsat >= school["lsat_50"]:
        # Between 50th and 75th: map to 60-85
        progress = (lsat - school["lsat_50"]) / max(school["lsat_75"] - school["lsat_50"], 1)
        lsat_score = 60 + progress * 25
    elif lsat >= school["lsat_25"]:
        # Between 25th and 50th: map to 40-60
        progress = (lsat - school["lsat_25"]) / max(school["lsat_50"] - school["lsat_25"], 1)
        lsat_score = 40 + progress * 20
    else:
        # Below 25th: map to 0-40
        if lsat < 120:
            lsat_score = 0
        else:
            deficit = (school["lsat_25"] - lsat) / max(school["lsat_25"] - 120, 1)
            lsat_score = max(40 - deficit * 40, 0)

    # GPA scoring (similar approach)
    if gpa >= school["gpa_75"]:
        overage = (gpa - school["gpa_75"]) / max(school["gpa_75"] - school["gpa_50"], 0.01)
        gpa_score = min(85 + overage * 15, 100)
    elif gpa >= school["gpa_50"]:
        progress = (gpa - school["gpa_50"]) / max(school["gpa_75"] - school["gpa_50"], 0.01)
        gpa_score = 60 + progress * 25
    elif gpa >= school["gpa_25"]:
        progress = (gpa - school["gpa_25"]) / max(school["gpa_50"] - school["gpa_25"], 0.01)
        gpa_score = 40 + progress * 20
    else:
        deficit = (school["gpa_25"] - gpa) / max(school["gpa_25"] - 2.0, 0.01)
        gpa_score = max(40 - deficit * 40, 0)

    # Weighted composite: LSAT 70%, GPA 30%
    composite = lsat_score * 0.70 + gpa_score * 0.30

    # Determine tier (LSAT-weighted logic)
    lsat_at_75 = lsat is not None and lsat >= school["lsat_75"]
    lsat_at_50 = lsat is not None and lsat >= school["lsat_50"]
    lsat_at_25 = lsat is not None and lsat >= school["lsat_25"]
    gpa_at_75 = gpa >= school["gpa_75"]
    gpa_at_50 = gpa >= school["gpa_50"]

    if lsat_at_75 or (lsat_at_50 and gpa_at_75):
        tier = "safety"
    elif lsat_at_50 or (lsat_at_25 and gpa_at_50):
        tier = "target"
    elif lsat_at_25:
        tier = "reach"
    else:
        tier = "hard reach"

    return composite, tier


def _compute_goal_fit_score(profile: dict, school: dict) -> float:
    """
    Compute goal fit score based on primary career goal.

    Maps user's primary goal to relevant employment outcome percentages:
    - BigLaw → biglaw_pct
    - Federal Clerkship → federal_clerkship_pct
    - Public Interest → public_interest_pct
    - Government → government_pct
    - Academia → composite of clerkship_pct + biglaw_pct (proxies for prestige/placement)
    - In-house → biglaw_pct * 0.8 (BigLaw is common path to in-house)
    - Solo/Small Firm → inverse of biglaw_pct (regional schools often better for this)
    - Unsure → balanced average of all outcomes

    Args:
        profile: User profile dict with 'goal' field
        school: School data dict with employment outcome percentages

    Returns:
        Score 0-100
    """
    goal = profile.get("goal", "Unsure").lower()

    if "biglaw" in goal:
        return school.get("biglaw_pct", 0) * 100
    elif "clerkship" in goal:
        return school.get("federal_clerkship_pct", 0) * 100
    elif "interest" in goal:  # public interest
        return school.get("public_interest_pct", 0) * 100
    elif "government" in goal:
        return school.get("government_pct", 0) * 100
    elif "academia" in goal:
        # Academia requires elite placement: weight clerkships + biglaw as proxies
        clerkship_score = school.get("federal_clerkship_pct", 0) * 100
        biglaw_score = school.get("biglaw_pct", 0) * 100
        # Clerkships are stronger signal for academia, weight 60/40
        return clerkship_score * 0.6 + biglaw_score * 0.4
    elif "in-house" in goal or "inhouse" in goal or "in house" in goal:
        # In-house often recruited from BigLaw, so use biglaw_pct as proxy
        return school.get("biglaw_pct", 0) * 100 * 0.8
    elif "solo" in goal or "small firm" in goal:
        # Solo/small firm practice: regional schools often better
        # Use inverse of biglaw_pct as rough proxy (not perfect, but reasonable)
        biglaw_pct = school.get("biglaw_pct", 0)
        # Map 0% biglaw → 70%, 50% biglaw → 35%, 100% biglaw → 0%
        return max(70 - (biglaw_pct * 70), 0)
    else:  # Unsure or other: balanced average
        outcomes = [
            school.get("biglaw_pct", 0),
            school.get("federal_clerkship_pct", 0),
            school.get("public_interest_pct", 0),
            school.get("government_pct", 0),
        ]
        return (sum(outcomes) / len(outcomes)) * 100


def _compute_practice_area_fit(profile: dict, school: dict) -> float:
    """
    Compute practice area fit based on overlap between user interests and school strengths.

    Calculates: (# matching areas / # user interests) * 100
    Returns 100 if user has no stated interests (neutral).

    Args:
        profile: User profile dict with 'practice_areas' field (list)
        school: School data dict with 'practice_area_strengths' field (list)

    Returns:
        Score 0-100
    """
    user_areas = [area.lower() for area in profile.get("practice_areas", [])]
    school_areas = [area.lower() for area in school.get("practice_area_strengths", [])]

    if not user_areas:
        return 100  # Neutral if no preferences stated

    matches = sum(1 for area in user_areas if area in school_areas)
    return (matches / len(user_areas)) * 100


def _compute_scholarship_likelihood(profile: dict, school: dict, lsat: Optional[int], gpa: float) -> float:
    """
    Compute scholarship likelihood based on profile fit and school generosity.

    Logic:
    - Splitter (high LSAT, low GPA): high merit aid likelihood (75+ threshold)
    - Reverse splitter (high GPA, low LSAT): moderate merit aid likelihood
    - Otherwise: based on school's scholarship_pct and percentile fit
    - Consider median_scholarship as indicator of school's generosity

    Args:
        profile: User profile dict
        school: School data dict with scholarship_pct, median_scholarship, LSAT/GPA percentiles
        lsat: User's LSAT score (or None)
        gpa: User's GPA

    Returns:
        Score 0-100
    """
    if lsat is None:
        lsat = 160  # Default conservative estimate

    # Percentile calculation (rough)
    lsat_vs_75 = lsat - school["lsat_75"]  # Positive = above 75th
    gpa_vs_25 = gpa - school["gpa_25"]  # Positive = above 25th

    # Splitter: high LSAT, low GPA → schools offer merit aid for LSAT boost
    if lsat_vs_75 > 5 and gpa_vs_25 < 0.5:
        splitter_boost = 85
    # Reverse splitter: high GPA, low LSAT → more modest boost
    elif gpa - school["gpa_75"] > 0.5 and lsat < school["lsat_50"]:
        splitter_boost = 60
    else:
        splitter_boost = 50

    # Base on school's scholarship percentage and median
    school_generosity = school.get("scholarship_pct", 0.75) * 100
    median_scholarship_bonus = min(school.get("median_scholarship", 20000) / 50000, 1.0) * 10

    # Percentile fit bonus
    lsat_percentile = min(max((lsat - school["lsat_25"]) / (school["lsat_75"] - school["lsat_25"]) * 100, 0), 100)
    gpa_percentile = min(max((gpa - school["gpa_25"]) / (school["gpa_75"] - school["gpa_25"]) * 100, 0), 100)
    percentile_fit = (lsat_percentile + gpa_percentile) / 2 * 0.3

    scholarship_score = (splitter_boost * 0.4 + school_generosity * 0.3 + percentile_fit + median_scholarship_bonus)
    return min(scholarship_score, 100)


def _compute_school_quality_score(school: dict) -> float:
    """
    Compute school quality/prestige score based on objective metrics.

    Uses three indicators:
    - Median LSAT (higher is better) - 50% weight
    - Bar pass rate (higher is better) - 30% weight
    - Selectivity via acceptance rate (lower is better) - 20% weight

    This prevents low-tier schools from ranking above elite schools
    just because a candidate is overqualified.

    Args:
        school: School data dict

    Returns:
        Score 0-100
    """
    # LSAT median score (map 140-175 to 0-100)
    lsat_median = school.get("lsat_50", 150)
    lsat_score = min(max((lsat_median - 140) / (175 - 140) * 100, 0), 100)

    # Bar pass rate score (already 0-1, convert to 0-100)
    bar_pass_score = school.get("bar_pass_rate_first_time", 0.75) * 100

    # Selectivity score (lower acceptance rate is better)
    # Map 0.05 (5%) → 100, 0.50 (50%) → 0
    acceptance_rate = school.get("acceptance_rate", 0.30)
    selectivity_score = max(100 - (acceptance_rate * 200), 0)

    # Weighted composite
    quality_score = (
        lsat_score * 0.50
        + bar_pass_score * 0.30
        + selectivity_score * 0.20
    )

    return min(quality_score, 100)


def _compute_geographic_fit(profile: dict, school: dict) -> float:
    """
    Compute geographic fit score.

    Returns 100 if user has no geographic preferences (flexible).
    Returns 100 if school is in a preferred region.
    Returns 50 if school is outside preferences but not explicitly excluded.

    Args:
        profile: User profile dict with 'geography' field (list of regions)
        school: School data dict with 'location' field (city, state)

    Returns:
        Score 0-100
    """
    user_regions = [r.lower() for r in profile.get("geography", [])]

    if not user_regions or "Anywhere" in profile.get("geography", []):
        return 100  # Flexible

    location = school.get("location", "").lower()
    school_state = location.split(",")[-1].strip().lower() if "," in location else ""

    # Map regions to states
    region_map = {
        "northeast": ["ma", "ct", "ny", "nj", "pa", "vt", "nh", "me", "ri"],
        "southeast": ["nc", "sc", "va", "ga", "fl", "al", "tn", "tx"],
        "midwest": ["oh", "il", "mi", "in", "wi", "mn", "ia", "mo"],
        "southwest": ["tx", "az", "nm"],
        "west coast": ["ca", "wa", "or"],
    }

    matched_region = False
    for region in user_regions:
        states = region_map.get(region, [])
        if school_state in states:
            matched_region = True
            break

    return 100 if matched_region else 50


def _apply_filters(schools_with_scores: list[dict], profile: dict) -> list[dict]:
    """
    Apply user preference filters to remove schools that don't meet criteria.

    Filters:
    - Reach preference: "Only schools where I'm a strong candidate" → remove reaches
    - Scholarship: "Must have significant scholarship" → remove low scholarship likelihood

    Args:
        schools_with_scores: List of school dicts with computed scores
        profile: User profile dict with reach preference and scholarship importance

    Returns:
        Filtered list of schools
    """
    filtered = schools_with_scores

    # Reach filter
    reach_pref = profile.get("reach_preference", "Want a balanced list")
    if "Only schools where I'm a strong candidate" in reach_pref:
        # Remove reach and hard reach tiers
        filtered = [s for s in filtered if s["admissibility_tier"] in ["safety", "target"]]

    # Scholarship filter
    scholarship_pref = profile.get("scholarship", "Prefer but not required")
    if "Must have significant scholarship" in scholarship_pref:
        # Remove schools with low scholarship likelihood
        filtered = [s for s in filtered if s["scholarship_likelihood_score"] >= 50]

    return filtered


def rank_schools(
    profile: dict,
    schools: list[dict],
    top_n: int = 20,
) -> list[dict]:
    """
    Rank law schools based on user profile and return top N matches.

    Scoring logic:

    1. **Admissibility (30%)**: LSAT/GPA fit using percentile-based scoring
       - Compares user stats to school medians and percentiles
       - LSAT weighted 70%, GPA weighted 30%
       - Assigns tier: safety, target, reach, hard reach

    2. **Goal Fit (25%)**: Employment outcome alignment
       - Matches primary career goal to relevant outcome percentage
       - E.g., BigLaw goal → weighted by school's biglaw_pct
       - Academia goal → composite of clerkship + biglaw (prestige proxies)

    3. **School Quality (10%)**: Prestige/selectivity indicator
       - Based on median LSAT, bar pass rate, and acceptance rate
       - Prevents low-tier schools from ranking above elite schools

    4. **Practice Area Fit (15%)**: Interest-strength overlap
       - Counts matching practice areas between user interests and school strengths

    5. **Scholarship Likelihood (10%)**: Merit aid probability
       - Splitters (high LSAT, low GPA) score highly
       - Based on school's scholarship percentage and median

    6. **Geographic Fit (10%)**: Location preference alignment
       - 100 if in preferred region, 50 if flexible, 0 if excluded

    **Composite Score**: Weighted average of above (weights: 30/25/10/15/10/10)

    **Filtering**:
    - Respects "Only strong candidates" preference (removes reaches)
    - Respects "Must have scholarship" preference

    Args:
        profile: User profile dict with:
            - lsat (int or None)
            - gpa (float)
            - goal (str)
            - practice_areas (list[str])
            - geography (list[str])
            - reach_preference (str)
            - scholarship (str)
        schools: List of school dicts (from data_loader)
        top_n: Number of top schools to return (default 20)

    Returns:
        List of top N schools sorted by composite score (desc), each with:
            - All original school fields
            - admissibility_score (0-100)
            - admissibility_tier (safety/target/reach/hard reach)
            - goal_fit_score (0-100)
            - practice_area_fit_score (0-100)
            - scholarship_likelihood_score (0-100)
            - geographic_fit_score (0-100)
            - school_quality_score (0-100)
            - composite_score (0-100)

    Raises:
        ValueError: If profile or schools data is invalid
    """
    # Validate inputs
    if not profile:
        raise ValueError("profile cannot be empty")
    if not schools:
        raise ValueError("schools cannot be empty")
    if top_n < 1:
        raise ValueError("top_n must be at least 1")

    lsat = profile.get("lsat")
    gpa = profile.get("gpa", 0)

    if gpa == 0 or gpa is None:
        raise ValueError("profile must include a valid GPA")

    # Score each school
    scored_schools = []
    for school in schools:
        # Compute component scores
        admissibility_score, tier = _compute_admissibility_score(lsat, gpa, school)
        goal_fit_score = _compute_goal_fit_score(profile, school)
        practice_area_score = _compute_practice_area_fit(profile, school)
        scholarship_score = _compute_scholarship_likelihood(profile, school, lsat, gpa)
        geographic_score = _compute_geographic_fit(profile, school)
        school_quality_score = _compute_school_quality_score(school)

        # Composite score (with school quality factored in)
        composite_score = (
            admissibility_score * 0.30
            + goal_fit_score * 0.25
            + school_quality_score * 0.10
            + practice_area_score * 0.15
            + scholarship_score * 0.10
            + geographic_score * 0.10
        )

        # Augment school with scores
        school_with_scores = school.copy()
        school_with_scores["admissibility_score"] = round(admissibility_score, 1)
        school_with_scores["admissibility_tier"] = tier
        school_with_scores["goal_fit_score"] = round(goal_fit_score, 1)
        school_with_scores["practice_area_fit_score"] = round(practice_area_score, 1)
        school_with_scores["scholarship_likelihood_score"] = round(scholarship_score, 1)
        school_with_scores["geographic_fit_score"] = round(geographic_score, 1)
        school_with_scores["school_quality_score"] = round(school_quality_score, 1)
        school_with_scores["composite_score"] = round(composite_score, 1)

        scored_schools.append(school_with_scores)

    # Apply user preference filters
    filtered_schools = _apply_filters(scored_schools, profile)

    # Sort by composite score descending
    filtered_schools.sort(key=lambda s: s["composite_score"], reverse=True)

    # Return top N
    return filtered_schools[:top_n]
