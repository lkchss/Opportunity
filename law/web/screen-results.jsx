/* screen-results.jsx — guided shortlist (default) + dense table + transfers. */

const TIER_SECTIONS = [
{ tier: "target", title: "Targets", sub: "Your numbers sit at or near the median. Apply broadly here." },
{ tier: "safety", title: "Safeties", sub: "Likely admits with strong merit aid" },
{ tier: "reach", title: "Reaches", sub: "Below their medians, but worth the application fee" }];


function SchoolCard({ m, onOpen, added, onToggleCompare, goalLabel, pure }) {
  const t = TIERS[m.tier];
  const score = pure ? m.pure : m.composite;
  return (
    <div className="school-card" onClick={() => onOpen(m)}>
      <ScoreRing value={score} color={gradeColor(score)} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
          <span className="sc-name">{m.name}</span>
          <span className="sc-meta">{m.loc} · USNWR {fmtRank(m.rank)}</span>
        </div>
        <div className="sc-why"><span className={`lead ${t.cls}`}>{t.label}.</span> {m.why}</div>
      </div>
      <div className="sc-stats">
        <div className="sc-stat">
          <div className="v">{fmtPct(m.goalPct)}</div>
          <div className="k">{goalLabel}</div>
        </div>
        <div className="sc-stat">
          <div className="v">{fmtPct(m.bar)}</div>
          <div className="k">Bar pass</div>
        </div>
        <div className="sc-stat">
          <div className="v">{fmtMoneyK(m.netDebt)}</div>
          <div className="k">Est. cost</div>
        </div>
      </div>
      <button className={`sc-add ${added ? "added" : ""}`} title={added ? "Remove from comparison" : "Add to side-by-side comparison"}
      aria-label={`${added ? "Remove" : "Add"} ${m.name} ${added ? "from" : "to"} compare`}
      onClick={(e) => {e.stopPropagation();onToggleCompare(m.id);}}>
        {added ? "✓ Added" : "+ Compare"}
      </button>
    </div>);

}

function GuidedView({ results, pure, onOpen, compareIds, onToggleCompare, goalLabel }) {
  const [expanded, setExpanded] = React.useState({}); // tier -> bool (show all)
  const [showHard, setShowHard] = React.useState(false);
  const byTier = (t) => results.filter((m) => m.tier === t);
  const hard = byTier("hard");

  // "Ignore admissibility": admission is assumed everywhere, so tier grouping
  // is meaningless — one flat list ranked by pure fit. Tier pills still show.
  if (pure) {
    const cap = expanded.pure ? results.length : 10;
    return (
      <section className="tier-section">
        <div className="ts-head">
          <h2>Best fit<span className="colon">:</span></h2>
          <span className="count">{results.length} schools</span>
        </div>
        <p className="ts-sub">Ranked by fit alone, as if you could get in anywhere</p>
        <div>
          {results.slice(0, cap).map((m) =>
          <SchoolCard key={m.id} m={m} pure onOpen={onOpen} goalLabel={goalLabel}
          added={compareIds.includes(m.id)} onToggleCompare={onToggleCompare} />
          )}
        </div>
        {results.length > 10 &&
        <div className="show-more-row">
            <button className="btn sm ghost"
          onClick={() => setExpanded((e) => ({ ...e, pure: !e.pure }))}>
              {expanded.pure ? "Show fewer" : `Show all ${results.length} schools ▾`}
            </button>
          </div>
        }
      </section>);
  }

  return (
    <div>
      {TIER_SECTIONS.map(({ tier, title, sub }) => {
        const rows = byTier(tier);
        if (!rows.length) return null;
        const cap = expanded[tier] ? rows.length : 4;
        return (
          <section className="tier-section" key={tier}>
            <div className="ts-head">
              <span className="dot" style={{ width: 10, height: 10, borderRadius: 99, background: TIERS[tier].color }}></span>
              <h2>{title}</h2>
              <span className="count">{rows.length} school{rows.length > 1 ? "s" : ""}</span>
            </div>
            <p className="ts-sub">{sub}</p>
            <div>
              {rows.slice(0, cap).map((m) =>
              <SchoolCard key={m.id} m={m} onOpen={onOpen} goalLabel={goalLabel}
              added={compareIds.includes(m.id)} onToggleCompare={onToggleCompare} />
              )}
            </div>
            {rows.length > 4 &&
            <div className="show-more-row">
                <button className="btn sm ghost"
              onClick={() => setExpanded((e) => ({ ...e, [tier]: !e[tier] }))}>
                  {expanded[tier] ? "Show fewer" : `Show all ${rows.length} ${tier === "safety" ? "safeties" : TIERS[tier].label.toLowerCase() + "s"} ▾`}
                </button>
              </div>
            }
          </section>);

      })}

      {hard.length > 0 && !showHard &&
      <div className="collapsed-tier">
          <span className="dot" style={{ width: 10, height: 10, borderRadius: 99, background: TIERS.hard.color, flex: "none" }}></span>
          <span><strong style={{ color: "var(--ink)" }}>{hard.length} hard reach{hard.length > 1 ? "es" : ""}</strong> hidden — long odds for your numbers.</span>
          <span className="show" onClick={() => setShowHard(true)}>Show anyway ▾</span>
        </div>
      }
      {hard.length > 0 && showHard &&
      <section className="tier-section">
          <div className="ts-head">
            <span className="dot" style={{ width: 10, height: 10, borderRadius: 99, background: TIERS.hard.color }}></span>
            <h2>Hard Reaches</h2>
            <span className="count">{hard.length}</span>
            <button className="btn xs ghost" onClick={() => setShowHard(false)}>hide</button>
          </div>
          <p className="ts-sub">Below their 25th percentiles. Apply only if money and time allow.</p>
          <div>
            {hard.map((m) =>
          <SchoolCard key={m.id} m={m} onOpen={onOpen} goalLabel={goalLabel}
          added={compareIds.includes(m.id)} onToggleCompare={onToggleCompare} />
          )}
          </div>
        </section>
      }
    </div>);

}

