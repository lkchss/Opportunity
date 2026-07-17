"""Server-rendered SEO landing pages built from the law-school dataset.

The app itself is a client-rendered React SPA, which search engines index
poorly. These routes emit plain, fast, server-rendered HTML — one page per
school, one per state, plus an index hub and sitemap — so the structured ABA
data we already hold becomes crawlable, shareable surface area that funnels to
the matcher. Pure functions of (schools, base_url): no app context needed, so
they're trivially testable.

Nothing here is personalized and nothing is scored; it's a read-only projection
of law_schools.json into HTML.
"""

from __future__ import annotations

from html import escape as _esc
from typing import Optional

SITE_NAME = "Opportunity: Law"
TAGLINE = "Free, no-login law school matching on official ABA data."

# Code → full state name (incl. DC). Pages render only for states present in
# the dataset; this map just supplies display names + URL slugs.
STATE_NAMES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}


# ── URL slugs ────────────────────────────────────────────────────────────────

def state_slug(code: str) -> str:
    """'TX' → 'texas'. Falls back to the lowercased code if unknown."""
    name = STATE_NAMES.get((code or "").upper())
    return name.lower().replace(" ", "-") if name else (code or "").lower()


def state_from_slug(slug: str) -> Optional[str]:
    """'texas' → 'TX' (None if no match)."""
    s = (slug or "").lower()
    for code, name in STATE_NAMES.items():
        if name.lower().replace(" ", "-") == s:
            return code
    if s.upper() in STATE_NAMES:
        return s.upper()
    return None


def school_url(school: dict) -> str:
    return f"/law-schools/{school['id']}"


def state_url(code: str) -> str:
    return f"/law-schools-in/{state_slug(code)}"


# ── formatters ───────────────────────────────────────────────────────────────

def _pct(frac, digits=0) -> str:
    if frac is None:
        return "—"
    return f"{round(frac * 100, digits):g}%"


def _money(n) -> str:
    return "—" if n is None else "$" + format(int(round(n)), ",")


def _rank(r) -> str:
    return "Unranked" if r is None or r >= 999 else f"#{int(r)}"


def _num(n, digits=2) -> str:
    return "—" if n is None else f"{round(float(n), digits):g}"


def _city_state(location: str, state: str) -> tuple[str, str]:
    if location and "," in location:
        city, st = location.rsplit(",", 1)
        return city.strip(), st.strip()
    return (location or "").strip(), (state or "").strip()


# ── shared layout ────────────────────────────────────────────────────────────

_CSS = """
*{box-sizing:border-box}
body{margin:0;font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  color:#29261b;background:#faf9f7}
a{color:#2f7a50;text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:760px;margin:0 auto;padding:0 18px}
header.site{border-bottom:1px solid #ece7dd;background:#fff}
header.site .wrap{display:flex;align-items:center;justify-content:space-between;height:56px}
header.site .brand{font-weight:700;color:#29261b;font-size:17px}
.cta{display:inline-block;background:#2f7a50;color:#fff;font-weight:600;
  padding:10px 16px;border-radius:9px;margin:0}
.cta:hover{background:#276843;text-decoration:none;color:#fff}
.crumbs{font-size:13px;color:#6f6a5e;margin:18px 0 6px}
.crumbs a{color:#6f6a5e}
h1{font-size:27px;line-height:1.25;margin:6px 0 4px}
h2{font-size:20px;margin:30px 0 10px;padding-bottom:6px;border-bottom:1px solid #ece7dd}
.sub{color:#6b6657;margin:0 0 8px}
.lede{font-size:17px;color:#43402f}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:16px 0}
.stat{background:#fff;border:1px solid #ece7dd;border-radius:10px;padding:12px 14px}
.stat .k{font-size:12px;color:#6f6a5e;text-transform:uppercase;letter-spacing:.03em}
.stat .v{font-size:21px;font-weight:700;margin-top:2px}
table{width:100%;border-collapse:collapse;margin:10px 0;font-size:15px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #ece7dd}
th{font-size:12px;text-transform:uppercase;letter-spacing:.03em;color:#6f6a5e}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
ul.links{list-style:none;padding:0;margin:10px 0;columns:2;column-gap:24px}
ul.links li{margin:0 0 6px;break-inside:avoid}
.callout{background:#fff;border:1px solid #ece7dd;border-left:3px solid #2f7a50;
  border-radius:0 10px 10px 0;padding:16px 18px;margin:24px 0}
.callout p{margin:0 0 12px}
.faq{display:flex;flex-direction:column;gap:14px;margin-top:12px}
.faq-item h3{font-size:16px;margin:0 0 4px}
.faq-item p{margin:0;color:#43402f}
footer.site{margin:48px 0 24px;color:#6f6a5e;font-size:13px;text-align:center}
footer.site a{text-decoration:underline}
@media(max-width:520px){ul.links{columns:1}h1{font-size:23px}}
"""


