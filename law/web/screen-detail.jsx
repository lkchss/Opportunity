/* screen-detail.jsx — single school: hero, three questions, financial detail. */

const DETAIL_YEARS = [1, 3, 5, 8, 10];

function buildSchedule(debt, monthlyPayment) {
  const r = 0.07 / 12;
  let balance = debt;
  const out = {};
  for (let year = 1; year <= 10; year++) {
    const start = balance;
    let paid = 0;
    for (let mth = 0; mth < 12; mth++) {
      const interest = balance * r;
      const pay = Math.min(monthlyPayment, balance + interest);
      balance = Math.max(balance + interest - pay, 0);
      paid += pay;
    }
    out[year] = { year, start, paid, end: balance };
  }
  return DETAIL_YEARS.map((y) => out[y]);
}

function ScheduleTable({ rows, forgivenLast }) {
  return (
    <table className="schedule">
      <thead><tr><th>Year</th><th>Balance start</th><th>Paid</th><th>Balance end</th></tr></thead>
      <tbody>
        {rows.map((row, idx) => (
          <tr key={row.year}>
            <td>{row.year}</td>
            <td>{fmtMoneyK(row.start)}</td>
            <td>{fmtMoneyK(row.paid)}</td>
            <td>{forgivenLast && idx === rows.length - 1 ? "forgiven" : fmtMoneyK(row.end)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* number line: 25th–median–75th with a dot for the user */
function RangeLine({ label, lo, mid, hi, you, fmt }) {
  const f = fmt || ((v) => v);
  const pos = (v) => {
    const span = hi - lo || 1;
    if (v <= lo) return Math.max(3, 15 - (lo - v) / span * 70);
    if (v <= mid) return 15 + (v - lo) / (mid - lo || 1) * 35;
    if (v <= hi) return 50 + (v - mid) / (hi - mid || 1) * 35;
    return Math.min(97, 85 + (v - hi) / span * 70);
  };
  return (
    <div className="range-line">
      <div className="rl-label">{label}</div>
      <div className="rl-wrap">
        <div className="rl-track"></div>
        {[[lo, 15], [mid, 50], [hi, 85]].map(([v, p]) => (
          <React.Fragment key={p}>
            <span className="rl-tick" style={{ left: `${p}%` }}></span>
            <span className="rl-tick-label" style={{ left: `${p}%` }}>{f(v)}</span>
          </React.Fragment>
        ))}
        {you != null && (
          <span className="rl-you" style={{ left: `${pos(you)}%` }}>
            <span className="rl-you-val">{f(you)}</span>
          </span>
        )}
      </div>
    </div>
  );
}

/* Render a one-line selectivity trend summary, or null when unavailable.
   Hidden when fewer than 2 years of data exist (selTrend is null in that case). */
function SelTrendLine({ trend }) {
  if (!trend || !trend.years || trend.years.length < 2) return null;
  const yrs = trend.years;
  const first = yrs[0], last = yrs[yrs.length - 1];
  const lsats = trend.lsat_50;
  const accs  = trend.accept_rate;
  const lsatStr = lsats.join("→");   // →
  const accStr  = accs.map((a) => a != null ? Math.round(a * 100) + "%" : "—").join("→");
  return (
    <div className="selectivity-trend mono" style={{ fontSize: "0.78rem", color: "var(--fg2)", marginTop: 4 }}>
      Selectivity trend ({first}–{last}): LSAT median {lsatStr}, acceptance {accStr}
    </div>
  );
}

function DetailScreen({ m, profile, onBack }) {
  const userLsat = profile.noLsat ? null : profile.lsat;
  const stdRows = buildSchedule(m.totalDebt, m.monthly);
  // PSLF numbers come from the matcher (IDR net of LRAP); fall back to an
  // estimate only if a stale payload lacks them.
  const idrMonthly = m.idrMonthly != null ? m.idrMonthly : Math.round(m.monthly * 0.38);
  const idrRows = m.pslf ? buildSchedule(m.totalDebt, idrMonthly) : null;
  const pslfPaid = m.pslfPaid != null ? m.pslfPaid : idrMonthly * 120;
  const pslfForgiven = m.pslfForgiven != null ? m.pslfForgiven
    : Math.max(Math.round(m.totalDebt * 1.35 - idrMonthly * 120), 0);
  const alumni = (m.alumni || []).slice(0, 8);
  const goalKey = GOAL_KEY[profile.goal] || "biglaw";
  const goalStat = {
    biglaw: ["BigLaw", fmtPct(m.biglaw)], clerk: ["Fed clerk", fmtPct(m.clerk)],
    gov: ["Government", fmtPct(m.gov)], pi: ["Pub interest", fmtPct(m.pi)],
    solo: ["Solo/small", fmtPct(m.solo)]
  }[goalKey];

  return (
    <div>
      <div className="crumb"><button className="btn sm ghost" onClick={onBack}>← Back to results</button></div>
      <div className="detail-head">
        <div>
          <h1 className="display">{m.name}<span className="colon">:</span></h1>
          <div className="sub">{m.loc} · USNWR {fmtRank(m.rank)} · class of {m.size}</div>
        </div>
        <div className="head-right">
          <div className="ms-block">
            <div className="ms-top">
              <TierPill tier={m.tier} />
              <span className="ms-num">{Math.round(m.composite)}<span className="ms-denom"> /100</span></span>
            </div>
            <div className="ms-scale">
              <div className="ms-fill" style={{ width: `${clamp(m.composite)}%`, background: gradeColor(m.composite) }}></div>
            </div>
            <div className="ms-labels"><span>0</span><span>match score</span><span>100</span></div>
          </div>
          <a className="mono" href={schoolSite(m)} target="_blank" rel="noreferrer" onClick={() => track("school_site_clicked")}>More about the school ↗</a>
        </div>
      </div>

      <div className="detail-hero">
        <div style={{ display: "flex", justifyContent: "center" }}>
          <Radar scores={m.radar} size={270} />
        </div>
        <div>
          <div className="stat-grid">
            <Stat label="LSAT 50" value={m.l50 == null ? "—" : m.l50}
              sub={m.l25 != null && m.l75 != null ? `25/75: ${m.l25}·${m.l75}` : undefined} />
            <Stat label="GPA 50" value={fmtGpa(m.g50)} sub={`25/75: ${fmtGpa(m.g25)}·${fmtGpa(m.g75)}`} />
            <Stat label="Acceptance" value={fmtPct(m.accept)} />
            <Stat label={goalStat[0]} value={goalStat[1]} />
            <Stat label="Bar pass" value={fmtPct(m.bar)} />
          </div>
          <div className="score-bars">
            {SCORE_NAMES_LONG.map((n, i) => (
              <Bar key={n} value={m.radar[i]} label={n} />
            ))}
          </div>
        </div>
      </div>

      <div className="story-cols">
        <div className="story-col">
          <h2>Will you get in?
            <InfoTip text="Tier reflects how your numbers sit against the class 25/50/75. Not a prediction of admission." /></h2>
          <RangeLine label="LSAT" lo={m.l25} mid={m.l50} hi={m.l75} you={userLsat} />
          <RangeLine label="GPA" lo={m.g25} mid={m.g50} hi={m.g75} you={profile.gpa}
            fmt={(v) => Number(v).toFixed(2)} />
          <div className="verdict"><TierPill tier={m.tier} /></div>
          <SelTrendLine trend={m.selTrend} />
          <div className="kv">
            <span className="k">1L attrition</span><span className="v">{fmtPct1(m.attr)}</span>
            <span className="k">Transfer out / in</span><span className="v">{fmtPct1(m.trOut)} · {m.trIn == null ? "—" : m.trIn + "/yr"}</span>
            {m.cond && <React.Fragment>
              <span className="k t-reach" style={{ fontWeight: 600 }}>Conditional scholarships
                <InfoTip text="Aid can be revoked if your GPA slips below a stipulation. Ask what share of 1Ls keep theirs." /></span>
              <span className="v">ask</span>
            </React.Fragment>}
          </div>
        </div>

        <div className="story-col">
          <h2>Will you get the job?
            <InfoTip text="Share of the graduating class landing each outcome. Your goal row is highlighted." /></h2>
          <div className="kv">
            <span className={`k ${goalKey === "biglaw" ? "goal" : ""}`}>BigLaw</span>
            <span className={`v ${goalKey === "biglaw" ? "goal" : ""}`}>{fmtPct(m.biglaw)}</span>
            <span className={`k ${goalKey === "clerk" ? "goal" : ""}`}>Fed. clerkship</span>
            <span className={`v ${goalKey === "clerk" ? "goal" : ""}`}>{fmtPct(m.clerk)}</span>
            <span className={`k ${goalKey === "gov" ? "goal" : ""}`}>Government</span>
            <span className={`v ${goalKey === "gov" ? "goal" : ""}`}>{fmtPct(m.gov)}</span>
            <span className={`k ${goalKey === "pi" ? "goal" : ""}`}>Public interest</span>
            <span className={`v ${goalKey === "pi" ? "goal" : ""}`}>{fmtPct(m.pi)}</span>
            <span className={`k ${goalKey === "solo" ? "goal" : ""}`}>Solo / small firm</span>
            <span className={`v ${goalKey === "solo" ? "goal" : ""}`}>{fmtPct(m.solo)}</span>
          </div>
          <div className="kv" style={{ borderTop: "1px solid var(--line)", paddingTop: 10 }}>
            <span className="k">Bar pass (first · ultimate)</span><span className="v">{fmtPct(m.bar)} · {fmtPct(m.barUlt)}</span>
            <span className="k">Employed @10 mo</span><span className="v">{fmtPct(m.emp)}</span>
            <span className="k">Feeder markets</span><span className="v">{m.feeds.length ? m.feeds.join(" · ") : "—"}</span>
          </div>
        </div>

        <div className="story-col">
          <h2>Can you afford it?
            <InfoTip text="Blends the school's aid grid, your numbers, your savings, and typical pay for your goal. Always negotiate." /></h2>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <div><div className="mono">est. cost after aid</div><div className="big-num">{fmtMoneyK(m.netDebt)}</div></div>
            <div style={{ textAlign: "right" }}><div className="mono">starting salary</div><div className="big-num">{fmtMoneyK(m.salary)}</div></div>
          </div>
          <div className="kv">
            <span className="k">Monthly payment (10-yr)</span><span className="v">{fmtMoney(m.monthly)}</span>
            <span className="k">Debt-to-income</span><span className="v">{m.dti}×</span>
            <span className="k">Tuition basis</span><span className="v">{m.instate ? "in-state" : m.isPublic ? "out-of-state" : "private"}</span>
            <span className="k">Real grads: debt · earnings
              <InfoTip text="College Scorecard medians: actual federal debt and earnings four years out." /></span>
            <span className="v">{fmtMoneyK(m.scDebt)} · {fmtMoneyK(m.scEarn)}</span>
            {m.placementStates && m.placementStates.length > 0 && (
              <React.Fragment>
                <span className="k">Where grads work</span>
                <span className="v" data-testid="placement-states">
                  {m.placementStates.map((p) => `${p.state} ${p.pct}%`).join(" · ")}
                  {m.placementYear ? ` (Class of ${m.placementYear})` : ""}
                </span>
              </React.Fragment>
            )}
          </div>
        </div>
      </div>

      {m.leverage && m.leverage.above_both_medians && (
        <div className="detail-section leverage-block" data-testid="leverage-block">
          <h2 className="display">Negotiation leverage</h2>
          <div className="panel" style={{ maxWidth: 640 }}>
            <div className="label" style={{ marginBottom: 10 }}>
              Your LSAT and GPA are both at or above this school&#39;s 50th-percentile medians
              <InfoTip text="When your numbers clear both medians, you have real bargaining power. Schools compete for applicants who lift their reported stats." />
            </div>
            <div className="kv">
              {m.leverage.pct_half_plus != null && (
                <React.Fragment>
                  <span className="k">Students receiving half tuition or more</span>
                  <span className="v">{m.leverage.pct_half_plus}%</span>
                  <span className="k">Students receiving a full ride</span>
                  <span className="v">{m.leverage.pct_full}%</span>
                </React.Fragment>
              )}
            </div>
            <div className="mono" style={{ marginTop: 10, lineHeight: 1.5 }}>{m.leverage.note}</div>
          </div>
        </div>
      )}

      {alumni.length > 0 && (
        <div className="detail-section">
          <h2 className="display">Notable alumni</h2>
          <div className="people-list">
            {alumni.map((a) => (
              <a key={a.name} className="person" href={a.url || wiki(a.name)} target="_blank" rel="noreferrer">{a.name}</a>
            ))}
          </div>
          <div className="mono" style={{ marginTop: 8 }}>Source: Wikipedia</div>
        </div>
      )}

      <div className="detail-section">
        <h2 className="display">Financial detail</h2>

        <div style={{ display: "flex", gap: 18, flexWrap: "wrap", alignItems: "flex-start" }}>
          <div className="panel" style={{ flex: "1 1 320px", maxWidth: 480 }}>
            <div className="label" style={{ marginBottom: 12 }}>Standard repayment — 10-yr @ 7%
              <InfoTip text="Pays the balance off in ten years on a private-sector salary. Aid is estimated; always negotiate." /></div>
            <div className="ledger">
              <div className="lr"><span>Tuition × 3 yrs</span><span className="amt">{fmtMoney(m.tuition * 3)}</span></div>
              <div className="lr"><span>Living × 3 yrs</span><span className="amt">{fmtMoney(m.living * 3)}</span></div>
              <div className="lr subtotal"><span>Gross cost</span><span className="amt">{fmtMoney(m.gross)}</span></div>
              <div className="lr"><span>Est. aid</span><span className="amt">−{fmtMoney(m.aid3)}</span></div>
              {m.cashApplied > 0 &&
                <div className="lr"><span>Savings applied</span><span className="amt">−{fmtMoney(m.cashApplied)}</span></div>}
              <div className={`lr ${m.existingDebt > 0 ? "subtotal" : "total"}`}><span>Borrowed</span><span className="amt">{fmtMoney(m.netDebt)}</span></div>
              {m.existingDebt > 0 && <React.Fragment>
                <div className="lr"><span>Existing student debt</span><span className="amt">+{fmtMoney(m.existingDebt)}</span></div>
                <div className="lr total"><span>Total debt</span><span className="amt">{fmtMoney(m.totalDebt)}</span></div>
              </React.Fragment>}
            </div>
            <div className="ledger" style={{ marginTop: 14 }}>
              <div className="lr"><span>Starting salary</span><span className="amt">{fmtMoney(m.salary)}</span></div>
              <div className="lr"><span>Monthly payment</span><span className="amt">{fmtMoney(m.monthly)}</span></div>
              <div className="lr"><span>Debt-to-income</span><span className="amt">{m.dti}×</span></div>
            </div>
          </div>

          <div className="panel" style={{ flex: "1 1 300px", maxWidth: 420 }}>
            <div className="label" style={{ marginBottom: 8 }}>Year-by-year — standard plan</div>
            <ScheduleTable rows={stdRows} forgivenLast={false} />
          </div>

          {m.pslf && (
            <div className="panel" style={{ flex: "1 1 320px", maxWidth: 480 }}>
              <div className="label" style={{ marginBottom: 12 }}>PSLF / IDR path
                <InfoTip text="Government or 501(c)(3) employers only. After 120 qualifying payments the rest is forgiven tax-free; confirm at studentaid.gov." /></div>
              <div className="ledger">
                <div className="lr"><span>IDR monthly (est.)</span><span className="amt">{fmtMoney(idrMonthly)}</span></div>
                <div className="lr"><span>Total paid over 10 yrs</span><span className="amt">{fmtMoney(pslfPaid)}</span></div>
                <div className="lr total"><span>Forgiven at year 10</span><span className="amt">{fmtMoney(pslfForgiven)}</span></div>
              </div>
              {idrRows && (
                <div style={{ marginTop: 14 }}>
                  <div className="label" style={{ marginBottom: 8 }}>Year-by-year — IDR</div>
                  <ScheduleTable rows={idrRows} forgivenLast={true} />
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

window.DetailScreen = DetailScreen;