function TableView({ results, profile, pure, onOpen, compareIds, onToggleCompare, goalLabel }) {
  const [sortKey, setSortKey] = React.useState("score");
  const [asc, setAsc] = React.useState(false);
  const [tierFilter, setTierFilter] = React.useState("");
  const cols = [
  { k: "name", label: "School", l: true, sort: (m) => m.name },
  { k: "tier", label: "Tier", l: true, sort: (m) => TIER_ORDER.indexOf(m.tier) },
  { k: "rank", label: "USNWR", sort: (m) => m.rank },
  { k: "goal", label: goalLabel, l: true, sort: (m) => m.goalPct },
  { k: "bar", label: "Bar", l: true, sort: (m) => m.bar },
  { k: "delta", label: "LSAT Δ", sort: (m) => profile.lsat == null ? 0 : profile.lsat - m.l50 },
  { k: "cost", label: "Cost/aid", sort: (m) => m.netDebt },
  { k: "score", label: pure ? "Pure fit" : "Score", sort: (m) => pure ? m.pure : m.composite }];

  const filtered = React.useMemo(
    () => tierFilter ? results.filter((m) => m.tier === tierFilter) : results,
    [results, tierFilter]);
  const sorted = React.useMemo(() => {
    const col = cols.find((cc) => cc.k === sortKey);
    if (!col) return filtered;
    return [...filtered].sort((a, b) => {
      const av = col.sort(a),bv = col.sort(b);
      return (av < bv ? -1 : av > bv ? 1 : 0) * (asc ? 1 : -1);
    });
  }, [filtered, sortKey, asc, pure]);
  const onHeader = (col) => {
    if (sortKey === col.k) setAsc((v) => !v);else
    {setSortKey(col.k);setAsc(col.k === "name" || col.k === "rank" || col.k === "cost" || col.k === "tier");}
  };
  const topScore = Math.max(...results.map((m) => pure ? m.pure : m.composite));
  return (
    <div>
      <div className="chip-group" style={{ marginTop: 16 }}>
        <button type="button" className={`chip ${tierFilter === "" ? "active" : ""}`}
        onClick={() => setTierFilter("")}>All · {results.length}</button>
        {TIER_ORDER.map((tk) => {
          const n = results.filter((m) => m.tier === tk).length;
          return (
            <button key={tk} type="button" className={`chip ${tierFilter === tk ? "active" : ""}`}
            onClick={() => setTierFilter(tierFilter === tk ? "" : tk)}>
              {TIERS[tk].label} · {n}</button>);

        })}
      </div>
    <div className="dense-wrap">
      <table className="dense">
        <thead>
          <tr>
            <th style={{ width: 34, textAlign: "center" }} title="Select to compare">☐</th>
            {cols.map((col) =>
              <th key={col.k} className={col.l ? "l" : ""} onClick={() => onHeader(col)}>
                {col.label}{sortKey === col.k && <span className="arrow">{asc ? " ▲" : " ▼"}</span>}
              </th>
              )}
          </tr>
        </thead>
        <tbody>
          {sorted.map((m) => {
              const delta = profile.lsat == null || m.l50 == null ? null : profile.lsat - m.l50;
              const sc = pure ? m.pure : m.composite;
              return (
                <tr key={m.id} className={compareIds.includes(m.id) ? "selected" : ""} onClick={() => onOpen(m)}>
                <td style={{ textAlign: "center" }} onClick={(e) => {e.stopPropagation();onToggleCompare(m.id);}}>
                  <input type="checkbox" className="cmp-box" readOnly checked={compareIds.includes(m.id)}
                    aria-label={`Select ${m.name} to compare`} />
                </td>
                <td className="l school-cell"><span className="nm">{m.name}</span><span className="lc">{m.loc}</span></td>
                <td className="l"><TierPill tier={m.tier} /></td>
                <td>{fmtRank(m.rank)}</td>
                <td className="l"><CellBar frac={m.goalPct} /></td>
                <td className="l"><CellBar frac={m.bar} /></td>
                <td className={delta == null ? "" : delta >= 0 ? "delta-pos" : "delta-neg"}>
                  {delta == null ? "—" : (delta >= 0 ? "+" : "") + delta}</td>
                <td>{fmtMoneyK(m.netDebt)}</td>
                <td><span className={`score-chip ${sc >= topScore - 2 ? "top" : ""}`}>{Math.round(sc)}</span></td>
              </tr>);

            })}
        </tbody>
      </table>
      <div className="table-foot">
        <span>{sorted.length} SCHOOLS{tierFilter ? ` · ${TIERS[tierFilter].label.toUpperCase()} ONLY` : ""}</span>
        <span>SORT: {cols.find((cc) => cc.k === sortKey).label.toUpperCase()} {asc ? "ASC" : "DESC"}</span>
        <span className="right">CLICK ROW → DETAIL · ☐ → COMPARE</span>
      </div>
    </div>
    </div>);

}

