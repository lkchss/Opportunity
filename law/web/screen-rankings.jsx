/* screen-rankings.jsx — the Docket: dense raw-data browser, no algorithm.
   Data: GET /api/schools (fetched and adapted by the app shell). */

const RK_COLS = [
{ k: "name", label: "School", l: true, sort: (s) => s.name,
  render: (s) => <td className="l school-cell"><span className="nm">{s.name}</span><span className="lc">{s.loc}</span></td> },
{ k: "rank", label: "Rank", sort: (s) => s.rank, render: (s) => <td>{fmtRank(s.rank)}</td> },
{ k: "lsat", label: "LSAT 25/50/75", sort: (s) => s.l50,
  render: (s) => <td>{s.l25}/{s.l50}/{s.l75}</td> },
{ k: "gpa", label: "GPA 50", sort: (s) => s.g50, render: (s) => <td>{fmtGpa(s.g50)}</td> },
{ k: "accept", label: "Accept", sort: (s) => s.accept, render: (s) => <td>{fmtPct(s.accept)}</td> },
{ k: "biglaw", label: "BigLaw", sort: (s) => s.biglaw,
  render: (s) => <td>{fmtPct(s.biglaw)}</td> },
{ k: "emp", label: "Employed", sort: (s) => s.emp, render: (s) => <td>{fmtPct(s.emp)}</td> },
{ k: "bar", label: "Bar", sort: (s) => s.bar, render: (s) => <td>{fmtPct(s.bar)}</td> },
{ k: "tuit", label: "Tuition", sort: (s) => s.tuitNon, render: (s) => <td>{fmtMoneyK(s.tuitNon)}</td> }];


/* percentile of a value among all schools (higher = better standing) */
function rkPctile(schools, key, v) {
  if (v == null) return null;
  const vals = schools.map((s) => s[key]).filter((x) => x != null);
  if (vals.length < 2) return null;
  const below = vals.filter((x) => x < v).length;
  return Math.round(below / (vals.length - 1) * 100);
}

function RawDetail({ s, schools }) {
  const row = (k, v, pkey) => {
    const p = pkey != null ? rkPctile(schools, pkey, s[pkey]) : null;
    return (
      <React.Fragment>
        <span className="k">{k}</span>
        <span className="v">{v}{p != null &&
          <span style={{ color: "var(--faint)", marginLeft: 6 }}>· {p}%</span>}
        </span>
      </React.Fragment>);
  };
  return (
    <div className="raw-detail">
      <div className="kv">
        {row("Acceptance rate", fmtPct(s.accept))}
        {row("1L class size", s.size == null ? "—" : s.size)}
        {row("BigLaw %", fmtPct(s.biglaw), "biglaw")}
        {row("Fed. clerkship %", fmtPct(s.clerk), "clerk")}
        {row("Government %", fmtPct(s.gov), "gov")}
        {row("Public interest %", fmtPct(s.pi), "pi")}
        {row("Employed @10 mo", fmtPct(s.emp), "emp")}
        {row("Bar pass (first-time)", fmtPct(s.bar), "bar")}
        {row("Bar pass (ultimate)", fmtPct(s.barUlt), "barUlt")}
      </div>
      <div className="kv">
        {row("Resident tuition", fmtMoney(s.tuitRes))}
        {row("Nonresident tuition", fmtMoney(s.tuitNon))}
        {row("Living budget /yr", fmtMoney(s.living))}
        {row("Any-grant rate", fmtPct(s.grantRate), "grantRate")}
        {row("Median grant /yr", fmtMoney(s.medGrant), "medGrant")}
        {row("Transfers in / out rate", `${s.trIn == null ? "—" : s.trIn} / ${fmtPct1(s.trOut)}`)}
        {row("Real grad debt · earnings @4yr", `${fmtMoneyK(s.scDebt)} · ${fmtMoneyK(s.scEarn)}`)}
      </div>
      <div className="mono" style={{ gridColumn: "1 / -1" }}>
        <a href={schoolSite(s)} target="_blank" rel="noreferrer" onClick={() => track("school_site_clicked")}>About the school ↗</a>
      </div>
    </div>);

}

