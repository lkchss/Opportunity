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
    # No-LSAT path: GPA-only scoring with capped tier
    if lsat is None:
        if gpa >= school["gpa_75"]:
            gpa_only_score = 65
            no_lsat_tier = "target"
        elif gpa >= school["gpa_50"]:
            gpa_only_score = 50
            no_lsat_tier = "target"
        elif gpa >= school["gpa_25"]:
            gpa_only_score = 35
            no_lsat_tier = "reach"
        else:
            gpa_only_score = 15
            no_lsat_tier = "hard reach"
        return gpa_only_score, no_lsat_tier

    # LSAT scoring (percentile-based, more granular)
    if lsat >= school["lsat_75"]:
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
    elif lsat < school["lsat_25"] - 10:
        # Statistical impossibility: 10+ points below 25th
        lsat_score = 0
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

    # Determine tier (both LSAT and GPA matter — schools protect both medians)
    lsat_at_75 = lsat >= school["lsat_75"]
    lsat_at_50 = lsat >= school["lsat_50"]
    lsat_at_25 = lsat >= school["lsat_25"]
    gpa_at_75 = gpa >= school["gpa_75"]
    gpa_at_50 = gpa >= school["gpa_50"]
    gpa_at_25 = gpa >= school["gpa_25"]

    # Safety requires strong on both axes — protects GPA median
    if lsat_at_75 and gpa_at_50:
        tier = "safety"
    elif lsat_at_50 and gpa_at_50:
        tier = "target"
    elif (lsat_at_50 and gpa_at_25) or (lsat_at_25 and gpa_at_50):
        tier = "target"
    elif lsat_at_25 and gpa_at_25:
        tier = "reach"
    elif lsat_at_75 or gpa_at_75:
        # Extreme splitter: one axis elite, other below 25th → reach
        tier = "reach"
    elif lsat_at_50 or gpa_at_50:
        tier = "reach"
    else:
        tier = "hard reach"

    return composite, tier


_LRAP_MULTIPLIERS = {
    "excellent": 1.25,
    "strong": 1.10,
    "moderate": 1.00,
    "weak": 0.80,
}


def _compute_goal_fit_scalars(schools: list[dict]) -> dict:
    """Precompute max employment percentages across schools for normalization."""
    return {
        "biglaw_max": max((s.get("biglaw_pct", 0) for s in schools), default=1) or 1,
        "clerkship_max": max((s.get("federal_clerkship_pct", 0) for s in schools), default=1) or 1,
        "pi_max": max((s.get("public_interest_pct", 0) for s in schools), default=1) or 1,
        "gov_max": max((s.get("government_pct", 0) for s in schools), default=1) or 1,
    }


def _compute_goal_fit_score(profile: dict, school: dict, scalars: Optional[dict] = None) -> float:
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
    scalars = scalars or {}

    # Normalize against top-performing school for each outcome (percentile-style)
    biglaw_max = scalars.get("biglaw_max", 1) or 1
    clerkship_max = scalars.get("clerkship_max", 1) or 1
    pi_max = scalars.get("pi_max", 1) or 1
    gov_max = scalars.get("gov_max", 1) or 1

    biglaw_norm = (school.get("biglaw_pct", 0) / biglaw_max) * 100
    clerkship_norm = (school.get("federal_clerkship_pct", 0) / clerkship_max) * 100
    pi_norm = (school.get("public_interest_pct", 0) / pi_max) * 100
    gov_norm = (school.get("government_pct", 0) / gov_max) * 100

    # LRAP multiplier for careers needing loan forgiveness
    lrap = school.get("lrap_quality", "moderate").lower()
    lrap_mult = _LRAP_MULTIPLIERS.get(lrap, 1.0)

    if "biglaw" in goal:
        return min(biglaw_norm, 100)
    elif "clerkship" in goal:
        return min(clerkship_norm, 100)
    elif "interest" in goal:  # public interest — LRAP critical
        return min(pi_norm * lrap_mult, 100)
    elif "government" in goal:  # government — LRAP relevant (PSLF)
        return min(gov_norm * lrap_mult, 100)
    elif "academia" in goal:
        # Academia requires elite placement: clerkships 60%, biglaw 40%
        return min(clerkship_norm * 0.6 + biglaw_norm * 0.4, 100)
    elif "in-house" in goal or "inhouse" in goal or "in house" in goal:
        return min(biglaw_norm * 0.8, 100)
    elif "solo" in goal or "small firm" in goal:
        # Regional/small firm: inverse of biglaw, modest baseline
        biglaw_pct = school.get("biglaw_pct", 0)
        return max(70 - (biglaw_pct * 70), 0)
    else:  # Unsure: balanced average of normalized outcomes
        return (biglaw_norm + clerkship_norm + pi_norm + gov_norm) / 4


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

    # Splitter: high LSAT, low GPA → merit aid IF GPA doesn't tank school's median
    # Schools won't pay to hurt their own GPA median (USNWR impact)
    gpa_below_25 = school["gpa_25"] - gpa
    if lsat_vs_75 > 5 and gpa_vs_25 < 0.5 and gpa_below_25 <= 0.3:
        # Classic splitter, GPA within range
        splitter_boost = 85
    elif lsat_vs_75 > 5 and gpa_below_25 > 0.3:
        # Catastrophic GPA: drags median too far, minimal $ offered
        splitter_boost = 35
    elif gpa - school["gpa_75"] > 0.5 and lsat < school["lsat_50"]:
        # Reverse splitter: high GPA, low LSAT
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


