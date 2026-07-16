/* screen-compare.jsx — side-by-side: overlay radar + best-value table. */

const CMP_PERSONAL = [
  { label: "Admit tier", better: null, cell: (m) => ({ num: null, node: <TierPill tier={m.tier} /> }) },
  { label: "Match score", better: "high", cell: (m) => ({ num: m.composite, node: Math.round(m.composite) }) },
  { label: "Career fit", better: "high", cell: (m) => ({ num: m.career, node: m.career }) },
  { label: "Location fit", better: "high", cell: (m) => ({ num: m.location, node: m.location }) },
  { label: "Scholarship", better: "high", cell: (m) => ({ num: m.scholarship, node: m.scholarship }) },
  { label: "Est. cost after aid", better: "low", cell: (m) => ({ num: m.netDebt, node: fmtMoney(m.netDebt) }) },
  { label: "Monthly payment", better: "low", cell: (m) => ({ num: m.monthly, node: fmtMoney(m.monthly) }) },
  { label: "Debt / income", better: "low", cell: (m) => ({ num: m.dti, node: m.dti + "×" }) },
  { label: "Tuition basis", better: null, cell: (m) => ({ num: null, node: m.instate ? "in-state" : m.isPublic ? "out-of-state" : "private" }) },
];

const CMP_RAW = [
  { label: "USNWR rank", better: "low", cell: (m) => ({ num: m.rank, node: fmtRank(m.rank) }) },
  { label: "Acceptance rate", better: "low", cell: (m) => ({ num: m.accept, node: fmtPct(m.accept) }) },
  { label: "LSAT 25/50/75", better: null, cell: (m) => ({ num: null, node: m.l25 == null ? "—" : `${m.l25} · ${m.l50} · ${m.l75}` }) },
  { label: "GPA 25/50/75", better: null, cell: (m) => ({ num: null, node: `${fmtGpa(m.g25)} · ${fmtGpa(m.g50)} · ${fmtGpa(m.g75)}` }) },
  { label: "BigLaw %", better: "high", cell: (m) => ({ num: m.biglaw, node: fmtPct(m.biglaw) }) },
  { label: "Fed. clerkship %", better: "high", cell: (m) => ({ num: m.clerk, node: fmtPct(m.clerk) }) },
  { label: "Government %", better: "high", cell: (m) => ({ num: m.gov, node: fmtPct(m.gov) }) },
  { label: "Public interest %", better: "high", cell: (m) => ({ num: m.pi, node: fmtPct(m.pi) }) },
  { label: "Bar pass (first-time)", better: "high", cell: (m) => ({ num: m.bar, node: fmtPct(m.bar) }) },
  { label: "Bar pass (ultimate)", better: "high", cell: (m) => ({ num: m.barUlt, node: fmtPct(m.barUlt) }) },
  { label: "Employed @10 mo", better: "high", cell: (m) => ({ num: m.emp, node: fmtPct(m.emp) }) },
  { label: "Sticker tuition /yr", better: "low", cell: (m) => ({ num: m.tuitNon, node: fmtMoney(m.tuitNon) }) },
  { label: "Real grad fed debt", better: "low", cell: (m) => ({ num: m.scDebt, node: fmtMoneyK(m.scDebt) }) },
  { label: "Real grad earnings @4 yr", better: "high", cell: (m) => ({ num: m.scEarn, node: fmtMoneyK(m.scEarn) }) },
];

function bestIdx(cells, better) {
  if (!better) return new Set();
  const nums = cells.map((c) => c.num).filter((n) => n != null && !Number.isNaN(n));
  if (!nums.length) return new Set();
  const best = better === "high" ? Math.max(...nums) : Math.min(...nums);
  const set = new Set();
  cells.forEach((c, i) => { if (c.num === best) set.add(i); });
  return set;
}

function CompareScreen({ schools, profile, onBack, onRemove }) {
  const [mode, setMode] = React.useState("personal");
  const rows = mode === "personal" ? CMP_PERSONAL : CMP_RAW;

  if (schools.length < 2) {
    return (
      <div>
        <div className="crumb"><button className="btn sm ghost" onClick={onBack}>← Back to results</button></div>
        <div className="center-msg">
          Select at least two schools to compare — use the <strong>＋</strong> button on any school card.
          <div style={{ marginTop: 16 }}>
            <button className="btn primary" onClick={onBack}>← Back to results</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="crumb"><button className="btn sm ghost" onClick={onBack}>← Back to results</button></div>
      <div className="results-head" style={{ paddingTop: 14 }}>
        <div>
          <h1 className="display">Side by side<span className="colon">:</span></h1>
          <p>Green cells mark the best value in each row.</p>
        </div>
      </div>

      <div className="compare-legend">
        <RadarOverlay series={schools.map((m, i) => ({ scores: m.radar, color: SERIES_COLORS[i % SERIES_COLORS.length] }))} size={300} />
        <div className="legend-list">
          {schools.map((m, i) => (
            <div key={m.id} className="legend-row">
              <span className="swatch" style={{ background: SERIES_COLORS[i % SERIES_COLORS.length] }}></span>
              <div>
                <div className="nm">{m.name}</div>
                <div className="meta">{fmtRank(m.rank)} · {TIERS[m.tier].label} · Score {Math.round(m.composite)}</div>
              </div>
              <button className="btn xs ghost" onClick={() => onRemove(m.id)}>remove</button>
            </div>
          ))}
        </div>
      </div>

      <div className="tabs" style={{ marginTop: 18 }}>
        <button className={`tab ${mode === "personal" ? "active" : ""}`} onClick={() => setMode("personal")}>With your numbers</button>
        <button className={`tab ${mode === "raw" ? "active" : ""}`} onClick={() => setMode("raw")}>Raw school stats</button>
      </div>

      <div style={{ overflowX: "auto" }}>
        <table className="compare-table">
          <thead>
            <tr>
              <th className="metric-col"><span className="sr-only">Metric</span></th>
              {schools.map((m) => (
                <th key={m.id}>
                  <div className="nm">{m.name}</div>
                  <div className="mono">{m.loc} · {fmtRank(m.rank)}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const cells = schools.map((m) => row.cell(m));
              const best = bestIdx(cells, row.better);
              return (
                <tr key={row.label}>
                  <td className="metric-col">{row.label}</td>
                  {cells.map((cc, i) => (
                    <td key={i} className={best.has(i) ? "best" : ""}>{cc.node}</td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {mode === "personal" && (
        <div className="note" style={{ marginTop: 16 }}>
          Scores and costs reflect your profile (LSAT {profile.noLsat ? "—" : profile.lsat}, GPA {profile.gpa},
          goal {profile.goal}). Switch to <strong>Raw school stats</strong> to compare published numbers,
          independent of you.
        </div>
      )}
    </div>
  );
}

window.CompareScreen = CompareScreen;
