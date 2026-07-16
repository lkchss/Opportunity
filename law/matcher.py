"""
Law school matching algorithm — v3.

Produces six independent, transparent scores per school:
  1. Admissibility  — LSAT/GPA fit vs school percentiles → tier label
  2. Prestige       — USNWR rank-based institutional standing
  3. Career Fit     — employment outcome alignment with target career
  4. Location Fit   — placement strength in user's target state
  5. Scholarship    — merit likelihood + need-based aid signal
  6. Financial      — net debt vs expected starting salary

All scores are 0–100. Composite rank = weighted average of the six.
"""

import math
from typing import Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sigmoid(x: float, midpoint: float = 0, scale: float = 1) -> float:
    try:
        return 1 / (1 + math.exp(-scale * (x - midpoint)))
    except OverflowError:
        return 1.0 if x > midpoint else 0.0


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# 1. Admissibility
# ---------------------------------------------------------------------------

# Tiers, best → worst, with the 0-100 score band each maps to. The returned
# score is placed WITHIN its tier's band so the number can never contradict the
# tier label (a "reach" is always 38-60, a "safety" always 82-100, etc.).
_TIER_RANK = ["hard reach", "reach", "target", "safety"]
_TIER_BANDS = {
    "hard reach": (0.0, 38.0),
    "reach":      (38.0, 60.0),
    "target":     (60.0, 82.0),
    "safety":     (82.0, 100.0),
}

# Absolute-selectivity ceiling: even maxed-out stats are not a "safety" at a
# school that rejects the overwhelming majority of applicants (holistic review +
# yield protection). Acceptance rate caps the BEST tier a school can be assigned,
# independent of how far above the medians the applicant sits.
_ACCEPT_CEILING = [
    (0.05, "reach"),    # < 5% admit (Yale/Stanford tier): best case a reach
    (0.12, "target"),   # < 12% admit (lower T14): best case a target
]


def _percentile_score(value, p25, p50, p75, floor=120):
    """Map a value to 0-100 by where it sits across a school's 25/50/75 band."""
    if value >= p75:
        overage = (value - p75) / max(p75 - p50, 1)
        return min(85 + overage * 15, 100)
    elif value >= p50:
        progress = (value - p50) / max(p75 - p50, 1)
        return 60 + progress * 25
    elif value >= p25:
        progress = (value - p25) / max(p50 - p25, 1)
        return 40 + progress * 20
    elif value < p25 - 10:
        return 0.0
    else:
        deficit = (p25 - value) / max(p25 - floor, 1)
        return max(40 - deficit * 40, 0)


def _selectivity_ceiling(school: dict) -> str:
    """Best tier this school can be assigned, given its acceptance rate."""
    rate = school.get("acceptance_rate")
    if rate is None:
        return "safety"
    for threshold, ceiling in _ACCEPT_CEILING:
        if rate < threshold:
            return ceiling
    return "safety"


def _cap_tier(tier: str, ceiling: str) -> str:
    """Demote a tier to the ceiling when the ceiling is the stricter (worse) one."""
    if _TIER_RANK.index(tier) > _TIER_RANK.index(ceiling):
        return ceiling
    return tier


def _score_in_band(tier: str, fit: float) -> float:
    """Place a 0-100 fit value inside the tier's score band (keeps score↔tier consistent)."""
    lo, hi = _TIER_BANDS[tier]
    return lo + _clamp(fit) / 100 * (hi - lo)


def _compute_admissibility(
    lsat: Optional[int],
    gpa: float,
    school: dict,
) -> tuple[float, str]:
    """
    Score LSAT/GPA fit against school percentiles and assign a tier.

    Returns (score 0-100, tier label). The score is mapped into the tier's band
    so it never contradicts the label, and the tier is capped by the school's
    absolute selectivity (acceptance rate) so ultra-selective schools are never
    a "safety" regardless of stats.
    """
    ceiling = _selectivity_ceiling(school)

    # No-LSAT path: GPA-only, capped at target (an LSAT-less file is never a safety).
    if lsat is None:
        if gpa >= school["gpa_50"]:
            tier = "target"
        elif gpa >= school["gpa_25"]:
            tier = "reach"
        else:
            tier = "hard reach"
        tier = _cap_tier(tier, ceiling)
        gpa_fit = _percentile_score(
            gpa, school["gpa_25"], school["gpa_50"], school["gpa_75"], floor=2.0)
        # 0.85 factor (applied to the fit, BEFORE banding) keeps a GPA-only file
        # below the same GPA backed by a real LSAT while staying inside the tier band.
        return _clamp(_score_in_band(tier, gpa_fit * 0.85)), tier

    lsat_score = _percentile_score(
        lsat, school["lsat_25"], school["lsat_50"], school["lsat_75"])
    gpa_score = _percentile_score(
        gpa, school["gpa_25"], school["gpa_50"], school["gpa_75"], floor=2.0)
    fit = lsat_score * 0.70 + gpa_score * 0.30

    # Tier: both axes must be healthy (schools protect both medians).
    at_75_lsat = lsat >= school["lsat_75"]
    at_50_lsat = lsat >= school["lsat_50"]
    at_25_lsat = lsat >= school["lsat_25"]
    at_75_gpa  = gpa  >= school["gpa_75"]
    at_50_gpa  = gpa  >= school["gpa_50"]
    at_25_gpa  = gpa  >= school["gpa_25"]

    if at_75_lsat and at_50_gpa:
        tier = "safety"
    elif at_50_lsat and at_50_gpa:
        tier = "target"
    elif (at_50_lsat and at_25_gpa) or (at_25_lsat and at_50_gpa):
        tier = "target"
    elif at_25_lsat and at_25_gpa:
        tier = "reach"
    elif at_75_lsat or at_75_gpa:
        tier = "reach"   # extreme splitter — one axis strong, other weak
    elif at_50_lsat or at_50_gpa:
        tier = "reach"
    else:
        tier = "hard reach"

    tier = _cap_tier(tier, ceiling)
    return _clamp(_score_in_band(tier, fit)), tier


# ---------------------------------------------------------------------------
# 2. Career Fit
# ---------------------------------------------------------------------------

_GOAL_FIELDS = {
    "biglaw":        ["biglaw_pct"],
    "federal clerkship": ["federal_clerkship_pct"],
    "government":    ["government_pct"],
    "public interest": ["public_interest_pct"],
    "solo/small firm": ["solo_small_firm_pct"],
    "in-house":      ["biglaw_pct"],        # BigLaw is primary pipeline
    "academia":      ["federal_clerkship_pct", "biglaw_pct"],  # prestige proxies
    "unsure":        ["biglaw_pct", "federal_clerkship_pct", "government_pct",
                      "public_interest_pct", "solo_small_firm_pct"],
}

_GOAL_WEIGHTS = {
    "academia": [0.60, 0.40],
    "unsure":   [0.25, 0.20, 0.20, 0.20, 0.15],
}

_LRAP_MULTIPLIERS = {"excellent": 1.25, "strong": 1.10, "moderate": 1.00, "weak": 0.85}