function TransferCard({ m, onOpen, stats, whyText }) {
  const t = TIERS[m.tier];
  return (
    <div className="school-card" onClick={() => onOpen(m)}>
      <ScoreRing value={m.composite} color={gradeColor(m.composite)} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
          <span className="sc-name">{m.name}</span>
          <span className="sc-meta">{m.loc} · USNWR {fmtRank(m.rank)}</span>
        </div>
        <div className="sc-why"><span className={`lead ${t.cls}`}>{t.label}.</span> {whyText}</div>
      </div>
      <div className="sc-stats">
        {stats.map(([v, k]) =>
        <div className="sc-stat" key={k}>
            <div className="v">{v}</div>
            <div className="k">{k}</div>
          </div>
        )}
      </div>
    </div>);
}

function TransfersView({ plan, onOpen, goalLabel }) {
  const { launchpads, targets } = plan;
  return (
    <div>
      <section className="tier-section">
        <div className="ts-head">
          <h2>Launchpads<span className="colon">:</span></h2>
          <span className="count">{launchpads.length} of your matches</span>
        </div>
        <p className="ts-sub">Realistic admits whose students regularly move up after 1L</p>
        <div>
          {launchpads.length === 0 && <div className="muted">No realistic admits with strong transfer-out records.</div>}
          {launchpads.map((m) =>
          <TransferCard key={m.id} m={m} onOpen={onOpen}
          whyText={`${fmtPct1(m.trOut)} of 1Ls transfer up · ${m.scholarship >= 70 ? "big merit aid keeps 1L cheap" : "keeps 1L costs down"}`}
          stats={[[fmtPct1(m.trOut), "move up /yr"], [fmtMoneyK(m.netDebt), "est. cost"], [fmtPct(m.bar), "bar pass"]]} />
          )}
        </div>
      </section>

      <section className="tier-section">
        <div className="ts-head">
          <h2>Transfer-friendly targets<span className="colon">:</span></h2>
          <span className="count">{targets.length} schools</span>
        </div>
        <p className="ts-sub">Schools above your tier today that admit a meaningful transfer class every year</p>
        <div>
          {targets.length === 0 && <div className="muted">No reach schools with meaningful transfer classes for this profile.</div>}
          {targets.map((m) =>
          <TransferCard key={m.id} m={m} onOpen={onOpen}
          whyText={`Admits ~${m.trIn} transfers a year · 1L grades replace your LSAT here`}
          stats={[[String(m.trIn), "seats /yr"], [fmtPct(m.goalPct), goalLabel], [fmtRank(m.rank), "USNWR"]]} />
          )}
        </div>
      </section>
    </div>);

}