def _layout(*, title: str, description: str, canonical: str, base_url: str,
            body: str, jsonld: str = "", og_type: str = "website") -> str:
    """Wrap page body in a full HTML document with SEO + social meta."""
    abs_url = base_url + canonical
    t = _esc(title)
    d = _esc(description)
    ld = f'<script type="application/ld+json">{jsonld}</script>' if jsonld else ""
    return (
        "<!doctype html><html lang=\"en\"><head>"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<meta name=\"theme-color\" content=\"#2f7a50\">"
        "<link rel=\"icon\" href=\"data:,\">"
        f"<title>{t}</title>"
        f"<meta name=\"description\" content=\"{d}\">"
        f"<link rel=\"canonical\" href=\"{_esc(abs_url)}\">"
        f"<meta property=\"og:type\" content=\"{og_type}\">"
        f"<meta property=\"og:title\" content=\"{t}\">"
        f"<meta property=\"og:description\" content=\"{d}\">"
        f"<meta property=\"og:url\" content=\"{_esc(abs_url)}\">"
        f"<meta property=\"og:site_name\" content=\"{_esc(SITE_NAME)}\">"
        "<meta name=\"twitter:card\" content=\"summary\">"
        f"<meta name=\"twitter:title\" content=\"{t}\">"
        f"<meta name=\"twitter:description\" content=\"{d}\">"
        f"<style>{_CSS}</style>{ld}</head><body>"
        "<header class=\"site\"><div class=\"wrap\">"
        f"<a class=\"brand\" href=\"/\">{_esc(SITE_NAME)}</a>"
        "<a class=\"cta\" href=\"/\">Find your matches →</a>"
        "</div></header><main class=\"wrap\">"
        f"{body}"
        "</main><footer class=\"site\"><div class=\"wrap\">"
        f"{_esc(TAGLINE)} Data from ABA 509 disclosures &amp; College Scorecard. "
        "<a href=\"/law-schools\">All law schools</a>."
        "</div></footer></body></html>"
    )


def _crumbs(*items: tuple[str, Optional[str]]) -> str:
    """items: (label, href|None). Last item is the current page (no link)."""
    parts = []
    for label, href in items:
        parts.append(f'<a href="{_esc(href)}">{_esc(label)}</a>' if href else _esc(label))
    return f'<div class="crumbs">{" › ".join(parts)}</div>'


def _cta_block(text: str) -> str:
    return (
        f'<div class="callout"><p>{_esc(text)}</p>'
        '<a class="cta" href="/">Find your matches →</a></div>'
    )


# ── generated prose + FAQ (long-tail SEO surface) ────────────────────────────

def _school_intro(school: dict, city: str, state_name: str) -> str:
    """A short, keyword-rich overview paragraph built from real fields."""
    name = school.get("name", "This law school")
    kind = "public" if school.get("is_public") else "private"
    rank = school.get("usnwr_rank_2026")
    rank_clause = (f", ranked {_rank(rank)} by U.S. News for 2026,"
                   if rank and rank < 999 else "")
    sentences = [f"{name} is a {kind} law school in {city}, {state_name}{rank_clause}."]

    l50, g50, acc = school.get("lsat_50"), school.get("gpa_50"), school.get("acceptance_rate")
    if l50 and g50:
        sentences.append(
            f"The median entering student has an LSAT of {l50} and a GPA of {_num(g50)}.")
    if acc is not None:
        sentences.append(f"It admits roughly {_pct(acc)} of applicants.")
    bar = school.get("bar_pass_rate_first_time")
    if bar is not None:
        sentences.append(f"{_pct(bar)} of first-time test-takers pass the bar.")
    return " ".join(sentences)