def _precompute_career_scalars(schools: list[dict]) -> dict:
    """Max value across all schools per outcome field, for normalization."""
    fields = {
        "biglaw_pct", "federal_clerkship_pct", "government_pct",
        "public_interest_pct", "solo_small_firm_pct",
    }
    return {
        f: max((s.get(f, 0) for s in schools), default=1) or 1
        for f in fields
    }


def _career_goals(profile: dict) -> list[tuple[str, float]]:
    """
    Normalize a profile's career preference into [(goal, weight), ...].

    Prefers the weighted multi-goal form (``goals_weighted``: a list of
    {"goal", "weight"}); falls back to the legacy single ``goal``. Drops blank
    goals and non-positive weights.
    """
    weighted = profile.get("goals_weighted")
    goals: list[tuple[str, float]] = []
    if weighted:
        for g in weighted:
            name = (g.get("goal") or "").strip()
            try:
                weight = float(g.get("weight", 0))
            except (TypeError, ValueError):
                weight = 0.0
            if name and weight > 0:
                goals.append((name, weight))
    if not goals:
        goals.append((profile.get("goal") or "Unsure", 1.0))
    return goals


def _single_goal_component(goal_str: str, school: dict, scalars: dict) -> float:
    """Goal-specific normalized outcome fit for ONE career goal (0-100)."""
    goal_key = (goal_str or "unsure").lower()
    matched = "unsure"
    for key in _GOAL_FIELDS:
        if key in goal_key:
            matched = key
            break

    fields = _GOAL_FIELDS[matched]
    weights = _GOAL_WEIGHTS.get(matched, [1.0])

    normed = []
    for f in fields:
        raw = school.get(f, 0)
        mx = scalars.get(f, 1) or 1
        normed.append(_clamp((raw / mx) * 100))

    if len(normed) == 1:
        score = normed[0]
    else:
        w = weights[:len(normed)]
        total_w = sum(w)
        score = sum(n * (wi / total_w) for n, wi in zip(normed, w))

    # LRAP multiplier for loan-sensitive careers
    if matched in ("public interest", "government"):
        lrap = school.get("lrap_quality", "moderate").lower()
        score *= _LRAP_MULTIPLIERS.get(lrap, 1.0)

    return score


def _compute_career_fit(profile: dict, school: dict, scalars: dict) -> float:
    """
    Career-outcome fit for the applicant's goal(s). Multiple goals are combined
    as a weight-average of each goal's single-goal fit (e.g. BigLaw/PI = 70/30),
    then adjusted once by goal-independent real-placement and bar-passage signals.
    """
    goals = _career_goals(profile)
    total_w = sum(w for _, w in goals) or 1.0
    score = sum(_single_goal_component(g, school, scalars) * (w / total_w)
                for g, w in goals)

    # Real-outcome quality adjustment (ABA Employment Summary, when available).
    # employed_10mo_pct (FTLT bar-required + JD-advantage / grads) is the
    # gold-standard placement metric; school_funded_pct flags employment-stat
    # gaming (schools hiring their own grads into short-term funded roles) and is
    # netted out. Blend 70% goal-specific fit, 30% real discounted placement.
    employed = school.get("employed_10mo_pct")
    if employed is not None:
        funded = school.get("school_funded_pct") or 0.0
        real_placement = max(employed - funded, 0.0)
        score = score * 0.70 + (real_placement * 100) * 0.30

    # Bar-passage value-add (ABA 2026): a school that beats its state's first-time
    # pass rate adds outcome value beyond the students it admits; one that lags is
    # a risk. bar_pass_vs_state is school-minus-state; nudge career ±10% (capped).
    vs_state = school.get("bar_pass_vs_state")
    if vs_state is not None:
        score *= 1 + max(-0.10, min(0.10, vs_state))

    return _clamp(score)


# ---------------------------------------------------------------------------
# 2. Prestige
# ---------------------------------------------------------------------------

# Reputation is top-heavy, not linear: the T14 cliff is steep, differences
# shrink rapidly past ~rank 20, and the long tail is nearly flat (rank 60 vs 90
# barely registers nationally). Piecewise-linear over documented knots.
_PRESTIGE_KNOTS = [
    (1, 100.0), (5, 92.0), (10, 83.0), (14, 76.0), (20, 62.0),
    (35, 40.0), (60, 26.0), (100, 16.0), (150, 10.0), (196, 7.0),
]
_UNRANKED_PRESTIGE = 5.0

# Regional prestige band: a school's standing among the schools serving the
# applicant's target market. The market's flagship earns real prestige even if
# its national rank is modest, but stays below the national elite.
_REGIONAL_PRESTIGE_MIN = 20.0
_REGIONAL_PRESTIGE_MAX = 75.0


def _national_prestige(rank: Optional[int]) -> float:
    """USNWR rank → 0-100 on the top-heavy curve. Unranked (999) → floor."""
    if rank is None or rank >= 999:
        return _UNRANKED_PRESTIGE
    if rank <= _PRESTIGE_KNOTS[0][0]:
        return _PRESTIGE_KNOTS[0][1]
    for (r0, p0), (r1, p1) in zip(_PRESTIGE_KNOTS, _PRESTIGE_KNOTS[1:]):
        if rank <= r1:
            return p0 + (p1 - p0) * (rank - r0) / (r1 - r0)
    return _PRESTIGE_KNOTS[-1][1]


def _precompute_regional_pools(schools: list[dict]) -> dict[str, list[str]]:
    """
    state → school ids serving that market (located there or listing it as a
    target state), ordered best-to-worst by national rank.
    """
    pools: dict[str, list[tuple[float, str, str]]] = {}
    for s in schools:
        states = {(s.get("state") or "").upper()}
        states.update((t or "").upper() for t in s.get("target_states", []))
        rank = s.get("usnwr_rank_2026") or 999
        for st in states:
            if st:
                pools.setdefault(st, []).append((rank, s.get("name", ""), s.get("id", "")))
    return {st: [sid for _, _, sid in sorted(rows)] for st, rows in pools.items()}


def _compute_prestige(
    school: dict,
    profile: Optional[dict] = None,
    regional_pools: Optional[dict] = None,
) -> float:
    """
    Institutional prestige (0-100): national reputation on a top-heavy curve,
    lifted by regional standing in the applicant's target market(s).

    Regional component: where the school sits among all schools serving each
    target state (banded 20-75 so a market flagship beats its national tail
    score but never outranks the national elite), scaled by how strongly it
    actually serves that market (home state / primary feed > minor feed), and
    weight-averaged across the applicant's markets.
    Final score = max(national, regional).
    """
    nat = _national_prestige(school.get("usnwr_rank_2026"))
    prefs = _location_prefs(profile or {})
    if not prefs or not regional_pools:
        return _clamp(nat)

    reg_acc, w_acc = 0.0, 0.0
    band = _REGIONAL_PRESTIGE_MAX - _REGIONAL_PRESTIGE_MIN
    for state, weight in prefs:
        pool = regional_pools.get(state) or []
        reg = 0.0
        if school.get("id") in pool and len(pool) > 1:
            standing = 1 - pool.index(school["id"]) / (len(pool) - 1)
            serve = _single_state_fit(state, school) / 100.0
            reg = (_REGIONAL_PRESTIGE_MIN + standing * band) * serve
        reg_acc += reg * weight
        w_acc += weight
    regional = reg_acc / w_acc if w_acc else 0.0
    return _clamp(max(nat, regional))