function exportCsv(results, pure) {
  const esc = (v) => {const s = String(v == null ? "" : v);return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;};
  const head = ["#", "School", "USNWR", "Tier", pure ? "Pure fit" : "Score", "LSAT 25/50/75", "GPA 25/50/75", "BigLaw %", "Bar %", "Cost after aid", "Monthly payment", "Starting salary"];
  const lines = [head, ...results.map((m, i) => [
  i + 1, m.name, fmtRank(m.rank), TIERS[m.tier].label, pure ? m.pure : m.composite,
  `${m.l25}/${m.l50}/${m.l75}`, `${m.g25}/${m.g50}/${m.g75}`,
  fmtPct(m.biglaw), fmtPct(m.bar), m.netDebt, m.monthly, m.salary]
  )];
  const csv = "\uFEFF" + lines.map((r) => r.map(esc).join(",")).join("\r\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "law-school-matches" + (pure ? "-purefit" : "") + ".csv";
  a.click();
  URL.revokeObjectURL(a.href);
}

function SaveMenu({ results, pure }) {
  const [open, setOpen] = React.useState(false);
  const [copied, setCopied] = React.useState(false);
  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);setTimeout(() => setCopied(false), 1500);
    } catch (e) {/* http clipboard unavailable */}
  };
  return (
    <div style={{ position: "relative" }}>
      <button className="btn sm ghost" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        {copied ? "copied ✓" : "save / share ▾"}</button>
      {open &&
      <div style={{ position: "absolute", right: 0, top: "110%", zIndex: 40, minWidth: 180,
        background: "var(--surface)", border: "1px solid var(--line2)", borderRadius: 10,
        boxShadow: "0 8px 22px rgba(28,25,23,0.16)", padding: 5 }}>
          {[["Copy share link", () => {track("share_copied");copyLink();setOpen(false);}],
        ["Export CSV", () => {track("export_csv");exportCsv(results, pure);setOpen(false);}],
        ["Print / save PDF", () => {track("print_results");window.print();setOpen(false);}]].map(([lbl, fn]) =>
        <button key={lbl} className="btn sm ghost" style={{ display: "block", width: "100%", textAlign: "left", border: "none" }}
        onClick={fn}>{lbl}</button>
        )}
        </div>
      }
    </div>);

}

/* ---- Apply Plan (portfolio) ---- */

const PORTFOLIO_BUCKETS = [
  { key: "safeties",  title: "Safeties",  sub: "Likely admits — anchor your list here.", tier: "safety" },
  { key: "targets",   title: "Targets",   sub: "Your numbers are at or near the median.", tier: "target" },
  { key: "reaches",   title: "Reaches",   sub: "Below their medians, but worth the shot.", tier: "reach"  },
  { key: "longshots", title: "Long shots", sub: "Below the 25th percentile — a flier, not a plan.", tier: "hard" },
];

