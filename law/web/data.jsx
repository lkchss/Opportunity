/* data.jsx — constants, formatters, and the /api adapter.
   Scoring lives on the backend (law/matcher.py); this file translates the
   posted intake form into the /api/match payload and the API response into
   the flat school shape the screens render. */

const STATES = ["AL","AK","AZ","AR","CA","CO","CT","DC","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"];

const GOALS = ["Unsure", "BigLaw / In-house", "Federal Clerkship", "Government", "Public Interest", "Solo/Small Firm", "Academia"];

const TIERS = {
  safety: { label: "Safety", cls: "t-safety", color: "var(--safety-dot)" },
  target: { label: "Target", cls: "t-target", color: "var(--target-dot)" },
  reach:  { label: "Reach",  cls: "t-reach",  color: "var(--reach-dot)" },
  hard:   { label: "Hard reach", cls: "t-hard", color: "var(--hard-dot)" },
};
const TIER_ORDER = ["safety", "target", "reach", "hard"];

/* Backend tier labels → frontend tier keys. */
const TIER_FROM_API = { "safety": "safety", "target": "target", "reach": "reach", "hard reach": "hard" };

/* Career goal → the outcome stat it features (cards, table column, detail). */
const GOAL_KEY = {
  "BigLaw / In-house": "biglaw", "Federal Clerkship": "clerk", "Government": "gov",
  "Public Interest": "pi", "Solo/Small Firm": "solo", "Academia": "clerk", "Unsure": "biglaw",
};
const GOAL_LABEL = {
  "BigLaw / In-house": "BigLaw", "Federal Clerkship": "Fed clerk", "Government": "Gov",
  "Public Interest": "Pub int", "Solo/Small Firm": "Solo/Sm", "Academia": "Clerk", "Unsure": "BigLaw",
};

const wiki = (n) => "https://en.wikipedia.org/wiki/" + n.replace(/ /g, "_");

/* Official school site. Falls back to a name-scoped web search when the record
   has no website_url (only ~75/196 are populated), which reliably lands on the
   school's own site as the top result rather than Wikipedia. */
const schoolSite = (m) =>
  (m && m.site) || ("https://www.google.com/search?q=" + encodeURIComponent((m && m.name || "") + " law school"));

/* Anonymous usage ping — feature interactions only, never profile data.
   Fire-and-forget: it must never block the UI or surface an error. The backend
   drops anything not on its event allowlist. */