# ---------------------------------------------------------------------------
# 3. Location Fit
# ---------------------------------------------------------------------------

def _single_state_fit(target: str, school: dict) -> float:
    """Placement-strength score for one target state against a school."""
    target = (target or "").strip().upper()
    if not target:
        return 50.0

    school_state   = (school.get("state") or "").upper()
    target_states  = [s.upper() for s in school.get("target_states", [])]

    if not target_states:
        return 20.0

    # Position in the ordered target_states list
    try:
        position = target_states.index(target)
    except ValueError:
        position = -1

    if position == -1:
        base = 15.0  # not listed — possible but unlikely
    elif position == 0:
        base = 100.0
    elif position == 1:
        base = 85.0
    elif position <= 3:
        base = 70.0
    else:
        base = 55.0

    # Physical proximity bonus: school is in the target state
    if school_state == target and position != 0:
        base = min(base + 15.0, 100.0)

    return _clamp(base)


def _location_prefs(profile: dict) -> list[tuple[str, float]]:
    """
    Normalize a profile's location preference into [(state, weight), ...].

    Prefers the weighted multi-state form (``target_states_weighted``: a list of
    {"state", "weight"}); falls back to the legacy single ``target_state``.
    Drops blank states and non-positive weights.
    """
    weighted = profile.get("target_states_weighted")
    prefs: list[tuple[str, float]] = []
    if weighted:
        for p in weighted:
            state = (p.get("state") or "").strip().upper()
            try:
                weight = float(p.get("weight", 0))
            except (TypeError, ValueError):
                weight = 0.0
            if state and weight > 0:
                prefs.append((state, weight))
    if not prefs:
        single = (profile.get("target_state") or "").strip().upper()
        if single:
            prefs.append((single, 1.0))
    return prefs


def _compute_location_fit(profile: dict, school: dict) -> float:
    """
    Score how strongly the school places graduates into the user's target
    state(s). Multiple states are combined as a weight-average of each state's
    single-state fit (e.g. CA/NY = 70/30 → 0.7·fit(CA) + 0.3·fit(NY)).

    Uses the school's target_states list (ordered: first = strongest placement);
    a physical-location bonus applies when the school sits in a preferred state.
    """
    prefs = _location_prefs(profile)
    if not prefs:
        return 50.0  # neutral if no preference stated

    total_w = sum(w for _, w in prefs) or 1.0
    score = sum(_single_state_fit(state, school) * (w / total_w) for state, w in prefs)
    return _clamp(score)


# ---------------------------------------------------------------------------
# 4. Scholarship
# ---------------------------------------------------------------------------

_NEED_FACTORS = {
    "under_65k":   1.00,
    "65k_130k":    0.60,
    "130k_200k":   0.20,
    "over_200k":   0.00,
    "prefer_not":  0.30,
}

_NEED_BOOST_MAX = 15.0   # max points added to scholarship score for high-need


def _grid_generosity(school: dict) -> Optional[float]:
    """Award-size-weighted generosity from the ABA 509 grid (None if absent)."""
    full = school.get("scholarship_full_pct")
    if full is None:
        return None
    htf = school.get("scholarship_half_to_full_pct") or 0.0
    lth = school.get("scholarship_less_than_half_pct") or 0.0
    return full * 1.0 + htf * 0.7 + lth * 0.3


def _precompute_scholarship_scalar(schools: list[dict]) -> float:
    """Max grid generosity across the dataset, for normalizing to 0-100."""
    vals = [g for s in schools if (g := _grid_generosity(s)) is not None]
    return max(vals, default=0.70) or 0.70


def _compute_scholarship(
    profile: dict,
    school: dict,
    lsat: Optional[int],
    gpa: float,
    generosity_max: float = 0.70,
) -> float:
    """
    Combined merit + need-based scholarship likelihood.

    Merit: splitter detection + school generosity.
    Need:  income-bracket signal scales a flat boost across all schools.
    """
    # --- Merit component ---
    # No-LSAT path: GPA-only merit. A placeholder LSAT must never reach the
    # splitter branches — at low-LSAT schools it would fake a high-LSAT splitter
    # and inflate merit (and, downstream, expected aid) for exactly the
    # applicants who haven't tested yet.
    if lsat is None:
        if gpa - school["gpa_75"] > 0.1:
            merit_base = 60.0   # clearly above the 75th — strong merit signal
        elif gpa >= school["gpa_50"]:
            merit_base = 50.0
        else:
            merit_base = 40.0
    else:
        lsat_vs_75  = lsat - school["lsat_75"]
        gpa_vs_75   = gpa  - school["gpa_75"]
        gpa_below_25 = school["gpa_25"] - gpa

        # Splitter: high LSAT, low-ish GPA
        if lsat_vs_75 > 5 and gpa_below_25 <= 0.30:
            merit_base = 85.0
        elif lsat_vs_75 > 5 and gpa_below_25 > 0.30:
            merit_base = 35.0   # GPA drags school median too far
        elif gpa_vs_75 > 0.5 and lsat < school["lsat_50"]:
            merit_base = 60.0   # reverse splitter
        else:
            merit_base = 50.0

    # Generosity: prefer the real ABA 509 award grid (weights award SIZE, not just
    # receipt) — full band counts most, then half-to-full, then <half — normalized
    # against the most generous school so it occupies the full 0-100 range. Fall
    # back to the flat "any grant" rate when grid data is absent.
    grid_g = _grid_generosity(school)
    if grid_g is not None:
        school_generosity = _clamp((grid_g / generosity_max) * 100)
    else:
        school_generosity = school.get("scholarship_pct", 0.75) * 100
    median_scholarship_bonus = min(school.get("median_scholarship", 20000) / 50000, 1.0) * 10

    gpa_pct = _clamp(
        (gpa  - school["gpa_25"])  / max(school["gpa_75"]  - school["gpa_25"],  0.01) * 100
    )
    if lsat is None:
        percentile_fit = gpa_pct * 0.30   # GPA-only: no fake LSAT percentile
    else:
        lsat_pct = _clamp(
            (lsat - school["lsat_25"]) / max(school["lsat_75"] - school["lsat_25"], 1) * 100
        )
        percentile_fit = (lsat_pct + gpa_pct) / 2 * 0.30

    merit_score = (
        merit_base                * 0.40
        + school_generosity       * 0.30
        + percentile_fit
        + median_scholarship_bonus
    )

    # Conditional scholarships (ABA reported) can be revoked after 1L if the
    # student misses a GPA stipulation. Penalize by the school's ACTUAL reduction
    # rate (share of conditional awards historically cut) when known — a school
    # that rarely cuts is low-risk, one that guts a quarter of them is not — and
    # fall back to a flat penalty when the rate is unavailable.
    if school.get("conditional_scholarship"):
        reduction_rate = school.get("conditional_reduction_rate")
        merit_score -= reduction_rate * 40.0 if reduction_rate is not None else 5.0

    # --- Need component ---
    income_bracket = profile.get("income_bracket", "prefer_not")
    need_factor    = _NEED_FACTORS.get(income_bracket, 0.30)
    need_boost     = need_factor * _NEED_BOOST_MAX

    return _clamp(merit_score + need_boost)


