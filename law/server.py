"""Flask backend for the Law School Matcher web app.

Serves the static frontend in ``law/web`` and exposes a single JSON endpoint
that runs the matching algorithm against a posted profile.
"""

import hmac
import math
import os
from html import escape as html_escape
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

from law import analytics, seo
from law.data_loader import DataValidationError, load_law_schools
from law.matcher import rank_schools, transfer_up_plan, build_portfolio, _parse_user_weights

WEB_DIR = Path(__file__).parent / "web"

# Single shared password (HTTP Basic Auth). Set APP_PASSWORD in the deploy
# environment to gate the whole site; leave it unset for open local dev. The
# browser supplies a username we ignore — only the password is checked.
_APP_PASSWORD = os.environ.get("APP_PASSWORD")

# Radar axis order — must match SCORE_NAMES on the frontend.
_RADAR_KEYS = [
    "admissibility_score",
    "prestige_score",
    "career_fit_score",
    "location_fit_score",
    "scholarship_score",
    "financial_score",
]

app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path="")

try:
    _SCHOOLS = load_law_schools()
    _SCHOOLS_BY_ID = {s["id"]: s for s in _SCHOOLS}
except (FileNotFoundError, DataValidationError) as exc:  # pragma: no cover
    raise SystemExit(f"Failed to load law school data: {exc}")


def _is_public_path(path: str) -> bool:
    """Public, crawlable marketing surface — never behind the site password.

    The SEO landing pages are useless if gated (search engines can't read them),
    so they stay open even when APP_PASSWORD gates the matcher app itself.
    """
    return (
        path == "/law-schools"
        or path.startswith("/law-schools/")
        or path.startswith("/law-schools-in/")
        or path in ("/sitemap.xml", "/robots.txt")
    )


def _base_url() -> str:
    """Absolute site origin for canonical/OG/sitemap URLs.

    Prefers SITE_BASE_URL; otherwise derives from the request, honoring the
    proxy's X-Forwarded-Proto so canonicals are https on Render rather than http.
    """
    env = os.environ.get("SITE_BASE_URL")
    if env:
        return env.rstrip("/")
    proto = request.headers.get("X-Forwarded-Proto", request.scheme)
    return f"{proto}://{request.host}"


@app.before_request
def _require_password() -> Response | None:
    """Gate every route behind a single shared password when one is configured."""
    if not _APP_PASSWORD:
        return None  # no password set — open (local dev)
    if _is_public_path(request.path):
        return None  # marketing pages are always public
    auth = request.authorization
    if auth is not None and auth.password is not None and hmac.compare_digest(
        auth.password, _APP_PASSWORD
    ):
        return None
    return Response(
        "Authentication required.",
        401,
        {"WWW-Authenticate": 'Basic realm="Law School Matcher"'},
    )


# Static asset extensions safe to cache at the edge for a while.
_STATIC_EXT = (".css", ".jsx", ".js", ".svg", ".png", ".ico", ".woff", ".woff2")


@app.after_request
def _headers(resp: Response) -> Response:
    """Baseline security headers everywhere; modest caching for public assets.

    Caching is only applied to the public, idempotent surfaces (SEO pages,
    sitemap/robots, static files) — never to the matcher app shell or the API,
    which must stay fresh and (when gated) private.
    """
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")

    path = request.path
    if request.method == "GET" and resp.status_code == 200 and "Cache-Control" not in resp.headers:
        if _is_public_path(path):
            resp.headers["Cache-Control"] = "public, max-age=3600"
        elif path.endswith(_STATIC_EXT):
            resp.headers["Cache-Control"] = "public, max-age=600"
    return resp


def _build_weighted_states(payload: dict) -> list[dict]:
    """Coerce posted location preferences into [{state, weight}, ...].

    Accepts the multi-state weighted form (``target_states_weighted``); falls
    back to the single ``target_state`` field. Keeps only non-blank states with
    a positive weight.
    """
    raw = payload.get("target_states_weighted")
    prefs: list[dict] = []
    if isinstance(raw, list):
        for item in raw:
            state = str((item or {}).get("state") or "").strip()
            try:
                weight = float((item or {}).get("weight", 0))
            except (TypeError, ValueError):
                weight = 0.0
            if state and weight > 0:
                prefs.append({"state": state, "weight": weight})
    if not prefs:
        single = (payload.get("target_state") or "").strip()
        if single:
            prefs.append({"state": single, "weight": 1.0})
    return prefs