const STRATEGY_OPTIONS = [
  { k: "aggressive", label: "Aggressive" },
  { k: "balanced",   label: "Balanced" },
  { k: "safe",       label: "Safe" },
];
const STRATEGY_BLURB = {
  aggressive: "Fewer safeties, more reaches — for applicants who'd rather re-apply than under-shoot.",
  balanced:   "A standard spread: a couple of safeties, a core of targets, a few reaches.",
  safe:       "A wider safety net and fewer reaches — for a cost- or certainty-first cycle.",
};

/* Risk posture + opt-in long shots. Changing either re-fetches the slate. */
function ApplyControls({ strategy, includeHard, onApplyChange }) {
  return (
    <div className="apply-controls">
      <div className="ac-row">
        <span className="ac-label">List strategy</span>
        <Seg options={STRATEGY_OPTIONS} value={strategy}
          onChange={(k) => onApplyChange({ strategy: k })} />
        <label className="checkbox-row" style={{ fontSize: 13, gap: 5, marginLeft: "auto" }}
          title="Surface a couple of hard reaches below the 25th percentile">
          <input type="checkbox" checked={!!includeHard}
            onChange={(e) => onApplyChange({ includeHard: e.target.checked })} />
          include long shots
        </label>
      </div>
      <p className="ts-sub" style={{ margin: 0 }}>{STRATEGY_BLURB[strategy] || ""}</p>
    </div>
  );
}

/* Application calendar — generic ABA cycle rhythm, with a profile-aware nudge. */
function ApplyTimeline({ profile }) {
  const steps = [];
  if (profile.lsat == null) {
    steps.push(["Lock your LSAT first",
      "Most files can't be read without a score on record. Get one before you build around these schools."]);
  }
  steps.push(
    ["Submit early (Sep–Nov)",
     "Almost all ABA schools admit on a rolling basis — the same file read in the fall beats February for both admission and aid."],
    ["Hit priority & scholarship deadlines (Nov–Jan)",
     "These fall well before the final regular deadline (Feb–Mar). Most merit money is committed by the late deadline."],
    ["Compare offers (Jan–Apr)",
     "Line up admit and aid letters side by side as they arrive — this is your negotiation window (see Scholarship strategy)."],
    ["Seat deposits (Apr–Jun)",
     "Schools hold your spot with a deposit (often $250–$1,000). Budget for one or two while you finalize."],
  );
  return (
    <section className="tier-section">
      <div className="ts-head"><h2>Timeline</h2></div>
      <p className="ts-sub">When to do what — the cycle rewards moving early.</p>
      <ol className="apply-timeline">
        {steps.map(([t, d]) => (
          <li key={t}><strong>{t}.</strong> {d}</li>
        ))}
      </ol>
    </section>
  );
}

/* Scholarship strategy — where merit aid is winnable + how to negotiate it.
   Leverage list is derived from the slate: schools where the applicant is at or
   above median (they pay to pull their numbers up). */
function ScholarshipStrategy({ portfolio, profile }) {
  const pool = [...(portfolio.safeties || []), ...(portfolio.targets || [])];
  const atOrAbove = (m) => profile.lsat != null
    ? (m.l50 != null && profile.lsat >= m.l50)
    : (m.scholarship != null && m.scholarship >= 70);
  const leverage = pool.filter(atOrAbove)
    .sort((a, b) => (b.scholarship || 0) - (a.scholarship || 0))
    .slice(0, 3);
  return (
    <section className="tier-section">
      <div className="ts-head"><h2>Scholarship strategy</h2></div>
      <p className="ts-sub">Merit aid is negotiable. Plan for it like part of the application.</p>
      {leverage.length > 0 && (
        <p style={{ marginTop: 4 }}>
          <strong>Most winnable here:</strong>{" "}
          {leverage.map((m) => m.name).join(", ")} — you're at or above their median,
          so they have a reason to pay to enroll you.
        </p>
      )}
      <ul className="apply-tips">
        <li><strong>Use competing offers.</strong> A bigger award from a peer school is leverage —
          ask another to match it in writing. Schools reconsider; there's no penalty for asking.</li>
        <li><strong>Aim safeties and strong targets for merit, not just admission.</strong>{" "}
          That's where you're most likely to land a half-to-full ride.</li>
        <li><strong>Request fee waivers.</strong> Via LSAC, law fairs, or the school directly — and
          CAS fee waivers exist for need. Don't let app fees cap how many schools you reach.</li>
      </ul>
    </section>
  );
}

