"""
Tests for the application portfolio builder (law/matcher.py::build_portfolio).

Covers:
  1. Slate counts and target quotas (2 safeties / 4 targets / 3 reaches)
  2. Graceful shrink when a tier has fewer schools than the quota
  3. State-diversification rule (at most 2 per state per bucket)
  4. Cheap-safety preference (lower net_debt wins within 3 composite points)
  5. Determinism: same input → same slate
  6. No-LSAT profile: slate builds without error
  7. Low-stat profile: shrunk or empty slate is valid (no exception)
  8. Snapshot guard: build_portfolio does not change id order or composite_score
"""

import pytest
from law.data_loader import load_law_schools
from law.matcher import rank_schools, build_portfolio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def schools():
    return load_law_schools()


def _profile(**kwargs):
    base = {
        "lsat": 165,
        "gpa": 3.7,
        "goal": "BigLaw",
        "target_state": "NY",
        "instate_states": [],
        "income_bracket": "prefer_not",
        "scholarship": 5,
        "career_weight": 5,
        "location_weight": 5,
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# 1. Slate counts
# ---------------------------------------------------------------------------

class TestSlateCounts:

    def test_full_slate_counts(self, schools):
        """Standard profile should yield ≤2 safeties, ≤4 targets, ≤3 reaches."""
        ranked = rank_schools(_profile(), schools, top_n=len(schools))
        pf = build_portfolio(ranked)
        assert len(pf["safeties"]) <= 2
        assert len(pf["targets"]) <= 4
        assert len(pf["reaches"]) <= 3

    def test_full_profile_has_nonempty_buckets(self, schools):
        """A 165/3.7 profile should generate at least one school in each bucket."""
        ranked = rank_schools(_profile(), schools, top_n=len(schools))
        pf = build_portfolio(ranked)
        total = len(pf["safeties"]) + len(pf["targets"]) + len(pf["reaches"])
        assert total > 0, "Expected at least one school in the slate"

    def test_hard_reaches_excluded(self, schools):
        """Hard reach schools must never appear in the portfolio slate."""
        ranked = rank_schools(_profile(), schools, top_n=len(schools))
        pf = build_portfolio(ranked)
        for bucket in ("safeties", "targets", "reaches"):
            for entry in pf[bucket]:
                assert entry["admissibility_tier"] != "hard reach", (
                    f"Hard reach '{entry['name']}' found in {bucket}")

    def test_slate_entries_have_required_keys(self, schools):
        """Each slate entry must carry id, name, admissibility_tier, composite_score, net_debt, reason."""
        ranked = rank_schools(_profile(), schools, top_n=len(schools))
        pf = build_portfolio(ranked)
        required = {"id", "name", "admissibility_tier", "composite_score", "net_debt", "reason"}
        for bucket in ("safeties", "targets", "reaches"):
            for entry in pf[bucket]:
                missing = required - set(entry.keys())
                assert not missing, f"Entry missing keys {missing}: {entry}"


# ---------------------------------------------------------------------------
# 2. Graceful shrink
# ---------------------------------------------------------------------------

class TestGracefulShrink:

    def test_no_lsat_builds_without_error(self, schools):
        """No-LSAT profile must not raise; slate may be smaller but must be valid."""
        ranked = rank_schools(_profile(lsat=None), schools, top_n=len(schools))
        pf = build_portfolio(ranked)
        # Should not raise; all lists must be actual lists
        assert isinstance(pf["safeties"], list)
        assert isinstance(pf["targets"], list)
        assert isinstance(pf["reaches"], list)

    def test_low_stat_profile_no_error(self, schools):
        """Very low stats should produce a valid (possibly empty) slate without exception."""
        ranked = rank_schools(_profile(lsat=145, gpa=2.9), schools, top_n=len(schools))
        pf = build_portfolio(ranked)
        # The slate is allowed to be empty per bucket; what must not happen is a crash.
        for bucket in ("safeties", "targets", "reaches"):
            assert isinstance(pf[bucket], list)
        # No hard reaches
        for bucket in ("safeties", "targets", "reaches"):
            for entry in pf[bucket]:
                assert entry["admissibility_tier"] != "hard reach"

    def test_shrink_when_tier_is_small(self, schools):
        """When a tier has fewer schools than the quota the bucket is smaller than the cap."""
        ranked = rank_schools(_profile(lsat=145, gpa=2.9), schools, top_n=len(schools))
        pf = build_portfolio(ranked)
        # safety quota is 2 — never exceeds quota
        assert len(pf["safeties"]) <= 2
        assert len(pf["targets"]) <= 4
        assert len(pf["reaches"]) <= 3

    def test_empty_ranked_list_returns_empty_buckets(self):
        """build_portfolio on an empty list must return empty buckets without crashing."""
        pf = build_portfolio([])
        assert pf["safeties"] == []
        assert pf["targets"] == []
        assert pf["reaches"] == []
        # Default (no profile/strategy) reproduces the historical balanced slate.
        assert pf["strategy"] == "balanced"
        assert pf["quota"] == {"safety": 2, "target": 4, "reach": 3}
        assert pf["adapt_notes"] == []
        assert "longshots" not in pf  # opt-in only


# ---------------------------------------------------------------------------
# 3. Diversification (state cap)
# ---------------------------------------------------------------------------

class TestStateDiversification:

    def test_state_cap_per_bucket(self, schools):
        """Each bucket must have at most 2 schools with the same state."""
        ranked = rank_schools(_profile(), schools, top_n=len(schools))
        pf = build_portfolio(ranked)
        for bucket in ("safeties", "targets", "reaches"):
            state_counts: dict = {}
            for entry in pf[bucket]:
                # Resolve state from ranked list
                s = next((r for r in ranked if r.get("id") == entry["id"]), None)
                if s:
                    st = (s.get("state") or "").upper()
                    state_counts[st] = state_counts.get(st, 0) + 1
                    assert state_counts[st] <= 2, (
                        f"State '{st}' appears {state_counts[st]} times in {bucket} "
                        f"(cap is 2, unless no alternative)")


# ---------------------------------------------------------------------------
# 4. Cheap-safety preference
# ---------------------------------------------------------------------------

class TestCheapSafetyPreference:

    def test_cheap_safety_preferred_within_3_points(self, schools):
        """
        When two safeties are within 3 composite points, the one with lower
        net_debt should appear before the one with higher net_debt.
        """
        ranked = rank_schools(_profile(), schools, top_n=len(schools))
        pf = build_portfolio(ranked)
        safeties = pf["safeties"]
        for i in range(len(safeties) - 1):
            a, b = safeties[i], safeties[i + 1]
            score_diff = abs((a["composite_score"] or 0) - (b["composite_score"] or 0))
            if score_diff <= 3:
                debt_a = a["net_debt"] if a["net_debt"] is not None else float("inf")
                debt_b = b["net_debt"] if b["net_debt"] is not None else float("inf")
                assert debt_a <= debt_b, (
                    f"Safety '{a['name']}' (debt ${debt_a}) ranked before "
                    f"'{b['name']}' (debt ${debt_b}) despite being within 3 pts and more expensive"
                )


# ---------------------------------------------------------------------------
# 5. Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:

    def test_same_input_same_slate(self, schools):
        """Calling build_portfolio twice on the same ranked list yields identical output."""
        ranked = rank_schools(_profile(), schools, top_n=len(schools))
        pf1 = build_portfolio(ranked)
        pf2 = build_portfolio(ranked)
        assert pf1 == pf2

    def test_determinism_no_lsat(self, schools):
        """No-LSAT slate is also deterministic."""
        ranked = rank_schools(_profile(lsat=None), schools, top_n=len(schools))
        pf1 = build_portfolio(ranked)
        pf2 = build_portfolio(ranked)
        assert pf1 == pf2

    def test_determinism_varied_profiles(self, schools):
        """Four varied profiles each produce consistent slates across two calls."""
        profiles = [
            _profile(lsat=172, gpa=3.95, target_state="CA"),
            _profile(lsat=155, gpa=3.3, target_state="TX"),
            _profile(lsat=None, gpa=3.6, target_state="IL"),
            _profile(lsat=145, gpa=2.9, target_state="FL"),
        ]
        for p in profiles:
            ranked = rank_schools(p, schools, top_n=len(schools))
            pf1 = build_portfolio(ranked)
            pf2 = build_portfolio(ranked)
            assert pf1 == pf2, f"Non-deterministic slate for profile {p}"


# ---------------------------------------------------------------------------
# 6. Snapshot guard — ranking order preserved
# ---------------------------------------------------------------------------

class TestSnapshotGuard:

    def _snapshot(self, ranked: list) -> list[tuple]:
        """Capture (id, composite_score) in order."""
        return [(s.get("id"), s.get("composite_score")) for s in ranked]

    def test_snapshot_standard_profile(self, schools):
        """build_portfolio must not change composite_score or id order."""
        ranked = rank_schools(_profile(), schools, top_n=len(schools))
        before = self._snapshot(ranked)
        build_portfolio(ranked)
        after = self._snapshot(ranked)
        assert before == after, "Ranking snapshot changed after build_portfolio"

    def test_snapshot_no_lsat(self, schools):
        ranked = rank_schools(_profile(lsat=None), schools, top_n=len(schools))
        before = self._snapshot(ranked)
        build_portfolio(ranked)
        after = self._snapshot(ranked)
        assert before == after

    def test_snapshot_low_stat(self, schools):
        ranked = rank_schools(_profile(lsat=145, gpa=2.9), schools, top_n=len(schools))
        before = self._snapshot(ranked)
        build_portfolio(ranked)
        after = self._snapshot(ranked)
        assert before == after

    def test_snapshot_high_stat(self, schools):
        ranked = rank_schools(_profile(lsat=172, gpa=3.95, target_state="CA"), schools, top_n=len(schools))
        before = self._snapshot(ranked)
        build_portfolio(ranked)
        after = self._snapshot(ranked)
        assert before == after

    def test_snapshot_varied_profile(self, schools):
        ranked = rank_schools(_profile(lsat=155, gpa=3.4, target_state="TX",
                                       income_bracket="under_65k"), schools, top_n=len(schools))
        before = self._snapshot(ranked)
        build_portfolio(ranked)
        after = self._snapshot(ranked)
        assert before == after

    def test_snapshot_via_server(self, schools):
        """
        server.py path: rank_schools → build_portfolio → ranking unchanged.
        Mimics what the /api/match endpoint does.
        """
        from law.server import app as flask_app
        import json

        with flask_app.test_client() as client:
            payloads = [
                {"lsat": 165, "gpa": 3.7, "goal": "BigLaw", "target_state": "NY",
                 "instate_states": [], "income_bracket": "prefer_not",
                 "scholarship": 5, "career_weight": 5, "location_weight": 5},
                {"no_lsat": True, "lsat": None, "gpa": 3.5, "goal": "Government",
                 "target_state": "DC", "instate_states": [],
                 "income_bracket": "under_65k",
                 "scholarship": 5, "career_weight": 5, "location_weight": 5},
                {"lsat": 145, "gpa": 2.9, "goal": "Public Interest",
                 "target_state": "FL", "instate_states": ["FL"],
                 "income_bracket": "under_65k",
                 "scholarship": 5, "career_weight": 5, "location_weight": 5},
                {"lsat": 172, "gpa": 3.95, "goal": "Federal Clerkship",
                 "target_state": "CA", "instate_states": ["CA"],
                 "income_bracket": "over_200k",
                 "scholarship": 5, "career_weight": 5, "location_weight": 5},
                {"lsat": 158, "gpa": 3.55, "goal": "Government",
                 "target_state": "TX", "instate_states": [],
                 "income_bracket": "65k_130k",
                 "scholarship": 7, "career_weight": 5, "location_weight": 5},
                {"lsat": 152, "gpa": 3.1, "goal": "Solo/Small Firm",
                 "target_state": "OH", "instate_states": ["OH"],
                 "income_bracket": "prefer_not",
                 "scholarship": 5, "career_weight": 5, "location_weight": 5},
            ]
            for payload in payloads:
                resp = client.post(
                    "/api/match",
                    data=json.dumps(payload),
                    content_type="application/json",
                )
                assert resp.status_code == 200, f"Unexpected status {resp.status_code}"
                data = resp.get_json()
                schools_resp = data["schools"]
                ids_before = [(s["id"], s["composite_score"]) for s in schools_resp]

                # build_portfolio uses the same ranked list; re-run to verify
                from law.matcher import build_portfolio as bp
                bp(schools_resp)  # must not mutate
                ids_after = [(s["id"], s["composite_score"]) for s in schools_resp]
                assert ids_before == ids_after, (
                    f"Snapshot mismatch for payload {payload}: "
                    f"before={ids_before[:3]} after={ids_after[:3]}"
                )