# ---------------------------------------------------------------------------
# 5. Financial Reality
# ---------------------------------------------------------------------------

_LIVING_EXPENSE_BASE = 22_000   # annual baseline (NALP estimate), scaled by COL index

_GOAL_USES_PRIVATE_SALARY = {
    "biglaw", "in-house", "academia",
}

_MONTHLY_PAYMENT_FACTOR = 0.01161   # 10-yr repayment at 7% interest

# PSLF / IDR constants
_PSLF_ELIGIBLE_GOALS  = {"public interest", "government"}
_IDR_POVERTY_LINE     = 22_590   # 150% of 2024 federal poverty line (1 person)
_IDR_POVERTY_PER_DEP  = 8_070    # 150% of the +$5,380 per additional household member
_IDR_INCOME_PCT       = 0.10     # PAYE/IBR: 10% of discretionary income
_PSLF_MONTHS          = 120      # 10 years of qualifying payments


def _financial_inputs(profile: dict) -> tuple[float, float, int]:
    """Optional financials (cash toward law school, existing student debt,
    dependents) — all default to 0 so omitting them is a no-op."""
    def _num(key: str) -> float:
        try:
            v = float(profile.get(key) or 0)
        except (TypeError, ValueError):
            return 0.0
        # NaN/Infinity survive float() but poison round() downstream → treat as 0
        return max(v, 0.0) if math.isfinite(v) else 0.0
    return _num("cash_available"), _num("existing_debt"), int(_num("dependents"))

# LRAP monthly reductions by school quality tier (dollars)
_LRAP_MONTHLY_REDUCTION = {
    "excellent": 700,
    "strong":    400,
    "moderate":  150,
    "weak":        0,
}


def _expected_tuition_discount(school: dict, scholarship_score: float) -> Optional[float]:
    """
    Fraction of annual tuition the applicant can expect covered, derived from the
    school's real ABA 509 award grid scaled by the applicant's competitiveness.

    Returns None when grid data is absent (caller falls back to the heuristic).

    avg_award_frac = dollar-weighted average award SIZE among recipients
                     (full≈1.0, half-to-full≈0.75, <half≈0.25 of tuition).
    award_rate     = share of the class receiving any grant, scaled by a
                     competitiveness factor (scholarship_score 50 ≈ neutral).
    discount       = avg_award_frac × min(award_rate × comp, 1.0)   ∈ [0, 1]
    """
    full = school.get("scholarship_full_pct")
    if full is None:
        return None
    htf = school.get("scholarship_half_to_full_pct") or 0.0
    lth = school.get("scholarship_less_than_half_pct") or 0.0
    awarded = full + htf + lth
    if awarded <= 0:
        return 0.0
    avg_award_frac = (full * 1.0 + htf * 0.75 + lth * 0.25) / awarded
    comp = 0.4 + (scholarship_score / 100) * 1.0          # [0.4, 1.4]
    return min(avg_award_frac * min(awarded * comp, 1.0), 1.0)


def _compute_financial(
    profile: dict,
    school: dict,
    scholarship_score: float,
) -> tuple[float, dict]:
    """
    Estimate net debt and score debt-to-income ratio (standard repayment).

    Also computes an optional PSLF/IDR path for Public Interest and Government
    goals — returned in the breakdown dict for display, but does NOT affect the
    score (the score stays on standard repayment so it remains a conservative
    baseline regardless of career commitment length).

    Returns (score 0-100, breakdown dict with raw numbers for display).
    """
    # Determine tuition: resident if user qualifies, else nonresident
    instate_states = [s.upper() for s in profile.get("instate_states", [])]
    school_state   = (school.get("state") or "").upper()
    qualifies_instate = school_state in instate_states

    if qualifies_instate:
        annual_tuition = school.get("annual_tuition_resident", school.get("annual_tuition", 0))
    else:
        annual_tuition = school.get("annual_tuition_nonresident", school.get("annual_tuition", 0))

    tuition_3yr = annual_tuition * 3

    # Living costs: prefer the school's real ABA-reported annual living expense
    # (off-campus budget); fall back to the COL-index heuristic when absent.
    annual_living = school.get("living_expense_annual")
    if annual_living is None:
        col_index = school.get("cost_of_living_index", 100)
        annual_living = _LIVING_EXPENSE_BASE * (col_index / 100)
    living_3yr = annual_living * 3

    gross_cost = tuition_3yr + living_3yr

    # Estimated aid: prefer the school's real award grid (ABA 509) gated by the
    # applicant's competitiveness; fall back to the median-scholarship heuristic
    # when grid data is absent.
    median_scholarship = school.get("median_scholarship", 0)
    discount = _expected_tuition_discount(school, scholarship_score)
    if discount is not None:
        expected_aid = annual_tuition * discount * 3
    elif scholarship_score >= 65:
        expected_aid = median_scholarship * 3
    elif scholarship_score >= 45:
        expected_aid = median_scholarship * 1.5
    else:
        expected_aid = 0.0

    # Optional financials: cash on hand reduces what must be borrowed; existing
    # student debt rides along into the repayment math (it doesn't vary by
    # school, but it changes the monthly payment and DTI the applicant faces).
    cash_available, existing_debt, dependents = _financial_inputs(profile)

    net_debt = max(gross_cost - expected_aid - cash_available, 0)
    total_debt = net_debt + existing_debt

    # Starting salary based on career goal
    goal_key = (profile.get("goal") or "Unsure").lower()
    use_private = any(g in goal_key for g in _GOAL_USES_PRIVATE_SALARY)
    starting_salary = (
        school.get("median_private_sector_salary", 75000) if use_private
        else school.get("median_public_sector_salary", 60000)
    )

    # Primary score: standard 10-yr repayment DTI (conservative baseline).
    # Use the rounded total_debt that gets reported so the displayed DTI exactly
    # equals reported debt / salary (no off-by-a-cent rounding drift).
    # total_debt == net_debt when no existing debt is entered (the default).
    dti            = round(total_debt) / max(starting_salary, 1)
    score          = _clamp(100 - (dti * 25))
    monthly_payment = total_debt * _MONTHLY_PAYMENT_FACTOR

    breakdown = {
        "annual_tuition_effective":  annual_tuition,
        "qualifies_instate":         qualifies_instate,
        "tuition_3yr":               round(tuition_3yr),
        "living_3yr":                round(living_3yr),
        "gross_cost":                round(gross_cost),
        "expected_aid":              round(expected_aid),
        "cash_applied":              round(cash_available),
        "existing_debt":             round(existing_debt),
        "net_debt":                  round(net_debt),
        "total_debt":                round(total_debt),
        "starting_salary":           starting_salary,
        "monthly_payment_estimate":  round(monthly_payment),
        "debt_to_income_ratio":      round(dti, 2),
        "pslf_eligible":             False,
    }

    # PSLF / IDR alternate path — only for PI and Government goals
    matched_goal = "unsure"
    for g in _PSLF_ELIGIBLE_GOALS:
        if g in goal_key:
            matched_goal = g
            break

    if matched_goal != "unsure":
        # IDR monthly payment (PAYE/IBR: 10% of income above 150% poverty line).
        # The poverty line scales with household size, so dependents lower the
        # payment and raise the forgiven amount.
        poverty_line         = _IDR_POVERTY_LINE + dependents * _IDR_POVERTY_PER_DEP
        discretionary_income = max(starting_salary - poverty_line, 0)
        idr_monthly_gross    = round(discretionary_income * _IDR_INCOME_PCT / 12)

        # LRAP reduces your out-of-pocket IDR payment
        lrap_quality     = school.get("lrap_quality", "moderate").lower()
        lrap_reduction   = _LRAP_MONTHLY_REDUCTION.get(lrap_quality, 0)
        idr_monthly_net  = max(idr_monthly_gross - lrap_reduction, 0)

        # Total paid over 10 years, capped at total_debt (can't overpay)
        pslf_total_paid  = min(idr_monthly_net * _PSLF_MONTHS, total_debt)
        pslf_forgiven    = max(round(total_debt - pslf_total_paid), 0)

        breakdown.update({
            "pslf_eligible":       True,
            "idr_monthly_gross":   idr_monthly_gross,
            "lrap_monthly":        lrap_reduction,
            "idr_monthly_net":     idr_monthly_net,
            "pslf_total_paid":     round(pslf_total_paid),
            "pslf_forgiven":       pslf_forgiven,
        })

    return _clamp(score), breakdown