function PortfolioBucketCard({ m, onOpen }) {
  const t = TIERS[m.tier] || TIERS.target;
  return (
    <div className="school-card" onClick={() => onOpen(m)} style={{ cursor: "pointer" }}>
      <ScoreRing value={m.composite} color={gradeColor(m.composite)} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
          <span className="sc-name">{m.name}</span>
          <span className="sc-meta">{m.loc} · USNWR {fmtRank(m.rank)}</span>
        </div>
        <div className="sc-why">
          <span className={`lead ${t.cls}`}>{t.label}.</span>{" "}
          {m.portfolioReason || m.why}
        </div>
      </div>
      <div className="sc-stats">
        <div className="sc-stat">
          <div className="v">{fmtMoneyK(m.netDebt)}</div>
          <div className="k">Est. cost</div>
        </div>
        <div className="sc-stat">
          <div className="v">{Math.round(m.composite)}</div>
          <div className="k">Score</div>
        </div>
      </div>
    </div>
  );
}

function PortfolioView({ portfolio, profile, strategy, includeHard, onApplyChange, onOpen }) {
  if (!portfolio) {
    return (
      <div className="tier-section">
        <p className="muted">Not enough schools across tiers to build a slate — add more profile detail or check your stats.</p>
      </div>
    );
  }

  const adaptNotes = portfolio.adaptNotes || [];

  return (
    <div>
      <ApplyControls strategy={strategy} includeHard={includeHard} onApplyChange={onApplyChange} />

      {adaptNotes.length > 0 &&
        <div className="apply-notes">
          {adaptNotes.map((n, i) => <p key={i} className="apply-note">{n}</p>)}
        </div>
      }

      {PORTFOLIO_BUCKETS.map(({ key, title, sub, tier }) => {
        const entries = portfolio[key] || [];
        // Long shots only appear when opted in; other buckets always show.
        if (key === "longshots" && !includeHard) return null;
        return (
          <section className="tier-section" key={key}>
            <div className="ts-head">
              <span className="dot" style={{ width: 10, height: 10, borderRadius: 99, background: TIERS[tier].color }}></span>
              <h2>{title}</h2>
              <span className="count">{entries.length} school{entries.length !== 1 ? "s" : ""}</span>
            </div>
            <p className="ts-sub">{sub}</p>
            {entries.length === 0
              ? <p className="muted" style={{ marginTop: 8 }}>No schools in this tier for your profile.</p>
              : <div>{entries.map((m) => <PortfolioBucketCard key={m.id} m={m} onOpen={onOpen} />)}</div>
            }
          </section>
        );
      })}

      <p className="muted" style={{ fontSize: 12, margin: "16px 0 8px" }}>
        Slate sizes are a starting point, not a rule — apply to as many as your time and budget allow.
      </p>

      <ApplyTimeline profile={profile} />
      <ScholarshipStrategy portfolio={portfolio} profile={profile} />
    </div>
  );
}