def _build_weighted_goals(payload: dict) -> list[dict]:
    """Coerce posted career preferences into [{goal, weight}, ...].

    Accepts the multi-goal weighted form (``goals_weighted``); falls back to the
    single ``goal`` field. Keeps only non-blank goals with a positive weight.
    """
    raw = payload.get("goals_weighted")
    goals: list[dict] = []
    if isinstance(raw, list):
        for item in raw:
            goal = str((item or {}).get("goal") or "").strip()
            try:
                weight = float((item or {}).get("weight", 0))
            except (TypeError, ValueError):
                weight = 0.0
            if goal and weight > 0:
                goals.append({"goal": goal, "weight": weight})
    if not goals:
        single = (payload.get("goal") or "").strip()
        goals.append({"goal": single or "Unsure", "weight": 1.0})
    return goals


def _build_profile(payload: dict) -> dict:
    """Coerce the posted form payload into the shape rank_schools expects."""
    no_lsat = bool(payload.get("no_lsat"))
    lsat = payload.get("lsat")
    weighted = _build_weighted_states(payload)
    goals = _build_weighted_goals(payload)
    primary_goal = max(goals, key=lambda g: g["weight"])["goal"]
    return {
        "lsat": None if no_lsat or lsat in (None, "") else int(lsat),
        "gpa": float(payload.get("gpa") or 0),
        "goal": primary_goal,                 # top-weighted goal (salary + display + columns)
        "goals_weighted": goals,
        "target_state": (payload.get("target_state") or "").strip(),
        "target_states_weighted": weighted,
        "instate_states": [s for s in (payload.get("instate_states") or []) if str(s).strip()],
        "income_bracket": payload.get("income_bracket") or "prefer_not",
        # Optional financials — blank/absent means 0 (a no-op in the matcher).
        "dependents": int(float(payload.get("dependents") or 0)),
        "cash_available": float(payload.get("cash_available") or 0),
        "existing_debt": float(payload.get("existing_debt") or 0),
        "scholarship": int(payload.get("scholarship", 5)),
        "career_weight": int(payload.get("career_weight", 5)),
        "location_weight": int(payload.get("location_weight", 5)),
        "wants_transfer": bool(payload.get("wants_transfer")),
    }