# ---------------------------------------------------------------------------
# Composite + ranking
# ---------------------------------------------------------------------------

# Multipliers applied to composite score by admissibility tier.
# Individual scores stay transparent — only the ranking priority shifts.
_TIER_COMPOSITE_MULTIPLIER = {
    "safety":     1.00,
    "target":     1.00,
    "reach":      0.92,
    "hard reach": 0.80,
}


def _composite_weights(
    career_slider: float,
    location_slider: float,
    scholarship_slider: float,
    cost_sensitivity: float = 0.0,
) -> tuple[float, float, float, float]:
    """
    User-adjustable weights (sliders 0-10 each, financial absorbs the remainder):
      career_w     = 0.25 + (career_slider/10)*0.12     → [0.25, 0.37]
      location_w   = 0.17 + (location_slider/10)*0.10   → [0.17, 0.27]
      scholarship_w = 0.05 + (scholarship_slider/10)*0.10 → [0.05, 0.15]
      financial_w  = 0.80 − career_w − location_w − scholarship_w

    At all defaults (slider=5): career 31%, location 22%, scholarship 10%, financial 17%.
    """
    career_w      = 0.25 + (career_slider      / 10) * 0.12
    location_w    = 0.17 + (location_slider    / 10) * 0.10
    scholarship_w = 0.05 + (scholarship_slider / 10) * 0.10
    financial_w   = 0.80 - career_w - location_w - scholarship_w

    # Financial weight is the *remainder*, so raising the scholarship-importance
    # slider paradoxically shrinks the weight on real net debt — worst exactly for
    # the cost-sensitive applicants who crank that slider. Guarantee financial a
    # need-scaled floor (income bracket + scholarship slider drive cost_sensitivity),
    # refilling the deficit proportionally from the discretionary career/location
    # budget. No-op for cost-insensitive profiles, where the floor sits below the
    # natural financial_w, so non-cost-driven rankings are unchanged.
    financial_floor = 0.10 + cost_sensitivity * 0.12   # [0.10, 0.22]
    if financial_w < financial_floor:
        deficit = financial_floor - financial_w
        pool = career_w + location_w
        if pool > 0:
            career_w   -= deficit * (career_w / pool)
            location_w -= deficit * (location_w / pool)
        financial_w = financial_floor

    return career_w, location_w, scholarship_w, financial_w


# Valid score keys that the user-weight multiplier layer recognises.
_WEIGHT_KEYS = frozenset(
    {"admissibility", "prestige", "career_fit", "location_fit", "scholarship", "financial"}
)


def _parse_user_weights(raw: object) -> Optional[dict]:
    """
    Parse and validate an optional per-score multiplier map sent by the client.

    Accepted shape: {score_key: multiplier, ...} where keys are drawn from
    _WEIGHT_KEYS.  Unknown keys are silently ignored so future fields don't
    break old clients.

    Rules:
      - None / empty dict / missing → returns None (caller uses default weights).
      - Non-finite or negative values are clamped to 0.0 (not rejected), so a
        client that sends 0.0 for a dimension simply removes that dimension from
        the composite rather than crashing.
      - If every recognised key maps to 0.0 after clamping, the call is invalid
        and ValueError is raised (caller should return 400).

    Returns a dict with only the recognised, clamped values, or None.
    """
    if not raw:
        return None
    if not isinstance(raw, dict):
        return None
    out: dict[str, float] = {}
    for k in _WEIGHT_KEYS:
        if k not in raw:
            continue
        try:
            v = float(raw[k])
        except (TypeError, ValueError):
            v = 0.0
        out[k] = max(v, 0.0) if math.isfinite(v) else 0.0
    if not out:
        return None
    if all(v == 0.0 for v in out.values()):
        raise ValueError("All user-supplied weights are zero — at least one must be positive.")
    return out


def _apply_user_weights(
    base_w: dict,
    user_weights: Optional[dict],
) -> dict:
    """
    Apply optional per-score multipliers to a pre-computed weight map, then
    renormalize so the total weight stays at 1.0.

    The cost-sensitivity floor is already baked into base_w before this is
    called, so multiplying financial's weight down can never violate it in a
    way that would surprise the user — the floor was already the minimum, and
    the user is consciously reducing that score's influence.  The result is
    renormalized, not refloor-checked, to keep the interaction transparent.

    If user_weights is None or empty, base_w is returned unchanged (no copy).
    """
    if not user_weights:
        return base_w
    adjusted = {k: v * user_weights.get(k, 1.0) for k, v in base_w.items()}
    total = sum(adjusted.values())
    if total <= 0:
        return base_w  # safety: all multiplied to zero — fall back
    factor = 1.0 / total
    return {k: v * factor for k, v in adjusted.items()}