function ResultsScreen({ results, plan, portfolio, profile, whatIf, setWhatIf, onOpen, onEditProfile, compareIds, onToggleCompare, onClearCompare, onCompare, rview, setRview, tweakOpen, onTweakToggle, applyStrategy, includeHard, onApplyChange }) {
  const [pure, setPure] = React.useState(false);
  const [whatIfOpen, setWhatIfOpen] = React.useState(false);
  const goalLabel = GOAL_LABEL[profile.goal] || "BigLaw";

  const ranked = React.useMemo(
    () => pure ? [...results].sort((a, b) => b.pure - a.pure) : results,
    [results, pure]);

  const viewOpts = [
  { k: "guided", label: "Shortlist" },
  { k: "table", label: "Full table" },
  ...(profile.transfer ? [{ k: "transfers", label: "Transfer path" }] : []),
  ...(portfolio ? [{ k: "portfolio", label: "Apply plan" }] : [])];

  // Stale view guard: a re-submitted profile may have dropped the transfer intent,
  // or the portfolio may have disappeared on re-submit.
  const view = (rview === "transfers" && !profile.transfer) ||
               (rview === "portfolio" && !portfolio) ? "guided" : rview;

  const compareNames = results.filter((m) => compareIds.includes(m.id)).map((m) => m.name);

  return (
    <div>
      <div className="results-head">
        <div>
          <h1 className="display">Your matches, ranked<span className="colon">:</span></h1>
          <p>Every school scored for <em>your</em> numbers, goal, and budget</p>
        </div>
        <div className="profile-card">
          {[["LSAT", profile.noLsat ? "—" : profile.lsat], ["GPA", profile.gpa],
          ["Goal", goalLabel], ["Practice", (profile.practice || []).filter((p) => p.state).map((p) => p.state).join("·") || "—"]].map(([k, v]) =>
          <div className="pc-cell" key={k}><div className="k">{k}</div><div className="v">{v}</div></div>
          )}
          <button className="pc-edit" onClick={onEditProfile}>Edit</button>
        </div>
      </div>

      <div className="results-toolbar">
        <Seg options={viewOpts} value={view} onChange={(k) => {setRview(k);track("view_changed", k);if (k === "portfolio") track("apply_plan_opened");}} />
        <span className="spacer"></span>
        {onTweakToggle &&
          <button className={`twp-trigger${tweakOpen ? " active" : ""}`}
            aria-pressed={!!tweakOpen} onClick={onTweakToggle}
            title="Adjust how much each score dimension influences the ranking">
            <span className="dot"></span>
            Adjust weights
          </button>
        }
        {!profile.noLsat && view !== "transfers" && (whatIfOpen ?
        <span className="spin" title="What-if LSAT">
            <span className="spin-val" style={whatIf > 0 ? {} : { color: "var(--soft)" }}>{Math.min(profile.lsat + whatIf, 180)}</span>
            <span className="spin-btns">
              <button disabled={profile.lsat + whatIf >= 180} onClick={() => setWhatIf(whatIf + 1)} aria-label="Raise LSAT">+</button>
              <button disabled={whatIf <= 0} onClick={() => setWhatIf(whatIf - 1)} aria-label="Lower LSAT">−</button>
            </span>
            <button className="spin-x" aria-label="Close what-if"
          onClick={() => {setWhatIfOpen(false);setWhatIf(0);}}>×</button>
          </span> :
        <button className="btn sm primary" onClick={() => setWhatIfOpen(true)}>retake what-if</button>
        )}
        <label className="checkbox-row" style={{ fontSize: 13, gap: 5 }}
        title="Re-rank as if getting in weren't a factor">
          <input type="checkbox" checked={pure} onChange={(e) => {setPure(e.target.checked);track("pure_fit_toggled", e.target.checked ? "on" : "off");}} />
          ignore admissibility
          <InfoTip text="Re-ranks by fit alone, ignoring your odds of admission. Tiers still show." />
        </label>
        <SaveMenu results={ranked} pure={pure} />
      </div>

      {view === "guided" &&
      <GuidedView results={ranked} pure={pure} onOpen={onOpen} compareIds={compareIds}
      onToggleCompare={onToggleCompare} goalLabel={goalLabel} />
      }
      {view === "table" &&
      <TableView results={ranked} profile={profile} pure={pure} onOpen={onOpen}
      compareIds={compareIds} onToggleCompare={onToggleCompare} goalLabel={goalLabel} />
      }
      {view === "transfers" &&
      <TransfersView plan={plan} onOpen={onOpen} goalLabel={goalLabel} />
      }
      {view === "portfolio" &&
      <PortfolioView portfolio={portfolio} profile={profile} goalLabel={goalLabel}
      strategy={applyStrategy} includeHard={includeHard} onApplyChange={onApplyChange}
      onOpen={onOpen} />
      }

      {compareIds.length > 0 &&
      <div className="compare-tray">
          <span className="names">{compareIds.length} selected: {compareNames.join(", ")}</span>
          <button className="btn sm primary" disabled={compareIds.length < 2} onClick={onCompare}>
            Compare →</button>
          <button className="clear" onClick={onClearCompare}>Clear</button>
        </div>
      }
    </div>);

}

Object.assign(window, { ResultsScreen });