def _school_faqs(school: dict) -> list[tuple[str, str]]:
    """Q&A pairs answered from real data — only those with data are returned."""
    name = school.get("name", "this school")
    faqs: list[tuple[str, str]] = []

    l50, g50 = school.get("lsat_50"), school.get("gpa_50")
    l25, g25 = school.get("lsat_25"), school.get("gpa_25")
    l75, g75 = school.get("lsat_75"), school.get("gpa_75")
    acc = school.get("acceptance_rate")

    if acc is not None or l50:
        a = ""
        if acc is not None:
            a += f"{name} admits about {_pct(acc)} of applicants. "
        if l50 and g50:
            a += f"The median admit has a {l50} LSAT and {_num(g50)} GPA"
            if l25 and l75:
                a += f", with the middle 50% scoring {l25}–{l75} on the LSAT"
            a += "."
        faqs.append((f"How hard is it to get into {name}?", a.strip()))

    if l50 and g50:
        a = (f"Aim for around a {l50} LSAT and {_num(g50)} GPA — those are the medians "
             f"at {name}.")
        if l25 and g25:
            a += (f" The 25th-percentile admit had a {l25} LSAT and {_num(g25)} GPA, so "
                  "applicants below a median often still get in with a stronger "
                  "complementary number.")
        faqs.append((f"What LSAT and GPA do you need for {name}?", a))

    tuition = school.get("annual_tuition_nonresident") or school.get("annual_tuition")
    if tuition:
        a = f"Annual tuition at {name} is about {_money(tuition)}"
        living = school.get("living_expense_annual")
        if living:
            a += f", plus roughly {_money(living)} a year in living costs"
        a += ". "
        sp = school.get("scholarship_pct")
        if sp is not None:
            a += f"About {_pct(sp)} of students receive a scholarship"
            mg = school.get("median_scholarship")
            if mg:
                a += f" (median {_money(mg)} per year)"
            a += ". "
        debt = school.get("scorecard_median_debt")
        if debt:
            a += f"Recent graduates carried a median of {_money(debt)} in law-school debt."
        faqs.append((f"How much does {name} cost?", a.strip()))

    bar = school.get("bar_pass_rate_first_time")
    if bar is not None:
        a = f"{_pct(bar)} of first-time test-takers from {name} pass the bar exam"
        ult = school.get("bar_pass_ultimate")
        if ult is not None:
            a += f", and {_pct(ult)} pass eventually"
        a += "."
        faqs.append((f"What is the bar passage rate at {name}?", a))

    big = school.get("biglaw_pct")
    sal = school.get("median_private_sector_salary")
    if big is not None or sal:
        a = ""
        if big is not None:
            a += f"About {_pct(big)} of {name} graduates take BigLaw jobs"
            clerk = school.get("federal_clerkship_pct")
            if clerk:
                a += f" and {_pct(clerk)} land federal clerkships"
            a += ". "
        if sal:
            a += f"The median private-sector starting salary is {_money(sal)}."
        faqs.append((f"What kind of jobs do {name} graduates get?", a.strip()))

    ps = school.get("placement_states") or []
    if ps:
        tops = ", ".join(
            f"{STATE_NAMES.get(p['state'], p['state'])} ({_num(p.get('pct'), 1)}%)"
            for p in ps[:3] if p.get("state"))
        if tops:
            faqs.append((f"Where do {name} graduates work?",
                         f"Most {name} graduates begin their careers in {tops}."))
    return faqs


def _faq_section(faqs: list[tuple[str, str]]) -> str:
    if not faqs:
        return ""
    items = "".join(
        f'<div class="faq-item"><h3>{_esc(q)}</h3><p>{_esc(a)}</p></div>'
        for q, a in faqs
    )
    return f'<h2>Frequently asked questions</h2><div class="faq">{items}</div>'