def _composite(
    scores: dict,
    career_slider: float,
    location_slider: float,
    scholarship_slider: float,
    tier: str,
    cost_sensitivity: float = 0.0,
    user_weights: Optional[dict] = None,
) -> float:
    """
    Weighted average of six scores, scaled by admissibility tier.

    Fixed weights:  admissibility 0.12, prestige 0.08  (total 0.20 fixed)
    Tier multiplier suppresses hard-reach schools in the composite ranking.

    Optional user_weights: per-score multipliers (from _parse_user_weights).
    Applied AFTER the cost-sensitivity floor is resolved, then renormalized so
    the total remains 1.0.  Absent/None → identical to current behavior.
    """
    career_w, location_w, scholarship_w, financial_w = _composite_weights(
        career_slider, location_slider, scholarship_slider, cost_sensitivity)

    base_w = {
        "admissibility": 0.12,
        "prestige":      0.08,
        "career_fit":    career_w,
        "location_fit":  location_w,
        "scholarship":   scholarship_w,
        "financial":     financial_w,
    }
    w = _apply_user_weights(base_w, user_weights)

    raw = (
        scores["admissibility"] * w["admissibility"]
        + scores["prestige"]    * w["prestige"]
        + scores["career_fit"]  * w["career_fit"]
        + scores["location_fit"]* w["location_fit"]
        + scores["scholarship"] * w["scholarship"]
        + scores["financial"]   * w["financial"]
    )
    multiplier = _TIER_COMPOSITE_MULTIPLIER.get(tier, 1.00)
    return _clamp(raw * multiplier)


def _fit_without_admissibility(
    scores: dict,
    career_slider: float,
    location_slider: float,
    scholarship_slider: float,
    cost_sensitivity: float = 0.0,
    user_weights: Optional[dict] = None,
) -> float:
    """
    Composite with admissibility removed: drop the admissibility term AND the
    tier multiplier, renormalize the remaining 0.88 of weight back to 0-100.
    Answers "how well does this school fit me, ignoring whether I'd get in".

    user_weights: same per-score multipliers as _composite; admissibility key
    is ignored here since that score is excluded by definition.
    """
    career_w, location_w, scholarship_w, financial_w = _composite_weights(
        career_slider, location_slider, scholarship_slider, cost_sensitivity)

    base_w = {
        "prestige":     0.08,
        "career_fit":   career_w,
        "location_fit": location_w,
        "scholarship":  scholarship_w,
        "financial":    financial_w,
    }
    # Strip admissibility key from user_weights before applying (not present here)
    uw_no_adm = {k: v for k, v in (user_weights or {}).items() if k != "admissibility"}
    w = _apply_user_weights(base_w, uw_no_adm or None)

    raw = (
        scores["prestige"]      * w["prestige"]
        + scores["career_fit"]  * w["career_fit"]
        + scores["location_fit"]* w["location_fit"]
        + scores["scholarship"] * w["scholarship"]
        + scores["financial"]   * w["financial"]
    )
    # Renormalize back to 0-100: divide by the sum of non-admissibility weights
    total_w = sum(w.values())
    return _clamp(raw / total_w) if total_w > 0 else 0.0


# ---------------------------------------------------------------------------
# Transfer-up planning (for applicants not competitive at their target tier
# who intend to transfer to a higher-ranked school after 1L)
# ---------------------------------------------------------------------------

def compute_scholarship_leverage(
    lsat: Optional[int],
    gpa: float,
    school: dict,
) -> dict:
    """
    Display-only aid-grid insight: is the applicant above both of the school's
    50th-percentile medians, and if so, how does the school's real ABA 509
    scholarship grid break down?

    Returns a dict with:
      above_both_medians (bool)
      pct_full (float|None)   -- fraction (as pct, 0-100) receiving full-tuition aid
      pct_half_plus (float|None) -- fraction receiving half-tuition or more
      note (str)              -- human-readable one-liner for display

    Rules:
    - No-LSAT profile (lsat None): always above_both_medians=False (no LSAT on file
      means the school cannot benchmark the applicant on its primary admissions axis).
    - Grid absent (scholarship_full_pct is None): pct_full / pct_half_plus are None.
    - Does NOT touch any score, tier, or sort key.
    """
    if lsat is None:
        return {
            "above_both_medians": False,
            "pct_full": None,
            "pct_half_plus": None,
            "note": "Submit an LSAT score to see leverage data.",
        }

    above = lsat >= school.get("lsat_50", 0) and gpa >= school.get("gpa_50", 0.0)

    full = school.get("scholarship_full_pct")
    htf  = school.get("scholarship_half_to_full_pct")

    if full is None:
        pct_full      = None
        pct_half_plus = None
    else:
        pct_full      = round(full * 100, 1)
        pct_half_plus = round((full + (htf or 0.0)) * 100, 1)

    if not above:
        return {
            "above_both_medians": False,
            "pct_full": pct_full,
            "pct_half_plus": pct_half_plus,
            "note": "Your numbers are below one or both medians here.",
        }

    # Applicant is above both medians -- build a meaningful note
    if pct_half_plus is not None and pct_half_plus > 0:
        note = (
            f"Your numbers are above both medians -- "
            f"{pct_half_plus}% of students here received half tuition or more "
            f"({pct_full}% received a full ride). "
            "Use this as leverage in negotiations."
        )
    elif pct_half_plus is not None:
        note = (
            "Your numbers are above both medians. "
            "Aid grid shows limited half-or-more scholarships -- ask directly."
        )
    else:
        note = (
            "Your numbers are above both medians -- "
            "no detailed grid available, but your profile is competitive for aid."
        )

    return {
        "above_both_medians": True,
        "pct_full": pct_full,
        "pct_half_plus": pct_half_plus,
        "note": note,
    }


def _transfer_metrics(school: dict) -> dict:
    """
    Per-school transfer mobility from ABA Transfers data, normalized by 1L class
    size. Returns rates rounded to 3 dp; values are None when data is missing.

      transfer_out_rate — share of the 1L class that transferred out (a proxy for
                          "viable launchpad": students here successfully move up).
      transfer_in_rate  — transfers admitted relative to class size (how open the
                          school is to taking transfers).
    """
    class_1l = school.get("class_size_1l")
    t_out = school.get("transfers_out")
    t_in = school.get("transfers_in")
    out_rate = round(t_out / class_1l, 3) if class_1l and t_out is not None else None
    in_rate = round(t_in / class_1l, 3) if class_1l and t_in is not None else None
    return {"transfer_out_rate": out_rate, "transfer_in_rate": in_rate}