def _apply_tier_adjustment(tier: str, reach_slider: float) -> float:
    """
    Apply tier-based adjustment based on reach preference slider.

    reach_slider: 0 = love reaches (boost reaches), 10 = only safe (crush reaches).
    Direction matters — prior version was inverted.

    Args:
        tier: Admissibility tier (safety, target, reach, hard reach)
        reach_slider: Slider value 0-10

    Returns:
        Multiplier to apply to composite score
    """
    # Normalized slider position: -1 (love reaches) to +1 (only safe)
    pos = (reach_slider - 5) / 5.0  # -1..+1

    tier_multipliers = {
        # Safety boost when user wants safety
        "safety": 1.0 + max(pos, 0) * 0.15,         # 1.0 → 1.15
        "target": 1.0,
        # Reach: boost when love reaches, crush when only safe
        "reach": 1.20 - (reach_slider / 10) * 0.80,      # 1.20 → 0.40
        # Hard reach: boost smaller, crush harder
        "hard reach": 0.90 - (reach_slider / 10) * 0.80, # 0.90 → 0.10
    }
    return tier_multipliers.get(tier, 1.0)


def _apply_adjustments(schools_with_scores: list[dict], profile: dict) -> list[dict]:
    """
    Apply user preference adjustments to scores (no hard filtering).

    Adjustments:
    - Reach preference (0-10 slider): Penalize/boost reach schools based on preference
    - Scholarship (0-10 slider): Adjust scholarship score weight in composite

    Args:
        schools_with_scores: List of school dicts with computed scores
        profile: User profile dict with reach_preference and scholarship (0-10 sliders)

    Returns:
        List of schools with adjusted composite scores
    """
    reach_slider = profile.get("reach_preference", 5)  # Default 5 = balanced
    scholarship_slider = profile.get("scholarship", 5)  # Default 5 = moderate

    adjusted = []
    for school in schools_with_scores:
        school_copy = school.copy()

        # Apply tier-based adjustment for reach preference
        tier = school_copy.get("admissibility_tier", "target")
        tier_multiplier = _apply_tier_adjustment(tier, reach_slider)

        # Recalculate composite with reach adjustment and scholarship weight
        admissibility = school_copy.get("admissibility_score", 0)
        goal_fit = school_copy.get("goal_fit_score", 0)
        school_quality = school_copy.get("school_quality_score", 0)
        practice_area = school_copy.get("practice_area_fit_score", 0)
        scholarship = school_copy.get("scholarship_likelihood_score", 0)
        geographic = school_copy.get("geographic_fit_score", 0)

        # Scholarship weight: 0-10 slider maps to 0.05-0.15 (default 0.10)
        scholarship_weight = 0.05 + (scholarship_slider / 100)

        # Rebalanced base weights: quality bumped 10→20 to protect elite schools
        # admissibility 28 + goal 22 + quality 20 + practice 10 + geo 10 = 0.90
        base_weight = 0.28 + 0.22 + 0.20 + 0.10 + 0.10
        remaining_weight = 1.0 - scholarship_weight
        scaling_factor = remaining_weight / base_weight

        adjusted_composite = (
            admissibility * 0.28 * scaling_factor
            + goal_fit * 0.22 * scaling_factor
            + school_quality * 0.20 * scaling_factor
            + practice_area * 0.10 * scaling_factor
            + scholarship * scholarship_weight
            + geographic * 0.10 * scaling_factor
        ) * tier_multiplier

        school_copy["composite_score"] = round(adjusted_composite, 1)
        adjusted.append(school_copy)

    return adjusted


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

    # Precompute goal-fit scalars for percentile-style normalization
    scalars = _compute_goal_fit_scalars(schools)

    # Score each school
    scored_schools = []
    for school in schools:
        # Compute component scores
        admissibility_score, tier = _compute_admissibility_score(lsat, gpa, school)
        goal_fit_score = _compute_goal_fit_score(profile, school, scalars)
        practice_area_score = _compute_practice_area_fit(profile, school)
        scholarship_score = _compute_scholarship_likelihood(profile, school, lsat, gpa)
        geographic_score = _compute_geographic_fit(profile, school)
        school_quality_score = _compute_school_quality_score(school)

        # Composite (base weights — overwritten by _apply_adjustments)
        composite_score = (
            admissibility_score * 0.28
            + goal_fit_score * 0.22
            + school_quality_score * 0.20
            + practice_area_score * 0.10
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

    # Apply user preference adjustments
    adjusted_schools = _apply_adjustments(scored_schools, profile)

    # Sort by composite score descending
    adjusted_schools.sort(key=lambda s: s["composite_score"], reverse=True)

    # Return top N
    return adjusted_schools[:top_n]