def _faq_jsonld(faqs: list[tuple[str, str]]) -> Optional[dict]:
    if not faqs:
        return None
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in faqs
        ],
    }


# ── per-school page ──────────────────────────────────────────────────────────

def render_school(school: dict, schools: list[dict], base_url: str) -> str:
    name = school.get("name", "Law School")
    city, st = _city_state(school.get("location", ""), school.get("state", ""))
    state_code = (school.get("state") or "").upper()
    state_name = STATE_NAMES.get(state_code, state_code)
    rank = school.get("usnwr_rank_2026")
    l50, g50 = school.get("lsat_50"), school.get("gpa_50")
    acc = school.get("acceptance_rate")

    title = f"{name} — Admissions Stats, Scholarships & Outcomes | {SITE_NAME}"
    desc = (
        f"{name} ({city}, {state_code}): median LSAT {l50 or '—'}, GPA {_num(g50)}, "
        f"{_pct(acc)} acceptance. See admit profile, scholarship odds, bar passage, "
        f"where grads work, and true 3-year cost."
    )[:300]

    # Key stats grid
    stats = [
        ("US News rank", _rank(rank)),
        ("Median LSAT", str(l50) if l50 else "—"),
        ("Median GPA", _num(g50)),
        ("Acceptance rate", _pct(acc)),
        ("Bar pass (1st time)", _pct(school.get("bar_pass_rate_first_time"))),
        ("Employed @10mo", _pct(school.get("employed_10mo_pct"))),
    ]
    grid = "".join(
        f'<div class="stat"><div class="k">{_esc(k)}</div><div class="v">{_esc(v)}</div></div>'
        for k, v in stats
    )

    # Admissions table (25/50/75)
    adm = (
        '<h2>Admissions profile</h2>'
        '<table><tr><th>Percentile</th><th class="n">LSAT</th><th class="n">GPA</th></tr>'
        f'<tr><td>25th</td><td class="n">{school.get("lsat_25") or "—"}</td>'
        f'<td class="n">{_num(school.get("gpa_25"))}</td></tr>'
        f'<tr><td>Median</td><td class="n">{l50 or "—"}</td>'
        f'<td class="n">{_num(g50)}</td></tr>'
        f'<tr><td>75th</td><td class="n">{school.get("lsat_75") or "—"}</td>'
        f'<td class="n">{_num(school.get("gpa_75"))}</td></tr></table>'
    )

    # Cost
    tuition = school.get("annual_tuition_nonresident") or school.get("annual_tuition")
    cost = (
        '<h2>Cost &amp; aid</h2><div class="grid">'
        f'<div class="stat"><div class="k">Annual tuition</div><div class="v">{_esc(_money(tuition))}</div></div>'
        f'<div class="stat"><div class="k">Living budget /yr</div><div class="v">{_esc(_money(school.get("living_expense_annual")))}</div></div>'
        f'<div class="stat"><div class="k">Any-scholarship rate</div><div class="v">{_esc(_pct(school.get("scholarship_pct")))}</div></div>'
        f'<div class="stat"><div class="k">Median grant /yr</div><div class="v">{_esc(_money(school.get("median_scholarship")))}</div></div>'
        "</div>"
    )
    debt = school.get("scorecard_median_debt")
    earn = school.get("scorecard_earn_4yr")
    if debt or earn:
        cost += (
            f'<p class="sub">Real graduate outcomes (College Scorecard): median debt '
            f'<strong>{_esc(_money(debt))}</strong>, earnings 4 years out '
            f'<strong>{_esc(_money(earn))}</strong>.</p>'
        )

    # Careers
    careers = (
        '<h2>Career outcomes</h2><div class="grid">'
        f'<div class="stat"><div class="k">BigLaw</div><div class="v">{_esc(_pct(school.get("biglaw_pct")))}</div></div>'
        f'<div class="stat"><div class="k">Fed. clerkship</div><div class="v">{_esc(_pct(school.get("federal_clerkship_pct")))}</div></div>'
        f'<div class="stat"><div class="k">Government</div><div class="v">{_esc(_pct(school.get("government_pct")))}</div></div>'
        f'<div class="stat"><div class="k">Public interest</div><div class="v">{_esc(_pct(school.get("public_interest_pct")))}</div></div>'
        f'<div class="stat"><div class="k">Median private salary</div><div class="v">{_esc(_money(school.get("median_private_sector_salary")))}</div></div>'
        f'<div class="stat"><div class="k">Median public salary</div><div class="v">{_esc(_money(school.get("median_public_sector_salary")))}</div></div>'
        "</div>"
    )

    # Where grads work
    placement = ""
    ps = school.get("placement_states") or []
    if ps:
        rows = "".join(
            f'<tr><td><a href="{_esc(state_url(p["state"]))}">{_esc(STATE_NAMES.get(p["state"], p["state"]))}</a></td>'
            f'<td class="n">{_num(p.get("pct"), 1)}%</td></tr>'
            for p in ps if p.get("state")
        )
        yr = school.get("placement_year")
        placement = (
            f'<h2>Where graduates work{f" ({yr})" if yr else ""}</h2>'
            '<table><tr><th>State</th><th class="n">Share of grads</th></tr>'
            f'{rows}</table>'
        )

    # Internal links: other schools in the same state
    siblings = [s for s in schools if (s.get("state") or "").upper() == state_code and s["id"] != school["id"]]
    siblings.sort(key=lambda s: (s.get("usnwr_rank_2026") or 999))
    sib_links = ""
    if siblings:
        items = "".join(f'<li><a href="{_esc(school_url(s))}">{_esc(s.get("name",""))}</a></li>'
                        for s in siblings[:12])
        sib_links = (
            f'<h2>Other law schools in {_esc(state_name)}</h2>'
            f'<ul class="links">{items}</ul>'
            f'<p><a href="{_esc(state_url(state_code))}">All {_esc(state_name)} law schools →</a></p>'
        )

    official = ""
    if school.get("website_url"):
        official = (f'<p><a href="{_esc(school["website_url"])}" rel="nofollow noopener" '
                    f'target="_blank">Official school website ↗</a></p>')

    cta = _cta_block(
        f"See how {name} stacks up against your LSAT, GPA, target state, and budget — "
        "with your real admit read and projected debt, free and without an account."
    )

    intro = _school_intro(school, city, state_name)
    faqs = _school_faqs(school)
    faq_html = _faq_section(faqs)

    body = (
        _crumbs(("Home", "/"), ("Law schools", "/law-schools"),
                (STATE_NAMES.get(state_code, state_code), state_url(state_code)), (name, None))
        + f"<h1>{_esc(name)}</h1>"
        + f'<p class="sub">{_esc(city)}, {_esc(state_code)} · {_esc(_rank(rank))} US News (2026) · '
        + ("Public" if school.get("is_public") else "Private") + "</p>"
        + f'<p class="lede">{_esc(intro)}</p>'
        + f'<div class="grid">{grid}</div>'
        + official
        + adm + cost + careers + placement
        + faq_html
        + cta
        + sib_links
    )

    city_name, _ = _city_state(school.get("location", ""), state_code)
    jsonld = _school_jsonld(school, base_url, city_name, state_code)
    return _layout(title=title, description=desc, canonical=school_url(school),
                   base_url=base_url, body=body, jsonld=jsonld, og_type="article")