function RankingsScreen({ schools, error, onRetry }) {
  const [q, setQ] = React.useState("");
  const [stateFilter, setStateFilter] = React.useState("");
  const [sortKey, setSortKey] = React.useState("rank");
  const [asc, setAsc] = React.useState(true);
  const [openId, setOpenId] = React.useState(null);

  const list = React.useMemo(() => {
    if (!schools) return [];
    const needle = q.trim().toLowerCase();
    let rows = schools;
    if (needle) rows = rows.filter((s) => s.name.toLowerCase().includes(needle) || (s.loc || "").toLowerCase().includes(needle));
    if (stateFilter) rows = rows.filter((s) => s.state === stateFilter);
    const col = RK_COLS.find((c) => c.k === sortKey);
    if (col) rows = [...rows].sort((a, b) => {
      const av = col.sort(a),bv = col.sort(b);
      return (av < bv ? -1 : av > bv ? 1 : 0) * (asc ? 1 : -1);
    });
    return rows;
  }, [schools, q, stateFilter, sortKey, asc]);

  const onHeader = (col) => {
    if (sortKey === col.k) setAsc((v) => !v);else
    {setSortKey(col.k);setAsc(["rank", "name", "accept", "tuit"].includes(col.k));}
  };

  return (
    <div>
      <div className="results-head">
        <div>
          <h1 className="display">All schools<span className="colon">:</span></h1>
          <p>
            <span className="mono">{schools ? `${schools.length} ABA-accredited schools · ABA 509 + College Scorecard data` : ""}</span></p>
        </div>
        <div style={{ display: "flex", gap: 8, flex: "none" }}>
          <input type="text" placeholder="Search school or city…" value={q} style={{ width: 220 }}
          aria-label="Search schools by name or city"
          onChange={(e) => setQ(e.target.value)} />
          <select value={stateFilter} aria-label="Filter by state"
            onChange={(e) => setStateFilter(e.target.value)}>
            <option value="">All states</option>
            {STATES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>

      {error &&
      <div className="center-msg">
        Could not load the school data.
        <div style={{ marginTop: 16 }}><button className="btn primary" onClick={onRetry}>Retry</button></div>
      </div>
      }
      {!error && !schools &&
      <div className="center-msg"><div className="spinner" />Loading schools…</div>
      }

      {!error && schools &&
      <div className="dense-wrap">
        <table className="dense">
          <thead>
            <tr>
              {RK_COLS.map((c) =>
              <th key={c.k} className={c.l ? "l" : ""} onClick={() => onHeader(c)}>
                  {c.label}{sortKey === c.k && <span className="arrow">{asc ? " ▲" : " ▼"}</span>}
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {list.map((s) =>
            <React.Fragment key={s.id}>
                <tr tabIndex={0}
              onClick={() => setOpenId(openId === s.id ? null : s.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setOpenId(openId === s.id ? null : s.id);
                }
              }}>
                  {RK_COLS.map((c) => <React.Fragment key={c.k}>{c.render(s)}</React.Fragment>)}
                </tr>
                {openId === s.id &&
              <tr className="raw-detail-row">
                    <td colSpan={RK_COLS.length} className="l"><RawDetail s={s} schools={schools} /></td>
                  </tr>
              }
              </React.Fragment>
            )}
          </tbody>
        </table>
        {list.length === 0 && <div className="center-msg">No schools match your search.</div>}
        <div className="table-foot">
          <span>{list.length} SCHOOLS</span>
          <span>SORT: {RK_COLS.find((c) => c.k === sortKey).label.toUpperCase()} {asc ? "ASC" : "DESC"}</span>
          <span className="right">CLICK ROW → FULL DATA SHEET</span>
        </div>
      </div>
      }
    </div>);

}

window.RankingsScreen = RankingsScreen;
