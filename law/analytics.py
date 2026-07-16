"""In-process, anonymous usage counters for the Law School Matcher.

No personal data is ever recorded. Only a fixed allowlist of UI-interaction
event names (and, for a few of them, a bounded set of labels) is accepted; an
unknown name is silently dropped. There is deliberately no code path that reads
a profile field — LSAT/GPA/income/state never reach this module.

Counters live in memory and reset on restart. Because gunicorn may run more than
one worker, the in-memory snapshot reflects a single worker; the durable,
aggregate record is the structured JSON line emitted to stdout per event
(captured by the host's log stream, e.g. Render logs).
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import time
from collections import Counter
from typing import Optional

logger = logging.getLogger("usage")
# Emit one structured line per event to stdout regardless of host logging config
# (this stream is the durable, cross-worker record). Self-contained so it works
# the same under gunicorn on Render and under the Flask dev server.
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("usage %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

# Allowlisted interaction events. Anything not in this set is rejected outright —
# this is the guard that keeps profile/PII fields from ever being recorded.
ALLOWED_EVENTS: frozenset[str] = frozenset({
    "match_run",                # a profile was submitted and matched
    "view_changed",             # results sub-tab switched
    "whatif_used",              # LSAT what-if stepper bumped
    "pure_fit_toggled",         # "ignore admissibility"
    "weights_opened",           # score-weights panel opened
    "weights_changed",          # a weight slider moved
    "apply_plan_opened",        # Apply-plan tab viewed
    "apply_strategy_changed",   # safe/balanced/aggressive toggle
    "apply_longshots_toggled",  # include long shots
    "school_opened",            # a school detail page opened
    "compare_opened",           # compare view opened
    "export_csv",               # CSV download
    "share_copied",             # share link copied
    "print_results",            # print
    "rankings_opened",          # rankings/browse view
    "methodology_opened",       # "how it works"
    "report_opened",            # report a bug / request a feature
    "school_site_clicked",      # outbound official-site link
})

# Per-event bounded label sets. Events absent here accept no label. Labels are
# fixed UI states (never free text), so they cannot carry user data.
ALLOWED_LABELS: dict[str, frozenset[str]] = {
    "view_changed":            frozenset({"guided", "table", "transfers", "portfolio"}),
    "apply_strategy_changed":  frozenset({"safe", "balanced", "aggressive"}),
    "apply_longshots_toggled": frozenset({"on", "off"}),
    "pure_fit_toggled":        frozenset({"on", "off"}),
}

_lock = threading.Lock()
_counts: "Counter[str]" = Counter()
_started = time.time()


def record(name: object, label: object = None) -> bool:
    """Validate and count one interaction event.

    Returns True if the event was recorded. Unknown event names (or labels not
    in the bounded set) are ignored so a malformed or hostile client cannot
    inflate arbitrary keys or smuggle data through this path. The base event
    name is always counted; a valid label additionally increments ``name:label``.
    """
    if not isinstance(name, str) or name not in ALLOWED_EVENTS:
        return False

    safe_label: Optional[str] = None
    allowed = ALLOWED_LABELS.get(name)
    if allowed and isinstance(label, str) and label in allowed:
        safe_label = label

    with _lock:
        _counts[name] += 1
        if safe_label is not None:
            _counts[f"{name}:{safe_label}"] += 1

    logger.info(json.dumps({"evt": name, "label": safe_label}))
    return True


def snapshot() -> dict:
    """Current counters plus uptime, for the stats view."""
    with _lock:
        counts = dict(_counts)
    return {
        "since_epoch": round(_started, 1),
        "uptime_seconds": round(time.time() - _started, 1),
        "events": dict(sorted(counts.items())),
    }


def reset() -> None:
    """Clear all counters (used by tests; not exposed over HTTP)."""
    global _started
    with _lock:
        _counts.clear()
        _started = time.time()