def _school_jsonld(school: dict, base_url: str, city: str, state_code: str) -> str:
    import json
    org = {
        "@context": "https://schema.org",
        "@type": "CollegeOrUniversity",
        "name": school.get("name"),
        "url": school.get("website_url") or (base_url + school_url(school)),
        "address": {
            "@type": "PostalAddress",
            "addressLocality": city,
            "addressRegion": state_code,
            "addressCountry": "US",
        },
    }
    crumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Law schools",
             "item": base_url + "/law-schools"},
            {"@type": "ListItem", "position": 2, "name": school.get("name"),
             "item": base_url + school_url(school)},
        ],
    }
    graph = [org, crumbs]
    faq = _faq_jsonld(_school_faqs(school))
    if faq:
        graph.append(faq)
    return json.dumps(graph)


# ── per-state page ───────────────────────────────────────────────────────────

def render_state(state_code: str, schools: list[dict], base_url: str) -> str:
    state_code = state_code.upper()
    state_name = STATE_NAMES.get(state_code, state_code)
    located = [s for s in schools if (s.get("state") or "").upper() == state_code]
    located.sort(key=lambda s: (s.get("usnwr_rank_2026") or 999))

    title = f"Law Schools in {state_name} — Stats, Cost & Outcomes | {SITE_NAME}"
    desc = (
        f"All {len(located)} ABA-accredited law schools in {state_name}, ranked with "
        f"median LSAT/GPA, acceptance rate, bar passage, and true cost. Free matcher, no login."
    )[:300]

    rows = "".join(
        f'<tr><td><a href="{_esc(school_url(s))}">{_esc(s.get("name",""))}</a></td>'
        f'<td class="n">{_esc(_rank(s.get("usnwr_rank_2026")))}</td>'
        f'<td class="n">{s.get("lsat_50") or "—"}</td>'
        f'<td class="n">{_num(s.get("gpa_50"))}</td>'
        f'<td class="n">{_esc(_pct(s.get("acceptance_rate")))}</td>'
        f'<td class="n">{_esc(_pct(s.get("bar_pass_rate_first_time")))}</td></tr>'
        for s in located
    )
    table = (
        '<table><tr><th>School</th><th class="n">US News</th><th class="n">LSAT</th>'
        '<th class="n">GPA</th><th class="n">Accept</th><th class="n">Bar</th></tr>'
        f'{rows}</table>' if located else '<p class="sub">No ABA law schools on record for this state.</p>'
    )

    # Unique-data section: schools nationwide that send the most grads to this state
    feeders = []
    for s in schools:
        for p in (s.get("placement_states") or []):
            if (p.get("state") or "").upper() == state_code and p.get("pct"):
                feeders.append((s, p["pct"]))
    feeders.sort(key=lambda t: t[1], reverse=True)
    feed_html = ""
    if feeders:
        frows = "".join(
            f'<tr><td><a href="{_esc(school_url(s))}">{_esc(s.get("name",""))}</a></td>'
            f'<td class="n">{_num(pct,1)}%</td></tr>'
            for s, pct in feeders[:10]
        )
        feed_html = (
            f'<h2>Schools that send the most grads to {_esc(state_name)}</h2>'
            f'<p class="sub">Share of each school’s graduating class that takes jobs in {_esc(state_name)} '
            '(ABA employment data) — useful if you want to practice here, wherever you study.</p>'
            '<table><tr><th>School</th><th class="n">% to ' + _esc(state_code) + '</th></tr>'
            f'{frows}</table>'
        )

    cta = _cta_block(
        f"Want to know which {state_name} law school fits your numbers and budget? "
        "Enter your LSAT, GPA, and goals for a ranked, personalized list — free, no account."
    )

    faqs = _state_faqs(state_name, located)
    faq_html = _faq_section(faqs)

    body = (
        _crumbs(("Home", "/"), ("Law schools", "/law-schools"), (state_name, None))
        + f"<h1>Law Schools in {_esc(state_name)}</h1>"
        + f'<p class="lede">{_esc(desc)}</p>'
        + (f'<h2>The {len(located)} ABA law schools in {_esc(state_name)}</h2>' if located else "")
        + table + feed_html + faq_html + cta
    )

    graph = [_state_jsonld_obj(state_name, located, base_url)]
    faq_ld = _faq_jsonld(faqs)
    if faq_ld:
        graph.append(faq_ld)
    import json as _json
    return _layout(title=title, description=desc, canonical=state_url(state_code),
                   base_url=base_url, body=body, jsonld=_json.dumps(graph))