def transfer_up_plan(
    profile: dict,
    schools: list[dict],
    top_n: int = 5,
) -> dict:
    """
    Build a two-sided transfer-up plan from the applicant's own match results.

      launchpads — the applicant's best realistic matches (safety/target tier),
                   ranked by composite fit: good places to enroll, excel, and
                   transfer up from.
      targets    — schools that are a reach right now (so, an upgrade after a strong
                   1L) AND that actually admit transfers, gated on transfer intake
                   first and then ordered by how well they fit this applicant.

    Both lists run through the full matcher, so they track the applicant's career,
    location and cost — not a fixed mobility table. Returns
    {"launchpads": [...], "targets": [...]}; empty lists when none qualify.
    """
    if not profile.get("gpa"):
        raise ValueError("profile must include a valid GPA")

    ranked = rank_schools(profile, schools, top_n=len(schools))

    # Launchpads: best realistic admits, by composite fit.
    launch_pool = [s for s in ranked if s["admissibility_tier"] in ("safety", "target")]
    launch_pool.sort(key=lambda s: s["composite_score"], reverse=True)
    launchpads = [
        {
            "id": s.get("id"),
            "name": s.get("name"),
            "usnwr_rank_2026": s.get("usnwr_rank_2026"),
            "admissibility_tier": s.get("admissibility_tier"),
            "composite_score": s.get("composite_score"),
            "transfer_out_rate": s.get("transfer_out_rate"),
        }
        for s in launch_pool[:top_n]
    ]

    # Targets: a reach now (the realistic upgrade) AND the school takes transfers.
    # The "takes transfers" gate comes first; among those, rank mostly by how well
    # the school fits THIS applicant (composite) so location/career/cost drive the
    # list, with transfer-openness as a secondary factor.
    target_pool = [
        s for s in ranked
        if s["admissibility_tier"] == "reach" and s.get("transfers_in")
    ]
    max_in = max((s["transfers_in"] for s in target_pool), default=0) or 1

    def _target_score(school: dict) -> float:
        openness = school["transfers_in"] / max_in * 100
        return school["composite_score"] * 0.70 + openness * 0.30

    target_pool.sort(key=_target_score, reverse=True)
    targets = [
        {
            "id": s.get("id"),
            "name": s.get("name"),
            "usnwr_rank_2026": s.get("usnwr_rank_2026"),
            "transfers_in": s.get("transfers_in"),
            "composite_score": s.get("composite_score"),
            "match_score": round(_target_score(s), 1),
        }
        for s in target_pool[:top_n]
    ]

    return {"launchpads": launchpads, "targets": targets}


_PORTFOLIO_STRATEGIES: dict[str, dict[str, int]] = {
    # safety / target / reach quotas per risk posture. Targets stay the anchor;
    # the knob trades safeties against reaches.
    "safe":       {"safety": 3, "target": 4, "reach": 2},
    "balanced":   {"safety": 2, "target": 4, "reach": 3},
    "aggressive": {"safety": 1, "target": 4, "reach": 4},
}
_HARD_LONGSHOT_QUOTA = 2   # how many hard reaches surface when include_hard is on


def build_portfolio(
    ranked: list[dict],
    profile: Optional[dict] = None,
    strategy: str = "balanced",
    include_hard: bool = False,
) -> dict:
    """
    Build a deterministic application portfolio from the already-ranked school list.

    Selection rules
    ---------------
    Base quotas come from ``strategy`` (safe 3/4/2, balanced 2/4/3, aggressive
    1/4/4); ``balanced`` reproduces the historical 2/4/3 slate exactly. Counts
    shrink gracefully when a tier contains fewer schools than the quota.

    Auto-adaptation: the base quota is nudged from profile signals (e.g. a highly
    cost-sensitive applicant gets one extra safety in place of a reach). Every
    adjustment is recorded in ``adapt_notes`` so the UI can explain it.

    When ``include_hard`` is set, up to two hard-reach "long shots" are returned
    in a separate ``longshots`` bucket (still state-capped); they are excluded by
    default because they are below the school's 25th percentiles.

    Within each bucket the algorithm takes the composite-ranked top of that tier
    subject to two diversification constraints:

    1. State cap: at most 2 schools sharing the same state per bucket, unless no
       alternative exists. When a state would exceed the cap the next-best school
       from a different state is taken in its place (continuing down the ranked list).

    2. Cheap-safety preference: within the safety bucket, when two candidates are
       within 3 composite points of each other, the one with the lower net_debt
       (from financial_breakdown) is preferred.

    Each slate entry carries:
      id, name, admissibility_tier, composite_score, net_debt, reason (one-line,
      built deterministically from real fields).

    The reason line is the strongest of the school's six scores (prestige,
    career_fit, location_fit, scholarship, financial) plus an in-state / cheap
    flag when relevant.

    The function does NOT modify any score, tier, or ranking order.
    Snapshot guard: the caller must verify id+composite order is byte-identical
    before and after calling this function (it reads only, never writes back).

    Returns {"safeties": [...], "targets": [...], "reaches": [...]} — any bucket
    may be an empty list when the tier has no schools at all.
    """
    # Base quotas from the chosen risk posture (defaults to balanced 2/4/3).
    QUOTA: dict[str, int] = dict(
        _PORTFOLIO_STRATEGIES.get(strategy, _PORTFOLIO_STRATEGIES["balanced"]))
    STATE_CAP = 2

    # ── Auto-adaptation: nudge the base quota from profile signals ───────────
    adapt_notes: list[str] = []
    p = profile or {}

    # Highly cost-sensitive applicants carry more debt risk, so widen the safety
    # net by one at the expense of a reach. A safety with merit aid is the
    # cheapest insurance against a bad-money outcome.
    cost_slider = int(p.get("scholarship", 5) or 0)
    low_means = (p.get("income_bracket") == "under_65k"
                 and float(p.get("cash_available") or 0) < 20_000)
    if (cost_slider >= 8 or low_means) and QUOTA["reach"] > 1:
        QUOTA["safety"] += 1
        QUOTA["reach"]  -= 1
        adapt_notes.append(
            "Added a safety in place of a reach — you flagged cost as critical, "
            "and a likely-admit with merit aid is your debt insurance.")

    # No LSAT yet: reach calls are guesswork without a real score.
    if profile is not None and p.get("lsat") in (None, "", 0):
        adapt_notes.append(
            "Add an LSAT score for sharper reach/target calls — this slate is "
            "built from GPA and preferences alone.")

    # Score-name → label used in the reason line
    _SCORE_LABELS: dict[str, str] = {
        "prestige_score":      "strong prestige",
        "career_fit_score":    "strong career fit",
        "location_fit_score":  "strong location fit",
        "scholarship_score":   "strong scholarship odds",
        "financial_score":     "favorable cost",
    }

    def _reason(school: dict) -> str:
        """One deterministic reason line built from real school fields."""
        # Find the strongest non-admissibility score dimension
        best_key = max(
            _SCORE_LABELS.keys(),
            key=lambda k: school.get(k, 0.0),
        )
        reason = _SCORE_LABELS[best_key]

        fb = school.get("financial_breakdown") or {}
        instate = fb.get("qualifies_instate", False)
        net_debt = fb.get("net_debt")

        # Append a cost / location flag when meaningful
        tier = school.get("admissibility_tier", "")
        if instate:
            reason += " · in-state tuition"
        elif tier == "safety" and net_debt is not None and net_debt < 80_000:
            reason += " · low projected debt"

        return f"{school.get('admissibility_tier', 'safety').title()} — {reason}."

    def _pick_bucket(pool: list[dict], quota: int) -> list[dict]:
        """
        Select up to `quota` schools from pool (already ordered best-first by
        composite_score) respecting the state cap.
        """
        chosen: list[dict] = []
        state_counts: dict[str, int] = {}
        for s in pool:
            state = (s.get("state") or "").upper()
            if state_counts.get(state, 0) >= STATE_CAP:
                continue
            chosen.append(s)
            state_counts[state] = state_counts.get(state, 0) + 1
            if len(chosen) >= quota:
                break
        return chosen

    def _apply_cheap_safety_preference(candidates: list[dict]) -> list[dict]:
        """
        Within the safety bucket: when two adjacent candidates are within 3
        composite points of each other, prefer the cheaper one (lower net_debt).
        Uses a single-pass bubble-style swap so the sort stays stable for
        well-separated candidates.
        """
        result = list(candidates)
        for i in range(len(result) - 1):
            a, b = result[i], result[i + 1]
            if abs(a.get("composite_score", 0) - b.get("composite_score", 0)) <= 3:
                debt_a = (a.get("financial_breakdown") or {}).get("net_debt") or float("inf")
                debt_b = (b.get("financial_breakdown") or {}).get("net_debt") or float("inf")
                if debt_b < debt_a:
                    result[i], result[i + 1] = b, a
        return result

    def _slate_entry(school: dict) -> dict:
        fb = school.get("financial_breakdown") or {}
        return {
            "id":                school.get("id"),
            "name":              school.get("name"),
            "admissibility_tier": school.get("admissibility_tier"),
            "composite_score":   school.get("composite_score"),
            "net_debt":          fb.get("net_debt"),
            "reason":            _reason(school),
        }

    # Partition ranked list by tier (preserving composite order)
    by_tier: dict[str, list[dict]] = {"safety": [], "target": [], "reach": [], "hard reach": []}
    for s in ranked:
        t = s.get("admissibility_tier", "")
        if t in by_tier:
            by_tier[t].append(s)

    # Safety bucket: apply cheap preference first, then state-cap filter
    safety_pool = _apply_cheap_safety_preference(by_tier["safety"])
    safeties = _pick_bucket(safety_pool, QUOTA["safety"])

    targets = _pick_bucket(by_tier["target"], QUOTA["target"])
    reaches = _pick_bucket(by_tier["reach"], QUOTA["reach"])

    out = {
        "safeties": [_slate_entry(s) for s in safeties],
        "targets":  [_slate_entry(s) for s in targets],
        "reaches":  [_slate_entry(s) for s in reaches],
        "strategy": strategy if strategy in _PORTFOLIO_STRATEGIES else "balanced",
        "quota":    dict(QUOTA),
        "adapt_notes": adapt_notes,
    }

    # Optional "long shots": a couple of hard reaches, opt-in only.
    if include_hard:
        longshots = _pick_bucket(by_tier["hard reach"], _HARD_LONGSHOT_QUOTA)
        out["longshots"] = [_slate_entry(s) for s in longshots]

    return out