@app.get("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.get("/api/schools")
def schools():
    """Raw dataset for the rankings/browse view — no profile, no algorithm."""
    return jsonify({"schools": _SCHOOLS})


@app.post("/api/match")
def match():
    payload = request.get_json(silent=True) or {}

    # Coercion (int/float) can raise on malformed input posted directly to the
    # API (the UI guards most of this); turn it into a clean 400, not a 500.
    try:
        profile = _build_profile(payload)
    except (TypeError, ValueError, OverflowError):
        return jsonify({"error": "Invalid profile fields (check LSAT/GPA)."}), 400

    if not (profile["gpa"] > 0) or math.isnan(profile["gpa"]):
        return jsonify({"error": "A valid GPA is required."}), 400

    # Optional per-score weight multipliers from the TweaksPanel.
    # Absent / null / {} → None (exact default behavior, byte-identical output).
    # All-zero → 400.  Unknown keys are silently ignored.
    try:
        user_weights = _parse_user_weights(payload.get("weights"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        ranked = rank_schools(profile, _SCHOOLS, top_n=len(_SCHOOLS),
                              user_weights=user_weights)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    for school in ranked:
        school["radar"] = [round(school[k]) for k in _RADAR_KEYS]

    transfer_plan = transfer_up_plan(profile, _SCHOOLS)

    # Apply-plan controls (optional). Unknown strategy falls back to balanced;
    # absence reproduces the historical 2/4/3 slate.
    strategy = str(payload.get("apply_strategy") or "balanced").lower()
    include_hard = bool(payload.get("include_hard"))
    portfolio = build_portfolio(ranked, profile=profile,
                                strategy=strategy, include_hard=include_hard)

    return jsonify({
        "profile": profile,
        "schools": ranked,
        "transfer_plan": transfer_plan,
        "portfolio": portfolio,
    })


@app.post("/api/event")
def event() -> Response:
    """Record one anonymous interaction event (feature usage only).

    Accepts {"name": <allowlisted>, "label": <optional bounded>}. Anything not on
    the allowlist is dropped by analytics.record. Always answers 204 — it never
    errors the client and never reveals which names are valid.
    """
    payload = request.get_json(silent=True) or {}
    analytics.record(payload.get("name"), payload.get("label"))
    return Response(status=204)


@app.get("/api/stats")
def stats() -> Response:
    """Anonymous usage counters as JSON (gated by the site password in prod)."""
    return jsonify(analytics.snapshot())


@app.get("/stats")
def stats_page() -> Response:
    """Minimal human-readable usage dashboard (same password gate as the site)."""
    snap = analytics.snapshot()
    rows = "".join(
        f"<tr><td>{html_escape(k)}</td><td class='n'>{v}</td></tr>"
        for k, v in snap["events"].items()
    ) or "<tr><td colspan='2'>No events recorded yet.</td></tr>"
    mins = round(snap["uptime_seconds"] / 60, 1)
    body = (
        "<!doctype html><meta charset='utf-8'>"
        "<title>Usage stats</title>"
        "<style>body{font:14px/1.5 system-ui,sans-serif;max-width:560px;margin:40px auto;"
        "padding:0 16px;color:#29261b}h1{font-size:18px}table{border-collapse:collapse;"
        "width:100%}td{padding:6px 10px;border-bottom:1px solid #eee}td.n{text-align:right;"
        "font-variant-numeric:tabular-nums;font-weight:600}small{color:#888}</style>"
        f"<h1>Usage stats</h1><small>This worker, up {mins} min. "
        "Aggregate history lives in the stdout log stream.</small>"
        f"<table>{rows}</table>"
    )
    return Response(body, mimetype="text/html")


# ── SEO landing pages (server-rendered, public, crawlable) ───────────────────

@app.get("/law-schools")
def seo_index() -> Response:
    return Response(seo.render_index(_SCHOOLS, _base_url()), mimetype="text/html")


@app.get("/law-schools/<slug>")
def seo_school(slug: str) -> Response:
    school = _SCHOOLS_BY_ID.get(slug)
    if school is None:
        return Response("Law school not found.", status=404, mimetype="text/plain")
    return Response(seo.render_school(school, _SCHOOLS, _base_url()), mimetype="text/html")


@app.get("/law-schools-in/<state>")
def seo_state(state: str) -> Response:
    code = seo.state_from_slug(state)
    if code is None:
        return Response("State not found.", status=404, mimetype="text/plain")
    return Response(seo.render_state(code, _SCHOOLS, _base_url()), mimetype="text/html")


@app.get("/sitemap.xml")
def sitemap() -> Response:
    return Response(seo.render_sitemap(_SCHOOLS, _base_url()), mimetype="application/xml")


@app.get("/robots.txt")
def robots() -> Response:
    return Response(seo.render_robots(_base_url()), mimetype="text/plain")


@app.errorhandler(404)
def not_found(_e) -> Response:
    """API callers get JSON; people get a small branded page back to the app."""
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found"}), 404
    body = (
        "<!doctype html><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Not found — Opportunity: Law</title>"
        "<style>body{font:16px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
        "color:#29261b;background:#faf9f7;max-width:520px;margin:18vh auto;padding:0 20px;"
        "text-align:center}a{color:#2f7a50;font-weight:600}h1{font-size:22px}</style>"
        "<h1>Page not found</h1>"
        "<p>That page doesn’t exist. Try the <a href='/'>law school matcher</a> "
        "or <a href='/law-schools'>browse all law schools</a>.</p>"
    )
    return Response(body, status=404, mimetype="text/html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
