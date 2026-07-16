"""Tests for anonymous usage tracking (law/analytics.py + server endpoints).

The contract under test: only allowlisted interaction events are counted, labels
are bounded, unknown input is silently dropped, and no endpoint errors the
client. There is intentionally no code path that records profile data.
"""

import pytest

from law import analytics
from law.server import app


@pytest.fixture(autouse=True)
def _reset_counters():
    analytics.reset()
    yield
    analytics.reset()


@pytest.fixture
def client():
    return app.test_client()


# --- analytics.record -------------------------------------------------------

class TestRecord:
    def test_allowlisted_event_is_counted(self):
        assert analytics.record("match_run") is True
        assert analytics.snapshot()["events"]["match_run"] == 1

    def test_unknown_event_is_dropped(self):
        assert analytics.record("steal_profile") is False
        assert "steal_profile" not in analytics.snapshot()["events"]

    def test_non_string_name_is_dropped(self):
        assert analytics.record({"lsat": 175}) is False
        assert analytics.record(None) is False
        assert analytics.snapshot()["events"] == {}

    def test_valid_label_increments_base_and_sublabel(self):
        analytics.record("apply_strategy_changed", "safe")
        events = analytics.snapshot()["events"]
        assert events["apply_strategy_changed"] == 1
        assert events["apply_strategy_changed:safe"] == 1

    def test_invalid_label_counts_base_only(self):
        # A label not in the bounded set is ignored (no PII can leak via labels).
        analytics.record("apply_strategy_changed", "lsat=175,gpa=4.0")
        events = analytics.snapshot()["events"]
        assert events["apply_strategy_changed"] == 1
        assert all(":" not in k for k in events)

    def test_label_ignored_for_events_without_label_set(self):
        analytics.record("match_run", "anything")
        events = analytics.snapshot()["events"]
        assert events == {"match_run": 1}

    def test_counts_accumulate(self):
        for _ in range(3):
            analytics.record("whatif_used")
        assert analytics.snapshot()["events"]["whatif_used"] == 3


# --- /api/event -------------------------------------------------------------

class TestEventEndpoint:
    def test_event_returns_204_and_counts(self, client):
        r = client.post("/api/event", json={"name": "school_opened"})
        assert r.status_code == 204
        assert analytics.snapshot()["events"]["school_opened"] == 1

    def test_unknown_event_still_204_but_uncounted(self, client):
        r = client.post("/api/event", json={"name": "exfiltrate"})
        assert r.status_code == 204
        assert analytics.snapshot()["events"] == {}

    def test_event_with_label(self, client):
        client.post("/api/event", json={"name": "view_changed", "label": "table"})
        events = analytics.snapshot()["events"]
        assert events["view_changed:table"] == 1

    def test_malformed_body_does_not_error(self, client):
        r = client.post("/api/event", data="not json",
                        content_type="application/json")
        assert r.status_code == 204

    def test_extra_payload_keys_are_ignored(self, client):
        # Even if a client posts profile fields, only name/label are read.
        client.post("/api/event", json={"name": "match_run", "lsat": 175, "gpa": 4.0})
        assert analytics.snapshot()["events"] == {"match_run": 1}


# --- /api/stats and /stats --------------------------------------------------

class TestStats:
    def test_stats_json_shape(self, client):
        analytics.record("match_run")
        r = client.get("/api/stats")
        assert r.status_code == 200
        body = r.get_json()
        assert body["events"]["match_run"] == 1
        assert "uptime_seconds" in body

    def test_stats_page_renders_html(self, client):
        analytics.record("match_run")
        r = client.get("/stats")
        assert r.status_code == 200
        assert r.mimetype == "text/html"
        assert b"match_run" in r.data

    def test_stats_page_empty_state(self, client):
        r = client.get("/stats")
        assert r.status_code == 200
        assert b"No events recorded yet" in r.data