def rank_schools(
    profile: dict,
    schools: list[dict],
    top_n: int = 20,
    user_weights: Optional[dict] = None,
) -> list[dict]:
    """
    Rank law schools by profile fit. Returns top N with all scores attached.

    Profile keys expected:
      lsat (int|None), gpa (float), goal (str),
      target_state (str),           e.g. "TX"
      instate_states (list[str]),   e.g. ["TX"]
      income_bracket (str),         "under_65k"|"65k_130k"|"130k_200k"|"over_200k"|"prefer_not"
      scholarship (int 0-10),       scholarship importance slider
      career_weight (int 0-10),     career fit importance slider
      location_weight (int 0-10),   location fit importance slider

    Optional user_weights: per-score multipliers parsed by _parse_user_weights.
      Keys: admissibility, prestige, career_fit, location_fit, scholarship, financial.
      None (default) → identical to current behavior (no change to results).
      Applied after the cost-sensitivity floor, then renormalized to sum=1.0.

    Each returned school dict has extra keys:
      admissibility_score, admissibility_tier,
      prestige_score,
      career_fit_score, location_fit_score,
      scholarship_score, financial_score,
      financial_breakdown (dict),
      composite_score
    """
    if not profile:
        raise ValueError("profile cannot be empty")
    if not schools:
        raise ValueError("schools cannot be empty")
    if top_n < 1:
        raise ValueError("top_n must be at least 1")

    lsat = profile.get("lsat")
    gpa  = profile.get("gpa")
    if not gpa:
        raise ValueError("profile must include a valid GPA")

    scholarship_slider = profile.get("scholarship", 5)
    career_slider      = profile.get("career_weight", 5)
    location_slider    = profile.get("location_weight", 5)

    # Cost-sensitivity drives the financial-weight floor in _composite: the higher
    # of the applicant's income-based need and their explicit scholarship slider.
    need_factor      = _NEED_FACTORS.get(profile.get("income_bracket", "prefer_not"), 0.30)
    cost_sensitivity = max(need_factor, scholarship_slider / 10)

    scalars = _precompute_career_scalars(schools)
    generosity_max = _precompute_scholarship_scalar(schools)
    regional_pools = _precompute_regional_pools(schools)

    scored = []
    for school in schools:
        admissibility, tier = _compute_admissibility(lsat, gpa, school)
        prestige            = _compute_prestige(school, profile, regional_pools)
        career_fit          = _compute_career_fit(profile, school, scalars)
        location_fit        = _compute_location_fit(profile, school)
        scholarship         = _compute_scholarship(profile, school, lsat, gpa, generosity_max)
        financial, breakdown = _compute_financial(profile, school, scholarship)

        scores = {
            "admissibility": admissibility,
            "prestige":      prestige,
            "career_fit":    career_fit,
            "location_fit":  location_fit,
            "scholarship":   scholarship,
            "financial":     financial,
        }

        entry = school.copy()
        entry["admissibility_score"]   = round(admissibility, 1)
        entry["admissibility_tier"]    = tier
        entry["prestige_score"]        = round(prestige, 1)
        entry["career_fit_score"]      = round(career_fit, 1)
        entry["location_fit_score"]    = round(location_fit, 1)
        entry["scholarship_score"]     = round(scholarship, 1)
        entry["financial_score"]       = round(financial, 1)
        entry["financial_breakdown"]   = breakdown
        entry.update(_transfer_metrics(school))
        # Display-only aid insight — never used in any score or sort key
        entry["scholarship_leverage"]  = compute_scholarship_leverage(lsat, gpa, school)
        entry["composite_score"]       = round(
            _composite(scores, career_slider, location_slider, scholarship_slider,
                       tier, cost_sensitivity, user_weights), 1
        )
        # Admissibility-blind fit — same weights, no admissibility term, no tier
        # multiplier. Surfaced as the "pure fit" view; never drives the ranking.
        entry["fit_no_admissibility_score"] = round(
            _fit_without_admissibility(scores, career_slider, location_slider,
                                       scholarship_slider, cost_sensitivity, user_weights), 1
        )
        scored.append(entry)

    scored.sort(key=lambda s: s["composite_score"], reverse=True)
    return scored[:top_n]