function track(name, label) {
  try {
    const body = JSON.stringify(label ? { name, label } : { name });
    fetch("/api/event", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch(() => {});
  } catch (e) {/* analytics must never break the app */}
}

/* ---------------- formatters ---------------- */
const fmtMoney = (n) => n == null ? "—" : "$" + Math.round(n).toLocaleString();
const fmtMoneyK = (n) => n == null ? "—" : "$" + Math.round(n / 1000) + "k";
const fmtPct = (f) => f == null ? "—" : Math.round(f * 100) + "%";
const fmtPct1 = (f) => f == null ? "—" : Math.round(f * 1000) / 10 + "%";
const fmtRank = (r) => r == null || r >= 999 ? "Unranked" : "#" + r;
const fmtGpa = (g) => g == null ? "—" : Number(g).toFixed(2);
const clamp = (v, lo = 0, hi = 100) => Math.max(lo, Math.min(hi, v));

/* ---------------- form → payload ---------------- */

/* Typed household income ($) → the bracket the matcher's need factor uses. */
function incomeBracket(raw) {
  if (raw === "" || raw == null) return "prefer_not";
  const n = Number(raw);
  if (Number.isNaN(n)) return "prefer_not";
  if (n < 65000) return "under_65k";
  if (n < 130000) return "65k_130k";
  if (n < 200000) return "130k_200k";
  return "over_200k";
}

function buildPayload(form, lsatOverride, weightsOverride, applyOpts) {
  const raw = lsatOverride !== undefined ? lsatOverride : form.lsat;
  const lsat = Number(raw);
  // A blank/zero/garbage LSAT must never reach the matcher as a real score.
  const noLsat = !!form.noLsat || raw === "" || raw == null || Number.isNaN(lsat) || lsat <= 0;
  const payload = {
    no_lsat: noLsat,
    lsat: noLsat ? null : Math.min(lsat, 180),
    gpa: Number(form.gpa),
    goals_weighted: [{ goal: form.goal || "Unsure", weight: 1 }],
    target_states_weighted: (form.practice || []).filter((p) => p.state && p.weight > 0),
    instate_states: (form.instate || []).filter(Boolean),
    income_bracket: incomeBracket(form.income),
    cash_available: Number(form.cash) || 0,
    existing_debt: Number(form.debt) || 0,
    scholarship: Math.round(form.costW),
    career_weight: Math.round(form.careerW),
    location_weight: Math.round(form.locW),
    wants_transfer: !!form.transfer,
  };
  // Optional per-score weight multipliers from the TweaksPanel.
  // null/undefined → key omitted → byte-identical backend baseline.
  const w = weightsOverride !== undefined ? weightsOverride : (form.weights || null);
  if (w != null) payload.weights = w;
  // Optional apply-plan controls (risk posture + opt-in long shots). Omitting
  // them reproduces the historical balanced 2/4/3 slate.
  const opts = applyOpts || {};
  if (opts.strategy) payload.apply_strategy = opts.strategy;
  if (opts.includeHard) payload.include_hard = true;
  return payload;
}

/* ---------------- API → screen shape ---------------- */

/* Raw school record (either endpoint) → the flat shape the screens use. */
function adaptRaw(s) {
  const size = s.class_size_1l;
  return {
    id: s.id, name: s.name, loc: s.location, state: s.state,
    site: s.website_url || null,
    isPublic: !!s.is_public,
    rank: s.usnwr_rank_2026 == null ? 999 : s.usnwr_rank_2026,
    accept: s.acceptance_rate,
    l25: s.lsat_25, l50: s.lsat_50, l75: s.lsat_75,
    g25: s.gpa_25, g50: s.gpa_50, g75: s.gpa_75,
    biglaw: s.biglaw_pct, clerk: s.federal_clerkship_pct, gov: s.government_pct,
    pi: s.public_interest_pct, solo: s.solo_small_firm_pct,
    bar: s.bar_pass_rate_first_time, barUlt: s.bar_pass_ultimate, emp: s.employed_10mo_pct,
    tuitRes: s.annual_tuition_resident != null ? s.annual_tuition_resident : s.annual_tuition,
    tuitNon: s.annual_tuition_nonresident != null ? s.annual_tuition_nonresident : s.annual_tuition,
    living: s.living_expense_annual,
    grantRate: s.scholarship_pct, medGrant: s.median_scholarship,
    cond: !!s.conditional_scholarship,
    trIn: s.transfers_in,
    trOut: s.transfer_out_rate != null ? s.transfer_out_rate
      : s.transfers_out != null && size ? s.transfers_out / size : null,
    attr: s.attrition_1l_pct, salPriv: s.median_private_sector_salary,
    size, feeds: s.target_states || [],
    scDebt: s.scorecard_median_debt, scEarn: s.scorecard_earn_4yr,
    alumni: s.notable_alumni || [],
    placementStates: s.placement_states || null,
    placementYear: s.placement_year || null,
    selTrend: s.selectivity_trend || null,
  };
}

function whyLine(m, goal) {
  const out = [];
  const goalShort = goal === "BigLaw / In-house" ? "BigLaw" :
    goal === "Federal Clerkship" ? "clerkship" :
    goal === "Public Interest" ? "public-interest" : (goal || "unsure").toLowerCase();
  if (m.career >= 68) out.push(`Strong ${goalShort} pipeline (${fmtPct(m.goalPct)})`);
  if (m.tier === "safety" && m.scholarship >= 70) out.push("strong odds of a large scholarship");
  else if (m.scholarship >= 72) out.push("likely merit aid");
  if (m.location >= 88) out.push("places grads in your market");
  if (m.fin >= 72) out.push("manageable projected debt");
  if ((m.tier === "reach" || m.tier === "hard") && out.length < 2)
    out.push("below their medians — the upside is real");
  if (out.length === 0) out.push("a balanced option for your profile");
  const line = out.slice(0, 2).join(" · ");
  return line.charAt(0).toUpperCase() + line.slice(1);
}

/* Matched school (/api/match entry) → screen shape with scores + financials. */
function adaptMatched(s, goal) {
  const m = adaptRaw(s);
  const fb = s.financial_breakdown || {};
  m.tier = TIER_FROM_API[s.admissibility_tier] || "hard";
  m.admiss = Math.round(s.admissibility_score);
  m.prestige = Math.round(s.prestige_score);
  m.career = Math.round(s.career_fit_score);
  m.location = Math.round(s.location_fit_score);
  m.scholarship = Math.round(s.scholarship_score);
  m.fin = Math.round(s.financial_score);
  m.composite = s.composite_score;
  m.pure = s.fit_no_admissibility_score;
  m.radar = s.radar || [m.admiss, m.prestige, m.career, m.location, m.scholarship, m.fin];
  m.instate = !!fb.qualifies_instate;
  m.tuition = fb.annual_tuition_effective;
  m.gross = fb.gross_cost;
  m.aid3 = fb.expected_aid;
  m.cashApplied = fb.cash_applied || 0;
  m.existingDebt = fb.existing_debt || 0;
  m.netDebt = fb.net_debt;
  m.totalDebt = fb.total_debt != null ? fb.total_debt : fb.net_debt;
  m.salary = fb.starting_salary;
  m.monthly = fb.monthly_payment_estimate;
  m.dti = fb.debt_to_income_ratio;
  m.pslf = !!fb.pslf_eligible;
  m.idrMonthly = fb.idr_monthly_net;
  m.pslfPaid = fb.pslf_total_paid;
  m.pslfForgiven = fb.pslf_forgiven;
  // Display-only scholarship leverage insight (never affects scores or ranking)
  m.leverage = s.scholarship_leverage || null;
  const gk = GOAL_KEY[goal] || "biglaw";
  m.goalPct = gk === "biglaw" ? m.biglaw : gk === "clerk" ? m.clerk :
    gk === "gov" ? m.gov : gk === "pi" ? m.pi : m.solo;
  m.why = whyLine(m, goal);
  return m;
}

/* Full /api/match response → { schools, plan, portfolio }. The transfer plan
   entries are resolved back to the full matched objects so cards render the same
   idiom. Portfolio slate entries keep the backend shape (id, name, tier, reason,
   net_debt, composite_score) and are resolved to full school objects for click-
   through. */
function adaptMatchResponse(json, goal) {
  const schools = (json.schools || []).map((s) => adaptMatched(s, goal));
  const byId = {};
  schools.forEach((m) => { byId[m.id] = m; });
  const tp = json.transfer_plan || {};
  const resolve = (rows) => (rows || []).map((p) => byId[p.id]).filter(Boolean);
  // The launchpad card asserts "X% of 1Ls transfer up" — keep only schools
  // where that claim holds (the backend ranks but doesn't gate on it).
  const launchpads = resolve(tp.launchpads).filter((m) => m.trOut != null && m.trOut >= 0.015);

  // Portfolio: resolve each slate entry to full school + carry the reason line.
  const rawPortfolio = json.portfolio || {};
  function resolveSlate(entries) {
    return (entries || []).map((e) => {
      const full = byId[e.id];
      if (!full) return null;
      return { ...full, portfolioReason: e.reason };
    }).filter(Boolean);
  }
  const portfolio = {
    safeties:  resolveSlate(rawPortfolio.safeties),
    targets:   resolveSlate(rawPortfolio.targets),
    reaches:   resolveSlate(rawPortfolio.reaches),
    longshots: resolveSlate(rawPortfolio.longshots),
    strategy:  rawPortfolio.strategy || "balanced",
    quota:     rawPortfolio.quota || null,
    adaptNotes: rawPortfolio.adapt_notes || [],
  };
  const totalSlate = portfolio.safeties.length + portfolio.targets.length +
    portfolio.reaches.length + portfolio.longshots.length;

  return {
    schools,
    plan: { launchpads, targets: resolve(tp.targets) },
    portfolio: totalSlate > 0 ? portfolio : null,
  };
}

/* Share-link profile encoding: UTF-8-safe base64 of the form JSON. */
function encodeShare(form) {
  return btoa(unescape(encodeURIComponent(JSON.stringify(form))));
}
function decodeShare(hash) {
  return JSON.parse(decodeURIComponent(escape(atob(hash))));
}

Object.assign(window, {
  STATES, GOALS, TIERS, TIER_ORDER, TIER_FROM_API, GOAL_KEY, GOAL_LABEL, wiki, schoolSite, track,
  fmtMoney, fmtMoneyK, fmtPct, fmtPct1, fmtRank, fmtGpa, clamp,
  incomeBracket, buildPayload, adaptRaw, adaptMatched, adaptMatchResponse,
  encodeShare, decodeShare,
});