def _state_faqs(state_name: str, located: list[dict]) -> list[tuple[str, str]]:
    """Q&A for a state page, from the located-school set."""
    if not located:
        return []
    faqs = [(
        f"How many law schools are in {state_name}?",
        f"{state_name} has {len(located)} ABA-accredited law school"
        f"{'s' if len(located) != 1 else ''}.",
    )]
    ranked = [s for s in located if (s.get("usnwr_rank_2026") or 999) < 999]
    if ranked:
        top = min(ranked, key=lambda s: s["usnwr_rank_2026"])
        faqs.append((
            f"What is the highest-ranked law school in {state_name}?",
            f"{top['name']} is the highest-ranked, at {_rank(top['usnwr_rank_2026'])} "
            "in the U.S. News 2026 rankings.",
        ))
    with_acc = [s for s in located if s.get("acceptance_rate") is not None]
    if with_acc:
        easiest = max(with_acc, key=lambda s: s["acceptance_rate"])
        faqs.append((
            f"What is the easiest law school to get into in {state_name}?",
            f"By acceptance rate, {easiest['name']} is the most accessible, admitting "
            f"about {_pct(easiest['acceptance_rate'])} of applicants.",
        ))
    return faqs


def _state_jsonld_obj(state_name: str, located: list[dict], base_url: str) -> dict:
    items = [
        {"@type": "ListItem", "position": i + 1, "name": s.get("name"),
         "url": base_url + school_url(s)}
        for i, s in enumerate(located)
    ]
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": f"Law schools in {state_name}",
        "itemListElement": items,
    }


# ── index hub ────────────────────────────────────────────────────────────────

def render_index(schools: list[dict], base_url: str) -> str:
    title = f"All ABA Law Schools — Stats, Rankings & Outcomes | {SITE_NAME}"
    desc = (
        f"Browse all {len(schools)} ABA-accredited law schools with median LSAT/GPA, "
        "acceptance rate, scholarship odds, bar passage, and true cost. Free matcher, no login."
    )[:300]

    states_present = sorted({(s.get("state") or "").upper() for s in schools if s.get("state")},
                            key=lambda c: STATE_NAMES.get(c, c))
    state_links = "".join(
        f'<li><a href="{_esc(state_url(c))}">Law schools in {_esc(STATE_NAMES.get(c, c))}</a></li>'
        for c in states_present
    )

    top = sorted(schools, key=lambda s: (s.get("usnwr_rank_2026") or 999))
    top_rows = "".join(
        f'<tr><td class="n">{_esc(_rank(s.get("usnwr_rank_2026")))}</td>'
        f'<td><a href="{_esc(school_url(s))}">{_esc(s.get("name",""))}</a></td>'
        f'<td>{_esc((s.get("state") or "").upper())}</td>'
        f'<td class="n">{s.get("lsat_50") or "—"}</td>'
        f'<td class="n">{_num(s.get("gpa_50"))}</td></tr>'
        for s in top[:25]
    )

    all_links = "".join(
        f'<li><a href="{_esc(school_url(s))}">{_esc(s.get("name",""))}</a></li>'
        for s in sorted(schools, key=lambda s: s.get("name", ""))
    )

    body = (
        _crumbs(("Home", "/"), ("Law schools", None))
        + "<h1>All ABA Law Schools</h1>"
        + f'<p class="lede">{_esc(desc)}</p>'
        + _cta_block("Skip the spreadsheets — get a ranked, personalized list from your "
                     "LSAT, GPA, target state, and budget. Free, no login.")
        + "<h2>Top 25 by US News (2026)</h2>"
        + '<table><tr><th class="n">Rank</th><th>School</th><th>State</th>'
          '<th class="n">LSAT</th><th class="n">GPA</th></tr>'
        + top_rows + "</table>"
        + "<h2>Browse by state</h2>"
        + f'<ul class="links">{state_links}</ul>'
        + "<h2>All schools (A–Z)</h2>"
        + f'<ul class="links">{all_links}</ul>'
    )
    return _layout(title=title, description=desc, canonical="/law-schools",
                   base_url=base_url, body=body)


# ── sitemap & robots ─────────────────────────────────────────────────────────

def render_sitemap(schools: list[dict], base_url: str) -> str:
    urls = ["/", "/law-schools"]
    urls += sorted(state_url(c) for c in {(s.get("state") or "").upper()
                                          for s in schools if s.get("state")})
    urls += [school_url(s) for s in schools]
    entries = "".join(f"<url><loc>{_esc(base_url + u)}</loc></url>" for u in urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{entries}</urlset>"
    )


def render_robots(base_url: str) -> str:
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /stats\n"
        f"Sitemap: {base_url}/sitemap.xml\n"
    )
